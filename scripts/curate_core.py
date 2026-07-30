#!/usr/bin/env python3
"""Fetch primary Wiktionary senses for core learner words and merge into french.json."""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DICT = ROOT / "data" / "french.json"
OUT_OVERRIDES = ROOT / "data" / "curated-overrides.json"
UA = {"User-Agent": "SakanaVocabulary/0.1 (educational; VS Code extension)"}

CORE = """
bonjour merci oui non homme femme garçon fille enfant ami amie maison appartement
rue ville pays monde eau pain fromage vin lait café thé bière viande poisson fruit
légume pomme riz sucre sel chien chat oiseau cheval livre école travail bureau
magasin restaurant hôtel voiture train bus avion vélo temps jour nuit matin soir
année mois semaine heure minute demain hier maintenant toujours jamais souvent
petit grand bon mauvais beau nouveau vieux jeune long court haut bas chaud froid
facile difficile heureux triste fatigué malade manger boire parler faire aller
venir voir savoir pouvoir vouloir devoir prendre mettre donner trouver aimer
regarder écouter lire écrire acheter vendre travailler étudier comprendre penser
croire être avoir père mère frère sœur fils famille gens personne tête main pied
œil oreille bouche nez bras jambe cœur rouge bleu vert blanc noir jaune
un deux trois quatre cinq six sept huit neuf dix cent mille beaucoup pardon
argent prix euro soleil pluie neige vent ciel mer montagne porte fenêtre table
chaise lit question réponse problème idée musique film photo téléphone ordinateur
internet français anglais salut pain
au-revoir
""".split()


def strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", "", html or "")
    return re.sub(r"\s+", " ", text).replace("&nbsp;", " ").strip()


def fetch_definition(word: str):
    url = (
        "https://en.wiktionary.org/api/rest_v1/page/definition/"
        + urllib.parse.quote(word)
    )
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def primary_french(data: dict):
    for block in data.get("fr") or []:
        pos = (block.get("partOfSpeech") or "").lower()
        for d in block.get("definitions") or []:
            meaning = strip_html(d.get("definition") or "")
            if not meaning or "inflection of" in meaning.lower():
                continue
            sents = []
            for ex in d.get("parsedExamples") or []:
                text = strip_html(ex.get("example") or "")
                tr = strip_html(ex.get("translation") or ex.get("literally") or "")
                if text and tr:
                    sents.append({"text": text, "translation": tr})
            return pos, meaning[:240], sents
    return None, None, []


def main() -> None:
    payload = json.loads(DICT.read_text(encoding="utf-8"))
    by = {e["word"].lower(): e for e in payload["words"]}
    # also alias ids
    seen = set()
    uniq = []
    for w in CORE:
        k = w.lower()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(w)

    overrides = []
    for w in uniq:
        try:
            data = fetch_definition(w)
        except Exception as exc:  # noqa: BLE001
            print("fail", w, exc)
            continue
        pos, meaning, sents = primary_french(data)
        if not meaning:
            print("no fr", w)
            continue
        prev = by.get(w.lower())
        if not prev:
            print("missing in dict", w)
            continue
        if not sents:
            if prev.get("sentences") and "synthetic-example" not in prev.get("tags", []):
                sents = prev["sentences"]
            else:
                m = meaning.split(";")[0].split(",")[0].strip()
                sents = [
                    {
                        "text": f"Le mot « {prev['word']} » veut dire « {m} ».",
                        "translation": f'The word "{prev["word"]}" means "{m}".',
                    }
                ]
        entry = {
            "id": prev["id"],
            "language": "fr",
            "word": prev["word"],
            "ipa": prev["ipa"],
            "meaning": meaning,
            "pos": pos or prev.get("pos"),
            "sentences": sents[:3],
            "tags": ["wiktionary", "frequency", "curated-primary"],
        }
        overrides.append(entry)
        print(f"ok {w}: {meaning[:55]} | {sents[0]['text'][:45]}")
        time.sleep(0.04)

    OUT_OVERRIDES.write_text(json.dumps(overrides, ensure_ascii=False, indent=2), encoding="utf-8")

    # Merge: curated overrides replace matching ids
    ov_by_id = {e["id"]: e for e in overrides}
    merged = []
    replaced = 0
    for e in payload["words"]:
        if e["id"] in ov_by_id:
            merged.append(ov_by_id[e["id"]])
            replaced += 1
        else:
            merged.append(e)
    payload["words"] = merged
    payload["count"] = len(merged)
    payload["version"] = 3
    DICT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Merged {replaced} curated overrides; total {len(merged)}")


if __name__ == "__main__":
    main()
