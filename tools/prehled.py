"""Vygeneruje PREHLED.md: knihy v indexu, rozsah strojového čtení (PERO) a počty zápisů přečtených očima.

    python tools/prehled.py
"""
import csv
import datetime
import sys
from collections import Counter
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
ARCHIVY = {
    "portafontium": "SOA Plzeň – Porta fontium",
    "vca": "SOA Zámrsk – Východočeské archivy (ARON)",
    "zayt": "Národní archiv – židovské matriky a familianti (zayt.org)",
    "soapraha": "SOA Praha – eBadatelna",
    "soatrebon": "SOA Třeboň – DigiArchiv",
    "ahmp": "Archiv hlavního města Prahy",
    "mza": "Moravský zemský archiv – Acta Publica",
    "konskripce": "Národní archiv – pražské policejní přihlášky (konskripce)",
    "familysearch": "FamilySearch – digitalizované fondy českých archivů",
}
TYPY = {"N": "narození", "O": "sňatky", "Z": "úmrtí", "P": "převody gruntů", "S": "soupisy", "J": "jiné"}


def rows(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def lines(path):
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as f:
        return max(sum(1 for _ in f) - 1, 0)


def num(n):
    return f"{n:,}".replace(",", " ")


def cell(s):
    return str(s or "").replace("|", "/").replace("\n", " ")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    books = []
    for d in sorted((REPO / "knihy").glob("*/*")):
        if not d.is_dir() or d.parent.name == "testy":
            continue
        meta = yaml.safe_load((d / "kniha.yaml").read_text(encoding="utf-8")) if (d / "kniha.yaml").exists() else {}
        pre = rows(d / "precteno.tsv")
        books.append({
            "archiv": d.parent.name, "kniha": d.name, "nazev": meta.get("nazev") or d.name, "url": meta.get("url"),
            "druh": meta.get("druh") or "matrika", "roky": meta.get("roky") or "",
            "stran": len({r.get("snimek") for p in d.glob("stranky*.tsv") for r in rows(p)}),
            "radku": sum(lines(p) for p in d.glob("ocr-*.tsv")),
            "typy": Counter(r.get("typ") or "J" for r in pre), "ocima": len(pre),
        })
    total = Counter()
    for b in books:
        total["knih"] += 1
        total["stran"] += b["stran"]
        total["radku"] += b["radku"]
        total["ocima"] += b["ocima"]
        total.update({"t" + k: v for k, v in b["typy"].items()})
    druhy = Counter(b["druh"] for b in books)
    today = datetime.date.today()
    out = [
        "# Přehled indexu",
        "",
        f"Stav k {today.day}. {today.month}. {today.year} (generuje `python tools/prehled.py`).",
        "",
        f"- **{total['knih']} knih** ({', '.join(f'{k} {v}' for k, v in druhy.most_common())})",
        f"- **{num(total['stran'])} stran** převedených strojově (PERO OCR), **{num(total['radku'])} řádků** strojového "
        "textu – nekontrolovaný, slouží k hledání",
        f"- **{num(total['ocima'])} zápisů přečtených očima**: "
        + ", ".join(f"{TYPY[k]} {total['t' + k]}" for k in TYPY if total["t" + k]),
        "",
        "Sloupce: *OCR* = strany a řádky strojového textu, *očima* = zápisy přečtené člověkem nebo modelem se zdrojem a "
        "jistotou (N narození, O sňatky, Z úmrtí, P převody gruntů, S soupisy, J jiné). Skeny v indexu nejsou – "
        "odkaz vede na portál archivu.",
    ]
    for archiv in sorted({b["archiv"] for b in books}, key=lambda a: list(ARCHIVY).index(a) if a in ARCHIVY else 99):
        part = [b for b in books if b["archiv"] == archiv]
        out += ["", f"## {ARCHIVY.get(archiv, archiv)} ({len(part)})", "",
                "| kniha | druh | roky | OCR stran | OCR řádků | očima |", "|---|---|---|--:|--:|---|"]
        for b in part:
            name = f"[{cell(b['nazev'])}]({b['url']})" if b["url"] else cell(b["nazev"])
            typy = " ".join(f"{k} {v}" for k, v in sorted(b["typy"].items()))
            out.append(f"| {name} | {b['druh']} | {cell(b['roky'])} | {b['stran'] or ''} | "
                       f"{b['radku'] or ''} | {b['ocima'] or ''}{f' ({typy})' if typy else ''} |")
    (REPO / "PREHLED.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("PREHLED.md", total["knih"], "knih")


if __name__ == "__main__":
    main()
