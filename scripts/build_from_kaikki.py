#!/usr/bin/env python3
"""Build data/french.json from kaikki.org Wiktionary extract + IPA/frequency lists."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "french.json"
KAIKKI = Path("/tmp/kaikki/french.jsonl")
FREQ_PATH = Path("/tmp/fr_freq.txt")
IPA_PATH = Path("/tmp/fr_ipa.txt")

SKIP_GLOSS = re.compile(
    r"inflection of|^plural of|misspelling|alternative (spelling|form)|obsolete|"
    r"archaic|rare|eye dialect|initialism|abbreviation",
    re.I,
)
SKIP_POS = {
    "name",
    "character",
    "symbol",
    "suffix",
    "prefix",
    "infix",
    "circumfix",
    "interfix",
    "proverb",
    "phrase",
    "prep",
    "conj",
    "particle",
    "article",
    "det",
    "pron",
}
NICHÉ = re.compile(
    r"homemade|in-house|heraldry|chemistry|biology|anatomy|typography|computing",
    re.I,
)
WORD_RE = re.compile(r"[A-Za-zÀ-ÿœæŒÆ''\-]+")


def load_freq(limit: int = 6000) -> list[str]:
    words: list[str] = []
    with FREQ_PATH.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= limit:
                break
            w = line.split()[0]
            if WORD_RE.fullmatch(w) and len(w) >= 2:
                words.append(w)
    return words


def load_ipa() -> dict[str, str]:
    ipa_map: dict[str, str] = {}
    with IPA_PATH.open(encoding="utf-8") as f:
        for line in f:
            if "\t" not in line:
                continue
            w, ipa = line.rstrip().split("\t", 1)
            key = w.lower()
            if key in ipa_map:
                continue
            ipa = ipa.split(",")[0].strip()
            ipa_map[key] = "/" + ipa.strip("/[]") + "/"
    return ipa_map


def norm_ipa(raw: str) -> str:
    return "/" + str(raw).strip("/[]") + "/"


def score(entry: dict, key: str, freq_rank: dict[str, int]) -> int:
    sc = 0
    sc += {"noun": 50, "verb": 50, "adj": 40, "adv": 30, "intj": 20}.get(entry["pos"], 10)
    ex = entry["examples"]
    if ex:
        sc += 100
        if any(e["contains"] for e in ex):
            sc += 50
        if any(" " in e["text"] and len(e["text"]) > 12 for e in ex):
            sc += 30
    meaning = entry["meaning"]
    sc += max(0, 40 - len(meaning) // 2)
    head = meaning.split("(")[0].strip()
    if re.fullmatch(r"[A-Za-z\- ]{2,40}", head):
        sc += 20
    if key in freq_rank:
        sc += max(0, 30 - freq_rank[key] // 200)
        if freq_rank[key] < 2000 and NICHÉ.search(meaning):
            sc -= 80
    return sc


def synth_sentence(word: str, meaning: str, pos: str) -> dict:
    m = meaning.split(";")[0].split(",")[0].strip()
    if pos == "verb":
        bare = m[3:].strip() if m.lower().startswith("to ") else m
        return {"text": f"Nous allons {word}.", "translation": f"We are going to {bare}."}
    if pos == "adj":
        return {"text": f"C'est très {word}.", "translation": f"It is very {m}."}
    if pos == "adv":
        return {"text": f"Elle répond {word}.", "translation": f"She answers {m}."}
    if pos == "intj":
        return {"text": f"{word} !", "translation": f"{m}!"}
    return {
        "text": f"Le mot « {word} » est important.",
        "translation": f'The word "{word}" ({m}) is important.',
    }


def main() -> None:
    freq = load_freq()
    freq_rank = {w.lower(): i for i, w in enumerate(freq)}
    ipa_map = load_ipa()

    cands: dict[str, list] = defaultdict(list)
    with KAIKKI.open(encoding="utf-8") as f:
        for line in f:
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            word = o.get("word") or ""
            if not word or " " in word or len(word) < 2 or not WORD_RE.fullmatch(word):
                continue
            pos = o.get("pos") or ""
            if pos in SKIP_POS:
                continue
            ipa = None
            for s in o.get("sounds") or []:
                if s.get("ipa"):
                    ipa = s["ipa"]
                    break
            if not ipa:
                ipa = ipa_map.get(word.lower())
            if not ipa:
                continue
            ipa = norm_ipa(ipa)

            for s in o.get("senses") or []:
                gs = s.get("glosses") or s.get("raw_glosses") or []
                if not gs:
                    continue
                gloss = gs[0].strip()
                if SKIP_GLOSS.search(gloss) or not (2 <= len(gloss) <= 200):
                    continue
                examples = []
                for ex in s.get("examples") or []:
                    text = ex.get("text")
                    tr = ex.get("english") or ex.get("translation")
                    if not text or not tr:
                        continue
                    text = str(text).strip()
                    tr = str(tr).strip()
                    if len(text) < 3 or len(tr) < 3:
                        continue
                    examples.append(
                        {
                            "text": text,
                            "translation": tr,
                            "contains": word.lower() in text.lower(),
                        }
                    )
                cands[word.lower()].append(
                    {
                        "word": word,
                        "pos": pos,
                        "ipa": ipa,
                        "meaning": gloss,
                        "examples": examples,
                    }
                )

    final = []
    for key, entries in cands.items():
        has_ex = any(e["examples"] for e in entries)
        if key not in freq_rank and not has_ex:
            continue
        best = max(entries, key=lambda e: score(e, key, freq_rank))
        with_ex = [e for e in entries if e["examples"]]
        if with_ex:
            best_ex = max(with_ex, key=lambda e: score(e, key, freq_rank))
            if score(best_ex, key, freq_rank) >= score(best, key, freq_rank) - 40:
                best = best_ex

        sentences = [
            {"text": ex["text"], "translation": ex["translation"]} for ex in best["examples"]
        ]
        tags = ["wiktionary"]
        if key in freq_rank:
            tags.append("frequency")
        if not sentences:
            sentences = [synth_sentence(best["word"], best["meaning"], best["pos"])]
            tags.append("synthetic-example")

        final.append(
            {
                "id": f"fr:{key}",
                "language": "fr",
                "word": best["word"],
                "ipa": best["ipa"],
                "meaning": best["meaning"][:240],
                "pos": best["pos"],
                "sentences": sentences[:3],
                "tags": tags,
            }
        )

    final.sort(key=lambda e: (freq_rank.get(e["word"].lower(), 10_000), e["word"].lower()))

    payload = {
        "language": "fr",
        "version": 2,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sources": [
            {
                "name": "Wiktextract / kaikki.org French (enwiktionary)",
                "url": "https://kaikki.org/dictionary/French/",
                "license": "CC BY-SA 4.0",
                "usedFor": "English glosses, IPA, example sentences with translations",
            },
            {
                "name": "open-dict-data/ipa-dict (fr_FR)",
                "url": "https://github.com/open-dict-data/ipa-dict",
                "license": "MIT",
                "usedFor": "IPA fallback",
            },
            {
                "name": "FrequencyWords (fr)",
                "url": "https://github.com/hermitdave/FrequencyWords",
                "license": "Open word lists",
                "usedFor": "frequency ordering",
            },
        ],
        "notes": (
            "Prefer Wiktionary bilingual examples. Entries tagged synthetic-example use a short "
            "pedagogical frame when Wiktionary had no bilingual example; gloss/IPA remain from "
            "dictionary sources."
        ),
        "count": len(final),
        "words": final,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    auth = sum(1 for e in final if "synthetic-example" not in e["tags"])
    print(f"Wrote {len(final)} words ({auth} authentic examples) → {OUT}")

    checks = [
        "bonjour",
        "maison",
        "chien",
        "manger",
        "eau",
        "merci",
        "livre",
        "femme",
        "garçon",
        "temps",
    ]
    for w in checks:
        e = next((x for x in final if x["word"].lower() == w), None)
        if not e:
            print(w, "MISSING")
            continue
        print(
            f"{w}: {e['ipa']} | {e['meaning'][:55]} | {e['sentences'][0]['text'][:55]} | {e['tags']}"
        )


if __name__ == "__main__":
    main()
