#!/usr/bin/env node
/*
 * FUSIONA las dos transcripciones en un borrador, y DICE DE DÓNDE SALIÓ CADA PALABRA.
 *
 * Idea del editor, 2026-09-11: si cada sistema falla distinto, combinarlos da mejor
 * resultado que elegir uno. Es cierto, y medido — Whisper acierta las marcas porque toma
 * glosario, Premiere capta habla que Whisper se come— pero hay que decir qué NO es esto:
 *
 *   **NO es una transcripción verificada.** Es un borrador con las costuras a la vista.
 *   Donde los dos coinciden se puede confiar; lo demás queda MARCADO, y decidirlo es
 *   escuchar. `cotejar_transcripcion.js` da esa lista.
 *
 * ── LA RESTRICCIÓN QUE MANDA EL DISEÑO: LOS TIEMPOS ──
 *
 * Whisper da tiempos POR PALABRA; Premiere, por SEGMENTO. El flujo de este repo corta
 * sobre los tiempos de palabra —`armar.js` resuelve cada frase a sus bordes—, así que una
 * palabra traída de Premiere con el tiempo de su segmento es un corte MAL PUESTO esperando.
 *
 * Por eso la base es SIEMPRE Whisper, y lo que se trae de Premiere viaja con
 * `tiempoExacto: false`. Quien corte tiene que mirar ese campo; quien sólo lea el texto,
 * no. Es la misma asimetría que el `desdeFuente` de la transcripción: un dato que sirve
 * para dos cosas distintas y sólo una necesita precisión.
 *
 *   node herramientas/fusionar_transcripcion.js --whisper x.audio.json --premiere y.json \
 *        [--salida z.json]
 */
const fs = require("fs"), path = require("path");
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf("--" + n); return i === -1 ? d : args[i + 1]; };
const W = opt("whisper"), P = opt("premiere"), S = opt("salida");
if (!W || !P) { console.error("Faltan --whisper y --premiere"); process.exit(1); }

const norm = (s) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^\wñ]/g, "");

function palabrasWhisper(j) {
  return (j.palabras || []).filter((p) => (p.texto || "").trim()).map((p) => ({
    texto: String(p.texto), desde: Number(p.desde ?? 0), hasta: Number(p.hasta ?? 0),
    fuente: "whisper", tiempoExacto: true, seguro: false,
  }));
}
/* Las TRES formas que produce el propio repo (2026-10-24, S01E02): sólo leía la primera, y con las otras la parte de
 * Premiere salía VACÍA sin aviso —el "borrador" era Whisper solo—. Las dos de archivo traen tiempo por palabra, más
 * cerca que el del segmento; igual viajan como `tiempoExacto: false`, porque la precisión de esos tiempos no está
 * medida para cortar.
 *   {segmentos:[{texto, desdeFuente, hastaFuente}]}     la respuesta del verbo `transcripcion`
 *   {palabras:[{texto, desde, dura}]}                   el .audio.json de `audio.js --motor premiere`
 *   {segments:[{start, words:[{text, start, duration}]}]} el .premiere.json, el esquema de Premiere */
function palabrasPremiere(j) {
  const out = [];
  for (const s of j.segmentos || []) {
    const d = Number(s.desdeFuente ?? s.desde ?? 0), h = Number(s.hastaFuente ?? s.hasta ?? d);
    for (const t of String(s.texto || "").split(/\s+/)) if (t)
      out.push({ texto: t, desde: d, hasta: h, fuente: "premiere", tiempoExacto: false, seguro: false });
  }
  if (!out.length) for (const p of j.palabras || []) {
    const t = String(p.texto || "").trim(), d = Number(p.desde ?? 0);
    if (t) out.push({ texto: t, desde: d, hasta: d + Number(p.dura ?? 0), fuente: "premiere", tiempoExacto: false, seguro: false });
  }
  if (!out.length) for (const s of j.segments || []) for (const w of s.words || []) {
    const t = String(w.text || "").trim(), d = Number(w.start ?? s.start ?? 0);
    if (t) out.push({ texto: t, desde: d, hasta: d + Number(w.duration ?? 0), fuente: "premiere", tiempoExacto: false, seguro: false });
  }
  return out;
}
/* Cada palabra se normaliza UNA vez, y la tabla va en 16 bits mientras alcance: con un episodio entero eran 200
 * millones de `normalize` y ~430 MB (ver `cotejar_transcripcion.js`). */
function pares(a, b) {
  const n = a.length, m = b.length;
  const na = a.map((x) => norm(x.texto)), nb = b.map((x) => norm(x.texto));
  const Fila = Math.min(n, m) < 65536 ? Uint16Array : Int32Array;
  const L = Array.from({ length: n + 1 }, () => new Fila(m + 1));
  for (let i = n - 1; i >= 0; i--) {
    const ai = na[i], Li = L[i], Ls = L[i + 1];
    for (let j = m - 1; j >= 0; j--) Li[j] = ai && ai === nb[j] ? Ls[j + 1] + 1 : Math.max(Ls[j], Li[j + 1]);
  }
  const out = []; let i = 0, j = 0;
  while (i < n && j < m) {
    if (na[i] && na[i] === nb[j]) { out.push([i, j]); i++; j++; }
    else if (L[i + 1][j] >= L[i][j + 1]) i++; else j++;
  }
  return out;
}

const wj = JSON.parse(fs.readFileSync(W, "utf8")), pj = JSON.parse(fs.readFileSync(P, "utf8"));
const w = palabrasWhisper(wj), p = palabrasPremiere(pj.premiere || pj);
/* Un vacío es "no lo encontré", no "no hay": se dice qué claves traía el archivo. */
const claves = (j) => (j && typeof j === "object") ? "[" + Object.keys(j).slice(0, 8).join(", ") + "]" : typeof j;
if (!w.length) { console.error("El JSON de Whisper no trae palabras: trae " + claves(wj) + "."); process.exit(1); }
if (!p.length) {
  console.error("El JSON de Premiere no trae palabras que se puedan leer: trae " + claves(pj) + ". Sin ellas, el " +
    "\"borrador\" sería Whisper solo.");
  process.exit(1);
}
/* La MISMA transcripción en dos formatos: el .premiere.json que deja `audio.js` es del motor que corrió. */
if (pj.motor && pj.motor === wj.motor) {
  console.error(`Las dos son del motor "${pj.motor}": no hay nada que fusionar. --premiere tiene que ser la de Premiere.`);
  process.exit(1);
}
if (w.length === p.length && w.every((x, i) => norm(x.texto) === norm(p[i].texto) && Math.abs(x.desde - p[i].desde) < 0.001)) {
  console.error(`Las dos son la MISMA transcripción (${w.length} palabras, con los mismos tiempos): casi seguro una en ` +
    "dos formatos. El .premiere.json que deja audio.js es del motor que corrió, no de Premiere.");
  process.exit(1);
}

const pr = pares(w, p);
const fus = [];
let iw = 0, ip = 0, coinciden = 0, soloP = 0, conflictos = 0;
const cerrar = (hw, hp) => {
  const gw = w.slice(iw, hw), gp = p.slice(ip, hp);
  if (gw.length && gp.length) {           /* CONFLICTO: manda Whisper por los tiempos */
    conflictos++;
    gw[0] = Object.assign({}, gw[0], { alternativa: gp.map((x) => x.texto).join(" ") });
    fus.push.apply(fus, gw);
  } else if (gw.length) fus.push.apply(fus, gw);
  else if (gp.length) { soloP += gp.length; fus.push.apply(fus, gp); }
};
for (const [a, b] of pr) {
  cerrar(a, b);
  fus.push(Object.assign({}, w[a], { seguro: true }));   /* los dos dicen lo mismo */
  coinciden++; iw = a + 1; ip = b + 1;
}
cerrar(w.length, p.length);

const res = {
  archivo: wj.archivo || null,
  advertencia: "BORRADOR: sólo las palabras con `seguro: true` las dicen los dos sistemas. " +
    "Las que traen `tiempoExacto: false` vienen de Premiere y su tiempo es del SEGMENTO, " +
    "no de la palabra: NO cortar sobre ellas sin mirar.",
  resumen: { total: fus.length, coinciden: coinciden, soloPremiere: soloP, conflictos: conflictos },
  palabras: fus,
};
if (S) fs.writeFileSync(S, JSON.stringify(res, null, 1));
console.log(`${fus.length} palabras · ${coinciden} las dicen LOS DOS · ${soloP} sólo Premiere ` +
  `(tiempo aproximado) · ${conflictos} conflicto(s) con alternativa anotada`);
if (S) console.log("→ " + S);
