// Pomocné funkce pro stránky PERO OCR (https://pero-ocr.fit.vutbr.cz). Vložit do konzole prohlížeče na stránce
// PERO (nebo přes javascript_tool) a zavolat. Postup je v PERO.md.

// Na stránce /document/upload_images_to_document/<dokument>: přidá vlevo nahoře vstup pro soubory (aria-label
// „claude upload“), který bere obrázky i balíky *.pack z tools/pero/balik.py a předá je nahrávači stránky. Vstup
// zůstává stejný, takže nástroje typu file_upload ho mohou plnit opakovaně.
function pripravNahravani() {
  window.__nahrano = window.__nahrano || 0;
  if (document.getElementById("clup")) return "vstup už existuje";
  const inp = document.createElement("input");
  inp.type = "file";
  inp.multiple = true;
  inp.id = "clup";
  inp.setAttribute("aria-label", "claude upload");
  inp.style.cssText = "position:fixed;left:5px;top:5px;z-index:99999;width:200px;height:30px";
  // Nahrávač stránky (Dropzone) vzniká až po načtení stránky, proto se hledá teprve při výběru souborů.
  inp.addEventListener("change", async () => {
    const dz = Dropzone.instances[0];
    if (!dz) {
      window.__chyba = "nahrávač stránky ještě není připravený, vyberte soubory znovu";
      return;
    }
    const files = [...inp.files];
    inp.value = "";
    for (const f of files) {
      if (!f.name.endsWith(".pack")) {
        dz.addFile(f);
        window.__nahrano++;
        continue;
      }
      const buf = await f.arrayBuffer();
      const n = new DataView(buf).getUint32(0, true);
      const head = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 4, n)));
      let off = 4 + n;
      for (const [name, size] of head) {
        dz.addFile(new File([buf.slice(off, off + size)], name, {type: "image/jpeg"}));
        off += size;
        window.__nahrano++;
      }
    }
  });
  document.body.appendChild(inp);
  return "ok";
}

// Na téže stránce: nahraje obrázky rovnou z archivu, který povoluje CORS (Porta fontium, MZA Acta Publica).
// seznam = [[jménoSouboru, url], …], např. výstup `mza.py pero`. Stahuje po jednom, nejvýš 5 obrázků za sekundu
// (z www.mza.cz 1 za 2 s, viz POMALE v tools/scan/slusne.py), a čeká, než nahrávač stránky dožene frontu. Stav je
// v window.__zUrl.
async function nahrajZUrl(seznam) {
  const dz = Dropzone.instances[0];
  window.__zUrl = {hotovo: 0, chyby: []};
  for (const [name, url] of seznam) {
    while (dz.getQueuedFiles().length + dz.getUploadingFiles().length >= 3) await new Promise(r => setTimeout(r, 500));
    const t0 = Date.now();
    try {
      const r = await fetch(url);
      if (r.status === 429 || r.status === 503) {
        window.__zUrl.chyby.push(name + " HTTP " + r.status + " – archiv přetížen, končím");
        return window.__zUrl;
      }
      if (!r.ok) throw new Error("HTTP " + r.status);
      dz.addFile(new File([await r.blob()], name, {type: "image/jpeg"}));
      window.__zUrl.hotovo++;
    } catch (e) {
      window.__zUrl.chyby.push(name + " " + e);
    }
    const odstup = new URL(url).hostname === "www.mza.cz" ? 2000 : 200;
    await new Promise(r => setTimeout(r, Math.max(0, odstup - (Date.now() - t0))));
  }
  return window.__zUrl;
}

// Na libovolné stránce PERO po dokončení OCR: složí PAGE XML všech stran dokumentu do jednoho souboru (PERO u velkých
// dokumentů na vlastní export odpovídá chybou 504) a nabídne ho ke stažení jako <nazev>.pagexml.txt. Lokálně ho
// zabalit do <nazev>.pagexml.zip pro tools/pero_import.py (název = `export` v položce ocr v kniha.yaml).
async function exportuj(dokument, nazev) {
  const h = await (await fetch("/ocr/show_results/" + dokument)).text();
  const d = new DOMParser().parseFromString(h, "text/html");
  const ids = [...new Set([...d.querySelectorAll("figure[data-image]")].map(f => f.dataset.image))];
  const parts = [];
  for (const id of ids) {
    const xml = await (await fetch("/document/get_page_xml_lines/" + id + "/1")).text();
    parts.push("### PAGE " + id + "\n" + xml);
  }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([parts.join("\n")], {type: "text/plain"}));
  a.download = nazev + ".pagexml.txt";
  a.textContent = "STÁHNOUT EXPORT (" + ids.length + " stran)";
  a.style.cssText = "position:fixed;left:20px;top:20px;z-index:99999;font:bold 28px sans-serif;background:yellow;padding:12px";
  document.body.appendChild(a);
  return ids.length;
}
