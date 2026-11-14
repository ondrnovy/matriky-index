"""Corrections of OCR readings (knihy/<archiv>/<kniha>/opravy.tsv) and applying them to the OCR lines.

    python tools/opravy.py <kniha> <snímek+strana> <řádek> <puvodne> <spravne> --kdo "Jan Novák 2026-10-21" [--jistota vysoká]

Example: python tools/opravy.py dnesice-01 24L 3 Plozene Plozara --kdo "claude-opus-5-5/xhigh 2026-10-21"
`puvodne` is the text as PERO read it (a word or a part of the line; empty string = the whole line), `spravne` what is
really written on the scan – a reading, not an interpretation (a scribe's error proven by other entries goes to
vyklad.tsv, who the person really was belongs to a family tree). `kdo` follows the same rule as `cetl` in precteno.tsv:
a language model is named by its id and effort. A correction
is anchored by the line's box on the scan, not by its number, so it survives a new OCR of the page.
"""
import argparse
import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIELDS = ["snimek", "soubor", "strana", "x", "y", "sirka", "vyska", "puvodne", "spravne", "kdo", "jistota"]



def ocr_files(folder):
    """Every machine reading of a book: ocr-pero.tsv first, then ocr-<cteni>.tsv of other tools and models."""
    return sorted(folder.glob("ocr-*.tsv"), key=lambda p: (p.name != "ocr-pero.tsv", p.name))

def book_dir(book):
    found = [p for p in REPO.glob(f"knihy/*/{book}") if p.is_dir()]
    if not found:
        sys.exit(f"kniha {book} neexistuje")
    return found[0]


def read_tsv(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def overlap(a, b):
    ax, ay, aw, ah = (int(a[k]) for k in ("x", "y", "sirka", "vyska"))
    bx, by, bw, bh = (int(b[k]) for k in ("x", "y", "sirka", "vyska"))
    w = min(ax + aw, bx + bw) - max(ax, bx)
    h = min(ay + ah, by + bh) - max(ay, by)
    if w <= 0 or h <= 0:
        return 0.0
    return w * h / min(aw * ah, bw * bh)


def apply(rows, corrections):
    """Returns the OCR rows with text corrected; a corrected row keeps the OCR text in `text_ocr`."""
    by_page = {}
    for c in corrections:
        by_page.setdefault(c["soubor"], []).append(c)
    out = []
    for row in rows:
        row = dict(row)
        for c in by_page.get(row["soubor"], []):
            if overlap(row, c) < 0.5:
                continue
            row.setdefault("text_ocr", row["text"])
            if c["puvodne"] and c["puvodne"] in row["text"]:
                row["text"] = row["text"].replace(c["puvodne"], c["spravne"])
            elif not c["puvodne"]:
                row["text"] = c["spravne"]
        out.append(row)
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # the Windows console defaults to cp1252
    parser = argparse.ArgumentParser()
    parser.add_argument("kniha")
    parser.add_argument("snimek", help="snímek a strana, např. 24L")
    parser.add_argument("radek", type=int)
    parser.add_argument("puvodne")
    parser.add_argument("spravne")
    parser.add_argument("--kdo", required=True)
    parser.add_argument("--jistota", default="vysoká")
    args = parser.parse_args()
    folder = book_dir(args.kniha)
    snimek, strana = args.snimek[:-1], args.snimek[-1].upper()
    line = next((r for p in ocr_files(folder) for r in read_tsv(p)
                 if r["snimek"] == snimek and r["strana"] == strana and int(r["radek"]) == args.radek), None)
    if line is None:
        sys.exit(f"řádek {args.radek} na snímku {args.snimek} v OCR není")
    if args.puvodne and args.puvodne not in line["text"]:
        sys.exit(f"„{args.puvodne}“ na řádku není: {line['text']}")
    path = folder / "opravy.tsv"
    new = not path.exists()
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, FIELDS, delimiter="\t", lineterminator="\n")
        if new:
            w.writeheader()
        w.writerow({**{k: line[k] for k in ("snimek", "soubor", "strana", "x", "y", "sirka", "vyska")},
                    "puvodne": args.puvodne, "spravne": args.spravne, "kdo": args.kdo, "jistota": args.jistota})
    print(f"{path.relative_to(REPO)}: {line['text']} → {args.spravne}")


if __name__ == "__main__":
    main()
