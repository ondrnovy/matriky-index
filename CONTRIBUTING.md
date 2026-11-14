# Jak přispět do indexu

Index je společný: co jednou někdo přečetl, nemusí už nikdo číst znovu. Když si necháte přečíst matriku, pozemkovou knihu,
sčítání lidu nebo jiný pramen (očima, přes PERO OCR, Claude nebo jiný nástroj), pošlete výsledek sem, ne jen do svého
klonu. Přečtené zápisy se hodí, i když se netýkají vaší rodiny – právě ty ušetří práci ostatním.

## Tři cesty

1. **Pull request** (doporučeno; Claude Code nebo jiný agent ho připraví sám, viz [AGENTS.md](AGENTS.md)):
   fork repozitáře → nová větev → přidané řádky v `knihy/<archiv>/<kniha>/` → `python tools/kontrola.py` →
   pull request proti větvi `main`.
2. **Formulář „Nové čtení“** v [Issues](../../issues/new/choose) pro ty, kdo nepoužívají git: archiv, kniha, snímky a
   přečtené zápisy (vložený text nebo přiložený soubor). Správce z nich pull request udělá.
3. **Úprava v prohlížeči**: na GitHubu otevřete `precteno.tsv` knihy, tužkou ho upravte (přidejte řádky na konec) a
   zvolte „Propose changes“ – GitHub sám vytvoří fork a pull request.

Než začnete číst celou knihu, podívejte se do [PREHLED.md](PREHLED.md) a `python tools/hledej.py`, jestli už přečtená
není, a založte Issue „Čtu: <archiv>/<kniha>“ (formulář „Čtu knihu“), ať ji nečte někdo další souběžně. Do popisu
pull requestu, který knihu dočte, napište `Closes #<číslo issue>`; GitHub issue po sloučení zavře sám.

## Co se přidává

- `precteno.tsv` – zápisy přečtené očima, jeden řádek na zápis, doslovně, nejistá místa s `[?]`; formát v
  [README](README.md#precteno-tsv--zápisy-přečtené-očima). Do `cetl` napište, kdo četl a kdy, např.
  `Jan Novák 2026-11-05`; s jazykovým modelem i jeho id a effort, např.
  `Jan Novák + claude-opus-5-5/xhigh 2026-11-05` (viz [Kdo četl](README.md#kdo-četl)).
- `ocr-pero.tsv`, `stranky.tsv` – strojový text z PERO; postup v [PERO.md](PERO.md). Strojový text z jiného
  nástroje nebo modelu (Transkribus, ScribbleSense) jako další čtení `ocr-<cteni>.tsv` a `stranky-<cteni>.tsv` vedle
  něj – stávající čtení se nemaže ani nepřepisuje; nástroj, model, nastavení a snímky do `ocr` v `kniha.yaml`.
- `opravy.tsv` – opravy strojového čtení, nástrojem `tools/opravy.py`.
- `vyklad.tsv` – chyby písaře (špatné jméno, věk, vztah), které dokazují jiné zápisy v indexu, nástrojem
  `tools/vyklad.py`; formát a pravidla v [README](README.md#vykladtsv--chyby-písaře).
- Nová kniha potřebuje `kniha.yaml` aspoň s poli `archiv`, `kniha`, `nazev`, `url` (odkaz na knihu na portálu archivu),
  ideálně i `roky`, `farnost`, `obsah`, a pokud knihu má [Mapa matrik](https://github.com/ondrnovy/mapa-matrik), i `mapa`
  (odkaz na mapu knihy, např. `https://ondrnovy.github.io/mapa-matrik/v1/svazky/soa-plzen/kozlany-22.json`).

Nepatří sem: skeny a celé exporty z PERO (dají se kdykoli stáhnout znovu), jiný výklad než doložená chyba písaře (kdo
osoba ve skutečnosti je, čí je sourozenec – to patří do vašeho rodokmenu, ve sloupci `odkaz` se na něj dá odkázat), a to
ani do sloupců `osoby` a `ostatni`, a nic o žijících lidech.

## Pravidla

- **Jen přidávat.** Řádky se nemažou ani nepřepisují – cizí ani vlastní, které už jsou v `main`. Nesouhlasíte se čtením
  nebo jste ho zpřesnili? Přidejte nový řádek k témuž zápisu nebo opravu do `opravy.tsv`; čtení zůstanou vedle sebe a
  rozhodne sken.
- **`PREHLED.md` neměňte.** Po sloučení ho z dat v `main` přegeneruje GitHub Action; v pull requestech by se hádal.
- **Žijící lidé.** Matriky narozených jsou veřejné po 100 letech, oddaných a zemřelých po 75 letech (zákon o matrikách
  301/2000 Sb.); stejnou lhůtu držíme u sčítání lidu. Mladší zápisy kontrola odmítne.
- **Ohleduplnost k archivům.** Stahujte jen, co potřebujete, a přes `tools/scan/slusne.py` (viz
  [README](README.md#ohleduplnost-k-archivům)). Blokaci archivu neobcházejte.
- **Každý řádek musí jít ověřit**: archiv, kniha a snímek vedou na sken. Proto se nepřidávají zápisy bez snímku.

## Kontrola a schválení

1. U každého pull requestu běží automaticky `python tools/kontrola.py --zmeny main`; totéž si spusťte předem. Výsledek
   uvidíte u pull requestu jako štítek, při chybách nebo bodech k posouzení i s komentářem a výpisem:
   - `kontrola-chyby` – formát, povinná pole, lhůty, smazané nebo změněné řádky, soubor, který do indexu nepatří (sken,
     `PREHLED.md`), e-mail nebo cesta na disk, kniha, která už v indexu je pod jinou složkou. Opravte a pošlete změny
     do téže větve, kontrola proběhne znovu.
   - `k-posouzeni` – bez chyb, jen pár míst nechává kontrola na správci: rok mimo roky knihy, snímek za koncem knihy,
     slovo příbuzenství nebo ztotožnění v `osoby` či `ostatni`, nové jméno v `cetl`, hodně nízké jistoty, víc než 150
     řádků, strojové čtení, oprava nebo výklad, změna `kniha.yaml` existující knihy, nový archiv, soubor mimo `knihy/`.
     Opravovat nic nemusíte, správce pull request projde a sloučí. Tato pravidla jsou zatím přísná a podle zkušeností
     se budou povolovat.
   - `kontrola-ok` – bez chyb i bez bodů k posouzení.
2. Správce pull request projde a namátkou porovná několik řádků se skeny. U ověřených přispěvatelů se pull request se
   štítkem `kontrola-ok` může sloučit sám; i takové správce namátkou vybírá k porovnání, před sloučením i po něm.
   Chybné čtení není problém, pokud je označené nižší jistotou; vymyšlená data bez snímku se nepřijímají.
3. Po sloučení se kniha sama objeví v [PREHLED.md](PREHLED.md).

## Licence

Odesláním pull requestu nebo formuláře souhlasíte, že vaše data budou zveřejněna pod licencí
[CC BY 4.0](LICENSE-DATA.md) jako zbytek indexu a příspěvky do `tools/` pod licencí [MIT](LICENSE). Autorství zůstává
vidět ve sloupci `cetl` a v historii gitu.
