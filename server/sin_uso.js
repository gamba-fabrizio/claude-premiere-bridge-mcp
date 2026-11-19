/*
 * QUÉ MEDIOS DEL PROYECTO NO USA NINGUNA SECUENCIA (2026-11-16, un reporte de uso del 10/11). Sólo LEE.
 *
 * El verbo `usoDeMedios` contesta por tandas —las hojas del panel con su id, y los ids que traen los clips de unas
 * pocas secuencias por llamada—, para que ninguna llamada barra el proyecto. Acá se unen las tandas y se resta.
 *
 * Un falso «sin uso» termina en un medio borrado, así que el veredicto lleva sus CONTROLES POSITIVOS: si se leyeron
 * clips y ninguno de sus ids está en el panel, los ids no sirven para comparar y se rebota en vez de decir que todo
 * sobra; y lo que no se pudo leer —un ítem sin id, un clip sin medio— se cuenta aparte y se dice.
 *
 * EL ARCHIVO COMPARTIDO (2026-11-19, medido): un subclip y su fuente son dos ítems del panel con la MISMA ruta, y con
 * el subclip en el timeline la fuente figuraba sin uso. Sacar ese ítem del proyecto no rompe nada; borrar su ARCHIVO
 * rompe el subclip. Así que lo que no está en ninguna secuencia pero comparte archivo con algo que sí va aparte, en
 * `comparteArchivo`, nombrando con quién. Lo mismo vale para un archivo importado dos veces.
 *
 * Lo que la API sigue sin ver: un medio que sólo es la FUENTE de un multicámara o de un clip fusionado, sin medir.
 * Por eso el resumen lo avisa siempre.
 */
async function sinUsoDe(pedir) {
  const lista = await pedir({ listar: true });
  const hojas = Array.isArray(lista.hojas) ? lista.hojas : [];
  const enUso = {}, secuencias = [];
  let clips = 0, sinLeer = 0, desde = 0, vueltas = 0, total = null;
  while (desde !== null) {
    if (++vueltas > 500) throw new Error("`usoDeMedios` no termina de recorrer las secuencias: se cortó a las 500 tandas. No se concluyó nada.");
    const r = await pedir({ desdeSecuencia: desde, limite: 4 });
    for (const id of Object.keys(r.enUso || {})) enUso[id] = (enUso[id] || 0) + r.enUso[id];
    for (const s of r.secuencias || []) secuencias.push(s);
    clips += r.clips || 0; sinLeer += r.sinLeer || 0; total = r.total;
    if (r.siguiente !== null && r.siguiente !== undefined && !(r.siguiente > desde)) {
      throw new Error("`usoDeMedios` devolvió una tanda que no avanza: no se concluyó nada.");
    }
    desde = r.siguiente === undefined ? null : r.siguiente;
  }
  /*
   * LAS SECUENCIAS DEL PANEL QUE `getSequences` NO TRAE (2026-11-19, medido con el editor): la fuente de un
   * multicámara creado en el panel es una secuencia y no está en esa lista, así que sus cámaras figuraban sin uso.
   * Cada una se pide por su ítem (`deItem`); la que no se deja recorrer se NOMBRA y vuelve dudoso el resultado.
   */
  const recorridas = new Set(secuencias.map((s) => s.id).filter((id) => id !== null && id !== undefined));
  const porItem = [], sinRecorrer = [];
  for (const h of hojas) {
    if (h.esSecuencia !== true || h.id === null || h.id === undefined || recorridas.has(h.id)) continue;
    let r = null;
    try { r = await pedir({ deItem: h.id }); } catch (e) { r = null; }
    if (!r || r.recorrida !== true) { sinRecorrer.push(h.nombre); continue; }
    for (const id of Object.keys(r.enUso || {})) enUso[id] = (enUso[id] || 0) + r.enUso[id];
    clips += r.clips || 0; sinLeer += r.sinLeer || 0;
    porItem.push(h.nombre);
  }
  const idsPanel = new Set(hojas.map((h) => h.id).filter((id) => id !== null && id !== undefined));
  const usados = Object.keys(enUso);
  const reconocidos = usados.filter((id) => idsPanel.has(id)).length;
  if (clips > 0 && usados.length > 0 && reconocidos === 0) {
    throw new Error(`Se leyeron ${clips} clip(s) y NINGUNO de sus ${usados.length} medios aparece en el panel por id: ` +
      "los ids no sirven para comparar, y decir qué sobra sería adivinar. No se concluyó nada.");
  }
  if (clips > 0 && usados.length === 0) {
    throw new Error(`Se leyeron ${clips} clip(s) y de ninguno se pudo leer el medio: no se concluyó nada.`);
  }
  const medios = hojas.filter((h) => h.esSecuencia !== true);
  const sinId = medios.filter((h) => h.id === null || h.id === undefined);
  // Las rutas vienen en NFD y se comparan normalizadas; una hoja sin ruta legible no entra en esta cuenta.
  // Sólo una RUTA de verdad es un archivo: una capa de ajuste trae un código («1112293707»), el mismo en todas, y
  // dos capas distintas quedaban emparejadas como un mismo archivo (medido el 2026-11-19).
  const esRuta = (r) => typeof r === "string" && (/^\//.test(r) || /^[A-Za-z]:[\\/]/.test(r) || /^\\\\/.test(r));
  const clave = (r) => (esRuta(r) ? r.normalize("NFC") : null);
  const archivosEnUso = new Map();
  for (const h of medios) {
    const k = clave(h.ruta);
    if (k === null || h.id === null || h.id === undefined || !enUso[h.id]) continue;
    if (!archivosEnUso.has(k)) archivosEnUso.set(k, []);
    archivosEnUso.get(k).push(h.nombre);
  }
  const libres = medios.filter((h) => h.id !== null && h.id !== undefined && !enUso[h.id]);
  const sinUso = libres.filter((h) => !archivosEnUso.has(clave(h.ruta))).map((h) => ({ nombre: h.nombre, bin: h.bin }));
  const comparteArchivo = libres.filter((h) => archivosEnUso.has(clave(h.ruta)))
    .map((h) => ({ nombre: h.nombre, bin: h.bin, enUsoComo: archivosEnUso.get(clave(h.ruta)) }));
  const sinRuta = medios.filter((h) => !h.ruta).length;   // un sintético tiene código, no le falta la ruta
  const anidadas = hojas.filter((h) => h.esSecuencia === true && enUso[h.id]).map((h) => h.nombre);
  const fuera = usados.length - reconocidos;
  const dudoso = sinLeer > 0 || sinId.length > 0 || (lista.saltados || 0) > 0 || sinRecorrer.length > 0;
  const fusionados = medios.filter((h) => h.esFusionado === true).map((h) => h.nombre);
  return {
    resumen:
      `${sinUso.length} de ${medios.length} medio(s) no están en ninguna de las ${secuencias.length} secuencia(s) ` +
      `(${clips} clip(s) leídos en ${vueltas} tanda(s))` +
      (sinUso.length ? `: ${sinUso.slice(0, 30).map((m) => `"${m.nombre}"` + (m.bin && m.bin !== "(raíz)" ? ` [${m.bin}]` : "")).join(", ")}` +
        (sinUso.length > 30 ? ` y ${sinUso.length - 30} más (la lista entera va en \`sinUso\`)` : "") : "") +
      (comparteArchivo.length ? ` · ${comparteArchivo.length} más no están en ninguna secuencia pero su ARCHIVO sí se usa, por otro ítem ` +
        `—un subclip o una copia—: se pueden sacar del proyecto, el archivo NO se borra: ` +
        comparteArchivo.slice(0, 10).map((m) => `"${m.nombre}" (en uso como "${m.enUsoComo[0]}")`).join(", ") +
        (comparteArchivo.length > 10 ? ` y ${comparteArchivo.length - 10} más` : "") : "") +
      (porItem.length ? ` · ${porItem.length} secuencia(s) que la lista de secuencias no trae —fuentes de multicámara— se leyeron desde su ítem: ${porItem.slice(0, 8).join(", ")}` : "") +
      (sinRecorrer.length ? ` · OJO: ${sinRecorrer.length} secuencia(s) del panel NO SE PUDIERON RECORRER: ${sinRecorrer.slice(0, 8).join(", ")} — lo que sólo usan ellas figura sin uso y NO lo está` : "") +
      (fusionados.length ? ` · hay ${fusionados.length} clip(s) fusionado(s) (${fusionados.slice(0, 5).join(", ")}): sus fuentes figuran sin uso y no lo están` : "") +
      (anidadas.length ? ` · secuencias anidadas en otra: ${anidadas.slice(0, 10).join(", ")}` : "") +
      (sinLeer ? ` · OJO: ${sinLeer} clip(s) sin medio legible: algo de la lista PUEDE estar en uso` : "") +
      (sinId.length ? ` · OJO: ${sinId.length} medio(s) sin id, que no se pudieron juzgar: ${sinId.slice(0, 5).map((h) => h.nombre).join(", ")}` : "") +
      (lista.saltados ? ` · OJO: ${lista.saltados} ítem(s) del panel no se pudieron leer` : "") +
      (fuera ? ` · ${fuera} medio(s) en uso que no están en el panel` : "") +
      (sinRuta ? ` · ${sinRuta} medio(s) sin ruta legible: de ésos no se sabe si comparten archivo con otro` : "") +
      " · NO ve lo que sólo es FUENTE de un clip fusionado: figura sin uso y no lo está. " +
      "Es lo que hay en Premiere AHORA, guardado o no. Sólo lee: no saca nada.",
    sinUso: sinUso, comparteArchivo: comparteArchivo, sinRuta: sinRuta, total: medios.length, secuencias: secuencias.length, clips: clips, tandas: vueltas,
    sinLeer: sinLeer, sinId: sinId.map((h) => h.nombre), anidadas: anidadas, dudoso: dudoso,
    leidasPorItem: porItem, sinRecorrer: sinRecorrer, fusionados: fusionados
  };
}

module.exports = { sinUsoDe };
