"""Kontrola dat v knihy/: formát souborů, povinná pole a ochrana žijících lidí.

    python tools/kontrola.py                 # celý index
    python tools/kontrola.py --zmeny main    # jen knihy změněné proti větvi main, zákaz mazání řádků a přísná
                                             # pravidla pro přidané řádky precteno.tsv (datum, jistota, sloupce)

Chyby (ukončí s kódem 1) zastaví pull request a opravuje je autor. Body k posouzení (jen s --zmeny) nic nezamítají:
pull request s nimi projde správce, bez nich se u ověřeného přispěvatele sloučí sám. Varování jen upozorňují.
Spouští ji GitHub Action u každého pull requestu. Přísná pravidla platí jen pro přidané řádky: starší řádky indexu je
nesplňují a měnit se nesmějí.
"""
import argparse
import collections
import csv
import datetime
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
KNIHY = ROOT / "knihy"
HLAVICKY = {
    "precteno.tsv": ["snimek", "datum", "typ", "obec", "osoby", "ostatni", "jistota", "cetl", "odkaz"],
    "ocr-pero.tsv": ["snimek", "soubor", "strana", "radek", "x", "y", "sirka", "vyska", "jistota", "text"],
    "stranky.tsv": ["snimek", "soubor", "sirka_obrazku", "vyska_obrazku", "radku"],
    "opravy.tsv": ["snimek", "soubor", "strana", "x", "y", "sirka", "vyska", "puvodne", "spravne", "kdo", "jistota"],
    "vyklad.tsv": ["snimek", "datum", "udaj", "napsano", "spravne", "doklady", "kdo", "jistota"],
}
TYPY = {"N", "O", "Z", "P", "S", "K", "J"}
JISTOTA = ("vysoká", "střední", "nízká")
# Jazykový model se v cetl píše jako id/effort (claude-sonnet-5-5/xhigh), aby šlo zápisy přečtené slabším modelem
# najít a přečíst znovu; samotné „Claude“ nebo „agent“ nestačí. Effort je sjednocení hodnot API Anthropicu, OpenAI,
# Googlu a xAI, číslo je rozpočet na přemýšlení v tokenech (Gemini 2.5); „neuvedeno“ je pro nástroje, které effort
# neukazují. Id modelu obsahuje číslici nebo pomlčku (o3, gpt-5.2, deepseek-reasoner), aby se nespletlo s jiným textem.
EFFORT = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "neuvedeno")
MODEL_EFFORT = re.compile(r"\b(?=[a-z0-9.-]*[0-9-])[a-z][a-z0-9.]*(?:-[a-z0-9.]+)*/([a-z]+|[0-9]+)\b", re.I)
JAZYKOVY_MODEL = re.compile(r"\b(claude|agent|opus|sonnet|haiku|gpt|chatgpt|codex|o[1-9]|gemini|grok|copilot|deepseek|"
                            r"mistral|llama|qwen|kimi|perplexity|llm)\b", re.I)
# Produkt smí stát vedle id modelu, který v něm četl („Copilot gpt-4.1/neuvedeno“).
PRODUKT = re.compile(r"\b(chatgpt|copilot|perplexity)\b", re.I)
# Matriky narozených jsou veřejně přístupné po 100 letech, oddaných a zemřelých po 75 letech (zákon o matrikách
# 301/2000 Sb., § 5a); soupisy obyvatel držíme stejně jako narozené. Mladší zápisy mohou týkat žijících lidí.
LHUTA = {"N": 100, "S": 100, "O": 75, "Z": 75}
# Soubory, ve kterých se cizí řádky nesmí mazat ani měnit. Strojová čtení (ocr-*.tsv) se nepřepisují jinými nástroji:
# každé čtení má vlastní soubor a import ho přepíše jen celé, novým exportem téhož čtení.
NEPREPISOVAT = ("precteno.tsv", "opravy.tsv", "vyklad.tsv")
# Doklad výkladu: zápis v precteno.tsv, „<archiv>/<kniha>/<snimek> <datum> (popis)“; víc dokladů oddělených „; “.
DOKLAD = re.compile(r"^([^/\s]+)/([^/\s]+)/([^/\s]+) (\S+)(?: \((.+)\))?$")
# Výklad s nízkou jistotou je domněnka, ne doložená chyba písaře.
JISTOTA_VYKLADU = ("vysoká", "střední")
# Nejistě přečtená hodnota může být chyba čtení, ne písaře; výklad potřebuje čitelný údaj.
NEJISTE = re.compile(r"\[(\?|…|\.\.\.)\]")
# Datum přidaného řádku musí jít řadit a hledat: 1756-01-14, 1757-04, ~1723 nebo rozsah 1756–1758 (1786/1787).
# Neznámý den se vynechá, nejistota patří do ostatni.
_DEN = r"~?\d{4}(?:-(?:0[1-9]|1[0-2])(?:-(?:0[1-9]|[12]\d|3[01]))?)?"
DATUM = re.compile(rf"{_DEN}(?:[–/]{_DEN})?")
# Text osob ve sloupci obec znamená posunuté sloupce (chybějící nebo přebývající tabulátor).
OBEC_S_OSOBAMI = re.compile(r"^\s*(ženich|nevěsta|dítě|zemřel[áý]?|otec|matka|kmot[rř]\w*|svěd\w*)\s*:", re.I)
# Hlavička hunku diffu: +<první řádek>[,<počet>]; počet chybí, když je řádek jeden.
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
# Kniha smí obsahovat jen tyto soubory; skeny a celé exporty se do indexu nedávají.
POVOLENE = re.compile(r"^(kniha\.yaml|precteno\.tsv|opravy\.tsv|vyklad\.tsv|ocr-[a-z0-9-]+\.tsv|"
                      r"stranky(?:-[a-z0-9-]+)?\.tsv)$")
# E-mail, telefon nebo cesta na disk přispěvatele do veřejného indexu nepatří. Písmeno s dvojtečkou za písmenem je
# schéma adresy (https://), ne disk.
OSOBNI = re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}|\+42[01] ?\d{3} ?\d{3} ?\d{3}|\b[67]\d{2} \d{3} \d{3}\b|"
                    r"(?<![a-z])[a-z]:[\\/](?![\\/])|/Users/|/home/", re.I)

# Body k posouzení: pull request s nimi projde správce, bez nich se u ověřeného přispěvatele může sloučit sám. Jsou
# záměrně přísná; pravidlo, které správce opakovaně uzná za planý poplach, se povolí.
POSOUDIT = {
    "mimo-knihy": "mění soubory mimo knihy/",
    "zmena-knihy": "mění kniha.yaml existující knihy",
    "ocr": "přidává nebo přepisuje strojové čtení",
    "opravy": "přidává opravy strojového čtení",
    "vyklad": "přidává výklad chyby písaře",
    "novy-archiv": "první kniha z archivu, který v indexu ještě není",
    "velky-pr": "hodně nových řádků najednou",
    "novy-ctenar": "jméno v cetl, které v indexu ještě není",
    "rok-mimo-knihu": "rok zápisu leží mimo roky knihy",
    "snimek-mimo-knihu": "snímek za posledním snímkem knihy",
    "duplicita": "stejný zápis už v knize je",
    "vyklad-v-osobach": "osoby nebo ostatni obsahují slovo výkladu (příbuzenství, ztotožnění)",
    "nizka-jistota": "velký podíl zápisů s nízkou jistotou",
    "slaby-model": "starý zápis čtený slabším modelem nebo s nízkým effortem",
}
VELKY_PR = 150
NIZKA_JISTOTA_PODIL = 0.3
# Zápisy v precteno.tsv jsou doslovné; příbuzenství nebo ztotožnění, které v zápisu není, je výklad a patří do
# rodokmenu přispěvatele. Slovo ale může stát i v českém zápisu („bratr nevěsty“), proto jen k posouzení.
VYKLAD_SLOVA = re.compile(r"\b(sestr\w*|bratr\w*|švagr\w*|tch[áy]n\w*|zeť\w*|snach\w*|vnu[kč]\w*|strýc\w*|teta|tety|"
                          r"neteř\w*|synov[ec]\w*|sestřenic\w*|bratran\w*|totožn\w*|ztotožn\w*|před(?:ek|k\w+)|"
                          r"praděd\w*|prabab\w*|prapra\w*|rodokmen\w*|pravděpodobně|nejspíš|tentýž|tatáž|náš|naše\w*|"
                          r"můj|moje\w*)\b", re.I)
# Před rokem 1800 čte slabší model nebo nízký effort staré písmo citelně hůř.
SLABY_MODEL = re.compile(r"haiku|/(none|minimal|low)\b", re.I)
STARY_ZAPIS = 1800


class Hlaseni:
    def __init__(self):
        self.chyby, self.posoudit, self.varovani = [], [], []
        # Přidané řádky pro pravidla k posouzení: [(složka knihy, kde, řádek)] a počty u opravy.tsv a vyklad.tsv.
        self.pridane_zapisy = []
        self.pridane_jine = collections.Counter()

    def chyba(self, kde, co):
        self.chyby.append(f"{kde}: {co}")

    def posud(self, pravidlo, kde, co):
        self.posoudit.append((pravidlo, f"{kde}: {co}"))

    def varuj(self, kde, co):
        self.varovani.append(f"{kde}: {co}")


def rel(p):
    return p.relative_to(ROOT).as_posix()


def kontrola_knihy(d, h, prisne, pridane=None, nova=False):
    """d = knihy/<archiv>/<kniha>; prisne = kniha je v pull requestu, chybějící popis je chyba;
    pridane = {cesta souboru: čísla přidaných řádků}; nova = pull request knihu zakládá."""
    # Odkaz by kontrolu nechal číst soubory mimo repozitář a vypsat je do veřejného logu.
    if d.parent.is_symlink() or d.is_symlink() or any(p.is_symlink() for p in d.iterdir()):
        h.chyba(rel(d), "symbolický odkaz – kniha smí obsahovat jen obyčejné soubory")
        return
    for p in sorted(d.iterdir()):
        if p.is_dir():
            h.chyba(rel(p), "podsložka – kniha obsahuje jen soubory kniha.yaml, precteno.tsv, opravy.tsv, vyklad.tsv, "
                            "ocr-*.tsv a stranky*.tsv")
        elif not POVOLENE.match(p.name):
            h.chyba(rel(p), "soubor sem nepatří – kniha obsahuje jen kniha.yaml, precteno.tsv, opravy.tsv, vyklad.tsv, "
                            "ocr-*.tsv a stranky*.tsv; skeny a celé exporty se do indexu nedávají")
    archiv, kniha = d.parent.name, d.name
    ky = d / "kniha.yaml"
    if not ky.exists():
        (h.chyba if prisne else h.varuj)(rel(d), "chybí kniha.yaml (archiv, kniha, nazev, url)")
    else:
        text = ky.read_text(encoding="utf-8")
        if m := OSOBNI.search(text):
            h.chyba(rel(ky), f"„{m[0]}“ vypadá jako e-mail, telefon nebo cesta na disk – do veřejného indexu nepatří")
        try:
            meta = yaml.safe_load(text) or {}
        except yaml.YAMLError as e:
            h.chyba(rel(ky), f"neplatný YAML: {e}")
            meta = {}
        if not isinstance(meta, dict):
            h.chyba(rel(ky), "kniha.yaml musí být slovník polí (archiv, kniha, nazev, url…)")
            meta = {}
        url = meta.get("url")
        if url and (jinde := [k for k in urls_v_indexu().get(normalizuj_url(url), []) if k != f"{archiv}/{kniha}"]):
            if nova:
                h.chyba(rel(ky), f"kniha s touto url už v indexu je ({', '.join(jinde)}) – zápisy patří tam")
            elif not prisne:
                h.varuj(rel(ky), f"stejnou url má i {', '.join(jinde)}")
        # U MZA je složka id knihy z adresy matrika/detail/<id>, aby se stejná kniha nezaložila dvakrát.
        if archiv == "mza" and (m := re.search(r"/detail/(\d+)", str(url or ""))) and m[1] != kniha:
            h.chyba(rel(ky), f"složka knihy MZA má být id z url ({m[1]}), ne „{kniha}“")
        if meta.get("archiv") not in (None, archiv):
            h.chyba(rel(ky), f"archiv „{meta.get('archiv')}“ nesouhlasí se složkou „{archiv}“")
        if meta.get("kniha") not in (None, kniha):
            h.chyba(rel(ky), f"kniha „{meta.get('kniha')}“ nesouhlasí se složkou „{kniha}“")
        for pole in ("nazev", "url"):
            if not meta.get(pole):
                (h.chyba if prisne else h.varuj)(rel(ky), f"chybí pole {pole}")
        # Web vkládá url a mapa do odkazů; jiné schéma (javascript:) by spustilo kód v prohlížeči čtenáře.
        for pole in ("url", "mapa"):
            hodnota = meta.get(pole)
            if hodnota and not str(hodnota).startswith(("https://", "http://")):
                h.chyba(rel(ky), f"{pole} „{str(hodnota)[:60]}“ musí začínat https:// nebo http://")
    for p in sorted(d.glob("*.tsv")):
        jmeno = ("ocr-pero.tsv" if p.name.startswith("ocr-") else "stranky.tsv" if p.name.startswith("stranky-")
                 else p.name)
        if jmeno in HLAVICKY:
            kontrola_tsv(p, HLAVICKY[jmeno], h, None if pridane is None else pridane.get(rel(p), set()))
    if ky.exists():
        ocr = (yaml.safe_load(ky.read_text(encoding="utf-8")) or {}).get("ocr") or []
        for e in ocr if isinstance(ocr, list) else [ocr]:
            if isinstance(e, dict) and e.get("soubor") and not (d / str(e["soubor"])).exists():
                h.chyba(rel(ky), f"ocr: soubor {e['soubor']} v knize není")


def normalizuj_url(url):
    return re.sub(r"^http://", "https://", str(url).strip()).rstrip("/").lower()


_URLS = None


def urls_v_indexu():
    """{normalizovaná url: [archiv/kniha, …]} všech knih v indexu."""
    global _URLS
    if _URLS is None:
        _URLS = collections.defaultdict(list)
        for ky in KNIHY.glob("*/*/kniha.yaml"):
            try:
                meta = yaml.safe_load(ky.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                continue
            if isinstance(meta, dict) and meta.get("url"):
                _URLS[normalizuj_url(meta["url"])].append(f"{ky.parent.parent.name}/{ky.parent.name}")
    return _URLS


def rok_udalosti(datum):
    roky = [int(r) for r in re.findall(r"(?<!\d)(1[0-9]{3}|20[0-9]{2})(?!\d)", datum)]
    return max(roky) if roky else None


def model_bez_id(cetl):
    zbytek = MODEL_EFFORT.sub("", cetl)
    if zbytek != cetl:
        zbytek = PRODUKT.sub("", zbytek)
    return JAZYKOVY_MODEL.search(zbytek)


def kontrola_kdo(kde, kdo, h, pole):
    if not kdo.strip():
        h.chyba(kde, f"chybí {pole} (kdo a kdy)")
    elif spatne := [e for e in MODEL_EFFORT.findall(kdo) if e.lower() not in EFFORT and not e.isdigit()]:
        h.chyba(kde, f"{pole} „{kdo}“: effort „{spatne[0]}“ není z {', '.join(EFFORT)} ani počet tokenů")
    elif model_bez_id(kdo):
        h.chyba(kde, f"{pole} „{kdo}“: u jazykového modelu uveďte jeho id a effort, např. claude-sonnet-5-5/xhigh")


_ZAPISY = None


def zapisy():
    """Klíče (archiv, kniha, snimek, datum) všech řádků precteno.tsv v indexu."""
    global _ZAPISY
    if _ZAPISY is None:
        _ZAPISY = set()
        for p in KNIHY.glob("*/*/precteno.tsv"):
            with open(p, encoding="utf-8", newline="") as f:
                for r in list(csv.reader(f, delimiter="\t"))[1:]:
                    if len(r) >= 2:
                        _ZAPISY.add((p.parent.parent.name, p.parent.name, r[0], r[1]))
    return _ZAPISY


def rozeber_doklady(text):
    """Seznam (archiv, kniha, snimek, datum, popis); ValueError u položky, která neodpovídá formátu."""
    out = []
    for polozka in (x.strip() for x in text.split(";")):
        m = DOKLAD.match(polozka)
        if not m:
            raise ValueError(f"doklad „{polozka}“ není ve tvaru <archiv>/<kniha>/<snimek> <datum> (popis)")
        out.append(m.groups())
    return out


def kontrola_vykladu(p, r, kde, h):
    archiv, kniha = p.parent.parent.name, p.parent.name
    snimek, datum, udaj, napsano, spravne, doklady, kdo = r[:7]
    jistota = r[7] if len(r) > 7 else ""
    if (archiv, kniha, snimek, datum) not in zapisy():
        h.chyba(kde, f"zápis {snimek} {datum} není v precteno.tsv této knihy – vykládaný zápis se přidá nejdřív tam")
    if not (udaj.strip() and napsano.strip() and spravne.strip()):
        h.chyba(kde, "udaj, napsano i spravne musí být vyplněné")
    elif napsano.strip() == spravne.strip():
        h.chyba(kde, "napsano a spravne jsou stejné")
    elif NEJISTE.search(napsano):
        h.chyba(kde, f"napsano „{napsano}“ je nejisté čtení – výklad jen u čitelně napsaného údaje, jiné čtení patří "
                     f"do precteno.tsv")
    if not doklady.strip():
        h.chyba(kde, "chybí doklady (zápisy v indexu, které chybu dokazují)")
    else:
        try:
            for d in rozeber_doklady(doklady):
                if d[:2] == (archiv, kniha) and d[2:4] == (snimek, datum):
                    h.chyba(kde, "doklad nemůže být vykládaný zápis sám")
                elif d[:4] not in zapisy():
                    h.chyba(kde, f"doklad {'/'.join(d[:3])} {d[3]} není v precteno.tsv – přidejte ho tam")
        except ValueError as e:
            h.chyba(kde, str(e))
    kontrola_kdo(kde, kdo, h, "kdo")
    if jistota not in JISTOTA_VYKLADU:
        h.chyba(kde, f"jistota „{jistota}“: výklad jen s jistotou {' nebo '.join(JISTOTA_VYKLADU)}")


def kontrola_pridaneho(kde, typ, datum, obec, jistota, h):
    if not (DATUM.fullmatch(datum) or (typ == "J" and not datum)):
        h.chyba(kde, f"datum „{datum}“: použijte 1756-01-14, 1757-04, ~1723 nebo rozsah 1756–1758; neznámý den "
                     f"vynechte (1757-04), nejisté čtení napište do ostatni")
    if OBEC_S_OSOBAMI.match(obec):
        h.chyba(kde, f"obec „{obec[:40]}…“ obsahuje text osob – posunuté sloupce (chybí nebo přebývá tabulátor)?")
    if not jistota.startswith(JISTOTA):
        h.chyba(kde, f"jistota „{jistota}“ musí začínat {'/'.join(JISTOTA)}")


def kontrola_tsv(p, hlavicka, h, pridane=None):
    """pridane = čísla přidaných řádků (kontrola pull requestu), None = celý index."""
    pridane_rezim = pridane is not None
    pridane = pridane or set()
    with open(p, encoding="utf-8", newline="") as f:
        radky = list(csv.reader(f, delimiter="\t"))
    if not radky:
        h.chyba(rel(p), "prázdný soubor")
        return
    if radky[0] != hlavicka:
        h.chyba(rel(p), "hlavička musí být: " + "\t".join(hlavicka))
        return
    letos = datetime.date.today().year
    for i, r in enumerate(radky[1:], start=2):
        kde = f"{rel(p)}:{i}"
        if not any(r):
            continue
        # Prázdný poslední sloupec (odkaz) smí chybět.
        if len(r) not in (len(hlavicka), len(hlavicka) - 1):
            h.chyba(kde, f"{len(r)} sloupců místo {len(hlavicka)} (oddělovač je tabulátor)")
            continue
        if p.name in NEPREPISOVAT and (i in pridane or not pridane_rezim):
            if m := next(filter(None, (OSOBNI.search(c) for c in r)), None):
                h.chyba(kde, f"„{m[0]}“ vypadá jako e-mail, telefon nebo cesta na disk – do veřejného indexu nepatří")
        if p.name == "vyklad.tsv":
            kontrola_vykladu(p, r, kde, h)
            if i in pridane:
                h.pridane_jine[("vyklad", rel(p))] += 1
            continue
        if p.name == "opravy.tsv":
            kontrola_kdo(kde, r[9], h, "kdo")
            if i in pridane:
                h.pridane_jine[("opravy", rel(p))] += 1
            continue
        if p.name != "precteno.tsv":
            continue
        if i in pridane:
            h.pridane_zapisy.append((p.parent, kde, r))
        snimek, datum, typ, obec, osoby, _, jistota, cetl = r[:8]
        if not snimek.strip():
            h.chyba(kde, "chybí snímek")
        if typ not in TYPY:
            h.chyba(kde, f"typ „{typ}“ není z {', '.join(sorted(TYPY))}")
        kontrola_kdo(kde, cetl, h, "cetl")
        if not osoby.strip():
            h.varuj(kde, "prázdné osoby")
        if i in pridane:
            kontrola_pridaneho(kde, typ, datum, obec, jistota, h)
        elif jistota and not jistota.startswith(JISTOTA):
            h.varuj(kde, f"jistota „{jistota}“ nezačíná vysoká/střední/nízká")
        rok = rok_udalosti(datum)
        if rok is None:
            h.varuj(kde, f"datum „{datum}“ bez roku")
        elif typ in LHUTA and rok > letos - LHUTA[typ]:
            h.chyba(kde, f"zápis typu {typ} z roku {rok} je mladší než {LHUTA[typ]} let – může se týkat žijících "
                         f"lidí, do veřejného indexu nepatří")


def zmenene_knihy(zaklad):
    out = subprocess.run(["git", "diff", "--name-only", f"{zaklad}...HEAD", "--", "knihy"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.split()
    knihy = set()
    for f in out:
        casti = Path(f).parts
        if len(casti) >= 3:
            knihy.add(ROOT.joinpath(*casti[:3]))
    return knihy


def projdi_diff(zaklad, h):
    """Nahlásí odebrané nebo přepsané řádky v NEPREPISOVAT (změna se v diffu ukáže jako - a +) a vrátí čísla
    přidaných řádků těchto souborů {cesta: set}."""
    diff = subprocess.run(["git", "diff", "--unified=0", f"{zaklad}...HEAD", "--", "knihy"], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8", check=True).stdout
    pridane = collections.defaultdict(set)
    soubor = None
    for radek in diff.splitlines():
        if radek.startswith("--- "):
            continue
        if radek.startswith("+++ "):
            soubor = radek[6:] if radek.startswith("+++ b/") else None
            continue
        if not soubor or Path(soubor).name not in NEPREPISOVAT:
            continue
        if m := HUNK.match(radek):
            zacatek, pocet = int(m[1]), int(m[2]) if m[2] is not None else 1
            pridane[soubor].update(range(zacatek, zacatek + pocet))
        elif radek.startswith("-"):
            h.chyba(soubor, f"odebraný nebo změněný řádek: {radek[1:80]}… – cizí řádky se nemění, oprava patří do "
                            f"opravy.tsv nebo jako nový řádek")
    return pridane


def zmeny_souboru(zaklad):
    """[(stav A/M/D/T, cesta)] všech souborů, které pull request mění."""
    out = subprocess.run(["git", "-c", "core.quotepath=false", "diff", "--name-status", "--no-renames", "-z",
                          f"{zaklad}...HEAD"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                         check=True).stdout.split("\0")
    return [(out[i][0], out[i + 1]) for i in range(0, len(out) - 1, 2)]


def v_zakladu(zaklad, cesta):
    return subprocess.run(["git", "cat-file", "-e", f"{zaklad}:{cesta}"], cwd=ROOT, capture_output=True).returncode == 0


def roky(text):
    return [int(r) for r in re.findall(r"(?<!\d)(1[0-9]{3}|20[0-9]{2})(?!\d)", str(text or ""))]


def ctenar(cetl):
    """Jméno člověka v cetl, bez modelu, data a poznámky v závorce („Jan Novák + claude-opus-5-5/xhigh 2026-11-05“
    → „Jan Novák“); prázdné, když řádek četl jen model."""
    t = re.sub(r"\([^)]*\)", " ", MODEL_EFFORT.sub(" ", cetl))
    t = PRODUKT.sub(" ", re.sub(r"\d{4}(?:-\d{2}){0,2}", " ", t))
    return " ".join(t.replace("+", " ").replace(",", " ").split())


def tsv_radky(p):
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.reader(f, delimiter="\t"))


def posouzeni_pr(zaklad, zmeny, pridane, h):
    """Pravidla POSOUDIT nad celým pull requestem: změněné soubory a přidané řádky (h.pridane_zapisy)."""
    archivy = set()
    for stav, cesta in zmeny:
        casti = cesta.split("/")
        if casti[0] != "knihy":
            if cesta == "PREHLED.md":
                h.chyba(cesta, "PREHLED.md neměňte – po sloučení ho z dat v main přegeneruje GitHub Action; vraťte ho do "
                               "stavu v main")
            else:
                h.posud("mimo-knihy", cesta, POSOUDIT["mimo-knihy"])
            continue
        if len(casti) != 4:
            h.chyba(cesta, "soubor patří do složky knihy, knihy/<archiv>/<kniha>/")
            continue
        if stav == "D":
            h.chyba(cesta, "smazaný soubor – z indexu se nic nemaže")
            continue
        if casti[3] == "kniha.yaml" and stav != "A":
            h.posud("zmena-knihy", cesta, POSOUDIT["zmena-knihy"])
        if casti[3].startswith(("ocr-", "stranky")):
            h.posud("ocr", cesta, "nové strojové čtení" if stav == "A" else "přepsané strojové čtení")
        if casti[1] not in archivy:
            archivy.add(casti[1])
            if not v_zakladu(zaklad, f"knihy/{casti[1]}"):
                h.posud("novy-archiv", f"knihy/{casti[1]}", POSOUDIT["novy-archiv"])
    for (pravidlo, cesta), n in sorted(h.pridane_jine.items()):
        h.posud(pravidlo, cesta, f"{n} nových řádků")
    zapisy_pr = h.pridane_zapisy
    celkem = len(zapisy_pr) + sum(h.pridane_jine.values())
    if celkem > VELKY_PR:
        h.posud("velky-pr", "pull request", f"{celkem} nových řádků (víc než {VELKY_PR})")
    if not zapisy_pr:
        return
    znami = set()
    for p in KNIHY.glob("*/*/precteno.tsv"):
        nove = pridane.get(rel(p), set())
        znami.update(ctenar(r[7]) for i, r in enumerate(tsv_radky(p)[1:], start=2) if i not in nove and len(r) >= 8)
    nahlaseni, knihy, nizka = set(), {}, 0
    for d, kde, r in zapisy_pr:
        snimek, datum, typ, _, osoby, ostatni, jistota, cetl = r[:8]
        if d not in knihy:
            ky = d / "kniha.yaml"
            try:
                meta = (yaml.safe_load(ky.read_text(encoding="utf-8")) or {}) if ky.exists() else {}
            except yaml.YAMLError:
                meta = {}  # chybu už nahlásila kontrola_knihy
            snimky = [int(s[0]) for p in d.glob("stranky*.tsv") for s in tsv_radky(p)[1:] if s and s[0].isdigit()]
            p = d / "precteno.tsv"
            nove = pridane.get(rel(p), set())
            stare = {tuple(x.strip() for x in (s[0], s[1], s[2], s[4])) for i, s in enumerate(tsv_radky(p)[1:], start=2)
                     if i not in nove and len(s) >= 5}
            knihy[d] = (roky(meta.get("roky") if isinstance(meta, dict) else None), max(snimky, default=None), stare)
        roky_knihy, posledni, stare = knihy[d]
        jmeno = ctenar(cetl)
        if jmeno and jmeno not in znami and jmeno not in nahlaseni:
            nahlaseni.add(jmeno)
            h.posud("novy-ctenar", kde, f"„{jmeno}“ v indexu ještě nečetl")
        roky_zapisu = roky(datum)
        if roky_knihy and roky_zapisu and (min(roky_zapisu) < min(roky_knihy) - 1 or
                                           max(roky_zapisu) > max(roky_knihy) + 1):
            h.posud("rok-mimo-knihu", kde, f"datum {datum}, kniha {min(roky_knihy)}–{max(roky_knihy)}")
        if posledni and any(int(n) > posledni for n in re.findall(r"\d+", snimek)):
            h.posud("snimek-mimo-knihu", kde, f"snímek {snimek}, poslední snímek knihy {posledni}")
        if tuple(x.strip() for x in (snimek, datum, typ, osoby)) in stare:
            h.posud("duplicita", kde, f"zápis {snimek} {datum} {typ} se stejnými osobami už v knize je")
        if m := VYKLAD_SLOVA.search(f"{osoby} {ostatni}"):
            h.posud("vyklad-v-osobach", kde, f"„{m[0]}“ – je to v zápisu, nebo výklad?")
        if SLABY_MODEL.search(cetl) and roky_zapisu and min(roky_zapisu) < STARY_ZAPIS:
            h.posud("slaby-model", kde, f"zápis z roku {min(roky_zapisu)} četl {cetl}")
        nizka += jistota.startswith("nízká")
    if len(zapisy_pr) >= 5 and nizka / len(zapisy_pr) > NIZKA_JISTOTA_PODIL:
        h.posud("nizka-jistota", "pull request", f"{nizka} z {len(zapisy_pr)} nových zápisů má nízkou jistotu")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--zmeny", metavar="ZAKLAD", help="kontrolovat jen knihy změněné proti této větvi")
    a = ap.parse_args()
    h = Hlaseni()
    if a.zmeny:
        zmeny = zmeny_souboru(a.zmeny)
        nove = {ROOT / Path(c).parent for s, c in zmeny if s == "A" and c.count("/") == 3 and c.endswith("/kniha.yaml")}
        pridane = projdi_diff(a.zmeny, h)
        for d in sorted(zmenene_knihy(a.zmeny)):
            if d.is_dir():
                kontrola_knihy(d, h, prisne=True, pridane=pridane, nova=d in nove)
        posouzeni_pr(a.zmeny, zmeny, pridane, h)
    else:
        for d in sorted(p for p in KNIHY.glob("*/*") if p.is_dir() and p.parent.name != "testy"):
            kontrola_knihy(d, h, prisne=False)
    for v in h.varovani:
        print("varování:", v)
    for pravidlo, text in h.posoudit:
        print(f"k posouzení [{pravidlo}]:", text)
    for c in h.chyby:
        print("CHYBA:", c)
    print(f"chyb: {len(h.chyby)}, k posouzení: {len(h.posoudit)}, varování: {len(h.varovani)}")
    sys.exit(1 if h.chyby else 0)


if __name__ == "__main__":
    main()
