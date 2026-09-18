# Sentences

A very small language-learning site: fill-in-the-blank sentences drawn from
out-of-copyright classic literature, with simple spaced repetition.

- A sentence in the target language is shown with one word missing.
- Type the word, press Enter. You see whether you were right, the full sentence,
  its English translation, and (where the browser has a voice) hear it read aloud.
- Press Enter again for the next sentence.
- Cards you get wrong come back within the session and then the next day; cards
  you get right come back at growing intervals (1 day, 3 days, then roughly ×2.5).
- New sentences are drip-fed, 10 a day by default (change it in Settings).

Progress is stored in the browser (localStorage), per language. Settings has
export/import so you can move it between devices.

## Running it

It's a static site, but it loads its data with `fetch`, so it needs to be served
over HTTP rather than opened as a file:

```
cd simple_language_learning
python3 -m http.server 8000
```

Then open http://localhost:8000.

## Deployment

The site is hosted on Railway at https://web-production-bef70.up.railway.app.
`Dockerfile` serves the static files with Caddy; Railway builds it on each push
to `main` once the GitHub repo is connected to the `web` service. To deploy the
working directory directly instead: `railway up --service web`.

Progress lives in each visitor's browser (localStorage), so there are no
accounts and nothing is stored on the server.

## Layout

```
index.html, style.css, app.js     the whole app
data/languages.json               list of languages the app offers
data/de/cards.json                the German deck (420 cards, easiest first)
data/pt/cards.json                the Portuguese deck (247 cards)
data/<lang>/candidates.jsonl      the larger pool each deck was picked from
tools/extract_sentences.py        Gutenberg text -> candidate sentences
tools/pt_modernise.py             19th-century Portuguese spelling -> modern
tools/lexicon/pt.txt              modern Portuguese word frequencies (OpenSubtitles)
tools/translate_cards.py          optional: draft translations with Claude
tools/<lang>_curation.tsv         the hand-checked selection + translations
tools/build_deck.py               curation TSV -> cards.json
```

Card format (`data/<lang>/cards.json`):

```json
{"id": "de-22367-00012",
 "cloze": "Aber nun muss ich ___.",
 "answer": "aufstehen",
 "text": "Aber nun muss ich aufstehen.",
 "translation": "But now I must get up.",
 "source": {"author": "Franz Kafka", "title": "Die Verwandlung", "year": 1915}}
```

## German sources

All from Project Gutenberg, authors dead more than 70 years:
Kafka (*Die Verwandlung*, *Der Prozess*), Storm (*Immensee*, *Der Schimmelreiter*),
Fontane (*Effi Briest*), Goethe (*Werther*), Thomas Mann (*Tonio Kröger*),
Hauptmann (*Bahnwärter Thiel*), Keller (*Die Leute von Seldwyla*),
Eichendorff (*Taugenichts*), and the Grimms' *Kinder- und Hausmärchen*.

The extraction step modernises the commonest pre-1996 spellings (daß → dass,
wußte → wusste, and so on) and skips sentences with clearly archaic forms. The
answer check also treats ß and ss as equivalent.

## Portuguese sources

Also from Project Gutenberg: Machado de Assis (*Dom Casmurro*, *Memórias
Póstumas de Brás Cubas*, *Quincas Borba*, *Histórias sem Data*), Eça de Queirós
(*Os Maias*, *O Crime do Padre Amaro*, *A Cidade e as Serras*, *O Mandarim*),
Aluísio Azevedo (*O Cortiço*), Camilo Castelo Branco (*Amor de Perdição*) and
Almeida Garrett (*Viagens na Minha Terra*). It is a mix of Brazilian and
Portuguese authors; speech uses a European Portuguese voice (`pt-PT` in
`data/languages.json`; change to `pt-BR` if you prefer).

The Gutenberg editions keep pre-1911 spelling (*annos*, *elle*, *d'aquelle*,
*ridiculo*), so `tools/pt_modernise.py` rewrites every word against a modern
frequency list: safe rules first (double consonants, ph/th/y, contractions,
verb+clitic forms), then spelling and accent variants checked against the
lexicon. Sentences containing any word that does not resolve are dropped.

## Building a deck (or adding a language)

1. Download plain-text books from Gutenberg into a folder as `<id>.txt`
   (`https://www.gutenberg.org/ebooks/<id>.txt.utf-8`; some entries only
   have `/files/<id>/<id>-0.txt`).
2. Add the book ids, authors, titles and character names to `SOURCES` in
   `tools/extract_sentences.py` (and, for a new language, a `MODERNISE` map
   if the orthography has changed since the books were written).
3. `python3 tools/extract_sentences.py --lang fr --raw-dir raw/ --out data/fr/candidates.jsonl`
   Add `--lexicon tools/lexicon/fr.txt` (a `word count` per line list, e.g. from
   github.com/hermitdave/FrequencyWords) to rank difficulty by real-world frequency
   and to modernise old spelling as for Portuguese; the variant rules in
   `pt_modernise.py` are Portuguese-specific and would need a French set.
4. Write `tools/fr_curation.tsv`: one line per chosen candidate,
   `index<TAB>word-to-blank<TAB>English translation`. To get a first draft
   from Claude: `python3 tools/translate_cards.py --lang fr --count 200 --out tools/fr_draft.tsv`
   (needs `pip install anthropic` and an API key), then prune it by hand.
5. `python3 tools/build_deck.py --lang fr`
6. Add the language to `data/languages.json` with its BCP-47 speech code
   (`fr-FR`, `pt-PT` or `pt-BR`).

## Audio

Uses the browser's built-in speech synthesis (`speechSynthesis`), so quality
depends on the installed voices. Safari and Chrome on macOS both ship a German
voice; if none is found, the Listen button is hidden. Recorded audio could be
added later by putting an `audio` URL on each card.
