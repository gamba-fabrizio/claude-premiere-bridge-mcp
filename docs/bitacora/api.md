# Firmas de la API, lo que no permite y lo que el .prproj tiene

> Bitácora movida TAL CUAL desde `CLAUDE.md` el 2026-09-23, en el orden en que
> estaba. «Arriba» y «abajo» se refieren a aquel archivo único. Los títulos no se
> tocaron: el código que cita una sección «de CLAUDE.md» la encuentra acá con `grep`.

# Firmas de la API, medidas y no deducidas

**Antes de adivinar una firma, reflejala.** El verbo `api` lee los nombres de métodos sin
llamar a ninguno. La aridad que reporta `fn.length` **sirve a veces**:
`createOverwriteItemAction` dice 4 y es correcto, `createRemoveItemsAction` dice 0 y son 3.

Cuando la firma igual no se deduce, **enumerá los valores reales y probalos**. La prueba de
cuál sirvió no es que la llamada no tire, sino **el efecto observable**.

**Y no enumeres ni llames getters a lo bruto**: una sonda que lo hizo crasheó Premiere.

## Las que costaron caro

```
createOverwriteItemAction(medio, tick, pistaVideo, pistaAudio)
   El CUARTO argumento es la pista de AUDIO. Con -1 cae SIEMPRE en A1.
   Y el overwrite PISA: quince capas con -1 le comieron 2,4s cada una a A1.

createRemoveItemsAction(..., ..., Constants.MediaType.ANY)
   El tercero es un MediaType. No se dedujo: se enumeraron los valores y se probó.

exportSequence(secuencia, ExportType, salida, preset)
   El TIPO va SEGUNDO. Con (secuencia, salida, preset, tipo) NO TIRA y devuelve
   `false` sin escribir nada. La primera versión cortaba en la forma que no tiraba
   e informaba éxito sobre un export que no existió.

createSetInterpolationAtKeyframeAction(tick, modo)
   Vive en el PARAM, no en el keyframe, así que el tipo de keyframe no la limita.

performSceneEditDetectionOnSelection(operacionString, TrackItemSelection)
   La operación va PRIMERO. Con el objetivo primero, las 20 formas probadas
   contestan "Illegal Parameter type".

createSubClipAction(nombre, inicioTick, finTick, limitesDuros)
   CUATRO argumentos, no seis. Los tiempos van como TickTime, no en segundos.
```

## Tipos de retorno que NO son uniformes

Suponer que esta API es uniforme costó una vuelta entera:

```
getFrameRate()        devuelve un NÚMERO pelado
getVideoFrameRate()   devuelve {value: fps}
getValueAtTime()      devuelve {value: n} envuelto, y createKeyframe lo RECHAZA
```

**Cuando un getter y un setter son de la misma propiedad, la forma que devuelve el getter es
la primera que hay que probar en el setter.**

## El sentinel de los in/out

Sin marca, los getters de in/out de una secuencia **no devuelven 0 y el final**: devuelven
**−400000**, un sentinel. Se había escrito lo contrario sin medirlo.

Y el sentinel **se puede reescribir**, así que el estado "sin marca" vuelve, siempre que se
lea ANTES y se reponga el valor leído.

**`exportSequence` respeta los in/out de la secuencia**, y esto se entrega solo: un out viejo
—puesto a mano hace días— fija el largo del archivo sin que nada lo mencione. Medido: un
export salió **94 segundos más largo que el contenido**, clavado en el out point. Y
**respetó el OUT e ignoró el IN**, así que un in suelto no recorta la cabeza pero un out
suelto sí estira la cola. Es la asimetría que hace que el defecto se entregue: un export más
corto se nota, uno más largo con negro al final no.

**El rango va en DOS transacciones, y el IN primero.** Con las dos acciones en una sola, el
in **no se aplica**: si Premiere aplica el out primero queda un rango invertido y descarta el
in **en silencio**.

## `editar salida` es punto de FUENTE, no una duración

Un Transparent Video entra con `entrada ≈ 3600` —los sintéticos son generadores de una hora
y el clip nace por el medio—, así que para dejarlo de 10s hay que pedir `salida: 3610`.
Pedir `salida: 10` cae **antes** del in-point: no recorta, no tira error, y el clip se queda
en su duración por defecto.

**No es sólo el Transparent Video: un PNG fijo hace lo mismo.** Nueve placas quedaron de 5
segundos —la duración por defecto de una imagen— porque el colocador pedía `entrada: 0`.

La forma correcta es **leer la `entrada` real del clip recién insertado** y sumarle la
duración. No se puede asumir 3600 para cualquier medio.

## `createSetInPointAction` además MUEVE el clip

Medido: pidiendo `entrada` y `desde` en la misma llamada, el in-point entró y el clip se fue
a donde decía la entrada. Van en DOS llamadas, primero la entrada y después la posición — el
mismo patrón que los in/out del export.

## Los vinculados: el delta, no el valor

`entrada` y `salida` son puntos adentro del MATERIAL, y el material de cada clip arranca
donde arranca. Copiarle al vinculado el mismo número absoluto le da una duración que no es
la suya. En el peor caso, cero:

```
V4  300–305s  entrada 5      ← se le pide salida 8  → 300–303s, 3s ✓
A1  300–305s  entrada 8      ← le llegaba salida 8  → 300–300s, CERO ✗
```

Y **Premiere acepta un clip de largo cero**. Ojo con la diferencia: si el pedido diera
duración **negativa**, Premiere lo ignora y el clip queda intacto. Exactamente **cero** sí lo
aplica.

Lo que comparten dos vinculados es **dónde terminan en el timeline**, no dónde terminan
adentro de su material. Así que se pasa el **delta**.

## Deducir el vínculo: exigí que el socio sea del OTRO tipo

La deducción era "mismo medio + mismo rango", sin mirar el tipo. Dos clips de VIDEO del
mismo medio en pistas distintas, con el mismo rango, eran un par vinculado — y eso no
existe: un grupo vinculado es siempre video + audio.

**El tipo se decide por la PISTA, no por `getMediaType()`**: los valores de
`Constants.MediaType` **no son primitivos** y comparados como texto dan `[object Object]`.

---

# Cosas que la API NO permite

Anotadas porque cada una se descubrió intentándola, y algunas tienen una vía alternativa.

**No hay razor.** Cortar es: leer el clip, achicar la cabeza con `createSetEndAction`, y
pegar la cola con un overwrite. Y **el overwrite no copia nada**, así que la cola nace con
Motion por defecto y **borra el escalado del clip original** si no se lo repone a mano.

**No hay verbo para agregar pistas de VIDEO** —`Sequence` sólo expone `getVideoTrack` y
`getVideoTrackCount`—, pero **CLONAR las crea**: un clon cuyo destino queda por encima de las
que hay hizo que una secuencia pasara de 6 a 8 pistas sin que nadie lo pidiera. Así que la
afirmación "la API no puede" es falsa; lo que no hay es una vía para pedirlo a propósito.
**Y tampoco hay para BORRARLAS**, así que las que aparecen quedan. Las de **audio** sí se
crean solas al pedir una fuera de rango.

**No hay `detachProxy`.** Se adjunta y no se suelta. Corolario: **no adjuntar nunca un proxy
que viva en una carpeta temporal.**

**No se pueden crear capas de ajuste**, ni cargar presets de Lumetri (`.prfpset`), ni aplicar
un `.cube` propio por ruta. Pero el efecto **sí se controla entero**: Lumetri expone 130
parámetros nombrados, y los looks de fábrica se aplican **por índice**.

**No se puede importar una transcripción por API.** `Transcript.importFromJSON` devuelve un
**cascarón**: un objeto sin propiedades propias y con el puntero interno en null. Probado con
el JSON que Premiere mismo exportó, así que el esquema es idéntico byte por byte. Las 16
combinaciones de segundo argumento contestan "Illegal Parameter type".

Pero **el pipeline SÍ cierra con UN import a mano**: JSON en el esquema de `Transcript` →
panel Text → Import → y el verbo de lectura devuelve los segmentos y las palabras con los
tiempos intactos. El único paso manual es **un** Import, no transcribir clip por clip.

**El modo de fusión (`Blend Mode`) SÍ se lee y se escribe**, y llega al render — 4 valores, 4
cuadros distintos, y al reponer vuelve el md5 exacto. Vive en el componente `Opacity`, cuyos
params son `["Opacity", "Blend Mode", "Blend Mode"]` —aparece dos veces— y es un índice
numérico.

## `copiarEfecto` NO es una copia: es la MISMA INSTANCIA

`createAppendComponentAction(comp)` con un componente de otro clip **no lo copia: lo
COMPARTE.** Medido entre dos secuencias distintas:

```
origen  Exposure      0,4
destino Exposure      0,4     (recién "copiado")
escribo 2,5 SOLO en el destino
origen  Exposure      2,5     <- cambió el ORIGEN
```

Eso **explica de golpe todo lo que parecía un éxito**: los valores "viajaron", las máscaras
internas "viajaron", los efectos de terceros "viajaron". Claro que sí — es el mismo objeto.

**Lo descubrió el usuario, no la verificación**: entró a la secuencia nueva, apagó un efecto,
y se le apagó también en la otra. **Ninguna de las pruebas lo podía encontrar**, porque todas
leían el destino después de escribir el origen, y eso da igual con una copia que con un
vínculo. La prueba que los distingue es la INVERSA —escribir en el destino y leer el
ORIGEN—.

Es una variante nueva de la verificación simétrica: no fue leer con la misma conversión con
que se escribió, fue **medir siempre en la misma dirección**. Un vínculo y una copia sólo se
distinguen mirando para el otro lado.

**Y el vínculo SOBREVIVE a cerrar y reabrir el proyecto**, así que no es un alias de sesión
sino una propiedad que Premiere guarda en el `.prproj`.

## Copiar los componentes NO es copiar el look

Ocho componentes llegaron con sus valores, el verbo informó que cada uno viajó, y el
resultado estaba **completamente roto**: naranja, borroso y oscuro.

Falta que **`Opacity` y `Blend Mode` viven en un componente que TODO clip ya tiene**, así que
no se pueden traer. Una sola capa mal compuesta destruye todo el cuadro: una capa que
funciona *al 25% y en otro modo*, copiada en Normal al 100%, simplemente tapa la imagen.

**Y la bisección es el método, no el ojo.** Apagar las cuatro y prenderlas de a una lo
encontró en una pasada, con un número por capa:

```
todas apagadas        142,6
+ base                158,8    plausible
+ la capa mala        112,5    <- -46 de un saque: es ésta
+ las otras dos       108,0
```

---

## Y `clonar` SÍ es una copia de verdad

La contracara de lo de arriba, y lo que lo vuelve utilizable.
`SequenceEditor.createCloneTrackItemAction` duplica un clip **con sus efectos, su Motion y su
recorte**, y el clon queda **independiente**. Probado por la inversa, que es la única prueba
que distingue una copia de un vínculo:

```
Scale        original 100  ->  100      clon 100  ->   42
Exposure     fuente  1,75  ->  1,75     clon 1,75 -> -3,25
```

Escribiendo en el clon, el original no se movió. Con un param intrínseco (`Motion`) y con un
efecto agregado (`Lumetri`), que también viaja.

**Lo que NO reemplaza:** clona el CLIP entero a otro lugar. Llevar un look a un clip que YA
existe sigue siendo copiar el componente, con su instancia compartida.

### La firma toma OFFSETS, no posiciones — y eso hay que esconderlo

```
origen arranca 2,52s · pedido "tick 40"   ->  el clon quedo en 42,52s
origen arranca 20s   · pedido "tick 40"   ->  el clon quedo en 60s
```

El argumento de pista **se suma** al índice de la pista de origen, así que un clon "a V4"
desde V3 aterriza en V6. Exponer eso crudo garantiza que el próximo lo ponga en otro lado.

**El verbo recibe el destino ABSOLUTO y hace la resta**, y además cuantiza al cuadro avisando
cuánto movió. Es la misma regla que otro verbo de este repo ya pagó dejando 121 de 139
marcadores entre frames: aplicarla al de al lado ANTES de que muerda es más barato que
descubrirla dos veces.

## Un medio se puede REPUNTAR a otro archivo, y el ciclo persiste

`ClipProjectItem.changeMediaFilePath` + `refreshMedia`. Medido de punta a punta sobre un
proyecto armado a propósito:

```
proyecto abierto con el medio AUSENTE   isOffline true
export en ese estado                    media 97,83
repuntado                               isOffline false
export despues                          IDENTICO al sano (media 124,338)
cerrar y reabrir                        sigue online: la reparacion PERSISTE
```

**Tres cosas que sólo aparecen midiéndolo:**

- **Un clip offline NO exporta NEGRO: exporta la placa "Media Offline"**, que dio media 97,83.
  Detectarlo preguntando "¿el cuadro es negro?" no funciona; lo dice `isOffline`.
- **Premiere relinkea SOLO** cuando el archivo se movió dentro del árbol del proyecto. Para
  conseguir un offline de verdad hubo que mandarlo afuera **y con otro nombre**. Los dos
  primeros intentos fallaron por eso y parecían un fallo del método.
- **El archivo destino tiene que existir, y eso lo comprueba el lado que ve el DISCO.** El
  panel no lo ve. Repuntar a una ruta ausente deja el medio offline y Premiere recién lo avisa
  al reproducir, que se lee como un problema del archivo original.

Y **no pasa por una transacción, así que no hay Cmd+Z**: se desanda repuntando a la ruta
anterior, que por eso el verbo informa.

## El cartel de guardar BLOQUEA el Cmd+Q — y el panel sigue contestando

Esto es un modo de fallo del ENTORNO, no de la API, y es de los que más caro salen porque no
se nota.

Cerrar Premiere con un macro es lo que hace automatizable recargar el plugin. Con **dos
proyectos abiertos**, el Cmd+Q le pide guardar al que NO tiene foco, sale su cartel, y el
cartel traba el cierre. Hasta ahí es un cuelgue.

**Lo grave es que EL PANEL SIGUE LATIENDO Y CONTESTANDO con el modal en pantalla.** Medido: el
verbo de estado respondió normal, con su resumen completo. Así que desde el otro lado no se
nota nada y se sigue trabajando sobre un Premiere a medio cerrar, con el proyecto en el limbo.
Esa sesión terminó borrando la carpeta de un proyecto que todavía estaba abierto.

**Y el cartel puede estar en OTRO MONITOR.** `screencapture -x` captura UNA pantalla; para
verlas todas hay que darle un nombre por pantalla.

### Informar no alcanza: hay que TRABAR

La primera versión del arreglo guardaba todos los proyectos antes de cerrar y, si igual
fallaba, lo informaba. **El informe se lee y se sigue**, que es literalmente lo que había
pasado. Así que ahora un cierre que no termina **deja una marca y el transporte REBOTA TODA
LLAMADA** hasta que alguien mire la pantalla y la levante a mano.

Va en el **transporte** —no en la herramienta— porque es el único punto por el que pasan los
dos caminos: las herramientas del repo llaman directo y saltean la capa MCP.

### Y el arreglo produjo el modal que existía para evitar

Pedía "guardá todos" y **después** cerraba los proyectos huérfanos. Pero **un proyecto cuyo
archivo fue borrado sigue teniendo RUTA**, así que entraba en el guardado y Premiere abrió:

```
Project Modified — The project file has been modified since last save. Do you wish to continue?
```

El chequeo miraba si la ruta estaba **vacía**, no si el archivo **existía**. Peor: el
comentario de esa misma función decía que el veredicto lo daba el lado que ve el disco, y no
estaba implementado — **un comentario que describe la intención en vez del código**.

El arreglo es el ORDEN, y la firma lo hace cumplir: el parámetro dejó de ser un booleano y
pasó a ser **la lista de rutas** que arma el lado que ve el disco. El panel ya no puede
decidirlo, así que tampoco puede equivocarse.

# Lo que el `.prproj` tiene y la API no expone

Es XML gzippeado. Dos cosas se leyeron de ahí porque no hay verbo:

**Los marcadores del MEDIO** (los que pone la detección de escenas) — el verbo de marcadores
lee los de la SECUENCIA e informaba "no tiene marcadores" con 145 puestos:

```xml
<Marker><DVAMarker>{"DVAMarker":{"mStartTime":{"ticks":877066444800000},...
```

Ticks divididos por 254.016.000.000 y quedan los segundos. Cotejados contra los detectados
por ffmpeg: **los mismos 145, diferencia 0 ms** — dos métodos independientes, que es la única
confirmación que vale.

**Las transiciones**, que por API se pueden ver pero no hay verbo (`clips` pide sólo
`TrackItemType.CLIP`, clavado). **Y en el XML NO cuelgan de la pista**: cuelgan de cada clip,
como `HeadTransition` / `TailTransition`. Recorrer los `TrackItems` de cada pista devuelve
**cero** en una secuencia que tiene 39. Una transición es cola de un clip y cabeza del
siguiente, así que **hay que deduplicar por `ObjectID`**.

**El punto de corte es `Start + Alignment`, y la alineación NO se puede asumir.** En una sola
secuencia aparecieron las tres: centradas, una que arranca 6 cuadros antes del corte y una
que **termina** en el corte. Suponer "centrado" habría dejado dos de seis corridas ~1,7s.

## Tres falsos negativos el mismo día, todos por adivinar el nombre del campo

Es lo que más vale de esta sección, porque el modo de fallo es el mismo las tres veces:
**escribí un lector, no encontró nada, y estuve a punto de informar que el trabajo del editor
no estaba.**

```
transiciones   busqué en TrackItems      -> "0 transiciones" con 39 puestas
clip muteado   busqué <Disabled>         -> "ninguno apagado", el campo es <IsMuted>
efectos del    resolví un nivel de menos -> "SIN EFECTOS" en los 8, con el compresor
master                                      puesto
```

Los tres se veían igual desde afuera: un lector nuevo devolviendo vacío. Y **un vacío se lee
como "no está" cuando en realidad es "no lo encontré"**.

**Lo que los separó fue un CONTROL, no mirar mejor el código.** Leer el mismo campo donde se
SABE que el efecto no está: las secuencias intactas dieron **2 componentes** y las tocadas
**3**. Recién ahí el tercero significa algo.

**La regla operativa: un lector nuevo sobre el `.prproj` no informa "no hay" hasta haber
pasado un control positivo.** El daño de equivocarse acá no es un número mal: es decirle al
editor que su trabajo no entró.

---
