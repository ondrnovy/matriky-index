# Pokyny pro AI agenty (Claude Code, Codex a další)

Pracuješ v klonu veřejného indexu přečtených matrik a dalších pramenů. Index je společný: cílem je, aby každé čtení
skončilo i v původním repozitáři, ne jen v tomto klonu. Postupuj takto.

## Před čtením

- Hledej, jestli už je kniha nebo zápis přečtený: `python tools/hledej.py <slovo> --maxd 1` a [PREHLED.md](PREHLED.md).
  Co v indexu je, znovu nestahuj ani neOCRkuj.
- Skeny stahuj jen přes `tools/scan/` a modul `tools/scan/slusne.py` (sdílený limit dotazů, pauza po 429/503). Vlastní
  skripty volají `slusne.urlopen()` / `slusne.get()`. Archiv, který nestíhá nebo blokuje, nech být
  (`python tools/scan/slusne.py zablokuj <server> <hodin>`); blokaci neobcházej.
- Velké knihy čti nejdřív strojově přes PERO OCR ([PERO.md](PERO.md)) a očima jen zásahy.
- Kde v knize leží který rok, ves nebo rejstřík, může napovědět [Mapa matrik](https://github.com/ondrnovy/mapa-matrik):
  mapa knihy je v poli `mapa` v `kniha.yaml`, rozcestník podle obce na `https://ondrnovy.github.io/mapa-matrik/v1/`.
  Je to pomůcka, ne povinný krok; přečtený zápis patří sem do indexu.

## Zápis

- Každý zápis, který přečteš, přidej jako řádek do `knihy/<archiv>/<kniha>/precteno.tsv` – i když se netýká hledané
  rodiny. Formát a typy (`N`, `O`, `Z`, `P`, `S`, `K`, `J`) jsou v [README](README.md#precteno-tsv--zápisy-přečtené-očima):
  doslovně, nejistá místa `[?]` (v datu ne: `1757-04` bez neznámého dne, nejistotu napiš do `ostatni`), `obec` dnešním
  názvem, `jistota` vysoká/střední/nízká, `cetl` = jméno uživatele (zeptej se ho, jak chce být
  uveden) + id modelu a effort + datum, např. `Jan Novák + claude-opus-5-5/xhigh 2026-11-05`. Effort je v záznamu
  sezení Claude Code (`~/.claude/projects/<projekt>/<sezení>.jsonl`, pole `effort`); samotné „Claude“ kontrola odmítne.
- Nová kniha: `kniha.yaml` s poli `archiv`, `kniha`, `nazev`, `url`, `roky`, `farnost`, `obsah`; `mapa`, pokud knihu má
  Mapa matrik.
- Strojový text z PERO importuj nástrojem `tools/pero_import.py`; popis exportu (`import` s prefixem a dělitelem,
  položka `ocr` s `export`) patří do `kniha.yaml` knihy, kód neměň ([PERO.md](PERO.md)). Čtení jiným nástrojem
  nebo modelem (Transkribus, ScribbleSense) přidej jako další `ocr-<cteni>.tsv` vedle stávajícího, nic nepřepisuj.
- Řádky, které už jsou v `main`, nikdy neměň ani nemaž – cizí ani vlastní. Jiné nebo přesnější čtení = nový řádek
  nebo oprava přes `tools/opravy.py`.
- `PREHLED.md` necommituj; po sloučení ho z dat v `main` přegeneruje GitHub Action.
- Nezapisuj nic mladšího než 100 let (narození, sčítání) nebo 75 let (sňatky, úmrtí) – může jít o žijící lidi.
- Chybu písaře, kterou dokazují jiné zápisy (matka zapsaná jménem babičky, věk o několik let vedle), zapiš nástrojem
  `tools/vyklad.py` do `vyklad.tsv`; vykládaný zápis i doklady musí být v `precteno.tsv`. Jiný výklad (kdo osoba ve
  skutečnosti je, rodokmen uživatele) do indexu nepatří, ani do `osoby` a `ostatni`; skeny ani celé exporty PERO
  necommituj.

## Odeslání

Na konci práce spusť `python tools/kontrola.py`, commitni změny v `knihy/` a **nabídni
uživateli, že výsledek pošleš do původního repozitáře** jako pull request. S jeho souhlasem:

    gh repo fork --remote            # jen poprvé; vytvoří fork a remote „origin“ na něj, původní repo jako „upstream“
    git switch -c cteni-<archiv>-<kniha>
    git push -u origin HEAD
    gh pr create --repo pe-pan/matriky-index --base main --title "<archiv>/<kniha>: <co bylo přečteno>" --body "<shrnutí>"

Do popisu pull requestu napiš: které knihy a snímky, kolik zápisů, čím se četlo (očima, PERO, model), jistotu a
výsledek `tools/kontrola.py`. Kontrola u pull requestu dá štítek `kontrola-chyby` (oprav), `k-posouzeni` (projde
správce, opravovat nic netřeba) nebo `kontrola-ok`. Má-li kniha issue „Čtu: <archiv>/<kniha>“ a pull request ji
dočítá, přidej `Closes #<číslo issue>`; GitHub issue po sloučení zavře sám. Bez souhlasu uživatele nic neodesílej.
Podrobnosti v [CONTRIBUTING.md](CONTRIBUTING.md).
