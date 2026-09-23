# La API de Premiere, medida

Las firmas y los comportamientos de la API de UXP de Premiere que costó medir. Casi ninguno se
deduce del nombre del método, y varios son contraintuitivos: no hay razor, `createSetInPointAction`
además corre el clip, el tercer argumento de `createRemoveItemsAction` es un `MediaType`.

> Estas secciones vivían en el `README.md` y se mudaron TAL CUAL el 2026-09-23, un nivel más arriba
> y con el mismo título. Donde el texto había quedado viejo, lo dice una nota de corrección al
> principio de la sección, en vez de reescribirlo.

## Importar la transcripción: por la interfaz SÍ, por la API todavía no (2026-08-17)

**El camino que funciona, verificado de punta a punta:** panel Text → pestaña
Transcript → **Import**, con el clip seleccionado, eligiendo el `.premiere.json`
que genera la herramienta. Premiere lo acepta y después `premiere_transcripcion`
lo lee: entraron 4 segmentos y 89 palabras, con los tiempos intactos.

Eso confirma tres cosas que antes eran suposiciones: el esquema que generamos es
correcto, el `speaker` con un UUID inventado no molesta, y **el único paso manual
es un Import** — no transcribir clip por clip. Los `.json` se pueden dejar en
tanda y el usuario los importa.

El Import del panel es **de secuencia o de clip según qué esté seleccionado**, y
eso es la pista para lo que falta: la acción probablemente quiere el clip del
TIMELINE (un `TrackItem`) o la secuencia, no el `ClipProjectItem` del panel de
proyecto, que es lo único que se probó.

### Por la API NO se puede: `importFromJSON` devuelve vacío (Premiere 26.3.2)

La firma está confirmada en la documentación de Adobe:

```
Transcript.importFromJSON(jsonString: string): TextSegments
Transcript.createImportTextSegmentsAction(textSegments, clipProjectItem): Action
```

Y es exactamente lo que el bridge llama. La transacción **committea y devuelve
`true`**, y no pasa nada.

**El diagnóstico que lo resolvió:** `TextSegments` no expone ninguna propiedad, así
que el único modo de mirar adentro es `TextSegments.exportToJSON(segs)`. Devuelve
**`null`**. O sea que el parser no parseó nada y la acción recibe un objeto vacío
— por eso committea sin efecto.

**Y la prueba de que no es nuestro JSON:** se hizo el round-trip con el JSON que
Premiere MISMO exportó de otro clip (`desdeMedio`), sin que nuestro conversor
participe. Da `null` idéntico. Exportar de Premiere e importar a Premiere no
sobrevive el viaje.

Queda una ambigüedad honesta: no se puede distinguir "el parser devuelve vacío"
de "`TextSegments.exportToJSON` devuelve null aunque el objeto esté bien". Para el
resultado da igual —la importación no ocurre— pero importa si algún día se
reintenta con otra versión de Premiere: el test a correr es el round-trip.

### Las 29 formas que se probaron antes de llegar ahí

Se midieron 13 formas y ninguna importa. Lo que SÍ quedó establecido, para no
volver a empezar de cero:

- **`importFromJSON` no importa: es un PARSER.** Recibe el JSON **como string y
  como primer argumento** —pasarle una ruta contesta *"Failed to parse input
  string into JSON"*, que es lo que delató el argumento— y devuelve un objeto
  **`TextSegments`**. Eso se descubrió mirando lo que la llamada DEVUELVE, porque
  no tiraba error y tampoco hacía nada.
- **El que importaría es `createImportTextSegmentsAction`**, en una transacción.
  Con `(clipItem, TextSegments)` contesta *"Invalid parameter."*; con
  `(TextSegments, clipItem)` **committea y devuelve `true`, y no pasa nada** —
  `hasTranscript` sigue en false. Modo de fallar nº1 en su forma más pura.
- **El JSON no es el culpable.** Importando el JSON que Premiere EXPORTÓ de otro
  medio falla idéntico. Eso aísla la variable: el problema es el mecanismo o el
  destino, no el contenido.

Lo que queda por probar es **a qué se le aplica la acción**: quizá no a un
`ClipProjectItem` sino a una secuencia, a un clip del timeline o a un
`CaptionTrack`. El verbo `importarTranscripcion` quedó en el repo como sonda, con
las 13 formas y su error exacto, y **no está expuesto como herramienta** a
propósito: anunciar algo que no funciona es peor que no tenerlo.

El esquema que Premiere exporta —y por lo tanto el que hay que producir— es:

```jsonc
{ "language": "es-es",
  "speakers": [{ "id": "<uuid>", "name": "Unknown" }],
  "segments": [{ "start": 0.33, "duration": 30.18, "language": "es-es",
                 "speaker": "<uuid>",
                 "words": [{ "text": "Te", "start": 0.33, "duration": 0.09,
                             "confidence": 1, "eos": false, "tags": [],
                             "type": "word" }] }] }
```

Mapea casi 1:1 con lo que devuelve `herramientas/audio.js`. Se puede ver en vivo
con `premiere_transcripcion` y `crudo: true`.

## Los keyframes viven en el reloj del MATERIAL

Un clip que arranca en el segundo 20 de la secuencia y está recortado para
empezar en el 12 de su fuente tiene su propio reloj. Un keyframe que se ve "en
el segundo 25" se guarda en el 17. El bridge convierte en los dos sentidos, así
que los tiempos que entran y salen son siempre de **secuencia**.

Es una trampa cara porque en el caso fácil no se nota: con desfase 0 los dos
relojes coinciden, y con UN solo keyframe tampoco se nota nunca, porque el valor
queda constante y da igual dónde cayó. Aparece recién al animar sobre un clip
movido, con todo corrido.

**Y la velocidad entra en la cuenta:**

```
material = velocidad × (entrada + secuencia − inicio)
```

Un clip al 50% tiene su material corriendo a la mitad, así que dos keyframes
separados 5s en la secuencia están separados 2,5s en el material. La fórmula sin
el factor es este mismo caso con la velocidad en 1 — por eso pasó todas las
pruebas hasta que hubo un clip a 0.5x, donde pedir keyframes en 100/105/110 los
puso en 215,84/225,84/235,84.

Y ojo con cómo se verifica: que el bridge lea 25 después de escribir 25 **no
prueba nada**, porque leer y escribir usan la misma conversión y un error
simétrico se confirma a sí mismo. Pasó dos veces. Las dos se resolvieron con
verdad de afuera: mirando Effect Controls. La segunda dejó además una prueba
independiente — con la fórmula corregida, el bridge leyó los keyframes viejos
(escritos por el código roto) en los mismos timecodes que mostraba Premiere, y
eso no puede salir de un error simétrico.

## Qué hace y qué no hace cada acción del timeline

- **No hay razor arbitrario.** Ni `Sequence` ni `TrackItem` tienen nada de
  cortar, y `SEQUENCE_OPERATION_APPLYCUT` —que parecía una pista— resultó ser
  otra cosa: los tres valores de `Constants.SequenceOperation` son
  `"ApplyCuts"`, `"CreateMarkers"` y `"CreateSubclips"`, o sea qué hacer con los
  cortes que encuentra `performSceneEditDetectionOnSelection`. Corta donde la
  detección de escenas ve un cambio de plano, no donde uno quiera.
- **Un corte en un tiempo cualquiera se emula** y anda: `premiere_cortar`
  recorta la salida del clip hasta el punto y reinserta el mismo medio con la
  entrada corrida. El audio vinculado se parte igual. Verificado: partir en 25s
  un clip de 0-60 con entrada 10 deja `0-25 (entrada 10)` + `25-60 (entrada 35)`,
  pegados y sincronizados.
- **`premiere_sacar_rangos`** encadena eso: dos cortes y un borrado con ripple
  por cada tramo. Procesa **del último al primero**, porque cada ripple corre los
  tiempos de la derecha y de adelante para atrás los rangos siguientes ya no
  valdrían. Verificado con tres rangos de una: 100s → 84s, los 16s pedidos, sin
  huecos y con el audio en sincro.

  Esto es lo que permite editar EN la secuencia en vez de reconstruirla, y eso
  importa cuando el usuario ya editó a mano encima: reconstruir pierde su
  trabajo.
- `createSetInPointAction` **también corre el arranque del clip** en la
  secuencia: es el equivalente a arrastrar su borde izquierdo, no a cambiar qué
  parte de la fuente se ve dejándolo en su lugar.
- `createMoveAction` toma un **delta**, no un tiempo absoluto.
- Sí hay: mover, recortar entrada y salida, apagar, renombrar, y transiciones
  (`createAddVideoTransitionAction`).

## El timeline no es solo video

> **CORREGIDO (2026-08-17):** el cuarto argumento de `createOverwriteItemAction` es la PISTA DE
> AUDIO. En `-1` cae en A1 y PISA lo que haya ahí, y una pista que no existe se crea: UNA, al
> final (pidiendo A9 con seis, el audio cae en A7).

`premiere_clips` lista pistas de video **y de audio** (`V2`, `A1`), y los verbos
que apuntan a un clip aceptan esa etiqueta. No es cosmético: la primera versión
solo miraba video, así que al sacar un clip con audio vinculado el audio quedaba
huérfano — y la verificación, que también contaba solo video, informaba
"1 → 0 clips" y daba el borrado por bueno.

Y el vínculo **la API no lo expone**: el TrackItem no tiene ningún
`getLinkedItems`, y el segundo argumento de `addItem` no los incluye (probado).
Se deducen por medio de origen y rango de tiempo idénticos.

Eso vale para borrar **y para mover**. `createMoveAction` mueve UN item: sin
arrastrar los vinculados, mover un video dejaba su audio donde estaba —medido:
video a 30s, audio en 5s— y nada avisaba. Es peor que el audio huérfano, porque
ahí queda algo visible de más y acá algo que solo se nota reproduciendo.

Ojo con cómo se prueba: como los vinculados se identifican por rango de tiempo,
un clip YA desincronizado no tiene vinculados detectables. Un test que arranca
de ese estado no ejercita nada y puede parecer que pasa.

`premiere_insertar` pone también el audio del medio, y el cuarto argumento de
`createOverwriteItemAction` en `-1` **no lo suprime** — no está claro qué
significa, y el verbo informa cuántos clips de audio aparecieron en vez de
callarlo. `premiere_borrar` después se los lleva junto con el video.

Un clip de audio expone `Volume` (Mute, Level) y `Channel Volume` (33 params),
así que `premiere_param` y `premiere_keyframe` sirven para niveles y fundidos.
`Mute` llega como `{value: false}`: los params de casilla se normalizan aparte
porque como número dan `null`, indistinguible de un param ilegible.

## Transcripciones

> **CORREGIDO (26.5, medido el 2026-09-11):** desde Premiere 26.5 SÍ se puede disparar una
> transcripción por API, con `Transcript.transcribeClipProjectItem(clip, {language: "es-es"})` —ver
> *Lo medido que solo estaba en la bitácora*—. Lo que sigue sin poderse es IMPORTAR una de afuera.

`Transcript` tiene `hasTranscript`, `exportToJSON`, `importFromJSON` y
`querySupportedLanguages`: todo leer y escribir transcripciones que ya existen.
**No hay forma de disparar una transcripción desde la API** — se hace a mano en
el panel Text. No es que no se haya buscado: `Application` solo expone `version`
y eventos (no hay nada como el `executeMenuCommand` del viejo QE), `Utils` tiene
un solo método, `Metadata` solo lee el XMP que ya existe. Y `SequenceUtils.performSceneEditDetectionOnSelection`
prueba que Adobe SÍ expone disparar procesamientos pesados: la ausencia de
`transcribe` es una decisión, no un descuido de la búsqueda.

El sujeto de todas ellas es un **`ClipProjectItem`**, o sea el `ProjectItem`
casteado (mismo patrón que `FolderItem` para los bins). Con ProjectItem crudo,
TrackItem, Sequence, Project o Media contesta *"Invalid parameter"*.

El JSON trae segmentos con `speaker`, y adentro cada palabra con `start`,
`duration`, `confidence` y `eos`. Alcanza para cortar por palabra.

**Sus tiempos son de la FUENTE**, no de la secuencia: la transcripción es del
material y no sabe dónde quedó el clip ni qué parte se usó. Pasan por el mismo
reloj que los keyframes, velocidad incluida, y lo que cae fuera del clip se
marca como recortado — está en el material pero no en el timeline.

## Leer un valor animado

`valorEnTiempo` devuelve el valor **INTERPOLADO** en el tiempo pedido. Esta
sección decía lo contrario —que devolvía el keyframe anterior, y que para el
valor final había que usar `p.getKeyframePtr(ts[ts.length - 1]).value`— y las
dos mitades quedaron falsas el 2026-08-16, cuando se sacó `getKeyframePtr` de
`valorEnTiempo`. Medido lado a lado sobre un clip que va de 100 a 110:

```
frac    getKeyframePtr   getValueAtTime
0       100              100
0.25    100              102.5
0.5     100              105
0.75    100              107.5
```

**Y NO llames `getKeyframePtr` para esto.** Devuelve un PUNTERO a la estructura
interna del keyframe, y en ráfaga tira Premiere con SIGBUS —señal 10, tres
crashes en dos días, reproducido a propósito con 90 punteros en ~2s—. El
diagnóstico completo está en `CLAUDE.md`, sección *"`getKeyframePtr` en ráfaga
tira Premiere"*. `getValueAtTime` anda con y sin keyframes, sobre números
(`Scale`) y sobre puntos (`Position`), y devuelve la misma forma `{value}`.

Una llamada suelta no hace daño y por eso sigue como última opción adentro de
`valorEnTiempo`; lo que mata es el volumen. Recetarlo desde acá era mandar
directo al régimen que crashea, en el archivo que `CLAUDE.md` pide leer antes de
tocar nada.

## Qué cortes se pueden deshacer

Dos clips contiguos se pueden fusionar **solo si el segundo continúa al primero
en el material**: `b.entrada == a.entrada + a.duracion`. Si no, entre medio se
sacó algo y unirlos cambiaría lo que se ve. Es la diferencia entre un corte
hecho para cambiar la escala —que no saca nada y es reversible— y uno hecho para
sacar una muletilla, que es permanente.

Al fusionar, sacar con `MediaType.VIDEO` y no `ANY`: en un punch-in el audio
nunca se cortó y tiene que seguir de largo.

## `setPlayerPosition` no funciona en una secuencia recién creada

Mover el playhead de una secuencia temporal —creada con `createSequenceFromMedia`
y puesta activa— **no hace nada**: queda en 0. `premiere_frame` entonces exporta
siempre el mismo cuadro, y cuatro muestras a minutos de distancia salen idénticas,
lo que parece decir que el sujeto está inmóvil. Se detectó comparando md5.

`premiere_vistazo` sí anda sobre esas secuencias, así que hay una diferencia que
no está identificada. **Mientras tanto**: para mirar un momento puntual de un
medio, ponerlo en una secuencia de verdad y usar `premiere_playhead` +
`premiere_frame`, que es el camino probado. El parámetro `tiempos` de
el verbo `mirarMedio` NO es confiable.

## Aplicar algo a MUCHOS clips

Un verbo cómodo que ubica el clip recorriendo todas las pistas está bien para
una operación suelta y **es veneno en un bucle**: con 94 clips de video y 48 de
audio son ~140 llamadas por operación, y cien operaciones son veinte mil
llamadas en ráfaga. Eso crasheó Premiere con el proyecto real abierto.

Los verbos masivos —`aplicar_escalas`, `aplicar_zooms`— recorren la pista **una
sola vez** y traen `limite` y `siguiente` para ir por tandas. Con tandas de 12-15
y una pausa entre medio, los 94 clips pasan sin problema. Una llamada que toca
94 clips es además un solo punto de falla del que no se puede retomar.

## Fijar el valor de un param, sin keyframes

`param.createSetValueAction` **no toma el número**: con un valor crudo contesta
*"Illegal Parameter type"*. Hay que pasarle un objeto `Keyframe`, el mismo que
se le da a `createAddKeyframeAction`:

```js
let kf; project.lockedAccess(() => { kf = p.createKeyframe(50); });
acciones.addAction(p.createSetValueAction(kf));
```

Con eso se hace lo que Premiere llama *Set to Frame Size*: con material del
doble del cuadro, escala 50. `ClipProjectItem.createSetScaleToFrameSizeAction`
también existe, pero opera sobre el MEDIO y lo afectaría en todas las secuencias
que lo usen.

Y la resolución de la secuencia se cambia con `SequenceSettings.setVideoFrameRect`
más `sequence.createSetSettingsAction`. El rectángulo se arma con
`new ppro.RectF(0, 0, ancho, alto)` — acá `new` sí funciona, a diferencia de
`new ppro.TrackItemSelection()`.

## Marcadores

`createAddMarkerAction(nombre, algo, tick, duracion, tipo)` crea el marcador,
pero **el comentario NO entra por argumento**: con cinco queda en `"Comment"` —el
valor por defecto— y con cuatro, vacío. El segundo argumento acepta un string y
lo ignora. El comentario se pone con `marker.createSetCommentsAction(texto)`.

Ojo con cómo se verifica: dar por buena la forma que hace APARECER un marcador
deja pasar la que lo crea sin la nota. La comprobación tiene que releer el
marcador y exigir nombre **y** comentario.

Y el marcador nuevo se identifica **por `guid`**, no agarrando el último de la
lista: `getMarkers()` los devuelve ordenados por TIEMPO, así que uno puesto antes
que los existentes no queda al final. Agarrar el último verificaba un marcador
ajeno, lo daba por fallido y **lo borraba** — se perdieron dos buenos y quedaron
dos rotos antes de encontrarlo.

**El color va en otra transacción.** `createAddMarkerAction` no lo toma en
ninguna de sus formas; el setter es `marker.createSetColorByIndexAction(i)` y
vive en el `Marker`, no en la colección. Por eso `marcar` con color son **dos
Cmd+Z**, y lo dice en el resumen.

Los índices salen de `Constants.MarkerColor`, reflejado:

```
GREEN 0 · RED 1 · MAGNETA 2 · ORANGE 3 · YELLOW 4 · BLUE 6 · CYAN 7
```

Dos cosas de esa lista. `MAGNETA` está mal escrito **en la API**, así que el
verbo acepta "magenta" y lo traduce. Y **el 5 falta**: la constante no lo expone,
pero existe — en un proyecto real aparecieron marcadores puestos a mano con
`getColorIndex()` igual a 5. O sea que la constante no es la lista completa de
colores válidos, solo la de los que tienen nombre.

**El color de etiqueta de un CLIP no se puede tocar.** Es la pregunta natural al
lado de esto y la respuesta es no: `VideoClipTrackItem` expone 26 métodos y
ninguno es de label ni de color. Para distinguir capas de anotación a simple
vista, el color de marcador es el único camino. (Existe
`Constants.ProjectItemColorLabel`, pero es del PANEL DE PROYECTO, no del
timeline: sin medir.)

## El vínculo se deduce, y sólo vale entre video y audio

La API **no expone** qué está vinculado con qué. `buscarVinculados` lo deduce por
medio de origen y rango iguales, y además **exige que el socio sea del otro
tipo** — un grupo vinculado en Premiere es siempre video + audio.

Sin esa última condición empareja video con video, y ahí `editar` le manda al
falso socio el mismo `salida`, que es un punto de FUENTE: si los materiales
arrancan en distinto lugar, quedan con duraciones distintas. Medido con dos
instancias del mismo medio en V3 y V4, entradas 10 y 5: pedir 5s dejaba al otro
en 10s.

**El tipo se decide por la PISTA, no por `getMediaType()`.** Los valores de
`Constants.MediaType` (ANY, AUDIO, DATA, VIDEO) no son primitivos, así que
compararlos como texto da `[object Object]` y el filtro sale invertido — se
probó, y dio exactamente al revés.

## Cortar por texto

El flujo completo anda: `premiere_transcripcion` da los tiempos, se eligen los
pasajes, `premiere_armar_secuencia` los corta y los pega en una secuencia nueva.

Las tres piezas de la API se midieron una por una: `Project.createSequence(nombre)`
crea, `ClipProjectItem.createSetInOutPointsAction(entrada, salida)` marca el
fragmento, y `createOverwriteItemAction` **respeta esos puntos** — pedir 20→30s
deja un clip de 10,01s con entrada en 19,978s.

Dos cosas medidas al armarlo:

- **Cada fragmento se pega donde TERMINÓ el anterior, releído del timeline.** La
  duración real difiere de la pedida por el redondeo a frames, y ese error
  acumulado deja huecos si el cursor se calcula sumando.
- **Los tiempos son de FUENTE**, no de secuencia. Por eso `transcripcion`
  devuelve los dos (`desdeFuente`/`hastaFuente` además de `desde`/`hasta`):
  reconvertir en el verbo que corta sería otra oportunidad de equivocar el reloj.

El audio vinculado viene solo y alineado.

**La secuencia se crea desde el primer medio**, no con `createSequence`, que la
arma con los ajustes por defecto. Si el material no es 1920x1080@25 —una FX3
puede dar 3840x2160@50— los clips entrarían reescalados o con franjas, en
silencio. El precio es que `createSequenceFromMedia` mete el clip entero adentro
y hay que vaciarla antes de pegar los fragmentos.

## Cómo se arma una selección

`TrackItemSelection` **no tiene `createEmpty`**, y `new ppro.TrackItemSelection()`
devuelve "Connection to object lost". La única vía que funciona es pedir el
objeto vivo con `sequence.getSelection()`, vaciarlo con `removeItem` y agregarle
el clip. Medido probando las tres, no deducido.

## Firmas que no se adivinan

**Antes de adivinar una firma, reflejala.** El verbo `api` lee los nombres de métodos sin llamar a
ninguno, y con `{objeto: "SequenceEditor"}` refleja cualquier fábrica del módulo. Eso evitó diseñar
la selección a ciegas — y menos mal, porque `new ppro.TrackItemSelection()` devuelve *"Connection to
object lost"*.

La aridad que reporta `fn.length` **sirve a veces**: `createOverwriteItemAction` dice 4, que es lo
correcto, pero `createRemoveItemsAction` dice 0 y son 3. Vale como pista, no como dato.

Cuando la firma igual no se deduce, **enumerá los valores reales y probalos**. Así salió
`createRemoveItemsAction(seleccion, ripple, ppro.Constants.MediaType.ANY)`: el tercer argumento es
una constante de tipo de medio, no un booleano — con un booleano contesta *"Illegal Parameter
type"*, y con dos argumentos *"Not Enough Parameters"*. Se encontró enumerando los valores reales de
`Constants.MediaType` y `Constants.SequenceOperation`. La prueba de cuál sirvió no es que la llamada
no tire, sino el efecto observable.

Y **no enumeres ni llames getters a lo bruto**: en otro plugin una sonda que lo hizo crasheó Premiere.

## Lo medido que solo estaba en la bitácora (resumen del 2026-09-23)

Una línea por dato, agrupados por objeto. Salen de la bitácora privada con la que se construyó
el bridge: cada una es una medición contra Premiere, no una deducción del nombre del método.

**Proyecto**

- `Project.open(ruta)`: ruta absoluta, sin `file://`. Trae al frente uno ya abierto y NO lo
  recarga; con una ruta inexistente contesta "Failed to open the project" y deja el foco donde
  estaba.
- `OpenProjectOptions` con `setShowLocateFileDialog(false)`, `setShowWarningDialog(false)` y
  `setShowConvertProjectDialog(false)` abre sin el modal de medios faltantes
  (`abrirProyecto {sinDialogos: true}`).
- `Project.createProject(ruta)` con la carpeta padre inexistente NO falla: crea un gzip sin
  extensión un nivel más arriba e informa éxito. El prevuelo de `server/bridge.js` lo rebota antes.
- `project.close(opts)` con `CloseProjectOptions.setPromptIfDirty(false)` cierra sin preguntar y
  DESCARTA lo que no estaba guardado.
- `ProjectUtils.getProjectViewIds()` + `getProjectFromViewId()` enumeran los proyectos abiertos;
  `ProjectUtils.getSelection(project)` da la selección del panel de proyecto.
- `ProjectSettings.getScratchDiskSettings(project).getScratchDiskPath(FOLDERTYPE_*)` lee los
  discos de rayado.

**Medios**

- Los métodos de un medio viven en `ClipProjectItem`: sin `ppro.ClipProjectItem.cast(item)`
  contestan "is not a function", que se lee como que la API no los tiene.
- `importFiles` no deduplica: pedir un archivo que ya está crea otro item con el mismo nombre.
- `createBinAction` y `createMoveItemAction` son de `FolderItem`, y la acción se crea ADENTRO de
  `lockedAccess`; afuera contesta "Requires locked access". Un bin no contesta `getItems()` sin
  castearlo a `FolderItem`.
- `attachProxy(ruta, 0)` adjunta y `hasProxy` / `getProxyPath` lo releen; `detachProxy` no existe.
- `createSetOverrideFrameRateAction(fps)` reinterpreta: la duración del clip ya puesto NO cambia,
  el contenido sí.
- `getFrameRate()` del medio devuelve un número; `Sequence.getVideoFrameRate()`, un `{value}`.
- `createSubClipAction(nombre, inTick, outTick, limitesDuros)`: cuatro argumentos, no seis.
- `Constants.ProjectItemColorLabel` no tiene el índice 2: son 15 colores en 16 lugares.
- `canChangeMediaPath()` + `changeMediaFilePath(ruta)` relinkean, sin pasar por
  `executeTransaction`: no hay Cmd+Z.
- `findItemsMatchingMediaPath(ruta)` es de instancia y contesta sobre su receptor, no busca en el
  proyecto; compara la cadena exacta.
- La duración de un medio sale de `getMedia().getDuration()`; `getMedia().duration` es una Promise.
- Premiere devuelve los nombres en NFC y las rutas en NFD.

**Secuencia**

- `createSequenceFromMedia` hereda tamaño y fps del material. `createSequenceWithPresetPath(nombre,
  ruta)` toma un `.sqpreset`: `VideoFrameRate` en ticks por cuadro, `VideoFrameSize`, y
  `VideoTimeDisplay`, que es 101 a 25 fps y 104 a 30.
- Ajustes de una secuencia existente: `const st = await sequence.getSettings()` AFUERA del lock
  —adentro devuelve una Promise—, `st.setVideoFrameRate(ppro.FrameRate.createWithValue(fps))`,
  `st.setVideoFrameRect(new ppro.RectF(0, 0, ancho, alto))` y `sequence.createSetSettingsAction(st)`.
- `getTimebase()` son los ticks por cuadro. `alignToNearestFrame` contesta "Illegal Parameter
  type": se cuantiza con aritmética entera sobre ticks.
- Los in/out sin marca devuelven −400000, que es el "sin valor" de toda la API y se puede
  reescribir. Se ponen en DOS transacciones y el in primero: en una sola, el in se pierde.
- `WorkAreaUtils` lee y escribe el work area, y `exportSequence` lo ignora.
- `createSubsequence()` copia el contenido a una secuencia nueva y deja la madre igual: no anida.
  Una nest es `armarSecuencia` + `insertar`.
- `getCaptionTrackCount()` vive en `Sequence`; no hay fábrica para crear una pista de captions.
- `SequenceEditor.getEditor(seq).insertMogrtFromPath(ruta, tick, pistaV, pistaA)` coloca un MOGRT;
  su `Source Text` no se puede escribir.

**Pistas y clips**

- `createOverwriteItemAction(item, tick, pistaV, pistaA)`: el cuarto es la pista de AUDIO, `-1`
  cae en A1, PISA lo que haya, y una pista de audio que no existe se crea: UNA, al final.
- `createMoveAction` toma un delta y SOLAPA en vez de pisar.
- `createSetEndAction` guarda el tick exacto y el overwrite pega al cuadro: un corte entre cuadros
  deja un hueco de uno.
- Al arrastrar un clip, Premiere recuantiza su in-point a la grilla de la SECUENCIA, y el del
  audio vinculado no.
- `TrackItem.getTrackIndex()` es 0-based y separa dos copias del mismo clip en el mismo instante.
- `isDisabled()` lo tienen los clips de video y los de audio; `isAdjustmentLayer()`, solo
  `VideoClipTrackItem`.
- `VideoTrack.isMuted()` / `setMute()` es el ojito de la pista y llega al render; no pasa por
  `executeTransaction`.
- `getTrackItems(tipo, false)`: con `true` incluye los vacíos, y sin el segundo argumento tira
  "Illegal Parameter type". Con `TrackItemType.TRANSITION` la lista tiene el largo correcto y todos
  sus items son `null`: las transiciones se cuentan, no se leen.
- `createCloneTrackItemAction(item, tick, pistaV, pistaA)` toma OFFSETS relativos al clip de
  origen. El clon es independiente, efectos incluidos, y puede crear pistas de video.
- `new ppro.TrackItemSelection()` contesta "Connection to object lost".

**Transiciones**

- `TransitionFactory.createVideoTransition(matchName)` + `new ppro.AddTransitionOptions()`
  (`setApplyToStart`, `setTransitionAlignment` como fracción 0..1, `setDuration(tick)`) +
  `clip.createAddVideoTransitionAction(t, opts)`, todo adentro de UN `lockedAccess`.
- `Constants.TransitionPosition.START` vale 1, que es "termina en el corte".
- El Cross Dissolve de Cmd+D es `AE.AE_Impact_Dissolve`; `ADBE Cross Dissolve` es el Legacy.
- Los clips de audio no tienen ningún método de transición.

**Componentes y params**

- `Scale` de Motion es proporcional: el Uniform Scale no hace falta. `Rotation` es el param 4.
- El componente `Opacity` trae `["Opacity", "Blend Mode", "Blend Mode"]`; el Blend Mode es un
  índice —18 es Normal— y llega al render.
- Lumetri (`AE.ADBE Lumetri`) tiene 130 params. `Look` e `Input LUT` son índices sin nombre, y un
  `.cube` propio no se carga por ruta.
- `createSetValueAction` sobre un param animado escribe el valor BASE, y los keyframes lo tapan.
- `getValueAtTime` lee con y sin keyframes y devuelve `{value}`; `getKeyframePtr` en ráfaga es un
  SIGBUS.
- `getKeyframeListAsTickTimes` es sincrónico adentro del lock y no lee valores.
- `createRemoveKeyframeAction(tick)` borra uno. `createSetInterpolationAtKeyframeAction(tick,
  modo)` cambia el tipo, que no se puede releer, y un bezier sin tiradores se mueve como un lineal.
- `VideoComponentChain.createAppendComponentAction(comp)` con un componente de OTRO clip lo
  COMPARTE, y el vínculo sobrevive a cerrar y reabrir. `createInsertComponentAction(comp, i)`
  contesta "Illegal Parameter type".

**Marcadores**

- `Markers.getMarkers()` acepta la secuencia o el MEDIO; con un TrackItem, "Invalid parameter".
- `createAddMarkerAction(nombre, algo, tick, duracion, tipo)` crea el marcador en la primera forma que
  se prueba, pero el comentario NO entra por argumento: ver *Marcadores*.
- `createMoveMarkerAction(marker, tick)` no cuantiza. `marker.createSetColorByIndexAction(i)` y
  `createSetDurationAction(tick)` editan uno ya puesto.
- `performSceneEditDetectionOnSelection(operacion, seleccion)`: la operación va PRIMERO, y los
  marcadores de `CreateMarkers` van sobre el clip, no sobre la secuencia.

**Exportar, transcribir y eventos**

- `exportSequence(secuencia, ExportType, salida, preset)`: el tipo va SEGUNDO; en otro orden
  devuelve `false` sin escribir nada.
- En `EncoderManager`, `getExportFileExtension` e `isAMEInstalled` figuran en el reflejo y no son
  funciones.
- `launchEncoder()` devuelve `true` antes de que Media Encoder esté listo; `startBatchEncode()`
  arranca la cola, y hay que pedirlo más de una vez.
- `Transcript.transcribeClipProjectItem(clip, {language: "es-es"})` crea una transcripción desde
  26.5. `importFromJSON` sigue devolviendo un cascarón, y `TextSegments.exportToJSON` sobre él
  dereferencia un nulo: no llamarlo.
- `EventManager.addGlobalEventListener(nombre, cb)` registra; de los eventos probados solo llega
  `Project.ACTIVATED`.
- `SourceMonitor.openProjectItem` devuelve `true` y no abre nada.

