#!/usr/bin/env python3
"""Replace meta/template example sentences with varied, meaning-aware French."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DICT = ROOT / "data" / "french.json"

# Only the old meta templates — not natural sentences that happen to start similarly.
OLD_TEMPLATE_RE = re.compile(
    r"^(Le mot «|Exemple\s*:|"
    r"Nous allons \S+\.$|"
    r"C['’]est très \S+\.$|"
    r"Elle répond \S+\.$)",
    re.I,
)


def pick(seed: str, options: list):
    h = int(hashlib.md5(seed.encode("utf-8")).hexdigest(), 16)
    return options[h % len(options)]


def clean_gloss(meaning: str) -> str:
    m = meaning.split(";")[0].split(",")[0].strip()
    m = re.sub(r"\([^)]*\)", "", m).strip()
    return re.sub(r"\s+", " ", m)[:60]


def verb_bare(meaning: str) -> str:
    m = clean_gloss(meaning)
    return m[3:].strip() if m.lower().startswith("to ") else m


def starts_vowel(w: str) -> bool:
    return w[:1].lower() in "aeiouàâäéèêëîïôöùûüyœæh"


def likely_fem(word: str, meaning: str) -> bool:
    w = word.lower()
    if "feminine" in meaning.lower() or "(female)" in meaning.lower():
        return True
    return bool(re.search(r"(tion|sion|té|ée|elle|ette|ance|ence|ure|ade|ière|euse)$", w))


def arts(word: str, fem: bool):
    if starts_vowel(word):
        return "l'", "l'", "cet" if not fem else "cette"
    return ("une", "la", "cette") if fem else ("un", "le", "ce")


def join_art(art: str, word: str) -> str:
    return art + word if art.endswith("'") else f"{art} {word}"


def fix_fr(text: str) -> str:
    text = re.sub(r"\bde ([aeiouàâäéèêëîïôöùûüyœæhAEIOUH])", r"d'\1", text)
    text = re.sub(r"\bde le\b", "du", text)
    text = re.sub(r"\bde les\b", "des", text)
    text = re.sub(r"\bà le\b", "au", text)
    text = re.sub(r"\bà les\b", "aux", text)
    text = re.sub(r"\ble ([aeiouàâäéèêëîïôöùûüyœæhAEIOUH])", r"l'\1", text)
    text = re.sub(r"\bla ([aeiouàâäéèêëîïôöùûüyœæhAEIOUH])", r"l'\1", text)
    return text


STARTER_SENTENCES: dict[str, list[dict]] = {
    "bonjour": [{"text": "Bonjour, je m’appelle Marie.", "translation": "Hello, my name is Marie."}],
    "salut": [{"text": "Salut ! Tu viens ce soir ?", "translation": "Hi! Are you coming tonight?"}],
    "merci": [{"text": "Merci beaucoup pour le cadeau.", "translation": "Thank you so much for the gift."}],
    "oui": [{"text": "Oui, j’ai compris la question.", "translation": "Yes, I understood the question."}],
    "non": [{"text": "Non, je ne veux pas de dessert.", "translation": "No, I don’t want dessert."}],
    "pardon": [{"text": "Pardon, je suis en retard.", "translation": "Sorry, I’m late."}],
    "je": [{"text": "Je travaille à Lyon.", "translation": "I work in Lyon."}],
    "tu": [{"text": "Tu aimes le chocolat ?", "translation": "Do you like chocolate?"}],
    "il": [{"text": "Il ouvre la fenêtre.", "translation": "He opens the window."}],
    "elle": [{"text": "Elle prépare le dîner.", "translation": "She is preparing dinner."}],
    "nous": [{"text": "Nous visitons un musée demain.", "translation": "We are visiting a museum tomorrow."}],
    "vous": [{"text": "Vous parlez trop vite pour moi.", "translation": "You speak too fast for me."}],
    "homme": [{"text": "Cet homme porte un chapeau gris.", "translation": "This man is wearing a gray hat."}],
    "femme": [{"text": "La femme lit le journal au café.", "translation": "The woman is reading the newspaper at the café."}],
    "enfant": [{"text": "L’enfant dessine une maison rouge.", "translation": "The child is drawing a red house."}],
    "ami": [{"text": "Mon ami m’attend devant le cinéma.", "translation": "My friend is waiting for me in front of the cinema."}],
    "amie": [{"text": "Mon amie chante dans un groupe.", "translation": "My (female) friend sings in a band."}],
    "père": [{"text": "Mon père répare le vélo dans le garage.", "translation": "My father is fixing the bike in the garage."}],
    "mère": [{"text": "Ma mère prépare une tarte aux pommes.", "translation": "My mother is making an apple pie."}],
    "frère": [{"text": "Mon frère joue au football le dimanche.", "translation": "My brother plays soccer on Sundays."}],
    "sœur": [{"text": "Ma sœur étudie la médecine.", "translation": "My sister is studying medicine."}],
    "famille": [{"text": "Toute la famille dîne ensemble le vendredi.", "translation": "The whole family has dinner together on Fridays."}],
    "maison": [{"text": "Leur maison a un petit jardin.", "translation": "Their house has a small garden."}],
    "école": [{"text": "Les enfants rentrent de l’école à quatre heures.", "translation": "The children come home from school at four."}],
    "travail": [{"text": "Son travail commence à neuf heures.", "translation": "His job starts at nine."}],
    "ville": [{"text": "Cette ville est célèbre pour ses ponts.", "translation": "This city is famous for its bridges."}],
    "rue": [{"text": "Il y a une boulangerie dans ma rue.", "translation": "There is a bakery on my street."}],
    "eau": [{"text": "Peux-tu me passer un verre d’eau ?", "translation": "Can you pass me a glass of water?"}],
    "pain": [{"text": "Nous mangeons du pain chaud le matin.", "translation": "We eat warm bread in the morning."}],
    "fromage": [{"text": "Ce fromage sent un peu fort.", "translation": "This cheese smells a bit strong."}],
    "vin": [{"text": "Ils boivent un peu de vin rouge.", "translation": "They are drinking a little red wine."}],
    "café": [{"text": "Je prends un café après le déjeuner.", "translation": "I have a coffee after lunch."}],
    "thé": [{"text": "Elle préfère le thé au lait.", "translation": "She prefers tea with milk."}],
    "lait": [{"text": "Il reste encore du lait dans le frigo.", "translation": "There is still some milk left in the fridge."}],
    "livre": [{"text": "J’ai emprunté ce livre à la bibliothèque.", "translation": "I borrowed this book from the library."}],
    "voiture": [{"text": "Sa voiture est garée trop loin.", "translation": "His car is parked too far away."}],
    "train": [{"text": "Le train pour Marseille part dans dix minutes.", "translation": "The train to Marseille leaves in ten minutes."}],
    "chien": [{"text": "Leur chien court dans le parc.", "translation": "Their dog is running in the park."}],
    "chat": [{"text": "Le chat se cache sous le canapé.", "translation": "The cat is hiding under the sofa."}],
    "table": [{"text": "Pose les assiettes sur la table, s’il te plaît.", "translation": "Please put the plates on the table."}],
    "porte": [{"text": "N’oublie pas de fermer la porte.", "translation": "Don’t forget to close the door."}],
    "fenêtre": [{"text": "Ouvre la fenêtre, il fait trop chaud.", "translation": "Open the window, it’s too hot."}],
    "jour": [{"text": "Quel jour sommes-nous aujourd’hui ?", "translation": "What day is it today?"}],
    "nuit": [{"text": "La nuit, la ville devient plus calme.", "translation": "At night, the city becomes quieter."}],
    "matin": [{"text": "Le matin, je cours avant le petit-déjeuner.", "translation": "In the morning, I run before breakfast."}],
    "soir": [{"text": "Ce soir, on regarde un film.", "translation": "Tonight we’re watching a movie."}],
    "aujourd'hui": [{"text": "Aujourd’hui, le ciel est très bleu.", "translation": "Today the sky is very blue."}],
    "demain": [{"text": "Demain, j’ai un examen important.", "translation": "Tomorrow I have an important exam."}],
    "hier": [{"text": "Hier, nous avons visité le château.", "translation": "Yesterday we visited the castle."}],
    "temps": [{"text": "Je n’ai pas le temps de t’appeler maintenant.", "translation": "I don’t have time to call you right now."}],
    "être": [{"text": "Il veut être médecin plus tard.", "translation": "He wants to be a doctor later."}],
    "avoir": [{"text": "Nous avons assez de chaises pour tout le monde.", "translation": "We have enough chairs for everyone."}],
    "aller": [{"text": "Vous allez au marché avec moi ?", "translation": "Are you going to the market with me?"}],
    "faire": [{"text": "Que fait-elle dans la cuisine ?", "translation": "What is she doing in the kitchen?"}],
    "parler": [{"text": "Ils parlent trop fort dans le bus.", "translation": "They are talking too loudly on the bus."}],
    "manger": [{"text": "On mange des pâtes ce midi.", "translation": "We’re eating pasta for lunch."}],
    "boire": [{"text": "Les sportifs boivent beaucoup d’eau.", "translation": "Athletes drink a lot of water."}],
    "voir": [{"text": "Tu vois cet oiseau sur le toit ?", "translation": "Do you see that bird on the roof?"}],
    "aimer": [{"text": "Les enfants aiment les histoires drôles.", "translation": "Children love funny stories."}],
    "vouloir": [{"text": "Je veux essayer ce plat.", "translation": "I want to try this dish."}],
    "pouvoir": [{"text": "Tu peux m’aider à porter ça ?", "translation": "Can you help me carry this?"}],
    "savoir": [{"text": "Elle sait jouer du piano.", "translation": "She knows how to play the piano."}],
    "venir": [{"text": "Mes cousins viennent ce week-end.", "translation": "My cousins are coming this weekend."}],
    "prendre": [{"text": "Je prends le métro tous les jours.", "translation": "I take the metro every day."}],
    "donner": [{"text": "Il donne des conseils utiles.", "translation": "He gives useful advice."}],
    "lire": [{"text": "Le soir, elle lit avant de dormir.", "translation": "In the evening, she reads before sleeping."}],
    "écrire": [{"text": "Écris ton nom en haut de la page.", "translation": "Write your name at the top of the page."}],
    "acheter": [{"text": "Nous achetons des fruits au marché.", "translation": "We buy fruit at the market."}],
    "travailler": [{"text": "Il travaille dans une petite entreprise.", "translation": "He works in a small company."}],
    "comprendre": [{"text": "Maintenant je comprends mieux la règle.", "translation": "Now I understand the rule better."}],
    "bon": [{"text": "Ce restaurant est vraiment bon.", "translation": "This restaurant is really good."}],
    "petit": [{"text": "Il y a un petit café au coin de la rue.", "translation": "There is a little café on the street corner."}],
    "grand": [{"text": "Leur fils est déjà très grand.", "translation": "Their son is already very tall."}],
    "beau": [{"text": "Quel beau paysage après la pluie !", "translation": "What a beautiful landscape after the rain!"}],
    "nouveau": [{"text": "J’ai un nouveau téléphone depuis hier.", "translation": "I’ve had a new phone since yesterday."}],
    "jeune": [{"text": "Cette jeune artiste expose à Paris.", "translation": "This young artist is exhibiting in Paris."}],
    "vieux": [{"text": "Ce vieux pont traverse encore la rivière.", "translation": "This old bridge still crosses the river."}],
    "chaud": [{"text": "Le thé est encore trop chaud.", "translation": "The tea is still too hot."}],
    "froid": [{"text": "Il fait froid dehors ce matin.", "translation": "It’s cold outside this morning."}],
    "facile": [{"text": "Cet exercice est plus facile que l’autre.", "translation": "This exercise is easier than the other one."}],
    "difficile": [{"text": "La question était difficile, mais juste.", "translation": "The question was difficult, but fair."}],
    "heureux": [{"text": "Ils ont l’air heureux ensemble.", "translation": "They look happy together."}],
    "triste": [{"text": "Pourquoi as-tu l’air si triste ?", "translation": "Why do you look so sad?"}],
    "rouge": [{"text": "Elle porte une écharpe rouge.", "translation": "She is wearing a red scarf."}],
    "bleu": [{"text": "Le ciel est bleu après l’orage.", "translation": "The sky is blue after the storm."}],
    "vert": [{"text": "Les feuilles deviennent vertes au printemps.", "translation": "The leaves turn green in spring."}],
    "blanc": [{"text": "Le chat blanc dort au soleil.", "translation": "The white cat is sleeping in the sun."}],
    "noir": [{"text": "Il a choisi un manteau noir.", "translation": "He chose a black coat."}],
    "pas": [{"text": "Je ne connais pas encore cette chanson.", "translation": "I don’t know this song yet."}],
    "avec": [{"text": "Viens avec nous au concert.", "translation": "Come with us to the concert."}],
    "dans": [{"text": "Les clés sont dans mon sac.", "translation": "The keys are in my bag."}],
    "pour": [{"text": "Ce gâteau est pour ton anniversaire.", "translation": "This cake is for your birthday."}],
    "sur": [{"text": "Le chat dort sur mon lit.", "translation": "The cat is sleeping on my bed."}],
}


def gen_verb(word: str, meaning: str) -> dict:
    bare = verb_bare(meaning)
    frames = [
        (f"Hier soir, on a essayé de {word} autrement.", f"Last night we tried to {bare} differently."),
        (f"Tu arrives à {word} sans te presser ?", f"Can you manage to {bare} without rushing?"),
        (f"Elle refuse de {word} quand elle est fatiguée.", f"She refuses to {bare} when she’s tired."),
        (f"Pour progresser, il faut {word} un peu chaque jour.", f"To improve, you need to {bare} a little every day."),
        (f"Ils préfèrent {word} tôt le matin.", f"They prefer to {bare} early in the morning."),
        (f"Je commence seulement à {word} correctement.", f"I’m only just starting to {bare} properly."),
        (f"On ne peut pas {word} indéfiniment.", f"You can’t {bare} indefinitely."),
        (f"Avant le départ, pense à {word}.", f"Before leaving, remember to {bare}."),
        (f"Les élèves apprennent à {word} en classe.", f"The students learn to {bare} in class."),
        (f"Si tu veux, on peut {word} après le café.", f"If you want, we can {bare} after coffee."),
        (f"Personne ne m’a dit comment {word} ici.", f"Nobody told me how to {bare} here."),
        (f"Il a mis longtemps à {word} seul.", f"It took him a long time to {bare} on his own."),
        (f"Demain on pourra enfin {word} tranquillement.", f"Tomorrow we’ll finally be able to {bare} in peace."),
        (f"Pourquoi faut-il {word} aussi vite ?", f"Why do we have to {bare} so quickly?"),
        (f"Elle m’a demandé de {word} avec elle.", f"She asked me to {bare} with her."),
        (f"Dans ce métier, on doit {word} souvent.", f"In this job, you often have to {bare}."),
        (f"J’hésite encore avant de {word}.", f"I’m still hesitating before I {bare}."),
        (f"Sous la pluie, difficile de {word} correctement.", f"In the rain, it’s hard to {bare} properly."),
    ]
    fr, en = pick(word, frames)
    return {"text": fix_fr(fr), "translation": en}


def gen_adj(word: str, meaning: str) -> dict:
    g = clean_gloss(meaning)
    frames = [
        (f"Ce quartier est plus {word} le soir.", f"This neighborhood is more {g} in the evening."),
        (f"Elle reste {word} face au problème.", f"She stays {g} in the face of the problem."),
        (f"Leur idée paraît vraiment {word}.", f"Their idea seems really {g}."),
        (f"D’où vient ce ton si {word} ?", f"Where is this {g} tone coming from?"),
        (f"Après la marche, on se sent {word}.", f"After the walk, you feel {g}."),
        (f"Ce n’est pas aussi {word} que prévu.", f"It isn’t as {g} as expected."),
        (f"Les voyageurs trouvent l’auberge {word}.", f"Travelers find the inn {g}."),
        (f"Il veut paraître {word} devant ses collègues.", f"He wants to seem {g} in front of his colleagues."),
        (f"Même sous la pluie, le paysage reste {word}.", f"Even in the rain, the landscape stays {g}."),
        (f"Cette réponse courte est déjà {word}.", f"This short answer is already {g}."),
        (f"Le résultat final semble {word} à tous.", f"The final result seems {g} to everyone."),
        (f"Tu trouves ce choix {word}, toi ?", f"Do you find this choice {g}?"),
        (f"Au début, rien ne paraissait {word}.", f"At first, nothing seemed {g}."),
        (f"Le café du coin est étonnamment {word}.", f"The corner café is surprisingly {g}."),
    ]
    fr, en = pick(word, frames)
    return {"text": fix_fr(fr), "translation": en}


def gen_adv(word: str, meaning: str) -> dict:
    g = clean_gloss(meaning)
    frames = [
        (f"Elle travaille {word} quand le délai approche.", f"She works {g} when the deadline approaches."),
        (f"Il parle {word}, alors on tend l’oreille.", f"He speaks {g}, so we listen closely."),
        (f"Nous avons réglé ça {word} ce matin.", f"We sorted that out {g} this morning."),
        (f"Tu arrives {word} à chaque rendez-vous.", f"You arrive {g} to every appointment."),
        (f"Le moteur redémarre {word} après la pause.", f"The engine restarts {g} after the break."),
        (f"Ils avancent {word} malgré le vent.", f"They move forward {g} despite the wind."),
        (f"Réponds {word}, on n’entend rien.", f"Answer {g}; we can’t hear anything."),
        (f"Le rideau tombe {word} à la fin.", f"The curtain falls {g} at the end."),
        (f"Elle a réagi {word} à la nouvelle.", f"She reacted {g} to the news."),
        (f"Le bus repart {word} après l’arrêt.", f"The bus leaves again {g} after the stop."),
    ]
    fr, en = pick(word, frames)
    return {"text": fix_fr(fr), "translation": en}


def gen_noun(word: str, meaning: str) -> dict:
    g = clean_gloss(meaning)
    fem = likely_fem(word, meaning)
    indef, defart, det = arts(word, fem)
    eng = "an" if g[:1].lower() in "aeiou" else "a"
    frames = [
        (f"J’ai remarqué {join_art(indef, word)} près du quai.", f"I noticed {eng} {g} near the platform."),
        (f"{det.capitalize()} {word} change complètement le plan.", f"This {g} completely changes the plan."),
        (f"Sans {join_art(defart, word)}, tout devient plus long.", f"Without the {g}, everything takes longer."),
        (f"Raconte-moi ton {word} de la semaine.", f"Tell me about your {g} from this week."),
        (f"Ils cherchent encore {join_art(indef, word)} fiable.", f"They’re still looking for a reliable {g}."),
        (f"Le guide montre {join_art(defart, word)} aux visiteurs.", f"The guide shows the {g} to the visitors."),
        (f"Au détour du chemin apparaît {join_art(indef, word)}.", f"Around the bend, {eng} {g} appears."),
        (f"On range {join_art(defart, word)} dans le tiroir du bas.", f"We put the {g} away in the bottom drawer."),
        (f"Pour elle, {join_art(defart, word)} reste prioritaire.", f"For her, the {g} remains a priority."),
        (f"Elle a croqué {join_art(indef, word)} dans son carnet.", f"She sketched {eng} {g} in her notebook."),
        (f"Personne n’attendait {join_art(indef, word)} semblable.", f"Nobody expected such {eng} {g}."),
        (f"Derrière la vitrine, on aperçoit {join_art(indef, word)}.", f"Behind the shop window, you can see {eng} {g}."),
        (f"Le bruit vient de {join_art(defart, word)} d’à côté.", f"The noise is coming from the {g} next door."),
        (f"Acheter {join_art(indef, word)} ici coûte plus cher.", f"Buying {eng} {g} here costs more."),
        (f"Sur la photo, on reconnaît clairement {join_art(defart, word)}.", f"In the photo, you can clearly make out the {g}."),
    ]
    fr, en = pick(word + ("-f" if fem else "-m"), frames)
    return {"text": fix_fr(fr), "translation": en}


def gen_prep(word: str, meaning: str) -> dict:
    special = {
        "avec": ("Je voyage avec ma sœur cet été.", "I’m traveling with my sister this summer."),
        "sans": ("Il boit son café sans sucre.", "He drinks his coffee without sugar."),
        "dans": ("Les tickets sont dans mon portefeuille.", "The tickets are in my wallet."),
        "sur": ("Pose le vase sur l’étagère.", "Put the vase on the shelf."),
        "sous": ("Le chat dort sous la chaise.", "The cat is sleeping under the chair."),
        "pour": ("Ce message est pour le professeur.", "This message is for the teacher."),
        "chez": ("On dîne chez mes parents ce soir.", "We’re having dinner at my parents’ tonight."),
        "entre": ("Assieds-toi entre Paul et Léa.", "Sit between Paul and Léa."),
        "après": ("Après le cours, on prend un thé.", "After class, we have a tea."),
        "avant": ("Lave-toi les mains avant de manger.", "Wash your hands before eating."),
        "pendant": ("Pendant le film, tout le monde riait.", "During the movie, everyone was laughing."),
        "depuis": ("Je vis ici depuis trois ans.", "I’ve lived here for three years."),
        "contre": ("Elle est contre cette décision.", "She is against this decision."),
        "vers": ("Ils marchent vers la colline.", "They are walking toward the hill."),
        "par": ("On entre par la petite porte.", "You enter through the small door."),
        "de": ("Je reviens de la bibliothèque.", "I’m coming back from the library."),
        "à": ("On se retrouve à la gare.", "We’ll meet at the station."),
    }
    if word.lower() in special:
        fr, en = special[word.lower()]
        return {"text": fr, "translation": en}
    g = clean_gloss(meaning)
    frames = [
        (f"Le cadeau est {word} toi.", f"The gift is {g} you."),
        (f"On marche {word} la rivière en silence.", f"We walk {g} the river in silence."),
        (f"Range ça {word} les livres, s’il te plaît.", f"Please put that {g} the books."),
        (f"Il part {word} ses amis ce week-end.", f"He’s leaving {g} his friends this weekend."),
    ]
    fr, en = pick(word, frames)
    return {"text": fix_fr(fr), "translation": en}


def gen_other(word: str, meaning: str, pos: str) -> dict:
    special = {
        "je": ("Je prépare le petit-déjeuner.", "I’m making breakfast."),
        "tu": ("Tu fermes la lumière ?", "Are you turning off the light?"),
        "il": ("Il range sa chambre.", "He is tidying his room."),
        "elle": ("Elle appelle sa grand-mère.", "She is calling her grandmother."),
        "nous": ("Nous partageons le taxi.", "We’re sharing the taxi."),
        "vous": ("Vous connaissez ce quartier ?", "Do you know this neighborhood?"),
        "ils": ("Ils jouent dans la cour.", "They are playing in the courtyard."),
        "elles": ("Elles choisissent une chanson.", "They are choosing a song."),
        "on": ("On essaie une nouvelle recette.", "We’re trying a new recipe."),
        "ça": ("Ça sent bon dans la cuisine.", "It smells good in the kitchen."),
        "oui": ("Oui, j’arrive dans cinq minutes.", "Yes, I’ll be there in five minutes."),
        "non": ("Non, ce n’est pas la bonne adresse.", "No, that’s not the right address."),
        "et": ("Du pain et du beurre, s’il te plaît.", "Bread and butter, please."),
        "ou": ("Thé ou chocolat chaud ?", "Tea or hot chocolate?"),
        "mais": ("C’est petit, mais très pratique.", "It’s small, but very practical."),
        "si": ("Si tu as faim, prends une pomme.", "If you’re hungry, take an apple."),
        "que": ("Je crois que le bus arrive.", "I think that the bus is coming."),
        "qui": ("Qui a laissé la porte ouverte ?", "Who left the door open?"),
        "quoi": ("Quoi de prévu ce week-end ?", "What’s planned for this weekend?"),
        "où": ("Où as-tu mis mes lunettes ?", "Where did you put my glasses?"),
        "quand": ("Quand commence le spectacle ?", "When does the show start?"),
        "comment": ("Comment on écrit ce mot ?", "How do you write this word?"),
        "pourquoi": ("Pourquoi le magasin est fermé ?", "Why is the shop closed?"),
        "très": ("Cette soupe est très épicée.", "This soup is very spicy."),
        "bien": ("Tu chantes vraiment bien.", "You sing really well."),
        "aussi": ("Moi aussi, j’aime voyager.", "I like traveling too."),
        "encore": ("Encore un peu de pain ?", "A bit more bread?"),
        "déjà": ("Tu as déjà fini ton devoir ?", "Have you already finished your homework?"),
        "toujours": ("Il est toujours ponctuel.", "He is always on time."),
        "souvent": ("On se voit souvent le samedi.", "We often see each other on Saturdays."),
        "maintenant": ("Maintenant, on peut commencer.", "Now we can start."),
        "ici": ("Assieds-toi ici, près de moi.", "Sit here, next to me."),
        "là": ("Le restaurant est juste là.", "The restaurant is right there."),
        "pas": ("Je ne mange pas de viande.", "I don’t eat meat."),
        "ne": ("Je ne vois rien dans le noir.", "I can’t see anything in the dark."),
        "le": ("Le soleil se couche tard.", "The sun sets late."),
        "la": ("La pluie commence enfin.", "The rain is finally starting."),
        "les": ("Les magasins ferment à vingt heures.", "The shops close at eight."),
        "un": ("Un oiseau chante dehors.", "A bird is singing outside."),
        "une": ("Une idée me vient tout à coup.", "An idea comes to me all of a sudden."),
        "des": ("Des enfants jouent près de l’école.", "Some children are playing near the school."),
        "ce": ("Ce gâteau est encore chaud.", "This cake is still warm."),
        "cette": ("Cette chanson me rappelle l’été.", "This song reminds me of summer."),
        "ces": ("Ces fleurs viennent du jardin.", "These flowers come from the garden."),
        "mon": ("Mon parapluie est cassé.", "My umbrella is broken."),
        "ma": ("Ma valise est trop lourde.", "My suitcase is too heavy."),
        "ton": ("Ton message m’a fait rire.", "Your message made me laugh."),
        "ta": ("Ta veste est sur la chaise.", "Your jacket is on the chair."),
        "son": ("Son chien aboie la nuit.", "His/her dog barks at night."),
        "sa": ("Sa réponse était claire.", "His/her answer was clear."),
    }
    if word.lower() in special:
        fr, en = special[word.lower()]
        return {"text": fr, "translation": en}
    g = clean_gloss(meaning)
    if pos == "interj":
        frames = [
            (f"{word.capitalize()} ! Tu m’as fait peur.", f"{g.capitalize()}! You scared me."),
            (f"{word.capitalize()}, j’avais complètement oublié.", f"{g.capitalize()}, I had completely forgotten."),
            (f"Il a juste dit « {word} » et il est parti.", f"He just said “{g}” and left."),
        ]
    else:
        frames = [
            (f"Dans cette phrase, {word} joue un rôle clé.", f"In this sentence, “{g}” plays a key role."),
            (f"Essaie d’employer {word} dans un contexte réel.", f"Try using “{g}” in a real context."),
            (f"Les apprenants confondent souvent {word} avec un autre mot.", f"Learners often confuse “{g}” with another word."),
        ]
    fr, en = pick(word, frames)
    return {"text": fix_fr(fr), "translation": en}


def generate(entry: dict) -> list[dict]:
    key = entry["word"].lower()
    if key in STARTER_SENTENCES:
        return STARTER_SENTENCES[key]
    word = entry["word"]
    meaning = entry.get("meaning") or ""
    pos = (entry.get("pos") or "").lower()
    if pos == "verb":
        s = gen_verb(word, meaning)
    elif pos == "adj":
        s = gen_adj(word, meaning)
    elif pos == "adv":
        s = gen_adv(word, meaning)
    elif pos == "noun":
        s = gen_noun(word, meaning)
    elif pos == "prep":
        s = gen_prep(word, meaning)
    else:
        s = gen_other(word, meaning, pos)
    out = [s]
    if entry.get("level") in {"starter", "A1", "A2"} and pos in {"noun", "verb", "adj"}:
        if pos == "verb":
            bare = verb_bare(meaning)
            frames = [
                (f"Demain j’aimerais {word} avant midi.", f"Tomorrow I’d like to {bare} before noon."),
                (f"Sous la pluie, personne ne veut {word}.", f"In the rain, nobody wants to {bare}."),
                (f"Apprends à {word} sans te précipiter.", f"Learn to {bare} without rushing."),
            ]
        elif pos == "adj":
            g = clean_gloss(meaning)
            frames = [
                (f"Même fatigué, il reste {word}.", f"Even when tired, he stays {g}."),
                (f"Au début, l’idée paraît {word}.", f"At first, the idea seems {g}."),
            ]
        else:
            g = clean_gloss(meaning)
            fem = likely_fem(word, meaning)
            indef, _, _ = arts(word, fem)
            eng = "an" if g[:1].lower() in "aeiou" else "a"
            frames = [
                (f"Tu as déjà vu {join_art(indef, word)} comme ça ?", f"Have you ever seen {eng} {g} like this?"),
                (f"Au marché, j’ai trouvé {join_art(indef, word)} parfait.", f"At the market I found a perfect {g}."),
            ]
        fr, en = pick(word + "|alt", frames)
        alt = {"text": fix_fr(fr), "translation": en}
        if alt["text"] != s["text"]:
            out.append(alt)
    return out[:2]


def needs_regen(entry: dict) -> bool:
    if entry["word"].lower() in STARTER_SENTENCES:
        return True
    tags = entry.get("tags") or []
    if "synthetic-example" in tags or "crafted-example" in tags:
        return True
    text = entry["sentences"][0]["text"]
    if OLD_TEMPLATE_RE.search(text):
        return True
    if text.strip().lower() == entry["word"].lower() or len(text) < 8:
        return True
    return False


def main() -> None:
    payload = json.loads(DICT.read_text(encoding="utf-8"))
    changed = 0
    for e in payload["words"]:
        if not needs_regen(e):
            continue
        e["sentences"] = generate(e)
        tags = [t for t in (e.get("tags") or []) if t != "synthetic-example"]
        tags.append("crafted-example")
        e["tags"] = sorted(set(tags))
        changed += 1
    payload["version"] = 8
    DICT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    left = sum(1 for e in payload["words"] if OLD_TEMPLATE_RE.search(e["sentences"][0]["text"]))
    print(f"updated {changed}; old templates left {left}")
    for w in ["bonjour", "maison", "manger", "triste", "découvrir", "option", "abribus", "glas"]:
        e = next(x for x in payload["words"] if x["word"].lower() == w)
        print(f"{e['word']}: {e['sentences'][0]['text']} || {e['sentences'][0]['translation']}")


if __name__ == "__main__":
    main()
