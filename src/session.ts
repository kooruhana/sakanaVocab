import * as vscode from 'vscode';
import { ProgressStore } from './storage/progressStore';
import { StudyCard, VocabEntry, ViewMode } from './types';
import { isDue, todayIso } from './srs/sm2';
import { VocabTerminal } from './terminal/vocabTerminal';
import { VocabWebviewPanel } from './webview/vocabPanel';

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

  async start(preferredMode?: ViewMode): Promise<void> {
    const config = vscode.workspace.getConfiguration('sakanaVocab');
    const dailyNewLimit = config.get<number>('dailyNewLimit', 20);
    const defaultView = config.get<ViewMode>('defaultView', 'terminal');
    this.mode = preferredMode ?? defaultView;

    this.queue = this.store.buildStudyQueue(dailyNewLimit);
    if (this.queue.length === 0) {
      // Fallback: allow browsing dictionary even if daily new limit hit and nothing due
      this.queue = this.store.getDictionary().slice(0, 50);
    }
    this.index = 0;
    this.revealed = false;
    this.reviewedThisPass.clear();

    await this.showActiveView();
    this.render();
  }

  async toggleView(): Promise<void> {
    if (this.queue.length === 0) {
      await this.start(this.mode === 'terminal' ? 'ui' : 'terminal');
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
    // Going back does not auto-schedule
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
    // Auto-schedule as Good when leaving a revealed card
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
