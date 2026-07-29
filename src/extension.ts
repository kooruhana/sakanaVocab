import * as vscode from 'vscode';
import { ProgressStore } from './storage/progressStore';
import { StudySession } from './session';
import { VocabEntry } from './types';

let store: ProgressStore;
let session: StudySession;

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  store = new ProgressStore(context);
  await store.init();
  session = new StudySession(context, store);

  context.subscriptions.push(
    vscode.commands.registerCommand('sakanaVocab.start', async () => {
      await session.start();
    }),
    vscode.commands.registerCommand('sakanaVocab.toggleView', async () => {
      await session.toggleView();
    }),
    vscode.commands.registerCommand('sakanaVocab.next', async () => {
      await session.next();
    }),
    vscode.commands.registerCommand('sakanaVocab.prev', async () => {
      await session.prev();
    }),
    vscode.commands.registerCommand('sakanaVocab.reveal', () => {
      session.reveal();
    }),
    vscode.commands.registerCommand('sakanaVocab.markForgot', async () => {
      await session.markForgot();
    }),
    vscode.commands.registerCommand('sakanaVocab.addToBook', async () => {
      await session.addCurrentToBook();
    }),
    vscode.commands.registerCommand('sakanaVocab.dailyProgress', async () => {
      await showTodayFlow();
    }),
    vscode.commands.registerCommand('sakanaVocab.learnMore', async () => {
      await learnMoreFlow();
    }),
    vscode.commands.registerCommand('sakanaVocab.lookup', async () => {
      await lookupFlow();
    }),
    vscode.commands.registerCommand('sakanaVocab.openBook', async () => {
      await openBookFlow();
    }),
    { dispose: () => session.dispose() }
  );

  const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  status.text = '$(book) Sakana';
  status.tooltip = 'Sakana Vocabulary — Ctrl+Alt+S · Today: Ctrl+Alt+D';
  status.command = 'sakanaVocab.dailyProgress';
  status.show();
  context.subscriptions.push(status);
}

async function showTodayFlow(): Promise<void> {
  const config = vscode.workspace.getConfiguration('sakanaVocab');
  const dailyNewLimit = config.get<number>('dailyNewLimit', 20);
  const summary = store.getProgressSummary();
  const learned = store.getTodayLearnedEntries();
  const cap = store.getTodayNewWordCap(dailyNewLimit);
  const remainingSlots = Math.max(0, cap - summary.today.newWords);

  type Item = vscode.QuickPickItem & {
    action?: 'more10' | 'moreCustom' | 'start' | 'details';
    entry?: VocabEntry;
  };

  const items: Item[] = [
    {
      label: `$(add) Learn 10 more`,
      description: summary.remainingUnseen > 0 ? `${summary.remainingUnseen} left in dictionary` : 'none left',
      detail: `Today ${summary.today.newWords}/${cap} new · unlock 10 extra beyond the daily goal`,
      action: 'more10',
    },
    {
      label: `$(add) Learn more…`,
      description: 'Choose how many',
      action: 'moreCustom',
    },
    {
      label: `$(play) Continue studying`,
      description: remainingSlots > 0 ? `${remainingSlots} new slot(s) left today` : 'reviews / already unlocked extras',
      action: 'start',
    },
  ];

  if (learned.length === 0) {
    items.push({
      label: 'No new words learned yet today',
      description: summary.today.date,
    });
  } else {
    items.push({
      label: `Today’s new words (${learned.length})`,
      kind: vscode.QuickPickItemKind.Separator,
    });
    for (const e of learned) {
      items.push({
        label: e.word,
        description: e.ipa,
        detail: `${e.meaning}${e.level ? ` · ${e.level}` : ''}`,
        action: 'details',
        entry: e,
      });
    }
  }

  const picked = await vscode.window.showQuickPick(items, {
    title: `Sakana — Today (${summary.today.date}) · ${summary.today.newWords} new · ${summary.today.reviews} reviews`,
    matchOnDescription: true,
    matchOnDetail: true,
    placeHolder: 'Pick a word to inspect, or learn more',
  });
  if (!picked) {
    return;
  }

  if (picked.action === 'more10') {
    await session.learnMore(10);
    return;
  }
  if (picked.action === 'moreCustom') {
    await learnMoreFlow();
    return;
  }
  if (picked.action === 'start') {
    await session.start();
    return;
  }
  if (picked.entry) {
    await showEntryActions(picked.entry, store.isInBook(picked.entry.id));
  }
}

async function learnMoreFlow(): Promise<void> {
  const remaining = store.countRemainingUnseen();
  if (remaining <= 0) {
    vscode.window.showInformationMessage('No more new dictionary words left to learn.');
    return;
  }
  const raw = await vscode.window.showInputBox({
    title: 'Sakana Vocabulary — Learn more',
    prompt: `How many extra new words today? (${remaining} still unseen)`,
    value: '10',
    validateInput: (v) => {
      const n = Number(v);
      if (!Number.isInteger(n) || n < 1) {
        return 'Enter a whole number ≥ 1';
      }
      if (n > 200) {
        return 'Keep it ≤ 200 per unlock';
      }
      return undefined;
    },
  });
  if (raw === undefined) {
    return;
  }
  await session.learnMore(Math.min(Number(raw), remaining));
}

async function lookupFlow(): Promise<void> {
  const query = await vscode.window.showInputBox({
    title: 'Sakana Vocabulary — Lookup',
    prompt: 'Search the French dictionary (word or English meaning)',
    placeHolder: 'e.g. bonjour, house, manger…',
  });
  if (query === undefined) {
    return;
  }
  const results = store.lookup(query);
  if (results.length === 0) {
    vscode.window.showWarningMessage(`No matches for “${query}”.`);
    return;
  }
  const picked = await vscode.window.showQuickPick(
    results.map((e) => ({
      label: e.word,
      description: e.ipa,
      detail: e.meaning,
      entry: e,
    })),
    { title: 'Dictionary results — Add to vocabulary book' }
  );
  if (!picked) {
    return;
  }
  await showEntryActions(picked.entry);
}

async function openBookFlow(): Promise<void> {
  const book = store.getBookEntries();
  if (book.length === 0) {
    const go = await vscode.window.showInformationMessage(
      'Your vocabulary book is empty. Lookup a word to add one?',
      'Lookup'
    );
    if (go === 'Lookup') {
      await lookupFlow();
    }
    return;
  }
  const picked = await vscode.window.showQuickPick(
    book.map((e) => {
      const p = store.getProgress(e.id);
      return {
        label: e.word,
        description: e.ipa,
        detail: `${e.meaning}${p ? ` · due ${p.sm2.dueDate}` : ' · not studied yet'}`,
        entry: e,
      };
    }),
    { title: `Vocabulary book (${book.length})` }
  );
  if (!picked) {
    return;
  }
  await showEntryActions(picked.entry, true);
}

async function showEntryActions(entry: VocabEntry, inBook = false): Promise<void> {
  const actions = [
    'Add to vocabulary book',
    'Show details',
    ...(inBook || store.isInBook(entry.id) ? ['Remove from book'] : []),
  ];
  const action = await vscode.window.showQuickPick(actions, {
    title: `${entry.word}  ${entry.ipa}`,
  });
  if (!action) {
    return;
  }
  if (action === 'Add to vocabulary book') {
    const added = await store.addToBook(entry.id);
    vscode.window.showInformationMessage(
      added ? `Added “${entry.word}” to your book.` : `“${entry.word}” is already in your book.`
    );
  } else if (action === 'Remove from book') {
    await store.removeFromBook(entry.id);
    vscode.window.showInformationMessage(`Removed “${entry.word}” from your book.`);
  } else if (action === 'Show details') {
    const sentences = entry.sentences
      .map((s) => `• ${s.text}\n  ${s.translation}`)
      .join('\n\n');
    await vscode.window.showInformationMessage(
      `${entry.word} ${entry.ipa}\n${entry.meaning}\n\n${sentences}`,
      { modal: true }
    );
  }
}

export function deactivate(): void {
  session?.dispose();
}
