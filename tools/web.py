"""Builds the browsable web page (GitHub Pages) of the index into a folder.

    python tools/web.py [--out _site]

Writes <out>/index.html (copied from web/index.html), <out>/data/knihy.json (one entry per book), <out>/data/precteno.json
and <out>/data/vyklad.json (all eye-read entries and interpretations, rows referring to a book by its position in
knihy.json) and copies knihy/ so the page can load a book's OCR and corrections on demand. Run by the GitHub Action
.github/workflows/pages.yml on every push to main; locally: python tools/web.py && python -m http.server -d _site.
"""
import argparse
import csv
import json
import re
import shutil
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
csv.field_size_limit(10_000_000)

# Region of the country an archive covers; the national archive and FamilySearch hold books from everywhere.
ARCHIVY = {
    "portafontium": ("SOA Plzeň (Porta fontium)", "západní Čechy"),
    "soatrebon": ("SOA Třeboň (DigiArchiv)", "jižní Čechy"),
    "soapraha": ("SOA Praha (eBadatelna)", "střední Čechy"),
    "ahmp": ("Archiv hl. m. Prahy", "Praha"),
    "konskripce": ("NA – pražské policejní přihlášky", "Praha"),
    "vca": ("SOA Zámrsk (VČA, ARON)", "východní Čechy"),
    "mza": ("Moravský zemský archiv (Acta Publica)", "jižní Morava"),
    "zaopava": ("Zemský archiv v Opavě", "severní Morava a Slezsko"),
    "zayt": ("NA – židovské matriky (zayt.org)", "celé Čechy"),
    "nacr": ("Národní archiv", "celé Čechy"),
    "cuzk": ("ČÚZK – indikační skici", "celé Čechy"),
    "ndk": ("Národní digitální knihovna", "edice a tisky"),
    "familysearch": ("FamilySearch", "různé"),
}


def url_snimku(archiv, kniha, url):
    """Address template of one scan ({snimek}), where the archive's viewer allows it; otherwise empty."""
    if archiv == "zayt":
        return url.split("?")[0] + "?p={snimek}"
    if archiv == "soatrebon" and re.fullmatch(r"\d+", kniha):
        return f"https://digi.ceskearchivy.cz/DA?lang=cs&menu=3&id={kniha}&page={{snimek}}"
    if archiv == "ahmp" and "permalink?xid=" in url:
        return url + "&scan={snimek}"
    return ""


def read_tsv(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.reader(f, delimiter="\t"))[1:]



def cteni(d, ocr):
    """Machine readings of the book for the viewer: [{soubor, stranky, popis}], PERO first."""
    out = []
    for p in sorted(d.glob("ocr-*.tsv"), key=lambda p: (p.name != "ocr-pero.tsv", p.name)):
        suffix = p.stem.removeprefix("ocr-")
        stranky = "stranky.tsv" if suffix == "pero" else f"stranky-{suffix}.tsv"
        info = [o for o in ocr if isinstance(o, dict) and o.get("soubor", "ocr-pero.tsv") == p.name]
        nastroj = str(info[0].get("nastroj", "")).split(" (")[0] if info else suffix
        model = str(info[0].get("model", "")) if info else ""
        snimky = ", ".join(str(o["snimky"]) for o in info if o.get("snimky"))
        out.append({"soubor": p.name, "stranky": stranky,
                    "popis": f"{nastroj}{' – ' + model if model else ''}{' (sn. ' + snimky + ')' if snimky else ''}"})
    return out

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(REPO / "_site"))
    args = parser.parse_args()
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    (out / "data").mkdir(parents=True)

    knihy, precteno, vyklad = [], [], []
    for meta_path in sorted(REPO.glob("knihy/*/*/kniha.yaml")):
        d = meta_path.parent
        archiv, kniha = d.parent.name, d.name
        if archiv == "testy":
            continue
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        i = len(knihy)
        rows = [r for r in read_tsv(d / "precteno.tsv") if len(r) >= 8]
        for r in rows:
            precteno.append([i] + (r + [""])[:9])
        for r in read_tsv(d / "vyklad.tsv"):
            if len(r) >= 7:
                vyklad.append([i] + (r + [""])[:8])
        stranky = [s for p in sorted(d.glob("stranky*.tsv")) for s in read_tsv(p)]
        ocr = meta.get("ocr") or []
        if isinstance(ocr, dict):
            ocr = [ocr]
        roky = [int(m) for r in rows for m in re.findall(r"(?<!\d)(1[4-9]\d\d)(?!\d)", r[1])]
        nazev_archivu, oblast = ARCHIVY.get(archiv, (archiv, "různé"))
        url = str(meta.get("url") or "")
        knihy.append({
            "id": f"{archiv}/{kniha}", "archiv": archiv, "archiv_nazev": nazev_archivu, "oblast": oblast, "kniha": kniha,
            "nazev": str(meta.get("nazev") or kniha), "farnost": str(meta.get("farnost") or ""),
            "druh": str(meta.get("druh") or "matrika"), "roky": str(meta.get("roky") or ""),
            "obsah": str(meta.get("obsah") or ""), "poznamka": str(meta.get("poznamka") or ""), "url": url,
            "mapa": str(meta.get("mapa") or ""), "url_snimku": url_snimku(archiv, kniha, url),
            "precteno": len(rows), "vyklad": sum(1 for v in vyklad if v[0] == i),
            "ocr_stran": len({s[0] for s in stranky if s}), "ocr_radku": sum(int(s[4]) for s in stranky if len(s) > 4 and s[4].isdigit()),
            "opravy": len(read_tsv(d / "opravy.tsv")),
            "ocr_model": ", ".join(dict.fromkeys(str(o.get("model", "")) for o in ocr if isinstance(o, dict))),
            "ocr_cteni": cteni(d, ocr),
            "precteno_od": min(roky) if roky else None, "precteno_do": max(roky) if roky else None,
        })

    def dump(name, value):
        (out / "data" / name).write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    dump("knihy.json", knihy)
    dump("precteno.json", precteno)
    dump("vyklad.json", vyklad)
    shutil.copy(REPO / "web" / "index.html", out / "index.html")
    shutil.copytree(REPO / "knihy", out / "knihy", ignore=shutil.ignore_patterns("testy"))
    (out / ".nojekyll").write_text("", encoding="utf-8")
    print(f"{out}: {len(knihy)} knih, {len(precteno)} přečtených zápisů, {len(vyklad)} výkladů")


if __name__ == "__main__":
    main()
