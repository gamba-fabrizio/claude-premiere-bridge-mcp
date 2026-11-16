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
 * Lo que la API NO ve: un medio que sólo es la FUENTE de un subclip, de un multicámara o de un clip fusionado figura
 * sin uso, porque en el timeline está el derivado. Por eso el resumen lo avisa siempre.
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
  const sinUso = medios.filter((h) => h.id !== null && h.id !== undefined && !enUso[h.id])
    .map((h) => ({ nombre: h.nombre, bin: h.bin }));
  const anidadas = hojas.filter((h) => h.esSecuencia === true && enUso[h.id]).map((h) => h.nombre);
  const fuera = usados.length - reconocidos;
  const dudoso = sinLeer > 0 || sinId.length > 0 || (lista.saltados || 0) > 0;
  return {
    resumen:
      `${sinUso.length} de ${medios.length} medio(s) no están en ninguna de las ${secuencias.length} secuencia(s) ` +
      `(${clips} clip(s) leídos en ${vueltas} tanda(s))` +
      (sinUso.length ? `: ${sinUso.slice(0, 30).map((m) => `"${m.nombre}"` + (m.bin && m.bin !== "(raíz)" ? ` [${m.bin}]` : "")).join(", ")}` +
        (sinUso.length > 30 ? ` y ${sinUso.length - 30} más (la lista entera va en \`sinUso\`)` : "") : "") +
      (anidadas.length ? ` · secuencias anidadas en otra: ${anidadas.slice(0, 10).join(", ")}` : "") +
      (sinLeer ? ` · OJO: ${sinLeer} clip(s) sin medio legible: algo de la lista PUEDE estar en uso` : "") +
      (sinId.length ? ` · OJO: ${sinId.length} medio(s) sin id, que no se pudieron juzgar: ${sinId.slice(0, 5).map((h) => h.nombre).join(", ")}` : "") +
      (lista.saltados ? ` · OJO: ${lista.saltados} ítem(s) del panel no se pudieron leer` : "") +
      (fuera ? ` · ${fuera} medio(s) en uso que no están en el panel` : "") +
      " · NO ve lo que sólo es FUENTE de un subclip, un multicámara o un clip fusionado: figura sin uso y no lo está. " +
      "Es lo que hay en Premiere AHORA, guardado o no. Sólo lee: no saca nada.",
    sinUso: sinUso, total: medios.length, secuencias: secuencias.length, clips: clips, tandas: vueltas,
    sinLeer: sinLeer, sinId: sinId.map((h) => h.nombre), anidadas: anidadas, dudoso: dudoso
  };
}

module.exports = { sinUsoDe };
