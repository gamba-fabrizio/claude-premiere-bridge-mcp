

## Vigente (2026-09-23)

- **Una guarda se verifica haciéndola fallar**, mirando por posición y sin comentarios ni strings.
  → «Una guarda se verifica HACIÉNDOLA FALLAR»
- **Medí el piso del instrumento**: si el resultado se mueve con un parámetro, no mediste. → «Medí
  el PISO DEL INSTRUMENTO»
- **Un test de render lleva un valor que tenga que verse, y un umbral.** → «Un test de render se
  hace»
- **Verificar cada paso no verifica la tanda.** → «Verificar cada paso NO verifica la tanda»
- **Un contador que mira el lugar equivocado convierte un éxito en fracaso**, y un medio sin video
  no pone nada en V. → «El contador ciego», «Un contador que mira la pista de VIDEO»
- **Homónimos: se compara la ruta, no el nombre.** → «Homónimos: el material entra»
- **Un parámetro que el verbo no lee rebota.** → «Un parámetro no declarado»
- **Antes de informar que algo no está, un control positivo.** → «Antes de informar que algo no
  está»
- **Lo que se escribe tiene que poder releerse.** → «Escribir algo que nada puede releer»
- **Un item nulo no voltea un recorrido: se cuenta.** → «Recorrer bins: un item nulo»
- **Un nombre parcial que engancha más de uno rebota.** → «El match parcial del proyecto»
- **`clips` y `revisar` leen la salida de cada pista.** → «Una pista con el OJO APAGADO»
- **Un pendiente se cierra en la misma tanda que su trabajo.** → «Un pendiente que no se cierra»

# Método de verificación

> Bitácora movida TAL CUAL desde `CLAUDE.md` el 2026-09-23, en el orden en que
> estaba. «Arriba» y «abajo» se refieren a aquel archivo único. Los títulos no se
> tocaron: el código que cita una sección «de CLAUDE.md» la encuentra acá con `grep`.

# Método de verificación

Esta es la parte más transferible del repo, y la que más caro salió aprender.

## Una guarda se verifica HACIÉNDOLA FALLAR

Sin excepción. Los casos que lo justifican:

**Una guarda que pasaba sobre código roto.** Su regex usaba `[^)]*?` para los argumentos, y
`[^)]` no puede atravesar el cierre de una llamada anidada:

```
createOverwriteItemAction(item, aTick(segundos), pista, -1)     INVISIBLE
createOverwriteItemAction(medio, juntaTick, pista, -1)          la veía
```

O sea que cubría un sitio y dejaba libres los dos donde el bug había mordido de verdad.
Verificado por mutación: con el `-1` puesto a mano, el test contestaba **"ok"**.

**Una guarda imposible de disparar.** Exigía un literal que aparece **CERO veces** en el
código: la condición era siempre false.

**Una guarda que matcheaba su propia prosa.** Buscaba un identificador en el cuerpo del verbo
y lo encontraba **en el comentario que explica por qué NO se usa**. Se arregla sacando los
comentarios antes de mirar, y exigiendo el **paréntesis** de la llamada y no la mención.
**Chequear presencia no es chequear uso.**

**Y el modo de fallo opuesto, que es peor: una guarda que rechaza código correcto.** El
filtro para saltear la DEFINICIÓN de una fábrica descartaba también su INVOCACIÓN, porque
las dos matcheaban el mismo patrón. Antes de encender una guarda nueva se contrastó contra
**96 llamadas reales**; sin eso habría roto lo que andaba.

## Medí el PISO DEL INSTRUMENTO

Variante del "medí dos casos" que se cobró tres vueltas en un día: no dos casos del material,
**el mismo caso con otro parámetro de la herramienta**.

Un benchmark daba 2,5x de mejora. Estaba inflado: cada medición incluía arrancar el proceso,
un costo fijo que Premiere no paga. Aislado, la mejora real era **5,5x** — el doble, tapada
por el arranque.

Y un detector de ataque de voz dio "los subtítulos están 340 ms tarde", que parecía un
hallazgo. Repetido con ventanas de 150/300/450/600/900 ms, **21 de 23 líneas cambian de
respuesta**. El número era del instrumento, no del material.

**Si el resultado se mueve al cambiar un parámetro del instrumento, no midió nada.** Y cuando
dos ajustes muy distintos dan el MISMO número, eso no es robustez: es el instrumento avisando
que no mide.

## Un test de render se hace con un valor que TENGA que verse

La primera medición puso un efecto en **3,7 sobre un default de 60** —o sea casi invisible— y
después preguntó si el cuadro cambiaba. Dio **9 milésimas, que es ruido**. Y la comparación
era `con !== sin` sobre strings, así que cualquier diferencia contaba: el test informó **"EL
EFECTO LLEGA AL RENDER"** sobre nada.

**Un test de render se hace con un valor que tenga que verse, y con un umbral, no con una
desigualdad.**

## Verificar cada paso NO verifica la tanda

Dos capas en la misma pista y la misma posición se comen: el overwrite pisa. **Y el verbo
informó "3/3 capas"**, porque cada una se verificaba a sí misma **en el momento de ponerla** y
nadie volvía a mirar después de poner la siguiente. Un clip truncado es legal: no es ni hueco
ni solape ni cero.

Para eso existe un verbo `revisar` que recorre la secuencia entera y sólo lee. Cuatro
chequeos, todos inequívocos a propósito, y cada uno corresponde a un daño que ya pasó:

- **Clips de duración cero** — Premiere los acepta y no se ven en el timeline.
- **Solapes** — `createMoveAction` **solapa, no pisa**, así que mover puede apilar dos clips
  en silencio.
- **Huecos, medidos en FRAMES.** En milisegundos no se puede decidir nada: 20 ms es un frame
  a 50fps y medio a 25.
- **Juntas removibles** — pegados, mismo medio y continuos: un corte que no corta nada.

Los cuatro se probaron **construyendo el daño a propósito**, no observando una secuencia
sana.

## El contador ciego

Un verbo corrió CUATRO veces y dejó 68 marcadores de más **mientras informaba que no había
pasado nada**. La API funcionaba desde la primera llamada correcta; el contador miraba el
sujeto equivocado —la secuencia, cuando los marcadores iban sobre el clip— y el bucle seguía
probando formas.

No fue la API la que mintió ni la verificación la que se confirmó sola: fue **un contador
mirando en el lugar equivocado**, que convierte un éxito en un falso negativo y encima lo
repite.

El mismo patrón, en otro verbo: un `try/catch` que convierte un fallo de lectura en lista
vacía, informa **"0 clips"** y sigue como si no hubiera nada que hacer. Visto en vivo con la
pista teniendo 88.

**Y volvió a pasar, en una sonda escrita el mismo día que releí esto.** Medía si un clon había
entrado contando los clips de **la pista que yo suponía** que era el destino; como el argumento
resultó ser un offset, el clon caía en otra. La sonda informó **"NO CLONÓ NADA" tres veces
sobre clones que sí habían entrado**.

Lo destapó **contar el total de la secuencia**: 12 clips al empezar, 18 después de las corridas
"fallidas". El número de la pista mentía; el del conjunto no. Cuando un contador parcial diga
que no pasó nada, contá el total.

## Homónimos: el material entra al clip equivocado

El importador decide "ya está" por **NOMBRE**, no por ruta. Un archivo homónimo en otra
carpeta se saltea en silencio, y después el insertador —que **también** busca por nombre—
agarra el medio VIEJO.

```
el colocador   "42 de 42 colocados · los 42 en su lugar y con su duración"
revisar        "sin problemas"
el frame       el texto del OTRO tema
```

Los dos primeros informes son **correctos**. Ninguno contesta qué medio quedó.

**La asimetría fue la única pista, y es la parte reusable.** El tema viejo llegaba hasta el
037, así que de 42 clips **38 salieron mal y los 4 últimos salieron bien**. Un fallo total se
nota; uno que deja las últimas cuatro bien parece un problema de otra cosa. **Cuando un
resultado sale mal en parte, el corte entre lo que anduvo y lo que no suele nombrar la
causa.**

Regla operativa: **los nombres de archivo generados llevan prefijo propio.** Un contador que
arranca en cero en cada carpeta es una colisión esperando.

## Un parámetro no declarado se descartaba en silencio

Cuatro bugs distintos, ninguno evidente:

```
una guarda de seguridad  -> declarada pero descartada: protección que no protegía
`segundos` en el frame   -> cuadro de otro momento, diagnóstico sobre la nada
un flag en otro verbo    -> verbo declarado roto durante horas
un filtro mal nombrado   -> una llamada perdida
```

Los tres primeros comparten la trampa: **la rama por DEFECTO se parece al éxito.** Un verbo
sin su parámetro lista y contesta "activa: X", que se lee igual que "la activé".

Resuelto con una tabla de claves aceptadas por verbo, que **rechaza** lo que no está:

```
"medios" no conoce el parámetro `filtro`. Acepta: buscar, más las guardas
proyecto y secuencia. NO se ejecutó nada.
```

Va **antes** que las demás guardas: una llamada mal escrita no tiene que ejecutar nada.

**Y lo que hace que esto no se pudra es que la tabla se DERIVA del código.** `test.js` la
vuelve a extraer y falla si no coincide, así que un verbo nuevo rompe el test en vez de
romperle la llamada al usuario.

**Y hubo que seguir los helpers, o la guarda habría sido peor que el problema.** La primera
versión miraba sólo el cuerpo del verbo y habría rechazado **llamadas correctas** — el modo
de fallo más caro posible para una guarda.

**La lección de método: antes de anotar que un verbo está roto, leer su firma.** Fueron dos
minutos de `grep` contra horas de trabajarle alrededor.

## Antes de informar que algo no está, pasá un control positivo

Ya dicho arriba para el `.prproj`, pero vale como regla general y aparece en todos lados:

- Un detector de repeticiones acústicas se calibró contra casos conocidos **antes** de usarlo:
  los positivos daban −0,07 y los negativos +0,32. **Estaba invertido.** Sin la calibración
  habría informado un hallazgo con toda confianza sobre nada.
- Un filtro nuevo se probó contra los **positivos conocidos** antes que contra los negativos
  imaginados: un umbral transferido de otro régimen volteó los 14 tramos buenos.

**Un número que se mueve al cambiar un parámetro del instrumento no midió nada. Y un vacío
no es "no hay" hasta que el lector demuestre que sabe distinguir.**

---

## Escribir algo que nada puede releer no es tenerlo

`marcar` aceptaba `duracion` y el rango entraba, pero `marcadores` devolvía sólo `segundos`,
`nombre`, `comentario` y `color`. O sea que el bridge **no podía verificar lo que acababa de
escribir**: es el *"el veredicto sale del ESTADO"* de este archivo sin estado que leer, y la
comprobación tuvo que salir de abrir el `.prproj`.

Arreglado leyendo `getDuration()`, que ya estaba a la vista. Verificado con los DOS casos, que es
lo que lo hace concluyente:

```
marcar segundos:5  duracion:3   ->  {segundos:5,  duracion:3}   resumen "5s +3"
marcar segundos:20 (sin dur)    ->  {segundos:20, duracion:0}   resumen "20s"
```

**Y un fallo de lectura NO cae a 0.** Cero es un marcador de PUNTO, una respuesta legítima:
tragarse la excepción informaría "no tiene rango" sobre uno que sí lo tiene. Va en
`duracionError` y el resumen lo nombra. Es el mismo lado por el que se paga un cuadro negro
cuando un lector que falló devuelve el valor "todo bien".

## Un contador que mira la pista de VIDEO miente con un medio que no tiene video

Un `.wav` no pone nada en la pista de video, así que un verificador que cuenta items de V1 informa
fracaso sobre un clip que entró perfecto en A1. Apareció en dos verbos el mismo día:

```
armarSecuencia   "0 de 1 fragmentos · FALLARON 1: no apareció en el timeline"   -> estaba en A1
el colocador     "6 PROBLEMA(S)" y seis "nada en Ns"                            -> estaban en A2
```

Es el contador ciego de este archivo por tercera vez, en el tercer verbo. Lo que lo vuelve caro no
es el número mal: es que **el informe queda al revés de la verdad**. Un "no entró" sobre algo que
entró manda a rehacer trabajo que estaba bien, y si alguien le hace caso y vuelve a colocar,
duplica.

La regla, que ya no da para más excepciones: **antes de escribir un verificador, preguntarse qué
hace con un medio que no tiene video.**

## Recorrer bins: un item nulo volteaba la llamada entera

Los recorridos hacían `String(hijos[i].name)` a secas, y un hueco en la lista tiraba
`Cannot read properties of null` — con eso una tanda entera rebotaba sin colocar nada. Ahora pasan
por un helper que devuelve `null` en vez de tirar.

**Y los salteados se CUENTAN y se informan**, que es la mitad que importa: un recorrido que se come
items en silencio contesta "no está" sobre algo que sí estaba. Un `try/catch` mudo habría sido peor
que el crash.

**Y el chequeo encontró el DOBLE de recorridos de los que había contado a ojo.** Miré el código,
conté tres, los arreglé, y `test.js` contestó que quedaban tres más. Son seis. Contar a ojo lo que
se puede contar con un `grep` es el mismo error que ya registró este archivo con los verbos
camelCase que la regex se perdía.

## El match parcial del proyecto, cuando es AMBIGUO

La guarda `proyecto` compara por subcadena y eso es deliberado: pedir un nombre corto y que enganche
el largo se usa. Lo que no es deliberado es que el mismo texto pueda referirse a **dos proyectos
abiertos**: ahí la guarda contestaba que sí sobre el que tiene foco, y el usuario creía estar
hablando del otro — el escenario para el que la guarda existe, sobreviviendo adentro de la guarda.

Ahora, **si el match es parcial**, se enumeran los abiertos y se rebota cuando coincide con más de
uno. Sólo cuando es parcial: con el nombre exacto no hay nada que desambiguar y cobrar una llamada
de más en el caso normal sería un impuesto. Y si no se puede enumerar, **se sigue**: no poder
averiguar no es estar en peligro.

Probado en las tres direcciones: con uno abierto el parcial pasa, con dos rebota nombrando los dos,
y el nombre exacto pasa.

## Un pendiente que no se cierra es peor que no tenerlo

Limpiando la lista de pendientes aparecieron **dos entradas que decían "SIGUE" o "sin hacer" sobre
trabajo terminado y verificado semanas antes**. En los dos casos el arreglo y su medición vivían en
otro lado —el encabezado de la herramienta, el commit— y la lista seguía diciendo que no.

Y este archivo le pide a toda sesión que lo lea antes de tocar nada, así que el efecto es concreto:
alguien evita una herramienta que anda, o vuelve a investigar algo ya medido.

**Un pendiente vencido se lee con la misma confianza que uno cierto**, y no hay forma de
distinguirlos desde adentro del texto. Al cerrar un trabajo, cerrar también su entrada, en la misma
tanda. Y cada tanto, cotejar la lista contra el CÓDIGO en vez de contra la memoria: los dos se
encontraron con un `grep` de "SIGUE|FALTA|sin hacer" y cinco minutos de leer lo que supuestamente
faltaba.

## Cerrados: casos resueltos, acotados o desmentidos

> Lo que estos casos dejaron de cómo anda hoy está arriba, en *Vigente*. Acá queda cómo se llegó.

## ~~Una pista con el OJO APAGADO no la ve NINGÚN verbo~~ RESUELTO

```
clips             la lista igual, en su lugar y con su duración
revisar           "sin problemas"
el colocador      "6 de 6 colocados y verificados"
el frame          NEGRO
```

**`VideoTrack.isMuted()` existía y nadie lo había mirado.** La lectura entró en `clips` y en
`revisar`, y con eso el fallo dejó de ser silencioso: `clips` avisa en el RESUMEN y `revisar`
mete la pista en su lista de problemas, así que ya no puede imprimir "sin problemas" sobre un
render negro.

**Las dos clases de pista, medidas por separado**, porque el aviso dice cosas distintas y
afirmar la de audio sin medirla habría sido inventar:

```
pista de VIDEO   media del cuadro  89,07  ->  0,00        (negro)
pista de AUDIO   mean -37,1 dB     ->  -91,0 dB           (silencio digital)
```

Cuatro decisiones que valen para cualquier verbo que agregue una lectura:

- **El aviso va en el RESUMEN**, no sólo en el dato: un dato que está en la respuesta y no en
  el resumen es un dato que no está.
- **En `revisar` entra en la lista que suprime el "sin problemas"**, y PRIMERO: una pista sin
  salida invalida todo lo demás que el verbo pueda informar.
- **UNA lectura por PISTA, no por clip.** El `track` ya está en la mano. Medido: el verbo pasó
  de 203 ms a 202 ms.
- **Si la lectura falla se INFORMA, no se asume `false`.** `false` significa "se ve", así que
  tragarse el error reportaría como sana una pista que no se pudo mirar.

Los tres primeros informes son CORRECTOS —el clip está ahí— y ninguno contesta la pregunta
que importaba, que es si se ve.

**Se confirma MIDIENDO el cuadro, no mirándolo**: la media dio **0** en la pista apagada y
**22,8** en otra. Un número separa los dos casos; el ojo no, porque un cuadro negro y un
cuadro vacío se ven igual.

Y hay una trampa de segundo orden: **el visor muestra un PNG negro o transparente como
BLANCO**, así que el primer diagnóstico fue "sale todo blanco" y se buscó un gráfico que no
existía.
