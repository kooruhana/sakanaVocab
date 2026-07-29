#!/usr/bin/env node
/**
 * Build data/french.json from:
 * - FrequencyWords French list (ordering)
 * - open-dict-data/ipa-dict fr_FR (IPA)
 * - English Wiktionary REST definitions (meanings + example translations)
 *
 * Only keeps entries that have IPA, an English gloss, and ≥1 example with translation.
 * Sources are attributed in the output metadata.
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');

const ROOT = path.join(__dirname, '..');
const OUT = path.join(ROOT, 'data', 'french.json');
const IPA_URL = 'https://raw.githubusercontent.com/open-dict-data/ipa-dict/master/data/fr_FR.txt';
const FREQ_URL =
  'https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/fr/fr_50k.txt';

const TARGET_CANDIDATES = Number(process.env.SAKANA_CANDIDATES || 4000);
const CONCURRENCY = Number(process.env.SAKANA_CONCURRENCY || 6);
const MIN_WORD_LEN = 2;

// Skip pure function/clitic noise that rarely has useful learner examples alone
const SKIP = new Set([
  "c'",
  "l'",
  "d'",
  "j'",
  "n'",
  "m'",
  "t'",
  "s'",
  "qu'",
  "aujourd'",
]);

function fetchText(url) {
  return new Promise((resolve, reject) => {
    const lib = url.startsWith('https') ? https : http;
    const req = lib.get(
      url,
      {
        headers: {
          'User-Agent': 'SakanaVocabularyBuilder/0.1 (VS Code extension; educational)',
          Accept: 'application/json,text/plain,*/*',
        },
      },
      (res) => {
        if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          fetchText(res.headers.location).then(resolve, reject);
          return;
        }
        if (res.statusCode === 404) {
          resolve(null);
          return;
        }
        if (res.statusCode !== 200) {
          reject(new Error(`HTTP ${res.statusCode} for ${url}`));
          return;
        }
        const chunks = [];
        res.on('data', (c) => chunks.push(c));
        res.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
      }
    );
    req.on('error', reject);
  });
}

function stripHtml(html) {
  return String(html || '')
    .replace(/<br\s*\/?>/gi, ' ')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, ' ')
    .trim();
}

function normalizeIpa(raw) {
  if (!raw) return '';
  // IPA dict may have multiple readings separated by comma or /
  const first = raw.split(',')[0].trim();
  let ipa = first;
  if (!ipa.startsWith('/')) {
    ipa = '/' + ipa.replace(/^\[|\]$/g, '');
  }
  if (!ipa.endsWith('/')) {
    ipa = ipa + '/';
  }
  return ipa;
}

function parseIpaFile(text) {
  const map = new Map();
  for (const line of text.split(/\r?\n/)) {
    if (!line.trim()) continue;
    const tab = line.indexOf('\t');
    if (tab < 0) continue;
    const word = line.slice(0, tab).trim();
    const ipa = normalizeIpa(line.slice(tab + 1).trim());
    if (!word || !ipa) continue;
    const key = word.toLowerCase();
    if (!map.has(key)) {
      map.set(key, ipa);
    }
  }
  return map;
}

function parseFreqFile(text) {
  const words = [];
  const seen = new Set();
  for (const line of text.split(/\r?\n/)) {
    const w = line.split(/\s+/)[0];
    if (!w) continue;
    const key = w.toLowerCase();
    if (seen.has(key)) continue;
    if (w.length < MIN_WORD_LEN) continue;
    if (SKIP.has(key)) continue;
    if (!/^[a-zàâäæçéèêëïîôœùûüÿñ\-']+$/i.test(w)) continue;
    seen.add(key);
    words.push(w);
  }
  return words;
}

function extractFrenchEntry(json, word) {
  if (!json || !json.fr || !Array.isArray(json.fr)) {
    return null;
  }

  for (const block of json.fr) {
    const defs = block.definitions || [];
    for (const def of defs) {
      const meaning = stripHtml(def.definition);
      if (!meaning || meaning.length < 2) continue;

      const sentences = [];
      const parsed = def.parsedExamples || [];
      for (const ex of parsed) {
        const text = stripHtml(ex.example);
        const translation = stripHtml(ex.translation || ex.literally || '');
        if (text && translation && text.length > 2 && translation.length > 2) {
          sentences.push({ text, translation });
        }
      }

      if (sentences.length === 0) continue;

      return {
        meaning: meaning.slice(0, 240),
        pos: block.partOfSpeech || undefined,
        sentences: sentences.slice(0, 3),
      };
    }
  }
  return null;
}

async function mapPool(items, concurrency, fn) {
  const results = new Array(items.length);
  let i = 0;
  async function worker() {
    while (i < items.length) {
      const idx = i++;
      results[idx] = await fn(items[idx], idx);
    }
  }
  await Promise.all(Array.from({ length: concurrency }, () => worker()));
  return results;
}

async function main() {
  console.log('Downloading IPA dictionary…');
  const ipaText = await fetchText(IPA_URL);
  const ipaMap = parseIpaFile(ipaText);
  console.log(`IPA entries: ${ipaMap.size}`);

  console.log('Downloading frequency list…');
  const freqText = await fetchText(FREQ_URL);
  const freqWords = parseFreqFile(freqText);
  console.log(`Frequency words: ${freqWords.length}`);

  const candidates = [];
  for (const w of freqWords) {
    if (candidates.length >= TARGET_CANDIDATES) break;
    const ipa = ipaMap.get(w.toLowerCase());
    if (!ipa) continue;
    candidates.push({ word: w, ipa });
  }
  console.log(`Candidates with IPA: ${candidates.length}`);

  let ok = 0;
  let fail = 0;
  const words = [];

  await mapPool(candidates, CONCURRENCY, async (c, idx) => {
    const encoded = encodeURIComponent(c.word);
    const url = `https://en.wiktionary.org/api/rest_v1/page/definition/${encoded}`;
    try {
      const body = await fetchText(url);
      if (!body) {
        fail++;
        return;
      }
      let json;
      try {
        json = JSON.parse(body);
      } catch {
        fail++;
        return;
      }
      const extracted = extractFrenchEntry(json, c.word);
      if (!extracted) {
        fail++;
        return;
      }

      // Light verification: IPA must look like IPA, meaning not empty, sentence has both sides
      if (!/^\/.+\/$/.test(c.ipa)) {
        fail++;
        return;
      }

      const id = `fr:${c.word.toLowerCase()}`;
      words.push({
        id,
        language: 'fr',
        word: c.word,
        ipa: c.ipa,
        meaning: extracted.meaning,
        pos: extracted.pos,
        sentences: extracted.sentences,
        tags: ['wiktionary', 'frequency'],
      });
      ok++;
    } catch (e) {
      fail++;
    }
    if ((idx + 1) % 100 === 0) {
      console.log(`…processed ${idx + 1}/${candidates.length} (kept ${ok})`);
    }
    // polite pause
    await new Promise((r) => setTimeout(r, 40));
  });

  // Stable order by original frequency candidate order
  const order = new Map(candidates.map((c, i) => [c.word.toLowerCase(), i]));
  words.sort(
    (a, b) => (order.get(a.word.toLowerCase()) ?? 0) - (order.get(b.word.toLowerCase()) ?? 0)
  );

  // Deduplicate by id
  const seen = new Set();
  const unique = [];
  for (const w of words) {
    if (seen.has(w.id)) continue;
    seen.add(w.id);
    unique.push(w);
  }

  const payload = {
    language: 'fr',
    version: 1,
    generatedAt: new Date().toISOString(),
    sources: [
      {
        name: 'open-dict-data/ipa-dict (fr_FR)',
        url: 'https://github.com/open-dict-data/ipa-dict',
        license: 'MIT',
        usedFor: 'IPA pronunciation',
      },
      {
        name: 'FrequencyWords (fr)',
        url: 'https://github.com/hermitdave/FrequencyWords',
        license: 'MIT-like / open word lists',
        usedFor: 'word frequency ordering',
      },
      {
        name: 'English Wiktionary (REST definitions)',
        url: 'https://en.wiktionary.org',
        license: 'CC BY-SA 4.0',
        usedFor: 'English glosses and example sentences with translations',
      },
    ],
    count: unique.length,
    words: unique,
  };

  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify(payload, null, 2));
  console.log(`Wrote ${unique.length} words → ${OUT} (failed/skipped ${fail})`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
