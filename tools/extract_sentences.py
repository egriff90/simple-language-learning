#!/usr/bin/env python3
"""Extract learner-friendly sentences from Project Gutenberg texts.

Usage:
    python3 tools/extract_sentences.py --lang de --raw-dir raw/ --out candidates.jsonl
    python3 tools/extract_sentences.py --lang pt --raw-dir raw_pt/ --out candidates.jsonl --lexicon tools/lexicon/pt.txt

Reads plain-text Gutenberg files named <id>.txt, strips the license boilerplate,
splits into sentences, filters for simple/self-contained ones, picks a word to
blank out, and writes JSON lines with `translation: null` for a later pass
(see translate_cards.py, or fill by hand).

Adding a language: add an entry to SOURCES and (optionally) a MODERNISE map.
"""
import argparse
import collections
import json
import math
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Gutenberg id -> (author, title, year, list of character names to never blank)
SOURCES = {
    "de": {
        "22367": ("Franz Kafka", "Die Verwandlung", 1915,
                  "Gregor Samsa Grete Prokurist"),
        "69327": ("Franz Kafka", "Der Prozess", 1925,
                  "Josef Bürstner Grubach Huld Leni Block Titorelli Kaminer Kullich Rabensteiner Elsa Franz Willem"),
        "74008": ("Theodor Storm", "Der Schimmelreiter", 1888,
                  "Hauke Haien Elke Volkerts Tede Ole Peters Wienke Ann Grete Trin Jans Carsten Iven Manners Jewe"),
        "6651": ("Theodor Storm", "Immensee", 1849,
                 "Reinhard Elisabeth Erich Werner"),
        "5323": ("Theodor Fontane", "Effi Briest", 1895,
                 "Effi Briest Innstetten Geert Luise Hulda Bertha Hertha Roswitha Johanna Crampas Gieshübler Kessin Hohen-Cremmen Cremmen Annie Wüllersdorf Niemeyer Dagobert Sidonie Grasenabb Rummschüttel Trippelli Friedrich Kruse Rollo"),
        "2407": ("Johann Wolfgang von Goethe", "Die Leiden des jungen Werther", 1774,
                 "Werther Lotte Lotten Albert Wilhelm Wahlheim"),
        "2408": ("Johann Wolfgang von Goethe", "Die Leiden des jungen Werther", 1774,
                 "Werther Lotte Lotten Albert Wilhelm Wahlheim Ossian"),
        "23313": ("Thomas Mann", "Tonio Kröger", 1903,
                  "Tonio Kröger Hans Hansen Ingeborg Inge Holm Lisaweta Iwanowna Knaak Magdalena Vermehren Erwin Jimmerthal Aalsgaard"),
        "29376": ("Gerhart Hauptmann", "Bahnwärter Thiel", 1888,
                  "Thiel Lene Minna Tobias Tobiaschen Schön-Schornstein Neu-Zittau"),
        "28042": ("Gottfried Keller", "Die Leute von Seldwyla", 1874,
                  "Strapinski Wenzel Nettchen Seldwyla Goldach Melchior Böhni Pankraz Dietegen Küngolt Jukundus Justine Züs Bünzlin Jobst Fridolin Dietrich Regine Viggi Störteler Gritli Wilhelm"),
        "35312": ("Joseph von Eichendorff", "Aus dem Leben eines Taugenichts", 1826,
                  "Leonhard Guido Flora Aurelie Rosette"),
        "77905": ("Brüder Grimm", "Kinder- und Hausmärchen", 1812,
                  "Hänsel Gretel Rapunzel Rumpelstilzchen Aschenputtel Dornröschen Schneewittchen Rotkäppchen Hans Grethel Kürdchen Hänschen Frieder Katherlieschen Elsie Elsa Dummling Jorinde Joringel Allerleirauh Fundevogel Lenchen Sneewittchen"),
    },
    "pt": {
        "55752": ("Machado de Assis", "Dom Casmurro", 1899,
                  "Bentinho Bento Capitu Capitú Capitolina Escobar Sancha Sanchinha José Dias Pádua Padua Glória Gloria Justina Cosme Ezequiel Santiago Manduca Cabral Gurgel Matacavalos"),
        "54829": ("Machado de Assis", "Memórias Póstumas de Brás Cubas", 1881,
                  "Brás Braz Cubas Virgília Virgilia Marcela Quincas Borba Lobo Neves Eugênia Eugenia Sabina Cotrim Damasceno Vilaça Villaça Prudêncio Prudencio Dutra Tijuca Loló Nhã"),
        "55682": ("Machado de Assis", "Quincas Borba", 1891,
                  "Rubião Sofia Sophia Palha Cristiano Christiano Carlos Maria Camacho Freitas Teófilo Theophilo Benedita Quincas Borba Barbacena Tonica Siqueira Fernanda"),
        "40409": ("Eça de Queirós", "Os Maias", 1888,
                  "Carlos Afonso Affonso Maia Ega Eduarda Cruges Alencar Craft Dâmaso Damaso Gouvarinho Eusebiozinho Vilaça Villaça Castro Gomes Ramalhete Steinbroken Taveira Pedro Monforte Sequeira Cohen Raquel Rachel Vilaça Teles Telles"),
        "18220": ("Eça de Queirós", "A Cidade e as Serras", 1901,
                  "Jacinto Jacintho Zé Fernandes Tormes Grilo Melchior Joaninha Silvério Silverio Sanches Dorotéia Dorothea Guimarães"),
        "31971": ("Eça de Queirós", "O Crime do Padre Amaro", 1875,
                  "Amaro Amélia Amelia Joaneira Natário Natario Dias Libaninho Cónego Conego Eduardo Leiria Silvério Silverio Totó Gertrudes Ferrão Brito Gonçalves Ruça Dionísia Dionisia Agostinho Saavedra Godinho Nunes"),
        "16425": ("Camilo Castelo Branco", "Amor de Perdição", 1862,
                  "Simão Botelho Teresa Tereza Thereza Albuquerque Mariana Marianna Baltasar Balthazar Coutinho Domingos Rita João Cruz Viseu Vizeu Monchique"),
        "69187": ("Aluísio Azevedo", "O Cortiço", 1890,
                  "João Romão Bertoleza Miranda Estela Estella Zulmira Jerônimo Jeronymo Piedade Rita Baiana Bahiana Firmo Pombinha Botelho Léonie Augusta Alexandre Bruno Leocádia Leocadia Henrique Albino Nenen Machona Isaura Dona Paula Libório Liborio"),
        "24401": ("Almeida Garrett", "Viagens na Minha Terra", 1846,
                  "Carlos Joaninha Dinis Diniz Santarém Santarem Georgina Azambuja Cartaxo Francisca"),
        "33056": ("Machado de Assis", "Histórias sem Data", 1884,
                  "Romão Xavier Inácio Ignacio Maria Benedita Clara Camilo Camillo Diogo Adelaide Cesária Cesaria Venancinha Fortunato Garcia Luís Luiz Alves Vieira"),
        "16384": ("Eça de Queirós", "O Mandarim", 1880,
                  "Teodoro Theodoro Chin-Fu Camilloff Pequim Tien-Hó Macau Sá-Tó"),
    }
}

# Pre-1996 -> modern spelling for the most common ß words (short vowel -> ss).
MODERNISE = {
    "de": {
        "daß": "dass", "muß": "muss", "mußt": "musst", "mußte": "musste", "mußten": "mussten",
        "müßte": "müsste", "müßten": "müssten", "wußte": "wusste", "wußten": "wussten",
        "wüßte": "wüsste", "weiß": "weiß", "läßt": "lässt", "läß": "lass", "laß": "lass",
        "ißt": "isst", "iß": "iss", "paßt": "passt", "paßte": "passte", "faßte": "fasste",
        "faßt": "fasst", "gefaßt": "gefasst", "bißchen": "bisschen", "gewiß": "gewiss",
        "naß": "nass", "Haß": "Hass", "Kuß": "Kuss", "Schloß": "Schloss", "Fluß": "Fluss",
        "Nuß": "Nuss", "Schluß": "Schluss", "Prozeß": "Prozess", "Anlaß": "Anlass",
        "Genuß": "Genuss", "Riß": "Riss", "Biß": "Biss", "mißt": "misst", "vergißt": "vergisst",
        "vergaß": "vergaß", "häßlich": "hässlich", "Fäßchen": "Fässchen", "Schlüßel": "Schlüssel",
        "verläßt": "verlässt", "entschloß": "entschloss", "beschloß": "beschloss",
        "schloß": "schloss", "floß": "floss", "goß": "goss", "genoß": "genoss", "verdroß": "verdross",
        "Roß": "Ross", "Faß": "Fass", "Meßner": "Messner", "Kongreß": "Kongress",
        "läßt's": "lässt's", "mußt's": "musst's", "wußt'": "wusst'",
    }
}


# Things that mark a sentence as fragmentary, archaic or too odd for a flashcard.
BAD_SUBSTRINGS = ["--", "—", "…", "...", "(", ")", "[", "]", ":", ";", "*", "_", "/", "&", "ſ"]
ARCHAIC = re.compile(r"\b(Thür|Thor|thun|thut|that|giebt|seyn|sey|ward|itzt|jetzo|allhier|Muhme|Ohm|Oheim|Thal|Theil|thät|thu|Sonnabend)\b", re.I)


def strip_gutenberg(text: str) -> str:
    start = re.search(r"\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*", text, re.I)
    end = re.search(r"\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG EBOOK", text, re.I)
    if start:
        text = text[start.end():]
    if end:
        text = text[: end.start() - (start.end() if start else 0)] if start else text[: end.start()]
    return text


def paragraphs(text: str):
    text = text.replace("\r", "").replace("﻿", "")
    for para in re.split(r"\n\s*\n", text):
        para = " ".join(line.strip() for line in para.splitlines()).strip()
        para = re.sub(r"^(--|—|–)\s*", "", para)
        if para:
            yield para


ABBREV = re.compile(r"\b(Dr|Hr|Frl|Fr|St|usw|bzw|z\. ?B|Nr|Mr|Mrs|u\. ?a|Kap|d\. ?h|ca|vgl|Prof)\.$", re.I)


def split_sentences(para: str):
    # Split after . ! ? possibly followed by a closing quote, when followed by space + capital/quote.
    pieces = re.split(r"(?<=[.!?][\"“”»«’'])\s+|(?<=[.!?])\s+(?=[\"“„»«A-ZÄÖÜ])", para)
    buf = ""
    for p in pieces:
        buf = (buf + " " + p).strip() if buf else p
        if ABBREV.search(buf):
            continue
        yield buf
        buf = ""
    if buf:
        yield buf


def normalise_quotes(s: str) -> str:
    return re.sub(r"[„“”»«]", '"', s)


def clean(s: str) -> str:
    s = normalise_quotes(s).strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+([,.!?])", r"\1", s)
    # Drop wrapping quotes if the whole sentence is one quotation.
    if s.startswith('"') and s.count('"') == 2 and s.endswith(('"', '."', '!"', '?"')):
        s = s.strip('"').strip()
    if s.startswith('"') and s.count('"') == 1:
        s = s[1:].strip()
    return s


WORD = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")


def tokens(s: str):
    return WORD.findall(s)


def acceptable(s: str, min_words: int, max_words: int, lang: str) -> bool:
    if not s or not s[0].isupper():
        return False
    if s[-1] not in ".!?":
        return False
    if any(b in s for b in BAD_SUBSTRINGS):
        return False
    if re.search(r"\d", s):
        return False
    if s.count('"') not in (0, 2):
        return False
    if s.count(",") > 2:
        return False
    if lang == "de" and ARCHAIC.search(s):
        return False
    toks = tokens(s)
    if not (min_words <= len(toks) <= max_words):
        return False
    if re.match(r"^[IVXLC]+\.$", s):
        return False
    # Very long words are usually names, compounds or hyphenation debris.
    if any(len(t) > 18 for t in toks):
        return False
    return True


def modernise(s: str, mapping: dict) -> str:
    def rep(m):
        w = m.group(0)
        if w in mapping:
            return mapping[w]
        lw = w.lower()
        if lw in mapping:
            r = mapping[lw]
            return r.capitalize() if w[0].isupper() else r
        return w
    return WORD.sub(rep, s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="de")
    ap.add_argument("--raw-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-words", type=int, default=5)
    ap.add_argument("--max-words", type=int, default=13)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--lexicon", help="word-frequency list (word count per line); enables lexicon-based "
                                      "modernisation for pt and lexicon-based difficulty ranking")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    sources = SOURCES[args.lang]
    modern = MODERNISE.get(args.lang, {})
    names = {n.lower() for src in sources.values() for n in src[3].split()}
    lexicon = None
    if args.lexicon:
        from pt_modernise import Lexicon  # generic enough for other Romance languages later
        lexicon = Lexicon(args.lexicon)

    def modernise_sentence(sent):
        """-> (sentence, ok). With a lexicon, every ordinary word must resolve to a known form."""
        if lexicon is None:
            return modernise(sent, modern), True
        ok = True
        first = True
        def rep(m):
            nonlocal ok, first
            w = m.group(0)
            res, known = lexicon.modernise_word(w)
            exempt = w.lower() in names or (not first and w[:1].isupper())
            if not known and not exempt:
                ok = False
            first = False
            return res
        return WORD.sub(rep, sent), ok

    # Pass 1: collect sentences per book and global word frequencies.
    sentences = []  # (book_id, sentence)
    freq = collections.Counter()
    books_with_word = collections.defaultdict(set)
    for path in sorted(Path(args.raw_dir).glob("*.txt")):
        book_id = path.stem
        if book_id not in sources:
            continue
        text = strip_gutenberg(path.read_text(encoding="utf-8", errors="replace"))
        seen = set()
        for para in paragraphs(text):
            for sent in split_sentences(para):
                sent, ok = modernise_sentence(clean(sent))
                if not ok:
                    continue
                for t in tokens(sent):
                    lt = t.lower()
                    freq[lt] += 1
                    books_with_word[lt].add(book_id)
                if acceptable(sent, args.min_words, args.max_words, args.lang) and sent not in seen:
                    seen.add(sent)
                    sentences.append((book_id, sent))

    if lexicon is not None:
        rank = lexicon.rank
        unknown_rank = len(rank) + 1
    else:
        ranked = [w for w, _ in freq.most_common()]
        rank = {w: i + 1 for i, w in enumerate(ranked)}
        unknown_rank = 1

    def blank_candidates(sent):
        toks = tokens(sent)
        out = []
        for i, t in enumerate(toks):
            lt = t.lower()
            if len(t) < 3 or "'" in t or "’" in t or "-" in t:
                continue
            if lt in names:
                continue
            # Capitalised in mid-sentence: only allow if it also appears in >=2 books (so not a name).
            if i > 0 and t[0].isupper() and len(books_with_word[lt]) < 2:
                continue
            if i == 0 and len(books_with_word[lt]) < 2:
                continue
            if freq[lt] < 4:
                continue
            # Skip the very commonest function words: blanking "und"/"der" teaches little.
            if rank.get(lt, unknown_rank) <= 60:
                continue
            if lexicon is not None and not lexicon.known(lt):
                continue
            out.append((i, t))
        return out

    def difficulty(sent):
        toks = tokens(sent)
        return sum(math.log(rank.get(t.lower(), unknown_rank)) for t in toks) / len(toks) + 0.15 * len(toks)

    cards = []
    for book_id, sent in sentences:
        cands = blank_candidates(sent)
        if not cands:
            continue
        # Prefer mid-frequency words: not "und"/"der", not one-off rarities.
        weights = []
        for i, t in cands:
            r = rank.get(t.lower(), unknown_rank)
            w = 1.0 if r <= 4000 else 0.4
            if i == 0:
                w *= 0.3
            weights.append(w)
        i, t = rng.choices(cands, weights=weights, k=1)[0]
        author, title, year, _ = sources[book_id]
        cards.append({
            "id": f"{args.lang}-{book_id}-{len(cards):05d}",
            "lang": args.lang,
            "text": sent,
            "blank": t,
            "blank_index": i,
            "source": {"author": author, "title": title, "year": year, "gutenberg_id": int(book_id)},
            "difficulty": round(difficulty(sent), 3),
            "translation": None,
        })

    cards.sort(key=lambda c: c["difficulty"])
    with open(args.out, "w", encoding="utf-8") as f:
        for c in cards:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    by_book = collections.Counter(c["source"]["title"] for c in cards)
    print(f"{len(cards)} candidate sentences written to {args.out}", file=sys.stderr)
    for t, n in by_book.most_common():
        print(f"  {n:5d}  {t}", file=sys.stderr)


if __name__ == "__main__":
    main()
