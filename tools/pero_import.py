"""Converts machine-read text (PAGE XML) into the index layout: knihy/<archiv>/<kniha>/ocr-<cteni>.tsv,
stranky-<cteni>.tsv and the `ocr` list in kniha.yaml.

    python tools/pero_import.py <export.zip> [<export.zip> ...]

The export is PERO's own ZIP (`/document/download_document_pages/<id>`: PAGE XML + TXT per page), a `*.pagexml.zip`
bundle assembled in the browser ("### PAGE <id>" followed by the page's PAGE XML) or any other ZIP of PAGE XML files
(Transkribus, ScribbleSense). Only the text of each line, its bounding box and confidence are kept.

Everything the import needs is data in the book's kniha.yaml, so a new reading changes nothing outside knihy/:
- `import: {prefix, delitel}` – prefix is the part of the image file name before "_<number>" (empty when the export
  holds one book only), delitel turns the file number into the snímek on the portal (file number // delitel);
- an `ocr` entry whose `export` names the export (file name, with or without .zip/.pagexml.zip), with `soubor`
  (ocr-pero.tsv, or ocr-<cteni>.tsv for another tool or model), `nastroj`, `dokument`, `model`, `nastaveni`, `datum`.
  An export that mixes models (Transkribus) has one entry per model, told apart by `model_id` or "(model <id>)" in
  `model`. The import fills in snimky, stranek, radku and poznamka, and dokument or datum when they are empty.
One export may cover several books: each has its own kniha.yaml with the same `export`.

Every reading (one tool and model) has its own pair of files, so several readings of a book stand side by side and
none replaces another. A reading made in parts (several exports) is imported by passing all its exports in one call;
its files are rewritten as a whole, so an export left out drops its pages.
"""
import argparse
import csv
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import yaml

REPO = Path(__file__).resolve().parent.parent
KNIHY = REPO / "knihy"
# Defaults for an `ocr` entry that does not name its tool or settings.
PERO = "PERO OCR (pero-ocr.fit.vutbr.cz)"
PERO_NASTAVENI = "rozbor rozložení Handwritten layout, řádky Universal, jazykový model žádný"


def local(element):
    return element.tag.rsplit("}", 1)[-1]


def child(element, name):
    return next((c for c in element if local(c) == name), None)


def parse_page(xml):
    root = ElementTree.fromstring(xml)
    page = root if local(root) == "Page" else next((e for e in root.iter() if local(e) == "Page"), None)
    if page is None:
        return None
    width, height = int(page.get("imageWidth")), int(page.get("imageHeight"))
    lines = []
    for line in (e for e in page.iter() if local(e) == "TextLine"):
        points = [tuple(map(int, p.split(","))) for p in child(line, "Coords").get("points").split()]
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        equiv = child(line, "TextEquiv")
        unicode = child(equiv, "Unicode") if equiv is not None else None
        text = (unicode.text or "") if unicode is not None else ""
        conf = equiv.get("conf", "") if equiv is not None else ""
        lines.append((min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys), conf, " ".join(text.split())))
    info = {}
    for e in root.iter():
        name = local(e)
        if name == "Creator" and e.text and (m := re.search(r"model_id=(\d+)", e.text)):
            info["model_id"] = m[1]
        elif name == "Created" and e.text:
            info["datum"] = e.text[:10]
        elif name == "TranskribusMetadata":
            info["dokument"] = e.get("docId")
    image = page.get("imageFilename").rsplit(".", 1)[0]
    return image, width, height, lines, info


def pages(path):
    with zipfile.ZipFile(path) as archive:
        if path.name.endswith(".pagexml.zip"):
            for name in archive.namelist():
                for chunk in archive.read(name).decode("utf-8").split("### PAGE ")[1:]:
                    yield chunk.split("\n", 1)[1].encode("utf-8")
        else:
            for name in sorted(n for n in archive.namelist() if n.endswith(".xml")):
                yield archive.read(name)


def stem(name):
    return Path(str(name)).name.removesuffix(".zip").removesuffix(".pagexml")


def cteni_of(soubor):
    """ocr-pero.tsv -> pero, ocr-transkribus-czech-m1.tsv -> transkribus-czech-m1"""
    return str(soubor or "ocr-pero.tsv").removeprefix("ocr-").removesuffix(".tsv")


def model_id_of(entry):
    m = re.search(r"\(model (\d+)\)", str(entry.get("model", "")))
    return str(entry.get("model_id") or (m[1] if m else ""))


def books_of(export_stem):
    """{book folder: (kniha.yaml data, [its ocr entries for this export])} for every book the export covers."""
    found = {}
    for path in sorted(KNIHY.glob("*/*/kniha.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        entries = [e for e in data.get("ocr") or [] if isinstance(e, dict) and stem(e.get("export", "")) == export_stem]
        if entries:
            found[path.parent] = (data, entries)
    return found


def book_of(image, books):
    for folder, (data, _) in books.items():
        prefix = str((data.get("import") or {}).get("prefix", ""))
        if not prefix or image.startswith(prefix + "_"):
            return folder
    return None


def page_image(image, books):
    """Transkribus names a page '<page no>_<file>'; the book is found by the file name."""
    if book_of(image, books) is None and (m := re.match(r"\d{4}_(.+)$", image)):
        return m[1]
    return image


def file_number(image):
    m = re.search(r"(\d{4})(?:-[a-z]+)?$", image)
    return int(m.group(1)) if m else None


def snimek(data, image):
    n = file_number(image)
    if n is None:
        return ""
    return str(n // int((data.get("import") or {}).get("delitel", 10)))


def entry_for(entries, info, image):
    if len(entries) == 1:
        return entries[0]
    match = [e for e in entries if model_id_of(e) and model_id_of(e) == info.get("model_id")]
    if len(match) != 1:
        sys.exit(f"{image}: model {info.get('model_id')} does not pick exactly one ocr entry "
                 f"({', '.join(str(e.get('soubor')) for e in entries)}); set model_id in kniha.yaml")
    return match[0]


def compact(numbers):
    """1, 2, 3, 7 -> '1–3, 7'"""
    nums = sorted(set(numbers))
    out, start = [], None
    for k, n in enumerate(nums):
        if start is None:
            start = n
        if k + 1 == len(nums) or nums[k + 1] != n + 1:
            out.append(f"{start}–{n}" if n != start else f"{n}")
            start = None
    return ", ".join(out)


def files_of(cteni):
    return ("ocr-pero.tsv", "stranky.tsv") if cteni == "pero" else (f"ocr-{cteni}.tsv", f"stranky-{cteni}.tsv")


def dump_yaml(data):
    def q(value):  # a JSON string is a valid YAML scalar, colons included
        return str(value) if isinstance(value, int) else json.dumps(str(value), ensure_ascii=False)
    out = []
    for k, v in data.items():
        if isinstance(v, list):
            out.append(f"{k}:")
            for item in v:
                for n, (kk, vv) in enumerate(item.items()):
                    out.append(f"{'- ' if n == 0 else '  '}{kk}: {q(vv)}")
        elif isinstance(v, dict):
            out.append(f"{k}:")
            out += [f"  {kk}: {q(vv)}" for kk, vv in v.items()]
        elif v is not None:
            out.append(f"{k}: {q(v)}")
    return "\n".join(out) + "\n"


def write_book(folder, cteni, rows, page_rows, entries):
    ocr_file, pages_file = files_of(cteni)
    rows.sort(key=lambda r: (file_number(r[1]) or 0, r[1], r[2], r[4]))
    with open(folder / ocr_file, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["snimek", "soubor", "strana", "radek", "x", "y", "sirka", "vyska", "jistota", "text"])
        line_no = {}
        for snim, image, side, x, y, wd, ht, conf, text in rows:
            line_no[(image, side)] = line_no.get((image, side), 0) + 1
            w.writerow([snim, image, side, line_no[(image, side)], x, y, wd, ht, conf, text])
    page_rows.sort(key=lambda r: (file_number(r[1]) or 0, r[1]))
    with open(folder / pages_file, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["snimek", "soubor", "sirka_obrazku", "vyska_obrazku", "radku"])
        w.writerows(page_rows)
    path = folder / "kniha.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    old = data.get("ocr") or []
    keep = [e for e in old if isinstance(e, dict) and e.get("soubor", "ocr-pero.tsv") != ocr_file]
    data["ocr"] = keep + entries
    path.write_text(dump_yaml(data), encoding="utf-8", newline="\n")
    print(f"{folder.relative_to(KNIHY).as_posix()} {ocr_file}: {len(page_rows)} stran, {len(rows)} řádků")


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # the Windows console defaults to cp1252
    parser = argparse.ArgumentParser()
    parser.add_argument("export", type=Path, nargs="+")
    args = parser.parse_args()
    rows, page_rows, entries = {}, {}, {}
    for export in args.export:
        books = books_of(stem(export.name))
        if not books:
            sys.exit(f"no kniha.yaml describes export {stem(export.name)}: add an ocr entry with export: {export.name}")
        seen = {}
        for xml in pages(export):
            parsed = parse_page(xml)
            if parsed is None:
                continue
            image, width, height, lines, info = parsed
            image = page_image(image, books)
            folder = book_of(image, books)
            if folder is None:
                print(f"skipping page {image}", file=sys.stderr)
                continue
            data, book_entries = books[folder]
            entry = entry_for(book_entries, info, image)
            cteni = cteni_of(entry.get("soubor"))
            snim = snimek(data, image)
            page_rows.setdefault((folder, cteni), []).append([snim, image, width, height, len(lines)])
            for x, y, wd, ht, conf, text in lines:
                rows.setdefault((folder, cteni), []).append(
                    (snim, image, "L" if x < width / 2 else "R", x, y, wd, ht, conf, text))
            s = seen.setdefault((folder, cteni), {"entry": entry, "stranek": 0, "radku": 0, "snimky": [],
                                                  "dokumenty": [], "data": []})
            s["stranek"] += 1
            s["radku"] += len(lines)
            if snim.isdigit():
                s["snimky"].append(int(snim))
            for k, lst in (("dokument", "dokumenty"), ("datum", "data")):
                if info.get(k) and info[k] not in s[lst]:
                    s[lst].append(info[k])
        for (folder, cteni), s in seen.items():
            e, dates = s["entry"], sorted(s["data"])
            entry = {"soubor": files_of(cteni)[0], "nastroj": e.get("nastroj") or PERO,
                     "dokument": e.get("dokument") or ", ".join(s["dokumenty"]), "model": e.get("model", "")}
            if e.get("model_id"):
                entry["model_id"] = e["model_id"]
            if e.get("nastaveni") or entry["nastroj"] == PERO:
                entry["nastaveni"] = e.get("nastaveni") or PERO_NASTAVENI
            entry.update({"datum": e.get("datum") or (dates[0] if len(dates) < 2 else f"{dates[0]}–{dates[-1]}"),
                          "export": e.get("export") or export.name, "snimky": compact(s["snimky"]),
                          "stranek": s["stranek"], "radku": s["radku"],
                          "poznamka": f"souřadnice v pixelech nahraného obrázku (viz {files_of(cteni)[1]}); text je "
                                      f"strojový, nekontrolovaný"})
            entries.setdefault((folder, cteni), []).append(entry)
    for folder, cteni in entries:
        write_book(folder, cteni, rows.get((folder, cteni), []), page_rows.get((folder, cteni), []),
                   entries[(folder, cteni)])


if __name__ == "__main__":
    main()
