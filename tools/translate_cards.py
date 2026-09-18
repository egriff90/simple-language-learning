#!/usr/bin/env python3
"""Draft English translations (and a suggested blank word) for candidate sentences
using Claude, writing a curation TSV that you then review by hand.

Usage:
    pip install anthropic
    export ANTHROPIC_API_KEY=...        # or `ant auth login`
    python3 tools/translate_cards.py --lang de --start 0 --count 100 --out tools/de_curation_draft.tsv

Reads data/<lang>/candidates.jsonl (from extract_sentences.py) and writes lines of
    <candidate index> TAB <word to blank> TAB <English translation>
in the same format tools/<lang>_curation.tsv uses, so you can review, delete the
bad ones, and paste the survivors into the real curation file before running
build_deck.py.
"""
import argparse
import json
import sys
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
LANG_NAMES = {"de": "German", "fr": "French", "pt": "Portuguese"}
BATCH = 25

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "translation": {"type": "string"},
                    "blank": {"type": "string"},
                    "keep": {"type": "boolean"},
                },
                "required": ["index", "translation", "blank", "keep"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def translate_batch(client, lang_name, batch):
    listing = "\n".join(f"{c['_idx']}\t{c['text']}\t(suggested blank: {c['blank']})" for c in batch)
    prompt = (
        f"These are sentences from classic {lang_name} literature, for use as fill-in-the-blank "
        f"flashcards for an intermediate learner. For each sentence give:\n"
        f"- translation: a natural, faithful English translation of the whole sentence\n"
        f"- blank: the single word (copied exactly as it appears) that would make the best cloze "
        f"blank: a common, useful word whose form is determined by the sentence, not a proper name. "
        f"Keep the suggested blank unless a clearly better word exists.\n"
        f"- keep: false if the sentence is a poor flashcard (archaic spelling, dialect, fragment, "
        f"depends on unseen context, or hinges on a character's name); otherwise true.\n\n"
        f"Sentences (index TAB sentence):\n{listing}"
    )
    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Request refused: {response.stop_details}")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)["items"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=100)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    path = ROOT / "data" / args.lang / "candidates.jsonl"
    cands = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    for i, c in enumerate(cands):
        c["_idx"] = i
    chunk = cands[args.start: args.start + args.count]
    client = anthropic.Anthropic()
    by_idx = {c["_idx"]: c for c in chunk}

    rows = []
    for b in range(0, len(chunk), BATCH):
        batch = chunk[b: b + BATCH]
        try:
            items = translate_batch(client, LANG_NAMES.get(args.lang, args.lang), batch)
        except anthropic.RateLimitError as e:
            print(f"Rate limited; retry after {e.response.headers.get('retry-after', '?')}s", file=sys.stderr)
            sys.exit(2)
        except anthropic.APIStatusError as e:
            print(f"API error {e.status_code}: {e.message}", file=sys.stderr)
            sys.exit(2)
        except anthropic.APIConnectionError:
            print("Network error", file=sys.stderr)
            sys.exit(2)
        for it in items:
            c = by_idx.get(it["index"])
            if not c or not it["keep"]:
                continue
            blank = it["blank"] if it["blank"] in c["text"] else c["blank"]
            rows.append(f"{it['index']}\t{blank}\t{it['translation'].strip()}")
        print(f"translated {min(b + BATCH, len(chunk))}/{len(chunk)}", file=sys.stderr)

    Path(args.out).write_text("# Draft from translate_cards.py - review before merging into the curation file\n"
                              + "\n".join(rows) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
