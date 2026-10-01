/**
 * El lado panel del bridge: latir, leer comandos, ejecutar, contestar.
 *
 * Lo único que hace es polear una carpeta. La lógica de Premiere vive en
 * lib/comandos.js; acá está el transporte y nada más.
 *
 * El latido merece una explicación porque parece un adorno y no lo es: si el
 * panel está cerrado, un comando se queda sin dueño y el servidor espera hasta
 * el timeout sin saber por qué. Escribiendo la vuelta a un archivo, el servidor
 * mira la frescura ANTES de mandar nada y contesta "el panel no está abierto"
 * al instante. Verificado: UXP no frena este timer cuando el panel pierde el
 * foco, así que el bridge sigue vivo mientras editás — que es cuando hace falta.
 */

/*
 * OJO: acá NO se declara `uxp` ni `ppro`. Los <script> comparten un solo scope
 * global, así que un segundo `const uxp` es SyntaxError y mata este archivo
 * entero — el panel dibuja el HTML y el timer no arranca nunca. Las constantes
 * las declara lib/comandos.js, que se carga primero; acá se usan de ahí.
 */

/*
 * Absoluta y escrita a mano: el panel corre adentro de Premiere y no tiene forma
 * de saber dónde está el repo. Si movés el repo, esta línea se actualiza a mano
 * (del lado del servidor la ruta sale sola de __dirname).
 */
const RUTA_BRIDGE = "/RUTA/ABSOLUTA/A/TU/COPIA/premiere-bridge/intercambio";   // <-- EDITAR
const MS_POLL = 200;

/*
 * CUANDO SE CARGO ESTE CODIGO. Va en el latido, que ya se escribe una vez por segundo, asi que
 * no cuesta una llamada ni un verbo nuevo.
 *
 * Sirve para una sola cosa y es importante: saber si un Reload ENTRO. Cada cambio en `plugin/`
 * necesita recargar, y si el reload no ocurrio —el clic no encontro el boton, UDT estaba en otra
 * pestana— las pruebas siguientes corren contra el codigo VIEJO y parecen decir otra cosa. Es el
 * modo de fallar numero uno del CLAUDE.md: dar por bueno algo que no paso.
 *
 * Comparando esto contra la fecha de modificacion de `comandos.js` se sabe, sin preguntarle a
 * nadie, si lo que esta corriendo incluye la ultima edicion.
 */
const CARGADO_EN = Date.now();

let carpeta = null;
let vueltas = 0;
let ultimoTexto = "";
let ultimoId = null;
let ocupado = false;
/*
 * UN COMANDO QUE YA ESTABA AL CARGAR NO SE EJECUTA (2026-10-01). `ultimoId` vive en memoria y un panel
 * nuevo arranca en null, así que lo primero que hacía era ejecutar el `comando.json` que hubiera. El
 * transporte lo borra cuando le llega la respuesta, pero no si se cae Premiere o se muere el cliente
 * con el comando adentro: el armado de 216 clips que tiró Premiere quedó en la carpeta, y al reabrir
 * el panel lo habría repetido. El transporte sólo escribe un comando después de ver latir a un panel,
 * y este escribe su primer latido antes de su primera lectura: lo que hay en esa lectura lo escribió
 * alguien para el panel anterior. Se marca como visto y no se ejecuta; si su cliente seguía
 * esperando, le vence la espera, que es un error que se ve, en vez de una repetición que no.
 */
let primeraLectura = true;

const elLatido = document.getElementById("latido");
const elEstado = document.getElementById("estado");
const elUltimo = document.getElementById("ultimo");

/*
 * EL DOM SE TOCA LO MENOS POSIBLE, y solo si el texto cambió (PROPUESTA 2026-09-30, sin medir).
 * Cuatro crashes del 2026-09-29 cayeron en el HILO PRINCIPAL, en el código que dibuja la UI, con
 * Premiere en segundo plano; el de las 23:14 adentro de `torq` (el motor de los paneles UXP)
 * desarmando un árbol de nodos, y el de las 19:28 en CoreText adentro de `torq` (un reporte de uso). Cada
 * `textContent =` saca el nodo de texto viejo y arma uno nuevo, y hasta acá pasaba cinco veces por
 * segundo en el latido, más el resumen entero —a veces cientos de caracteres en `pre-wrap`— en
 * cada comando. El latido va al disco igual: la pantalla es para el editor, no para el servidor.
 */
const MAX_TEXTO_PANEL = 160;
const CADA_VUELTAS_PANEL = 25;   // ~5 s con MS_POLL 200
const CADA_VUELTAS_LATIDO = 5;   // el latido al disco: ~1 por segundo con MS_POLL 200
function mostrar(el, texto) {
  const corto = texto.length > MAX_TEXTO_PANEL ? texto.slice(0, MAX_TEXTO_PANEL) + "…" : texto;
  if (el.textContent !== corto) el.textContent = corto;
  console.log("[bridge]", texto);
}

/*
 * La carpeta se abre con la URL CRUDA aunque el nombre tenga un espacio —
 * medido en Premiere, contra la alternativa de encodeURI. Igual se prueban las
 * dos y se informa cuál anduvo: si algún día cambia, el panel lo dice en vez de
 * fallar en silencio.
 */
async function abrirCarpeta() {
  const fs = uxp.storage.localFileSystem;
  const formas = [
    ["crudo", "file:" + RUTA_BRIDGE],
    ["encodeURI", "file:" + encodeURI(RUTA_BRIDGE)]
  ];
  const fallos = [];
  for (let i = 0; i < formas.length; i++) {
    try {
      const e = await fs.getEntryWithUrl(formas[i][1]);
      if (e) { mostrar(elEstado, "Carpeta abierta (" + formas[i][0] + ")"); return e; }
    } catch (err) {
      fallos.push(formas[i][0] + ": " + (err && err.message ? err.message : err));
    }
  }
  throw new Error("No se pudo abrir " + RUTA_BRIDGE + " — " + fallos.join(" | "));
}

async function escribir(nombre, obj) {
  const f = await carpeta.createFile(nombre, { overwrite: true });
  await f.write(JSON.stringify(obj, null, 2));
}

async function leerComando() {
  const archivo = await carpeta.getEntry("comando.json"); // tira si no está
  return await archivo.read();
}

async function vuelta() {
  vueltas++;

  if (!carpeta) {
    try { carpeta = await abrirCarpeta(); }
    catch (e) { mostrar(elEstado, e.message); return; }
  }

  // El latido va SIEMPRE, incluso mientras se ejecuta un comando largo: es la
  // señal de que Premiere sigue respondiendo. Si dejara de latir durante una
  // exportación, el servidor lo leería como panel caído.
  //
  // Pero UNA VEZ POR SEGUNDO y no en cada vuelta (2026-09-30, PROPUESTA SIN MEDIR). Escribirlo es
  // `createFile` + `write`, y cada uno crea un objeto nativo que después limpia el recolector: a cinco
  // vueltas por segundo eran unos 36.000 por hora sólo del latido, y cinco de los crashes de la noche
  // del 2026-09-29 cayeron en la recolección de esos envoltorios (`UserWeakCallback`, en el hilo de
  // scripts). El servidor lo da por muerto a los 5 s, así que un segundo sobra. El poleo de comandos
  // sigue en cada vuelta: la latencia no cambia.
  if (vueltas % CADA_VUELTAS_LATIDO === 1) {
    try { await escribir("latido.json", { vuelta: vueltas, cargadoEn: CARGADO_EN }); }
    catch (e) { mostrar(elEstado, "No se pudo escribir el latido: " + e.message); return; }
  }

  if (vueltas % CADA_VUELTAS_PANEL === 0) mostrarLatido();

  if (ocupado) return;

  let crudo;
  try { crudo = await leerComando(); }
  catch (e) { primeraLectura = false; return; } // sin comando.json no hay nada que hacer: es lo normal

  if (crudo === ultimoTexto) return;
  ultimoTexto = crudo;

  let comando;
  try { comando = JSON.parse(crudo); }
  catch (e) { return; } // pillado a mitad de la escritura; la próxima vuelta lo agarra

  if (!comando || !comando.id || comando.id === ultimoId) return;
  ultimoId = comando.id;

  if (primeraLectura) {
    primeraLectura = false;
    mostrar(elUltimo, comando.cmd + " · NO se ejecutó: estaba pendiente de antes de cargar el panel");
    return;
  }

  ocupado = true;
  let respuesta;
  try {
    const datos = await ejecutar(comando.cmd, comando.params);
    respuesta = Object.assign({ id: comando.id, cmd: comando.cmd }, datos);
    mostrar(elUltimo, comando.cmd + " · " + datos.resumen);
  } catch (e) {
    respuesta = {
      id: comando.id,
      cmd: comando.cmd,
      error: e && e.message ? e.message : String(e)
    };
    mostrar(elUltimo, comando.cmd + " · ERROR: " + respuesta.error);
  }
  ocupado = false;

  try { await escribir("respuesta.json", respuesta); }
  catch (e) { mostrar(elEstado, "No se pudo escribir la respuesta: " + e.message); }
}

/*
 * El timer se APAGA cuando el plugin se descarga, y no es prolijidad.
 *
 * Recargando desde UDT, Premiere crasheó con este reporte:
 *
 *   sourceFile      dvauxphost/queue/src/JsTaskQueue.cpp
 *   sourceFunction  JsTaskQueue::execute(...)
 *   threadName      dvascripting::Transient2
 *   UXPPlugin IDs   com.<usuario>.premierebridge
 *
 * O sea: el host de UXP ejecutando una tarea JS encolada de ESTE plugin
 * mientras lo desmontaba. El `setInterval` seguía disparando durante la
 * descarga y una vuelta corría contra un contexto ya muerto.
 *
 * `beforeunload` es lo que UXP dispara al descargar el panel. Si algún día
 * dejara de dispararse, la guarda de `desmontado` adentro de la vuelta sigue
 * evitando el trabajo pesado — por eso están las dos y no una.
 */
let latidoMostrado = "";
function mostrarLatido() {
  const t = ocupado ? "ejecutando…" : "latiendo (vuelta " + vueltas + ")";
  if (t !== latidoMostrado) { elLatido.textContent = t; latidoMostrado = t; }
}

let desmontado = false;
const timer = setInterval(() => {
  if (desmontado) return;
  vuelta().catch((e) => mostrar(elEstado, "La vuelta falló: " + (e && e.message ? e.message : e)));
}, MS_POLL);

function desmontar() {
  if (desmontado) return;
  desmontado = true;
  try { clearInterval(timer); } catch (e) { /* ya no importa */ }
}

try { window.addEventListener("beforeunload", desmontar); } catch (e) { /* si no existe, queda la guarda */ }
try { window.addEventListener("unload", desmontar); } catch (e) { /* idem */ }

mostrar(elEstado, "Arrancando…");
