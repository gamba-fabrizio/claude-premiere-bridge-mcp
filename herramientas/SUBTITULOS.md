# Subtítulos: dos vías, según qué se subtitula

| lo que se subtitula | la vía | cómo entra a Premiere |
|---|---|---|
| **HABLA**: entrevista, testimonio, locución, reel | Scribe sobre la MEZCLA exportada —o el de cada clip, si ya está— + `subtitular.py` | un **SRT** importado: un caption por bloque |
| **CANCIÓN**: la letra de un videoclip | Whisper sobre el stem de voces, por sección | **PNG** transparentes colocados como clips |

**Ninguna de las dos crea captions por API, porque no se puede.** `Transcript.importFromJSON`
devuelve un cascarón con el puntero interno en null, probado con el JSON que Premiere mismo
exportó, y el MCP de terceros que dice tenerlo hace una transacción que committea sobre la nada.
Por eso la de habla deja un SRT —que `premiere_importar` sí acepta: lo que queda a mano es ponerlo
en la secuencia— y la de canción, PNG que el bridge coloca.

## Habla: entrevistas, testimonios, locución y reels (2026-09-24)

Salió de subtitular tres videos de testimonios de cinco minutos, con locución y cortes del editor
adentro de las frases. Del tercero, el editor dijo *"están perfectas las divisiones que hiciste y
cómo interpretaste el material"*. Las herramientas genéricas reproducen idénticos los tres SRT
entregados —108, 94 y 86 subtítulos— desde los ajustes de cada video. Y los dos reels verticales de
un evento, a 29,97 y de una sola línea, que se habían hecho con un script del proyecto: idénticos
también, 28 y 34 subtítulos, con las opciones de reel (ver abajo).

### El flujo

Todo se trabaja en una carpeta del PROYECTO, al lado del material, con un `subtitulos.proyecto.json`
que dice dónde está cada cosa: ver la cabecera de `subtitular.py`. **No `subtitulos.json`**: en los
reels, ése es un archivo que el script del proyecto ESCRIBE, y el de configuración lo pisaría.

1. **Exportar el audio de la secuencia**: `premiere_exportar`, con el preset Waveform Audio 48 kHz, a
   `<video> - audio.wav`. Con las palabras de cada clip (paso 3), no hace falta.
2. **Leer la línea de tiempo**. Por el bridge, con la secuencia activa:
   `node herramientas/timeline_subtitulos.js subtitulos.proyecto.json "<video>" --secuencia "<nombre>"`.
   O del `.prproj` guardado, sin Premiere y **abriendo los nested**:
   `python3 herramientas/timeline_prproj.py subtitulos.proyecto.json "<video>"`. Si la voz está
   anidada, el bridge ve un solo clip con el nombre del nested, y hace falta el segundo. Los dos dejan
   los clips de cada pista de audio, los cortes de plano y los fps de la secuencia.
3. **Transcribir la MEZCLA**: `audio.js --motor scribe` sobre el wav. Scribe gasta créditos —unos 40
   por minuto—, así que se consulta antes. Para el cruce, además `--motor premiere` con otro
   `--destino` (por ejemplo `premiere/`): `audio.js` no pisa la de otro motor. **Si ya están las de
   Scribe de cada clip entero**, no se transcribe nada: `transcripcion_por_clip` las pasa por los
   cortes.
4. **Cruzar**: `python3 herramientas/cruzar_subtitulos.py subtitulos.proyecto.json "<video>"` lista
   dónde discrepan Scribe, la transcripción de Premiere del medio entero, la de Whisper y la de
   Premiere sobre la mezcla. **Se revisa uno por uno** (ver abajo por qué). Es de la vía de la mezcla.
5. **Escribir `<video> - ajustes.json`**, a mano: `cambios` (cada corrección al texto de Scribe, con
   su motivo), `agregados` (lo que suena y Scribe no escribió), `para_escuchar`, `manual` (los turnos
   que se dividen a mano) o `bloques` (el video entero), y `pausa_turno`.
6. **Subtitular**: `python3 herramientas/subtitular.py subtitulos.proyecto.json "<video>"` escribe
   `<video> - subtitulos.srt` y `<video> - revisar.txt`, con lo que hay que escuchar, cada cambio y
   los avisos de tiempo. Con la `envolvente` del reel, con `~/.venvs/audio/bin/python`: necesita
   numpy y scipy, y los medios montados.
7. **Importar el SRT** con `premiere_importar`, que lo acepta: entra un caption por bloque, con el
   texto y los tiempos exactos —verificado en el `.prproj`: el texto va en UTF-8, en base64, y los
   tiempos al tick—. Lo que queda **a mano es arrastrarlo a la secuencia**, que es lo que crea la
   pista de captions.

### Por qué Scribe sobre la mezcla, y por qué el cruce no manda

**Las transcripciones de Premiere y de Whisper de cada clip traen tiempos RUIDOSOS por palabra**:
contra la mezcla, una mediana de +0,26 s y hasta 1,4 s entre palabras vecinas. No sirven para saber
qué palabra quedó adentro de un corte. Con ésas hay que transcribir la MEZCLA, que es el audio ya
editado.

**Las de Scribe de cada clip, no**: en los reels arrancaban tarde de manera PAREJA —una mediana de
40 ms—, y la voz rearmada desde esos cortes calzó contra el export con el mismo corrimiento en los 24
fragmentos (+21,8 ms, que es el arranque del AAC, no un corte corrido). Es un trabajo, un hablante y
un corbatero: si ya están pagas, se usan; si no, la mezcla sigue siendo la base.

**Scribe sobre la mezcla es la mejor base**: resolvió solo marcas, nombres de productos y números
que las otras transcripciones erraban, y puntúa y cita.

**Y el voto clip + Whisper NO es independiente**: las dos salen del mismo medio y fallan JUNTAS. En un
video de 21 lugares donde el cruce le cambiaba el texto a Scribe, unos diez eran errores del cruce:
una frase entera oída distinto, un plural que no era, y palabras de la parte que el editor había
sacado en un corte. **Si la frase de Scribe tiene sentido, gana Scribe.** Por eso `subtitular.py`
parte de Scribe y no de lo que votó el cruce: lo que va a `cambios` es lo que Scribe erró de verdad y
lo que se limpia. Y en la cabeza de cada clip el cruce suele meter la última palabra del clip anterior.

**Lo que ninguna fuente corrige**, y va a mano: «echo» (de *echar*), que las cuatro escribieron
«hecho»; «súper natural», que no es «supernatural»; el voseo («mirá»); las frases hechas («sí o sí»);
y el nombre exacto de una marca o una entidad.

### El texto

- **Sin muletillas ni tartamudeos.** Las muletillas sueltas —«eh», «mm»— se sacan igual aunque no
  estén en `cambios`, y el `revisar.txt` las lista.
- **En cifras**: los tonos, los precios, los porcentajes y los volúmenes («la número 5», «6.0»,
  «35%», «2x1»). **En letras**: las cantidades y los plazos («cada tres, cuatro meses», «veinte
  días»).
- **Raya para un segundo hablante**, en el mismo bloque que la respuesta.
- **Entre comillas lo que dice un envase o un cartel.**
- **«súper» va separado**, y el voseo como se habla.
- **La locución lleva el texto EXACTO del guion**, con los tiempos que dejó `locucion.js`: no se
  transcribe.

### La división

- **Nunca después** de un artículo, una preposición, un clítico, un «no» o un auxiliar, y **nunca
  adentro** de una marca o de una frase hecha. Las frases hechas del idioma están en
  `subtitular.py`; las de un cliente —una marca de dos palabras, un código de producto— van en
  `pegadas` del proyecto, porque el código es de todos los proyectos.
- **Hasta 2 líneas de 42 caracteres**, en cuadros enteros y enganchadas a los cortes de plano. O
  las que diga el estilo, medidas en PÍXELES de la fuente real (`lineas` y `ancho`): ver el reel.
- **El cambio de hablante corta siempre**; la pausa que parte un turno de un mismo hablante es de
  1,5 a 2 s (`pausa_turno`).
- **La velocidad no le gana a la sintaxis**: cerca de 17 caracteres por segundo es la meta, pero un
  testimonio rápido se lee igual y manda la frase.
- **El automático acierta ~85 %.** El resto se divide a mano, leyendo el borrador como un
  subtitulador: en `manual`, cada lista es un turno entero y " / " es el salto de línea; en `bloques`,
  el video entero. Si el texto no calza palabra por palabra, rebota nombrando la primera que no.
- **Con UNA línea, 87 %** de los bloques de dos reels divididos a mano, que al principio eran 61 %. Lo
  que lo movió:
  - los **posesivos y los cuantificadores** —«nuestro», «distintos», «varios»— no pueden cerrar una
    línea: faltaban en la lista, y eso vale también para dos líneas (en la entrevista no había pasado);
  - el **umbral del bloque corto** se escala a lo que entra en el bloque: pensado para 2 x 42, con una
    línea hacía preferir «Destacamos también que /» a tres bloques de 17 caracteres;
  - lo que **arranca después de una coma de cláusula** y sigue en el bloque próximo cuesta como un
    corte en medio de una frase («en la planta, localizada / en la ciudad»). La coma de una
    enumeración no cuenta; ésa es la regla con menos respaldo: la sostiene un caso real, y en una frase
    de prueba el resultado sin ella salía mejor.
- **Lo que el automático no sabe**: un sustantivo de un adjetivo —puede partir «la carpintería /
  nueva»— y las frases hechas que no están en la lista. Y el 87 % es de un solo hablante: con otro
  material, a leerlo igual.

### En Premiere

- **Cada bloque del SRT es un subtítulo**, y Premiere no lo vuelve a partir.
- **Si el estilo de la pista tiene la caja más angosta que el bloque más ancho**, Premiere mete un
  salto de línea de más. Se ve al importar.
- **Los títulos que van abajo, como los rótulos de un punto de venta, pueden pisarse con los
  subtítulos.** Se resuelve con la posición del estilo de la pista. Esos títulos se declaran en
  `titulos` del proyecto, por el prefijo de su nombre, para que no cuenten como cortes de plano.
  Lo mismo un logo encima. Las capas de ajuste quedan afuera solas, por el nombre —«Adjustment
  Layer» o «Capa de ajuste»—: una encima de todo taparía todos los cortes de abajo.

### Un reel: una línea en píxeles, las palabras de cada clip y el `.prproj` (2026-09-24)

Dos reels verticales de un evento, 1080×1920 a 29,97, con el estilo de un reel de la marca: UNA
línea, Montserrat Medium 48 y un tope de 770 px, que es donde en la referencia arranca el ícono de
compartir. Se hicieron con un script del proyecto porque a la herramienta le faltaba esto:

```
"lineas": 1,
"ancho": {"fuente": "~/Library/Fonts/Montserrat-Medium.ttf", "cuerpo": 48, "px": 770},
"transcripcion_por_clip": "transcripciones/scribe/{medio}.audio.json",
"tiempos": "reel", "envolvente": true,
"videos": {"<video>": {"secuencia": "<nombre>", "pistas": {"habla": ["A1"]}}}
```

- **El tope es en píxeles de la fuente real, no en caracteres**: un bloque de 29 caracteres midió
  763 px y uno de 31, 707. Un bloque que se pasa rebota, con su ancho.
- **La voz estaba adentro de un NESTED**, y en cada reel en una pista distinta: por eso `videos`
  pisa las pistas por video. `timeline_prproj.py` abre el nested, y RECORTA lo de adentro a lo que el
  nested deja ver.
- **La división fue entera a mano**, en `bloques`, leyendo como un subtitulador. **El automático de una
  línea, medido contra esas dos divisiones**, acertaba 61 % de los bloques; ahora 87 % (54 de 62) y
  93 % de los cortes. Ver *La división*.
- **Las correcciones van ancladas al CLIP**, `["TOMA", 105.27]` —el medio, o el principio de su
  nombre, y un segundo del clip—: así sobreviven a que el editor recorte. Y lo que Scribe no
  escribió —fundió una palabra repetida en una sola— va en `agregados`, también en tiempo del clip.

**Y el editor recortó un reel DESPUÉS de la entrega**, que fue la prueba que faltaba. Sacó la
primera frase, y el script del proyecto ya no pudo rehacerlo: abría el nested sin recortarlo y metía
un fragmento en −5,97 s. Con las herramientas: la corrección de la frase que ya no estaba avisó que
no aplicaba, la división rebotó en la primera palabra que ya no se oía, y sin los cuatro bloques de
esa frase salieron 24, 22 de ellos iguales a los de antes corridos 6,807 s. Los otros dos se movieron 3 y 1 cuadros, por los cortes de plano que cambiaron.

### Los tiempos: dos modelos, sin reconciliar

Cada uno salió de un trabajo y reproduce el suyo. **No es un modelo con dos ajustes**: también cambian
las reglas, y cambiar uno por el otro mueve lo que ya se entregó.

| | `"entrevista"` (el de siempre) | `"reel"` |
|---|---|---|
| entra | en el cuadro de la primera palabra | 40 ms antes: Scribe marca tarde |
| fin de la voz | el de la última palabra de Scribe | medido en la envolvente, si hay `envolvente`: Scribe estira la última palabra sobre la pausa |
| sale | 0,30 s después, y dura al menos 0,8 s | con menos de 0,7 s de pausa, pegado al siguiente; si no, 0,35 s después |
| engancha | a un corte hasta 0,32 s antes de entrar, o a 0,36 s de salir | al corte más cercano a la entrada (0,20 antes, 0,067 después), o al primero entre 0,05 y 0,7 s después de la voz |
| cortes de plano | todos los bordes de V, menos el primero y el último | sin los que tapa una pista de arriba, con los de adentro de los nested, el cuadro 0 y el último |

Medido: con la regla de cortes del reel, uno de los tres videos de la entrevista cambia una salida
0,2 s. Por eso cada modelo conserva la suya. Para quedarse con uno hay que MIRARLOS sobre el mismo
material; hasta entonces, el de entrevista es el que viene por defecto.

**Y los dos escriben el milisegundo que cae ADENTRO de cada cuadro.** A 29,97 un cuadro no es un ms
exacto, y la vía de habla redondeaba a centésimas: el cuadro 63 son 2102,1 ms, y en 2102 Premiere lo
lee en el 62. Es la misma regla que la de la canción: los tiempos van en cuadros enteros de la
secuencia. A 25 fps no cambia nada, porque ahí cada cuadro son 40 ms justos.

## Canción: la letra de un videoclip (2026-08-21)

Hecho para un videoclip. **Ninguna parte de esto es obvia** y cada paso tiene un modo de
fallar en silencio. La vía es **PNG transparentes colocados como clips**, y tiene una ventaja que no
es menor: cada subtítulo queda como un clip suelto que el usuario puede correr o recortar.

### 1. El timing es el trabajo real, y hay DOS métodos: uno falla y otro anda

**Lo que NO funciona: compuerta de energía sobre el stem de voces.** Se probó midiendo la
envolvente del stem de Demucs y buscando huecos entre frases. Resultado: **una región de 21
segundos como "una frase"** donde había cinco líneas. La causa es que el canto es *legato* —
las pausas entre versos son de dos o tres décimas y la reverberación del stem las rellena.
De 23 líneas dio 9 "medidas" (mal) y 14 repartidas por igual, que es inventar.

**Lo que SÍ funciona: Whisper sobre el stem de voces, POR SECCIÓN y con segmentos cortos.**

    whisper-cli -m <modelo> -f <trozo>.wav -l es -oj -ml 28 --split-on-word

Tres detalles, los tres necesarios:

- **Sobre el stem de voces aislado**, no sobre la mezcla. En la mezcla la transcripción sale
  ilegible; en el stem las líneas se reconocen.
- **Sección por sección, sin darle nunca los instrumentales.** Corriéndolo sobre el tema
  entero, después del segundo 166 entra en **bucle de alucinación**: repitió *"Bajo un sauzio
  orillero"* veinte veces. Es la falla clásica de Whisper sobre música.
- **`-ml 28 --split-on-word`** fuerza segmentos de dos a seis segundos. Sin eso los segmentos
  abarcan estrofas enteras y no sirven para líneas.

**Y después hay que ALINEAR**, porque `-ml` corta por caracteres y parte los versos al medio.
Se arma un stream de palabras con tiempo —repartiendo cada segmento linealmente entre sus
palabras— y se camina la letra buscando cada palabra en orden. Normalizando acentos y
puntuación. Resultado: **23 de 23 líneas alineadas, 0 problemas de orden.**

La validación de que la alineación es real vino de afuera: *"extiende sus alas"* cayó en
160,95–166,94 y el plano del cantante levantando los brazos está en 162. El usuario había marcado
esa coincidencia como algo que le gustaba **antes** de que existieran los subtítulos.

### 1.b Las PRIMERAS líneas de cada sección no estaban medidas (2026-08-21)

Y el JSON decía `medido: true` en las cinco. Es el modo de fallar nº1 del repo escrito en un
campo de datos: **una afirmación de medición que no ocurrió.**

La causa es que Whisper **pega su primer segmento al arranque del audio que se le da**. Como
el pipeline corre sección por sección, el primer segmento de cada trozo empieza en el offset 0
del trozo, o sea exactamente en el borde de la sección. Así que la primera línea de cada
sección hereda el borde en vez de medirse.

Se ve a simple vista y nadie lo miró: los cinco valores son `24.00`, `47.00`, `72.00`,
`125.00`, `150.00`. **Cinco números redondos entre veintitrés que tienen dos decimales.**

Medido contra el stem de voces, leyendo el perfil de energía a mano:

| línea | decía | la voz entra en | error |
|---|---|---|---|
| "Si la estrella…" | 24,00 | **24,48** | 12 frames temprano |
| "Y en alguna estación…" | 47,00 | 47,00 | correcto |
| "Primera parada…" | 72,00 | **72,56** | 14 frames temprano |
| "Y en alguna estación…" (2) | 125,00 | **125,56** | 14 frames temprano |
| "Será la palabra…" | 150,00 | *no medible* | canto continuo antes |

Medio segundo en un subtítulo se ve. Las tres se corrigieron; la quinta se dejó como estaba y
se le puso `medido: false` con la razón, que es lo único honesto que se puede hacer con ella.

#### Cuatro instrumentos que NO sirvieron, y por qué vale anotarlos

Antes de llegar al perfil a mano se probaron cuatro métodos automáticos. **Los cuatro dieron
números plausibles y los cuatro eran basura**, y cada uno se descartó por una prueba distinta:

1. **Máximo de la derivada de la envolvente en una ventana de ±600 ms.** Dio un corrimiento
   mediano de +340 ms, que parecía un hallazgo. Lo mató la **prueba de estabilidad**: repetido
   con ventanas de 150/300/450/600/900 ms, **21 de 23 líneas cambian de respuesta**. Un
   detector que contesta distinto según dónde lo mires no está midiendo la línea, está
   agarrando el ataque más fuerte que tiene a mano. La firma estaba a la vista antes de la
   prueba: los valores se apilaban contra el borde de la ventana (±0,48, ±0,51, ±0,58).
2. **Whisper con `-dtw large.v3.turbo`.** Corre, pero **el JSON de `-oj` no expone los tiempos
   de token**, sólo los de segmento. No hay por dónde sacarlos.
3. **Whisper con `-ml 1 --split-on-word`** (una palabra por segmento, para tener tiempos reales
   en vez de la interpolación lineal). Anda, y **empeora con más margen**: con 2 s de margen dio
   `'Si' 22.00-22.55`; con 6 s devolvió **un solo segmento `"Música"` de 28 segundos**; con 12 s
   repartió las palabras por el instrumental (`'estrella'` de 15,18 a 21,52). El modelo
   desparrama el texto sobre el silencio que se le da. Los tiempos por palabra **no son
   medición, son reparto**.
4. **Compuerta de energía con histéresis** (un umbral para "es voz", otro para "es silencio").
   El retroceso hasta el inicio de la subida camina hacia atrás por **todo el canto anterior**,
   así que las líneas de adentro reportaban el ataque de la sección: `"sin equipaje"` a los
   36,01 contestó 24,47, o sea −11,5 s. Y el conteo de líneas medibles se movió 18 → 13 → 5 al
   cambiar el umbral.

**Lo que separa el resultado bueno de los cuatro malos no es el algoritmo: es que el bueno se
NIEGA a contestar donde no puede.** Las 18 líneas de adentro caen en canto continuo, no tienen
silencio antes, y **no hay forma de medirlas con lo que hay acá**. Eso ya estaba escrito arriba
para la compuerta de energía; los cuatro intentos lo reaprendieron.

El corolario de método, que es el que se repite en todo este repo: **antes de creerle a una
medición, correrla dos veces con un parámetro distinto.** Si el resultado se mueve, el número
no era del material: era del instrumento.

### 1.c Un tiempo a MEDIO frame deja un parpadeo de un frame (2026-08-21)

`revisar` marcó un hueco de 1 frame en V3, entre `sub_11` y `sub_12`. Entre dos subtítulos
consecutivos eso no es un detalle: **el texto desaparece un frame y se ve el parpadeo.**

La causa es el mismo bug de los cortes entre frames, en otra forma. Los dos comparten el
número —`hasta` de uno es `desde` del otro— pero se colocan por caminos distintos: la cola con
`salida`, que es un punto de fuente, y el arranque con `desde`. Mientras los dos redondeen para
el mismo lado no pasa nada.

**El problema es el empate.** `88,22 / 0,04 = 2205,50`, exactamente medio frame, y ahí un
camino redondea a 2205 y el otro a 2206. De 23 tiempos fuera de grilla, los que caen en `,25`
y `,75` no hicieron daño —los dos lados redondean igual— y **el único que produjo hueco fue el
único que caía en `,50`**.

Arreglado estirando `sub_11` un frame, y **cuadriculando el JSON entero** para que una
reconstrucción no lo reintroduzca: 23 valores movidos, ninguno más de 20 ms. Se verificó
después que ningún par contiguo se hubiera separado al redondear — que se mantengan juntos es
obvio (comparten el número), y por eso mismo había que chequearlo en vez de suponerlo.

Regla corta: **los tiempos de subtítulo van en frames enteros de la secuencia**, igual que las
posiciones de la sincro. El medio frame no existe en el timeline y lo único que produce es esta
clase de hueco.

### 2. La tipografía: un `.ttc` NO se puede pasar como archivo

El usuario pidió **Helvetica Medium Italic**. En macOS vive dentro de
`/System/Library/Fonts/HelveticaNeue.ttc`, que es un *font collection* con **14 caras**.

- Pasarle el `.ttc` a ImageMagick **agarra la cara 0 —Regular— y no avisa**. Se ve derecha en
  vez de itálica y no hay ningún error.
- Seleccionar por `-family/-weight/-style` **falla**: en esta máquina ImageMagick no tiene
  lista de fuentes de fontconfig (`magick -list font` no devuelve Helvetica).

**La solución es extraer la cara a un `.ttf` propio**, con `fonttools`:

```python
from fontTools.ttLib import TTCollection
c = TTCollection("/System/Library/Fonts/HelveticaNeue.ttc")
c.fonts[11].save("HelveticaNeue-MediumItalic.ttf")   # 11 = Medium Italic
```

Los índices hay que **listarlos**, no adivinarlos: van Regular 0, Bold 1, Italic 2… y
**Medium Italic es el 11**, no el 3 ni el 10.

`fonttools` va en el venv aislado `~/.venvs/vision`, no al sistema — igual que torch.

### 3. Medir el ancho: `%[label:w]` devolvió CERO y el chequeo no chequeó nada

La primera versión medía cada línea con `magick -format "%[label:w]" label:texto info:` para
achicar las que se pasaran del área segura. **Devolvió 0 para las 23**, así que el `if` nunca
se cumplió y todas se renderizaron a cuerpo fijo sin verificar nada. Otra guarda que no
protegía.

**Lo que sí mide es el PNG ya generado**, recortando lo transparente:

    magick sub_00.png -trim -format "%w %h" info:

Eso no puede mentir: es el pixel más a la izquierda y el más a la derecha del texto real.
Medido así, la línea más ancha usó **2031 px de 3840, el 53%**, o sea que el cuerpo fijo de
104 estaba bien. La guarda rota no causó daño esa vez; el punto es que no lo habría detectado.

### 4. Un PNG fijo entra con `entrada 3600`, igual que los sintéticos

Verificado antes de hacer los 23, justamente porque un still no tiene in/out de material
como un video y `editar salida` podía no funcionar:

    insertar sub_00.png  → desde 24, dura 5 (el default), entrada 3600
    editar salida 3606.44 → dura 6.44 exacto

Así que **`salida` es un punto de FUENTE**, no una duración: hay que leer la `entrada` real
del clip recién puesto y sumarle la duración. Pedir `salida: 6.44` cae antes del in-point,
Premiere lo ignora en silencio y el still queda con sus 5 segundos por defecto.

### 5. El orden de las pistas

    V1  el corte
    V2  la capa de ajuste del color
    V3  los subtítulos      ← arriba de todo, o el color se los pinta

Si los subtítulos van DEBAJO de la capa de ajuste, el Lumetri les cambia el amarillo.

### Receta corta

1. Separar el stem de voces con Demucs (`htdemucs`).
2. Whisper por sección sobre el stem, con `-ml 28 --split-on-word`.
3. Alinear la letra corregida contra el stream de palabras.
4. Extraer la cara del `.ttc` con `fonttools`.
5. Un PNG transparente por línea, del tamaño de la secuencia, texto abajo con sombra suave.
6. Verificar los anchos con `-trim` sobre los PNG, no con `%[label:w]`.
7. Importar, insertar en la pista de ARRIBA, y `editar salida` = entrada real + duración.
