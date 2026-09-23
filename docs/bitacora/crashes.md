# Los regímenes que tiran Premiere, y el espaciado

> Bitácora movida TAL CUAL desde `CLAUDE.md` el 2026-09-23, en el orden en que
> estaba. «Arriba» y «abajo» se refieren a aquel archivo único. Los títulos no se
> tocaron: el código que cita una sección «de CLAUDE.md» la encuentra acá con `grep`.

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
