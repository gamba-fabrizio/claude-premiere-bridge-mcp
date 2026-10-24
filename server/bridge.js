/**
 * El transporte: una carpeta compartida con el panel.
 *
 * El panel UXP no puede escuchar en un puerto —no abre sockets servidor—, así
 * que la dirección se invierte: el panel polea una carpeta y nosotros dejamos
 * el comando ahí. Feo, y anduvo a la primera.
 *
 * Tres cosas que salieron de medirlo en Premiere y no de suponerlas:
 *
 *  - Las rutas van CRUDAS. "Bridge Claude-Premiere" tiene un espacio y
 *    getEntryWithUrl lo acepta sin encodeURI. Se probaron las dos formas.
 *  - El panel ejecuta con Premiere adelante y el panel sin foco. UXP no frena
 *    su timer, así que el bridge funciona mientras editás, que es cuando tiene
 *    que funcionar.
 *  - El latido no es decoración. Si el panel está cerrado nadie contesta nunca,
 *    y un comando sin dueño se cuelga hasta el timeout. Mirando la frescura del
 *    latido se contesta "el panel no está abierto" en vez de esperar al pedo.
 */

const fs = require("fs/promises");
const path = require("path");

// Relativa al repo, no al home: mover el repo mueve la carpeta con él. El panel
// NO puede hacer lo mismo —vive adentro de Premiere y no sabe dónde está este
// código—, así que allá la ruta está escrita a mano. Si movés el repo, hay que
// editar RUTA_BRIDGE en plugin/index.js.
const CARPETA = path.join(__dirname, "..", "intercambio");

const ARCHIVO_COMANDO = path.join(CARPETA, "comando.json");
const ARCHIVO_RESPUESTA = path.join(CARPETA, "respuesta.json");
const ARCHIVO_LATIDO = path.join(CARPETA, "latido.json");

// El panel late una vez por segundo. Con 5s de margen, un latido viejo es una
// SOSPECHA: el panel cerrado, Premiere ocupado, o frenado por el sistema (abajo).
const MS_LATIDO_VIEJO = 5000;
// Cuánto se espera a que el latido AVANCE antes de darlo por muerto. Premiere
// ocupado puede tardar más de 10s por vuelta; abajo de eso no es un panel caído.
const MS_ESPERA_LATIDO = 25000;
const MS_TIMEOUT = 30000;
const MS_ENTRE_LECTURAS = 100;

let contador = 0;

function nuevoId() {
  contador += 1;
  return `${Date.now()}-${contador}`;
}

const dormir = (ms) => new Promise((r) => setTimeout(r, ms));

/**
 * Lee un JSON tolerando que esté a medio escribir.
 *
 * El panel escribe con createFile({overwrite:true}) y después write(), o sea que
 * entre las dos hay un instante donde el archivo existe y está VACÍO. Leerlo
 * justo ahí da un JSON inválido que no es un error: es una carrera normal, y lo
 * que corresponde es reintentar en la próxima vuelta.
 */
async function leerJson(ruta) {
  let texto;
  try {
    texto = await fs.readFile(ruta, "utf8");
  } catch (e) {
    return null; // todavía no existe
  }
  if (!texto.trim()) return null; // pillado a mitad de la escritura
  try {
    return JSON.parse(texto);
  } catch (e) {
    return null; // idem
  }
}

/** Hace cuánto que el panel no late, en ms. Infinity si nunca latió. */
async function edadDelLatido() {
  try {
    const stat = await fs.stat(ARCHIVO_LATIDO);
    return Date.now() - stat.mtimeMs;
  } catch (e) {
    return Infinity;
  }
}

async function asegurarCarpeta() {
  await fs.mkdir(CARPETA, { recursive: true });
}

/*
 * ¿MEDIA ENCODER ESTÁ ABIERTO? Lo ve el transporte y no el panel, que adentro de Premiere no puede listar
 * procesos (2026-10-01). `exportar` con `ame` decide si arranca la cola por la última línea del log de AME,
 * y el log no registra cuándo AME se abre o se cierra: si se cayó encodeando, queda un «Started» de una
 * sesión muerta. Se reconoce por su EJECUTABLE, como Premiere en `recargar.js`. `null` si `ps` no contestó,
 * y el panel lo trata como no saber: sigue creyéndole al log.
 */
function procesoAbierto(ejecutable) {
  try {
    const o = require("child_process").execFileSync("ps", ["-axo", "comm="], { encoding: "utf8", timeout: 5000 });
    return o.split("\n").some((l) => ejecutable.test(l.trim()));
  } catch (e) { return null; }
}
const ameAbierto = () => procesoAbierto(/\/Contents\/MacOS\/Adobe Media Encoder[^/]*$/);
/* Y Premiere, con el patrón de `recargar.js`: `pgrep -f` engancha al broker de IPC, que lleva la ruta de
   Premiere en sus argumentos y sobrevive al cierre. */
const premiereAbierto = () => procesoAbierto(/\/Contents\/MacOS\/Adobe Premiere Pro[^/]*$/);

/**
 * Manda un comando y espera la respuesta.
 *
 * Devuelve lo que contestó el panel. Tira si el panel no está abierto, si no
 * contesta a tiempo, o si contestó con un error — y en los tres casos el mensaje
 * dice QUÉ SE ENCONTRÓ, porque un "falló" pelado no se puede diagnosticar.
 */
/*
 * PREVUELO: lo que hay que comprobar EN EL DISCO antes de mandar el comando (2026-09-11).
 *
 * El panel NO PUEDE leer el disco —esta medido— asi que cualquier comprobacion de rutas
 * tiene que pasar de este lado. Y tiene que pasar ACA, en el transporte, y no en
 * `server/index.js`: las herramientas del repo usan el transporte DIRECTO y saltean las
 * herramientas MCP. Una guarda que solo vive en el despachador es una guarda que no esta
 * cuando la llama un script, que es exactamente como se pago esto.
 *
 * EL CASO QUE LO ORIGINO. `crearProyecto` con una ruta cuya CARPETA PADRE no existe no
 * falla: Premiere trunca la ruta y crea el proyecto un nivel mas arriba, con el nombre de
 * la carpeta que falta y SIN extension. Medido el 2026-09-11:
 *
 *   pedido  .../Proyectos/_CARPETA NUEVA/PROYECTO - BORRAR.prproj
 *   quedo   .../Proyectos/_CARPETA NUEVA          <- un gzip suelto, sin .prproj
 *
 * Y el verbo informa "CREO via createProject(ruta)" porque el proyecto activo SI cambio.
 * Es el modo de fallar numero 1 del CLAUDE.md: la API devuelve exito y hace otra cosa.
 * Ademas deja el proyecto viviendo suelto en la carpeta de proyectos, y con los scratch
 * en "Same as Project" eso saca un error de disco de rayado que no nombra la causa.
 *
 * El chequeo que ya existia en `index.js` mira el disco DESPUES de crear: informa el
 * daño, no lo evita.
 */
/* Cuanto tiene que estar quieto un archivo para importarlo (ver `importar`, abajo). */
const MS_ESCRIBIENDO = 5000;

/*
 * Que procesos tienen estos archivos abiertos PARA ESCRIBIR, con `lsof` en UNA llamada: [[ruta, quien]].
 * `lsof` sale con 1 cuando ninguno esta abierto, y eso es "nadie". Si no se pudo correr —no esta, vencio—
 * devuelve vacio: queda la fecha, y rebotar un import por no poder mirar seria rechazar uso correcto.
 */
function escritoresDe(rutas, lsof = require("fs").existsSync("/usr/sbin/lsof") ? "/usr/sbin/lsof" : "lsof") {
  /* `lsof` se puede pasar para probar la rama de "no se pudo correr". Y `fs` aca es el de promesas. */
  if (!rutas.length) return [];
  const { execFileSync } = require("child_process");
  let salida = "";
  try {
    salida = execFileSync(lsof, ["-F", "pcan", "--", ...rutas],
      { encoding: "utf8", timeout: 3000, stdio: ["ignore", "pipe", "ignore"] });
  } catch (e) {
    if (e && e.status === 1) salida = String(e.stdout || "");
    else return [];
  }
  const out = [];
  let pid = "?", cmd = "?", acceso = "";
  for (const l of salida.split("\n")) {
    const k = l[0], v = l.slice(1);
    if (k === "p") { pid = v; cmd = "?"; }
    else if (k === "c") cmd = v;
    else if (k === "a") acceso = v;
    else if (k === "n" && /[wu]/.test(acceso)) out.push([v, `"${cmd}" (pid ${pid})`]);
  }
  return out;
}

/*
 * Si ffprobe NO PUEDE ABRIR el archivo, el motivo; null si abre o si no se pudo mirar —no esta, vencio—,
 * porque no poder mirar no autoriza a rechazar el import. Solo en los contenedores donde ffprobe es
 * confiable y esta MEDIDO: lee el contenedor y no el codec, asi que un .mov sano con un codec que no conoce
 * abre igual, y sobre 313 medios reales de una carpeta de trabajo (2026-10-22) no rechazo ninguno. .mxf queda afuera: no
 * habia uno solo en los discos para medirlo. Fuera de la lista —MXF, BRAW, R3D, imagenes, proyectos— no se
 * mira. Se busca primero el de Homebrew: el servidor MCP no siempre arranca con su carpeta en el PATH.
 */
const EXT_CON_FFPROBE = /\.(mov|mp4|wav)$/i;
function noSeAbre(ruta, ffprobe = ["/usr/local/bin/ffprobe", "/opt/homebrew/bin/ffprobe"].find((r) => require("fs").existsSync(r)) || "ffprobe") {
  const { execFileSync } = require("child_process");
  try {
    execFileSync(ffprobe, ["-v", "error", "-show_entries", "format=format_name", "-of", "csv=p=0", ruta],
      { encoding: "utf8", timeout: 10000, stdio: ["ignore", "pipe", "pipe"] });
    return null;
  } catch (e) {
    if (!e || typeof e.status !== "number") return null;
    const motivo = String(e.stderr || "").split("\n")
      .map((l) => l.replace(/^\[[^\]]*\]\s*/, "").split(ruta + ":").join("").trim()).filter(Boolean);
    return motivo.length ? motivo.join(" · ") : `ffprobe salio con ${e.status}`;
  }
}
const PREVUELO = {
  /*
   * El panel NO VE EL DISCO. Relinkear a una ruta que no existe deja el medio apuntando a la
   * nada: Premiere lo marca offline recien al reproducir, y eso se lee como un problema del
   * archivo original. La comprobacion tiene que estar de este lado, y ANTES de mandar nada.
   */
  relink: (p) => {
    const fsx = require("fs");
    if (typeof p.ruta !== "string" || !p.ruta.trim()) return null;   /* lo rebota el verbo */
    if (!fsx.existsSync(p.ruta)) {
      return `"relink": el archivo "${p.ruta}" NO EXISTE en disco. Repuntar un medio a una ruta ` +
        `que no esta lo deja offline y Premiere recien lo avisa al reproducir. NO se ejecuto nada.`;
    }
    let st = null; try { st = fsx.statSync(p.ruta); } catch (e) { st = null; }
    if (st && st.isDirectory()) {
      return `"relink": "${p.ruta}" es una CARPETA, no un archivo. NO se ejecuto nada.`;
    }
    return null;
  },
  crearProyecto: (p) => {
    if (!p || typeof p.ruta !== "string" || !p.ruta.trim()) return null;   /* lo rebota el verbo */
    const fsx = require("fs"), px = require("path");
    const carpeta = px.dirname(p.ruta);
    let st = null;
    try { st = fsx.statSync(carpeta); } catch (e) { st = null; }
    if (!st || !st.isDirectory()) {
      return `"crearProyecto": la carpeta "${carpeta}" NO EXISTE, y Premiere NO falla por eso: ` +
        "trunca la ruta y crea el proyecto un nivel mas arriba, con el nombre de la carpeta " +
        "que falta y sin extension — despues informa que lo creo. Crea la carpeta primero. " +
        "NO se ejecuto nada.";
    }
    if (fsx.existsSync(p.ruta)) {
      return `"crearProyecto": ya existe un archivo en "${p.ruta}". NO se ejecuto nada: ` +
        "elegi otro nombre o borralo vos, para que no haya dudas de cual se piso.";
    }
    return null;
  },
  /*
   * EXPORTAR A UNA CARPETA QUE NO EXISTE (2026-10-19 y 21, un reporte de uso; medido el 2026-10-22). Con `ya`,
   * Premiere contesta "Invalid parameter" y nada mas, y se leyo como un problema de la «ñ» del nombre. Con
   * `ame` es peor: el verbo dice "encolado", la cola arranca y para en un segundo, y el error queda solo en
   * el log de Media Encoder ("The output destination could not be found"). Ninguno de los dos crea la
   * carpeta. Se rebota y no se crea: una ruta mal tipeada dejaria una carpeta suelta donde nadie la busca.
   */
  exportar: (p) => {
    if (!p || typeof p.salida !== "string" || !p.salida.trim()) return null;   /* lo rebota el verbo */
    const fsx = require("fs"), px = require("path");
    const carpeta = px.dirname(p.salida);
    let st = null;
    try { st = fsx.statSync(carpeta); } catch (e) { st = null; }
    if (!st || !st.isDirectory()) {
      return `"exportar": la carpeta de la salida "${carpeta}" NO EXISTE, y ni Premiere ni Media Encoder la ` +
        "crean: con `ya` contesta \"Invalid parameter\" sin decir por que, y con `ame` dice \"encolado\" y no " +
        "escribe nada. Creala primero. NO se ejecuto nada.";
    }
    return null;
  },
  /*
   * UN ARCHIVO QUE SE ESTA ESCRIBIENDO NO SE IMPORTA (2026-10-19, un reporte de uso). Un .mov que ffmpeg
   * todavia escribia saco el modal «File Import Failure»: el panel quedo trabado detras, la llamada
   * vencio a los 300 s y las dos siguientes a los 30.
   *
   * La FECHA de modificacion SOLA NO ALCANZA (medido el 2026-10-22): ffmpeg escribe en bloques de 256 KB,
   * y con poco bitrate paso 7 s sin tocar el archivo, asi que a los 5 s de quieto un .mov a medio escribir
   * pasaba. Lo que manda es si algun proceso lo tiene ABIERTO PARA ESCRIBIR (`lsof`, ~0,1 s); la fecha
   * queda para el que cierra y reabre entre escrituras. Sin esperas: el prevuelo es sincronico y una
   * espera aca frena todo comando. El que no existe lo cuenta el verbo.
   *
   * Y uno ROTO ya cerrado saca el MISMO modal, aunque se lo pida sin dialogos: medido el 2026-10-22 con un
   * .mov sin moov, la llamada espero 152 s hasta un clic en OK. Ese se mira con ffprobe (`noSeAbre`).
   */
  importar: (p) => {
    const fsx = require("fs");
    const rutas = typeof p.archivos === "string" ? [p.archivos] : (Array.isArray(p.archivos) ? p.archivos : []);
    const frescos = [], existen = [];
    for (const r of rutas) {
      let st = null; try { st = fsx.statSync(String(r)); } catch (e) { st = null; }
      if (!st || !st.isFile()) continue;
      existen.push(String(r));
      if (Date.now() - st.mtimeMs < MS_ESCRIBIENDO) {
        frescos.push(`"${r}" (cambio hace ${Math.max(0, (Date.now() - st.mtimeMs) / 1000).toFixed(1)} s)`);
      }
    }
    /* `lsof` da la ruta como la ve el sistema, que puede venir en otra normalizacion: se compara en NFC */
    for (const [ruta, quien] of escritoresDe(existen)) {
      const ya = frescos.some((f) => f.normalize("NFC").startsWith(`"${ruta.normalize("NFC")}"`));
      if (!ya) frescos.push(`"${ruta}" (lo tiene abierto para escribir ${quien})`);
    }
    if (frescos.length) {
      return `"importar": ${frescos.length === 1 ? "este archivo puede" : "estos archivos pueden"} estar ` +
        `escribiendose —cambio en los ultimos ${MS_ESCRIBIENDO / 1000} s, o un proceso lo tiene abierto para escribir—: ` +
        `${frescos.join(", ")}. ` +
        "Importar uno a medias saca un cartel modal en Premiere que traba el panel. Espera a que termine y " +
        "pedilo de nuevo. NO se ejecuto nada.";
    }
    const rotos = existen.filter((r) => EXT_CON_FFPROBE.test(r)).map((r) => [r, noSeAbre(r)]).filter(([, m]) => m);
    if (!rotos.length) return null;
    return `"importar": ffprobe no puede abrir ${rotos.length === 1 ? "este archivo" : "estos archivos"}: ` +
      rotos.map(([r, m]) => `"${r}" (${m})`).join(", ") + ". Importar uno asi saca el modal «File Import Failure», " +
      "que traba el panel hasta que alguien aprieta OK: pedirlo sin dialogos no lo apaga. Si Premiere si lo abre, " +
      "importalo a mano. NO se ejecuto nada.";
  },
};

/*
 * LA TRABA DEL REINICIO A MEDIAS (2026-09-11)
 *
 * El cartel de "guardar antes de cerrar" BLOQUEA el Cmd+Q y deja a Premiere a medio cerrar,
 * con el proyecto en el limbo. Y lo que lo vuelve peligroso de verdad: EL PANEL SIGUE
 * LATIENDO Y CONTESTANDO. Medido el 2026-09-11 — con el modal arriba, `estado` respondio
 * normal. Asi que desde este lado no se nota NADA y se sigue trabajando sobre un Premiere
 * que no esta sano, que es exactamente lo que paso: se borro una carpeta de proyecto
 * creyendo que ya estaba cerrado.
 *
 * `recargar.js` deja esta marca cuando pide el cierre y Premiere NO se va, y la borra cuando
 * el reinicio sale bien. Mientras exista, el transporte NO MANDA NADA. Es preferible que
 * TODO rebote con un mensaje claro a seguir escribiendo a ciegas: un cuelgue se nota, una
 * escritura sobre el proyecto equivocado no.
 *
 * Va en el TRANSPORTE por la misma razon que PREVUELO: las herramientas de este repo llaman
 * por aca y saltean las herramientas MCP, asi que una guarda puesta mas arriba no las cubre.
 */
const MARCA_TRABA = path.join(CARPETA, "reinicio-sin-terminar.json");

function leerTraba() {
  const fsx = require("fs");
  try { return JSON.parse(fsx.readFileSync(MARCA_TRABA, "utf8")); } catch (e) { return null; }
}

function ponerTraba(motivo) {
  const fsx = require("fs");
  try {
    fsx.mkdirSync(CARPETA, { recursive: true });
    fsx.writeFileSync(MARCA_TRABA, JSON.stringify({ cuando: new Date().toISOString(), motivo: String(motivo) }, null, 1));
    return true;
  } catch (e) { return false; }
}

function sacarTraba() {
  const fsx = require("fs");
  try { fsx.unlinkSync(MARCA_TRABA); return true; } catch (e) { return false; }
}

async function enviar(cmd, params = {}, msTimeout = MS_TIMEOUT) {
  /* ANTES que nada, incluso antes de PREVUELO: a un Premiere a medio cerrar no se le manda
     ni una comprobacion de parametros. */
  const traba = leerTraba();
  if (traba) {
    throw new Error(
      `TRABADO: el ultimo reinicio de Premiere NO TERMINO (${traba.cuando}).\n` +
      `Motivo: ${traba.motivo}\n` +
      `Lo mas probable es que haya un CARTEL abierto en Premiere —"guardar antes de cerrar"— ` +
      `bloqueando el Cmd+Q. El panel sigue latiendo igual, asi que no se nota desde aca, y ` +
      `seguir mandando comandos es trabajar sobre un proyecto en el limbo.\n` +
      `Resolvé el cartel en Premiere y despues: node herramientas/recargar.js --destrabar\n` +
      `NO se ejecutó "${cmd}".`
    );
  }
  if (PREVUELO[cmd]) {
    const problema = PREVUELO[cmd](params);
    if (problema) throw new Error(problema);
  }
  /* En el transporte y no en la herramienta MCP: los scripts del repo llaman por acá y saltean el servidor.
     Si quien llama ya lo dice, manda lo suyo. */
  if (cmd === "exportar" && params && params.modo === "ame" && params.ameAbierto === undefined) {
    params = Object.assign({}, params, { ameAbierto: ameAbierto() });
  }
  await asegurarCarpeta();

  /*
   * Un panel LENTO no es un panel MUERTO, y el chequeo confundía las dos cosas.
   *
   * La vuelta escribe el latido y normalmente tarda menos de un segundo, pero
   * con un proyecto grande recién abierto —conformando audio, generando picos—
   * llegó a tardar 11s. Con el umbral de 5s, las llamadas fallaban al azar según
   * cayeran antes o después del latido, y una tanda de cortes se cortaba por la
   * mitad. Pasó dos veces el 2026-08-16 editando el M1.
   *
   * Ahora, si el latido está viejo, se ESPERA a ver si avanza. Que avance
   * prueba que el panel vive; que no avance en todo ese rato es lo que antes
   * significaba el umbral.
   */
  let edad = await edadDelLatido();
  /*
   * Y "NO LATE" TIENE TRES CAUSAS, que piden cosas distintas (2026-10-07, un reporte de uso). Sin el proceso de
   * Premiere no hay a quién esperar: se dice al instante, en vez de 25 s después y como si el panel
   * estuviera cerrado. Con el proceso vivo, el latido viejo puede ser un panel cerrado, un Premiere colgado
   * o uno FRENADO por el sistema —tapado entero por otra ventana, oculto, el protector—, que late cada
   * tantos segundos y sigue ejecutando. Ese se distingue de afuera por la vuelta, que sube entre una
   * llamada y otra: el error la dice.
   */
  const vivo = edad > MS_LATIDO_VIEJO ? premiereAbierto() : true;
  if (vivo === false) {
    throw new Error(`Premiere NO está abierto: no hay proceso${edad === Infinity ? "" : `, y el último latido del panel es de hace ${Math.round(edad / 1000)} s`}. ` +
      `Abrilo con el proyecto: el panel arranca solo. NO se ejecutó "${cmd}".`);
  }
  if (edad > MS_LATIDO_VIEJO) {
    const marca = await leerJson(ARCHIVO_LATIDO);
    const vueltaAntes = marca && marca.vuelta;
    const hastaLatido = Date.now() + MS_ESPERA_LATIDO;
    while (Date.now() < hastaLatido) {
      await dormir(500);
      const ahora = await leerJson(ARCHIVO_LATIDO);
      if (ahora && vueltaAntes !== undefined && ahora.vuelta !== vueltaAntes) {
        edad = 0; // avanzó: está vivo, solo lento
        break;
      }
    }
  }
  if (edad > MS_LATIDO_VIEJO) {
    if (edad === Infinity) throw new Error("El panel del bridge nunca latió. Abrilo en Premiere: Window > Extensions > Claude Bridge.");
    const ultimo = await leerJson(ARCHIVO_LATIDO);
    throw new Error(
      `El panel del bridge no latió en ${Math.round(MS_ESPERA_LATIDO / 1000)}s de espera: el último latido es de hace ` +
      `${Math.round((await edadDelLatido()) / 1000)} s, vuelta ${ultimo && ultimo.vuelta !== undefined ? ultimo.vuelta : "?"}, ` +
      `y Premiere ${vivo ? "sigue corriendo" : "no se pudo mirar si sigue corriendo"}. ` +
      "Si en la llamada siguiente la vuelta subió, el panel vive y el sistema lo está FRENANDO —Premiere tapado entero " +
      "por otra ventana, oculto, o el protector de pantalla—: no es un crash, y se destraba con Premiere al frente. " +
      "Si no sube, el panel está cerrado o Premiere colgado."
    );
  }

  const id = nuevoId();
  await fs.writeFile(ARCHIVO_COMANDO, JSON.stringify({ id, cmd, params }, null, 2));

  const hasta = Date.now() + msTimeout;
  while (Date.now() < hasta) {
    await dormir(MS_ENTRE_LECTURAS);
    const r = await leerJson(ARCHIVO_RESPUESTA);
    if (r && r.id === id) {
      /*
       * El comando se BORRA una vez contestado.
       *
       * Al recargar el panel en UDT, su `ultimoId` vuelve a cero y lo primero
       * que hace es releer comando.json: si el archivo sigue ahí, ejecuta de
       * nuevo el último comando. Con verbos de lectura era una comodidad —se
       * usaba a propósito para disparar sondas con el Reload—, pero con verbos
       * que crean y borran es una repetición silenciosa. Pasó: un Reload creó
       * una segunda secuencia idéntica.
       */
      try { await fs.unlink(ARCHIVO_COMANDO); } catch (e) { /* ya no estaba */ }
      if (r.error) throw new Error(r.error);
      return r;
    }
  }

  /*
   * Y SE SACA TAMBIÉN AL VENCER, si sigue siendo ESTE (2026-10-01). Borrarlo sólo al contestar dejaba
   * afuera justo el caso de un Premiere que se cae con el comando adentro: el armado de 216 clips que lo
   * tiró quedó en la carpeta, y lo habría ejecutado el panel siguiente apenas cargara, o un Reload con el
   * proyecto abierto, que es cuando la repetición sí entra. Quien llama ya se rindió: que corra después
   * nunca es lo que espera. Si el panel lo está ejecutando, sacarlo no lo corta. Y si otro cliente
   * escribió encima, el comando ya no es este y no se toca.
   */
  const quedo = await leerJson(ARCHIVO_COMANDO);
  if (quedo && quedo.id === id) {
    try { await fs.unlink(ARCHIVO_COMANDO); } catch (e) { /* ya no estaba */ }
  }

  // Distinguir "se cayó mientras trabajaba" de "tardó" ayuda a decidir si
  // reintentar o ir a mirar Premiere.
  const edadFinal = await edadDelLatido();
  throw new Error(
    `El comando "${cmd}" no tuvo respuesta en ${Math.round(msTimeout / 1000)}s. ` +
    (edadFinal > MS_LATIDO_VIEJO
      ? "El panel dejó de latir mientras tanto: mirá si Premiere sigue vivo."
      : "El panel sigue latiendo, así que la operación está tardando o se colgó adentro de Premiere.")
  );
}

module.exports = { enviar, edadDelLatido, CARPETA, PREVUELO, escritoresDe, noSeAbre, ponerTraba, sacarTraba, leerTraba, ameAbierto, premiereAbierto };
