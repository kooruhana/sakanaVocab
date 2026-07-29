import * as vscode from 'vscode';
import { StudySession } from '../session';
import { ProgressStore } from '../storage/progressStore';
import { DailyStats, StudyCard } from '../types';

export class VocabWebviewPanel {
  public static current: VocabWebviewPanel | undefined;
  private readonly panel: vscode.WebviewPanel;
  private disposed = false;

  private constructor(
    panel: vscode.WebviewPanel,
    private readonly session: StudySession,
    private readonly store: ProgressStore
  ) {
    this.panel = panel;
    this.panel.webview.html = this.getHtml();
    this.panel.webview.onDidReceiveMessage(async (msg) => {
      switch (msg?.type) {
        case 'next':
          await this.session.next();
          break;
        case 'prev':
          await this.session.prev();
          break;
        case 'reveal':
          this.session.reveal();
          break;
        case 'forgot':
          await this.session.markForgot();
          break;
        case 'add':
          await this.session.addCurrentToBook();
          break;
        case 'toggle':
          await this.session.toggleView();
          break;
        case 'lookup':
          await vscode.commands.executeCommand('sakanaVocab.lookup');
          break;
        case 'book':
          await vscode.commands.executeCommand('sakanaVocab.openBook');
          break;
      }
    });
    this.panel.onDidDispose(() => {
      this.disposed = true;
      VocabWebviewPanel.current = undefined;
    });
  }

  static createOrShow(
    context: vscode.ExtensionContext,
    session: StudySession,
    store: ProgressStore
  ): VocabWebviewPanel {
    if (VocabWebviewPanel.current && !VocabWebviewPanel.current.disposed) {
      VocabWebviewPanel.current.reveal();
      return VocabWebviewPanel.current;
    }
    const panel = vscode.window.createWebviewPanel(
      'sakanaVocab',
      'Sakana Vocabulary',
      vscode.ViewColumn.Beside,
      { enableScripts: true, retainContextWhenHidden: true }
    );
    VocabWebviewPanel.current = new VocabWebviewPanel(panel, session, store);
    return VocabWebviewPanel.current;
  }

  reveal(): void {
    this.panel.reveal(vscode.ViewColumn.Beside);
  }

  dispose(): void {
    this.panel.dispose();
  }

  render(
    card: StudyCard | undefined,
    info: { index: number; total: number },
    summary: { totalLearned: number; dueToday: number; bookSize: number; today: DailyStats }
  ): void {
    if (this.disposed) {
      return;
    }
    void this.panel.webview.postMessage({ type: 'state', card, info, summary });
  }

  private getHtml(): string {
    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Sakana Vocabulary</title>
<style>
  :root {
    --bg0: #0f1419;
    --bg1: #1a2332;
    --ink: #e8eef7;
    --muted: #8b9bb4;
    --accent: #3dd6c3;
    --warn: #f0a05a;
    --line: #2a3648;
    --font-display: "Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif;
    --font-body: "Segoe UI", "Helvetica Neue", sans-serif;
    --font-mono: "Cascadia Code", "SF Mono", Consolas, monospace;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    min-height: 100vh;
    color: var(--ink);
    font-family: var(--font-body);
    background:
      radial-gradient(1200px 600px at 10% -10%, #1e3a4c 0%, transparent 55%),
      radial-gradient(900px 500px at 100% 0%, #243018 0%, transparent 50%),
      linear-gradient(160deg, var(--bg0), var(--bg1));
  }
  .wrap { max-width: 720px; margin: 0 auto; padding: 28px 24px 48px; }
  header {
    display: flex; justify-content: space-between; align-items: baseline; gap: 12px;
    margin-bottom: 28px;
  }
  .brand {
    font-family: var(--font-display);
    font-size: 1.65rem;
    letter-spacing: 0.02em;
    margin: 0;
  }
  .brand span { color: var(--accent); }
  .meta { color: var(--muted); font-size: 0.85rem; font-family: var(--font-mono); }
  .stage { min-height: 280px; }
  .flag {
    display: inline-block;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--accent);
    border-bottom: 1px solid var(--line);
    padding-bottom: 2px;
    margin-bottom: 18px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .word {
    font-family: var(--font-display);
    font-size: clamp(2.4rem, 6vw, 3.4rem);
    line-height: 1.1;
    margin: 0 0 8px;
    animation: rise 420ms ease-out;
  }
  .ipa {
    font-family: var(--font-mono);
    color: var(--muted);
    font-size: 1.05rem;
    margin-bottom: 6px;
  }
  .pos { color: var(--muted); font-size: 0.9rem; margin-bottom: 22px; }
  .meaning {
    font-size: 1.15rem;
    line-height: 1.45;
    margin-bottom: 22px;
    animation: rise 480ms ease-out;
  }
  .ex {
    border-left: 2px solid var(--accent);
    padding: 4px 0 4px 14px;
    margin: 0 0 14px;
    animation: rise 560ms ease-out;
  }
  .ex .fr { font-size: 1.05rem; margin-bottom: 4px; }
  .ex .en { color: var(--muted); font-size: 0.95rem; }
  .hidden-hint {
    color: var(--muted);
    font-family: var(--font-mono);
    font-size: 0.9rem;
    padding: 18px 0;
  }
  .actions {
    display: flex; flex-wrap: wrap; gap: 10px;
    margin-top: 28px;
  }
  button {
    appearance: none;
    border: 1px solid var(--line);
    background: transparent;
    color: var(--ink);
    font: inherit;
    font-size: 0.92rem;
    padding: 10px 14px;
    cursor: pointer;
    transition: border-color 160ms ease, color 160ms ease, transform 160ms ease;
  }
  button:hover { border-color: var(--accent); color: var(--accent); transform: translateY(-1px); }
  button.primary { border-color: var(--accent); color: var(--accent); }
  button.warn { border-color: var(--warn); color: var(--warn); }
  .stats {
    margin-top: 36px;
    padding-top: 16px;
    border-top: 1px solid var(--line);
    color: var(--muted);
    font-family: var(--font-mono);
    font-size: 0.8rem;
    display: flex; flex-wrap: wrap; gap: 16px;
  }
  .empty { color: var(--muted); padding: 40px 0; }
  @keyframes rise {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
  }
</style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1 class="brand">Sakana <span>Vocabulary</span></h1>
      <div class="meta" id="sessionMeta">—</div>
    </header>
    <div class="stage" id="stage">
      <div class="empty">Start a session with Ctrl+Alt+S</div>
    </div>
    <div class="actions">
      <button class="primary" data-cmd="reveal">Reveal</button>
      <button data-cmd="prev">Previous</button>
      <button data-cmd="next">Next</button>
      <button class="warn" data-cmd="forgot">Forgot</button>
      <button data-cmd="add">Add to book</button>
      <button data-cmd="book">Vocabulary book</button>
      <button data-cmd="lookup">Lookup</button>
      <button data-cmd="toggle">Terminal view</button>
    </div>
    <div class="stats" id="stats"></div>
  </div>
  <script>
    const vscode = acquireVsCodeApi();
    document.querySelectorAll('button[data-cmd]').forEach((btn) => {
      btn.addEventListener('click', () => vscode.postMessage({ type: btn.dataset.cmd }));
    });
    window.addEventListener('message', (event) => {
      const msg = event.data;
      if (msg.type !== 'state') return;
      const { card, info, summary } = msg;
      document.getElementById('sessionMeta').textContent =
        (info.total ? (info.index + 1) + ' / ' + info.total : '0') + ' · French';
      const stage = document.getElementById('stage');
      if (!card) {
        stage.innerHTML = '<div class="empty">No cards queued. Lookup a word or open your vocabulary book.</div>';
      } else {
        const flag = card.isNew ? 'New' : card.isDue ? 'Due' : 'Review';
        const book = card.inBook ? ' · in book' : '';
        const level = card.entry.level ? ' · ' + card.entry.level : '';
        let body = '<div class="flag">' + flag + level + book + '</div>';
        body += '<div class="word">' + escapeHtml(card.entry.word) + '</div>';
        body += '<div class="ipa">' + escapeHtml(card.entry.ipa) + '</div>';
        if (card.entry.pos) body += '<div class="pos">' + escapeHtml(card.entry.pos) + '</div>';
        if (card.revealed) {
          body += '<div class="meaning">' + escapeHtml(card.entry.meaning) + '</div>';
          (card.entry.sentences || []).slice(0, 2).forEach((s) => {
            body += '<div class="ex"><div class="fr">' + escapeHtml(s.text) + '</div>' +
              '<div class="en">' + escapeHtml(s.translation) + '</div></div>';
          });
        } else {
          body += '<div class="hidden-hint">Meaning and examples hidden — press Reveal</div>';
        }
        stage.innerHTML = body;
      }
      document.getElementById('stats').innerHTML =
        '<span>learned ' + summary.totalLearned + '</span>' +
        '<span>due ' + summary.dueToday + '</span>' +
        '<span>today ' + summary.today.reviews + ' reviews</span>' +
        '<span>book ' + summary.bookSize + '</span>';
    });
    function escapeHtml(s) {
      return String(s).replace(/[&<>"']/g, (c) => ({
        '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
      })[c]);
    }
  </script>
</body>
</html>`;
  }
}
