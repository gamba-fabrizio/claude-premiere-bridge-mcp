# Los regímenes que tiran Premiere, y el espaciado

> Bitácora movida TAL CUAL desde `CLAUDE.md` el 2026-09-23, en el orden en que
> estaba. «Arriba» y «abajo» se refieren a aquel archivo único. Los títulos no se
> tocaron: el código que cita una sección «de CLAUDE.md» la encuentra acá con `grep`.

## Vigente (2026-10-07)

- **Antes de teorizar sobre un crash, leé el reporte**: son cinco regímenes distintos, con firmas
  distintas. → «Los regímenes que tiran Premiere»
- **Una ráfaga de transacciones tira Premiere.** El espaciado real es `PAUSA + MS_POLL` y tiene que
  dar 500 ms o más; `test.js` lo exige. → «El espaciado real es la SUMA»
- **El borde se mueve con el peso y con la acción**: ~205 ms mató uno pesado y un banco pesado, y hoy
  aguantan uno chico, uno intermedio y una copia pesada con la secuencia del banco: qué lo movió no está
  separado. → «El umbral depende del PESO», «El tercer peso», «El cuarto peso», «El borde también
  depende de la ACCIÓN»
- **Menos transacciones antes que menos espera**: `porTransaccion` hasta `TOPE_LOTE` (10).
  → «Agrupar por transacción gana MÁS»
- **Un verbo con su propio bucle de lotes necesita su propia pausa entre lotes.** → «Y un verbo que
  hace su PROPIO bucle»
- **La pausa protege escrituras**; antes de una lectura no compra nada. → «El espaciado protege
  ESCRITURAS»
- **`getKeyframePtr` en ráfaga es un SIGBUS**: los valores salen de `getValueAtTime`.
  → «1. `getKeyframePtr` en ráfaga»
- **Leer valores de params en volumen tira Premiere**, y antes de barrer conviene fijarse si el dato
  ya está en una respuesta anterior. → «3. Lecturas de VALOR de params», «Releer lo que ya se tiene»
- **Verificar en un verbo de tanda no puede costar lecturas de valor.** → «En un verbo de TANDA»
- **`borrar` rebota desde el 6º borrado en 60 s**, y barrer una pista con solapes tiró Premiere.
  → «La guarda contra el BARRIDO», «4. `borrar` sobre una pista con SOLAPES»
- **Recargar el plugin con su `setInterval` vivo crasheaba**: el panel se desarma en
  `beforeunload`. → «5. Recargar el plugin»
- **Premiere se cae por lo ACUMULADO en la sesión**, no por el ritmo ni por un verbo, y el punto varía
  mucho: ~540–630 escrituras con `fijar` espaciado, de ~200 a ~3.000 con una tanda, con el panel nuevo
  igual. Guardar antes y después, y reiniciar antes de una tanda o un armado grande. → «Premiere se cae
  por lo ACUMULADO», «La tasa con el panel nuevo»
- **Un comando que quedó adentro cuando se cayó Premiere ya no se repite al reabrir.** → «El comando que
  quedó adentro»
- **Con Premiere tapado entero, oculto o con el protector, App Nap FRENA el panel** a una vuelta cada
  10–20 s: el latido va por RELOJ para que el transporte lo vea vivo, y cada llamada tarda eso. Sin App
  Nap (`NSAppSleepDisabled`) late normal. → «Premiere tapado: App Nap frena el panel»

# Los regímenes que tiran Premiere

Son **cinco distintos**, con firmas distintas, y confundirlos costó días. La regla general:
leer el `__sentry-event` o el `.dmp` **antes** de teorizar. Tres crashes se atribuyeron mal
durante dos días; los dos reportes que se leyeron contestaron en un minuto y dijeron cosas
distintas.

## 1. `getKeyframePtr` en ráfaga (SIGBUS, señal 10)

```
message "Unhandled signal!"   signal 10   threadName main
```

El método devuelve un **puntero** a la estructura interna del keyframe. **El crash es
DIFERIDO**: las llamadas contestan bien y Premiere se muere unos segundos después, que es
por qué costó tanto atribuirlo.

Reproducción: 30 clips con keyframes, tres barridos seguidos → 90 punteros en ~2s → SIGBUS.

**Arreglo:** leer el valor con `getValueAtTime` sobre el tick del último keyframe.
`getKeyframeListAsTickTimes` se sigue usando: devuelve tiempos, no punteros. Medido lado a
lado sobre un clip animado de 100 a 110:

```
frac    getKeyframePtr   getValueAtTime
0       100              100
0.25    100              102.5
0.5     100              105
0.75    100              107.5
```

O sea que el puntero **ni siquiera interpolaba**. No había nada que justificara usarlo
primero.

## 2. Ráfaga de TRANSACCIONES (SIGSEGV, señal 11)

```
message "Unhandled signal!"   signal 11   threadName dvascripting::Transient1
sourceFile   dvauxphost/queue/src/JsTaskQueue.cpp
```

No hace falta un puntero: alcanza con encadenar transacciones. Ver *El espaciado* abajo
para los números.

## 3. Lecturas de VALOR de params en volumen (`PromiseFulfillment`)

```
category   PromiseFulfillment / resolve
sourceFunc NAPIContextAdapter::CallCallback(...)
```

Tres crashes, y **la causa NO está identificada**. Lo que se probó y NO lo evitó:

| intento | qué se hizo | resultado |
|---|---|---|
| 1 | 130 params por clip, 88 clips | crash |
| 2 | tope de 40 params, 12 clips (~560 lecturas) | crash |
| 3 | 3 clips con 40 params cada uno (~120 lecturas) | crash |

El intento 3 mata la teoría del umbral: **120 lecturas en 3 llamadas se cayó, y otro verbo
hace ~176 en UNA sola y nunca se cayó.** Si el umbral explicara algo sería al revés.

**La capacidad se ELIMINÓ, no se acotó.** Un flag apagado es una invitación a prenderlo. El
verbo ahora es triage —dice si un clip tiene algo agregado, no cuánto vale— y si le llega
el parámetro viejo **rechaza**, porque un parámetro que no hace nada es peor que un error.

**Y lo que sí se midió: batchear es lo que lo dispara.** La versión que pide los valores de
a uno funciona; la que los pide de a 25 crashea. El batcheo se había hecho para ahorrar
llamadas, y esa eficiencia se pagaba con estabilidad.

**Corolario para verbos de LECTURA: que un verbo no escriba no lo hace seguro.** Éste sólo
lee y tiró la aplicación.

## 4. `borrar` sobre una pista con SOLAPES

176 clips con 119 solapes, barridos de atrás para adelante y espaciados 1,2s. **Las seis
primeras salieron; la séptima se colgó 300 segundos y ahí Premiere murió.** Siete
transacciones no son una ráfaga, así que el umbral de espaciado no explica nada acá.

Los `__sentry-event` traen **sólo tags, sin señal ni stack**, así que la causa **no está
identificada**.

**La regla operativa no depende de acertar la causa:** no barrer una pista con solapes desde
el bridge, y no barrer una pista larga aunque esté sana. En Premiere, seleccionar la pista y
apretar Delete es una operación nativa, instantánea y sin riesgo. **El bridge sirve para lo
preciso —colocar 88 clips en su frame— no para lo masivo.**

## 5. Recargar el plugin mientras su `setInterval` sigue disparando

```
sourceFile   dvauxphost/queue/src/JsTaskQueue.cpp
threadName   dvascripting::Transient2
```

El host de UXP ejecutando una tarea JS **encolada por el plugin** mientras lo desmontaba. Se
arregla desarmando el panel en `beforeunload`/`unload` —`clearInterval` más una bandera que
corta la vuelta—, las dos cosas a propósito: si el evento algún día no se dispara, la
bandera igual evita el trabajo.

**Detalle al probarlo:** la recarga que instala el arreglo todavía corre el código VIEJO, así
que ésa puede crashear igual. Recién la siguiente queda protegida.

---

# El espaciado, que es el número que más importa

## El espaciado real es la SUMA, no la pausa

Esto estuvo escrito en la unidad equivocada durante semanas. El panel tiene un `MS_POLL`, así
que **cada llamada cuesta un latido**, y la pausa de las herramientas se suma encima. El
espaciado REAL entre dos transacciones es `PAUSA + MS_POLL`.

Con eso el costo queda **cuantizado**. Medido con `MS_POLL = 700`:

```
PAUSA    0ms  ->   710ms/op   1 latido
PAUSA  600ms  ->   740ms/op   1
PAUSA  700ms  ->  1334ms/op   2
PAUSA 1200ms  ->  1442ms/op   2      <- lo que usaban las herramientas
PAUSA 1500ms  ->  2058ms/op   3
```

O sea que `PAUSA=1200` costaba **exactamente lo mismo** que `PAUSA=700`: 500 ms que no
compraban ni velocidad ni separación. Bajar `MS_POLL` no es sólo velocidad: **descuantiza el
espaciado** y recién ahí se puede buscar el mínimo.

## El umbral depende del PESO DEL PROYECTO

```
espaciado real   proyecto                      resultado
   ~205 ms       chico (15 clips)              aguantó 200 transacciones
   ~710 ms       chico                         aguantó 305
   ~205 ms       pesado (216 clips, 1284       MURIÓ en la 22 · EXC_BAD_ACCESS en 0x18
                 medios, 68 secuencias)
   ~205 ms       pesado                        SE COLGÓ en la 34 · 0% de CPU, sin dump
   ~355 ms       pesado                        aguantó 150
   ~505 ms       pesado                        aguantó 150
```

**El borde está entre 205 y 355 ms, y el fallo se reprodujo 2 de 2** — con dos desenlaces
distintos, y eso importa al detectarlo: una vez murió con `EXC_BAD_ACCESS` en la dirección
**0x18** —un puntero NULO desreferenciado a 24 bytes, no uno salvaje— y otra quedó **vivo a
0% de CPU con el panel sin latir**, que desde afuera se parece a "está tardando".

**El mismo espaciado que mató un timeline de 216 clips aguantó 200 transacciones con 15.** La
variable es el PESO, no el ritmo solo. Medir en el proyecto chico y concluir para el real es
el *"medir un caso y generalizar"* de este archivo, y casi se entrega.

**Lo que NO está probado:** n=1 en cada punto que sobrevivió, dos pesos de proyecto nada más,
y un solo verbo. Si aparece un proyecto más pesado, 505 ms puede no alcanzar.

**Y la conclusión de diseño vale más que el número: si el borde se mueve con el peso, una
constante fija es la forma equivocada.** El peso se lee barato; lo correcto sería que la
herramienta lo mire y escale sola. Con dos muestras no alcanza para escribir esa fórmula.

## El tercer peso: un proyecto intermedio aguanta al ritmo mínimo del transporte (2026-10-01)

Faltaba un tercer peso de proyecto para la curva del espaciado. Se midió en un proyecto de prueba
—122 medios, 10 secuencias—, que queda entre el chico de 15 clips y el pesado de arriba (216 clips,
1.284 medios, 68 secuencias), con la misma prueba: `editar salida` con `vinculados: true`, 150
escrituras sobre una secuencia de 50 clips, sin pausa del lado del llamador, en una sesión de
Premiere recién abierta.

```
espaciado real   proyecto                     resultado
   ~203 ms       intermedio                   aguantó 150, todas quedaron, revisar limpio
   ~203 ms       intermedio, sesión nueva     aguantó 150, todas quedaron, revisar limpio
```

Ningún crash. **La fórmula igual no sale**: 203 ms es el ritmo MÍNIMO del transporte —el panel mira
cada `MS_POLL`, 200 ms—, así que en el chico y en el intermedio el borde queda por debajo de lo que el
bridge puede pedir, y sólo el pesado cae dentro del rango. Lo que sí dice: el peso empieza a importar
del lado de los proyectos grandes, y el espaciado de 500 ms le deja 2,4 veces de margen al único borde
medido. Un proyecto más pesado que el de arriba sigue siendo el caso sin medir.

## El borde también depende de la ACCIÓN

```
editar salida   ·  ~355 ms  ·  proyecto pesado  ->  aguantó 150 transacciones
setValue Motion ·  ~503 ms  ·  proyecto pesado  ->  CRASH a las ~60 escrituras
```

O sea que un piso medido para un verbo **no es universal**. Es el error de este archivo
cometido en la regla que el propio archivo acababa de establecer.

**Y el síntoma previo vale anotarlo**: 30 segundos antes del crash,
`executeTransaction` empezó a contestar *"n.executeUndoableTransaction is not a function"*.
El objeto nativo **ya estaba inválido** y Premiere siguió contestando lecturas un rato más.
Si aparece eso, no es un bug del verbo: es Premiere ya enfermo, y lo que corresponde es
guardar y salir, no reintentar.

## Agrupar por transacción gana MÁS que apretar el espaciado

El espaciado se paga **por transacción**, no por clip. Medido sobre 30 clips:

```
porTransaccion  1    35,6s ·  30 transacciones ·  releído 30 de 30   ✓
porTransaccion 10     3,7s ·   3 transacciones ·  releído 30 de 30   ✓   9,6x
```

**Y la segunda razón vale más que la velocidad:** menos transacciones es menos exposición al
régimen que crashea. Va en la dirección correcta por las dos puntas.

**El tope es 10, medido a los golpes.** Arrancó en 50 porque sonaba prudente:

```
porTransaccion 10   ->  6 transacciones · 0,3s · releído 53 de 53 · Premiere vivo
porTransaccion 50   ->  2 transacciones · Premiere SE COLGÓ
```

Entre 10 y 50 **no hay ningún dato**, así que el tope quedó en el número comprobado y no en
uno interpolado. Es **una sola constante** compartida: tres topes sueltos se suben en uno y
no en los otros.

La ironía vale tenerla: agrupar existe para bajar la exposición al régimen que crashea, y
**agrupar DE MÁS lo vuelve a producir por otro camino**. La palanca tiene un óptimo, no una
dirección.

## Y un verbo que hace su PROPIO bucle de lotes no lo alcanza la pausa

El espaciado de las herramientas separa **LLAMADAS**. Un verbo que recorre sus lotes adentro
de una sola llamada corre todas sus transacciones **sin una pausa en el medio**: el
espaciado real es **CERO**.

```
29 fragmentos  ->  ~15 transacciones seguidas  ->  sobrevivió
88 fragmentos  ->   27 transacciones seguidas  ->  COLGÓ Premiere
```

Reproducido a pedido con el código viejo: **1 de 3**. Esa tasa es lo que hace que una
corrida limpia no pruebe nada — tiene 67% de salir bien por suerte.

**Y la trampa al bisecar: pedir MENOS acciones por transacción es lo PEOR, no lo
conservador.** Sobre esos 88 fragmentos, `porTransaccion: 1` da **177** transacciones en vez
de 27. Se descubrió calculándolo, no corriéndolo.

Arreglado con una espera entre lotes **dentro del verbo**, porque el bucle lo hace el verbo:
una pausa en quien llama no puede meterse en el medio de una llamada que ya empezó.

## El espaciado protege ESCRITURAS: antes de una lectura no compra nada

Una pausa antes de un `clips` o un `medios` no defiende de nada: no transaccionan. Se
sacaron **después de medirlo**, no por deducción, porque la duda era razonable —esa pausa
podía estar dándole a Premiere tiempo de que el estado quedara legible—:

```
fijar -> param INMEDIATO          8 de 8 lecturas vieron el valor recién escrito
insertar -> clips INMEDIATO       6 de 6 lecturas vieron el clip recién insertado
```

`test.js` mira las dos direcciones, y **la segunda importa más**: que no vuelva a aparecer
una pausa antes de una lectura (desperdicio), y que **no desaparezcan las que están antes de
las escrituras** (daño). La guarda del espaciado exige que la suma sea suficiente pero **no
que las pausas existan**: borrarlas todas la dejaba pasar.

---

## En un verbo de TANDA, verificar no puede costar lecturas de VALOR

Releer el valor de cada clip para confirmar mete al verbo en el régimen que tiró Premiere
tres veces. O sea: **la verificación habría convertido un informe optimista en una caída.**

Lo que sí es gratis, y alcanza:

```
contar keyframes    getKeyframeListAsTickTimes, SINCRÓNICO adentro del lock,
                    NO lee valores
el booleano de      executeTransaction ya lo devuelve; descartarlo no ahorra nada
la transacción
```

Con esas dos se detectan **los dos** fallos silenciosos sin una sola lectura de valor: el
param **animado** —donde la escritura va al valor base y los keyframes la tapan— y el
**limpió y no escribió**, que deja el clip sin animación mientras informa éxito.

**La regla: antes de agregar una verificación a un verbo que barre una pista, preguntarse
cuántas llamadas a la API agrega POR CLIP.** Si la respuesta no es cero, buscar el testigo
barato antes de aceptar el caro.

---

## La guarda contra el BARRIDO, y por qué los números no son los que uno propone

Barrer una pista con `borrar` de a un clip tira Premiere. Estaba documentado desde la primera vez
—176 clips con solapes— y **volvió a pasar**, con 8 llamadas seguidas espaciadas ~1,3s. La sesión
que lo provocó había leído este archivo al empezar. O sea que lo que faltaba no era documentación:
era algo que rebotara.

Ahora `borrar` rebota a partir del 6to borrado en 60s, con el mensaje que manda al Delete nativo.

**Los números no son los que proponía la nota original** ("a partir de la 3ra en, digamos, 30s").
Ese "digamos" marcaba que no estaban medidos. Lo que sí está medido es el daño: ráfagas de 8 y de
176. Con 3-en-30s, borrar cuatro clips puntuales a lo largo de medio minuto —uso legítimo y nada
raro— rebotaría, y **rechazar lo correcto es el peor modo de fallo de una guarda**.

Tres cosas del cómo:

- **Vive en el PANEL**, no en la herramienta MCP: las herramientas llaman por el transporte directo
  y saltean las MCP.
- **Cuenta los borrados que SALIERON**, no los intentos: uno que rebota por parámetros no ejecuta
  ninguna transacción, así que contarlo sólo castigaría un reintento legítimo.
- **El chequeo lee el bloque por LLAVES BALANCEADAS.** La primera versión buscaba `throw new Error`
  con un `indexOf` y **pasaba con `return {}; if (0) throw ...`**: el texto seguía ahí y la guarda
  estaba desarmada. Es el mismo agujero que tuvo la guarda del `-1`, cuyo `[^)]*?` no podía
  atravesar una llamada anidada.

## Releer lo que ya se tiene es un motivo para crashear

Leer valores de param en volumen es el régimen que tira Premiere, y está documentado. El detonante
de la última vez vale por lo evitable que era: un barrido de lecturas sobre varias secuencias y
varias pistas, **para averiguar un dato que ya estaba en la respuesta anterior**.

Antes de barrer para averiguar algo, fijarse si ya se lo tiene. El régimen peligroso no se justifica
por un dato que uno ya pidió.

## Premiere se cae por lo ACUMULADO en la sesión, en siete lugares distintos (2026-09-27)

Lo trajo un reporte de uso: una sesión terminó 46 capas con unos 95 `fijar` espaciados 1,2 s, como
pide `USO.md`, y Premiere se cayó en la escritura 57. La sesión ya venía con cientos de escrituras, y
el volcado decía que murió en la recolección de basura de fondo (`MinorGCJob` → `UserWeakCallback`,
`null+0x18`), no adentro de una edición. La hipótesis era que pesa la cantidad y no el ritmo, y se
midió tirando Premiere a propósito: trece corridas en el proyecto de prueba, con 46 capas en V2, cada
una desde Premiere recién abierto salvo donde se dice.

```
fijar Position en bucle, 1,2 s                    600 SIN CAER (14 min)
  ...y en la misma sesión, copiarEfecto           cayó en la copia 27: ~627 transacciones, 16 min
copiarEfecto de un Lumetri a 45 capas x2          90 SIN CAER
  ...y en la misma sesión, fijar en bucle         cayó en el fijar 538: ~629 transacciones, 16 min
aplicarEscalas, 46 clips por llamada              cayó en la llamada 18: ~782 clips, ~1.560 escrituras
aplicarMotion, 23 clips x 3 params por llamada    cayó en la llamada 11, 11, 42, 6, 5, 4 y 30
                                                  —de ~200 a ~2.900 escrituras—, también sin la espera
                                                  entre transacciones y en un proyecto nuevo, vacío
Premiere quieto, con el panel latiendo            21 min y ~6.000 latidos SIN CAER
```

**Los volcados caen en siete lugares distintos** del puente entre JavaScript y Premiere: la recolección
de basura (`UserWeakCallback`, y el scavenger con un puntero corrupto, `0x1500040008`), la liberación de
un timer (`clearValueOnJsThread`), la creación de una referencia (`napi_create_reference_with_finalize_callback`,
y `napi_wrap` al envolver lo que devuelve la API), la resolución de una promesa (`ConcludeDeferred`) y un
callback de `lockedAccess` (`NAPIContextAdapter::CallCallback`). Siempre en el hilo de scripts y nunca en
la edición en sí: es un estado que se corrompe con el uso, adentro de Premiere, y el bridge no lo puede
arreglar.

Lo que sale de esto, y lo que NO:

- **Espaciar no alcanza**: con el mismo ritmo, `fijar` pasó 600 en una sesión y cayó a las 538 en otra.
- **No es un verbo**: ni `fijar` ni `copiarEfecto` solos lo tiraron; la suma sí. El reporte, con su mezcla
  de `fijar` y `copiarEfecto`, es el mismo caso.
- **Una tanda NO es más segura por escritura.** `aplicarMotion` hace en una llamada lo que `fijar` en 69,
  pero cayó entre las ~200 y las ~2.900 escrituras, contra las ~540–630 de `fijar` espaciado. Lo que
  cambia es cuántas llamadas y cuánto tiempo hacen falta, no el riesgo. La variación entre corridas
  iguales es tan grande que ningún número de estos es un umbral.
- **El panel quieto no lo tira**: lo que se agota es por la actividad de la API, no por el latido.
- **Un envoltorio del contador intentaba pisar el `addAction` de cada transacción**: la asignación no tira
  y no queda. Con él, `aplicarMotion` cayó en la llamada 11 dos veces seguidas; sin él, entre la 4 y la
  42. Con esa dispersión no se puede decir que lo empeoraba, pero no contaba nada y tocaba un objeto
  nativo en medio de crashes de memoria: se sacó.

Lo que se hizo: `premiere_aplicar_motion` —escala, posición y rotación de hasta 30 clips por llamada, una
lectura de la pista, lotes de hasta 20 acciones espaciados, sin leer valores—, para que una sesión con
solo MCP no necesite 95 llamadas, y con la Rotation que ninguna tanda tenía; y un contador de la sesión
en `estado` y en el resumen de todo verbo que escribe —transacciones, y las escrituras que las tandas suman
aparte—, para que el próximo crash quede medido. Sin umbral de aviso: no hay número seguro. Lo que evita
perder trabajo es lo de siempre: guardar antes y después de cada tanda —Premiere recupera lo guardado— y
reiniciar Premiere antes de una tanda grande.

## La tasa con el panel nuevo: igual que antes (2026-10-01)

Los dos arreglos del panel del 2026-09-30 —el latido una vez por segundo y la pantalla cada ~5 s— se
midieron por tasa contra lo acumulado, con el mismo protocolo de la sección anterior: `aplicarMotion` sobre
46 capas, de a 23 clips por llamada con escala, posición y rotación, 1,2 s entre llamadas, cada corrida
desde un Premiere recién abierto, hasta el primer error o 100 llamadas. Una corrida se dio por caída sólo si
el proceso se había ido o había un reporte nuevo: con el protector de pantalla puesto el panel también deja
de latir, y eso no es un crash.

```
                              llamada en la que cayó          mediana
2026-09-27, panel viejo       11, 11, 42, 6, 5, 4, 30         11
2026-10-01, panel nuevo       45, 23, 23, 4, 26               23
```

Cayó en las cinco, entre ~200 y ~3.000 escrituras, y en los primeros 3 minutos de la sesión; las que
dejaron reporte, en el hilo de scripts, en dos de los siete lugares de arriba. **La mediana subió y no es
una mejora**: las dos distribuciones se pisan, y una prueba de rangos no las separa del azar. Con esta
carga el panel no mueve la tasa. Si ayuda en sesiones largas y livianas, donde el latido pesa más contra lo
que asigna la API, no se pudo medir, y los crashes de la interfaz no se reproducen a pedido.

## El cuarto peso: una copia pesada aguanta al ritmo mínimo, con la secuencia del banco (2026-10-01)

El 2026-09-11 el borde se remidió contra 26.5 en un banco de 434 medios, 21 secuencias y una de 216 clips,
y murió en la transacción 79 a ~202 ms. Esta vez se midió sobre una copia de un proyecto real, pesada al
revés que el de arriba: 339 medios y 35 secuencias, pero 1.700 clips de video y 856 de audio en sus pistas,
2.052 efectos y material 4K. A ~203 ms, 150 escrituras de `editar salida` con `vinculados: true`, cada
corrida desde un Premiere recién abierto:

```
secuencia editada                          corridas   resultado
50 clips de un medio, 3 pasadas               2       aguantaron
216 clips de un medio, 150 distintos          2       aguantaron, todas quedaron
216 clips de 54 medios, 150 distintos         2       aguantaron, todas quedaron
```

**Con la secuencia y el material del banco, seis de seis.** No es el largo de la secuencia editada, ni que
el material venga de uno o de muchos medios, ni el peso de timeline. Queda sin separar si fue algo propio de
aquel banco, el bridge de entonces —desde el 09-11 cambiaron el latido, la pantalla del panel, el contador
y `editar`— o el azar, porque la muerte del banco fue una sola. El espaciado de 500 ms queda como está.

## El comando que quedó adentro se repetía al reabrir (2026-10-01)

Premiere se cayó en medio de un armado de 216 clips, y su `comando.json` quedó en `intercambio/`. El
transporte lo borraba sólo al llegar la respuesta, y con Premiere caído no llega nunca; el panel guarda en
memoria el último id que ejecutó, así que uno nuevo arranca vacío y ejecuta el comando que encuentre.
Reabrir habría vuelto a armar lo que acababa de tirar Premiere. Medido en vivo con un `estado` puesto a mano
en la carpeta: el panel de antes lo ejecutó al cargar —falló sin daño sólo porque el proyecto todavía no
había abierto— y el nuevo no.

Los dos arreglos: el transporte saca su comando también al vencer la espera, si sigue siendo el suyo; y el
panel no ejecuta lo que encuentra en su primera lectura, porque el transporte sólo escribe después de ver
latir a un panel y este escribe su primer latido antes de leer. El segundo cubre lo que el primero no: un
cliente que se muere sin llegar a vencer. `test.js` ejecuta los dos contra discos de mentira, con mutación.

## Premiere tapado: App Nap frena el panel, y el latido por vueltas lo hacía parecer muerto (2026-10-07)

Una sesión de uso lo reportó: `estado` contestaba "el panel no latió" varias veces durante unos 5 minutos, con
Premiere vivo, a 0 % de CPU y sin reporte de crash. El latido avanzaba +5 cada ~55 s, contra uno por segundo. Al
frente había un navegador con un video, la máquina llevaba 15 minutos sin uso, y no había protector ni pantalla
bloqueada. Volvió a latir normal apenas Premiere pasó al frente.

Eran dos piezas juntas. macOS frena con App Nap a una app tapada entera, y con ella el timer del panel. Y el
latido se escribía cada CINCO VUELTAS, no por reloj: con la vuelta estirada, eso daba un latido cada casi un
minuto. El transporte espera 25 s a que avance, así que lo daba por muerto, aunque el panel seguía leyendo
comandos en cada vuelta.

Medido en un proyecto de prueba, con Premiere tapado por otra ventana:

```
panel                         Premiere            entre latidos       vueltas
viejo (cada 5 vueltas)        tapado, 5 min       17 a 43 s *         +5 por latido
nuevo (por reloj, 1 s)        al frente           1,01 s              ~5 por segundo
nuevo                         tapado, 3 min       10,2 a 20,5 s       +1 por latido (a veces 2–4 juntas)
nuevo, sin App Nap            tapado, 200 s       1,01 a 1,02 s       ~5 por segundo
```

\* Con huecos más cortos, de 3 a 11 s, cuando algo lo despertaba, y un tramo de 35 s a uno por segundo.

- **App Nap entra al minuto.** El panel nuevo siguió a un latido por segundo los primeros 60 s tapado, y
  después pasó a una vuelta cada 10,2 s, y a ratos cada ~20. A veces dos a cuatro vueltas salen juntas: el
  sistema junta los disparos atrasados.
- **Es App Nap, confirmado.** Con `defaults write com.adobe.PremierePro.26 NSAppSleepDisabled -bool YES` y
  Premiere reiniciado, tapado 200 s, el hueco más largo fue de 1,02 s. Cuesta ~3 % de CPU con Premiere quieto,
  contra ~0 % dormido. Va en el dominio del bundle id: un Premiere 27 arranca con App Nap otra vez, y el
  latido por reloj es la red para ese caso.
- **Un AppleEvent no lo despierta.** Después de un `get name` a Premiere, el hueco siguiente fue igual de 20 s.
- **Con el panel frenado, `estado` contesta igual, lento.** Con el viejo, siete llamadas tardaron de 3 a 27 s y
  ninguna falló: con latidos cada ~30 s, la espera de 25 s los alcanzó. El ~minuto del reporte, después de
  15 minutos quieto, no se reprodujo. Con el nuevo, cuatro de cuatro en 12 a 18 s.

**El arreglo.** El latido va por reloj (`MS_ENTRE_LATIDOS`): sin frenar es uno por segundo como antes, y frenado
late en cada vuelta. El transporte, sin el proceso de Premiere, lo dice al instante en vez de esperar 25 s al
panel. Con el proceso vivo y el latido quieto, el error dice la antigüedad del latido y su vuelta: si sube entre
una llamada y otra, el panel está frenado y no caído. `test.js` ejecuta el panel con un reloj de mentira, a 200 ms
y a 11 s por vuelta, y el transporte con un `ps` y un reloj de mentira, con mutación: 4 de 4.

**Lo que queda.** Con huecos de 20 s, a la espera de 25 s le queda poco margen, y un App Nap más profundo no se
midió con el panel nuevo: si pasa de 25 s, el error ahora dice qué es. Un protector de pantalla tapa todo, así
que probablemente frene igual; no se midió.
