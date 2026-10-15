/*
 * LAS `instructions` DEL SERVIDOR MCP: el texto que Claude Code le pone delante al modelo en TODA
 * sesión que tenga el bridge registrado, al arrancar y aunque las herramientas queden diferidas.
 *
 * Hasta el 2026-10-15 el servidor no mandaba ninguna, y las advertencias le llegaban al modelo solo
 * por el CLAUDE.md global de esta máquina, que es personal: el repo público se registra con
 * `--scope user` y le daba a cualquiera 60 herramientas que escriben en su timeline sin una sola
 * advertencia. Y la copia del global ya había quedado vieja: decía que a 1,2 s Premiere no se cae y
 * no nombraba lo ACUMULADO, que lo tiró a ese ritmo el 2026-09-27.
 *
 * Por eso salen de USO.md al arrancar y no de una copia: su sección «Antes de la primera llamada»,
 * entera, y la ruta del USO.md de ESTA copia del repo, que en otra instalación es otra.
 *
 * TOPE: Claude Code corta las instructions a 2.048 caracteres hasta la 2.1.295 —la que usa la app
 * de escritorio en esta máquina, al 2026-10-15, leído en su binario— y a 4.096 desde la 2.1.296.
 * Corta por el FINAL y le pega «… [truncated]», y lo último de la sección es lo ACUMULADO. `test.js`
 * exige el tope viejo. Y no hay que repetirlas en otro lado para que duren: Claude Code las vuelve a
 * anunciar después de cada compactación (medido en los transcripts, 2.1.280 a 2.1.295).
 */
const fs = require("fs");
const path = require("path");

const RUTA_USO = path.join(__dirname, "..", "USO.md");
const SECCION = "## Antes de la primera llamada";
const TOPE_INSTRUCCIONES = 2048;

/** El cuerpo de una sección `## ` de un markdown, hasta la `## ` siguiente; null si falta o está vacía. */
function seccionDe(texto, titulo) {
  const lineas = String(texto).split("\n");
  const i = lineas.findIndex((l) => l.trim() === titulo);
  if (i < 0) return null;
  let fin = i + 1;
  while (fin < lineas.length && !/^## /.test(lineas[fin])) fin++;
  return lineas.slice(i + 1, fin).join("\n").trim() || null;
}

/** `texto` es el USO.md, o null si no se pudo leer. Nunca devuelve vacío: si falta algo, lo dice. */
function instruccionesDe(texto, ruta) {
  const cabeza =
    "premiere-bridge opera Adobe Premiere Pro: lee y ESCRIBE el proyecto real del editor. " +
    "Antes de la primera llamada invocá la skill `premiere`, que es " + ruta +
    "; si no la tenés, leé ese archivo entero. Cada regla salió de un crash o de material roto.";
  if (texto == null)
    return cabeza + "\n\nNo pude leer ese archivo al arrancar: buscá el USO.md del repo del bridge antes de llamar.";
  const seccion = seccionDe(texto, SECCION);
  if (!seccion)
    return cabeza + "\n\nEse archivo no tiene la sección «" + SECCION.slice(3) + "»: leelo entero antes de llamar.";
  return cabeza + " Lo mínimo, de ahí:\n\n" + seccion;
}

/** Las de esta copia del repo, leídas de su USO.md. No tira: el servidor arranca igual sin USO.md. */
function instrucciones() {
  let texto = null;
  try {
    texto = fs.readFileSync(RUTA_USO, "utf8");
  } catch (e) {
    // instruccionesDe dice que no se pudo leer
  }
  return instruccionesDe(texto, RUTA_USO);
}

module.exports = { instrucciones, instruccionesDe, seccionDe, RUTA_USO, SECCION, TOPE_INSTRUCCIONES };
