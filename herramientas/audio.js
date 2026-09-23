#!/usr/bin/env node
/**
 * Transcribe un medio AFUERA de Premiere y mapea qué hay en cada segundo.
 *
 * Por qué existe: la API de Premiere puede LEER transcripciones pero no
 * crearlas — hay que apretar Transcribe a mano, clip por clip. Esto se puede
 * disparar en tanda, sobre archivos que todavía no están importados.
 *
 * Vive acá y no en `plugin/` porque el panel corre adentro de Premiere: no
 * puede leer archivos de audio ni ejecutar ffmpeg. Esto es del lado del disco.
 *
 * Salida: un JSON con dos cosas, las dos en segundos de la FUENTE.
 *   palabras: [{texto, desde, dura, confianza, eos, hablante}]
 *   tramos:   [{que: "VOZ"|"SUENA"|"SIL", desde, hasta, db}]
 *
 * TRES MOTORES, y el default es PREMIERE. Medido el 2026-09-21 sobre un
 * testimonio de 3:33 grabado en el piso de una feria — o sea sala reverberante,
 * PA de fondo, y dos personas que se pisan:
 *
 *   motor      palabras   cubre        diariza  glosario  costo
 *   scribe       1019     0-213,1s       SI       no      ~40 caracteres por minuto
 *   premiere      406     0,4-213,1s     no       no      gratis, va en la suscripcion
 *   whisper       220     0-213,3s       no       SI      gratis, local
 *
 * **Y ese conteo NO ordena los motores, que es el error que costo escribir esta
 * tabla dos veces.** La primera version los ranqueo por palabras y por velocidad y
 * concluyo que Premiere era mas completo que whisper — lo que ese numero medía era
 * que whisper se habia comido el 78% del habla. Un motor con mas palabras puede
 * estar equivocandose mas. El conteo dice CUANTO, no QUE.
 *
 * PREMIERE es el default por tres razones, y la tercera no la puede dar ningun
 * otro: es nativo, no cuesta nada, y **la transcripcion queda INCRUSTADA en el
 * proyecto**. Este repo tiene medido que Premiere puede CREAR transcripciones pero
 * no puede RECIBIR una de afuera —`importFromJSON` devuelve un cascaron con el
 * puntero en null— asi que lo que transcribe otro motor NUNCA va a entrar al panel
 * Text. Y el texto es bueno: tramos largos salen palabra por palabra.
 *
 * Lo que Premiere pierde es un PATRON y no ruido, y por eso se puede decidir de
 * antemano si importa:
 *
 *   nombres propios  "<nombre y apellido> de la empresa <marca>"
 *                       -> "En la empresa. En la decada pasada de clase media."
 *   NUMEROS          "veintidos KILOvatios"  ->  "22 vatios"     <- factor 1000
 *   dos voces        el tramo donde se pisan director y entrevistado es ilegible
 *   comprime         se come muletillas, repeticiones y medio segundo hablante
 *
 * De ahi sale la regla: **si el texto se va a LEER —voz en off, subtitulos, una cita
 * textual, una especificacion— no alcanza con Premiere.** Un nombre de marca perdido
 * o un numero con un factor de mil se entrega. Para barrer material buscando DONDE se
 * dice algo, Premiere sobra y es gratis.
 *
 * SCRIBE es el mas completo y el unico que diariza —verificado por tres vias
 * independientes sobre un podcast de 70 min: 99,4% contra una atribucion anterior,
 * 97,2% contra que camara estaba al aire, y la apertura que se autodeclara—. Cuesta
 * creditos, asi que no es el default.
 *
 * Y OJO con una afirmacion vieja de este archivo, que quedo acotada: se habia medido
 * que Scribe inventaba mas que whisper (4 alucinaciones contra 0) sobre una locucion
 * LIMPIA contra un guion conocido. Sobre audio de feria pasa lo contrario, y por
 * lejos. **Ninguno de los tres es "el mejor": el ranking cambia con el material**, que
 * es el "medir un caso y generalizar" de CLAUDE.md aplicado a los motores.
 *
 * WHISPER es el unico que toma GLOSARIO, que es lo que este setup tiene medido como
 * lo que mas afina los nombres propios. Sobre audio limpio es el que menos inventa;
 * sobre audio dificil su VAD se come habla real.
 *
 * LO QUE ESTA HERRAMIENTA **NO** HACE: poner el margen de corte. Los tiempos que
 * devuelve son los bordes REALES de la palabra, y corregirlos aca seria mentir
 * sobre cuando arranca. Medido el 2026-09-21: los tres motores dan aire 0,000s en
 * la mediana, porque el borde de palabra ES el borde del habla — cuanto mejor mide
 * un motor, menos aire deja. El margen es una decision de MONTAJE y va en la
 * herramienta que elige los cortes; lo que esta le da es `tramos`, la envolvente,
 * que es el dato con el que se corre el corte al valle.
 *
 * Uso:
 *   node herramientas/audio.js <archivo> [--motor premiere|scribe|whisper]
 *                                        [--glosario "..."] [--margen 8]
 *                                        [--modelo ruta] [--salida ruta.json]
 *
 * Requiere `ffmpeg` y `whisper-cli` (brew install whisper-cpp), más dos modelos
 * en ~/Library/Application Support/whisper-cpp/models/:
 *   ggml-large-v3-turbo.bin   (~1,5 GB)  el que transcribe
 *   ggml-silero-v5.1.2.bin    (~900 KB)  el VAD, NO es opcional (ver abajo)
 */

const { execFileSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const MODELOS = path.join(os.homedir(), "Library/Application Support/whisper-cpp/models");
const SR = 16000;
const VENTANA = 0.1; // el mapa se calcula en ventanas de 100ms
const MOTORES = ["premiere", "scribe", "whisper"];
/*
 * 0,7 no es un numero elegido: sale de cruzar las 686 palabras de dos testimonios
 * contra Scribe. Las que COINCIDEN tienen confianza media 0,94 y solo 6-9% cae por
 * debajo de 0,7; las que NO coinciden tienen 0,75 y cae 34-40%. O sea que por
 * debajo de 0,7 una palabra es ~5x mas probable que este mal.
 */
const UMBRAL_CONFIANZA = 0.7;

function medido(args) {
  const out = { archivo: null, motor: "premiere", idioma: "es-es", glosario: "", margen: 8, destino: null, modelo: path.join(MODELOS, "ggml-large-v3-turbo.bin"), vad: path.join(MODELOS, "ggml-silero-v5.1.2.bin"), salida: null, trozos: 0, sinContexto: false };
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === "--glosario") {
      const v = args[++i] || "";
      /*
       * `@archivo` lee el glosario de un archivo. El glosario es del PROYECTO, no
       * del bridge —los nombres propios de un curso de bajo no le sirven a otro
       * trabajo— así que vive al lado del material y se pasa por referencia.
       */
      out.glosario = v.startsWith("@") ? fs.readFileSync(v.slice(1), "utf8").trim() : v;
    }
    else if (a === "--margen") out.margen = Number(args[++i]);
    /*
     * El motor se ELIGE y se REBOTA si no se conoce. Un nombre mal escrito que cae
     * al default en silencio produce una transcripcion con otro motor del que se
     * pidio, y despues no hay forma de saber cual la hizo — que es justo lo que el
     * campo `motor` de la salida existe para evitar.
     */
    else if (a === "--idioma") out.idioma = String(args[++i] || "es-es").toLowerCase();
    else if (a === "--motor") {
      out.motor = String(args[++i] || "").toLowerCase();
      if (!MOTORES.includes(out.motor)) {
        console.error(`No conozco el motor \`${out.motor}\`. Son: ${MOTORES.join(", ")}.`);
        process.exit(1);
      }
    }
    /*
     * `--trozos [seg]` transcribe en ventanas cortas en vez de todo el archivo de una.
     * Ver la nota de `transcribirPorTrozos`: es el modo que hay que usar cuando el
     * texto REAL importa y hay frases repetidas.
     */
    /*
     * `--sin-contexto` pone `-mc 0`: cero tokens de contexto arrastrado entre ventanas.
     * Es lo que apaga las alucinaciones, y salio ganando contra el chunking. Medido el
     * 2026-09-02 contra un guion conocido, sobre una locucion de 2:24 (guion = 282 tokens):
     *
     *   por defecto      296 tokens · 3 alucinaciones graves (invento dos frases enteras)
     *   -mc 0            280 tokens · CERO alucinaciones   <- y los -2 son "P.O.S." tokenizado
     *   --trozos 12s     281 tokens · 2, y PERDIO "intencion de compra" en una junta
     *   Scribe (11Labs)  298 tokens · 4, invento dos frases y un "listos para estas"
     *
     * El costo de `-mc 0` es la CONSISTENCIA de los nombres propios: sin contexto el modelo
     * no puede acordarse de como escribio una marca antes, y "AR" salio "Art" cuatro veces
     * donde la pasada por defecto lo tenia bien. Para encontrar el TEXTO real gana; para
     * subtitulos, el default con glosario cuida mejor los nombres. NO es el default todavia
     * porque esta medido sobre UN archivo, y este repo ya pago por generalizar de uno.
     */
    else if (a === "--sin-contexto") out.sinContexto = true;
    else if (a === "--trozos") {
      const v = Number(args[i + 1]);
      if (Number.isFinite(v) && v > 0) { out.trozos = v; i++; } else out.trozos = 12;
    }
    else if (a === "--modelo") out.modelo = args[++i];
    else if (a === "--vad") out.vad = args[++i];
    else if (a === "--salida") out.salida = args[++i];
    /*
     * `--destino` manda las tres salidas a una carpeta aparte, nombradas por el
     * archivo de origen. Sin esto escribe al lado del material, y en una tanda de
     * 147 clips eso son 441 archivos nuevos metidos entre los crudos.
     */
    else if (a === "--destino") out.destino = args[++i];
    else if (!out.archivo) out.archivo = a;
  }
  return out;
}

/*
 * El VAD NO es opcional, y esto costó medirlo.
 *
 * Sin VAD, atravesando un pasaje largo sin voz —él tocando el bajo— pasan dos
 * cosas a la vez: el timestamp DERIVA (medido: 12 segundos) y el modelo INVENTA
 * texto sobre la música (apareció un "¡Gracias!" donde sólo hay bajo). Con VAD
 * no procesa lo que no es voz, así que no deriva ni alucina, y encima tarda 3
 * veces menos. Verificado el 2026-08-17 contra un tramo del M5.
 */
function transcribir(wav, cfg, base) {
  const args = [
    "-m", cfg.modelo, "-f", wav, "-l", "es",
    "-oj", "-ojf", "-of", base,
    "-ml", "1", "-sow",              // una palabra por segmento, partiendo por PALABRA
    "--vad", "-vm", cfg.vad,
    "-np"
  ];
  /* Ver `--sin-contexto` en la lectura de opciones: `-mc 0` es lo que apaga las
   * alucinaciones, y `-nf` saca el reintento con temperatura, que es la otra vía por la
   * que el decodificador se va por las ramas. */
  if (cfg.sinContexto) args.push("-mc", "0", "-nf");
  /*
   * El glosario cambia mucho más de lo que parece. Sin él, Whisper escribió
   * "hito revé" y "los bamban"; pasándole los nombres del curso salieron "Elito
   * Revé" y "Los Van Van", las tres menciones bien y con acento. Es preferible
   * sesgar antes que corregir después: una corrección que no se puede verificar
   * se lee igual de segura que una verificada.
   */
  if (cfg.glosario) args.push("--prompt", cfg.glosario);
  execFileSync("whisper-cli", args, { stdio: ["ignore", "ignore", "inherit"] });
  return JSON.parse(fs.readFileSync(base + ".json", "utf8"));
}

/*
 * Transcribir en TROZOS CORTOS, que es el modo fiable cuando el texto importa.
 *
 * El VAD de arriba resuelve el caso "pasaje sin voz": ahí Whisper derivaba e inventaba.
 * NO resuelve el otro, medido el 2026-09-02 sobre una locución de 2:24 de habla continua:
 *
 *   COLAPSA una frase repetida en una sola. La firma es una palabra con duración 1,50s
 *   —que es su tope— y un hueco al lado que no explica nada.
 *   INVENTA repeticiones que no existen: apareció una línea entera repetida donde el audio
 *   sólo tiene 2,88s de voz, que a la velocidad del hablante no da ni para la mitad.
 *   Y sus TIEMPOS se corren hasta un segundo, así que no sirven para ubicar un corte.
 *
 * Tres pasadas sobre el mismo archivo dieron tres respuestas distintas —dos tropiezos,
 * cuatro, cinco— y yo informé cada una como un hecho. En trozos de 12s no puede hacer
 * ninguna de las dos cosas: no hay contexto largo que arrastrar. Verificado que DETECTA,
 * que es la mitad que faltaba: agarró las dos repeticiones reales y descartó una inventada.
 *
 * El pegado va por TIEMPO y no por coincidencia de palabras. Pegar buscando el solape
 * exacto se probó y falló: dos trozos transcriben su solape distinto —"en general" contra
 * "en Japón"— así que no encuentra dónde unir y DUPLICA. Acá cada trozo es dueño de un
 * intervalo disjunto y el solape existe sólo para darle contexto al borde.
 */
function transcribirPorTrozos(wav, cfg, tmp, dur) {
  const LARGO = cfg.trozos;
  const SOLAPE = Math.min(2, LARGO / 4);
  const palabras = [];
  for (let a = 0; a < dur; a += LARGO) {
    const trozo = path.join(tmp, `tr_${Math.round(a)}.wav`);
    execFileSync("ffmpeg", ["-v", "error", "-y", "-ss", String(a),
      "-t", String(Math.min(LARGO + SOLAPE, dur - a)), "-i", wav, "-c", "copy", trozo]);
    const j = transcribir(trozo, cfg, path.join(tmp, `tr_${Math.round(a)}`));
    /*
     * El solape se DEDUPLICA, no se descarta por intervalo. La primera versión le daba a
     * cada trozo el intervalo [a, a+LARGO) y tiraba lo de afuera, y con eso **perdió
     * "intención de compra"**: una palabra que el trozo N ubica pasado su borde y que el
     * trozo N+1 no vuelve a emitir cae en la grieta. Perder texto es peor que duplicarlo,
     * porque duplicado se ve y faltando no.
     */
    for (const w of palabrasDe(j)) {
      const t = Number((w.desde + a).toFixed(3));
      const clave = String(w.texto).toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
      const yaEsta = palabras.some((x) => Math.abs(x.desde - t) < 0.45 &&
        String(x.texto).toLowerCase().replace(/[^\p{L}\p{N}]/gu, "") === clave);
      if (yaEsta) continue;
      palabras.push(Object.assign({}, w, { desde: t,
                                           hasta: Number((w.hasta + a).toFixed(3)) }));
    }
    fs.unlinkSync(trozo);
  }
  palabras.sort((x, y) => x.desde - y.desde);
  return palabras;
}

function palabrasDe(json) {
  const segs = (json.transcription || []).filter((s) => s.text.trim());
  const pal = segs.map((s) => {
    const toks = (s.tokens || []).filter((t) => typeof t.p === "number");
    return {
      texto: s.text.trim(),
      desde: s.offsets.from / 1000,
      hasta: s.offsets.to / 1000,
      confianza: toks.length ? Number(Math.min(...toks.map((t) => t.p)).toFixed(3)) : null,
      eos: /[.?!…]$/.test(s.text.trim())
    };
  });
  /*
   * Con VAD, la última palabra antes de un hueco INFLA su duración para taparlo:
   * "verlo." apareció como 13.37→42.12 cuando el habla vuelve en 42.12. El
   * `desde` es confiable, el `hasta` no. Se recorta contra la palabra siguiente
   * y, cuando eso da un largo absurdo, se acota a algo razonable.
   */
  for (let i = 0; i < pal.length; i++) {
    const tope = i + 1 < pal.length ? pal[i + 1].desde : pal[i].hasta;
    pal[i].hasta = Math.min(pal[i].hasta, tope);
    if (pal[i].hasta - pal[i].desde > 1.5) pal[i].hasta = pal[i].desde + 1.5;
    pal[i].dura = Number((pal[i].hasta - pal[i].desde).toFixed(3));
    pal[i].desde = Number(pal[i].desde.toFixed(3));
    delete pal[i].hasta;
  }
  return pal;
}

/*
 * El mapa de tres estados. VOZ la marca el VAD; el resto se decide por energía,
 * y no hace falta ningún modelo de instrumentos para eso: "suena algo" es
 * exactamente "no es voz y no está callado".
 *
 * El piso se mide EN EL PROPIO CLIP y no se fija a mano. Un umbral absoluto no
 * generaliza: medido sobre dos clips reales, uno de locución con música vive en
 * -20 dB y uno de habla seca en -40, así que el mismo número clasifica bien uno
 * y mal el otro. Con el piso relativo, un clip con música todo el tiempo
 * simplemente no reporta SIL — que es la respuesta correcta, no una falla.
 */
function mapa(wav, palabras, margen) {
  const buf = fs.readFileSync(wav);
  const datos = buf.indexOf(Buffer.from("data")) + 8;
  const muestras = Math.floor((buf.length - datos) / 2);
  const porVentana = Math.round(SR * VENTANA);
  const db = [];
  for (let i = 0; i + porVentana <= muestras; i += porVentana) {
    let s = 0;
    for (let k = 0; k < porVentana; k++) { const v = buf.readInt16LE(datos + (i + k) * 2) / 32768; s += v * v; }
    const rms = Math.sqrt(s / porVentana);
    db.push(rms > 0 ? 20 * Math.log10(rms) : -120);
  }
  const orden = [...db].sort((a, b) => a - b);
  const piso = orden[Math.floor(orden.length * 0.05)];
  const umbral = piso + margen;

  const arranques = palabras.map((p) => p.desde);
  const estado = db.map((d, i) => {
    const t = i * VENTANA;
    // ±0.35s de tolerancia: el arranque de palabra es bueno a ~100ms, no exacto
    if (arranques.some((w) => w >= t - 0.35 && w < t + VENTANA + 0.35)) return "VOZ";
    return d > umbral ? "SUENA" : "SIL";
  });

  const bruto = [];
  for (let i = 0; i < estado.length; i++) {
    const u = bruto[bruto.length - 1];
    if (u && u.que === estado[i]) u.hasta = (i + 1) * VENTANA;
    else bruto.push({ que: estado[i], desde: i * VENTANA, hasta: (i + 1) * VENTANA });
  }
  // Los parpadeos de menos de 0.3s se absorben en el tramo anterior: una sílaba
  // suelta no es un cambio de estado.
  const tramos = [];
  for (const t of bruto) {
    const u = tramos[tramos.length - 1];
    if (u && (t.hasta - t.desde < 0.3 || u.que === t.que)) { u.hasta = t.hasta; continue; }
    tramos.push({ ...t });
  }
  for (const t of tramos) {
    const d = db.slice(Math.round(t.desde / VENTANA), Math.round(t.hasta / VENTANA));
    t.db = d.length ? Number((d.reduce((a, b) => a + b, 0) / d.length).toFixed(1)) : null;
    t.desde = Number(t.desde.toFixed(2));
    t.hasta = Number(t.hasta.toFixed(2));
  }
  return { piso: Number(piso.toFixed(1)), umbral: Number(umbral.toFixed(1)), tramos };
}

/*
 * Convierte al esquema que Premiere exporta —y por lo tanto acepta— en
 * `Transcript.importFromJSON`. Se sacó exportando una transcripción real con
 * `premiere_transcripcion` y `crudo: true`, no de la documentación.
 *
 * Los segmentos se cortan por FIN DE ORACIÓN (`eos`), que es lo que hace
 * Premiere, y no por cantidad de palabras: cortar por cantidad parte a mitad de
 * frase, que ya se pagó armando un SRT.
 */
function aPremiere(palabras, idioma) {
  const hablante = "00000000-0000-4000-8000-000000000001";
  const segmentos = [];
  let actual = null;
  for (const p of palabras) {
    if (!actual) actual = { start: p.desde, duration: 0, language: idioma, speaker: hablante, words: [] };
    actual.words.push({
      confidence: p.confianza === null ? 1 : p.confianza,
      duration: p.dura,
      eos: !!p.eos,
      start: p.desde,
      tags: [],
      text: p.texto,
      type: "word"
    });
    actual.duration = Number((p.desde + p.dura - actual.start).toFixed(3));
    // Se cierra en fin de oración, o si el segmento ya se hizo muy largo.
    if (p.eos || actual.duration > 30) { segmentos.push(actual); actual = null; }
  }
  if (actual) segmentos.push(actual);
  return { language: idioma, speakers: [{ id: hablante, name: "Unknown" }], segments: segmentos };
}

/*
 * SRT, que es el formato que Premiere importa con `File > Import` seguro.
 *
 * Entra como PISTA DE SUBTÍTULOS, que no es lo mismo que una transcripción: da el
 * texto en el timeline y búsqueda en el panel Captions, pero no es lo que lee
 * `Transcript.exportToJSON`. Es el camino manual mientras la importación por API
 * siga sin resolverse.
 *
 * Se corta por FIN DE ORACIÓN, no por cantidad de palabras: cortar por cantidad
 * parte a mitad de frase, y eso ya se pagó armando un SRT antes. Con un tope de
 * caracteres para que quepa en pantalla.
 */
function aSRT(palabras, topeChars) {
  const tope = topeChars || 84;
  const bloques = [];
  let actual = null;
  for (const p of palabras) {
    if (!actual) actual = { desde: p.desde, hasta: p.desde + p.dura, texto: [] };
    actual.texto.push(p.texto);
    actual.hasta = p.desde + p.dura;
    const largo = actual.texto.join(" ").length;
    if (p.eos || largo >= tope) { bloques.push(actual); actual = null; }
  }
  if (actual) bloques.push(actual);
  /*
   * Y se fusionan los bloques huérfanos con el anterior.
   *
   * El tope de caracteres puede cortar a mitad de oración y dejar el resto solo:
   * medido, quedó un bloque con la única palabra "compases." de 0,45s. Un
   * subtítulo así parpadea y se lee peor que una línea larga.
   */
  const juntos = [];
  for (const b of bloques) {
    const u = juntos[juntos.length - 1];
    const corto = b.hasta - b.desde < 1 || b.texto.join(" ").length < 22;
    if (u && corto) { u.texto = u.texto.concat(b.texto); u.hasta = b.hasta; continue; }
    juntos.push(b);
  }
  bloques.length = 0;
  bloques.push(...juntos);
  const reloj = (s) => {
    const ms = Math.round(s * 1000);
    const h = String(Math.floor(ms / 3600000)).padStart(2, "0");
    const m = String(Math.floor((ms % 3600000) / 60000)).padStart(2, "0");
    const sg = String(Math.floor((ms % 60000) / 1000)).padStart(2, "0");
    return `${h}:${m}:${sg},${String(ms % 1000).padStart(3, "0")}`;
  };
  return bloques
    .map((b, i) => `${i + 1}\n${reloj(b.desde)} --> ${reloj(b.hasta)}\n${b.texto.join(" ")}\n`)
    .join("\n");
}

/**
 * Pasa las palabras de tiempo de FUENTE a tiempo de SECUENCIA, usando los clips
 * que devuelve `premiere_clips`.
 *
 * Existe para no hacer esta cuenta a mano en cada tanda. La fórmula del reloj de
 * material es la trampa más cara de este repo: **pasó todas las pruebas sin el
 * factor de velocidad**, porque todos los clips corrían a 1x. Escrita una vez y
 * verificada contra la conversión de Premiere, deja de ser un riesgo por tanda.
 *
 *   secuencia = clip.desde + (fuente − clip.entrada) / velocidad
 *
 * Una palabra puede caer en VARIOS clips —el mismo material cortado en pedazos—
 * y entonces aparece una vez por cada uno, que es lo correcto: se ve dos veces en
 * el timeline. Y las que caen fuera de todo clip se descartan: están en el
 * material pero no en la secuencia, así que no se puede cortar ahí.
 */
function aSecuencia(palabras, clips, nombreMedio) {
  const suyos = clips.filter((c) => {
    if (nombreMedio && c.nombre !== nombreMedio) return false;
    return typeof c.entrada === "number" && typeof c.desde === "number";
  });
  const fuera = [];
  const salida = [];
  for (const p of palabras) {
    let entro = false;
    for (const c of suyos) {
      const vel = typeof c.velocidad === "number" && c.velocidad > 0 ? c.velocidad : 1;
      const finFuente = c.entrada + (c.hasta - c.desde) * vel;
      // El borde de arriba es exclusivo: una palabra que arranca justo donde
      // termina el clip ya no se ve en ese clip.
      if (p.desde < c.entrada || p.desde >= finFuente) continue;
      entro = true;
      salida.push({
        texto: p.texto,
        desde: Number((c.desde + (p.desde - c.entrada) / vel).toFixed(3)),
        dura: Number((p.dura / vel).toFixed(3)),
        confianza: p.confianza,
        eos: p.eos,
        pista: c.pista,
        indice: c.indice
      });
    }
    if (!entro) fuera.push(p.texto);
  }
  salida.sort((a, b) => a.desde - b.desde);
  return { palabras: salida, recortadas: fuera.length, clipsUsados: suyos.length };
}

/*
 * PREMIERE. Importa el medio si no esta, dispara la transcripcion y la RELEE.
 *
 * El veredicto sale de releer, no del booleano: `sondaTranscribir` devuelve true
 * y lo unico que prueba que haya transcripto es que `transcripcion` devuelva
 * palabras. Es el modo de fallar n1 de CLAUDE.md.
 *
 * La guarda `proyecto` se DEDUCE del foco y se manda en cada llamada — no se pide
 * por flag, porque una guarda que hay que acordarse de pasar es una guarda que no
 * esta cuando hace falta. Si el foco cambia en el medio, las llamadas siguientes
 * rebotan, que es exactamente lo que tiene que pasar.
 */
async function palabrasPremiere(cfg) {
  const { enviar } = require("../server/bridge.js");
  const medio = path.basename(cfg.archivo);

  const est = await enviar("estado", {}, 30000);
  const proyecto = est && est.info && est.info.proyectoNombre;
  if (!proyecto) throw new Error("no pude leer que proyecto tiene el foco en Premiere; sin eso no mando la guarda `proyecto`");

  await enviar("importar", { archivos: [path.resolve(cfg.archivo)], proyecto }, 120000);

  const s = await enviar("sondaTranscribir",
    { medio, idioma: cfg.idioma, correr: true, proyecto }, 1800000);
  const yaEstaba = s && s.info && s.info.yaTenia;

  const r = await enviar("transcripcion", { medio, palabras: true, proyecto }, 120000);
  const segs = (r && r.segmentos) || [];
  const palabras = [];
  for (const sg of segs) {
    for (const w of (sg.palabras || [])) {
      /*
       * `desdeFuente`/`hastaFuente` y NO `desde`/`hasta`: esta herramienta promete
       * segundos de la FUENTE. En un medio que no esta en ninguna secuencia los dos
       * pares coinciden, asi que agarrar el equivocado no se nota hasta el dia que
       * el medio SI este montado — y ahi los tiempos salen del timeline y todo lo
       * que corte contra ellos cae en otro lado.
       *
       * Y `finDeOracion` es NATIVO: no hay que deducirlo de la puntuacion.
       */
      const d = Number(w.desdeFuente !== undefined ? w.desdeFuente : w.desde);
      const h = Number(w.hastaFuente !== undefined ? w.hastaFuente : w.hasta);
      palabras.push({
        texto: String(w.texto || "").trim(),
        desde: d,
        dura: Number.isFinite(h) ? Math.max(0, h - d) : 0,
        confianza: w.confianza !== undefined ? Number(w.confianza) : null,
        eos: !!w.finDeOracion,
        hablante: w.hablante || sg.hablante || null
      });
    }
  }
  if (!palabras.length) {
    throw new Error(`Premiere no devolvio palabras para "${medio}". Lo que contesto: ${(r && r.resumen) || "nada"}`);
  }
  return { palabras, nota: yaEstaba ? "el medio YA tenia transcripcion y se releyo la que habia" : null };
}

/*
 * SCRIBE. La key sale SOLO de $ELEVENLABS_API_KEY: ni de un archivo ni por
 * argumento, porque un argumento queda visible en `ps` mientras dura el pedido.
 *
 * Se manda un mp3 y no el wav a proposito: el wav de 16 kHz de una hora pesa
 * ~115 MB y el mp3 equivalente ~28. Es lo unico que cambia; el analisis de la
 * envolvente sigue saliendo del wav.
 */
async function palabrasScribe(cfg, wav, tmp) {
  const key = process.env.ELEVENLABS_API_KEY;
  if (!key) throw new Error("falta $ELEVENLABS_API_KEY en el entorno. No se acepta por argumento: quedaria visible en `ps`.");

  const mp3 = path.join(tmp, "a.mp3");
  execFileSync("ffmpeg", ["-v", "error", "-y", "-i", wav, "-c:a", "libmp3lame", "-b:a", "64k", mp3]);

  const fd = new FormData();
  fd.append("file", new Blob([fs.readFileSync(mp3)], { type: "audio/mpeg" }), "a.mp3");
  fd.append("model_id", "scribe_v1");
  fd.append("language_code", cfg.idioma.split("-")[0]);
  fd.append("diarize", "true");
  fd.append("timestamps_granularity", "word");

  const res = await fetch("https://api.elevenlabs.io/v1/speech-to-text",
    { method: "POST", headers: { "xi-api-key": key }, body: fd });
  if (!res.ok) throw new Error(`Scribe contesto ${res.status}: ${(await res.text()).slice(0, 300)}`);
  const j = await res.json();

  /*
   * `type` separa las palabras de los espacios y de los eventos de audio
   * ([risas], [aplausos]). Se quedan solo las palabras: un espacio con tiempos
   * entra al conteo y corre cualquier emparejamiento posterior.
   */
  const palabras = (j.words || [])
    .filter((w) => w.type === "word" && String(w.text || "").trim())
    .map((w) => ({
      texto: String(w.text).trim(),
      desde: Number(w.start),
      dura: Number(w.end) - Number(w.start),
      /*
       * Scribe devuelve `logprob`, que es NEGATIVO; Premiere devuelve una
       * probabilidad 0-1. Se normaliza para que el campo signifique lo mismo en
       * los dos — sin esto, cualquier umbral pensado para uno marca el 100% del
       * otro, que es lo que paso la primera vez que se corrio.
       */
      confianza: w.logprob !== undefined ? Math.exp(Number(w.logprob)) : null,
      eos: false,
      hablante: w.speaker_id || null
    }));
  if (!palabras.length) throw new Error("Scribe no devolvio ninguna palabra");
  marcarFinDeFrase(palabras);

  const quienes = new Set(palabras.map((w) => w.hablante).filter(Boolean));
  return { palabras, nota: quienes.size ? `${quienes.size} hablante(s) separados por Scribe` : null };
}

/*
 * `eos` lo pone whisper solo; los otros dos no lo traen, y el resto del repo lo
 * consume —`armar.js` resuelve cada frase a sus bordes de palabra—. Se deduce de
 * la puntuacion, que es lo que los tres devuelven.
 */
function marcarFinDeFrase(palabras) {
  for (const w of palabras) w.eos = /[.?!…]["')\]]?$/.test(w.texto);
  if (palabras.length) palabras[palabras.length - 1].eos = true;
}

/*
 * Lo que cada motor NO puede, dicho en el resumen de CADA corrida.
 *
 * Va en el resumen y no solo en el JSON porque un dato que esta en la respuesta
 * y no en el resumen es un dato que no esta — es la misma razon por la que
 * `clips` grita cuando una pista tiene el ojito apagado. El que transcribe tiene
 * que enterarse de que Premiere pierde los nombres propios ANTES de escribir una
 * voz en off con el nombre de la marca adentro, no despues de entregarla.
 */
const ACHAQUES = {
  premiere: "pierde NOMBRES PROPIOS y NUMEROS (medido: \"veintidos kilovatios\" -> \"22 vatios\") y no toma glosario. Si el texto se va a LEER, cotejalo.",
  scribe: "gasta creditos (~40 caracteres por minuto de audio) y no toma glosario.",
  whisper: "su VAD se come habla real en audio dificil (medido: 220 palabras donde Scribe saco 1019). Toma glosario, que es lo que afina los nombres propios."
};

async function main() {
  const cfg = medido(process.argv.slice(2));
  if (!cfg.archivo) {
    console.error("Falta el archivo. Uso: node herramientas/audio.js <archivo> [--motor premiere|scribe|whisper] [--glosario \"...\"] [--margen 8]");
    process.exit(1);
  }
  if (!fs.existsSync(cfg.archivo)) {
    console.error(`No existe el archivo: ${cfg.archivo}`);
    process.exit(1);
  }
  /*
   * Los modelos los pide SOLO whisper. Exigirlos siempre haria rebotar a
   * `--motor premiere`, que no los usa: rechazar uso correcto es el peor modo de
   * fallo de una guarda, y este repo ya lo pago con la guarda de `recargar.js`
   * que exigia UDT abierto cuando el macro lo abre.
   */
  if (cfg.motor === "whisper") {
    for (const [q, r] of [["el modelo", cfg.modelo], ["el modelo de VAD", cfg.vad]]) {
      if (!fs.existsSync(r)) {
        console.error(`No está ${q}: ${r}\nBajalo de https://huggingface.co/ggerganov/whisper.cpp y https://huggingface.co/ggml-org/whisper-vad`);
        process.exit(1);
      }
    }
  }
  if (cfg.glosario && cfg.motor !== "whisper") {
    console.error(`OJO: \`--glosario\` lo toma SOLO whisper, y pediste \`${cfg.motor}\`. Se va a ignorar, o corré con --motor whisper.`);
  }

  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "audio-"));
  const wav = path.join(tmp, "a.wav");
  try {
    // 16 kHz mono es lo que pide whisper, y de este wav sale la envolvente en los tres motores.
    execFileSync("ffmpeg", ["-v", "error", "-y", "-i", cfg.archivo, "-ar", String(SR), "-ac", "1", "-c:a", "pcm_s16le", wav]);

    let palabras, nota = null;
    if (cfg.motor === "premiere") {
      ({ palabras, nota } = await palabrasPremiere(cfg));
    } else if (cfg.motor === "scribe") {
      ({ palabras, nota } = await palabrasScribe(cfg, wav, tmp));
    } else if (cfg.trozos) {
      const dur = Number(execFileSync("ffprobe", ["-v", "error", "-show_entries",
        "format=duration", "-of", "csv=p=0", wav], { encoding: "utf8" }).trim());
      palabras = transcribirPorTrozos(wav, cfg, tmp, dur);
    } else {
      palabras = palabrasDe(transcribir(wav, cfg, path.join(tmp, "t")));
    }
    const m = mapa(wav, palabras, cfg.margen);

    const salida = {
      archivo: path.resolve(cfg.archivo),
      motor: cfg.motor,
      idioma: cfg.idioma,
      glosario: (cfg.motor === "whisper" && cfg.glosario) || null,
      piso: m.piso, umbral: m.umbral,
      palabras: palabras,
      tramos: m.tramos
    };
    const base = cfg.destino
      ? path.join(cfg.destino, path.basename(cfg.archivo).replace(/\.[^.]+$/, ""))
      : cfg.archivo.replace(/\.[^.]+$/, "");
    if (cfg.destino) fs.mkdirSync(cfg.destino, { recursive: true });
    const destino = cfg.salida || base + ".audio.json";
    fs.writeFileSync(destino, JSON.stringify(salida, null, 1));

    /*
     * Sólo si hay palabras. Un insert muto generaría un .srt vacío y un
     * .premiere.json sin segmentos, y en una tanda de 100 inserts eso son 200
     * archivos de ruido entre los que sí sirven.
     */
    let paraPremiere = null, srt = null;
    if (palabras.length) {
      // Y el mismo contenido en el esquema de Premiere.
      paraPremiere = base + ".premiere.json";
      fs.writeFileSync(paraPremiere, JSON.stringify(aPremiere(palabras, cfg.idioma), null, 1));

      // Y el SRT, que es el que Premiere importa a mano con File > Import.
      srt = base + ".srt";
      fs.writeFileSync(srt, aSRT(palabras));
    }

    /*
     * La confianza la dan premiere y scribe; whisper con esta configuracion no.
     * `null` significa "este motor no la informa" y NO cero: informar cero
     * palabras flojas sobre un motor que no las mide seria decir que esta todo
     * bien sobre algo que no se pudo mirar.
     */
    const conConf = palabras.filter((w) => typeof w.confianza === "number");
    /*
     * El umbral esta medido SOLO contra Premiere. Aplicarselo a otro motor seria
     * transferir un numero entre regimenes, que es como este repo volteo los 14
     * tramos buenos de `sincro.py` con el umbral del modo simple. Los otros
     * motores devuelven la confianza en el JSON y no se los juzga con este numero.
     */
    const flojas = (cfg.motor === "premiere" && conConf.length)
      ? conConf.filter((w) => w.confianza < UMBRAL_CONFIANZA).length
      : null;

    const cuenta = (q) => m.tramos.filter((t) => t.que === q).reduce((n, t) => n + (t.hasta - t.desde), 0);
    console.log(
      `${path.basename(cfg.archivo)} · motor ${cfg.motor.toUpperCase()}: ${palabras.length} palabras · ` +
      `voz ${cuenta("VOZ").toFixed(0)}s · suena ${cuenta("SUENA").toFixed(0)}s · silencio ${cuenta("SIL").toFixed(0)}s · ` +
      `piso ${m.piso}dB, silencio bajo ${m.umbral}dB` +
      (nota ? `\n   ${nota}` : "") +
      (flojas === null ? "" : `\n   ${flojas} palabra(s) con confianza < ${UMBRAL_CONFIANZA} — miralas. OJO: su SILENCIO no prueba nada,` +
        `\n   el 60% de los errores viene con confianza alta (medido sobre 686 palabras en 2 clips).`) +
      `\n   OJO, ${cfg.motor}: ${ACHAQUES[cfg.motor]}` +
      `\n   Los tiempos son los bordes REALES de la palabra, SIN margen de corte: el margen es` +
      `\n   una decision de montaje y va en la herramienta que elige los cortes, con \`tramos\`.` +
      /* LOS TRES ARCHIVOS, no solo el JSON.
       *
       * `paraPremiere` y `srt` se calculaban y NUNCA se imprimian: la herramienta escribia tres
       * archivos y nombraba uno. Y sin `--destino` escribe AL LADO DEL MEDIO, asi que apuntarla
       * a una carpeta de crudos le deja dos archivos adentro sin decirlo — paso el 2026-09-21
       * sobre el material de un evento, y se descubrio contando la carpeta, no leyendo el
       * resumen. Un dato que esta en la respuesta y no en el resumen es un dato que no esta. */
      `\n→ ${destino}` +
      (paraPremiere ? `\n→ ${paraPremiere}` : "") +
      (srt ? `\n→ ${srt}` : "") +
      (cfg.destino ? "" : "\n   (sin `--destino` se escribe AL LADO DEL MEDIO)")
    );
  } finally {
    try { fs.rmSync(tmp, { recursive: true, force: true }); } catch (e) { /* era temporal */ }
  }
}

if (require.main === module) main().catch((e) => { console.error("FALLO: " + e.message); process.exit(1); });
module.exports = { palabrasDe, mapa, aPremiere, aSRT, aSecuencia, marcarFinDeFrase, MOTORES, ACHAQUES };
