#!/usr/bin/env python3
"""
Reorder data/french.json for a gentle learner path:

  starter (thematic everyday) → A1 → A2 → B1 → B2 → C1 → C2 → ungraded

CEFR levels from FLELex (Beacco). Within each level, more frequent / shorter
everyday words come first. Function-word dumps are avoided at the very start.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DICT = ROOT / "data" / "french.json"
FLELEX = Path("/tmp/flelex/FleLex_TT_Beacco.tsv")
FREQ = Path("/tmp/fr_freq.txt")

LEVEL_ORDER = {"starter": 0, "A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6, "ungraded": 7}

# Explicit gentle onboarding path for absolute beginners (daily survival → people →
# places/things → verbs → descriptors → glue words). Only words present in the dict
# will be used; order within this list is the teaching order.
STARTER_PATH = [
    # Greetings & politeness
    "bonjour",
    "salut",
    "merci",
    "oui",
    "non",
    "pardon",
    # People
    "je",
    "tu",
    "il",
    "elle",
    "nous",
    "vous",
    "homme",
    "femme",
    "enfant",
    "ami",
    "amie",
    "père",
    "mère",
    "frère",
    "sœur",
    "famille",
    # Everyday places & things
    "maison",
    "école",
    "travail",
    "ville",
    "rue",
    "eau",
    "pain",
    "fromage",
    "vin",
    "café",
    "thé",
    "lait",
    "livre",
    "voiture",
    "train",
    "chien",
    "chat",
    "table",
    "porte",
    "fenêtre",
    # Time of day
    "jour",
    "nuit",
    "matin",
    "soir",
    "aujourd'hui",
    "demain",
    "hier",
    "temps",
    # Core verbs
    "être",
    "avoir",
    "aller",
    "faire",
    "parler",
    "manger",
    "boire",
    "voir",
    "aimer",
    "vouloir",
    "pouvoir",
    "savoir",
    "venir",
    "prendre",
    "donner",
    "lire",
    "écrire",
    "acheter",
    "travailler",
    "comprendre",
    # Simple descriptors
    "bon",
    "petit",
    "grand",
    "beau",
    "nouveau",
    "jeune",
    "vieux",
    "chaud",
    "froid",
    "facile",
    "difficile",
    "heureux",
    "triste",
    "rouge",
    "bleu",
    "vert",
    "blanc",
    "noir",
    # Numbers
    "un",
    "deux",
    "trois",
    "quatre",
    "cinq",
    "six",
    "sept",
    "huit",
    "neuf",
    "dix",
    # Essential sentence glue (after concrete words)
    "et",
    "ou",
    "mais",
    "pas",
    "ne",
    "de",
    "à",
    "dans",
    "avec",
    "pour",
    "sur",
    "sous",
    "chez",
    "sans",
    "très",
    "bien",
    "aussi",
    "ici",
    "là",
    "maintenant",
    "toujours",
    "souvent",
    "quand",
    "où",
    "comment",
    "pourquoi",
    "qui",
    "que",
    "quoi",
    "ce",
    "cette",
    "mon",
    "ma",
    "ton",
    "ta",
    "son",
    "sa",
    "le",
    "la",
    "les",
    "un",
    "une",
    "des",
    # Common spoken forms
    "est",
    "suis",
    "ai",
    "va",
    "fait",
    "dit",
    "ça",
    "moi",
    "toi",
]

POS_TO_TT = {
    "noun": "NOM",
    "verb": "VER",
    "adj": "ADJ",
    "adv": "ADV",
    "prep": "PRP",
    "pron": "PRO",
    "art": "DET:ART",
    "det": "DET:ART",
    "conj": "KON",
    "interj": "INT",
    "particle": "ADV",
}

PROPER_RE = re.compile(r"^[A-ZÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ]")


def load_flelex() -> dict[str, str]:
    """lemma(lower) -> best (earliest) CEFR level across POS."""
    best: dict[str, str] = {}
    with FLELEX.open(encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            w = row["word"].strip().lower()
            lv = row["level"].strip()
            if lv not in LEVEL_ORDER:
                continue
            if w not in best or LEVEL_ORDER[lv] < LEVEL_ORDER[best[w]]:
                best[w] = lv
    return best


def load_freq_rank() -> dict[str, int]:
    rank: dict[str, int] = {}
    with FREQ.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            w = line.split()[0].lower()
            if w not in rank:
                rank[w] = i
    return rank


def estimate_level(word: str, freq_rank: dict[str, int], flelex: dict[str, str]) -> str:
    key = word.lower()
    if key in flelex:
        return flelex[key]
    r = freq_rank.get(key, 50_000)
    if r < 800:
        return "A1"
    if r < 2000:
        return "A2"
    if r < 4000:
        return "B1"
    if r < 7000:
        return "B2"
    if r < 12000:
        return "C1"
    return "C2"


def difficulty_key(entry: dict, level: str, freq_rank: dict[str, int], starter_idx: dict[str, int]):
    key = entry["word"].lower()
    # Proper nouns / names later within level
    proper_penalty = 1 if PROPER_RE.match(entry["word"]) and entry.get("pos") == "noun" else 0
    # Prefer shorter concrete-ish words earlier
    length = len(key)
    freq = freq_rank.get(key, 50_000)
    starter = starter_idx.get(key, 10_000)
    if level == "starter":
        return (LEVEL_ORDER["starter"], starter, freq, length)
    return (LEVEL_ORDER.get(level, 7), proper_penalty, freq, length, key)


def main() -> None:
    payload = json.loads(DICT.read_text(encoding="utf-8"))
    words = payload["words"]
    by_key = {e["word"].lower(): e for e in words}

    flelex = load_flelex()
    freq_rank = load_freq_rank()

    starter_idx = {}
    for i, w in enumerate(STARTER_PATH):
        if w.lower() not in starter_idx and w.lower() in by_key:
            starter_idx[w.lower()] = i

    enriched = []
    for e in words:
        key = e["word"].lower()
        if key in starter_idx:
            level = "starter"
        else:
            level = estimate_level(e["word"], freq_rank, flelex)
        e = dict(e)
        e["level"] = level
        tags = list(e.get("tags") or [])
        if level == "starter" and "starter" not in tags:
            tags.append("starter")
        if level.startswith("A") or level.startswith("B") or level.startswith("C"):
            tag = f"cefr-{level.lower()}"
            if tag not in tags:
                tags.append(tag)
        e["tags"] = tags
        enriched.append(e)

    enriched.sort(key=lambda e: difficulty_key(e, e["level"], freq_rank, starter_idx))
    for i, e in enumerate(enriched):
        e["order"] = i + 1

    payload["words"] = enriched
    payload["count"] = len(enriched)
    payload["version"] = 5
    payload["learningPath"] = {
        "description": "starter (everyday survival) → CEFR A1→C2 → ungraded",
        "cefrSource": "FLELex Beacco (UCLouvain CEFRLex)",
        "cefrUrl": "https://cental.uclouvain.be/cefrlex/flelex/",
        "starterCount": sum(1 for e in enriched if e["level"] == "starter"),
        "levelCounts": {
            lv: sum(1 for e in enriched if e["level"] == lv)
            for lv in ["starter", "A1", "A2", "B1", "B2", "C1", "C2", "ungraded"]
        },
    }
    # keep sources list, append flelex
    sources = payload.get("sources") or []
    if not any("FLELex" in (s.get("name") or "") for s in sources):
        sources.append(
            {
                "name": "FLELex / CEFRLex (Beacco)",
                "url": "https://cental.uclouvain.be/cefrlex/flelex/",
                "license": "CC BY-NC-SA 4.0",
                "usedFor": "CEFR difficulty ordering (A1–C2)",
            }
        )
    payload["sources"] = sources

    DICT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("levelCounts", payload["learningPath"]["levelCounts"])
    print("--- first 60 (gentle start) ---")
    for e in enriched[:60]:
        print(f"{e['order']:4} [{e['level']:7}] {e['word']:15} {e['meaning'][:45]}")
    print("--- end of starter / start A1 ---")
    # find first A1
    for e in enriched:
        if e["level"] == "A1":
            idx = e["order"]
            break
    print(f"first A1 at order {idx}")
    print([e["word"] for e in enriched if e["order"] >= idx][:20])


if __name__ == "__main__":
    main()
