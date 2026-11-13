"""Converts machine-read text (PAGE XML) into the index layout: knihy/<archiv>/<kniha>/ocr-<cteni>.tsv,
stranky-<cteni>.tsv and the `ocr` list in kniha.yaml.

    python tools/pero_import.py <export.zip> [<export.zip> ...]

The export is PERO's own ZIP (`/document/download_document_pages/<id>`: PAGE XML + TXT per page), a `*.pagexml.zip`
bundle assembled in the browser ("### PAGE <id>" followed by the page's PAGE XML) or any other ZIP of PAGE XML files
(Transkribus, ScribbleSense). Only the text of each line, its bounding box and confidence are kept.
Every reading (one tool and model) has its own pair of files, so several readings of a book stand side by side and
none replaces another: PERO's reading is ocr-pero.tsv with stranky.tsv, any other one ocr-<cteni>.tsv with
stranky-<cteni>.tsv. A reading made in parts (several documents) is imported by passing all its exports in one call;
its files are rewritten as a whole, so an export left out drops its pages. A new book takes its kniha.yaml from BOOKS;
an existing kniha.yaml keeps all its fields and only its `ocr` entries for the imported reading are replaced.
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
PF = "https://www.portafontium.eu/register/soap-pn/"

# prefix: the part of the image file name before "_<number>"; delitel: file number // delitel = snímek on the portal.
BOOKS = {
    "dnesice-01": dict(archiv="portafontium", nazev="Dnešice 01", farnost="Dnešice", roky="1685–1735",
                       obsah="N 1685–1735 (snímky 3–151), O 1685–1735 (152–192), Z 1685–1735 (193–247, neOCRováno)",
                       url=PF + "dnesice-01", prefix="dnesice-01"),
    "dnesice-02": dict(archiv="portafontium", nazev="Dnešice 02", farnost="Dnešice", roky="1735–1770",
                       obsah="OCR jen snímky 55–75 (N 1746–1752) a 162–173 (O 1735–1744) – test přesnosti",
                       url=PF + "dnesice-02", prefix="dnesice-02"),
    "prestice-02": dict(archiv="portafontium", nazev="Přeštice 02", farnost="Přeštice", roky="1722–1756",
                        obsah="NOZ 1722–1756; OCR jen N soubory 1580–2520 a 3670–3810 (asi 1743–1756) a O 3300–3620 (asi 1743–1/1756); "
                              "snímek = číslo souboru // 10",
                        url=PF + "prestice-02", prefix="prestice-02"),
    "prestice-38": dict(archiv="portafontium", nazev="Přeštice 38", farnost="Přeštice", roky="",
                        obsah="rejstřík (index); OCR téměř prázdné (modré sloupce); snímek = číslo souboru // 10",
                        url=PF + "prestice-38", prefix="prestice-38"),
    "merklin-30": dict(archiv="portafontium", nazev="Merklín 30", farnost="Merklín", roky="",
                       obsah="rejstřík (index) N po písmenech, sloupce datum | jméno | ves | strana; snímek = číslo souboru // 10",
                       url=PF + "merklin-30", prefix="merklin-30"),
    "chotesov-29": dict(archiv="portafontium", nazev="Chotěšov 29", farnost="Chotěšov", roky="",
                        obsah="rejstřík (index); snímek = číslo souboru // 10",
                        url=PF + "chotesov-29", prefix="chotesov-29"),
    "dolni-lukavice-01": dict(archiv="portafontium", nazev="Dolní Lukavice 01", farnost="Dolní Lukavice", roky="1682–1765",
                              obsah="N 1682–1765 (snímky 3–370); soubor = snímek×10+1 (354–358: +2)",
                              url=PF + "dolni-lukavice-01", prefix="dolni-lukavice-01"),
    "velky-bor-01": dict(archiv="portafontium", nazev="Velký Bor 01", farnost="Velký Bor", roky="1707–1754",
                         obsah="N 1707–1753 (snímky 2–180), O 1708–1754 (181–228); snímek 135 na serveru prázdný",
                         url=PF + "velky-bor-01", prefix="velky-bor-01"),
    "velky-bor-02": dict(archiv="portafontium", nazev="Velký Bor 02", farnost="Velký Bor", roky="1746–1771",
                         obsah="N 1746–1771 (snímky 4–163); snímek 134 na serveru prázdný",
                         url=PF + "velky-bor-02", prefix="velky-bor-02"),
    "velky-bor-08": dict(archiv="portafontium", nazev="Velký Bor 08", farnost="Velký Bor", roky="1746–1771",
                         obsah="O 1746–1771 (snímky 2–67), řazeno podle obce nevěsty", url=PF + "velky-bor-08",
                         prefix="velky-bor-08"),
    "velky-bor-11": dict(archiv="portafontium", nazev="Velký Bor 11", farnost="Velký Bor", roky="1746–1771",
                         obsah="Z 1746–1771 (snímky 3–89)", url=PF + "velky-bor-11", prefix="velky-bor-11"),
    "maly-bor-05": dict(archiv="portafontium", nazev="Malý Bor 05", farnost="Malý Bor", roky="1745–1763",
                        obsah="N 1745–1763 (snímky 3–99), O (100–141), Z (142–176); navíc soubor 1205-o",
                        url=PF + "maly-bor-05", prefix="maly-bor-05"),
    "maly-bor-02": dict(archiv="portafontium", nazev="Malý Bor 02", farnost="Malý Bor", roky="1670–1703",
                       obsah="N, O, Z 1670–1703 (209 souborů: N přípona -n, O soubory 1340–1820, Z -z); OCR jen oddíl O; "
                             "snímek = číslo souboru Porta fontium (v precteno.tsv s příponou, např. 0100-o)",
                       url=PF + "maly-bor-02", prefix="maly-bor-02", delitel=1,
                       poznamka="zápisy přečtené při práci na rodokmenu; jen vybrané zápisy, ne celá kniha"),
    "maly-bor-03": dict(archiv="portafontium", nazev="Malý Bor 03", farnost="Malý Bor", roky="1704–1726",
                        obsah="N 1704–1726 (snímky 3–69), O (70–85), Z (86–100)", url=PF + "maly-bor-03",
                        prefix="maly-bor-03"),
    "horazdovice-05": dict(archiv="portafontium", nazev="Horažďovice 05", farnost="Horažďovice", roky="1699–1747",
                           obsah="OCR jen N 1699–1747 (snímky 4–184 a 254–267); Z (185–252) a O (269–322) bez OCR",
                           url=PF + "horazdovice-05", prefix="horazdovice-05"),
    "horazdovice-05-zo": dict(archiv="portafontium", nazev="Horažďovice 05 – zemřelí a oddaní", farnost="Horažďovice",
                              roky="1699–1747", obsah="Z (snímky 185–252) a O (269–322); oddíl N je v horazdovice-05",
                              url=PF + "horazdovice-05", prefix="horazdovice-05"),
    "kasejovice-03": dict(archiv="portafontium", nazev="Kasejovice 03",
                          farnost="Kasejovice (Kasejovice, Hradiště, Řesanice, Předmíř, Mětly, Újezd, Chlumek …)",
                          roky="1667–1689",
                          obsah="N 1667–1676 (snímky 3–44), O 1667–1676 (45–57), N 1677–1689 (58–108), O 1677–1689 (109–126), "
                                "Z 1677–1689 (128–142); OCR jen N 1667–1676 a Z 1677–1689",
                          url=PF + "kasejovice-03", prefix="kasejovice-03",
                          poznamka="zápisy přečtené očima: N 0030–0440 (1667–1676) a 0580–1080 (1677–1689), O 0450–0570 a 1090–1260 "
                                   "(1667–1689); "
                                   "příjmení většinou čtena ze snímků 1600 px, proto nízká jistota"),
    "kasejovice-05": dict(archiv="portafontium", nazev="Kasejovice 05", farnost="Kasejovice", roky="1690–1747",
                          obsah="O 1690–1747 (snímky 3–210); snímek 3 = str. 54–55 (1704–1705)",
                          url=PF + "kasejovice-05", prefix="kasejovice-05"),
    "cizkov-01": dict(archiv="portafontium", nazev="Čížkov 01", farnost="Čížkov", roky="1701–1720",
                      obsah="N 1701–1720 (soubory 0031–0491), O (0501–0621); OCR jen N a O; snímek = číslo souboru // 10",
                      url=PF + "cizkov-01", prefix="cizkov-01"),
    "blovice-02": dict(archiv="portafontium", nazev="Blovice 02", farnost="Blovice", roky="1688–1720",
                       obsah="N 1688–1720 (snímky 3–137)", url=PF + "blovice-02", prefix="blovice-02"),
    "zinkovy-02": dict(archiv="portafontium", nazev="Žinkovy 02", farnost="Žinkovy", roky="1683–1715",
                       obsah="N (snímky 4–128), O (129–155), Z (156–167); OCR jen N a O", url=PF + "zinkovy-02",
                       prefix="zinkovy-02"),
    "kasejovice-07": dict(archiv="portafontium", nazev="Kasejovice 07", farnost="Kasejovice", roky="1690–1744",
                          obsah="Z 1690–1744 (snímky 3–219); snímek 3 = str. 52–53",
                          url=PF + "kasejovice-07", prefix="kasejovice-07"),
    "horazdovice-05-kurrent": dict(archiv="portafontium", nazev="Horažďovice 05 (druhé OCR modelem Kurrent)",
                                   farnost="Horažďovice", roky="1737–1747",
                                   obsah="N 1737–1747 (snímky 133–184 a 254–267) znovu modelem Kurrent – česká kurzíva; "
                                         "celá kniha modelem Czech Handwritten je v horazdovice-05",
                                   url=PF + "horazdovice-05", prefix="horazdovice-05"),
    "vs-horazdovice-k1563": dict(archiv="portafontium", nazev="Vs Horažďovice K 1563 – kniha purkrechtní rychty Pačejovické",
                                 farnost="Malý Bor, Kvasňovice (Olšany, Pačejov, Týřovice, Velešice)", roky="1726–1817",
                                 obsah="pozemková kniha; OCR celé knihy kromě souboru 3740; soubor vs-horazdovice-k1563_NNNN, "
                                       "snímek = NNNN/10", url="https://www.portafontium.eu/amtsbuch/soap-pn/vs-horazdovice/k1563",
                                 prefix="vs-horazdovice-k1563", druh="pozemková kniha"),
    "maly-bor-06": dict(archiv="portafontium", nazev="Malý Bor 06", farnost="Malý Bor", roky="1764–1784",
                        obsah="N (snímky 5–95), O od 1764 (96–129), Z (130–187); latinsky", url=PF + "maly-bor-06",
                        prefix="maly-bor-06"),
    "maly-bor-04": dict(archiv="portafontium", nazev="Malý Bor 04", farnost="Malý Bor", roky="1727–1744",
                        obsah="N 1727–1744 (snímky 3–78, mezi nimi listy x; na snímku 72 i oddaní 1728), O (79–93, od 9/1735), Z (94–118)",
                        url=PF + "maly-bor-04", prefix="maly-bor-04"),
    "cernosin-03": dict(archiv="portafontium", nazev="Černošín 03", farnost="Černošín", roky="1731–1758",
                        obsah="německy a latinsky; podle nadpisů ve strojovém textu: N 1731–1758 (asi snímky 3–78, 1756 ≈ 69, 1758 ≈ 74), O (asi 78–108, 1751 ≈ 101), abecední rejstřík (109–125), Z 1731–1758 (126–165), biřmovaní 1751 (166); snímek = číslo souboru // 10",
                        url=PF + "cernosin-03", prefix="cernosin-03"),
    "kvasnovice-01": dict(archiv="portafontium", nazev="Kvasňovice 01", farnost="Kvasňovice", roky="1738–1765",
                          obsah="N 1738–1765 (snímky 3–62), Z (62–105), O 1738–1765 (106–127); česky, od asi 1763 latinsky",
                          url=PF + "kvasnovice-01", prefix="kvasnovice-01"),
    "kvasnovice-05": dict(archiv="portafontium", nazev="Kvasňovice 05", farnost="Kvasňovice", roky="1784–",
                          obsah="Z od 1784 (snímky 3–128, 37 a 52 chybí); česky, tabulky", url=PF + "kvasnovice-05",
                          prefix="kvasnovice-05"),
    "kvasnovice-02": dict(archiv="portafontium", nazev="Kvasňovice 02", farnost="Kvasňovice", roky="1766–1793",
                          obsah="N 1766–1793 (snímky 3–138, 240–244), Z (139–203, snímek 177 chybí), O (204–239); latinsky",
                          url=PF + "kvasnovice-02", prefix="kvasnovice-02"),
    "6568": dict(archiv="soapraha", nazev="Kněževes 03 (eBadatelna 6568)", farnost="Kněževes", roky="1735–1810",
                 obsah="OCR snímky 84–125 (O 1761–1810); soubor = číslo snímku v eBadatelně",
                 url="https://ebadatelna.soapraha.cz/d/6568/", prefix="", delitel=1),
    "o-235": dict(archiv="zayt", nazev="Hrochův Týnec, židovská kontrolní matrika O (NA HBMa inv. 235)",
                  farnost="Hrochův Týnec", roky="1839–1889",
                  obsah="OCR snímky 24–38 (O asi 1846–1856); soubor = snímek; zápisy jsou psané svisle, OCR je z obrázků "
                        "otočených o 90° po směru hodinových ručiček (soubor -r)",
                  url="https://zayt.org/collections/jewish-control-registers-1780-1911/o-235", prefix="o235", delitel=1),
    "o-2434": dict(archiv="zayt", nazev="Zájezdec, židovská matrika O (NA HBMa inv. 2434)", farnost="Zájezdec",
                   roky="1839, 1841–1868",
                   obsah="OCR snímky 22–34; soubor = snímek; zápisy jsou psané svisle, OCR je z obrázků otočených o 90° "
                         "po směru hodinových ručiček (soubor -r)",
                   url="https://zayt.org/collections/jewish-registers-1784-1949/o-2434", prefix="o2434", delitel=1),
    "noz-372": dict(archiv="zayt", nazev="Kostelec nad Černými lesy, židovská kontrolní matrika NOZ (NA HBMa inv. 372)",
                    farnost="Kostelec nad Černými lesy", roky="1840–1862",
                    obsah="N 1840–1862 fol. 1–10 (fol. 9 = sn. 11, fol. 10 = sn. 12), O 1840–1862 fol. 17–19 = sn. 13–15 "
                          "(posty 1–19), Z 1840–1862 fol. 24–30 = sn. 16–22, společný rejstřík N+O+Z (folio/post) pag. "
                          "40–46 = sn. 23–29, sn. 30 závěrečná doložka; OCR snímky 15–31; soubor = snímek",
                    url="https://zayt.org/collections/jewish-control-registers-1780-1911/noz-372", prefix="noz372",
                    delitel=1),
    "noz-371": dict(archiv="zayt", nazev="Kostelec nad Černými lesy, židovská kontrolní matrika NOZ (NA inv. 371)",
                    farnost="Kostelec nad Černými lesy", roky="1822–1839",
                    obsah="O 1822–1839, N 1833–1839, Z 1827–1839 (11 snímků); OCR snímky 3–9 z polovičního rozlišení; soubor = snímek",
                    url="https://zayt.org/collections/jewish-control-registers-1780-1911/noz-371", prefix="noz371", delitel=1),
    "noz-955": dict(archiv="zayt", nazev="Uhlířské Janovice, židovská kontrolní matrika NOZ (NA inv. 955)",
                    farnost="Uhlířské Janovice", roky="1800–1839",
                    obsah="N 1804–1839, O 1800/1827–1838, Z 1804–1839 (19 snímků); OCR snímky 3–18 z polovičního rozlišení; soubor = snímek",
                    url="https://zayt.org/collections/jewish-control-registers-1780-1911/noz-955", prefix="noz955", delitel=1),
    "n-2264": dict(archiv="zayt", nazev="Uhlířské Janovice, židovská matrika N 1808–1839 (NA inv. 2264)",
                   farnost="Uhlířské Janovice", roky="1808–1839",
                   obsah="N 1808–1839 (41 snímků; rejstřík sn. 5–12, popis rodin 1811 sn. 16–21); OCR snímky 16–21, 24–29, 32–33, "
                         "35–38 z polovičního rozlišení; soubor = snímek",
                   url="https://zayt.org/collections/jewish-registers-1784-1949/n-2264", prefix="n2264", delitel=1),
    "noz-536": dict(archiv="zayt", nazev="Nebužely, židovská kontrolní matrika NOZ (NA inv. 536)",
                    farnost="Nebužely (panství Řepín)", roky="1778–1864",
                    obsah="N 1778–1862, O 1839/1850, Z 1831–1864 (19 snímků); OCR snímky 4–17 z polovičního rozlišení; soubor = snímek",
                    url="https://zayt.org/collections/jewish-control-registers-1780-1911/noz-536", prefix="noz536", delitel=1),
    "noz-535": dict(archiv="zayt", nazev="Nebovidy, židovská kontrolní matrika NOZ (NA inv. 535)",
                    farnost="Nebovidy (Kolín)", roky="1788–1863",
                    obsah="N 1788–1860, O 1824–1857, Z 1829–1863 (31 snímků); OCR snímky 4–12, 14–15, 17–29 z polovičního rozlišení; "
                          "soubor = snímek",
                    url="https://zayt.org/collections/jewish-control-registers-1780-1911/noz-535", prefix="noz535", delitel=1),
    "z-409": dict(archiv="zayt", nazev="Heřmanův Městec, židovská matrika Z 1875–1944, duplikát (NA inv. 409)",
                  farnost="Heřmanův Městec (rabinát; Hroubovice, Chrast …)", roky="1875–1944",
                  obsah="Z 1875–1944; OCR snímky 45–95 (asi 1892–1914), skeny poloviční rozlišení, otočené (přípona -r); soubor = snímek",
                  url="https://zayt.org/collections/jewish-registers-1784-1949/z-409", prefix="z409", delitel=1),
    "n-822": dict(archiv="zayt", nazev="Kolín, židovská matrika N 1822–1839 (NA inv. 822)", farnost="Kolín", roky="1822–1839",
                  obsah="N 1822–1839 bez rejstříku (sn. 3 = 1822, 7 = 1823, 10 = 1824, 17 = 1825, 18–21 = 1826, 24 = 1827); OCR snímky 3–24 "
                        "z polovičního rozlišení; soubor = snímek", url="https://zayt.org/collections/jewish-registers-1784-1949/n-822", prefix="n822", delitel=1),
    "n-821": dict(archiv="zayt", nazev="Kolín, židovská matrika N 1788–1821 (NA inv. 821)", farnost="Kolín", roky="1788–1821",
                  obsah="N 1788–1821 (sn. 82 = 1818, 91 = 1819, 93 = 1820, 96–101 = 1821); OCR snímky 68–101 z polovičního rozlišení; "
                        "soubor = snímek", url="https://zayt.org/collections/jewish-registers-1784-1949/n-821", prefix="n821", delitel=1),
    "o-406": dict(archiv="zayt", nazev="Heřmanův Městec, židovská matrika O (NA inv. 406), duplikát 1839–1850",
                  farnost="Heřmanův Městec", roky="1839–1850",
                  obsah="OCR snímky 4–34 (O 1839–1850; snímek 11 se nestáhl); soubor = snímek; zápisy svisle, OCR z obrázků "
                        "oříznutých na knihu a otočených o 90° po směru hodinových ručiček (soubor -r)",
                  url="https://zayt.org/collections/jewish-registers-1784-1949/o-406", prefix="o406", delitel=1),
    "sign-26-1": dict(archiv="vca", nazev="Dobruška N 1799–1806 a Z 1799–1806, sign. 26-1 (kód RRGJJKAQ)",
                      farnost="Dobruška (Pulice, Pohoří …)", roky="1799–1806",
                      obsah="fol. = snímek + 2 (sn. 45 = fol. 47, XI–XII 1799); OCR snímky 115–189 (úmrtní oddíl, bez rejstříku); "
                            "soubor = snímek; šedotónové JPEG 4078 px",
                      url="https://storage.vychodoceskearchivy.cz/matriky/R/CZ_215000010_00190_RRGJJKAQ_sign-26-1.zip", prefix="dob261", delitel=1),
    "sign-26-12": dict(archiv="vca", nazev="Dobruška Z vesnice 1806–1843, sign. 26-12 (kód 3CF3NFID)",
                       farnost="Dobruška (vesnice)", roky="1806–1843",
                       obsah="po obcích; OCR snímky 74–87 (oddíl Pulice sn. 76–85, pag. 198–217); soubor = snímek; "
                             "šedotónové JPEG 4078 px",
                       url="https://storage.vychodoceskearchivy.cz/matriky/3/CZ_215000010_00190_3CF3NFID_sign-26-12.zip", prefix="dob2612", delitel=1),
    "sign-532": dict(archiv="vca", nazev="Uhersko O 1782–1853, sign. 532 (kód PTMXFXYU)",
                     farnost="Uhersko (Uhersko, Trusnov, Opočno, Franclina; Radhošť a Jaroslav 1782–1784)", roky="10/1782–11/1853",
                     obsah="O po obcích (Uhersko, Opočno, Trusnov, Franclina); snímky 1–114; soubor = snímek; "
                           "OCR ze šedotónových JPEG 2400 px",
                     url="https://aron.vychodoceskearchivy.cz/apu/725df1cf-5048-422a-87c4-e2ca07dde72a", prefix="uhersko532",
                     delitel=1),
    "sign-20-4": dict(archiv="vca", nazev="Červený Kostelec N, Z, O 1785–1814, sign. 20-4 (kód DTDAV6LU)",
                      farnost="Červený Kostelec", roky="1785–1814",
                      obsah="N, Z, O 1785–1814 po obcích; snímky 1–149; soubor = snímek; OCR ze šedotónových JPEG 2400 px",
                      url="https://aron.vychodoceskearchivy.cz/apu/df9d1ae5-8641-4ce5-83f6-c5ff756dc1d7", prefix="ckostelec204",
                      delitel=1),
    "sign-1309": dict(archiv="vca", nazev="Litomyšl N 1850–1857, sign. 1309 (kód WRH6GG3Q)",
                      farnost="Litomyšl", roky="10/1850–1857",
                      obsah="N Litomyšl město a předměstí (Dolní a Horní předměstí, Lány, Zahájí, Záhradí); snímky 1–395; "
                            "soubor = snímek; OCR ze šedotónových JPEG 2400 px",
                      url="https://aron.vychodoceskearchivy.cz/apu/9340aa8e-bfe5-4c80-af51-9adf97017290", prefix="lit1309",
                      delitel=1),
    "sign-7492": dict(archiv="vca", nazev="Litomyšl, index Z 1864–1906, sign. 7492 (kód LRIQXP2E)", farnost="Litomyšl",
                      roky="1864–1906",
                      obsah="rejstřík zemřelých celé farnosti (město, předměstí i vesnice); snímky 1–229; soubor = snímek; "
                            "OCR ze šedotónových JPEG 2400 px",
                      url="https://aron.vychodoceskearchivy.cz/apu/06a51ee1-4891-4871-b054-cd9370536c0b", prefix="lit7492",
                      delitel=1),
    "1215ac03": dict(archiv="vca", nazev="Sbírka matrik Východočeského kraje, sign.: 120-1 (poř.č. 8227), 1723-1797 – Opočno NOZ "
                                         "(Opočno, Podchlumí, Pohoří, Puličky, Semechnice, Trnov)",
                     farnost="Opočno", roky="1723–1797",
                     obsah="N 10.1723–3.1776 chronologicky pro všechny obce (bez oddílů, obec v levém sloupci „dies et locus "
                           "originis“; bez rejstříku): snímek 100 = pag. 188–189, 114 = pag. 216–217 (leden 1749), 117 = začátek "
                           "1750, 123 = začátek 1752, 126 = začátek 1753, 144 = září–říjen 1755, 145 = listopad 1755 – leden 1756, "
                           "149 = podzim 1756 – leden 1757, 150 = 1757 (leden–březen), 151 = duben–červenec 1757, "
                           "152 = srpen–listopad 1757, 153 = listopad 1757 – leden 1758, 154 = leden–březen 1758, "
                           "155 = březen–červen 1758, 156 = červenec–listopad 1758, 157 = listopad 1758 – únor 1759, "
                           "158 = únor–březen 1759, 160 = červenec–srpen 1759, 170 = srpen–září 1761, 206 = květen–červen 1769; Z od asi sn. 240 "
                           "(1760–1761; 306 = asi 1765), O od asi sn. 400 (1759 = sn. 431, 1773 = sn. 463, 1792 = sn. 485); snímek = pořadí snímku v ARON",
                     url="https://aron.vychodoceskearchivy.cz/apu/1215ac03-cbfc-4b1c-9f7f-0a0ebf8f4f45", prefix="opocno1201",
                     delitel=1,
                     poznamka="OCR celé knihy (sn. 1–490) ze šedotónových JPEG 2400 px; soubor = snímek; zip v ARON má 490 "
                              "snímků (ARON počítá 3 soubory na snímek); N 1723–1747 česky, od 1748 latinsky, od asi 1770 tabulky"),
    "c3113199": dict(archiv="vca", nazev="Sbírka matrik Východočeského kraje, sign.: 24-7 (poř.č. 1637), 6.1784-1849 – Deštné v "
                                         "Orlických horách O (Deštné, Dříš, Kout, Paseka, Pastviny, Víska, Zákoutí)",
                     farnost="Deštné v Orlických horách", roky="1784–1849",
                     obsah="O 6/1784–1849, německy; snímky 1–71; soubor = snímek; OCR ze šedotónových JPEG 2400 px",
                     url="https://aron.vychodoceskearchivy.cz/apu/c3113199-3a1e-42e1-9ea0-742a7f22d89e", prefix="destne247", delitel=1),
    "0484f35a": dict(archiv="vca", nazev="Sbírka matrik Východočeského kraje, sign.: 138-11 (poř.č. 9465), 5.1812-1857 – Rokytnice "
                                         "v Orlických horách O",
                     farnost="Rokytnice v Orlických horách", roky="1812–1857",
                     obsah="O 5/1812–1857 (Rokytnice, Hanička, Panské Pole, Julinčino Údolí, Údolíčko, Rýnek, Václavova Seč), "
                           "německy; snímky 1–171; soubor = snímek; OCR ze šedotónových JPEG 2400 px",
                     url="https://aron.vychodoceskearchivy.cz/apu/0484f35a-faa1-428b-b53c-b3fbe9171eba", prefix="rokytnice13811", delitel=1),
    "f7a85f10": dict(archiv="vca", nazev="Sbírka matrik Východočeského kraje, sign.: 171-2797 (poř.č. 12181), 1784-1837 – Velký "
                                         "Uhřínov O",
                     farnost="Velký Uhřínov", roky="1784–1837",
                     obsah="O 1784–1837; snímky 1–39 (sn. 2–24 chronologicky 1784–1837, sn. 25–39 podle letopočtů v OCR znovu 1784–1795 – jiná řada?); soubor = "
                           "snímek; OCR ze šedotónových JPEG 2400 px",
                     url="https://aron.vychodoceskearchivy.cz/apu/f7a85f10-ccc5-41dc-9d4c-b19a8cf97643", prefix="uhrinov1712797", delitel=1),
    "060e88a7": dict(archiv="vca", nazev="Sbírka matrik Východočeského kraje, sign.: 114-7333 (poř.č. 7990), 1642-1905 – Nové Město "
                                         "nad Metují, index O",
                     farnost="Nové Město nad Metují", roky="1642–1905",
                     obsah="rejstřík oddaných celé farnosti po písmenech, v písmeni chronologicky (rok, ženich, obec, nevěsta, "
                           "folio); OCR jen písmeno S (snímky 86–104: S 1700–1842 = sn. 89–93, 1842–1899 = 94–96; Š/Sch dál); "
                           "soubor = snímek; šedotónové JPEG 2400 px",
                     url="https://aron.vychodoceskearchivy.cz/apu/060e88a7-18e2-419a-8e49-b958f7b76396", prefix="nmnm1147333", delitel=1),
    "9634f2ed": dict(archiv="vca", nazev="Sbírka matrik Východočeského kraje, sign.: 24-5 (poř.č. 1630), 5.1784-6.1837 – Deštné "
                                         "v Orlických horách N (Deštné, Dříš, Kout, Paseka, Pastviny, Víska, Zákoutí)",
                     farnost="Deštné v Orlických horách", roky="1784–1837",
                     obsah="N 5/1784–6/1837 německy, tabulkově, chronologicky pro celou farnost (obec ve sloupci data); snímek 84 = "
                           "pag. 158–159 (1810); rejstřík N/Z/O 1784–1835 = sign. 24-9; snímky 1–145; soubor = snímek; OCR ze "
                           "šedotónových JPEG 2400 px – úzké sloupce tabulky čte PERO špatně",
                     url="https://aron.vychodoceskearchivy.cz/apu/9634f2ed-f27b-4902-b935-cc261da19e92", prefix="destne245", delitel=1),
    "ab67b4df": dict(archiv="vca", nazev="Sbírka matrik Východočeského kraje, sign.: 120-11 (poř.č. 8246), 1784-1834",
                     farnost="Opočno", roky="1784–1834",
                     obsah="O a index O, Pohoří, Puličky, Semechnice, Trnov …, tabulkově česky, po obcích (záložky Pohoří, Puličky, "
                           "Semechnice); rejstřík ženichů na konci (sn. 90 L = M); snímky 1–110; soubor = snímek; snímek = pořadí "
                           "snímku v ARON",
                     url="https://aron.vychodoceskearchivy.cz/apu/ab67b4df-8c81-4421-97bc-508551f5366d", prefix="opocno12011", delitel=1,
                     poznamka="OCR celé knihy ze šedotónových JPEG 2400 px; zápisy přečtené očima v precteno.tsv"),
    "1a6d0b5c": dict(archiv="vca", nazev="Sbírka matrik Východočeského kraje, sign.: 2095, 1725-1785 – Choceň NAROZENÝCH",
                     farnost="Choceň", roky="1725–1785",
                     obsah="N farnosti Choceň a filiálek chronologicky (sloupce Locus, Dies, Nomen prolis, Nomina et conditio parentum, "
                           "Levans, Testes, Baptisans), stránkováno (snímek 321 = s. 620–621, 330 = s. 638–639); snímek = pořadí "
                           "snímku v ARON",
                     url="https://aron.vychodoceskearchivy.cz/apu/1a6d0b5c-5f05-41fe-8bc6-27540ddbae5c", prefix="chocen2095", delitel=1,
                     poznamka="OCR jen snímky 270–390 (asi 1752–1766) ze šedotónových JPEG 2400 px; tabulkové sloupce čte PERO špatně; "
                              "jinak jen jednotlivé stránky očima"),
    "8964843b": dict(archiv="vca", nazev="Sbírka matrik Východočeského kraje, sign.: 117-2 (poř.č. 8087), 1771-1787 – Nový Hrádek "
                                         "NZO (farnost Nový Hrádek a filiální obvod Slavoňov)",
                     farnost="Nový Hrádek, Slavoňov", roky="1771–1787",
                     obsah="latinsky; N 1771–1783 asi sn. 5–95 (1778 ≈ sn. 47–52, 1780 ≈ 63–70), N 1784–1787 tabulkově asi sn. 99–140; "
                           "O asi sn. 145–200 (1778 = sn. 165–166); Z asi sn. 201–275; obce filiálky Slavoňov mj. Janov, Ohnišov, "
                           "Bohdašín, Sendraž, Mezilesí; snímky 1–276; soubor = snímek; snímek = pořadí snímku v ARON",
                     url="https://aron.vychodoceskearchivy.cz/apu/8964843b-907d-4651-a5c7-9f15b886fc49", prefix="nh1172", delitel=1,
                     poznamka="OCR celé knihy ze šedotónových JPEG 2400 px; tabulkové sloupce čte PERO špatně; zápisy přečtené "
                              "očima v precteno.tsv"),
    "8df4dc98": dict(archiv="vca", nazev="Sbírka matrik Východočeského kraje, sign.: 117-1 (poř.č. 8086), 1721-1771 – Nový Hrádek "
                                         "NZO (farnost Nový Hrádek a filiální obvod Slavoňov)",
                     farnost="Nový Hrádek, Slavoňov", roky="1721–1771",
                     obsah="latinsky, souvislý text; N 1721–1750 asi sn. 1–99 (1738 ≈ sn. 56, 1747 ≈ 87–89; fol. f ≈ sn. f+5 "
                           "až f+6 P), N 1751–1771 asi sn. 100–193 (1755 ≈ sn. 117–121, 1760 ≈ 140–145, 1765 ≈ 163–166, 1770 ≈ "
                           "186–190); O sn. 199–258 L (1722–1769, 1744–1769 ≈ sn. 220–258), sňatky 1769–1771 vloženy na sn. "
                           "193 R–197 L (fol. 61–64); Z asi sn. 283–318 (1743–1769); 319 snímků; soubor = snímek; snímek = "
                           "pořadí snímku v ARON",
                     url="https://aron.vychodoceskearchivy.cz/apu/8df4dc98-f935-4dda-87d2-15cfcb26dd4a", prefix="nh1171", delitel=1,
                     poznamka="OCR snímků 1–319 ze šedotónových JPEG 2400 px ve dvou dokumentech PERO; zápisy přečtené "
                              "očima v precteno.tsv"),
    "f9ac826b": dict(archiv="vca", nazev="Sbírka matrik Východočeského kraje, sign.: 14-4 (poř.č. 714), 1785-1826 – Bystré O "
                                         "(Bystré, Bačetín, Janov, Kounov, Sudín, Ohnišov)",
                     farnost="Bystré", roky="1785–1826",
                     obsah="O česky, tabulkově, po obcích (každý oddíl chronologicky 1785–1826: asi sn. 3–23, 24–47, 49–73, 74–89, "
                           "92–126; Ohnišov 1824 = sn. 124, Janov 1797 = sn. 51); snímky 1–126; soubor = snímek; snímek = pořadí "
                           "snímku v ARON",
                     url="https://aron.vychodoceskearchivy.cz/apu/f9ac826b-d61c-4270-b416-f20a88bb1417", prefix="by144", delitel=1,
                     poznamka="OCR celé knihy ze šedotónových JPEG 2400 px; úzké sloupce tabulky čte PERO špatně; zápisy přečtené "
                              "očima v precteno.tsv"),
    "o-2741": dict(archiv="zayt", nazev="Praha-Karlín, židovská matrika O 1848–1856 (NA HBMa inv. 2741)",
                   farnost="Karlín (krajský rabín Kouřimska; snoubenci z celého kraje)", roky="1848–1856",
                   obsah="„Trauungs-Matrik“, tištěný formulář přes dvojstranu, 4 posty na stranu (sn. 20 = pag. 18, 1854); "
                         "OCR snímky 3–35; soubor = snímek, obrázek oříznutý na knihu, šedotónový",
                   url="https://zayt.org/collections/jewish-registers-1784-1949/o-2741", prefix="o2741", delitel=1),
    "o-2745": dict(archiv="zayt", nazev="Praha-Libeň, židovská matrika O 1833–1849 (NA HBMa inv. 2745)",
                   farnost="Libeň (snoubenci i z venkova – Přistoupim, Poříčany, Cerhenice aj.)", roky="1833–1849",
                   obsah="ručně linkovaná tabulka přes dvojstranu (sn. 10 = pag. 12–13, rok 1837); OCR snímky 4–17; soubor = "
                         "snímek, obrázek oříznutý na knihu, šedotónový",
                   url="https://zayt.org/collections/jewish-registers-1784-1949/o-2745", prefix="o2745", delitel=1),
    "z-481": dict(archiv="zayt", nazev="Hroubovice (FÚ Luže), židovská kontrolní matrika Z (NA inv. 481)", farnost="Luže",
                  roky="1840–1873", obsah="Z Hroubovice 1840–1873; OCR snímky 3–52; soubor = snímek; oříznuté, šedotónové; "
                                          "sn. 3–11 neotočené, 12–52 otočené o 90° (soubor -r)",
                  url="https://zayt.org/collections/jewish-control-registers-1780-1911/z-481", prefix="z481", delitel=1),
    "su-xiv-5": dict(archiv="zaopava", nazev="Ruda nad Moravou N 1779–1825, ZA Opava, NAD 165, sign. Šu XIV 5 (inv. 7909)",
                     farnost="Ruda nad Moravou (Bartoňov, Bohdíkov, Bušín/Buschin, Hostice, Jakubovice, Olšany, Raškov, Ruda n. M. …)",
                     roky="1779–1825", obsah="OCR snímky 30–95 (asi 1782–1788; str. 1–181 = všechny obce 1779–1788); latinsky; "
                                             "soubor = snímek; obrázky v polovičním rozlišení (1800 px), šedotónové",
                     url="https://digi.archives.cz/da/permalink?xid=be93172a-f13c-102f-8255-0050568c0263",
                     prefix="bohdikov5", delitel=1),
    "su-xiv-4": dict(archiv="zaopava", nazev="Ruda nad Moravou N, O, Z 1772–1778, ZA Opava, NAD 165, sign. Šu XIV 4 (inv. 7908)",
                     farnost="Ruda nad Moravou (Bartoňov, Bohdíkov, Bušín, Hartíkov, Hostice, Jakubovice, Olšany, Raškov …)",
                     roky="1772–1778", obsah="po obcích, u každé N, O, Z (Bušín str. 1–72); OCR snímky 1–177; soubor = snímek; "
                                             "obrázky v polovičním rozlišení, šedotónové",
                     url="https://digi.archives.cz/da/permalink?xid=be9317b6-f13c-102f-8255-0050568c0263", prefix="ruda4", delitel=1),
    "be97d562": dict(archiv="zaopava", nazev="Ruda nad Moravou N, O, Z 1757–1771 s rejstříky N a O (1757–1792), ZA Opava, NAD 165",
                     farnost="Ruda nad Moravou (Bušín, Hostice, Olšany, Dolní Bohdíkov, Klášterec, Vyšehoří, Hartíkov …)",
                     roky="1757–1771", obsah="N str. 1–107, O str. 123–162, Z str. 184–239, rejstříky N a O (do 1792); OCR "
                                             "snímky 1–131 bez sn. 45 (portál nevydal); soubor = snímek; poloviční rozlišení, "
                                             "šedotónové",
                     url="https://digi.archives.cz/da/permalink?xid=be97d562-f13c-102f-8255-0050568c0263", prefix="ruda1757",
                     delitel=1),
    "be9318d8": dict(archiv="zaopava", nazev="Ruda nad Moravou N, Z, O 1701–1757, ZA Opava, NAD 165, sign. Šu XIV 2 (inv. 7906)",
                     farnost="Ruda nad Moravou (Bohdíkov, Bušín, Hartíkov, Hostice, Jakubovice, Janoušov, Klášterec, "
                             "Komňátka, Olšany, Raškov, Štědrákova Lhota, Vyšehoří)",
                     roky="1701–1757", obsah="N 1701–1757 asi sn. 1–249 (sn. 200 = I 1749), O asi sn. 250–363 (sn. 360 = I 1747), Z dál; "
                                             "OCR snímky 1–80 (N 1701–1720), 160–228 (N X 1738 – asi 1757), 250–372 (O 1701–1757) a 373–540 "
                                             "(Z 1701 – asi 1740); soubor = snímek; "
                                             "poloviční rozlišení, šedotónové",
                     url="https://digi.archives.cz/da/permalink?xid=be9318d8-f13c-102f-8255-0050568c0263", prefix="ruda1701",
                     delitel=1),
    "su-xiv-14": dict(archiv="zaopava", nazev="Ruda nad Moravou O 1779–1825, ZA Opava, NAD 165, sign. Šu XIV 14 (inv. 7918)",
                      farnost="Ruda nad Moravou (Bartoňov, Bohdíkov, Bušín, Hostice, Jakubovice, Olšany, Raškov …)",
                      roky="1779–1825", obsah="str. 1–47 = všechny obce 1779–1788, od 1789 po obcích; OCR snímky 1–35 "
                                              "(1779–1788); soubor = snímek; obrázky v polovičním rozlišení, šedotónové",
                      url="https://digi.archives.cz/da/permalink?xid=be9312c0-f13c-102f-8255-0050568c0263", prefix="ruda14", delitel=1),
    "su-xiv-19": dict(archiv="zaopava", nazev="Ruda nad Moravou Z 1779–1825, ZA Opava, NAD 165, sign. Šu XIV 19 (inv. 7923)",
                      farnost="Ruda nad Moravou (Bartoňov, Bohdíkov, Bušín, Hostice, Jakubovice, Olšany, Raškov …)",
                      roky="1779–1825", obsah="str. 1–86 = všechny obce 1779–1788, od 1789 po obcích; OCR snímky 1–302; "
                                              "soubor = snímek; obrázky v polovičním rozlišení, šedotónové",
                      url="https://digi.archives.cz/da/permalink?xid=be930f8c-f13c-102f-8255-0050568c0263", prefix="ruda19", delitel=1),
    "o-830": dict(archiv="zayt", nazev="Kolín, židovská matrika O 1850–1895 s rejstříkem (NA inv. 830)", farnost="Kolín",
                  roky="1850–1895", obsah="OCR snímky 2–78; soubor = snímek; oříznuté, šedotónové, poloviční rozlišení",
                  url="https://zayt.org/collections/jewish-registers-1784-1949/o-830", prefix="o830", delitel=1),
    "noz-530": dict(archiv="zayt", nazev="Hroubovice, židovská matrika N 1874–1895, O 1875–1891, Z 1875–1895 (NA inv. 530)",
                    farnost="Hroubovice", roky="1874–1895",
                    obsah="OCR snímky 2–73; soubor = snímek; oříznuté, šedotónové, poloviční rozlišení",
                    url="https://zayt.org/collections/jewish-registers-1784-1949/noz-530", prefix="noz530", delitel=1),
    "z-236": dict(archiv="zayt", nazev="Hrochův Týnec, židovská kontrolní matrika Z (NA inv. 236)", farnost="Hrochův Týnec",
                  roky="1839–1882", obsah="OCR snímky 41–46 a 51–58 (asi 1855–1857 a 1861–1866); soubor = snímek; zápisy svisle, "
                                          "OCR z oříznutých a otočených obrázků (soubor -r)",
                  url="https://zayt.org/collections/jewish-control-registers-1780-1911/z-236", prefix="z236", delitel=1),
    "noz-726": dict(archiv="zayt", nazev="Přistoupim, židovská kontrolní matrika NOZ (NA inv. 726)", farnost="Přistoupim",
                    roky="1803–1840",
                    obsah="N 1816–1840 s opisy N 1803, 1805, 1808, O 1826–1838, Z 1819–1839, rejstříky; OCR snímky 2–20 "
                          "(1 a 21 desky); soubor = snímek, obrázek oříznutý na knihu",
                    url="https://zayt.org/collections/jewish-control-registers-1780-1911/noz-726", prefix="noz726",
                    delitel=1),
    "noz-727": dict(archiv="zayt", nazev="Přistoupim, židovská kontrolní matrika NOZ (NA inv. 727)", farnost="Přistoupim",
                    roky="1840–1858", obsah="N 1841–1858 s rejstříkem, O 1840–1853, Z 1843–1853; OCR snímky 2–13 (1 a 14 "
                                            "desky); soubor = snímek, obrázek oříznutý na knihu",
                    url="https://zayt.org/collections/jewish-control-registers-1780-1911/noz-727", prefix="noz727",
                    delitel=1),
    "familianti-83": dict(archiv="zayt", nazev="Familiantská kniha Kouřimský kraj HBF IX/IX (Řimovice, Sázava, Kostelec "
                                                "nad Černými lesy)", farnost="panství Kostelec nad Černými lesy",
                          roky="1811–1848", obsah="OCR snímky 21–70 = panství Kostelec nad Černými lesy od fol. 43 (snímek "
                                                  "30 = fol. 60); soubor = snímek",
                          url="https://zayt.org/collections/jewish-familiant-books-1811-1848-redux/83", prefix="fam83",
                          delitel=1),
    "kramerius-1804": dict(archiv="ndk", nazev="Kraméryusowy Cýs. k. Pražské Posstowské Nowiny, ročník 16 (1804)",
                           farnost="celé Čechy (týdeník, Praha)", roky="1804", druh="noviny",
                           obsah="OCR č. 47–52 (24. 11.–29. 12. 1804), str. 185–208; soubor = strana ročníku; IMG_FULL z NDK",
                           url="https://ndk.cz/view/uuid:b1942b3d-435d-11dd-b505-00145e5790ea", prefix="kram1804",
                           delitel=1),
    "kramerius-1805": dict(archiv="ndk", nazev="Kraméryusowy Cýs. k. Pražské Posstowské Nowiny, ročník 17 (1805)",
                           farnost="celé Čechy (týdeník, Praha)", roky="1805", druh="noviny",
                           obsah="OCR č. 1–13 (5. 1.–30. 3. 1805), str. 1–52; soubor = strana ročníku; IMG_FULL z NDK",
                           url="https://ndk.cz/view/uuid:b1942b3e-435d-11dd-b505-00145e5790ea", prefix="kram1805",
                           delitel=1),
}
# export file stem -> (books it contains, PERO document, model, date), or a dict for other tools and settings:
# knihy, cteni (file suffix, default "pero"), nastroj, nastaveni, dokument, model, datum, and for an export that
# mixes models modely = {model id in the PAGE Creator: (cteni, model name)}.
PERO = "PERO OCR (pero-ocr.fit.vutbr.cz)"
PERO_NASTAVENI = "rozbor rozložení Handwritten layout, řádky Universal, jazykový model žádný"
TRANSKRIBUS = "Transkribus (app.transkribus.org), Quick Text Recognition"
TK_MODELY = {"263129": ("transkribus-czech-m1", "Transkribus Czech Handwriting M1 (model 263129)"),
             "341425": ("transkribus-old-czech", "Transkribus Old Czech Handwriting (with spaces) (model 341425)"),
             "35909": ("transkribus-german-hw-m1", "Transkribus German Handwriting M1 (model 35909)"),
             "50870": ("transkribus-german-giant", "The German Giant I (model 50870)")}
EXPORTS = {
    "dnesice-01": (["dnesice-01"], "c1785e53-4a1c-40f7-a924-7d219217bf15", "Kurrent (German, Czech)", "2026-10-19"),
    "dnesice-02-test": (["dnesice-02"], "103bd7f2-529f-455d-b84e-285b8807397a", "Kurrent (German, Czech)", "2026-10-19"),
    "dolni-lukavice-01": (["dolni-lukavice-01"], "f576fcb5-bc48-406e-b75a-5a0a3b1e2d2c", "Kurrent (German, Czech)",
                          "2026-10-19"),
    "velky-bor-01": (["velky-bor-01"], "658b2c64-93b8-43a8-a478-3cfd30f232fa", "Kurrent (German, Czech)", "2026-10-19"),
    "velky-bor-02": (["velky-bor-02"], "ea0f5d04-f694-4607-a7b3-030028813dbf", "Czech Handwritten", "2026-10-21"),
    "velky-bor-08-11": (["velky-bor-08", "velky-bor-11"], "f61096eb-8434-4bf0-8567-7e488a5ad40a", "Czech Handwritten",
                        "2026-10-21"),
    "maly-bor-05": (["maly-bor-05"], "414ba723-3991-4f8a-b1a5-5c2b4e63bf4a", "Czech Handwritten", "2026-10-21"),
    "maly-bor-03": (["maly-bor-03"], "d6e5e828-1460-4523-8ec1-891a6cad4f26", "Czech Handwritten", "2026-10-21"),
    "maly-bor-04": (["maly-bor-04"], "949bb837-fa4e-4144-a503-65ae049bcf1f", "Czech Handwritten", "2026-10-21"),
    "knezeves-03": (["6568"], "fda952f8-d802-487f-b70a-c278de37df0a", "Czech Handwritten", "2026-10-21"),
    "zidovske-o235-o2434-noz372": (["noz-372"], "17f0a0e2-56cb-476e-beb1-667191362e2a",
                                   "Kurrent (German, Czech)", "2026-10-21"),
    "zidovske-o235-o2434-otocene": (["o-235", "o-2434"], "00b4fec1-aa87-4774-92ec-bd38077992e2", "Kurrent (German, Czech)",
                                    "2026-10-21"),
    "pristoupim-noz726-noz727": (["noz-726", "noz-727"], "3ffd9a97-1756-472a-bc3f-84333d8b10fc", "Kurrent (German, Czech)",
                                 "2026-10-21"),
    "hermanuv-mestec-o406-otocene": (["o-406"], "59d2c47d-c079-4cbe-af77-4f405ae9982a", "Kurrent (German, Czech)",
                                     "2026-10-22"),
    "hrochuv-tynec-z236-otocene": (["z-236"], "ac372e5b-9763-46d4-9c58-9d48def1d0cf", "Kurrent (German, Czech)",
                                   "2026-10-22"),
    "familianti-83-kostelec": (["familianti-83"], "8c28db92-6852-49c1-8a02-d9dcb650a12b", "Kurrent (German, Czech)",
                               "2026-10-21"),
    "kvasnovice-02": (["kvasnovice-02"], "039c275f-e042-487c-af86-180ece6ab7e1", "Czech Handwritten", "2026-10-21"),
    "portafontium-cernosin-03": (["cernosin-03"], "43460ced-f268-4f99-a402-52f59d4ecf15", "Kurrent (German, Czech)", "2026-11-12"),
    "portafontium-maly-bor-02-o": (["maly-bor-02"], "2c7d420e-1ffc-4d91-a2a7-5234dcdabe21", "Kurrent (German, Czech)", "2026-11-13"),
    "export_job_31977240": dict(knihy=["horazdovice-05-zo", "1215ac03", "f7a85f10"], nastroj=TRANSKRIBUS,
                                nastaveni="rozbor rozložení automaticky, jazykový model žádný; nahráno 2400 px (Opočno, Uhřínov) a 2600 px šedotónově (Horažďovice)",
                                modely=TK_MODELY),
    "kvasnovice-01": (["kvasnovice-01"], "5c1a99a8-9ce5-4a29-b55e-e421741e0f61", "Kurrent (German, Czech)", "2026-10-21"),
    "kvasnovice-05": (["kvasnovice-05"], "eb1b5565-a613-4f43-9054-284e334056b0", "Kurrent (German, Czech)", "2026-10-22"),
    "maly-bor-06": (["maly-bor-06"], "c118aa96-dcf1-4ad3-97b9-21d1454f0e54", "Czech Handwritten", "2026-10-22"),
    "litomysl-z-index-7492": (["sign-7492"], "7c8f80c2-117d-4ead-bb24-519ac40c2005", "Czech Handwritten", "2026-11-02"),
    "dobruska-26-1-26-12": (["sign-26-1", "sign-26-12"], "6543ac92-3886-4503-b2f3-e973817b2f34", "Kurrent (German, Czech)",
                            "2026-11-02"),
    "litomysl-n-1309": (["sign-1309"], "9cf4c19e-3582-41cf-82c8-c4cb45510542", "Kurrent (German, Czech)", "2026-11-02"),
    "uhersko-o-532": (["sign-532"], "a0371923-62ad-4564-8525-8ba4f08b16f5", "Kurrent (German, Czech)", "2026-11-13"),
    "ckostelec-20-4": (["sign-20-4"], "06ed6490-1c61-4e08-a0c5-550380880a8e", "Kurrent (German, Czech)", "2026-11-13"),
    "kurrent-2741-2745-481": (["o-2741", "o-2745", "z-481"], "8b22ff4d-4bfb-48ce-a789-7644f374dc32",
                              "Kurrent (German, Czech)", "2026-11-02"),
    "bohdikov-su-xiv-5": (["su-xiv-5"], "161c8c33-983b-4c9a-87cd-36473e311b18", "Czech Handwritten", "2026-11-02"),
    "ruda-1757-1771": (["be97d562"], "61da916d-56f4-46e5-b358-2f9080289d2c", "Czech Handwritten", "2026-11-02"),
    "ruda-1701-1757": (["be9318d8"], "59dc2bb6-c7b9-4457-a9a1-4dd2d84eba46, 6e04fb07-1adc-4450-ac97-c3c0d7f458c1, "
                                     "5b1e5314-fc04-48ac-a7d5-fe111c9e8cef, 6323e93c-6924-47eb-9a8a-7ec850109f68",
                       "Czech Handwritten", "2026-11-03"),
    "kasejovice-03-n1667-z1677": (["kasejovice-03"], "9345001a-cea4-433e-a3c7-4e68d4313678", "Kurrent (German, Czech)",
                                  "2026-11-04"),
    "kasejovice-05-o1690-1747": (["kasejovice-05"], "bf7b354b-05a6-45de-b54a-a033d5b780c0", "Kurrent (German, Czech)",
                                 "2026-11-04"),
    "kasejovice-07-z1690-1744": (["kasejovice-07"], "36f52f6b-4218-4534-bc8e-81fd5f392349", "Kurrent (German, Czech)",
                                 "2026-11-04"),
    "cizkov-01-czh": (["cizkov-01"], "126567d4-cec4-41c6-a4aa-54ca8dd468e9", "Czech Handwritten", "2026-11-06"),
    "blovice-02-czh": (["blovice-02"], "53844fe1-8a74-44ce-b6de-9e9e0695ce82", "Czech Handwritten", "2026-11-06"),
    "z9-371-kurrent": (["noz-371"], "cbd6c056-ef2e-4854-98b0-ef8e0b266409", "Kurrent (German, Czech)", "2026-11-06"),
    "z9-955-kurrent": (["noz-955"], "3c9b00c4-748d-413e-9970-1665b5c2aa5f", "Kurrent (German, Czech)", "2026-11-06"),
    "z9-2264-kurrent": (["n-2264"], "13b4c37a-a6dd-4ece-8f92-701a134d5e1d", "Kurrent (German, Czech)", "2026-11-06"),
    "z9-536-kurrent": (["noz-536"], "d0273599-3711-4b2f-b6a7-86f3520258bc", "Kurrent (German, Czech)", "2026-11-06"),
    "z9-535-kurrent": (["noz-535"], "1568011a-e994-44d4-9444-ed481590ced4", "Kurrent (German, Czech)", "2026-11-06"),
    "prestice-02-P8": (["prestice-02"], "e0391f6c-46fc-4e7f-b7fa-7ca74f79baa5", "Czech Handwritten", "2026-11-06"),
    "indexy-prestice38-merklin30-chotesov29-P8": (["prestice-38", "merklin-30", "chotesov-29"],
                                                   "b27e5513-73dd-4f80-87d3-4f36dd2f8102", "Czech Handwritten", "2026-11-06"),
    "h4-z409": (["z-409"], "27a909e4-8cae-417d-ba8b-079219f6d007 (sn. 45–72) + 2e1eda7f-ac6b-42e7-b22b-558556d2e302 (sn. 73–95)",
                "Kurrent (German, Czech)", "2026-11-06"),
    "z10-822": (["n-822"], "8ae74665-b573-4324-97ed-3d47d157f312 (sn. 3–10) + 3df067ca-c307-4e70-ba49-6dc97a957640 (sn. 11–24)",
                "Kurrent (German, Czech)", "2026-11-06"),
    "z10-821": (["n-821"], "66a2140f-552f-4972-b395-4d1101451016 (sn. 68–77) + e23ff42b-1cfd-46b9-84f1-3e5a41cb58a7 (sn. 78–101)",
                "Kurrent (German, Czech)", "2026-11-06"),
    "zinkovy-02-czh": (["zinkovy-02"], "ee840a16-1ae5-4bb0-ac76-5a9217a1edbd", "Czech Handwritten", "2026-11-06"),
    "vca-opocno-120-1": (["1215ac03"], "cf09cad5-c2b4-4079-96a4-e723b41ab5de (sn. 113–158) + "
                         "bdb01a58-b7ab-4b04-8115-9c2acf8ff49a (sn. 1–112, 159–490)", "Kurrent (German, Czech)", "2026-11-09"),
    "vca-smola-o-destne-rokytnice-uhrinov-nmnm": (["c3113199", "0484f35a", "f7a85f10", "060e88a7"],
                                                  "22584668-c138-4a53-a0e9-b6d76bc57563", "Kurrent (German, Czech)",
                                                  "2026-11-09"),
    "vca-destne-24-5": (["9634f2ed"], "85d892fd-9037-43a3-8887-d2bc20b3bfc5", "Kurrent (German, Czech)", "2026-11-09"),
    "vca-opocno-120-11": (["ab67b4df"], "f1f63e66-3c2f-45c8-8781-74a33a4528b1", "Kurrent (German, Czech)", "2026-11-09"),
    "vca-chocen-2095-sn270-390": (["1a6d0b5c"], "2db0d5e1-2ee0-4150-98e4-83f9b1fd1dba", "Kurrent (German, Czech)", "2026-11-09"),
    "vca-novy-hradek-117-2": (["8964843b"], "8a8b2b23-2fa8-4dab-91d8-53d33ff2378d", "Kurrent (German, Czech)", "2026-11-10"),
    "vca-novy-hradek-117-1-sn100": (["8df4dc98"], "b225448f-56c8-422e-8589-f2e2b2c30dfe", "Kurrent (German, Czech)", "2026-11-10"),
    "vca-novy-hradek-117-1-sn1": (["8df4dc98"], "aadba446-b0a7-4df8-9cc6-3796925b8243", "Kurrent (German, Czech)", "2026-11-12"),
    "vca-bystre-14-4": (["f9ac826b"], "3052565f-a1ce-4d4d-a463-5f9420ae7fa2", "Kurrent (German, Czech)", "2026-11-10"),
    "kramerius-1804-1805": (["kramerius-1804", "kramerius-1805"], "9fa4607b-77db-46dc-930f-d34910174fc0",
                            "Czech Fraktur Printed", "2026-11-02"),
    "ruda-su-xiv-19": (["su-xiv-19"], "1a7cf0e9-622f-4314-8b7a-2a4027591f52", "Czech Handwritten", "2026-11-02"),
    "ruda-su-xiv-4-14": (["su-xiv-4", "su-xiv-14"], "2d56f6dc-b89c-49a9-9e93-099de7a9306b", "Czech Handwritten", "2026-11-02"),
    "zayt-o830-noz530": (["o-830", "noz-530"], "e9d24973-74c9-4448-a926-a8bbf814d218", "Kurrent (German, Czech)", "2026-11-02"),
    "horazdovice-05": (["horazdovice-05"], "fd143024-c5a7-4f8e-808b-be33654abe80", "Czech Handwritten", "2026-10-22"),
    "vs-horazdovice-k1563": (["vs-horazdovice-k1563"], "d93b37ec-4ffb-4ad6-a2a6-e3d4846c54da", "Czech Handwritten",
                             "2026-10-22"),
    "horazdovice-05-zo": (["horazdovice-05-zo"], "61f588be-d923-4111-85d4-63af9d9c9101", "Czech Handwritten", "2026-10-22"),
    "horazdovice-05-kurrent": dict(knihy=["horazdovice-05"], cteni="pero-kurrent",
                                   dokument="8862a4c4-aeee-4093-9fc2-cf199db556de",
                                   model="Kurrent (German, Czech)", datum="2026-10-22"),
}


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


def book_of(image, books):
    for key in books:
        prefix = BOOKS[key]["prefix"]
        if not prefix or image.startswith(prefix + "_"):
            return key
    return None


def page_image(image, books):
    """Transkribus names a page '<page no>_<file>'; the book is found by the file name."""
    if book_of(image, books) is None and (m := re.match(r"\d{4}_(.+)$", image)):
        return m[1]
    return image


def file_number(image):
    m = re.search(r"(\d{4})(?:-[a-z]+)?$", image)
    return int(m.group(1)) if m else None


def snimek(key, image):
    n = file_number(image)
    if n is None:
        return ""
    return str(n // BOOKS[key].get("delitel", 10))


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
        elif v is not None:
            out.append(f"{k}: {q(v)}")
    return "\n".join(out) + "\n"


def write_book(key, cteni, rows, page_rows, entries):
    meta = BOOKS[key]
    out = REPO / "knihy" / meta["archiv"] / key
    out.mkdir(parents=True, exist_ok=True)
    ocr_file, pages_file = files_of(cteni)
    rows.sort(key=lambda r: (file_number(r[1]) or 0, r[1], r[2], r[4]))
    with open(out / ocr_file, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["snimek", "soubor", "strana", "radek", "x", "y", "sirka", "vyska", "jistota", "text"])
        line_no = {}
        for snim, image, side, x, y, wd, ht, conf, text in rows:
            line_no[(image, side)] = line_no.get((image, side), 0) + 1
            w.writerow([snim, image, side, line_no[(image, side)], x, y, wd, ht, conf, text])
    page_rows.sort(key=lambda r: (file_number(r[1]) or 0, r[1]))
    with open(out / pages_file, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["snimek", "soubor", "sirka_obrazku", "vyska_obrazku", "radku"])
        w.writerows(page_rows)
    path = out / "kniha.yaml"
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    else:
        data = {"archiv": meta["archiv"], "kniha": key, "nazev": meta["nazev"], "druh": meta.get("druh", "matrika"),
                "farnost": meta["farnost"], "roky": meta["roky"], "obsah": meta["obsah"], "url": meta["url"],
                "poznamka": meta.get("poznamka")}
    old = data.get("ocr") or []
    keep = [e for e in old if isinstance(e, dict) and e.get("soubor", "ocr-pero.tsv") != ocr_file]
    data["ocr"] = keep + entries
    path.write_text(dump_yaml(data), encoding="utf-8", newline="\n")
    print(f"{meta['archiv']}/{key} {ocr_file}: {len(page_rows)} stran, {len(rows)} řádků")


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # the Windows console defaults to cp1252
    parser = argparse.ArgumentParser()
    parser.add_argument("export", type=Path, nargs="+")
    args = parser.parse_args()
    rows, page_rows, entries = {}, {}, {}
    for export in args.export:
        stem = export.name.removesuffix(".zip").removesuffix(".pagexml")
        if stem not in EXPORTS:
            sys.exit(f"unknown export {stem}; add it to EXPORTS")
        spec = EXPORTS[stem]
        if not isinstance(spec, dict):
            spec = dict(knihy=spec[0], dokument=spec[1], model=spec[2], datum=spec[3])
        keys = spec["knihy"]
        seen = {}
        for xml in pages(export):
            parsed = parse_page(xml)
            if parsed is None:
                continue
            image, width, height, lines, info = parsed
            image = page_image(image, keys)
            key = book_of(image, keys)
            if key is None:
                print(f"skipping page {image}", file=sys.stderr)
                continue
            if "modely" in spec:
                if info.get("model_id") not in spec["modely"]:
                    sys.exit(f"{image}: model {info.get('model_id')} is not in modely")
                cteni, model = spec["modely"][info["model_id"]]
            else:
                cteni, model = spec.get("cteni", "pero"), spec["model"]
            snim = snimek(key, image)
            page_rows.setdefault((key, cteni), []).append([snim, image, width, height, len(lines)])
            for x, y, wd, ht, conf, text in lines:
                rows.setdefault((key, cteni), []).append(
                    (snim, image, "L" if x < width / 2 else "R", x, y, wd, ht, conf, text))
            s = seen.setdefault((key, cteni), {"stranek": 0, "radku": 0, "snimky": [], "dokumenty": [], "data": [],
                                               "model": model})
            s["stranek"] += 1
            s["radku"] += len(lines)
            if snim.isdigit():
                s["snimky"].append(int(snim))
            for k, lst in (("dokument", "dokumenty"), ("datum", "data")):
                if info.get(k) and info[k] not in s[lst]:
                    s[lst].append(info[k])
        for (key, cteni), s in seen.items():
            data = sorted(s["data"])
            entry = {"soubor": files_of(cteni)[0], "nastroj": spec.get("nastroj", PERO),
                     "dokument": spec.get("dokument") or ", ".join(s["dokumenty"]), "model": s["model"]}
            if spec.get("nastaveni") or entry["nastroj"] == PERO:
                entry["nastaveni"] = spec.get("nastaveni", PERO_NASTAVENI)
            entry.update({"datum": spec.get("datum") or (data[0] if len(data) < 2 else f"{data[0]}–{data[-1]}"),
                          "export": export.name, "snimky": compact(s["snimky"]), "stranek": s["stranek"],
                          "radku": s["radku"],
                          "poznamka": f"souřadnice v pixelech nahraného obrázku (viz {files_of(cteni)[1]}); text je "
                                      f"strojový, nekontrolovaný"})
            entries.setdefault((key, cteni), []).append(entry)
    for key, cteni in entries:
        write_book(key, cteni, rows.get((key, cteni), []), page_rows.get((key, cteni), []), entries[(key, cteni)])


if __name__ == "__main__":
    main()
