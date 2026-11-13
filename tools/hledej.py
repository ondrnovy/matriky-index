"""Searches all indexed books for a word, tolerating OCR errors: entries read by eye (precteno.tsv), the scribe's errors
corrected in vyklad.tsv (a hit on the corrected value shows the entry as written) and the machine OCR text
(ocr-pero.tsv and the other readings ocr-<cteni>.tsv) with corrections from opravy.tsv applied (the original OCR text
is searched too).

    python tools/hledej.py <slovo> [--maxd 2] [--kniha KNIHA] [--kontext 1] [--skip REGEX]

Every OCR word (lower-case, without diacritics) is compared with <slovo> on its first len(<slovo>) characters by
Levenshtein distance, because PERO garbles rare surnames (Plocar → „Klozara“, „Plogar“). An empty result does not prove
that a name is missing from a book.
"""
import argparse
import csv
import re
import sys
import unicodedata
from pathlib import Path

from opravy import apply, ocr_files, read_tsv

REPO = Path(__file__).resolve().parent.parent
csv.field_size_limit(10_000_000)


def norm(text):
    text = unicodedata.normalize("NFD", text.replace("ſ", "s").replace("ʃ", "s"))
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # the Windows console defaults to cp1252
    parser = argparse.ArgumentParser()
    parser.add_argument("slovo")
    parser.add_argument("--maxd", type=int, default=2)
    parser.add_argument("--kniha", help="jen tato kniha (název adresáře, např. dnesice-01)")
    parser.add_argument("--kontext", type=int, default=1, help="kolik řádků nad a pod zásahem vypsat")
    parser.add_argument("--skip", help="regulární výraz slov, která se ignorují, např. '^(ploze|plota)'")
    args = parser.parse_args()
    target = norm(args.slovo)
    skip = re.compile(args.skip) if args.skip else None
    hits = 0
    def found(text):
        words = [w for w in re.split(r"[^a-z]+", norm(text)) if len(w) >= len(target) - 1]
        return next((w for w in words if not (skip and skip.match(w)) and lev(w[: len(target)], target) <= args.maxd),
                    None)

    for folder in sorted(p for p in REPO.glob("knihy/*/*") if p.is_dir()):
        book = folder.name
        if args.kniha and book != args.kniha:
            continue
        where = f"{folder.parent.name}/{book}"
        vyklady = {}
        for v in read_tsv(folder / "vyklad.tsv"):
            vyklady.setdefault((v["snimek"], v["datum"]), []).append(v)
        entries = {}
        for row in read_tsv(folder / "precteno.tsv"):
            text = " | ".join(row.get(k, "") for k in ("datum", "typ", "obec", "osoby", "ostatni"))
            entries.setdefault((row["snimek"], row["datum"]), text)
            note = "".join(f" [výklad: {v['udaj']} „{v['napsano']}“ → „{v['spravne']}“]"
                           for v in vyklady.get((row["snimek"], row["datum"]), []))
            match = found(text)
            if match:
                hits += 1
                print(f"{where} snímek {row['snimek']} [očima]{note} [{match}] {text}")
        for (snimek, datum), rows in vyklady.items():
            for v in rows:
                match = found(v["spravne"])
                if match:
                    hits += 1
                    print(f"{where} snímek {snimek} [výklad] [{match}] {v['udaj']}: napsáno „{v['napsano']}“, správně "
                          f"„{v['spravne']}“ (doklady: {v['doklady']}) | {entries.get((snimek, datum), datum)}")
        for ocr in ocr_files(folder):
            label = "" if ocr.name == "ocr-pero.tsv" else f" [{ocr.stem.removeprefix('ocr-')}]"
            rows = read_tsv(ocr)
            for row in rows:  # the test crops (knihy/testy) have "vyrez" instead of "soubor" and no "strana"
                row.setdefault("soubor", row.get("vyrez", ""))
                row.setdefault("strana", "")
            rows = apply(rows, read_tsv(folder / "opravy.tsv"))
            pages = {}
            for row in rows:
                pages.setdefault((row["soubor"], row["strana"]), []).append(row)
            for (image, side), lines in pages.items():
                for i, row in enumerate(lines):
                    match = found(row["text"]) or (found(row["text_ocr"]) if "text_ocr" in row else None)
                    if not match:
                        continue
                    hits += 1
                    around = " / ".join(r["text"] for r in lines[max(0, i - args.kontext): i + args.kontext + 1])
                    fixed = " [opraveno]" if "text_ocr" in row else ""
                    print(f"{where}{label} snímek {row['snimek']}{side} ř.{row['radek']}{fixed} [{match}] {around}")
    print(f"{hits} zásahů", file=sys.stderr)


if __name__ == "__main__":
    main()
