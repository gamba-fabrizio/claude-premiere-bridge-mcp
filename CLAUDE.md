# Bridge Claude ↔ Premiere Pro — lo que costó medir

Le da a un agente control de Premiere Pro: leer la secuencia, **mirar el frame**, navegar,
animar, editar y armar timeline. **57 herramientas MCP sobre 73 verbos del panel** — la
diferencia importa, ver *Al escribir un verbo nuevo*.

Esos dos números los chequea `test.js` contra el código. Escritos a mano envejecen: decían
33 sobre 43 cuando eran 35 sobre 46, y alguien los cruzó con la realidad y concluyó que
había verbos huérfanos donde no los había.

---

## Qué es este archivo

Seis semanas de mediciones contra la API de UXP de Premiere —del 14 de agosto al 23 de
septiembre de 2026, 292 commits— ordenadas por lo que enseñan. **Casi todo lo que está acá
se pagó con un crash, con material roto o con horas perdidas diagnosticando en el lugar
equivocado.**

Es una destilación de la bitácora privada con la que se construyó el bridge. Lo que se sacó
son los nombres de clientes y de personas, y las narraciones de trabajos sin estrenar. Lo
que quedó son las mediciones, que es lo único que le sirve a otro.

Cuando este archivo dice *"medido"*, hubo un experimento. Cuando dice *"no está
establecido"*, es literal — y esa distinción es la parte más importante del documento.

---

## Cómo está repartido esto (2026-09-23)

Este archivo son las REGLAS: lo que una sesión que edita el bridge necesita cargado siempre.
Hasta el 2026-09-23 era también la bitácora —1.222 líneas, con las reglas recién en la línea
1.030— y todo eso se cargaba en cada sesión.

```
USO.md            cómo USAR el bridge desde una sesión de trabajo. Vale también acá, y es corto
                  a propósito: se lee entero
docs/bitacora/    las mediciones, movidas TAL CUAL y partidas por tema: ver el índice de abajo
docs/api.md       las firmas y los comportamientos medidos de la API: se lee ANTES de tocar un verbo
README.md         el manual: instalar, qué hace cada herramienta, los flujos
```

**Lo nuevo no vuelve acá.** Un caso va al archivo de su tema en `docs/bitacora/`; acá sube solo
una regla que cambia cómo se trabaja, en una línea y con el puntero a su caso. `test.js` le pone
tope de líneas a este archivo: sin una guarda crece solo, una sesión a la vez.

**Las reglas de uso se cargan también acá**, porque una sesión que edita el bridge lo prueba con
Premiere: @USO.md

## Por qué está armado así

Un panel UXP **no puede abrir sockets**. Así que el servidor MCP y el panel se hablan por
una carpeta que el panel poletea:

```
agente  ->  servidor MCP (node)  ->  intercambio/  <-  panel UXP (dentro de Premiere)
```

Eso tiene una consecuencia que gobierna todo el resto: **cada llamada cuesta un latido del
poll**. Ver *El espaciado real es la SUMA*.

---

## Cómo se verifica acá

El bridge se verifica **con el bridge**, que es cómodo y peligroso a la vez.

- `node test.js` cubre lo que se rompe en silencio: dos scripts del panel declarando el
  mismo global (es SyntaxError y mata el archivo entero), verbos del servidor que el panel
  no conoce, las dos rutas de `intercambio/` apuntando a lados distintos, el `id` del
  manifest colisionando con otro plugin UXP instalado.
- **El panel tiene que estar abierto en Premiere**, si no las herramientas fallan al
  instante con "el panel nunca latió".
- **Cada cambio en `plugin/` necesita recargar.** Y si el plugin está INSTALADO —no cargado
  por UDT— la copia instalada es una COPIA, no un symlink: hay que reinstalar y reiniciar
  Premiere. `test.js` compara las dos copias y falla nombrando el archivo.
- Sin las herramientas MCP cargadas, el transporte directo sirve igual:
  `node -e "require('./server/bridge.js').enviar('estado').then(r=>console.log(r.resumen))"`

**`premiere_frame` es la verificación de último recurso y la mejor.** Devuelve el cuadro
como imagen. Cuando algo importa, mirá en vez de deducir.

---

## Los tres modos de fallar, todos ya pagados

**1. La API falla en silencio.** Devuelve éxito y no hace nada, o hace otra cosa. Por eso
**cada verbo devuelve qué encontró, no si salió bien**: "keyframes 0 → 1", no "ok". Y los
errores dicen qué había, no qué faltaba.

**2. La verificación simétrica se confirma sola.** Que el bridge lea 25 después de escribir
25 **no prueba nada** si leer y escribir usan la misma conversión. Pasó dos veces con el
reloj de material, y las dos veces la mentira era consistente. La verdad tiene que venir de
afuera: un frame, o una persona mirando Effect Controls.

**3. Medir un caso y generalizar.** Todos los bugs grandes salieron de acá. `Position` no
era `{x,y}` sino indexado por número. El param de escala SÍ cambia de nombre con Uniform
Scale (se midió un clip, se concluyó que no). El reloj de material ignoraba la velocidad, y
pasó todas las pruebas porque los clips corrían a 1x. **Antes de escribir una regla, medí
dos casos distintos.**

**Corolario: una guarda contra el error imaginado deja pasar el real.** El chequeo de que
las dos listas del catálogo midieran lo mismo no agarró que fueran promesas, porque
`undefined !== undefined` es falso.

### Y el inverso, que es menos obvio

No alcanza con desconfiar del mensaje de éxito: tampoco hay que creerle al de fracaso.
`editar` contesta **"NO CAMBIÓ NADA"** cuando lo que se le pide es lo que ya hay, y eso es
la respuesta correcta. Tratarla como fallo dejó dos clips en el limbo con la herramienta
informando "0 de 2".

**La lección común no es desconfiar del mensaje: es no usarlo como veredicto. El veredicto
sale de releer el estado.**

---

## El timeline no es solo video

Fue el punto ciego más caro y estaba metido hasta en el código de verificación. Antes de
tocar cualquier verbo nuevo, preguntate qué hace con el audio:

- `clips` lista `V2` y `A1`, y los verbos que apuntan a un clip aceptan esa etiqueta.
- **El vínculo la API no lo expone**: no hay `getLinkedItems` y el segundo argumento de
  `addItem` no los trae. Se deducen por medio de origen y rango de tiempo iguales. `borrar`
  y `editar` los arrastran; sin eso, borrar deja el audio huérfano y mover lo desincroniza.
- Contar solo pistas de video da por bueno un cambio a medias.

---

## Reglas que ya se pagaron

Una línea cada una. Donde hay caso, está en el archivo de `docs/bitacora/` que se nombra.

- **El plugin instalado es una COPIA**, no un symlink: un cambio en `plugin/` no corre hasta
  reinstalar y reiniciar Premiere (`node herramientas/recargar.js --reiniciar`), y reiniciar le
  corta el trabajo a quien esté usando Premiere. `test.js` compara las dos copias.
- **El espaciado que cuenta es `PAUSA + MS_POLL`** y tiene que dar 500 ms o más: a ~200 ms se cae.
  El borde se mueve con el peso del proyecto y con la acción. → `crashes.md`
- **Menos transacciones antes que menos espera.** Agrupar con `porTransaccion` hasta `TOPE_LOTE`
  (10), que es UNA constante para todos los verbos: con 50, Premiere se colgó. → `crashes.md`
- **Leer VALORES de params en volumen tira Premiere.** Los valores van de a uno, y antes de barrer
  hay que fijarse si el dato ya está en una respuesta anterior. → `crashes.md`
- **`borrar` rebota desde el 6º borrado en 60 s.** Vaciar una pista es Delete nativo o rehacer la
  secuencia; nunca barrerla, y menos con solapes. → `crashes.md`
- **Guardar antes y después de cada tanda.** Es lo que volvió gratis cada crash.
- **Lo nuevo se prueba en un proyecto de prueba descartable**, nunca en uno de trabajo, y con todos
  sus medios: un medio faltante saca un modal que traba cualquier prueba desatendida.
- **Un panel, un cliente por vez.** Mientras corre una tanda, el progreso se mira en el disco o en
  el log, nunca preguntándole al panel: las dos colas se pisan y una llamada se vence.
- **Nunca `pkill` a Premiere**: deja un dump que se lee como crash. `recargar.js` lo cierra con un
  macro que manda el Cmd+Q a Premiere, no a la app del frente.
- **Los macros de Keyboard Maestro fallan callados** con la pantalla bloqueada —ahí no entra ni una
  tecla—, y los que buscan por imagen también cuando una sesión remota oculta la pantalla.
- **Mirar antes de deducir.** Una captura de la ventana de Premiere —solo esa:
  `screencapture -x -o -l <ventana>`— contesta en segundos lo que el código no.
- **Una guarda se prueba haciéndola fallar**, mirando POR POSICIÓN y sin comentarios ni strings.
  Una rama "no pude comprobar" que informa ok no es una guarda, y rechazar uso correcto es su peor
  fallo. → `verificacion.md`
- **Antes de escribir un verificador, preguntate qué hace con un medio SIN VIDEO.** Tres verbos
  informaron "no entró" sobre un audio que sí había entrado. → `verificacion.md`
- **Un lector nuevo no informa "no hay" sin un control positivo**: un vacío es "no lo encontré".
  → `verificacion.md`, `firmas-y-limites.md`
- **Un parámetro con el mismo nombre significa lo mismo en todos los verbos**: `pistaAudio` es
  1-based en todos (A1 es 1).
- **Premiere devuelve los nombres en NFC y las rutas en NFD.** Se compara normalizando, y una ruta
  que devolvió la API se pasa tal cual, nunca retipeada. → `cuadros-y-nombres.md`
- **Un pendiente se cierra en la misma tanda que su trabajo**: uno vencido se lee con la misma
  confianza que uno cierto. → `verificacion.md`

## Al escribir un verbo nuevo

- **Chico y sobre algo que ya existe.** Nada de "ejecutá este JS": con una API que falla en
  silencio, un verbo genérico produce código plausible que no pasó.
- **Devolvé el antes y el después**, no un booleano.
- **Contá el efecto COMPLETO**, no la parte que se te ocurrió mirar.
- **Nombrá el objetivo explícitamente** en los verbos destructivos. Operar sobre "el
  seleccionado" es una sorpresa fea cuando nadie está mirando.
- **Decí cuántos Cmd+Z hacen falta**, contando las transacciones que de verdad corrieron.
  Decir "uno" cuando son dos deja al usuario con medio cambio puesto creyendo que lo sacó.
- **Y exponelo en el servidor, o no existe.** Un verbo que vive sólo en la tabla del panel es
  invisible desde las herramientas MCP: se usa el más parecido que sí está expuesto, y ese
  hace otra cosa. Ya pasó dos veces.
- **Decí lo que NO comprobaste.** "3 ESCRITOS (transacción corrida; el valor NO se releyó)"
  es honesto; "3 aplicados" no lo era.
- **Antes de adivinar una firma, reflejala** con el verbo `api`, que lee nombres sin llamar a
  nada; si igual no se deduce, enumerá los valores reales y probalos. La prueba es el efecto, no
  que la llamada no tire. → `docs/api.md`, *Firmas que no se adivinan*

`test.js` chequea **las dos direcciones**: que no haya verbos sin herramienta, y que los que
no la tienen estén **declarados a propósito** en una lista. El default —no hacer nada— falla.

## Cosas que NO se tocan

- **El `id` y el `shortname` del manifest.** Premiere identifica al plugin por ahí: cambiarlos
  lo instala como uno nuevo, y si coinciden con los de otro plugin UXP instalado, uno pisa al
  otro. `test.js` lo chequea contra todos los instalados.
- **La ruta del `intercambio/` en el panel y en el servidor** tienen que apuntar al mismo
  lado. El servidor la deduce de `__dirname`; el panel la tiene escrita a mano porque corre
  adentro de Premiere. **Mover el repo obliga a editar la del panel**, y `test.js` compara
  las dos.
## Pendientes abiertos (2026-09-23)

- **`armarSecuencia` pone los fps pero NO el formato del reloj**: con material de otra cadencia la
  regla cuenta mal. El arreglo es poner el formato de display junto con los fps y releerlo; a mano,
  *Sequence Settings → Display Format*.
- **`frame` llega truncado con cuadros grandes** por el transporte directo: la espera mira que el
  PNG exista, no que termine de escribirse. Hay que exigir que el tamaño se estabilice.
- **`audio.js` pisa la transcripción anterior** si se corren dos motores con el mismo `--destino`:
  el motor no está en el nombre del archivo. Mientras tanto, un `--destino` por motor.
- **`importar` a veces recibe un hueco en la lista de items**: está blindado y sigue sin causa.

## Índice por tarea: qué leer ANTES de tocar algo

Los punteros van por TAREA y no por síntoma: las trampas de acá hacen falta antes de escribir la
llamada, no después de que algo se rompa. Todos en `docs/bitacora/`:

**Cada archivo arranca con *Vigente*: leé eso primero** —las primeras ~40 líneas, con `limit`— y
bajá a un caso solo cuando haga falta: los punteros «...» dicen a cuál.

```
crashes.md            un verbo que barre una pista, encadena transacciones o lee params, y el
                      espaciado; y cuando Premiere se cae o se cuelga
firmas-y-limites.md   las firmas medidas, lo que la API no permite (copiarEfecto COMPARTE la
                      instancia, clonar sí copia, relink), el cartel que traba el cierre, y lo
                      que el .prproj tiene y la API no expone
cuadros-y-nombres.md  Unicode, la grilla de cuadro, el sub-frame, los huecos de un cuadro
verificacion.md       escribir o arreglar una guarda, medir el piso del instrumento, contadores
                      ciegos, controles positivos, homónimos, pendientes
```

## Estilo

Comentarios y textos en castellano; los nombres de la API en inglés. Los comentarios explican
**por qué**, sobre todo cuando la razón es una trampa que ya se pagó — que en este repo es
casi siempre.

Un comentario que describe la intención en vez del código **es peor que ninguno**, porque el
próximo que lo lea no va a mirar. Pasó: un encabezado afirmaba que los params se leían
sincrónicamente adentro de un lock, y el código pedía cada valor con un `await` afuera. Ese
comentario tapó el régimen que después crasheó.
