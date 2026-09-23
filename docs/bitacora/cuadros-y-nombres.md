

## Vigente (2026-09-23)

- **Los nombres llegan en NFC y las rutas en NFD**: se compara normalizando, y una ruta de la API
  se pasa tal cual. → «Los nombres vienen en DOS normalizaciones», «Y las RUTAS vienen al revés»
- **Premiere recuantiza el in-point a la grilla de la SECUENCIA, y el del audio no.** → «Premiere
  recuantiza el in-point»
- **Mover no se pega al cuadro; insertar sí.** → «Sub-frame: mover NO se pega»
- **Cortar entre cuadros deja un hueco de uno**: se cuantiza con aritmética entera sobre ticks.
  → «Cortar entre frames deja huecos»
- **La grilla es la de la secuencia, no una constante.** → «La grilla es la de LA SECUENCIA»
- **Una comparación con `>` rechaza el valor que cae exacto a medio cuadro.** → «Una comparación en
  segundos con»

# Unicode, cuadros y otras trampas del mundo real

> Bitácora movida TAL CUAL desde `CLAUDE.md` el 2026-09-23, en el orden en que
> estaba. «Arriba» y «abajo» se refieren a aquel archivo único. Los títulos no se
> tocaron: el código que cita una sección «de CLAUDE.md» la encuentra acá con `grep`.

# Unicode, cuadros y otras trampas del mundo real

## Los nombres vienen en DOS normalizaciones distintas

macOS entrega los nombres de archivo en **NFD** —"á" es `a` más una tilde combinante— y
Premiere devuelve los NOMBRES en **NFC**. Se ven idénticos y no son la misma cadena:

```
del disco  : 61 cc81 6c696461     ("a" + U+0301)
de Premiere: c3a1   6c696461      (U+00E1)
```

Cobró dos veces al mismo tiempo y en silencio: el importador no reconoció que ya estaban y
los **duplicó**, y el insertador informó *"no hay ningún medio que coincida"* con el medio
ahí, visible en el panel.

**De 35 archivos, los dos únicos con tilde fueron los dos únicos que fallaron.** En
castellano esto no es un caso borde: es la mitad del material. Y el diagnóstico costó una
hipótesis equivocada —se culpó a la COMA del nombre— hasta mirar los bytes.

Corolario cobrado semanas después: una comparación de rutas en otra herramienta **no tenía**
aplicado el helper de normalización, y rechazaba un armado correcto imprimiendo dos líneas
idénticas en pantalla. **Una regla implementada en un lugar no se aplica sola al de al
lado.**

### Y las RUTAS vienen al revés que los nombres

Los **nombres** salen en NFC; las **rutas de archivo**, que vienen del filesystem, salen en
**NFD**. Medido sobre un item con acento en la ruta: `ruta === ruta.normalize("NFD")` da true
y NFC da false.

Importa porque hay métodos que comparan la cadena **exacta**. Uno de búsqueda por ruta
devolvía `array de 0` sobre un medio que estaba en el proyecto, con su archivo presente, y
estuve a un paso de anotar que no servía:

```
la ruta tal como la devuelve la API   NFD  ->  1
la misma en NFC                            ->  0
```

**El error fue mío: RETIPEÉ la ruta** como literal en la línea de comando en vez de pasar la
que la API había devuelto. Mi tipeo salió NFC.

Y lo que lo destapó no fue mirar mejor el código: fue un **control positivo** con una ruta sin
caracteres no-ASCII, que devolvió 1 y probó que el lector funcionaba.

**La regla corta: no retipear nunca una ruta que la API ya devolvió.** Si hay que construirla,
`normalize("NFD")`.

## Premiere recuantiza el in-point a la grilla de la SECUENCIA

Que la API escriba sub-frame es cierto; que eso sirva para ganar precisión, **no**.

Un in-point de 3,10 —frame exacto a 50fps, medio frame a 25— arrastrado por el usuario quedó
en **3,12**, y el error de sincronía pasó de −9 ms a **−29 ms**. Y **el audio NO se
recuantiza con el video**: el mismo arrastre dejó el video en 3,12 y su audio vinculado en
3,10, con lo cual el par deja de tener el mismo rango y la deducción del vínculo **no
encuentra socio**.

**La regla: posición, in-point y out-point los tres en frames de la SECUENCIA**, porque lo
que tiene que ser múltiplo exacto no es cada número sino la DIFERENCIA `pos - ent`.

El costo se acepta a propósito: el error sube de ≤10 ms a ≤20 ms. **Un error de 19 ms que no
se mueve es mejor que uno de 9 que se convierte en 29 al primer arrastre** — y sobre todo,
19 ms es mejor de lo que se puede hacer a mano.

## Sub-frame: mover NO se pega al frame, insertar SÍ

```
insertar (createOverwriteItemAction)    SE PEGA al frame
editar desde (createMoveAction)         NO se pega: aceptó 0,005 y 0,010 s
editar entrada (createSetInPointAction) NO se pega: aceptó 22,430 s
```

El toggle de *Show Audio Time Units* **no hace falta**: gobierna a qué se pega el MOUSE. La
API trabaja en TickTime —254.016.000.000 por segundo— y saltea el snapping.

## Cortar entre frames deja huecos de un frame

`createSetEndAction` guarda el **tick exacto** y no snapea; el overwrite de la cola **sí**
snapea. Cortando en 313.03 sobre una secuencia a 25fps la cabeza terminaba en 313.03 y la
cola arrancaba en 313.04.

**Pegar la cola en el tick exacto de la cabeza NO alcanza** — hay que cuantizar el punto de
corte **antes de tocar nada**. Y la cuantización no sale por la API:
`alignToNearestFrame(timebase)` contesta *"Illegal Parameter type"*. Lo que anda es
aritmética entera sobre ticks, con `getTimebase()` que **son ticks por frame**:

```js
Math.round(ticks / ticksPorFrame) * ticksPorFrame
```

**Detalle de proceso que costó una vuelta entera:** la primera versión tenía un `catch` vacío
alrededor de la cuantización. No cuantizó, la tanda dio idéntica y no había ninguna pista de
por qué. Recién al hacer que el verbo **informara** apareció el "Illegal Parameter type".

## La grilla es la de LA SECUENCIA, no una constante

Una herramienta tenía `const FPS = 25` fijo. En un proyecto a **50fps**, cuantizar a 40 ms
movió la posición un cuadro y dejó **cinco de once clips** desincronizados.

**Y es el peor tipo de defecto**: el clip mide lo mismo, no hay hueco ni solape, el revisor no
lo ve, y el colocador informa "colocado y verificado" — porque verifica contra lo que él
mismo cuantizó. Se descubre ESCUCHANDO, no mirando.

---

## Una comparación en segundos con `>` rechaza el valor que cae EXACTO a medio cuadro

El cuantizador tenía una guarda razonable —"si el redondeo se fue más de medio cuadro, no cuantizo"—
escrita como `Math.abs(despues - antes) > 0.5 / fps`. Un valor que cae exacto a medio cuadro
—3,5 s a 25 fps son 87,5 cuadros— da `0.020000000000000018 > 0.02`, que es **true**: la guarda
rechazaba un redondeo correcto y devolvía el tick sin cuantizar.

Se detectó midiendo, no leyendo: se pidió `duracion: 3.5` y volvió 3,5 en vez de 3,52. Ahora se
compara **en cuadros** con una tolerancia.

Es la guarda contra el error imaginado rechazando el caso correcto, otra vez, y por punto flotante:
el mismo `undefined !== undefined` con otro disfraz.
