# Jak přidat knihu přes PERO OCR

[PERO OCR](https://pero-ocr.fit.vutbr.cz) (FIT VUT Brno) převede ručně psanou knihu na strojový text zdarma. Text má
chyby, ale stačí jako vyhledávač: hledá se volně (`tools/hledej.py`) a sken se čte jen tam, kde je zásah. Potřebuješ
vlastní účet v PERO; všechno níže běží v prohlížeči přihlášeném do PERO.

## 1. Skeny

| archiv | jak k obrázkům |
|---|---|
| Porta fontium (SOA Plzeň) | přímo z prohlížeče (archiv povoluje CORS): adresy `iipsrv.fcgi?FIF=…&WID=4000&CVT=jpeg`, seznam snímků dá `tools/scan/pfl.py` |
| Acta Publica (MZA Brno) | přímo z prohlížeče: `python -I tools/scan/mza.py pero <id> <a-b> <prefix> [sirka]` vypíše `[[soubor, url], …]` |
| VČA – SOA Zámrsk | na disk: `python -I tools/scan/vcakniha.py <kód> <sign> <složka> <prefix>` (celá kniha, šedotónově, 2400 px) |
| zayt.org (Národní archiv) | na disk po stranách: `tools/scan/zayt.py`, oříznout na knihu |
| eBadatelna SOA Praha | na disk: `tools/scan/ebget.py` |
| DigiArchiv SOA Třeboň | nestahovat a nepouštět do OCR: podmínky DigiArchivu povolují snímky jen prohlížet online (výjimkou je vestavěný export jednotlivých snímků pro registrovaného uživatele, ne hromadně) – zápisy číst ručně v prohlížeči |
| ZA Opava (digi.archives.cz) | katalog je za ochranou proti robotům: cesty ke snímkům v prohlížeči přes `tools/pero/zaopava.js`, obrázky pak na disk `tools/scan/zaopava.py` |

Všechno stahování jde přes `tools/scan/slusne.py` (sdílený limit; archivy za rychlé dávky blokují IP). Ve stránce PERO
stahuje `nahrajZUrl()` nejvýš 5 obrázků za sekundu.

Svisle psané tabulky (např. židovské matriky 1840–1870) před OCR otoč o 90° po směru hodinových ručiček
(`PIL: im.rotate(-90, expand=True)`) a pojmenuj `<prefix>_NNNN-r.jpg`; jinak PERO přečte jen tištěné záhlaví. Vždy
nejdřív zkontroluj náhled jednoho souboru. Číslo v názvu souboru je číslo snímku na portálu (u Porta fontium ×10).

## 2. Dokument v PERO a nahrání

1. `https://pero-ocr.fit.vutbr.cz/document/new_document` → název → Create.
2. Na stránce `upload_images_to_document/<dokument>` vlož do konzole `tools/pero/pero.js` a:
   - z archivu s CORS: `await nahrajZUrl(<výstup mza.py pero>)`;
   - z disku: `pripravNahravani()` a do nového vstupu vlevo nahoře vybírej soubory nebo balíky
     z `python -I tools/pero/balik.py <složka>` (balík ≤ 9,4 MB – nástroje typu Claude in Chrome přenesou nejvýš 10 MB
     na jedno nahrání).
3. Než stránku opustíš, počkej, až nahrávání doběhne (`Dropzone.instances[0].getUploadingFiles().length == 0`).

## 3. Rozbor rozložení a OCR

1. `/layout_analysis/select_layout/<dokument>` → **Handwritten layout** → Submit. Rozbor po OCR znovu spustit nejde
   (pak nový dokument).
2. Po dokončení `/ocr/select_ocr/<dokument>`: řádky (`baseline_id`) **Universal**; OCR **Kurrent (German, Czech)**
   pro kurent (německé i české zápisy), **Czech Handwritten** pro latinku (latina, čeština 2. pol. 19. stol.); jazykový
   model NONE. Handwritten layout najde jen oblasti, řádky hledá až baseline model: bez něj OCR skončí „OCR completed“
   s nulou řádků a dokument je třeba nahrát znovu.
3. Stav je v `/document/documents`. Doba závisí na vytížení serveru: obvykle minuty až desítky minut na stovky stran.

## 4. Export a import do indexu

1. Malý dokument: `https://pero-ocr.fit.vutbr.cz/document/download_document_pages/<dokument>`. Velký (stovky stran,
   PERO vrací 504): v konzoli `await exportuj("<dokument>", "<název>")`, kliknout na žlutý odkaz a stažený
   `<název>.pagexml.txt` zabalit do `<název>.pagexml.zip`.
2. Popis exportu patří do `knihy/<archiv>/<kniha>/kniha.yaml` (do kódu se nesahá, pull request pak mění jen data):

   ```yaml
   archiv: "vca"
   kniha: "sign-532"
   nazev: "Uhersko O 1782–1853, sign. 532"
   url: "https://aron.vychodoceskearchivy.cz/apu/…"
   import:
     prefix: "uhersko532"   # název obrázku před „_<číslo>“; prázdný, když je v exportu jen tato kniha
     delitel: 1             # snímek = číslo souboru // delitel (Porta fontium 10, soubory po jedné 1)
   ocr:
   - soubor: "ocr-pero.tsv"
     nastroj: "PERO OCR (pero-ocr.fit.vutbr.cz)"
     dokument: "<id dokumentu v PERO>"
     model: "Kurrent (German, Czech)"
     datum: "2026-11-13"
     export: "uhersko-o-532.pagexml.zip"
   ```

   Export pro víc knih: každá kniha má svůj `kniha.yaml` se stejným `export` a svým `prefix`.
3. `python tools/pero_import.py <název>.pagexml.zip` → `knihy/<archiv>/<kniha>/ocr-pero.tsv` a `stranky.tsv`;
   import doplní do položky `ocr` snímky, počty stran a řádků. Jiný model nebo nástroj (druhé čtení téže knihy)
   dostane vlastní položku v `ocr` se `soubor: "ocr-<cteni>.tsv"`; stávající čtení zůstane. Export PAGE XML
   z Transkribusu nebo ScribbleSense se importuje stejně; když míchá víc modelů, rozliší je `model_id`.

## 5. Hledání a čtení

- `python tools/hledej.py <slovo> --maxd 2` – volné hledání ve strojovém textu (vzácná příjmení PERO komolí).
- Zásah ověř na skenu; přečtený zápis zapiš celý do `precteno.tsv` (i když se netýká tvé rodiny – ušetří to práci
  dalším), opravu strojového čtení přes `tools/opravy.py`.
- Celé knihy očima nelistuj: na to je PERO. Prázdný výsledek hledání nepřítomnost nedokazuje.
