# Index matrik

Co už bylo z matričních knih přečteno – strojově (PERO OCR) i očima – bez vazby na konkrétní rodokmen. Slouží k tomu,
aby se stejná stránka nemusela znovu stahovat, OCRkovat ani číst. Index je veřejný a společný: kdo něco
nového přečte, pošle to sem (viz [Přispějte](#přispějte)).

Kromě matrik sem patří i další knihy se jmény: pozemkové (gruntovní) knihy, soupisy poddaných, familiantské knihy. Mají
stejnou strukturu; druh knihy říká pole `druh` v `kniha.yaml` (`matrika`, `pozemková kniha`, `urbář`,
`soupis poddaných`, `berní rula`, `sčítání lidu`, `policejní přihlášky`, `familianti`, `noviny`, `kronika`; chybí-li, jde o matriku). Zápisy přečtené dřív
při práci na rodokmenu mají ve sloupci `cetl` poznámku „(z rodokmenu …)“.

Skeny se neukládají (lze je kdykoli stáhnout z archivu). Plné exporty z PERO (PAGE XML s obrysy řádků) jsou mimo git.

**Prohlížení bez gitu: [pe-pan.github.io/matriky-index](https://pe-pan.github.io/matriky-index/)** – knihy podle oblasti a
archivu, hledání v přečtených zápisech, strojový text stránek s opravami a výklady. Stránku (`web/index.html`) i její data
vyrábí `python tools/web.py` (GitHub Action `pages.yml` po každém pushi do `main`; lokálně `python tools/web.py` a
`python -m http.server -d _site`). U zápisu přečteného víckrát (stejný snímek, datum, typ a obec) ukazuje nejnovější čtení
a starší na rozkliknutí.

Co v indexu je (knihy, rozsah OCR, počty přečtených zápisů): [PREHLED.md](PREHLED.md), po každé změně dat v `main` ho
přegeneruje GitHub Action (`tools/prehled.py`).

Licence: nástroje MIT ([LICENSE](LICENSE)), data v `knihy/` CC BY 4.0 ([LICENSE-DATA.md](LICENSE-DATA.md)).

## Kdo četl

Sloupec `cetl` v `precteno.tsv` uvádí u jazykového modelu jeho identifikátor a nastavení effortu (`claude-sonnet-5-5/xhigh`),
aby šlo zápisy přečtené slabším modelem nebo s nižším effortem najít a přečíst znovu lepším. Na kvalitu čtení má vliv
i rozlišení skenu (1600 px vs. výřez 4000 px); to uvádí sloupec `ostatni`, pokud je známé.

Řádky z let 2026-10 a 2026-11 dostaly model a effort dodatečně (`precteno.tsv` 2026-11-04, `opravy.tsv` 2026-11-05)
podle záznamů sezení Claude Code, kde je u každého dotazu uložen model i effort; dřív v nich stálo jen `agent` nebo
`Claude`. Stejné pravidlo platí pro sloupec `kdo` v `opravy.tsv` a `vyklad.tsv`.

Id modelu se píše, jak ho uvádí API (`claude-opus-5-5`, `gpt-5.2`, `o3`, `gemini-2.5-pro`, `grok-4`). Effort je
hodnota, jak ji nástroj nastavuje: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max` (Anthropic, OpenAI,
Google a xAI používají různé podmnožiny), u starších modelů Gemini rozpočet na přemýšlení v tokenech
(`gemini-2.5-pro/8192`). V Claude Code je effort v záznamu sezení (`~/.claude/projects/<projekt>/<sezení>.jsonl`, pole
`effort`), v Codex CLI v nastavení `model_reasoning_effort`. Aplikace jako claude.ai, ChatGPT, Gemini nebo Copilot
obvykle ukazují jen model nebo režim: tam patří `neuvedeno` a u produktu model, který v něm četl
(`Copilot gpt-4.1/neuvedeno`). Kontrola (`tools/kontrola.py`) odmítne řádek, v jehož `cetl` je jazykový model bez id
a effortu (samotné „Claude“, „ChatGPT“ nebo „agent“) nebo s jinou hodnotou effortu.

## Přispějte

Přečetli jste si matriku nebo jiný pramen – očima, přes PERO OCR nebo s Claudem? Pošlete to sem, ať to nemusí číst
nikdo další. Stačí pull request s novými řádky v `knihy/<archiv>/<kniha>/precteno.tsv` (Claude Code ho podle
[AGENTS.md](AGENTS.md) připraví sám), nebo formulář „Nové čtení“ v Issues. Pravidla, kontrola a licence:
[CONTRIBUTING.md](CONTRIBUTING.md). Než začnete číst celou knihu, založte Issue „Čtu knihu“.

## Struktura

```
knihy/<archiv>/<kniha>/
  kniha.yaml      popis knihy: archiv, název, farnost, roky, obsah (které snímky jsou N/O/Z), odkaz na portál,
                  volitelně mapa (odkaz na mapu knihy v Mapě matrik, github.com/ondrnovy/mapa-matrik), jak se
                  z čísla souboru dostat na snímek, a seznam ocr – u každého strojového čtení soubor, nástroj,
                  dokument, model, nastavení (rozbor rozložení, jazykový model, rozlišení), datum, snímky
  ocr-pero.tsv    strojový text z PERO: snímek, soubor, strana (L/R), řádek, obdélník x/y/šířka/výška v pixelech
                  obrázku, jistota (0–1), text – nekontrolovaný, s chybami
  stranky.tsv     stránky čtení ocr-pero.tsv: snímek, soubor, rozměry nahraného obrázku, počet řádků
  ocr-<cteni>.tsv,  další strojová čtení téže knihy (jiný nástroj nebo model, např. ocr-transkribus-czech-m1.tsv,
  stranky-<cteni>.tsv   ocr-scribblesense.tsv) ve stejném formátu; každé čtení má vlastní dvojici souborů
  precteno.tsv    zápisy přečtené očima (formát níže)
  opravy.tsv      opravy strojového čtení (viz Vrstvy a opravy)
  vyklad.tsv      chyby písaře doložené jinými zápisy (formát níže)
knihy/testy/      pokusná OCR (výřezy)
tools/
  kontrola.py     kontrola dat (formát, povinná pole, lhůty pro žijící lidi, doklady výkladů, u pull requestu i body
                  k posouzení); běží u každého pull requestu
  hledej.py       volné hledání slova ve všech knihách (precteno, výklady, OCR s opravami; Levenshtein na začátku slova)
  opravy.py       přidání opravy strojového čtení do opravy.tsv
  vyklad.py       přidání výkladu (chyby písaře) do vyklad.tsv
  pero_import.py  převod exportu z PERO do knihy/…
  prehled.py      vygeneruje PREHLED.md
  web.py          vyrobí webovou stránku indexu do _site/ (GitHub Pages)
  pero/           balik.py (skeny do balíků ≤ 9,4 MB), pero.js (nahrávání a export ve stránce PERO) – viz PERO.md
  scan/           stahování skenů: pfl.py, pf64.py (Porta fontium), ebget.py (eBadatelna SOA Praha), zget.py + rzip.py (VČA Zámrsk; vcakniha.py = celá kniha pro PERO),
                  zayt.py, books.py, bfilter.py (zayt.org), mza.py (Acta Publica, MZA Brno), zaopava.py (ZA Opava, cesty
                  ke snímkům zjistí tools/pero/zaopava.js v prohlížeči), cr.py (výřez skenu);
                  slusne.py = společný limit dotazů
```

Archivy: `portafontium` (SOA Plzeň), `soapraha` (eBadatelna, kniha = id matriky), `soatrebon`, `vca`, `zayt`, `nacr`,
`mza` (Acta Publica, kniha = id z adresy matrika/detail/<id>), `ahmp`, `familysearch` (kniha = číslo DGS),
`zaopava`, `konskripce` (policejní přihlášky NA), `cuzk` (indikační skici stabilního katastru, kniha = id rastru
z adresy ags.cuzk.gov.cz/archiv/openmap.html?typ=skicic&idrastru=<id>; čtou se v prohlížeči archivu map ČÚZK),
`ndk` (Národní digitální knihovna, noviny; kniha = titul a ročník, snímek = strana ročníku).

## Ohleduplnost k archivům

Digitální badatelny jsou veřejná služba pro všechny badatele, ne zdroj dat pro hromadné stahování. Když po nich začne
skeny tahat víc lidí s automatickými nástroji najednou, archiv přestane stíhat a odnesou to všichni, i ti, kdo listují
ručně. Na přelomu října a listopadu 2026 přestala Acta Publica (MZA Brno) odpovídat řadě badatelů a některé IP adresy
zablokovala.

- Stahujte jen knihy, které opravdu potřebujete, a jen jejich potřebnou část (rejstřík, roky, obec). Celou knihu do
  PERO teprve tehdy, když hledané jméno nejde najít jinak.
- Každé stahování jde přes `tools/scan/slusne.py`. Výchozí limit: stránky a hledání 1 dotaz za 2 s, obrázky 5 za 1 s.
  Přetížené archivy mají přísnější limit (`POMALE`, Acta Publica 1 snímek za 2 s). Po 429/503 je server půl hodiny
  zablokovaný pro všechny procesy (`python -I tools/scan/slusne.py stav`). Vlastní jednorázové skripty volají
  `slusne.urlopen()` / `slusne.get()`, ne přímo `urllib`, `requests` ani `curl`. Souběžné procesy limit nezrychlí, jen
  se o něj dělí.
- Když archiv odpovídá pomalu, píše o přetížení nebo vás zablokuje, dejte mu pauzu: `python -I tools/scan/slusne.py
  zablokuj <server> <hodin>`. Blokaci neobcházejte jinou sítí ani jinou IP adresou.
- Než knihu stáhnete, podívejte se do `knihy/`, jestli ji tu už někdo nepřečetl. Proto index existuje: jednou přečtená
  kniha se nemusí stahovat znovu.

## Hledání

    python tools/hledej.py plozar --maxd 2 [--kniha dnesice-01] [--skip '^(ploze|plota)'] [--kontext 1]

PERO komolí vzácná příjmení (Plocar → „Klozara“, „Plogar“), proto volné hledání; prázdný výsledek nedokazuje, že jméno
v knize není. Zásah se ověřuje na skenu (snímek a strana jsou ve výpisu).

## Přidání knihy

Celý postup (skeny podle archivu, nahrání do PERO, rozbor rozložení, volba modelu, export a import) je v
[PERO.md](PERO.md). Zkráceně: skeny do PERO (Porta fontium a Acta Publica přímo z prohlížeče, ostatní z disku),
„Handwritten layout“, OCR „Kurrent (German, Czech)“ pro kurent, „Czech Handwritten“ pro latinku, export, doplnit
`BOOKS` a `EXPORTS` v `tools/pero_import.py` a spustit `python tools/pero_import.py <export.zip>`.

Strojový text z jiného nástroje (Transkribus, ScribbleSense) se importuje stejně, z exportu PAGE XML: v `EXPORTS` se
u něj uvede `cteni` (přípona souborů), `nastroj`, `model` a `nastaveni`, případně `modely`, když export míchá víc
modelů. Vznikne `ocr-<cteni>.tsv` a `stranky-<cteni>.tsv` vedle stávajících čtení a položka v `ocr` v `kniha.yaml`.
Česká kurzíva 17.–18. století: Transkribus „Czech Handwriting M1“ čte jména zhruba dvakrát lépe než PERO; latinu a
kurent PERO stejně dobře nebo lépe.

## Vrstvy a opravy

Původní data se nepřepisují, opravy a výklady se přidávají zvlášť:

1. `ocr-pero.tsv` a `ocr-<cteni>.tsv` – strojový text, nemění se. Každé čtení (nástroj a model) má vlastní soubor;
   lepší čtení se přidá vedle, starší se nemaže – každý nástroj je silný na jiné písmo. Soubor se přepíše jen celý
   novým exportem téhož čtení.
2. `opravy.tsv` – opravy strojového čtení: co je na skenu opravdu napsáno (PERO „Plohar“, napsáno „Ploczar“). Oprava je
   ukotvená obdélníkem řádku na skenu, ne jeho číslem, takže přežije nové OCR. Přidává se nástrojem:

       python tools/opravy.py <kniha> <snímek+strana> <řádek> "<jak četl PERO>" "<co je napsáno>" --kdo "claude-opus-5-5/xhigh 2026-10-21"

   Sloupce: snimek, soubor, strana, x, y, sirka, vyska (obdélník řádku), puvodne (prázdné = celý řádek), spravne, kdo,
   jistota.
3. `precteno.tsv` – celé zápisy přečtené očima, doslovně, i s chybami písaře.
4. `vyklad.tsv` – chyby písaře: na skenu je čitelně napsáno něco, co jiné zápisy vyvracejí (jméno, věk, vztah). Zápis
   v `precteno.tsv` zůstává, jak je napsaný; výklad vedle něj říká, co je správně, a čím je to doložené (viz
   [vyklad.tsv](#vykladtsv--chyby-písaře)).

Jiný výklad (kdo osoba ve skutečnosti je, čí je sourozenec, ke které rodině patří) do indexu nepatří, ten je v rodokmenu
(ve sloupci `odkaz` se na něj dá odkázat).

`tools/hledej.py` prohledává `precteno.tsv` (zásah označen „[očima]“, s výkladem k zápisu „[výklad: …]“), správné hodnoty
z `vyklad.tsv` („[výklad]“ – hledání „Rozina“ najde i zápis, kde písař napsal Anna) a strojový text
s použitými opravami („[opraveno]“; hledá se i v původním znění).

## precteno.tsv – zápisy přečtené očima

Každý zápis, který člověk nebo agent při práci přečetl, i když se netýká hledané rodiny. Sloupce oddělené tabulátorem,
první řádek hlavička:

| sloupec | obsah |
|---|---|
| snimek | číslo snímku na portálu a strana, např. `124R` |
| datum | datum události v jednom z tvarů `1756-01-14`, `1757-04`, `~1723` nebo rozsah `1756–1758` (`1786/1787`); neznámý den nebo měsíc se vynechá, nejistě přečtené datum se zapíše bez otazníku a nejistota do `ostatni` (např. `datum nejisté`), aby šlo řadit a hledat; u `J` smí být prázdné |
| typ | `N` narození/křest, `O` sňatek, `Z` úmrtí/pohřeb, `P` převod gruntu v pozemkové knize (koupě, dědictví, přiženění, odhad), `S` řádek soupisu poddaných nebo sčítání lidu, `K` katastrální mapa (indikační skica: číslo domu, majitel), `J` jiné (ohlášky, atestát, rejstřík, familiant, prázdná strana) |
| obec | obec dnešním názvem a číslo domu (`Lhota 7`, `Praha – Nové Město 512`), aby šlo hledat podle místa; dobový tvar patří do `osoby` nebo `ostatni`, nejasnou obec nechte prázdnou; u pozemkové knihy i jméno gruntu (`Nová Ves 3, grunt Horákovský`) |
| osoby | hlavní osoby s rolí: `dítě: Jan; otec: Václav Novák; matka: Ludmila` (u O ženich, nevěsta a jejich rodiče; u P `prodávající: …; kupující: …; výměnkář: …`; u S `hospodář: …; manželka: …; děti: …`) |
| ostatni | kmotři, svědci, povolání, věk, příčina smrti – stručně; u P cena, splátky, výminek, svědci |
| jistota | `vysoká`, `střední`, `nízká` (smí následovat vysvětlení v závorce); nejisté čtení v textu značit `[?]` |
| cetl | kdo a kdy: jazykový model jako `model/effort datum` (`claude-sonnet-5-5/xhigh 2026-11-03`, ověření `…, ověřil claude-opus-5-5/xhigh 2026-11-04`), člověk jménem a datem (viz [Kdo četl](#kdo-četl)) |
| odkaz | volitelně odkaz na zpracovaný záznam jinde (např. v rodokmenu) |

## vyklad.tsv – chyby písaře

Farář se občas spletl: zapsal matku jménem babičky, věk zemřelého odhadl o několik let vedle, popletl jméno. Kdo to
dokáže jinými zápisy, zapíše to do `vyklad.tsv` téže knihy. Sloupce oddělené tabulátorem, první řádek hlavička:

| sloupec | obsah |
|---|---|
| snimek, datum | vykládaný zápis, přesně jako v `precteno.tsv` téže knihy |
| udaj | který údaj je chybný: `věk zemřelého`, `jméno matky`, `jméno babičky (matky matky)`, … |
| napsano | co je v zápisu čitelně napsáno (`67`, `Anna`), bez `[?]` |
| spravne | co je správně (`63`, `Rozina`) |
| doklady | zápisy v indexu, které to dokazují: `<archiv>/<kniha>/<snimek> <datum> (popis)`, víc dokladů oddělených `; ` |
| kdo | kdo a kdy, stejně jako `cetl` (u jazykového modelu id a effort) |
| jistota | `vysoká` nebo `střední`; domněnka s nízkou jistotou sem nepatří |

Příklad (smyšlený):

    124R	1768-03-12	jméno matky	Anna	Rozina	portafontium/lhota-03/88L 1762-02-04 (sňatek rodičů); portafontium/lhota-03/131R 1770-05-02 (křest sourozence)	Jan Novák 2026-11-05	vysoká

Pravidla:

- **Doklady jsou zápisy v indexu.** Vykládaný zápis i každý doklad musí být v `precteno.tsv`, aby šel kdokoli ověřit
  na skenu; kontrola jinak řádek odmítne. Rodinná tradice nebo vlastní rodokmen doklad nejsou.
- **Jen čitelně napsaný údaj.** Je-li zapsaná hodnota nejistá (`24 [?]`), může jít o chybu čtení, ne písaře; pak
  patří do `precteno.tsv` nové, lepší čtení zápisu, ne výklad.
- **Původní čtení se nemění.** Kdo s výkladem nesouhlasí, přidá vlastní řádek.
- Přidává se nástrojem, který řádek před zápisem zkontroluje:

      python tools/vyklad.py <archiv>/<kniha> <snimek> <datum> "<udaj>" "<napsano>" "<spravne>" \
          --doklad "<archiv>/<kniha>/<snimek> <datum> (popis)" --kdo "Jan Novák 2026-11-05" [--jistota střední]
