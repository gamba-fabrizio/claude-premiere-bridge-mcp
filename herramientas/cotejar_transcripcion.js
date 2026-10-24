#!/usr/bin/env node
/*
 * CRUZA DOS TRANSCRIPCIONES INDEPENDIENTES y devuelve SÓLO donde discrepan.
 *
 * Idea del editor, 2026-09-11, y es el método de este repo aplicado: dos mediciones
 * independientes que coinciden es la única confirmación que vale —lo mismo que cotejar
 * los marcadores del `.prproj` contra los de ffmpeg—. Acá las dos son Whisper y la
 * transcripción nativa de Premiere (26.5), que fallan de maneras DISTINTAS:
 *
 *   Adobe    más COMPLETO: capta habla que Whisper se come
 *   Whisper  más PRECISO en la palabra difícil, y acepta GLOSARIO
 *
 * Medido sobre un clip de 18s: 79% de coincidencia, y las 5 discrepancias incluían
 * "párpado" (Whisper, correcto en contexto) contra "el parto ¿lo vas?" (Adobe, sin
 * sentido) y tres tramos que Whisper no oyó y Adobe sí.
 *
 * Lo que devuelve NO es una transcripción mejor: es la LISTA CORTA de lo que hay que
 * escuchar. Un 79% de acuerdo sobre 18 segundos deja 5 puntos, no un archivo entero.
 *
 *   node herramientas/cotejar_transcripcion.js --whisper x.audio.json --adobe y.json
 *
 * `--adobe` acepta las tres formas del repo: la respuesta del verbo `transcripcion`, el `.audio.json` de
 * `audio.js --motor premiere` y el `.premiere.json`. OJO: el `.premiere.json` que deja `audio.js` es del motor
 * que CORRIÓ; el de una corrida de whisper es whisper, y rebota como la misma transcripción.
 *   node herramientas/cotejar_transcripcion.js --whisper x.audio.json --medio "CLIP.MP4" [--proyecto P]
 *
 * Con `--medio` lee la transcripción de Premiere por el bridge; el clip tiene que estar
 * en el proyecto y ya transcripto (`sondaTranscribir` con `correr: true`).
 */
const fs = require("fs");
const path = require("path");

const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf("--" + n); return i === -1 ? d : args[i + 1]; };
const W = opt("whisper"), A = opt("adobe"), MEDIO = opt("medio"), PROY = opt("proyecto");
const SALIDA = opt("salida");
if (!W || (!A && !MEDIO)) {
  console.error("Faltan datos. --whisper <json de audio.js> y (--adobe <json> o --medio \"CLIP.MP4\")");
  process.exit(1);
}

/* Palabras con tiempo, de cualquiera de las dos fuentes. El de Whisper las trae por
 * palabra; el de Premiere por segmento, así que ahí el tiempo es el del segmento —
 * alcanza para saltar ahí y escuchar, que es para lo que sirve. */
function deWhisper(j) {
  const out = [];
  for (const p of j.palabras || []) {
    const t = p.texto || p.palabra || "";
    if (t) out.push({ texto: String(t), desde: Number(p.desde ?? p.desdeFuente ?? 0) });
  }
  if (!out.length) for (const s of j.tramos || []) {
    for (const t of String(s.texto || "").split(/\s+/)) if (t) out.push({ texto: t, desde: Number(s.desde || 0) });
  }
  return out;
}
/* Las TRES formas que produce el propio repo (2026-10-24, un reporte de uso): sólo leía la primera, y con
 * las otras dos informaba "vino vacía" sobre 10.726 palabras.
 *   {segmentos:[{texto, desdeFuente}]}         la respuesta del verbo `transcripcion` (--medio)
 *   {palabras:[{texto, desde}]}                el .audio.json de `audio.js --motor premiere`
 *   {segments:[{start, words:[{text, start}]}]} el .premiere.json, el esquema de Premiere
 * Las dos últimas traen el tiempo por PALABRA, que es mejor que el del segmento. */
function deAdobe(j) {
  const out = [];
  for (const s of j.segmentos || []) {
    const d = Number(s.desdeFuente ?? s.desde ?? 0);
    for (const t of String(s.texto || "").split(/\s+/)) if (t) out.push({ texto: t, desde: d });
  }
  if (!out.length && Array.isArray(j.palabras)) return deWhisper(j);
  if (!out.length) for (const s of j.segments || []) {
    for (const w of s.words || []) {
      const t = String(w.text || "").trim();
      if (t) out.push({ texto: t, desde: Number(w.start ?? s.start ?? 0) });
    }
  }
  return out;
}
/* Un vacío es "no lo encontré", no "no hay": se dice qué claves traía el archivo. */
const claves = (j) => (j && typeof j === "object") ? "[" + Object.keys(j).slice(0, 8).join(", ") + "]" : typeof j;

const norm = (s) => s.toLowerCase()
  .normalize("NFD").replace(/[̀-ͯ]/g, "")   /* sin acentos: "mirame" vs "mírame" no es una discrepancia real */
  .replace(/[^\wñ]/g, "");

/* Alineación por subsecuencia común más larga: da las islas de acuerdo y, entre ellas,
 * los huecos que son las discrepancias.
 *
 * La tabla es n×m, y un episodio entero son ~10.000 × 10.000 palabras (S01E02, 2026-10-24): normalizar adentro
 * del doble bucle eran 200 millones de `normalize` (~1 min), y en Int32 ~430 MB. Cada palabra se normaliza UNA
 * vez, y la tabla va en 16 bits mientras la subsecuencia no pueda pasar de 65.535 —la mitad—. */
function alinear(a, b) {
  const n = a.length, m = b.length;
  const na = a.map((x) => norm(x.texto)), nb = b.map((x) => norm(x.texto));
  const Fila = Math.min(n, m) < 65536 ? Uint16Array : Int32Array;
  const L = Array.from({ length: n + 1 }, () => new Fila(m + 1));
  for (let i = n - 1; i >= 0; i--) {
    const ai = na[i], Li = L[i], Ls = L[i + 1];
    for (let j = m - 1; j >= 0; j--)
      Li[j] = ai && ai === nb[j] ? Ls[j + 1] + 1 : Math.max(Ls[j], Li[j + 1]);
  }
  const pares = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (na[i] && na[i] === nb[j]) { pares.push([i, j]); i++; j++; }
    else if (L[i + 1][j] >= L[i][j + 1]) i++; else j++;
  }
  return pares;
}

function tc(s) { const m = Math.floor(s / 60), r = (s % 60); return m + ":" + (r < 10 ? "0" : "") + r.toFixed(1); }

(async () => {
  const wj = JSON.parse(fs.readFileSync(W, "utf8"));
  let aj;
  if (A) aj = JSON.parse(fs.readFileSync(A, "utf8"));
  else {
    const { enviar } = require(path.join(__dirname, "..", "server", "bridge.js"));
    const p = { medio: MEDIO };
    if (PROY) p.proyecto = PROY;
    aj = await enviar("transcripcion", p, 300000);
  }

  const w = deWhisper(wj), a = deAdobe(aj);
  if (!w.length || !a.length) {
    console.error("Una de las dos vino vacía: whisper " + w.length + " palabras, premiere " + a.length + "." +
      " Lo que no se pudo leer puede ser el FORMATO y no la transcripción: whisper trae " + claves(wj) +
      ", premiere " + claves(aj) + ".");
    process.exit(1);
  }
  /* LA MISMA TRANSCRIPCIÓN EN DOS FORMATOS (2026-10-24, S01E02): el `.premiere.json` que deja `audio.js` al lado
   * del medio es del motor que CORRIÓ, no de Premiere, y pasado como --adobe contra el de whisper daba 100 %: se
   * comparaba consigo mismo. Dos motores no dan las mismas palabras con los mismos tiempos al milisegundo. */
  if (aj && wj && aj.motor && aj.motor === wj.motor) {
    console.error(`Las dos son del motor "${aj.motor}": no hay nada que cotejar. --adobe tiene que ser la de Premiere.`);
    process.exit(1);
  }
  if (a.length === w.length && a.every((x, i) => norm(x.texto) === norm(w[i].texto) && Math.abs(x.desde - w[i].desde) < 0.001)) {
    console.error(`Las dos son la MISMA transcripción (${a.length} palabras, con los mismos tiempos): casi seguro una ` +
      "en dos formatos. El .premiere.json que deja audio.js es del motor que corrió, no de Premiere.");
    process.exit(1);
  }
  const pares = alinear(a, w);
  const acuerdo = pares.length / Math.max(a.length, w.length);

  /* Los huecos ENTRE islas de acuerdo son las discrepancias. */
  const disc = [];
  let ia = 0, iw = 0;
  const empujar = (ha, hw) => {
    const ta = a.slice(ia, ha).map((x) => x.texto).join(" ");
    const tw = w.slice(iw, hw).map((x) => x.texto).join(" ");
    if (!ta && !tw) return;
    const t = (a[ia] || a[ha] || a[a.length - 1] || {}).desde;
    disc.push({ segundo: Number(t || 0), premiere: ta || "—", whisper: tw || "—",
      tipo: !ta ? "sólo Whisper" : !tw ? "sólo Premiere" : "distinto" });
  };
  for (const [pa, pw] of pares) { empujar(pa, pw); ia = pa + 1; iw = pw + 1; }
  empujar(a.length, w.length);

  const res = {
    palabras: { premiere: a.length, whisper: w.length, coinciden: pares.length },
    acuerdo: Number((acuerdo * 100).toFixed(1)),
    discrepancias: disc,
  };
  if (SALIDA) fs.writeFileSync(SALIDA, JSON.stringify(res, null, 1));

  console.log("Premiere " + a.length + " palabras · Whisper " + w.length +
    " · coinciden " + pares.length + " = " + res.acuerdo + "%\n");
  if (!disc.length) { console.log("Sin discrepancias: las dos dicen lo mismo."); return; }
  console.log(disc.length + " lugar(es) para escuchar:\n");
  for (const d of disc) {
    console.log("  " + tc(d.segundo).padStart(7) + "  " + d.tipo.padEnd(14) +
      "premiere: " + (d.premiere.slice(0, 38)).padEnd(40) + "whisper: " + d.whisper.slice(0, 38));
  }
  console.log("\nDonde coinciden podés confiar; esto es lo que hay que oír.");
  if (SALIDA) console.log("→ " + SALIDA);
})().catch((e) => { console.error("ERROR: " + (e && e.message ? e.message : e)); process.exit(1); });
