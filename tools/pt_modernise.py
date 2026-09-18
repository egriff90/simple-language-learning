"""Modernise 19th-century Portuguese orthography (as found in Project Gutenberg
texts) using a lexicon of modern word frequencies.

Rules that are always safe are applied first (double consonants, ph/th/y,
d'elle-style contractions, verb+clitic "fazel-o" forms). Anything still unknown
is matched against the lexicon by trying spelling variants (dropped silent
consonants, ou/oi, s/z) and accent placements, picking the commonest hit.

    lex = Lexicon("tools/lexicon/pt.txt")
    lex.modernise_word("adolescencia")  -> ("adolescência", True)
    lex.modernise_word("xyzzy")         -> ("xyzzy", False)
"""
import re
from functools import lru_cache

MIN_KNOWN = 30          # lexicon count below which a word is not "known"
SWAP_RATIO = 10         # prefer an accented variant if it is this much commoner

# Fixed replacements for archaic forms that the lexicon may still contain.
FIXED = {
    "cousa": "coisa", "cousas": "coisas", "dous": "dois", "ha": "há", "hontem": "ontem",
    "hombro": "ombro", "hombros": "ombros", "hespanha": "espanha", "hespanhol": "espanhol",
    "he": "é", "hum": "um", "huma": "uma", "á": "à", "ás": "às", "aquelle": "aquele",
    "aquella": "aquela", "aquillo": "aquilo", "ahi": "aí", "alli": "ali", "assim": "assim",
    "sinão": "senão", "quasi": "quase", "mãi": "mãe", "pae": "pai", "paes": "pais",
    "tambem": "também", "porem": "porém", "então": "então", "atravez": "através",
    "vôo": "voo", "enjôo": "enjoo", "pêlo": "pelo", "pólo": "polo", "ideia": "ideia",
    "idéia": "ideia", "assembléia": "assembleia", "européia": "europeia", "heróico": "heroico",
    "jóia": "joia", "bôa": "boa", "bôas": "boas", "sêde": "sede", "êle": "ele", "êles": "eles",
    "êste": "este", "êsse": "esse", "aquêle": "aquele", "vêr": "ver", "têr": "ter",
    "vér": "ver", "ninguem": "ninguém", "alguem": "alguém", "ateh": "até",
    "áquelle": "àquele", "áquella": "àquela", "áquelles": "àqueles", "áquellas": "àquelas", "áquillo": "àquilo",
    "áquele": "àquele", "áquela": "àquela", "áqueles": "àqueles", "áquelas": "àquelas", "áquilo": "àquilo",
    "quiz": "quis", "quizer": "quiser", "quizesse": "quisesse", "quizeram": "quiseram", "quizera": "quisera",
    "quizeste": "quiseste", "quizemos": "quisemos", "fel-o": "fê-lo", "fel-a": "fê-la",
    "logar": "lugar", "logares": "lugares", "ceo": "céu", "ceos": "céus", "danza": "dança",
    "marquez": "marquês", "atraz": "atrás", "christo": "cristo", "pekin": "pequim",
    "principio": "princípio", "heide": "hei de", "signal": "sinal", "signaes": "sinais",
    "objecto": "objeto", "objectos": "objetos", "reflecti": "refleti", "urn": "um",
}

VOWELS = "aeiou"
ACCENTS = {
    "a": "áâã", "e": "éê", "i": "í", "o": "óôõ", "u": "ú",
}
STRIP_ACCENT = str.maketrans("áâãéêíóôõú", "aaaeeiooou")

APOSTROPHE = re.compile(r"^(d|n|c)['’](\w+)$")
CLITIC = re.compile(r"^(.+?)([aeiouáâêôíú])l-(o|a|os|as)$")
DOUBLE = re.compile(r"(bb|cc|dd|ff|gg|ll|mm|nn|pp|tt)")


def safe_rules(w: str) -> str:
    m = APOSTROPHE.match(w)
    if m:
        w = m.group(1) + m.group(2)
    m = CLITIC.match(w)
    if m:
        stem, v, cl = m.groups()
        acc = {"a": "á", "e": "ê", "i": "i", "o": "ô", "u": "u"}[v.translate(STRIP_ACCENT)]
        w = f"{stem}{acc}-l{cl}"
    w = DOUBLE.sub(lambda m: m.group(1)[0], w)
    w = w.replace("ph", "f").replace("th", "t")
    if "y" in w:
        w = w.replace("y", "i")
    return w


def variant_rules(w: str):
    """Spelling changes that are only right for some words: yield candidates."""
    yield w
    for a, b in (("ct", "t"), ("cç", "ç"), ("pt", "t"), ("pç", "ç"), ("sc", "c"), ("mn", "n"),
                 ("mpt", "nt"), ("gn", "n"), ("ou", "oi"), ("z", "s"), ("s", "z"), ("ch", "c"),
                 ("ch", "qu"), ("ch", "x"), ("x", "s"), ("ea", "eia"), ("ôa", "oa"), ("ê", "e"), ("ô", "o")):
        if a in w:
            yield w.replace(a, b, 1)
            if w.count(a) > 1:
                yield w.replace(a, b)
    # Silent internal h: distrahido -> distraído, cahir -> cair, comprehender -> compreender.
    if re.search(r"(?<=[^cln\W])h", w[1:]):
        yield w[0] + re.sub(r"(?<![cln])h", "", w[1:])


def accent_variants(w: str):
    base = w.translate(STRIP_ACCENT)
    yield base
    for i, ch in enumerate(base):
        for acc in ACCENTS.get(ch, ""):
            yield base[:i] + acc + base[i + 1:]


class Lexicon:
    def __init__(self, path):
        self.freq = {}
        with open(path, encoding="utf-8") as f:
            for line in f:
                w, n = line.rsplit(" ", 1)
                self.freq[w] = int(n)
        self.rank = {w: i + 1 for i, w in enumerate(sorted(self.freq, key=self.freq.get, reverse=True))}

    def known(self, w: str) -> bool:
        return self.freq.get(w, 0) >= MIN_KNOWN

    def best_accent(self, w: str):
        """Return the best accent placement for w, or None if nothing is known."""
        best, best_n = None, 0
        for v in accent_variants(w):
            n = self.freq.get(v, 0)
            if n > best_n:
                best, best_n = v, n
        if best is None or best_n < MIN_KNOWN:
            return None
        own = self.freq.get(w, 0)
        if own >= MIN_KNOWN and best != w and best_n < SWAP_RATIO * own:
            return w
        return best

    @lru_cache(maxsize=None)
    def modernise_word(self, word: str):
        """-> (modern form, known). Case of the first letter is preserved."""
        lower = word.lower()
        hyphen_ok = True
        if "-" in lower and not CLITIC.match(lower):
            parts = lower.split("-")
            out = []
            for p in parts:
                m, ok = self.modernise_word(p)
                hyphen_ok &= ok or p in ("lo", "la", "los", "las", "me", "te", "se", "lhe", "lhes", "nos", "vos", "o", "a", "os", "as", "no", "na")
                out.append(m)
            res = "-".join(out)
            return (self._recase(word, res), hyphen_ok)

        if lower in FIXED:
            res = FIXED[lower]
        else:
            w = safe_rules(lower)
            if w in FIXED:
                w = FIXED[w]
            res = None
            if CLITIC.match(lower) or re.search(r"[áêô]-l(o|a|os|as)$", w):
                stem = re.sub(r"-l(o|a|os|as)$", "", w)
                inf = stem.translate(STRIP_ACCENT) + "r"
                res = w if self.known(inf) else None
            elif self.known(w) and self.best_accent(w) == w:
                res = w
                # Prefer post-1990 forms (director -> diretor) when they are much commoner.
                for a, b in (("ct", "t"), ("cç", "ç"), ("pt", "t"), ("pç", "ç")):
                    if a in w and self.freq.get(w.replace(a, b), 0) >= SWAP_RATIO * self.freq[w]:
                        res = w.replace(a, b)
                        break
            else:
                best, best_n = None, 0
                for v in variant_rules(w):
                    b = self.best_accent(v)
                    if b and self.freq[b] > best_n:
                        best, best_n = b, self.freq[b]
                res = best
        if res is None:
            return (self._recase(word, safe_rules(lower)), False)
        return (self._recase(word, res), True)

    @staticmethod
    def _recase(original: str, res: str) -> str:
        if original[:1].isupper():
            return res[:1].upper() + res[1:]
        return res


if __name__ == "__main__":
    import sys
    lex = Lexicon(sys.argv[1])
    tests = ("annos elle d'elle n'um aquelle ridiculo adolescencia attinge affagos sciencia philosophia "
             "relembral-as apanhal-as fazel-o pol-o cousa ha hontem sôbre côrte gôso Thereza Braz Capitú "
             "possivel proprio memoria commigo á áquelle janella supplantando ridiculas prompto assignar "
             "quizer distrahidos chicaras contrario historia ella ellas mui está esta e é você casa disse-me "
             "director acção óptimo lyrica somno damno mesmo hoje ideia coração").split()
    for t in tests:
        print(t, "->", lex.modernise_word(t))
