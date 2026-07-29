# Sakana Vocabulary

VS Code extension that helps language learners memorize vocabulary — **stealthily in a real terminal**, or in a proper webview UI.

**Official name:** Sakana Vocabulary  
**MVP language:** French (English & Japanese planned later)

## Features

1. **Terminal study mode** — real VS Code terminal (`Pseudoterminal`) that looks like a normal shell session
2. **Webview UI** — richer card view with the same study flow
3. **Toggle** between terminal and UI with one shortcut
4. **Vocabulary cards** — French word, IPA pronunciation, English meaning, sample sentence + English translation
5. **Previous / Next** navigation (global shortcuts + terminal keys)
6. **SM-2 spaced repetition** with **auto-scheduling** (revealing then going next = “Good”; optional “Forgot”)
7. **Daily progress** tracking
8. **Vocabulary book** — look up words in the built-in dictionary and add them

## Learning order

New words follow a **gentle → harder** path:

1. **Starter** (~145 everyday survival words): greetings → people → places/food → core verbs → simple adjectives/numbers → essential glue words  
2. **CEFR A1 → C2** using [FLELex](https://cental.uclouvain.be/cefrlex/flelex/) (textbook-graded frequencies)  
3. Within each level: more common / concrete words first; clitics and proper names later  

The study queue introduces new words in this order (after due reviews). Each card shows its level (`starter`, `A1`, …).

~12,000 entries. **Meanings** come from a bilingual FR→EN dictionary (not raw multi-sense Wiktionary dumps):

| Source | Use |
|--------|-----|
| [Matthias Buchmeier FR→EN](https://github.com/open-dsl-dict/wiktionary-dict) (CC BY-SA 3.0 / GFDL) | **Primary English meanings** (POS-tagged glosses) |
| [open-dict-data/ipa-dict](https://github.com/open-dict-data/ipa-dict) (MIT) | IPA pronunciation |
| [FrequencyWords](https://github.com/hermitdave/FrequencyWords) | Frequency ordering |
| [kaikki.org / Wiktextract](https://kaikki.org/dictionary/French/) (CC BY-SA 4.0) | Sample sentences when they match the chosen gloss |

Ultra-common homographs (`pas`, `sur`, `est`, `la`, …) use a curated verified table so learner meanings win over rare senses (e.g. `pas` = *not*, not *step*). Inflection-only senses are skipped unless curated.

## Shortcuts

| Shortcut (Windows/Linux) | macOS | Action |
|--------------------------|-------|--------|
| `Ctrl+Alt+S` | `Cmd+Alt+S` | Start study session |
| `Ctrl+Alt+T` | `Cmd+Alt+T` | Toggle terminal ↔ UI |
| `Ctrl+Alt+N` | `Cmd+Alt+N` | Next word |
| `Ctrl+Alt+P` | `Cmd+Alt+P` | Previous word |
| `Ctrl+Alt+R` | `Cmd+Alt+R` | Reveal meaning / examples |
| `Ctrl+Alt+F` | `Cmd+Alt+F` | Mark as forgotten (review sooner) |
| `Ctrl+Alt+A` | `Cmd+Alt+A` | Add current word to vocabulary book |
| `Ctrl+Alt+B` | `Cmd+Alt+B` | Open vocabulary book |
| `Ctrl+Alt+L` | `Cmd+Alt+L` | Lookup word in dictionary |
| `Ctrl+Alt+D` | `Cmd+Alt+D` | Show daily progress |

### Inside the terminal

| Key | Action |
|-----|--------|
| `Space` / `r` | Reveal |
| `n` | Next (auto-schedules if revealed) |
| `p` | Previous |
| `f` | Forgot |
| `a` | Add to book |
| `t` | Toggle UI |
| `help` | Help |

## How scheduling works

- Algorithm: **SM-2** (Anki-style forgetting curve)
- **Auto-schedule:** after you reveal a card, pressing **Next** records a “Good” review and sets the next due date
- **Forgot** (`Ctrl+Alt+F` / `f`): resets the streak and schedules a sooner review
- New words per day are limited (`sakanaVocab.dailyNewLimit`, default **20**)
- Due reviews are shown before new words; vocabulary-book words are prioritized

## Local data

Progress and your vocabulary book are stored **locally** on your machine in the extension’s global storage (follows your VS Code user profile, not a single workspace folder):

- learned/review state (SM-2)
- vocabulary book word IDs
- daily stats

## Install (development)

```bash
npm install
npm run compile
```

Then in VS Code: **Run → Start Debugging** (or `F5`) with this folder open, or pack with:

```bash
npx vsce package
```

## Commands palette

Search for **Sakana Vocabulary** in the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`).

## Settings

- `sakanaVocab.dailyNewLimit` — max new words introduced per day (default 20)
- `sakanaVocab.defaultView` — `terminal` (default) or `ui`

## Rebuild dictionary (optional)

```bash
# prerequisites under /tmp: fr_ipa.txt, fr_freq.txt, fren-dict/fr-en.txt, kaikki/french.jsonl
python3 scripts/rebuild_trusted_dict.py
```

## License

See [LICENSE](LICENSE). Dictionary content remains under the licenses of its upstream sources (notably CC BY-SA for Wiktionary-derived glosses/examples).
