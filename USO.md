# Usar el bridge

Para las sesiones que OPERAN Premiere desde un trabajo, no para editar el bridge: eso se hace en
una sesión abierta en el repo, con su `CLAUDE.md`. Es corto a propósito, así que se lee entero.
Cada regla salió de un daño real; el caso completo está en `docs/bitacora/`, y el índice por tema
en `CLAUDE.md`.

## Antes de la primera llamada

- **El panel tiene que estar abierto en Premiere.** El plugin está instalado y arranca con
  Premiere. Si las herramientas fallan al instante con "el panel nunca latió", no hay panel: se le
  dice al editor, no se insiste.
- **Todo opera sobre el proyecto CON FOCO y su secuencia ACTIVA**, no sobre la carpeta de la
  sesión. `estado` empieza por el nombre del proyecto: leelo. En toda llamada que escriba pasá
  `proyecto` —y `secuencia` si hay dos parecidas—: rebota si no coinciden, o si el nombre parcial
  engancha más de una. Las herramientas de `herramientas/` lo deducen solas.
- **Si el editor está trabajando en Premiere, no operes sin que te lo pida.**
- **Guardá (`premiere_guardar`) antes y después de cada tanda.** Es lo que volvió gratis cada crash.
- **Lo que no usaste nunca, o una tanda grande, se prueba primero en un proyecto de prueba**
  descartable, no en el del editor.
- **Si encadenás escrituras a mano, espaciadas**: a ~200 ms entre transacciones Premiere se cae, y
  el borde baja con los proyectos pesados. Las herramientas ya espacian.

## Cómo leer lo que contesta

- **Cada verbo devuelve qué encontró, no si salió bien, y el veredicto sale de RELEER el estado**
  —`clips`, `revisar`, un `frame`—, no del mensaje. Esta API acepta escrituras que no aplica, y a
  veces "NO CAMBIÓ NADA" es la respuesta correcta.
- **`insertar` se juzga por `entro`.** Con `entro !== true` no edites el clip que haya en ese
  punto: puede ser uno viejo del mismo medio.
- **`frame` es la mejor verificación: mirá en vez de deducir.** Y cuando importa, MEDÍ el cuadro
  (la media): un negro y un vacío se ven iguales, y el visor muestra un PNG transparente como
  blanco.
- **`revisar` después de cada tanda**: ceros, solapes, huecos en cuadros, juntas, y pistas con la
  salida apagada. Verificar cada paso no verifica la tanda.
- **Un parámetro inventado rebota** nombrando los que acepta. Antes de concluir que un verbo está
  roto, leé su firma; y si el editor dice que "siempre funcionó", el problema es la llamada.
- **Un dato que está en la respuesta y no en el resumen también cuenta**: `medios` tiene tope de 60
  e informa `total`; leé el campo, no el largo de la lista.

## Trampas por verbo, medidas

- **`fijar` fija un valor; `keyframe` ANIMA** en el playhead. Sobre un param ya animado, `fijar`
  escribe el valor base y la animación lo tapa.
- **`editar salida` es un punto de FUENTE, no una duración.** Un PNG o un Transparent Video entran
  con in-point ~3600: leé la `entrada` real y sumale la duración. Y **`editar entrada` además
  MUEVE el clip**: la entrada en una llamada y `desde` en otra.
- **`borrar` y `editar` arrastran el audio vinculado**, que se deduce por medio y rango iguales.
  `desactivar` y el `apagado` de las capas apagan también el audio socio: TODOS los streams de un
  medio multicanal. Si dos planos del mismo medio están en el mismo instante y el in-point no
  desempata, no lo tocan y lo dicen.
- **`pistaAudio` es 1-based (A1 es 1)**: 0 rebota, y una que no existe se crea, pero UNA y al final:
  pidiendo A9 con seis, el audio cae en A7 (`pistaAudioReal` dice dónde quedó). El overwrite PISA
  también en audio, así que dos cosas en la misma pista y posición se comen.
- **Un medio sin video no pone nada en V**: su clip se busca en la pista de audio.
- **`borrar` rebota desde el 6º borrado en 60 s.** Vaciar una pista es seleccionarla y Delete en
  Premiere, o `borrarSecuencia` + `armarSecuencia`. Nunca barrerla, y menos con solapes: tiró
  Premiere.
- **`armarSecuencia` crea aunque el nombre exista**, no reemplaza. `fragmentos` son
  `{desde, hasta, medio}` en segundos de FUENTE; `capas`, `{en, dura, pista, medio, desde,
  pistaAudio}`. Pone los fps y el formato del reloj que les toca, y lo relee: si no entra, lo
  dice. Y Premiere corta el nombre después del último punto: `secuencia` trae el que quedó. Si se
  corta a mitad, el error dice qué secuencia dejó y con cuántos fragmentos y capas.
- **`borrar_secuencia` elige por el nombre EXACTO**; si coinciden varias rebota, y dos con el mismo
  nombre se eligen con `duracion`. Dos gemelas —mismo nombre y mismo largo— se borran a mano.
- **`marcar` cuantiza al cuadro.** Con `clip`, el marcador va al MEDIO: `segundos` es tiempo de
  fuente y aparece en toda instancia de ese material.
- **`transicion` es solo video** —el crossfade de audio va a mano— y no se puede releer: el conteo
  prueba que apareció, no que esté bien puesta.
- **`copiarEfecto` NO copia: COMPARTE la instancia.** Tocar el destino cambia el origen, en otra
  secuencia y sin aviso. Para una copia independiente, `clonar` (el clip entero) o Cmd+C / Cmd+V.
  Opacity y Blend Mode viven en el componente Opacity y se fijan aparte.
- **`exportar` en modo `ya`**, que es el único que se confirma. El preset H.264 va de la carpeta
  `4E49434B_48323634`: el mismo nombre en la de QuickTime escribe `.mov`. Respeta los in/out de la
  secuencia, que `limpiarRangos` saca. Y el archivo se mide de afuera: duración por stream y
  paquetes de video.
- **La escala de un medio que ya está en la secuencia se lee con `leerEscalas`**, no se calcula de
  las dimensiones del archivo. `escalaFija` va de a 30 clips (`limite` y `siguiente`): sin tope,
  sobre material 4K pesado, tiró Premiere.
- **Las capas de ajuste no se crean por API y no se escalan**: se inserta una que ya exista, y
  escalada la corrección queda en un rectángulo.
- **`relink` no tiene Cmd+Z**, y `clonar` puede crear pistas de video que nada borra.
- **Los proxies no tienen `detachProxy`**: no adjuntes uno que viva en una carpeta temporal.
- **Las rutas que devuelve la API vienen en NFD**: pasalas tal cual, nunca retipeadas.
- **`cerrar_proyecto` guarda antes de cerrar y no descarta nunca.** No cierra el último abierto ni
  uno cuyo `.prproj` ya no está en disco —guardarlo abriría un cartel que el panel no ve—: esos los
  cierra el editor. Si el que cerrás tenía el foco, el foco se va solo a otro, y el resumen dice a
  cuál.

## Lo que NO se hace por el bridge

- Barrer o vaciar pistas: ver `borrar`, arriba.
- Leer valores de efectos en volumen: tiró Premiere cuatro veces.
- Replicar un look para retocarlo después: Cmd+C / Cmd+V, ver `copiarEfecto`.
- Importar una transcripción o crear captions: el Import del panel Text, a mano.
- Cerrar un proyecto DESCARTANDO sus cambios, tampoco por el transporte directo: lo decide el
  editor, a mano.
- Formatos de intercambio (AAF, FCPXML, OTIO): a mano, porque pierden cosas en silencio.

## Premiere y la máquina

- **Nunca `pkill` a Premiere.** Cerrar y reabrir es `node herramientas/recargar.js --reiniciar`:
  guarda todos los proyectos abiertos, cierra con el macro y exige que el panel vuelva.
- **Un panel, un cliente por vez.** Mientras una tanda corre, el avance se mira en el disco o en el
  log: preguntarle al panel en el medio le hace vencer una llamada a la tanda.
- **Mirar la pantalla contesta en segundos, pero SOLO la ventana de Premiere**: el número de
  ventana sale de `CGWindowListCopyWindowInfo` y se captura con `screencapture -x -o -l <n>`. Los
  otros monitores pueden tener cosas privadas.
- **Con la pantalla bloqueada no entra ningún macro de Keyboard Maestro**, y con el Privacy Mode de
  Jump fallan los que buscan por imagen. Los dos fallan callados.

## Las herramientas

```
colocar_fragmentos.js    coloca los fragmentos de una propuesta, por lote, y relee cada uno
colocar_propuesta.js     coloca una propuesta de corte con sus suplentes
colocar_sincro.js        coloca los tramos que detectó `sincro.py --segmentos`
desde_secuencia.js       convierte el timeline del editor en la propuesta: su edición manda
quirurgico.js            guarda el trabajo manual de una pista y lo repone tras reconstruirla
parchear_corte.py        aplica correcciones a un plan sin replanificar lo que no se criticó
revisar_medios.js        los defectos del material antes de armar: rotación, fps, resoluciones
sincro.py                el offset de cada clip contra el tema, por audio
grilla_angulos.js        qué muestra cada ángulo en cada instante del tema
audio.js                 transcribe (`--motor premiere|scribe|whisper`). No pisa la de otro
                         motor: rebota antes de transcribir (`--pisar` la reemplaza)
cotejar_transcripcion.js dónde discrepan dos transcripciones: la lista de lo que hay que oír
fusionar_transcripcion.js un borrador fusionado, con la fuente de cada palabra
proxies.js               genera o adjunta proxies (`--perfil prores|h264`, `--proxies <carpeta>`)
locucion.js, musica.js,  ElevenLabs. La key sale solo de $ELEVENLABS_API_KEY, y se consulta
sonido.js                antes de gastar créditos
recargar.js              recarga o reinicia Premiere y comprueba que el panel volvió
```

## Si encontrás un bug del bridge

**No lo arregles desde una sesión que lo está usando**: el arreglo corre los tests y lleva
reinstalar el plugin y reiniciar Premiere, y eso se hace desde el repo. Anotá qué pediste, qué
contestó y qué había de verdad, y avisale a quien esté usando Premiere.
