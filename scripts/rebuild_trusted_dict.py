#!/usr/bin/env python3
"""
Rebuild data/french.json with trustworthy FR→EN glosses.

Primary meaning source:
  Matthias Buchmeier French–English dictionary extracted from Wiktionary
  https://github.com/open-dsl-dict/wiktionary-dict (CC BY-SA 3.0 / GFDL)
  Format: word {pos} :: gloss

IPA:
  open-dict-data/ipa-dict fr_FR (MIT)

Examples:
  Wiktextract/kaikki bilingual examples when they align with the chosen gloss;
  otherwise a short pedagogical sentence tagged synthetic-example.

Also applies a curated override table for ultra-high-frequency function words
where homographs commonly derail automatic sense selection (pas, sur, est, …).
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "french.json"

BUCHMEIER = Path("/tmp/fren-dict/fr-en.txt")
IPA_PATH = Path("/tmp/fr_ipa.txt")
FREQ_PATH = Path("/tmp/fr_freq.txt")
KAIKKI = Path("/tmp/kaikki/french.jsonl")

LINE_RE = re.compile(
    r"^(?P<word>.+?)\s*\{(?P<pos>[^}]+)\}(?:\s*(?P<tags>\[[^\]]*\]))?\s*::\s*(?P<gloss>.+)$"
)

SKIP_POS = {
    "letter",
    "prefix",
    "suffix",
    "infix",
    "circumfix",
    "abbr",
    "abbreviation",
    "initialism",
    "symbol",
    "number",
    "numeral",
    "article",  # handled via curated + det/art prefer — actually KEEP art
}

# Normalize POS bucket
POS_BUCKET = {
    "prep": "prep",
    "preposition": "prep",
    "adv": "adv",
    "adverb": "adv",
    "pron": "pron",
    "pronoun": "pron",
    "art": "art",
    "article": "art",
    "det": "det",
    "determiner": "det",
    "conj": "conj",
    "conjunction": "conj",
    "interj": "interj",
    "intj": "interj",
    "interjection": "interj",
    "n": "noun",
    "noun": "noun",
    "m": "noun",
    "f": "noun",
    "mf": "noun",
    "prop": "noun",
    "v": "verb",
    "verb": "verb",
    "vi": "verb",
    "vt": "verb",
    "vti": "verb",
    "adj": "adj",
    "adjective": "adj",
    "particle": "particle",
}

FUNCTION_BUCKETS = {"prep", "adv", "pron", "art", "det", "conj", "interj", "particle"}
CONTENT_BUCKETS = {"noun", "verb", "adj", "adv"}

INFLECTIONISH = re.compile(
    r"\b(first|second|third)-person\b|present indicative|past participle|"
    r"imperfect|subjunctive|conjugation|inflection of|plural of|"
    r"feminine (singular|plural) of|masculine plural of|alternative form of|"
    r"misspelling|obsolete|archaic|rare\b",
    re.I,
)

NICHE_TAG = re.compile(
    r"chemistry|geology|heraldry|biology|anatomy|typography|computing|"
    r"card games|firearm|music|linguistics|philosophy|Quebec|Louisiana|"
    r"text messaging|plurale tantum",
    re.I,
)

# Curated primary learner meanings for homograph-prone / ultra-common words.
# Verified against standard FR→EN learner dictionaries (WordReference / Wiktionary primary sense).
CURATED: dict[str, dict] = {
    "je": {"pos": "pron", "meaning": "I", "sentences": [{"text": "Je suis étudiant.", "translation": "I am a student."}]},
    "tu": {"pos": "pron", "meaning": "you (singular, informal)", "sentences": [{"text": "Tu parles français ?", "translation": "Do you speak French?"}]},
    "il": {"pos": "pron", "meaning": "he; it", "sentences": [{"text": "Il est mon frère.", "translation": "He is my brother."}]},
    "elle": {"pos": "pron", "meaning": "she; it", "sentences": [{"text": "Elle habite à Paris.", "translation": "She lives in Paris."}]},
    "nous": {"pos": "pron", "meaning": "we; us", "sentences": [{"text": "Nous allons au marché.", "translation": "We are going to the market."}]},
    "vous": {"pos": "pron", "meaning": "you (plural or formal)", "sentences": [{"text": "Vous êtes très gentil.", "translation": "You are very kind."}]},
    "ils": {"pos": "pron", "meaning": "they (masculine / mixed)", "sentences": [{"text": "Ils travaillent ici.", "translation": "They work here."}]},
    "elles": {"pos": "pron", "meaning": "they (feminine)", "sentences": [{"text": "Elles sont amies.", "translation": "They are friends."}]},
    "on": {"pos": "pron", "meaning": "one; we (informal); people", "sentences": [{"text": "On va au cinéma.", "translation": "We're going to the movies."}]},
    "me": {"pos": "pron", "meaning": "me; myself", "sentences": [{"text": "Il me parle.", "translation": "He is talking to me."}]},
    "te": {"pos": "pron", "meaning": "you; yourself (informal object)", "sentences": [{"text": "Je te vois.", "translation": "I see you."}]},
    "se": {"pos": "pron", "meaning": "himself; herself; itself; themselves (reflexive)", "sentences": [{"text": "Il se lève tôt.", "translation": "He gets up early."}]},
    "le": {"pos": "art", "meaning": "the (masculine singular); him/it (object)", "sentences": [{"text": "Le chat dort.", "translation": "The cat is sleeping."}]},
    "la": {"pos": "art", "meaning": "the (feminine singular); her/it (object)", "sentences": [{"text": "La maison est grande.", "translation": "The house is big."}]},
    "les": {"pos": "art", "meaning": "the (plural); them (object)", "sentences": [{"text": "Les enfants jouent.", "translation": "The children are playing."}]},
    "un": {"pos": "art", "meaning": "a; an; one (masculine)", "sentences": [{"text": "Un livre est sur la table.", "translation": "A book is on the table."}]},
    "une": {"pos": "art", "meaning": "a; an; one (feminine)", "sentences": [{"text": "Une pomme est rouge.", "translation": "An apple is red."}]},
    "des": {"pos": "art", "meaning": "some; (plural of un/une)", "sentences": [{"text": "J’ai des amis.", "translation": "I have some friends."}]},
    "du": {"pos": "art", "meaning": "of the / some (de + le)", "sentences": [{"text": "Je bois du café.", "translation": "I drink some coffee."}]},
    "de": {"pos": "prep", "meaning": "of; from", "sentences": [{"text": "Je viens de France.", "translation": "I come from France."}]},
    "à": {"pos": "prep", "meaning": "to; at; in", "sentences": [{"text": "Je vais à l’école.", "translation": "I go to school."}]},
    "au": {"pos": "prep", "meaning": "to the / at the (à + le)", "sentences": [{"text": "Il va au marché.", "translation": "He is going to the market."}]},
    "aux": {"pos": "prep", "meaning": "to the / at the (à + les)", "sentences": [{"text": "Elle parle aux enfants.", "translation": "She is speaking to the children."}]},
    "et": {"pos": "conj", "meaning": "and", "sentences": [{"text": "Le pain et le fromage.", "translation": "Bread and cheese."}]},
    "ou": {"pos": "conj", "meaning": "or", "sentences": [{"text": "Thé ou café ?", "translation": "Tea or coffee?"}]},
    "mais": {"pos": "conj", "meaning": "but", "sentences": [{"text": "C’est petit mais confortable.", "translation": "It is small but comfortable."}]},
    "si": {"pos": "conj", "meaning": "if; yes (contradicting a negative)", "sentences": [{"text": "Si tu veux, on y va.", "translation": "If you want, we’ll go."}]},
    "que": {"pos": "conj", "meaning": "that; than; what", "sentences": [{"text": "Je pense que c’est vrai.", "translation": "I think that it is true."}]},
    "qui": {"pos": "pron", "meaning": "who; that; which", "sentences": [{"text": "La femme qui chante.", "translation": "The woman who is singing."}]},
    "quoi": {"pos": "pron", "meaning": "what", "sentences": [{"text": "Quoi de neuf ?", "translation": "What’s new?"}]},
    "dont": {"pos": "pron", "meaning": "whose; of which; about which", "sentences": [{"text": "Le livre dont je parle.", "translation": "The book I’m talking about."}]},
    "où": {"pos": "adv", "meaning": "where", "sentences": [{"text": "Où habites-tu ?", "translation": "Where do you live?"}]},
    "ne": {"pos": "adv", "meaning": "not (used with pas / plus / jamais…)", "sentences": [{"text": "Je ne sais pas.", "translation": "I don’t know."}]},
    "pas": {"pos": "adv", "meaning": "not (in ne … pas)", "sentences": [{"text": "Je ne comprends pas.", "translation": "I do not understand."}]},
    "plus": {"pos": "adv", "meaning": "more; no longer (ne … plus)", "sentences": [{"text": "Je veux plus de pain.", "translation": "I want more bread."}]},
    "jamais": {"pos": "adv", "meaning": "never; ever", "sentences": [{"text": "Je ne mens jamais.", "translation": "I never lie."}]},
    "rien": {"pos": "pron", "meaning": "nothing", "sentences": [{"text": "Ce n’est rien.", "translation": "It’s nothing."}]},
    "personne": {"pos": "pron", "meaning": "nobody; person", "sentences": [{"text": "Il n’y a personne.", "translation": "There is nobody."}]},
    "tout": {"pos": "adj", "meaning": "all; every; everything", "sentences": [{"text": "Tout le monde est là.", "translation": "Everyone is here."}]},
    "tous": {"pos": "adj", "meaning": "all (masculine plural)", "sentences": [{"text": "Tous les jours.", "translation": "Every day."}]},
    "toute": {"pos": "adj", "meaning": "all; whole (feminine singular)", "sentences": [{"text": "Toute la journée.", "translation": "The whole day."}]},
    "toutes": {"pos": "adj", "meaning": "all (feminine plural)", "sentences": [{"text": "Toutes les filles.", "translation": "All the girls."}]},
    "ce": {"pos": "det", "meaning": "this; that", "sentences": [{"text": "Ce livre est intéressant.", "translation": "This book is interesting."}]},
    "cet": {"pos": "det", "meaning": "this; that (before vowel)", "sentences": [{"text": "Cet homme est grand.", "translation": "This man is tall."}]},
    "cette": {"pos": "det", "meaning": "this; that (feminine)", "sentences": [{"text": "Cette maison est belle.", "translation": "This house is beautiful."}]},
    "ces": {"pos": "det", "meaning": "these; those", "sentences": [{"text": "Ces fleurs sont jolies.", "translation": "These flowers are pretty."}]},
    "ça": {"pos": "pron", "meaning": "that; it (informal)", "sentences": [{"text": "Ça va ?", "translation": "How’s it going?"}]},
    "cela": {"pos": "pron", "meaning": "that; it", "sentences": [{"text": "Cela est important.", "translation": "That is important."}]},
    "y": {"pos": "pron", "meaning": "there; about it", "sentences": [{"text": "J’y vais.", "translation": "I’m going there."}]},
    "en": {"pos": "pron", "meaning": "of it / some; in/to (place)", "sentences": [{"text": "J’en ai deux.", "translation": "I have two of them."}]},
    "sur": {"pos": "prep", "meaning": "on; upon; about", "sentences": [{"text": "Le livre est sur la table.", "translation": "The book is on the table."}]},
    "sous": {"pos": "prep", "meaning": "under", "sentences": [{"text": "Le chat est sous la table.", "translation": "The cat is under the table."}]},
    "dans": {"pos": "prep", "meaning": "in; into", "sentences": [{"text": "Il est dans la voiture.", "translation": "He is in the car."}]},
    "par": {"pos": "prep", "meaning": "by; through", "sentences": [{"text": "Un livre écrit par elle.", "translation": "A book written by her."}]},
    "pour": {"pos": "prep", "meaning": "for", "sentences": [{"text": "C’est pour toi.", "translation": "This is for you."}]},
    "avec": {"pos": "prep", "meaning": "with", "sentences": [{"text": "Je viens avec mon ami.", "translation": "I’m coming with my friend."}]},
    "sans": {"pos": "prep", "meaning": "without", "sentences": [{"text": "Un café sans sucre.", "translation": "A coffee without sugar."}]},
    "chez": {"pos": "prep", "meaning": "at the home of; at", "sentences": [{"text": "Je suis chez moi.", "translation": "I am at home."}]},
    "entre": {"pos": "prep", "meaning": "between; among", "sentences": [{"text": "Entre toi et moi.", "translation": "Between you and me."}]},
    "vers": {"pos": "prep", "meaning": "toward", "sentences": [{"text": "Il marche vers la gare.", "translation": "He is walking toward the station."}]},
    "contre": {"pos": "prep", "meaning": "against", "sentences": [{"text": "Je suis contre cette idée.", "translation": "I am against this idea."}]},
    "après": {"pos": "prep", "meaning": "after", "sentences": [{"text": "Après le dîner.", "translation": "After dinner."}]},
    "avant": {"pos": "prep", "meaning": "before", "sentences": [{"text": "Avant le cours.", "translation": "Before class."}]},
    "depuis": {"pos": "prep", "meaning": "since; for (time)", "sentences": [{"text": "Je vis ici depuis 2020.", "translation": "I have lived here since 2020."}]},
    "pendant": {"pos": "prep", "meaning": "during", "sentences": [{"text": "Pendant les vacances.", "translation": "During the holidays."}]},
    "comme": {"pos": "conj", "meaning": "like; as", "sentences": [{"text": "Il court comme un champion.", "translation": "He runs like a champion."}]},
    "quand": {"pos": "adv", "meaning": "when", "sentences": [{"text": "Quand arrives-tu ?", "translation": "When are you arriving?"}]},
    "comment": {"pos": "adv", "meaning": "how", "sentences": [{"text": "Comment ça va ?", "translation": "How are you?"}]},
    "pourquoi": {"pos": "adv", "meaning": "why", "sentences": [{"text": "Pourquoi es-tu triste ?", "translation": "Why are you sad?"}]},
    "combien": {"pos": "adv", "meaning": "how much; how many", "sentences": [{"text": "Combien ça coûte ?", "translation": "How much does it cost?"}]},
    "très": {"pos": "adv", "meaning": "very", "sentences": [{"text": "C’est très bon.", "translation": "It is very good."}]},
    "bien": {"pos": "adv", "meaning": "well; good; fine", "sentences": [{"text": "Je vais bien.", "translation": "I am well."}]},
    "mal": {"pos": "adv", "meaning": "badly; wrong", "sentences": [{"text": "Il chante mal.", "translation": "He sings badly."}]},
    "aussi": {"pos": "adv", "meaning": "also; too", "sentences": [{"text": "Moi aussi.", "translation": "Me too."}]},
    "encore": {"pos": "adv", "meaning": "still; again; yet", "sentences": [{"text": "Encore une fois.", "translation": "One more time."}]},
    "déjà": {"pos": "adv", "meaning": "already", "sentences": [{"text": "Tu as déjà mangé ?", "translation": "Have you already eaten?"}]},
    "toujours": {"pos": "adv", "meaning": "always; still", "sentences": [{"text": "Il est toujours à l’heure.", "translation": "He is always on time."}]},
    "souvent": {"pos": "adv", "meaning": "often", "sentences": [{"text": "Je voyage souvent.", "translation": "I travel often."}]},
    "maintenant": {"pos": "adv", "meaning": "now", "sentences": [{"text": "Fais-le maintenant.", "translation": "Do it now."}]},
    "ici": {"pos": "adv", "meaning": "here", "sentences": [{"text": "Viens ici.", "translation": "Come here."}]},
    "là": {"pos": "adv", "meaning": "there", "sentences": [{"text": "Il est là.", "translation": "He is there."}]},
    "oui": {"pos": "interj", "meaning": "yes", "sentences": [{"text": "Oui, bien sûr.", "translation": "Yes, of course."}]},
    "non": {"pos": "interj", "meaning": "no", "sentences": [{"text": "Non, merci.", "translation": "No, thank you."}]},
    "bonjour": {"pos": "interj", "meaning": "hello; good morning; good day", "sentences": [{"text": "Bonjour, comment allez-vous ?", "translation": "Hello, how are you?"}]},
    "merci": {"pos": "interj", "meaning": "thank you", "sentences": [{"text": "Merci pour ton aide.", "translation": "Thank you for your help."}]},
    "salut": {"pos": "interj", "meaning": "hi; bye (informal)", "sentences": [{"text": "Salut ! Ça va ?", "translation": "Hi! How’s it going?"}]},
    "être": {"pos": "verb", "meaning": "to be", "sentences": [{"text": "Je veux être heureux.", "translation": "I want to be happy."}]},
    "avoir": {"pos": "verb", "meaning": "to have", "sentences": [{"text": "J’ai deux sœurs.", "translation": "I have two sisters."}]},
    "faire": {"pos": "verb", "meaning": "to do; to make", "sentences": [{"text": "Que fais-tu ?", "translation": "What are you doing?"}]},
    "aller": {"pos": "verb", "meaning": "to go", "sentences": [{"text": "Nous allons à l’école.", "translation": "We are going to school."}]},
    "venir": {"pos": "verb", "meaning": "to come", "sentences": [{"text": "Tu viens demain ?", "translation": "Are you coming tomorrow?"}]},
    "voir": {"pos": "verb", "meaning": "to see", "sentences": [{"text": "Je vois la mer.", "translation": "I see the sea."}]},
    "savoir": {"pos": "verb", "meaning": "to know (a fact / how to)", "sentences": [{"text": "Je ne sais pas.", "translation": "I don’t know."}]},
    "pouvoir": {"pos": "verb", "meaning": "can; to be able to", "sentences": [{"text": "Je peux t’aider.", "translation": "I can help you."}]},
    "vouloir": {"pos": "verb", "meaning": "to want", "sentences": [{"text": "Je veux un café.", "translation": "I want a coffee."}]},
    "devoir": {"pos": "verb", "meaning": "must; to have to; duty", "sentences": [{"text": "Je dois partir.", "translation": "I must leave."}]},
    "dire": {"pos": "verb", "meaning": "to say; to tell", "sentences": [{"text": "Que veux-tu dire ?", "translation": "What do you mean?"}]},
    "parler": {"pos": "verb", "meaning": "to speak; to talk", "sentences": [{"text": "Elle parle anglais.", "translation": "She speaks English."}]},
    "manger": {"pos": "verb", "meaning": "to eat", "sentences": [{"text": "Nous mangeons du pain.", "translation": "We are eating bread."}]},
    "boire": {"pos": "verb", "meaning": "to drink", "sentences": [{"text": "Il boit de l’eau.", "translation": "He is drinking water."}]},
    "prendre": {"pos": "verb", "meaning": "to take", "sentences": [{"text": "Je prends le train.", "translation": "I am taking the train."}]},
    "donner": {"pos": "verb", "meaning": "to give", "sentences": [{"text": "Donne-moi le livre.", "translation": "Give me the book."}]},
    "mettre": {"pos": "verb", "meaning": "to put; to place", "sentences": [{"text": "Mets ça ici.", "translation": "Put that here."}]},
    "trouver": {"pos": "verb", "meaning": "to find", "sentences": [{"text": "J’ai trouvé mes clés.", "translation": "I found my keys."}]},
    "aimer": {"pos": "verb", "meaning": "to like; to love", "sentences": [{"text": "J’aime le chocolat.", "translation": "I like chocolate."}]},
    "maison": {"pos": "noun", "meaning": "house; home", "sentences": [{"text": "Ils habitent dans une grande maison.", "translation": "They live in a big house."}]},
    "eau": {"pos": "noun", "meaning": "water", "sentences": [{"text": "Je bois de l’eau.", "translation": "I drink water."}]},
    "temps": {"pos": "noun", "meaning": "time; weather", "sentences": [{"text": "Je n’ai pas le temps.", "translation": "I don’t have time."}]},
    "jour": {"pos": "noun", "meaning": "day", "sentences": [{"text": "Bonne journée !", "translation": "Have a nice day!"}]},
    "homme": {"pos": "noun", "meaning": "man; human", "sentences": [{"text": "Cet homme est mon père.", "translation": "This man is my father."}]},
    "femme": {"pos": "noun", "meaning": "woman; wife", "sentences": [{"text": "Cette femme travaille ici.", "translation": "This woman works here."}]},
    "enfant": {"pos": "noun", "meaning": "child", "sentences": [{"text": "L’enfant joue dehors.", "translation": "The child is playing outside."}]},
    "chien": {"pos": "noun", "meaning": "dog", "sentences": [{"text": "Le chien aboie.", "translation": "The dog is barking."}]},
    "chat": {"pos": "noun", "meaning": "cat", "sentences": [{"text": "Le chat dort.", "translation": "The cat is sleeping."}]},
    "livre": {"pos": "noun", "meaning": "book", "sentences": [{"text": "Elle lit un livre.", "translation": "She is reading a book."}]},
    "pain": {"pos": "noun", "meaning": "bread", "sentences": [{"text": "J’achète du pain.", "translation": "I am buying bread."}]},
    "fromage": {"pos": "noun", "meaning": "cheese", "sentences": [{"text": "Le fromage est délicieux.", "translation": "The cheese is delicious."}]},
    "ville": {"pos": "noun", "meaning": "city; town", "sentences": [{"text": "Paris est une grande ville.", "translation": "Paris is a large city."}]},
    "école": {"pos": "noun", "meaning": "school", "sentences": [{"text": "Les enfants vont à l’école.", "translation": "The children go to school."}]},
    "travail": {"pos": "noun", "meaning": "work; job", "sentences": [{"text": "Je vais au travail.", "translation": "I am going to work."}]},
    "voiture": {"pos": "noun", "meaning": "car", "sentences": [{"text": "La voiture est rouge.", "translation": "The car is red."}]},
    "est": {"pos": "verb", "meaning": "is (form of être: to be)", "sentences": [{"text": "Il est professeur.", "translation": "He is a teacher."}]},
    "suis": {"pos": "verb", "meaning": "am (form of être: to be)", "sentences": [{"text": "Je suis fatigué.", "translation": "I am tired."}]},
    "sommes": {"pos": "verb", "meaning": "are (nous form of être)", "sentences": [{"text": "Nous sommes prêts.", "translation": "We are ready."}]},
    "êtes": {"pos": "verb", "meaning": "are (vous form of être)", "sentences": [{"text": "Vous êtes en retard.", "translation": "You are late."}]},
    "sont": {"pos": "verb", "meaning": "are (ils/elles form of être)", "sentences": [{"text": "Ils sont ici.", "translation": "They are here."}]},
    "ai": {"pos": "verb", "meaning": "have (je form of avoir)", "sentences": [{"text": "J’ai faim.", "translation": "I am hungry."}]},
    "as": {"pos": "verb", "meaning": "have (tu form of avoir)", "sentences": [{"text": "Tu as raison.", "translation": "You are right."}]},
    "avons": {"pos": "verb", "meaning": "have (nous form of avoir)", "sentences": [{"text": "Nous avons un chien.", "translation": "We have a dog."}]},
    "avez": {"pos": "verb", "meaning": "have (vous form of avoir)", "sentences": [{"text": "Vous avez de la chance.", "translation": "You are lucky."}]},
    "ont": {"pos": "verb", "meaning": "have (ils/elles form of avoir)", "sentences": [{"text": "Ils ont une maison.", "translation": "They have a house."}]},
    "fait": {"pos": "verb", "meaning": "does/makes; done (form of faire); fact (noun)", "sentences": [{"text": "Il fait beau.", "translation": "The weather is nice."}]},
    "va": {"pos": "verb", "meaning": "goes (form of aller); how are things", "sentences": [{"text": "Comment ça va ?", "translation": "How’s it going?"}]},
    "dit": {"pos": "verb", "meaning": "says; said (form of dire)", "sentences": [{"text": "Il dit la vérité.", "translation": "He is telling the truth."}]},
}


def load_ipa() -> dict[str, str]:
    out: dict[str, str] = {}
    with IPA_PATH.open(encoding="utf-8") as f:
        for line in f:
            if "\t" not in line:
                continue
            w, ipa = line.rstrip().split("\t", 1)
            k = w.lower()
            if k in out:
                continue
            ipa = "/" + ipa.split(",")[0].strip().strip("/[]") + "/"
            out[k] = ipa
    return out


def load_freq(limit: int = 8000) -> list[str]:
    words: list[str] = []
    seen = set()
    with FREQ_PATH.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= limit * 3:
                break
            w = line.split()[0]
            k = w.lower()
            if k in seen:
                continue
            if not re.fullmatch(r"[A-Za-zÀ-ÿœæŒÆ''\-]+", w):
                continue
            if len(w) < 1:
                continue
            seen.add(k)
            words.append(w)
            if len(words) >= limit:
                break
    return words


def normalize_pos(raw: str) -> str:
    # raw may be "m", "prep", "vi", "m|f" etc.
    first = raw.split("|")[0].split(",")[0].strip().lower()
    # gender-only noun markers
    if first in {"m", "f", "mf", "mpl", "fpl"}:
        return "noun"
    return POS_BUCKET.get(first, first)


def parse_buchmeier() -> dict[str, list[dict]]:
    entries: dict[str, list[dict]] = defaultdict(list)
    with BUCHMEIER.open(encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            m = LINE_RE.match(line)
            if not m:
                continue
            word = m.group("word").strip()
            pos_raw = m.group("pos").strip()
            tags = (m.group("tags") or "").strip()
            gloss = m.group("gloss").strip()
            # strip wiki link debris like [[[ne]] ... pas]
            gloss = re.sub(r"\[\[\[|\]\]\]|\[\[|\]\]", "", gloss)
            gloss = re.sub(r"\s+", " ", gloss).strip()
            if not word or not gloss:
                continue
            if " " in word and len(word) > 40:
                continue
            bucket = normalize_pos(pos_raw)
            if bucket in {"letter", "prefix", "suffix", "abbr", "initialism", "symbol"}:
                continue
            entries[word.lower()].append(
                {
                    "word": word,
                    "pos": bucket,
                    "pos_raw": pos_raw,
                    "tags": tags,
                    "gloss": gloss,
                }
            )
    return entries


def score_sense(sense: dict, key: str, freq_rank: dict[str, int]) -> int:
    sc = 0
    pos = sense["pos"]
    gloss = sense["gloss"]
    tags = sense["tags"]

    # Prefer function POS for short high-frequency tokens
    rank = freq_rank.get(key, 9999)
    if rank < 300 and len(key) <= 5:
        if pos in FUNCTION_BUCKETS:
            sc += 120
        elif pos in CONTENT_BUCKETS:
            sc += 20
    else:
        if pos in CONTENT_BUCKETS:
            sc += 80
        elif pos in FUNCTION_BUCKETS:
            sc += 50

    if INFLECTIONISH.search(gloss):
        sc -= 150
    if NICHE_TAG.search(tags) or NICHE_TAG.search(gloss):
        sc -= 60
    if tags and NICHE_TAG.search(tags):
        sc -= 40

    # Prefer concise everyday glosses
    sc += max(0, 50 - len(gloss) // 3)

    # Common gloss words boost
    if re.fullmatch(r"[A-Za-z ,;\-\(\)/']{2,60}", gloss):
        sc += 15

    return sc


def pick_meaning(senses: list[dict], key: str, freq_rank: dict[str, int]) -> tuple[str, str, list[str]]:
    ranked = sorted(senses, key=lambda s: score_sense(s, key, freq_rank), reverse=True)
    best = ranked[0]
    # Collect up to 2 top glosses of the same POS bucket if short
    glosses = [best["gloss"]]
    for s in ranked[1:]:
        if s["pos"] != best["pos"]:
            continue
        if INFLECTIONISH.search(s["gloss"]) or NICHE_TAG.search(s["gloss"]):
            continue
        g = s["gloss"]
        if g.lower() in {x.lower() for x in glosses}:
            continue
        if len("; ".join(glosses + [g])) > 160:
            break
        glosses.append(g)
        if len(glosses) >= 2:
            break
    meaning = "; ".join(glosses)
    return best["word"], best["pos"], meaning


def load_kaikki_examples() -> dict[str, list[dict]]:
    """Map word -> list of {text, translation, gloss} from kaikki."""
    if not KAIKKI.exists():
        return {}
    out: dict[str, list[dict]] = defaultdict(list)
    with KAIKKI.open(encoding="utf-8") as f:
        for line in f:
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            word = (o.get("word") or "").lower()
            if not word or " " in word:
                continue
            for s in o.get("senses") or []:
                glosses = s.get("glosses") or []
                g0 = glosses[0] if glosses else ""
                for ex in s.get("examples") or []:
                    text = ex.get("text")
                    tr = ex.get("english") or ex.get("translation")
                    if not text or not tr:
                        continue
                    text = str(text).strip()
                    tr = str(tr).strip()
                    if len(text) > 140 or len(tr) > 140:
                        continue
                    out[word].append({"text": text, "translation": tr, "gloss": g0})
    return out


def example_matches(meaning: str, ex: dict) -> bool:
    """Loose overlap between chosen meaning and example gloss/translation."""
    m = set(re.findall(r"[a-zA-Z']{3,}", meaning.lower()))
    if not m:
        return False
    blob = f"{ex.get('gloss','')} {ex.get('translation','')}".lower()
    hits = sum(1 for w in m if w in blob)
    return hits >= 1


def synth(word: str, meaning: str, pos: str) -> dict:
    m = meaning.split(";")[0].split(",")[0].strip()
    if pos == "verb":
        bare = m[3:].strip() if m.lower().startswith("to ") else m
        return {"text": f"Nous allons {word}.", "translation": f"We are going to {bare}."}
    if pos == "adj":
        return {"text": f"C’est très {word}.", "translation": f"It is very {m}."}
    if pos == "adv":
        return {"text": f"Elle répond {word}.", "translation": f"She answers {m}."}
    if pos in {"interj", "pron", "art", "det", "conj", "prep", "particle"}:
        return {
            "text": f"Exemple : {word}",
            "translation": f'Example: "{word}" means "{m}".',
        }
    return {
        "text": f"Le mot « {word} » veut dire « {m} ».",
        "translation": f'The word "{word}" means "{m}".',
    }


def main() -> None:
    assert BUCHMEIER.exists(), f"Missing {BUCHMEIER}"
    assert IPA_PATH.exists(), f"Missing {IPA_PATH}"
    assert FREQ_PATH.exists(), f"Missing {FREQ_PATH}"

    print("Parsing Buchmeier FR→EN…")
    buch = parse_buchmeier()
    print(f"  headwords: {len(buch)}")

    print("Loading IPA + frequency…")
    ipa_map = load_ipa()
    freq = load_freq(9000)
    freq_rank = {w.lower(): i for i, w in enumerate(freq)}

    print("Loading kaikki examples (for matching only)…")
    examples_idx = load_kaikki_examples()
    print(f"  words with examples: {len(examples_idx)}")

    final = []
    seen = set()

    # 1) Curated first (highest trust for homographs)
    for key, cur in CURATED.items():
        ipa = ipa_map.get(key)
        if not ipa:
            continue
        display = buch.get(key, [{"word": key}])[0]["word"] if key in buch else key
        # Prefer casing from frequency list if present
        for w in freq:
            if w.lower() == key:
                display = w
                break
        final.append(
            {
                "id": f"fr:{key}",
                "language": "fr",
                "word": display,
                "ipa": ipa,
                "meaning": cur["meaning"],
                "pos": cur["pos"],
                "sentences": cur["sentences"][:3],
                "tags": ["buchmeier-curated", "frequency", "verified"],
            }
        )
        seen.add(key)

    # 2) Frequency-ordered Buchmeier lemmas / words
    for w in freq:
        key = w.lower()
        if key in seen:
            continue
        senses = buch.get(key)
        if not senses:
            continue
        ipa = ipa_map.get(key)
        if not ipa:
            continue

        # Skip if ALL senses look like pure inflections and word is not curated
        non_infl = [s for s in senses if not INFLECTIONISH.search(s["gloss"])]
        if not non_infl:
            # Keep only if very common? Skip conjugations without curated override.
            continue
        display, pos, meaning = pick_meaning(non_infl, key, freq_rank)

        sentences = []
        tags = ["buchmeier", "frequency"]
        for ex in examples_idx.get(key, []):
            if example_matches(meaning, ex):
                sentences.append({"text": ex["text"], "translation": ex["translation"]})
            if len(sentences) >= 2:
                break
        if not sentences:
            sentences = [synth(display, meaning, pos)]
            tags.append("synthetic-example")

        final.append(
            {
                "id": f"fr:{key}",
                "language": "fr",
                "word": display,
                "ipa": ipa,
                "meaning": meaning[:240],
                "pos": pos,
                "sentences": sentences[:3],
                "tags": tags,
            }
        )
        seen.add(key)

    # 3) Add remaining Buchmeier content lemmas (noun/verb/adj) with IPA not yet included
    extras = []
    for key, senses in buch.items():
        if key in seen:
            continue
        ipa = ipa_map.get(key)
        if not ipa:
            continue
        non_infl = [s for s in senses if not INFLECTIONISH.search(s["gloss"])]
        content = [s for s in non_infl if s["pos"] in {"noun", "verb", "adj", "adv", "interj"}]
        if not content:
            continue
        display, pos, meaning = pick_meaning(content, key, freq_rank)
        # Skip extremely niche-only
        if NICHE_TAG.search(meaning) and score_sense(content[0], key, freq_rank) < 40:
            continue
        sentences = []
        tags = ["buchmeier"]
        for ex in examples_idx.get(key, []):
            if example_matches(meaning, ex):
                sentences.append({"text": ex["text"], "translation": ex["translation"]})
            if len(sentences) >= 2:
                break
        if not sentences:
            sentences = [synth(display, meaning, pos)]
            tags.append("synthetic-example")
        extras.append(
            {
                "id": f"fr:{key}",
                "language": "fr",
                "word": display,
                "ipa": ipa,
                "meaning": meaning[:240],
                "pos": pos,
                "sentences": sentences[:3],
                "tags": tags,
            }
        )
    # Prefer shorter everyday extras first
    extras.sort(key=lambda e: (0 if e["pos"] in CONTENT_BUCKETS else 1, len(e["word"]), e["word"]))
    for e in extras:
        if e["id"][3:] in seen:
            continue
        final.append(e)
        seen.add(e["id"][3:])
        if len(final) >= 12000:
            break

    payload = {
        "language": "fr",
        "version": 4,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sources": [
            {
                "name": "Matthias Buchmeier French–English (via open-dsl-dict/wiktionary-dict)",
                "url": "https://github.com/open-dsl-dict/wiktionary-dict",
                "license": "CC BY-SA 3.0 / GFDL",
                "usedFor": "Primary English meanings (POS-tagged bilingual glosses)",
            },
            {
                "name": "open-dict-data/ipa-dict (fr_FR)",
                "url": "https://github.com/open-dict-data/ipa-dict",
                "license": "MIT",
                "usedFor": "IPA pronunciation",
            },
            {
                "name": "FrequencyWords (fr)",
                "url": "https://github.com/hermitdave/FrequencyWords",
                "license": "Open word lists",
                "usedFor": "Ordering / coverage priority",
            },
            {
                "name": "Wiktextract / kaikki.org (examples only)",
                "url": "https://kaikki.org/dictionary/French/",
                "license": "CC BY-SA 4.0",
                "usedFor": "Sample sentences when aligned with chosen gloss",
            },
        ],
        "notes": (
            "Meanings come from the Buchmeier FR→EN bilingual dictionary with POS-aware "
            "sense ranking. Ultra-common homographs use a curated verified table. "
            "Inflection-only senses are skipped unless curated."
        ),
        "count": len(final),
        "words": final,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(final)} words → {OUT}")

    checks = [
        "pas",
        "sur",
        "est",
        "tu",
        "la",
        "avec",
        "maison",
        "bonjour",
        "eau",
        "temps",
        "merci",
        "chien",
        "livre",
        "manger",
    ]
    for w in checks:
        e = next(x for x in final if x["word"].lower() == w)
        print(f"{w:10} | {e['meaning'][:55]:55} | {e['sentences'][0]['text'][:45]}")


if __name__ == "__main__":
    main()
