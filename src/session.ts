import * as vscode from 'vscode';
import { ProgressStore } from './storage/progressStore';
import { StudyCard, VocabEntry, ViewMode } from './types';
import { isDue, todayIso } from './srs/sm2';
import { VocabTerminal } from './terminal/vocabTerminal';
import { VocabWebviewPanel } from './webview/vocabPanel';

export interface StartOptions {
  preferredMode?: ViewMode;
  /** Only queue brand-new words (used after “Learn more”). */
  newOnly?: boolean;
  /** Unlock this many extra new-word slots before building the queue. */
  unlockExtra?: number;
}

export class StudySession {
  private queue: VocabEntry[] = [];
  private index = 0;
  private revealed = false;
  private reviewedThisPass = new Set<string>();
  private mode: ViewMode = 'terminal';
  private terminal: VocabTerminal | undefined;
  private panel: VocabWebviewPanel | undefined;

  constructor(
    private readonly context: vscode.ExtensionContext,
    private readonly store: ProgressStore
  ) {}

  getMode(): ViewMode {
    return this.mode;
  }

  getCurrentCard(): StudyCard | undefined {
    const entry = this.queue[this.index];
    if (!entry) {
      return undefined;
    }
    const progress = this.store.getProgress(entry.id);
    return {
      entry,
      progress,
      revealed: this.revealed,
      isDue: isDue(progress?.sm2, todayIso()),
      isNew: !progress,
      inBook: this.store.isInBook(entry.id),
    };
  }

  getQueueInfo(): { index: number; total: number } {
    return { index: this.index, total: this.queue.length };
  }

  async start(preferredModeOrOptions?: ViewMode | StartOptions): Promise<void> {
    const options: StartOptions =
      typeof preferredModeOrOptions === 'string' || preferredModeOrOptions === undefined
        ? { preferredMode: preferredModeOrOptions }
        : preferredModeOrOptions;

    const config = vscode.workspace.getConfiguration('sakanaVocab');
    const dailyNewLimit = config.get<number>('dailyNewLimit', 20);
    const defaultView = config.get<ViewMode>('defaultView', 'terminal');
    this.mode = options.preferredMode ?? defaultView;

    if (options.unlockExtra && options.unlockExtra > 0) {
      await this.store.unlockExtraNewWords(options.unlockExtra);
    }

    this.queue = this.store.buildStudyQueue(dailyNewLimit, { newOnly: options.newOnly });
    if (this.queue.length === 0) {
      const summary = this.store.getProgressSummary();
      const cap = this.store.getTodayNewWordCap(dailyNewLimit);
      if (summary.today.newWords >= cap && summary.remainingUnseen > 0) {
        const pick = await vscode.window.showInformationMessage(
          `Today’s goal is done (${summary.today.newWords}/${cap} new). Learn more?`,
          'Learn 10 more',
          'Choose amount…',
          'View today’s words'
        );
        if (pick === 'Learn 10 more') {
          await this.learnMore(10);
          return;
        }
        if (pick === 'Choose amount…') {
          await vscode.commands.executeCommand('sakanaVocab.learnMore');
          return;
        }
        if (pick === 'View today’s words') {
          await vscode.commands.executeCommand('sakanaVocab.dailyProgress');
          return;
        }
      }
    }

    this.index = 0;
    this.revealed = false;
    this.reviewedThisPass.clear();

    await this.showActiveView();
    this.render();
  }

  /** Unlock extra new words for today and start a new-words session. */
  async learnMore(count: number): Promise<void> {
    if (count <= 0) {
      return;
    }
    const remaining = this.store.countRemainingUnseen();
    if (remaining <= 0) {
      vscode.window.showInformationMessage('No more new dictionary words left to learn.');
      return;
    }
    const n = Math.min(count, remaining);
    await this.start({ unlockExtra: n, newOnly: true });
    vscode.window.setStatusBarMessage(
      `Sakana: unlocked ${n} more new word${n === 1 ? '' : 's'} for today`,
      3000
    );
  }

  async toggleView(): Promise<void> {
    if (this.queue.length === 0) {
      await this.start({ preferredMode: this.mode === 'terminal' ? 'ui' : 'terminal' });
      return;
    }
    this.mode = this.mode === 'terminal' ? 'ui' : 'terminal';
    await this.showActiveView();
    this.render();
  }

  private async showActiveView(): Promise<void> {
    if (this.mode === 'terminal') {
      if (!this.terminal) {
        this.terminal = new VocabTerminal(this);
      }
      this.terminal.show();
      this.panel?.dispose();
      this.panel = undefined;
    } else {
      if (!this.panel) {
        this.panel = VocabWebviewPanel.createOrShow(this.context, this, this.store);
      } else {
        this.panel.reveal();
      }
      this.terminal?.hide();
    }
  }

  render(): void {
    const card = this.getCurrentCard();
    const info = this.getQueueInfo();
    const summary = this.store.getProgressSummary();
    if (this.mode === 'terminal') {
      this.terminal?.render(card, info, summary);
    } else {
      this.panel?.render(card, info, summary);
    }
  }

  async next(): Promise<void> {
    if (this.queue.length === 0) {
      return;
    }
    await this.maybeAutoSchedule();
    this.index = (this.index + 1) % this.queue.length;
    this.revealed = false;
    await this.store.setSessionIndex(this.index);
    this.render();
  }

  async prev(): Promise<void> {
    if (this.queue.length === 0) {
      return;
    }
    this.index = (this.index - 1 + this.queue.length) % this.queue.length;
    this.revealed = false;
    await this.store.setSessionIndex(this.index);
    this.render();
  }

  reveal(): void {
    this.revealed = true;
    this.render();
  }

  private async maybeAutoSchedule(): Promise<void> {
    const card = this.getCurrentCard();
    if (!card || !this.revealed) {
      return;
    }
    if (this.reviewedThisPass.has(card.entry.id)) {
      return;
    }
    await this.store.recordReview(card.entry.id);
    this.reviewedThisPass.add(card.entry.id);
  }

  async markForgot(): Promise<void> {
    const card = this.getCurrentCard();
    if (!card) {
      return;
    }
    await this.store.markForgot(card.entry.id);
    this.reviewedThisPass.add(card.entry.id);
    this.revealed = true;
    this.render();
    vscode.window.setStatusBarMessage('Sakana: marked as forgotten — will review sooner', 2500);
  }

  async addCurrentToBook(): Promise<void> {
    const card = this.getCurrentCard();
    if (!card) {
      return;
    }
    const added = await this.store.addToBook(card.entry.id);
    vscode.window.showInformationMessage(
      added
        ? `Added “${card.entry.word}” to your vocabulary book.`
        : `“${card.entry.word}” is already in your vocabulary book.`
    );
    this.render();
  }

  dispose(): void {
    this.terminal?.dispose();
    this.panel?.dispose();
  }
}
