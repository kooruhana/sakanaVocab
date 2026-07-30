import * as vscode from 'vscode';
import { StudySession } from '../session';
import { DailyStats, StudyCard } from '../types';

/**
 * Real VS Code terminal backed by a Pseudoterminal.
 * Looks like a normal terminal session for stealth study.
 */
export class VocabTerminal {
  private terminal: vscode.Terminal | undefined;
  private writeEmitter = new vscode.EventEmitter<string>();
  private closeEmitter = new vscode.EventEmitter<void>();
  private inputBuffer = '';

  constructor(private readonly session: StudySession) {}

  show(): void {
    if (!this.terminal) {
      const pty: vscode.Pseudoterminal = {
        onDidWrite: this.writeEmitter.event,
        onDidClose: this.closeEmitter.event,
        open: () => {
          this.println(this.banner());
          this.session.render();
        },
        close: () => {
          this.terminal = undefined;
        },
        handleInput: (data: string) => {
          this.handleInput(data);
        },
      };

      this.terminal = vscode.window.createTerminal({
        name: 'sakana',
        pty,
      });
    }
    this.terminal.show(true);
  }

  hide(): void {
    // Keep process alive but don't force-focus; user switches to UI
  }

  dispose(): void {
    this.terminal?.dispose();
    this.terminal = undefined;
    this.writeEmitter.dispose();
    this.closeEmitter.dispose();
  }

  render(
    card: StudyCard | undefined,
    info: { index: number; total: number },
    summary: {
      totalLearned: number;
      dueToday: number;
      bookSize: number;
      today: DailyStats;
      todayLearnedCount?: number;
      remainingUnseen?: number;
    }
  ): void {
    this.clear();
    this.println(this.banner());
    const learned = summary.todayLearnedCount ?? summary.today.newWords;
    this.println(
      `session ${info.index + 1}/${info.total || 0}  |  due ${summary.dueToday}  |  today ${learned} new · ${summary.today.reviews} reviews  |  book ${summary.bookSize}`
    );
    this.println('─'.repeat(64));

    if (!card) {
      this.println('No cards in queue.');
      this.println('  today   — list words learned today');
      this.println('  more    — learn 10 more new words');
      this.println('  Ctrl+Alt+D — today’s list in UI');
      this.println('');
      this.print('sakana> ');
      return;
    }

    const flag = card.isNew ? 'NEW' : card.isDue ? 'DUE' : 'REVIEW';
    const book = card.inBook ? ' ★' : '';
    const level = card.entry.level ? ` ${card.entry.level}` : '';
    this.println(`[${flag}]${level}${book}`);
    this.println('');
    this.println(`  ${card.entry.word}`);
    this.println(`  ${card.entry.ipa}`);
    if (card.entry.pos) {
      this.println(`  (${card.entry.pos})`);
    }
    this.println('');

    if (card.revealed) {
      this.println(`  meaning: ${card.entry.meaning}`);
      this.println('');
      for (const s of card.entry.sentences.slice(0, 2)) {
        this.println(`  fr  ${s.text}`);
        this.println(`  en  ${s.translation}`);
        this.println('');
      }
      this.println('  next → auto-schedules (Good).  f → forgot');
    } else {
      this.println('  [hidden]  space/r reveal   n next   p prev   f forgot   a add-to-book');
    }

    this.println('');
    this.print('sakana> ');
  }

  private handleInput(data: string): void {
    // Enter
    if (data === '\r') {
      this.println('');
      const cmd = this.inputBuffer.trim().toLowerCase();
      this.inputBuffer = '';
      void this.runCommand(cmd);
      return;
    }
    // Backspace
    if (data === '\x7f') {
      if (this.inputBuffer.length > 0) {
        this.inputBuffer = this.inputBuffer.slice(0, -1);
        this.write('\b \b');
      }
      return;
    }
    // Ctrl+C
    if (data === '\x03') {
      this.println('^C');
      this.inputBuffer = '';
      this.print('sakana> ');
      return;
    }

    // Single-key shortcuts when buffer empty
    if (this.inputBuffer.length === 0) {
      if (data === ' ') {
        this.session.reveal();
        return;
      }
      if (data === 'n' || data === 'N') {
        void this.session.next();
        return;
      }
      if (data === 'p' || data === 'P') {
        void this.session.prev();
        return;
      }
      if (data === 'r' || data === 'R') {
        this.session.reveal();
        return;
      }
      if (data === 'f' || data === 'F') {
        void this.session.markForgot();
        return;
      }
      if (data === 'a' || data === 'A') {
        void this.session.addCurrentToBook();
        return;
      }
      if (data === 't' || data === 'T') {
        void this.session.toggleView();
        return;
      }
      if (data === '?' || data === 'h') {
        this.println('');
        this.println(this.help());
        this.print('sakana> ');
        return;
      }
    }

    // Echo printable chars
    if (data >= ' ' && data <= '~') {
      this.inputBuffer += data;
      this.write(data);
    }
  }

  private async runCommand(cmd: string): Promise<void> {
    if (!cmd || cmd === 'help' || cmd === '?') {
      this.println(this.help());
      this.print('sakana> ');
      return;
    }
    if (cmd === 'n' || cmd === 'next') {
      await this.session.next();
      return;
    }
    if (cmd === 'p' || cmd === 'prev') {
      await this.session.prev();
      return;
    }
    if (cmd === 'r' || cmd === 'reveal') {
      this.session.reveal();
      return;
    }
    if (cmd === 'f' || cmd === 'forgot') {
      await this.session.markForgot();
      return;
    }
    if (cmd === 'a' || cmd === 'add') {
      await this.session.addCurrentToBook();
      return;
    }
    if (cmd === 't' || cmd === 'ui' || cmd === 'toggle') {
      await this.session.toggleView();
      return;
    }
    if (cmd === 'today' || cmd === 'd') {
      await vscode.commands.executeCommand('sakanaVocab.dailyProgress');
      this.print('sakana> ');
      return;
    }
    if (cmd === 'more' || cmd === 'm') {
      await this.session.learnMore(10);
      return;
    }
    if (cmd.startsWith('more ')) {
      const n = Number(cmd.slice(5).trim());
      if (!Number.isInteger(n) || n < 1) {
        this.println('usage: more [N]   e.g. more 10');
        this.print('sakana> ');
        return;
      }
      await this.session.learnMore(n);
      return;
    }
    if (cmd === 'q' || cmd === 'quit' || cmd === 'exit') {
      this.println('Session stays open — close the terminal tab to dismiss.');
      this.print('sakana> ');
      return;
    }
    this.println(`unknown command: ${cmd}  (type help)`);
    this.print('sakana> ');
  }

  private banner(): string {
    return [
      'sakana vocabulary — french mvp',
      'type help · space reveal · n/p navigate · today · more · t ui',
    ].join('\r\n');
  }

  private help(): string {
    return [
      'commands:',
      '  space / r     reveal meaning + example',
      '  n / next      next word (auto-schedules if revealed)',
      '  p / prev      previous word',
      '  f / forgot    mark forgotten (review sooner)',
      '  a / add      add current word to vocabulary book',
      '  today / d     list words learned today',
      '  more [N]      learn more new words (default 10)',
      '  t / ui        toggle webview UI',
      '  help          this help',
      '',
      'global: Ctrl+Alt+S start · D today · M learn more · T toggle',
    ].join('\r\n');
  }

  private clear(): void {
    this.write('\x1b[2J\x1b[H');
  }

  private write(text: string): void {
    this.writeEmitter.fire(text);
  }

  private print(text: string): void {
    this.write(text);
  }

  private println(text: string): void {
    this.write(text + '\r\n');
  }
}
