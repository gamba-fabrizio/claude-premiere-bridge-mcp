

## Vigente (2026-10-12)

- **Los nombres llegan en NFC y las rutas en NFD**: se compara normalizando, y una ruta de la API
  se pasa tal cual. → «Los nombres vienen en DOS normalizaciones», «Y las RUTAS vienen al revés»
- **Premiere recuantiza el in-point a la grilla de la SECUENCIA.** Al ARRASTRAR, el del audio no; al PEGAR
  por API, sí, y hacia ABAJO: el audio vinculado y un audio solo (2026-11-02). → «Premiere recuantiza el
  in-point», «`insertar` no decía que Premiere BAJÓ la entrada»
- **`insertar` dice la entrada que Premiere bajó y el largo que cambió**; `in_out_medio` lo anticipa. Un
  subclip no se compara: se lee sin marca. → «`insertar` no decía que Premiere BAJÓ la entrada»
- **Mover no se pega al cuadro; insertar sí.** → «Sub-frame: mover NO se pega»
- **Cortar entre cuadros deja un hueco de uno**: se cuantiza con aritmética entera sobre ticks.
  → «Cortar entre frames deja huecos»
- **La grilla es la de la secuencia, no una constante.** → «La grilla es la de LA SECUENCIA»
- **Una comparación con `>` rechaza el valor que cae exacto a medio cuadro.** → «Una comparación en
  segundos con»
- **Un borde que va a Premiere se lleva al cuadro MÁS CERCANO**, y los veredictos van en ticks: Premiere
  BAJA lo que pega, y los segundos redondeados al milisegundo esconden un cuadro de más. → «Los bordes
  van al cuadro MÁS CERCANO»

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

## Los bordes van al cuadro MÁS CERCANO, y los veredictos en ticks (2026-10-12)

Una sesión que armaba un video a 30 fps pidió una capa de 442 cuadros escrita con seis decimales
—`{en: 30.733333, dura: 14.733333}`— y `armarSecuencia` contestó «en 30.733 · hasta 45.433»: **441**. A
30 fps, 14,733333 s son 441,99999 cuadros, y Premiere **baja** al cuadro los in/out que se le pegan, así
que el out cayó al cuadro de abajo. Ninguna tolerancia en segundos lo agarraba: 33 ms entran en cualquiera.

Después, `editar {salida: 14.7334}` dejó el fin 0,07 ms pasado el borde de un cuadro —recortar no se pega
al cuadro, como mover: ver «Sub-frame: mover NO se pega al frame»— y el export dibujó un cuadro de más.
`clips` y `editar` decían «45.467», igual que el fin bueno, porque redondean al milisegundo; y al
corregirlo, `editar` contestó **«NO CAMBIÓ NADA» habiendo corrido**: juzgaba con los segundos redondeados,
y 0,07 ms no llegan a un milisegundo.

Ahora:

- `armarSecuencia` y `colocarLote` llevan al cuadro más cercano los bordes que se pegan (`ticksAlCuadro`),
  cuentan la `dura` de las capas en cuadros enteros y releen el largo en cuadros (`largoDistinto`).
- `editar` juzga el cambio y hace las cuentas en TICKS, y en un clip con video a 1x lleva `desde`,
  `entrada` y `salida` al cuadro más cercano —de `salida`, el fin en la secuencia—. Un audio solo queda
  exacto, para la sincro fina; a otra velocidad tampoco se lleva, y lo avisa.
- `clips` y `editar` traen `cuadros`, leídos de los ticks: 1364,002 es un borde entre cuadros que
  «45.467» escondía.
- El mismo error estaba en `clonar`, `cerrarHuecos` y `unirVideo`, que hacían cuentas con los segundos
  redondeados: el clon caía 0,33 ms pasado el cuadro pedido, y cerrar un hueco dejaba otro de 0,33 ms.

A 25 fps nada de esto se veía: cada cuadro son 40 ms justos. Medido en vivo en un proyecto de prueba a
30 fps, y en `test.js`, que ejecuta `editar` contra una API de mentira que recorta y mueve al tick, con
mutación.

## `insertar` no decía que Premiere BAJÓ la entrada del medio a la grilla de la secuencia (2026-11-02)

Lo reportó una sesión de uso: `in_out_medio` en un ProRes de 59,94 con entradas fraccionales —0,5976, 3,2642 y
0,005 s— y después `insertar` en una secuencia de 30, para reemplazar un plano al cuadro. Los dos contestaron
bien, y el clip quedó con la entrada en 0,567, 3,233 y 0: un cuadro de secuencia antes que el original.

Ningún verbo mentía sobre lo que miraba: `in_out_medio` relee el MEDIO, que guarda 0,5976 tal cual, e
`insertar` juzgaba `entro` por conteo y nombre. Quien baja es Premiere al PEGAR, a la grilla de la SECUENCIA:
0,5976 · 30 = 17,93 → 17/30. Es la regla de «Los bordes van al cuadro MÁS CERCANO»: lo que pega lo BAJA.

El arreglo es DECIRLO, sin transacciones nuevas: `insertar` relee el clip puesto y avisa `entradaBajada` —con el
cuadro más cercano, que es lo que hay que pedirle al medio— y `largoCambiado`; `in_out_medio` avisa
`fueraDeGrilla` si la entrada no cae en un cuadro de la secuencia activa. No se corrige solo: sería tocar un
in/out que el editor puso. Y se reconoce por su FIRMA —el clip MENOS DE UN CUADRO por debajo del medio—, no por
cualquier diferencia: un PNG o un Transparent Video entran con in-point ~3600 con el medio en 0.

Medido en el proyecto de prueba: 50p en 25 con 1,02–3,02 entró 1,00–3,00, entrada y salida, y el audio vinculado
igual; en la grilla no avisó; un WAV con 0,517 entró con 0,48. Un SUBCLIP no se compara, y no se puede: uno de
2 s que entró en 23,976 con 1,9603 —0,952 de cuadro menos— sigue sin aviso porque **la API no expone su rango**.
Medido: sus in/out dan el centinela en las cuatro formas, `getMedia()` devuelve el `Media` del ARCHIVO —20 s desde
0 en un subclip 2–4, igual que en su original— y ni `ClipProjectItem` ni `ProjectItem` reflejan otro método de
rango. El `.prproj` lo tiene, pero es el último guardado: no se construyó.

**El WAV destapó un bug del lector.** `in_out_medio` sobre él contestó *«la transacción corrió y el medio NO
quedó como se pidió»*, y el clip insertado salió de 2 s: SÍ había quedado. `leerInOut` prueba VIDEO, ANY, AUDIO
y sin argumento, y se quedaba con la primera que devolviera ticks; en un medio sin video, `getInPoint(VIDEO)` da
el centinela −400000 s aunque haya marcas. Ahora el centinela no gana mientras otra forma traiga marcas.

Y eso alcanzaba a `armarSecuencia` y `colocarLote`, que leen y devuelven los in/out con `leerInOut`: a un audio
solo con marcas se las BORRABAN. Medido con el plugin de antes del arreglo instalado a propósito, y con un
testigo de afuera —insertar el WAV y mirar el clip, no releer con el lector que se prueba—:

```
                     WAV marcado 0,6–2,2, insertado ANTES del armado    insertado DESPUÉS de un armado que lo usa
código viejo         entrada 0,6, 1,6 s: las marcas estaban             entrada 0, el archivo ENTERO
código nuevo         entrada 0,6, 1,6 s                                 entrada 0,6, 1,6 s
```

Con el viejo, el armado informaba «in/out devueltos a como estaban»: un OK falso, porque lo devolvía al centinela.
`colocarLote` pasa por las mismas dos funciones y no se midió aparte.
