#!/usr/bin/env node
/* La línea de tiempo que necesita `subtitular.py`: los clips de cada pista de audio, los cortes de
 * plano y los fps, leídos de la secuencia por el bridge. Sólo LEE.
 *
 *   node herramientas/timeline_subtitulos.js <proyecto.json> "<video>" --secuencia "<nombre>"
 *   node herramientas/timeline_subtitulos.js <proyecto.json> "<video>" --volcado <clips.json> --fps 25
 *
 * La segunda forma no necesita Premiere: arma la línea de tiempo de un volcado de `premiere_clips`
 * guardado antes.
 *
 * ## Lo que deja, en «<video> - timeline.json» (la ruta sale del proyecto)
 *
 *   fps       los de la SECUENCIA, leídos con `estado`. Estaban fijos en 25, y a otros fps los cuadros
 *             de los subtítulos caen corridos sin que nada lo diga.
 *   fin       dónde termina el último clip.
 *   A         cada pista de audio con sus clips, `[medio, desde, hasta, entrada]`: el proyecto dice
 *             cuáles son de HABLA y cuál de LOCUCIÓN.
 *   V         los rangos de las pistas de video, que son los cortes de plano a los que se enganchan
 *             los subtítulos.
 *   titulos   los clips de video cuyo nombre empieza con uno de los `titulos` del proyecto —por
 *             ejemplo `["PDV ", "TIT "]`—: son texto ENCIMA de la imagen, no cortes de plano, y un
 *             subtítulo enganchado a un título entra o sale en el lugar equivocado.
 *
 * Los clips DESACTIVADOS —el ojito apagado— no cuentan: no se ven ni suenan en la mezcla.
 *
 * ## La secuencia tiene que ser la ACTIVA
 *
 * `--secuencia` es la guarda del bridge, no un selector: si la activa es otra, rebota sin leer
 * nada. Traerla al frente es del editor —o `premiere_secuencias`—, porque cambiar la activa le mueve
 * la interfaz a quien está trabajando. Sin `--secuencia` vale la `secuencia` del proyecto, que puede
 * ir por video en `videos`.
 *
 * ## Si la voz está adentro de un NESTED
 *
 * El bridge ve un solo clip con el nombre del nested, y sin los clips de adentro las palabras de
 * cada toma no se pueden pasar por los cortes. Para eso está `timeline_prproj.py`, que lee el .prproj
 * guardado y abre los nested.
 */
const fs = require("fs");
const path = require("path");

function uso(msg) {
  if (msg) console.error(msg + "\n");
  console.error('uso: node herramientas/timeline_subtitulos.js <proyecto.json> "<video>" --secuencia "<nombre>"\n' +
    '     node herramientas/timeline_subtitulos.js <proyecto.json> "<video>" --volcado <clips.json> --fps <n>');
  process.exit(1);
}

const args = process.argv.slice(2);
const opt = (n) => { const i = args.indexOf("--" + n); return i !== -1 && i + 1 < args.length ? args[i + 1] : null; };
const [rutaProyecto, video] = args;
if (!rutaProyecto || !video || rutaProyecto.startsWith("--") || video.startsWith("--")) uso();

const P0 = JSON.parse(fs.readFileSync(rutaProyecto, "utf8"));
if (P0.videos && !P0.videos[video]) uso(`«${video}» no está en \`videos\` del proyecto: ${Object.keys(P0.videos).join(", ")}`);
const P = Object.assign({}, P0, (P0.videos || {})[video] || {});   // lo de un video pisa lo del proyecto
const base = path.dirname(path.resolve(rutaProyecto));
const carpeta = path.join(base, P.carpeta || ".");
const salida = path.join(carpeta, (P.timeline || "{video} - timeline.json").split("{video}").join(video));
const prefijos = Array.isArray(P.titulos) ? P.titulos.map(String) : [];

/* La hora LOCAL, como la escribe quien trabaja: `toISOString` da UTC, tres horas corridas acá. */
function ahora() {
  const d = new Date(), dos = (x) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${dos(d.getMonth() + 1)}-${dos(d.getDate())} ${dos(d.getHours())}:${dos(d.getMinutes())}`;
}

/* Lo que sale del volcado de `clips`: las mismas reglas que tenía el script del proyecto que esto
 * generaliza, con los prefijos de títulos y las pistas de audio sacados del código. */
function armar(clips, fps, secuencia, de) {
  const esTitulo = (c) => prefijos.some((p) => String(c.nombre).startsWith(p));
  const T = {
    secuencia: secuencia,
    leido: ahora() + ", " + de,
    fin: Math.max(...clips.map((c) => c.hasta)),
    fps: fps,
    A: {},
    V: {},
    titulos: [],
  };
  for (const c of clips) {
    if (c.desactivado) continue;
    if (String(c.pista).startsWith("A")) {
      (T.A[c.pista] = T.A[c.pista] || []).push([c.nombre, c.desde, c.hasta, c.entrada]);
    } else if (esTitulo(c)) {
      T.titulos.push([c.nombre, c.desde, c.hasta]);
    } else {
      (T.V[c.pista] = T.V[c.pista] || []).push([c.desde, c.hasta]);
    }
  }
  return T;
}

(async () => {
  let clips, fps, secuencia, de;
  if (opt("volcado")) {
    const r = JSON.parse(fs.readFileSync(opt("volcado"), "utf8"));
    clips = r.clips || r;
    fps = Number(opt("fps"));
    if (!fps) uso("con --volcado hace falta --fps: el volcado de `clips` no trae los fps de la secuencia");
    secuencia = opt("secuencia") || P.secuencia || "(de un volcado)";
    de = "timeline_subtitulos.js --volcado";
  } else {
    secuencia = opt("secuencia") || P.secuencia;
    if (!secuencia) uso("falta --secuencia, o `secuencia` en el proyecto: la guarda de cuál tiene que estar activa");
    const { enviar } = require(path.join(__dirname, "..", "server", "bridge.js"));
    const guardas = { secuencia: secuencia };
    if (P.premiere) guardas.proyecto = String(P.premiere);   // el proyecto de Premiere, si el JSON lo nombra
    const e = await enviar("estado", guardas, 60000);
    fps = e.info && e.info.fps;
    if (!fps) throw new Error("`estado` no devolvió los fps de la secuencia: " + (e.resumen || "sin resumen"));
    const r = await enviar("clips", guardas, 120000);
    clips = r.clips;
    de = "timeline_subtitulos.js";
  }
  if (!Array.isArray(clips) || !clips.length) throw new Error("no hay clips en lo leído: nada con qué armar la línea de tiempo");

  const T = armar(clips, fps, secuencia, de);
  fs.mkdirSync(path.dirname(salida), { recursive: true });
  fs.writeFileSync(salida, JSON.stringify(T, null, 1));
  const cuenta = (o) => Object.entries(o).map(([k, v]) => `${k} ${v.length}`).join(" · ") || "ninguna";
  const pedidas = [...((P.pistas || {}).habla || ["A1"]), ...((P.pistas || {}).locucion || [])];
  const faltan = pedidas.filter((p) => !T.A[p]);
  console.log(`${video}: ${fps} fps · fin ${T.fin} s · audio: ${cuenta(T.A)} · video: ${cuenta(T.V)} · ` +
    `títulos ${T.titulos.length}` + (faltan.length ? ` · OJO: el proyecto pide ${faltan.join(", ")} y no tienen clips` : ""));
  console.log(`escrito: ${salida}`);
  process.exit(0);
})().catch((e) => { console.error("FALLÓ:", e.message.split("\n")[0]); process.exit(1); });
