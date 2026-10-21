"use strict";
/* Генератор PDF без внешних библиотек: A4, шрифт DejaVu Sans встраивается в файл.
   Вёрстка повторяет настольную версию: поля 1,5 см, отступ сверху 5 см, таблица 14 см
   (ППМ 4, S 1,1, МК 1,4, Время 2,8, Примечание 4,7), серая шапка, сетка 1 pt. */
(function () {
  const CM = 28.3465, PW = 595.28, PH = 841.89, FONT_URL = "fonts/DejaVuSans.ttf";
  let fontP = null;

  function parseFont(buf) {
    const dv = new DataView(buf), n = dv.getUint16(4), T = {};
    for (let i = 0; i < n; i++) {
      const o = 12 + i * 16;
      T[String.fromCharCode(dv.getUint8(o), dv.getUint8(o + 1), dv.getUint8(o + 2), dv.getUint8(o + 3))] = dv.getUint32(o + 8);
    }
    const upem = dv.getUint16(T.head + 18), nh = dv.getUint16(T.hhea + 34);
    let sub = 0; const nt = dv.getUint16(T.cmap + 2);
    for (let i = 0; i < nt; i++) {
      const o = T.cmap + 4 + i * 8;
      if (dv.getUint16(o) === 3 && dv.getUint16(o + 2) === 1) sub = T.cmap + dv.getUint32(o + 4);
    }
    const x2 = dv.getUint16(sub + 6), seg = x2 / 2, endO = sub + 14, stO = endO + x2 + 2, dlO = stO + x2, roO = dlO + x2;
    const gidOf = cp => {
      for (let s = 0; s < seg; s++) {
        if (cp <= dv.getUint16(endO + s * 2)) {
          const st = dv.getUint16(stO + s * 2); if (cp < st) return 0;
          const ro = dv.getUint16(roO + s * 2), dl = dv.getUint16(dlO + s * 2);
          if (ro === 0) return (cp + dl) & 0xFFFF;
          const g = dv.getUint16(roO + s * 2 + ro + (cp - st) * 2);
          return g ? (g + dl) & 0xFFFF : 0;
        }
      }
      return 0;
    };
    const cache = new Map(), used = new Map();
    const glyph = ch => {
      let r = cache.get(ch);
      if (!r) {
        const cp = ch.codePointAt(0), g = gidOf(cp);
        r = { g, w: dv.getUint16(T.hmtx + 4 * Math.min(g, nh - 1)) * 1000 / upem, cp };
        cache.set(ch, r);
      }
      return r;
    };
    return { buf, glyph, used };
  }
  const getFont = () => fontP || (fontP = fetch(FONT_URL).then(r => r.arrayBuffer()).then(parseFont));

  async function buildPdf(d) {
    const F = await getFont(); F.used.clear();
    const width = (s, z) => [...s].reduce((a, c) => a + F.glyph(c).w, 0) * z / 1000;
    const wrap = (text, z, maxW) => {
      const out = [];
      for (const para of String(text).split("\n")) {
        let cur = "";
        for (const word of para.split(" ")) {
          let t = cur ? cur + " " + word : word;
          if (width(t, z) <= maxW) { cur = t; continue; }
          if (cur) out.push(cur);
          cur = "";
          for (const ch of word) {
            if (width(cur + ch, z) > maxW && cur) { out.push(cur); cur = ch; } else cur += ch;
          }
        }
        out.push(cur);
      }
      return out;
    };
    const pages = []; let pg, y;
    const left = (PW - 14 * CM) / 2, cw = [4, 1.1, 1.4, 2.8, 4.7].map(v => v * CM), top = PH - 5 * CM, bottom = 72;
    const newPage = () => { pg = []; pages.push(pg); y = top; };
    const text = (x, yy, s, z) => {
      if (!s) return;
      let hex = "";
      for (const ch of s) { const g = F.glyph(ch); F.used.set(g.g, g.cp); hex += g.g.toString(16).padStart(4, "0"); }
      pg.push(`BT /F1 ${z} Tf ${x.toFixed(2)} ${yy.toFixed(2)} Td <${hex}> Tj ET`);
    };
    const base = (lineTop, L, z) => lineTop - (L / 2 + 0.32 * z); // базовая линия строки

    // заголовок «Маршрут: A — B»
    newPage();
    text(left, y - 11, d.title, 12);
    y -= 12 * 1.2 + 6;

    // строка таблицы
    const cells = (r, head) => r.map((v, i) => {
      const s = String(v == null ? "" : v).trim() || (head ? "" : " ");
      let z = 9;
      if (i === 4 && !head) { z = s.length > 350 ? 6 : s.length > 220 ? 7 : s.length > 120 ? 8 : 9; }
      const lines = wrap(i === 4 && !head ? s : String(v == null ? "" : v), z, cw[i] - 8);
      return { lines, z, L: i === 4 && !head ? z + 2 : z * 1.2 };
    });
    const drawRow = (r, head) => {
      const cs = cells(r, head), h = Math.max(...cs.map(c => c.lines.length * c.L)) + 6;
      if (y - h < bottom) { newPage(); drawRow(d.header, true); }
      let x = left;
      cs.forEach((c, i) => {
        if (head) pg.push(`0.8275 g ${x.toFixed(2)} ${(y - h).toFixed(2)} ${cw[i].toFixed(2)} ${h.toFixed(2)} re f 0 g`);
        pg.push(`0 G 1 w ${x.toFixed(2)} ${(y - h).toFixed(2)} ${cw[i].toFixed(2)} ${h.toFixed(2)} re S`);
        const blk = c.lines.length * c.L; let ly = y - 3 - (h - 6 - blk) / 2;
        c.lines.forEach(line => {
          const tw = width(line, c.z), tx = (!head && (i === 0 || i === 4)) ? x + 4 : x + (cw[i] - tw) / 2;
          text(tx, base(ly, c.L, c.z), line, c.z); ly -= c.L;
        });
        x += cw[i];
      });
      y -= h;
    };
    // шапка + строки (шапка повторяется на каждой странице)
    const first = y; drawRow(d.header, true); void first;
    d.rows.forEach(r => drawRow(r, false));
    y -= 10;

    // итоги
    d.info.forEach(s => {
      const lines = wrap(s, 9, 14 * CM), h = lines.length * 11 + 4;
      if (y - h < bottom) newPage();
      let ly = y - 2; lines.forEach(line => { text(left, base(ly, 11, 9), line, 9); ly -= 11; });
      y -= h;
    });

    // ---- сборка PDF ----
    const enc = new TextEncoder(), chunks = [], offs = []; let len = 0;
    const put = x => { const u = typeof x === "string" ? enc.encode(x) : x; chunks.push(u); len += u.length; };
    const obj = (n, parts) => { offs[n] = len; put(`${n} 0 obj\n`); [].concat(parts).forEach(put); put("\nendobj\n"); };
    const fontZ = new Uint8Array(await new Response(new Blob([F.buf]).stream().pipeThrough(new CompressionStream("deflate"))).arrayBuffer());
    const gids = [...F.used.keys()].sort((a, b) => a - b), hex4 = n => n.toString(16).padStart(4, "0").toUpperCase();
    const W = gids.map(g => { const ch = String.fromCodePoint(F.used.get(g)); return `${g} [${Math.round(F.glyph(ch).w)}]`; }).join(" ");
    let bf = ""; for (let i = 0; i < gids.length; i += 100) {
      const part = gids.slice(i, i + 100);
      bf += `${part.length} beginbfchar\n` + part.map(g => `<${hex4(g)}> <${hex4(F.used.get(g))}>`).join("\n") + "\nendbfchar\n";
    }
    const cmap = `/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def /CMapName /Adobe-Identity-UCS def /CMapType 2 def 1 begincodespacerange <0000> <FFFF> endcodespacerange\n${bf}endcmap CMapName currentdict /CMap defineresource pop end end`;
    put("%PDF-1.4\n");
    const kids = pages.map((_, i) => `${8 + 2 * i} 0 R`).join(" ");
    obj(1, "<< /Type /Catalog /Pages 2 0 R >>");
    obj(2, `<< /Type /Pages /Kids [${kids}] /Count ${pages.length} >>`);
    obj(3, "<< /Type /Font /Subtype /Type0 /BaseFont /DejaVuSans /Encoding /Identity-H /DescendantFonts [4 0 R] /ToUnicode 7 0 R >>");
    obj(4, `<< /Type /Font /Subtype /CIDFontType2 /BaseFont /DejaVuSans /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /FontDescriptor 5 0 R /DW 600 /W [${W}] /CIDToGIDMap /Identity >>`);
    obj(5, "<< /Type /FontDescriptor /FontName /DejaVuSans /Flags 4 /FontBBox [-1021 -463 1793 1232] /ItalicAngle 0 /Ascent 928 /Descent -236 /CapHeight 729 /StemV 80 /FontFile2 6 0 R >>");
    obj(6, [`<< /Length ${fontZ.length} /Length1 ${F.buf.byteLength} /Filter /FlateDecode >>\nstream\n`, fontZ, "\nendstream"]);
    obj(7, [`<< /Length ${enc.encode(cmap).length} >>\nstream\n`, cmap, "\nendstream"]);
    pages.forEach((c, i) => {
      const body = c.join("\n");
      obj(8 + 2 * i, `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${PW} ${PH}] /Resources << /Font << /F1 3 0 R >> >> /Contents ${9 + 2 * i} 0 R >>`);
      obj(9 + 2 * i, [`<< /Length ${enc.encode(body).length} >>\nstream\n`, body, "\nendstream"]);
    });
    const count = 8 + 2 * pages.length, xref = len;
    put(`xref\n0 ${count}\n0000000000 65535 f \n` + offs.slice(1).map(o => String(o).padStart(10, "0") + " 00000 n \n").join(""));
    put(`trailer\n<< /Size ${count} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`);
    const out = new Uint8Array(len); let p = 0; chunks.forEach(c => { out.set(c, p); p += c.length; });
    return out;
  }
  (typeof window !== "undefined" ? window : globalThis).buildPdf = buildPdf;
})();
