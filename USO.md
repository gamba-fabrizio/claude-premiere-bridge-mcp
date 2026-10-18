---
name: premiere
description: "Reglas para OPERAR Adobe Premiere Pro con el bridge: las herramientas premiere_* (estado, clips, frame, insertar, cortar, editar, fijar, keyframe, armar_secuencia, exportar...) y los scripts de herramientas/ del repo, que leen y escriben el timeline del editor. Invocala ANTES de la primera llamada a premiere_* o al bridge: cada regla salió de un crash o de material roto. Es para editar en Premiere; no para componer video en HTML (eso es HyperFrames) ni para modificar el código del bridge, que se hace en una sesión abierta en su repo."
---

# Usar el bridge

Para las sesiones que OPERAN Premiere desde un trabajo, no para editar el bridge: eso se hace en
una sesión abierta en el repo, con su `CLAUDE.md`. Es corto a propósito, así que se lee entero.
Es también la skill `premiere` —la misma, por symlink—: si la invocaste, no hace falta leerlo aparte.
Cada regla salió de un daño real; el caso completo está en `docs/bitacora/`, y el índice por tema
en `CLAUDE.md`.

## Antes de la primera llamada

- **El panel tiene que estar abierto en Premiere.** El plugin está instalado y arranca con
  Premiere. Sin Premiere, las herramientas fallan al instante con "Premiere NO está abierto"; con
  Premiere y sin panel, a los 25 s, con "el panel no latió" o "nunca latió". Se le dice al editor y
  no se insiste, salvo que la vuelta del latido suba en la llamada siguiente: eso es Premiere frenado
  por el sistema, no sin panel (ver «Premiere y la máquina»).
- **Todo opera sobre el proyecto CON FOCO y su secuencia ACTIVA**, no sobre la carpeta de la
  sesión. `estado` empieza por el nombre del proyecto: leelo. En toda llamada que escriba pasá
  `proyecto` —y `secuencia` si hay dos parecidas—: rebota si no coinciden, o si el nombre parcial
  engancha más de una. Las herramientas de `herramientas/` lo deducen solas.
- **Cada verbo devuelve qué encontró, no si salió bien, y el veredicto sale de RELEER el estado**
  —`clips`, `revisar`, un `frame`—, no del mensaje. Esta API acepta escrituras que no aplica, y a
  veces "NO CAMBIÓ NADA" es la respuesta correcta. Darlo por bueno sin mirar es el error que más caro
  salió.
- **Si el editor está trabajando en Premiere, no operes sin que te lo pida.**
- **Guardá (`premiere_guardar`) antes y después de cada tanda.** Es lo que volvió gratis cada crash.
- **Lo que no usaste nunca, o una tanda grande, se prueba primero en un proyecto de prueba**
  descartable, no en el del editor.
- **Si encadenás escrituras a mano, espaciadas**: a ~200 ms entre transacciones Premiere se cae, y
  el borde baja con los proyectos pesados. Las herramientas ya espacian.
- **Premiere se cae por lo ACUMULADO en la sesión, aunque espacies**, y el punto varía mucho: medido en
  el proyecto de prueba, ~540–630 escrituras con `fijar` espaciado y de ~200 a ~2.900 con una tanda.
  Ninguno es un umbral. Guardá antes y después de cada tanda —Premiere recupera lo guardado— y reiniciá
  antes de una grande (`node herramientas/recargar.js --reiniciar`). `premiere_aplicar_motion` hace con
  una llamada lo que `fijar` con 69, pero no es más segura por escritura. `estado` dice cuánto lleva la
  sesión.

## Cómo leer lo que contesta

- **`insertar` se juzga por `entro`.** Con `entro !== true` no edites el clip que haya en ese
  punto: puede ser uno viejo del mismo medio.
- **`frame` es la mejor verificación: mirá en vez de deducir.** Y cuando importa, MEDÍ el cuadro
  (la media): un negro y un vacío se ven iguales, y el visor muestra un PNG transparente como
  blanco. Una opacidad se mide en el ALFA del PNG: la luminancia no la ve.
- **`revisar` después de cada tanda**: ceros, solapes, huecos en cuadros, juntas, pistas con la
  salida apagada, y vecinos del mismo medio que REPITEN MATERIAL —se pisan en la fuente y ese tramo
  sale dos veces, con el timeline limpio—. Esto último sólo a 1x: los pares a otra velocidad los cuenta
  como sin medir. Verificar cada paso no verifica la tanda.
- **Un clip FUERA DE ORDEN en la lista de su pista no se dibuja ni sale en el export**, aunque `clips`
  lo lea en su lugar. Lo dejaba `cortar` hasta el 2026-09-30, y lo deja cualquier movimiento por API que
  pasa por encima de un vecino —`editar` ahora lo rebota—. `revisar` lo marca `FUERA DE ORDEN`. Se
  repara DUPLICANDO la secuencia, si no está anidada en otra: medido con `duplicarSecuencia`, que no es
  herramienta MCP a propósito, así que se corre por el transporte directo, o lo hace el editor
  con Duplicar. Mover el clip a mano en Premiere también lo reordena.
- **Un parámetro inventado rebota**: por MCP, nombrando la clave que sobra; por el transporte directo,
  nombrando las que acepta. Antes de concluir que un verbo está roto, leé su firma; y si el editor dice
  que "siempre funcionó", el problema es la llamada.
- **Un dato que está en la respuesta y no en el resumen también cuenta**: `medios` tiene tope de 60
  e informa `total`; leé el campo, no el largo de la lista.
- **Los segundos vienen redondeados al milisegundo; los `cuadros`, no.** `clips` y `editar` los
  traen leídos de los ticks: una fracción —1364,002— es un borde ENTRE cuadros, y Premiere dibuja el
  cuadro que el clip toca apenas. «45.467» decía lo mismo del fin bueno y del que mostraba uno de más.

## Trampas por verbo, medidas

- **`fijar` fija un valor; `keyframe` ANIMA** en el playhead. Sobre un param ya animado, `fijar`
  escribe el valor base y la animación lo tapa.
- **A `keyframe`, `agregar_efecto` y `motion` nombrales el clip** (`pista` + `indice`): con Selection
  Follows Playhead —prendido en esta máquina— mover el playhead SELECCIONA el clip de abajo, y sin
  nombrarlo operan sobre ése. En `keyframe`, un punto que cae fuera del clip rebota sin escribir nada;
  `motion` avisa si el playhead no está sobre el clip, porque lo animado se lee en el borde.
- **`editar salida` es un punto de FUENTE, no una duración.** Un PNG o un Transparent Video entran
  con in-point ~3600: leé la `entrada` real y sumale la duración. Y **`editar entrada` además
  MUEVE el clip**: la entrada en una llamada y `desde` en otra. En un clip con video, a 1x, `desde`,
  `entrada` y `salida` van al cuadro MÁS CERCANO —de `salida`, el fin en la secuencia— y el resumen
  dice qué movió. Un audio solo queda exacto, para la sincro fina, y a otra velocidad también.
- **`borrar`, `editar` y `desactivar` arrastran el audio vinculado**, que se deduce por medio, rango e
  in-point: TODOS los streams de un multicanal, y apuntados a un stream de audio, también el video y
  los otros streams. Si dos planos del mismo medio están en el mismo instante y el in-point no
  desempata, no tocan nada y lo dicen; `vinculados: false` toca sólo el clip nombrado. El `apagado`
  de `editar` es SÓLO el clip, a propósito: el plano entero se apaga con `desactivar`.
- **`pistaAudio` es 1-based (A1 es 1)**: 0 rebota, y una que no existe se crea, pero UNA y al final:
  pidiendo A9 con seis, el audio cae en A7 (`pistaAudioReal` dice dónde quedó). Un multicanal pone un
  stream por pista desde ahí y crea las que falten, y `insertar` dice dónde cayeron los otros
  (`otrasPistasAudio`). El overwrite PISA también en audio, así que dos cosas en la misma pista y
  posición se comen.
- **Un medio sin video no pone nada en V**: su clip se busca en la pista de audio.
- **`borrar` rebota desde el 6º borrado en 60 s.** Vaciar una pista es seleccionarla y Delete en
  Premiere, o `borrarSecuencia` + `armarSecuencia`. Nunca barrerla, y menos con solapes: tiró
  Premiere. Y deja la selección VACÍA (`seleccionVaciada`): hasta el 2026-09-24 dejaba adentro el
  clip borrado, y la edición siguiente en ese lugar tiraba Premiere.
- **`armarSecuencia` crea aunque el nombre exista**, no reemplaza. `fragmentos` son
  `{desde, hasta, medio}` en segundos de FUENTE; `capas`, `{en, dura, pista, medio, desde,
  pistaAudio}`. Pone los fps y el formato del reloj que les toca, y lo relee: si no entra, lo
  dice. Los bordes van al cuadro más cercano y `dura` en cuadros enteros: Premiere BAJA al cuadro lo
  que pega, y una `dura` con seis decimales apenas debajo del borde perdía un cuadro entero. Si el
  largo releído en cuadros no es el pedido, lo dice (`largoDistinto`); `colocarLote`, igual. Y
  Premiere corta el nombre después del último punto: `secuencia` trae el que quedó. Si se
  corta a mitad, el error dice qué secuencia dejó y con cuántos fragmentos y capas. Los in/out de
  los medios los devuelve a como estaban (`inOut` dice cuántos): hasta el 2026-09-24 los limpiaba, y
  un PNG limpiado entra con DOCE HORAS. Un still que ya quedó así NO se arregla
  reimportándolo —`importar` saltea lo que ya está—: se cura con `in_out_medio` `entrada: 0,
  salida: 5`. Y no se lo reconoce leyéndolo: se lee "sin marca", igual que un video sano; lo delata
  insertarlo en una secuencia descartable. Si dos fragmentos SEGUIDOS del mismo medio se pisan en la
  fuente, avisa (`pisados`): ese tramo va a salir dos veces. No lo rebota, por si es a propósito.
- **La cola de `cortar` es un CLON**: trae efectos, nombre, apagado y el mismo audio en las mismas
  pistas, y no pisa nada. Con audio vinculado queda SIN VÍNCULO en Premiere —la API no crea
  vínculos—: el bridge la sigue emparejando, y a mano es Cmd+L. A otra velocidad que 1x rebota. Cada
  corte borra por dentro un clon estacionado, con su propio tope: 15 por minuto, medido sin problemas a 23.
  `sacar_rangos` va de a ~7 rangos por minuto y, si el tope no alcanza para el rango siguiente, frena limpio:
  los que faltan quedan sin tocar y se piden de nuevo tal cual. `borrar` suelto sigue en 5.
- **`borrar_secuencia` prefiere el nombre EXACTO, y si no hay ninguno toma una PARCIAL**: con una sola
  secuencia que contenga el texto, borra ésa. Si coinciden varias rebota, y dos con el mismo nombre se
  eligen con `duracion`. Dos gemelas —mismo nombre y mismo largo— se borran a mano.
- **`marcar` cuantiza al cuadro.** Con `clip`, el marcador va al MEDIO: `segundos` es tiempo de
  fuente y aparece en toda instancia de ese material. Con comentario y color son tres transacciones,
  y el resumen dice cuántos Cmd+Z: como todo verbo que escribe en varias, cuenta las que corrieron.
- **`subclip` de un medio SIN VIDEO no entra**: con un WAV committea y no aparece nada (medido el
  2026-10-18), y el verbo lo dice como fallo. El de un video entra.
- **`transicion` es solo video** —el crossfade de audio va a mano— y no se puede releer: el conteo
  prueba que apareció, no que esté bien puesta.
- **Con dos efectos del mismo nombre** —dos Lumetri—, pasá `indiceEfecto`: 0 el primero, y `efectos` los
  marca #0, #1. Sin él, las escrituras rebotan y las lecturas leen el primero y lo avisan.
- **`copiarEfecto` NO copia: COMPARTE la instancia.** Tocar el destino cambia el origen, en otra
  secuencia y sin aviso. Para una copia independiente, `clonar` (el clip entero) o Cmd+C / Cmd+V.
  Opacity y Blend Mode viven en el componente Opacity y se fijan aparte.
- **`exportar` pide `modo` siempre, sin default**: `ya` es el único que se confirma, pero la llamada
  espera 30 min —si vence, el render sigue: no lo relances, mirá el disco—; `ame` no confirma nada y
  arranca la cola SÓLO si estaba parada: el play de Media Encoder alterna, así que con la cola corriendo
  el ítem entra a su turno y en pausa queda esperando. Con AME cerrado la arranca igual: su log no registra que se
  cerró, y lo mira el transporte. Y **con un preset `.mov` la cola ignora el rango** y exporta la secuencia
  entera, así que esa combinación rebota. `lote` no exporta. Si el export se cancela o falla, lo
  dice, no reintenta y repone el in/out. El preset H.264 va de la carpeta `4E49434B_48323634`: el
  mismo nombre en la de QuickTime escribe `.mov`. Respeta los in/out de la secuencia, que
  `limpiarRangos` saca. Y el archivo se mide de afuera: duración por stream y paquetes de video.
- **La escala de un clip que ya está en la secuencia se LEE** —con `motion` uno, con `leer_param` un
  rango—, no se calcula de las dimensiones del archivo. `escala` va de a 30 clips: la respuesta trae
  `siguiente`, que se pasa como `desdeIndice`. Sin tope, sobre material 4K pesado, tiró Premiere.
- **Las capas de ajuste no se crean por API y no se escalan**: se inserta una que ya exista, y
  escalada la corrección queda en un rectángulo.
- **`relink` no tiene Cmd+Z.** `clonar` a la pista SIGUIENTE a la última la crea —es la forma de agregar
  una pista de video— y más arriba rebota; no hay API para borrar pistas.
- **El nivel de un audio (`Volume > Level`) es CRUDO**: 0 dB es 0,1778 y 1 es +15 dB, medido exportando.
  Se pide con `db` en `fijar` y `keyframe`, y `leer_param` y `param` lo devuelven en `db`: un −6 pasado
  como `valor` dejaba el clip MUDO, y ahora rebota. El fader de la PISTA no lo toca el bridge.
- **Los proxies no tienen `detachProxy`**: no adjuntes uno que viva en una carpeta temporal. Ni
  importes nada del scratchpad (`/private/tmp`): el arranque de la máquina lo vacía, y el proyecto
  saca Link Media en cada apertura, que traba el Cmd+Q del reinicio siguiente.
- **Las rutas que devuelve la API vienen en NFD**: pasalas tal cual, nunca retipeadas.
- **`cerrar_proyecto` guarda antes de cerrar y no descarta nunca.** No cierra el último abierto ni
  uno cuyo `.prproj` ya no está en disco —guardarlo abriría un cartel que el panel no ve—: esos los
  cierra el editor. Si el que cerrás tenía el foco, el foco se va solo a otro, y el resumen dice a
  cuál.

## Lo que NO se hace por el bridge

- Barrer o vaciar pistas: ver `borrar`, arriba.
- Leer valores de efectos en volumen: tiró Premiere cuatro veces.
- Replicar un look para retocarlo después: Cmd+C / Cmd+V, ver `copiarEfecto`.
- Importar una transcripción: el Import del panel Text, a mano. Y los captions: un SRT entra con
  `importar`, pero ponerlo en la secuencia —que crea la pista de captions— es a mano.
- Cerrar un proyecto DESCARTANDO sus cambios, tampoco por el transporte directo: lo decide el
  editor, a mano. La única excepción es `recargar.js --reiniciar`, abajo.
- Formatos de intercambio (AAF, FCPXML, OTIO): a mano, porque pierden cosas en silencio.

## Premiere y la máquina

- **Nunca `pkill` a Premiere.** Cerrar y reabrir es `node herramientas/recargar.js --reiniciar`:
  guarda los proyectos abiertos, cierra con el macro y exige que el panel vuelva. Uno abierto cuyo
  `.prproj` ya no está en disco —carpeta movida o renombrada, disco desmontado— lo cierra DESCARTANDO,
  porque guardarlo abre un cartel que traba el Cmd+Q: si puede pasar, avisale al editor antes.
- **Un panel, un cliente por vez.** Mientras una tanda corre, el avance se mira en el disco o en el
  log: preguntarle al panel en el medio le hace vencer una llamada a la tanda.
- **Mirar la pantalla contesta en segundos, pero SOLO la ventana de Premiere**: el número de
  ventana sale de `CGWindowListCopyWindowInfo` y se captura con `screencapture -x -o -l <n>`. Los
  otros monitores pueden tener cosas privadas.
- **Con la pantalla bloqueada no entra ningún macro de Keyboard Maestro**, y con el Privacy Mode de
  Jump fallan los que buscan por imagen. Los dos fallan callados. El protector de pantalla marca la
  sesión como bloqueada aunque no tenga contraseña: `--reiniciar` lo saca y vuelve a mirar.
- **Con Premiere tapado entero por otra ventana, oculto o con el protector, macOS lo FRENA (App Nap)**:
  al minuto, el panel pasa a dar una vuelta cada 10 a 20 s, y cada llamada tarda eso. Contesta, lento.
  Si igual sale "el panel no latió", el error dice la vuelta del latido: si subió en la llamada
  siguiente, está frenado y no caído, y se destraba con Premiere al frente —que no se trae si el editor
  está usando otra cosa—. Sin el proceso de Premiere, el error lo dice al instante. Para una tanda
  desatendida, `caffeinate -d`, por el protector. Sin App Nap
  (`defaults write com.adobe.PremierePro.26 NSAppSleepDisabled -bool YES`, y reiniciar Premiere) late
  normal tapado, medido, a cambio de ~3 % de CPU quieto, y en esta máquina está puesta desde el
  2026-10-07. Va por el bundle id: un Premiere 27 vuelve a dormirse hasta que se la pone de nuevo.
- **A Media Encoder no se lo cierra mientras arranca**: un `quit` a los 21 s de abrirlo lo tiró, y ya
  arrancado cierra limpio con el `quit` común. Que el proceso se haya ido no prueba que cerró bien: mirá
  si quedó un `.ips` nuevo en `~/Library/Logs/DiagnosticReports`.

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
timeline_subtitulos.js,  subtítulos de HABLA: la línea de tiempo —por el bridge, o del .prproj
timeline_prproj.py,      guardado con los nested abiertos—, el cruce que lista qué revisar y el
cruzar_subtitulos.py,    SRT dividido por sintaxis, también de UNA línea con tope en píxeles. El
subtitular.py            método y los criterios, en `herramientas/SUBTITULOS.md`
proxies.js               genera o adjunta proxies (`--perfil prores|h264`, `--proxies <carpeta>`)
locucion.js, musica.js,  ElevenLabs. La key sale solo de $ELEVENLABS_API_KEY, y se consulta
sonido.js                antes de gastar créditos
recargar.js              recarga o reinicia Premiere y comprueba que el panel volvió
```

## Si encontrás un bug del bridge

**No lo arregles desde una sesión que lo está usando**: el arreglo corre los tests y lleva
reinstalar el plugin y reiniciar Premiere, y eso se hace desde el repo. Anotá qué pediste, qué
contestó y qué había de verdad, y avisale a quien esté usando Premiere.
