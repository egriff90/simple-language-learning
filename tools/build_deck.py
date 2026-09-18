#!/usr/bin/env python3
"""Build data/<lang>/cards.json from a candidates file plus a hand-curated TSV.

Usage:
    python3 tools/build_deck.py --lang de

Inputs:
    data/<lang>/candidates.jsonl   output of extract_sentences.py (one JSON per line)
    tools/<lang>_curation.tsv      lines of: <candidate index> TAB <word to blank> TAB <English>

Output card shape (what the web app consumes):
    {"id": "...", "cloze": "Er hielt inne und sah sich ___.", "answer": "um",
     "text": "Er hielt inne und sah sich um.", "translation": "He paused and looked around.",
     "source": {"author": ..., "title": ..., "year": ...}}

Cards are ordered easiest-first; the app drip-feeds them in this order.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def tidy(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'")
    # Old-fashioned capitalised "Du/Dich/Dein" inside a sentence -> modern lowercase.
    text = re.sub(r"(?<!^)(?<![.!?] )\b(Du|Dich|Dir|Dein|Deine|Deinen|Deiner)\b", lambda m: m.group(1).lower(), text)
    return text


def make_cloze(text: str, answer: str):
    pattern = re.compile(r"(?<![A-Za-zÄÖÜäöüß])" + re.escape(answer) + r"(?![A-Za-zÄÖÜäöüß])")
    m = pattern.search(text)
    if not m:
        return None
    return text[: m.start()] + "___" + text[m.end():]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True)
    args = ap.parse_args()

    cand_path = ROOT / "data" / args.lang / "candidates.jsonl"
    cur_path = ROOT / "tools" / f"{args.lang}_curation.tsv"
    out_path = ROOT / "data" / args.lang / "cards.json"

    candidates = [json.loads(l) for l in cand_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    cards, errors = [], []
    seen_ids = set()
    for line in cur_path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            errors.append(f"bad line: {line!r}")
            continue
        idx, answer, translation = int(parts[0]), parts[1].strip(), parts[2].strip()
        c = candidates[idx]
        text = tidy(c["text"])
        cloze = make_cloze(text, answer)
        if cloze is None:
            errors.append(f"{idx}: answer {answer!r} not found in {text!r}")
            continue
        if c["id"] in seen_ids:
            errors.append(f"{idx}: duplicate candidate")
            continue
        seen_ids.add(c["id"])
        cards.append({
            "id": c["id"],
            "cloze": cloze,
            "answer": answer,
            "text": text,
            "translation": translation,
            "source": {k: c["source"][k] for k in ("author", "title", "year")},
            "difficulty": c["difficulty"],
        })
    if errors:
        print("\n".join(errors), file=sys.stderr)
        sys.exit(1)
    cards.sort(key=lambda c: c["difficulty"])
    for c in cards:
        del c["difficulty"]
    out_path.write_text(json.dumps(cards, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(cards)} cards to {out_path}")


if __name__ == "__main__":
    main()
