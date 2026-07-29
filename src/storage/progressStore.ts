import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';
import {
  DailyStats,
  ProgressEntry,
  UserData,
  VocabEntry,
} from '../types';
import {
  AUTO_GOOD,
  FORGOT,
  ReviewQuality,
  createInitialSm2,
  isDue,
  reviewSm2,
  todayIso,
} from '../srs/sm2';

const USER_DATA_FILE = 'user-data.json';

function emptyUserData(): UserData {
  return {
    vocabularyBook: [],
    progress: {},
    dailyStats: {},
  };
}

export class ProgressStore {
  private data: UserData;
  private readonly filePath: string;
  private dictionary: VocabEntry[] = [];
  private byId = new Map<string, VocabEntry>();
  private byWord = new Map<string, VocabEntry>();

  constructor(private readonly context: vscode.ExtensionContext) {
    this.filePath = path.join(context.globalStorageUri.fsPath, USER_DATA_FILE);
    this.data = emptyUserData();
  }

  async init(): Promise<void> {
    await fs.promises.mkdir(this.context.globalStorageUri.fsPath, { recursive: true });
    await this.loadUserData();
    await this.loadDictionary();
  }

  private async loadUserData(): Promise<void> {
    try {
      const raw = await fs.promises.readFile(this.filePath, 'utf8');
      this.data = { ...emptyUserData(), ...JSON.parse(raw) };
    } catch {
      this.data = emptyUserData();
      await this.save();
    }
  }

  private async loadDictionary(): Promise<void> {
    const dictPath = path.join(this.context.extensionPath, 'data', 'french.json');
    const raw = await fs.promises.readFile(dictPath, 'utf8');
    const parsed = JSON.parse(raw) as { words: VocabEntry[] };
    this.dictionary = parsed.words;
    this.byId.clear();
    this.byWord.clear();
    for (const entry of this.dictionary) {
      this.byId.set(entry.id, entry);
      this.byWord.set(entry.word.toLowerCase(), entry);
    }
  }

  async save(): Promise<void> {
    await fs.promises.mkdir(path.dirname(this.filePath), { recursive: true });
    await fs.promises.writeFile(this.filePath, JSON.stringify(this.data, null, 2), 'utf8');
  }

  getDictionary(): VocabEntry[] {
    return this.dictionary;
  }

  getEntry(id: string): VocabEntry | undefined {
    return this.byId.get(id);
  }

  lookup(query: string): VocabEntry[] {
    const q = query.trim().toLowerCase();
    if (!q) {
      return [];
    }
    const exact = this.byWord.get(q);
    if (exact) {
      return [exact];
    }
    return this.dictionary
      .filter(
        (e) =>
          e.word.toLowerCase().includes(q) ||
          e.meaning.toLowerCase().includes(q)
      )
      .slice(0, 25);
  }

  getBookEntries(): VocabEntry[] {
    return this.data.vocabularyBook
      .map((id) => this.byId.get(id))
      .filter((e): e is VocabEntry => Boolean(e));
  }

  isInBook(id: string): boolean {
    return this.data.vocabularyBook.includes(id);
  }

  async addToBook(id: string): Promise<boolean> {
    if (!this.byId.has(id) || this.data.vocabularyBook.includes(id)) {
      return false;
    }
    this.data.vocabularyBook.push(id);
    await this.save();
    return true;
  }

  async removeFromBook(id: string): Promise<void> {
    this.data.vocabularyBook = this.data.vocabularyBook.filter((x) => x !== id);
    await this.save();
  }

  getProgress(id: string): ProgressEntry | undefined {
    return this.data.progress[id];
  }

  getDailyStats(date = todayIso()): DailyStats {
    if (!this.data.dailyStats[date]) {
      this.data.dailyStats[date] = {
        date,
        reviews: 0,
        newWords: 0,
        forgot: 0,
        remembered: 0,
      };
    }
    return this.data.dailyStats[date];
  }

  /**
   * Build today's study queue: due reviews first, then new words up to daily limit.
   * Prefer vocabulary-book words, then general dictionary.
   */
  buildStudyQueue(dailyNewLimit: number): VocabEntry[] {
    const today = todayIso();
    const bookIds = new Set(this.data.vocabularyBook);
    const due: VocabEntry[] = [];
    const newOnes: VocabEntry[] = [];

    const consider = (entry: VocabEntry) => {
      const p = this.data.progress[entry.id];
      if (!p) {
        newOnes.push(entry);
      } else if (isDue(p.sm2, today)) {
        due.push(entry);
      }
    };

    // Book words first
    for (const id of this.data.vocabularyBook) {
      const e = this.byId.get(id);
      if (e) {
        consider(e);
      }
    }

    // Then rest of dictionary
    for (const entry of this.dictionary) {
      if (bookIds.has(entry.id)) {
        continue;
      }
      consider(entry);
    }

    const todayStats = this.getDailyStats(today);
    const remainingNew = Math.max(0, dailyNewLimit - todayStats.newWords);
    const selectedNew = newOnes.slice(0, remainingNew);

    // Stable-ish order: due (older due first by dueDate), then new
    due.sort((a, b) => {
      const da = this.data.progress[a.id]?.sm2.dueDate ?? today;
      const db = this.data.progress[b.id]?.sm2.dueDate ?? today;
      return da.localeCompare(db);
    });

    const queue = [...due, ...selectedNew];
    this.data.lastSessionWordIds = queue.map((e) => e.id);
    this.data.lastSessionIndex = 0;
    void this.save();
    return queue;
  }

  restoreSession(): VocabEntry[] {
    const ids = this.data.lastSessionWordIds ?? [];
    return ids.map((id) => this.byId.get(id)).filter((e): e is VocabEntry => Boolean(e));
  }

  getLastSessionIndex(): number {
    return this.data.lastSessionIndex ?? 0;
  }

  async setSessionIndex(index: number): Promise<void> {
    this.data.lastSessionIndex = index;
    await this.save();
  }

  async recordReview(wordId: string, quality: ReviewQuality = AUTO_GOOD): Promise<ProgressEntry> {
    const today = todayIso();
    const stats = this.getDailyStats(today);
    let entry = this.data.progress[wordId];
    const isNew = !entry;

    if (!entry) {
      entry = {
        wordId,
        sm2: createInitialSm2(today),
        reviewCount: 0,
        forgotCount: 0,
        introducedAt: today,
      };
      stats.newWords += 1;
    }

    entry.sm2 = reviewSm2(entry.sm2, quality, today);
    entry.reviewCount += 1;
    stats.reviews += 1;

    if (quality < 3) {
      entry.forgotCount += 1;
      stats.forgot += 1;
    } else {
      stats.remembered += 1;
    }

    this.data.progress[wordId] = entry;
    await this.save();
    return entry;
  }

  async markForgot(wordId: string): Promise<ProgressEntry> {
    return this.recordReview(wordId, FORGOT);
  }

  getProgressSummary(): {
    totalLearned: number;
    dueToday: number;
    bookSize: number;
    today: DailyStats;
  } {
    const today = todayIso();
    const dueToday = Object.values(this.data.progress).filter((p) => isDue(p.sm2, today)).length;
    return {
      totalLearned: Object.keys(this.data.progress).length,
      dueToday,
      bookSize: this.data.vocabularyBook.length,
      today: this.getDailyStats(today),
    };
  }
}
