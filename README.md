# Claude ↔ Premiere Pro

Un bridge que le da a Claude acceso de lectura y escritura a Premiere Pro: leer la
secuencia, **mirar el frame** bajo el playhead, animar, editar y armar timeline.
**56 herramientas MCP sobre 73 verbos del panel.**

> **Esto salió de un flujo de trabajo real, no de un ejercicio.** Se usó para armar
> cortes de videoclips, cursos e institucionales, y casi todo lo que hay acá se pagó
> con un crash o con material roto. Antes de tocarlo, leé **[`CLAUDE.md`](CLAUDE.md)**:
> tiene los cinco regímenes que tiran Premiere, con sus umbrales medidos, y las firmas
> de la API que costó descubrir. No es documentación de cortesía — es la diferencia
> entre que ande y que te tire la aplicación con el proyecto abierto.

> **Sin garantía.** Escribe sobre tu timeline. Guardá antes de cada tanda: esa costumbre
> es lo que hizo que cuatro crashes costaran cero.

```
Claude ──MCP/stdio──> server/ ──carpeta compartida──> plugin/ ──> API premierepro
```

## Por qué está armado así

El panel UXP **no puede escuchar en un puerto** —no abre sockets servidor— así
que la dirección se invierte: el panel polea una carpeta y el servidor deja el
comando ahí. La carpeta es `intercambio/`, acá adentro.

El servidor la resuelve desde `__dirname`, pero **el panel la tiene escrita a
mano**: corre adentro de Premiere y no sabe dónde está este repo. Si movés el
repo, actualizá `RUTA_BRIDGE` en `plugin/index.js`.

Todo esto se midió en Premiere antes de escribirlo, con una sonda descartable.
Lo que contestó:

| Pregunta | Respuesta |
|---|---|
| ¿La API acepta escribir sin un gesto del usuario? | **Sí.** Un `setInterval` entra a `lockedAccess` y escribe. |
| ¿UXP frena el timer cuando el panel pierde el foco? | **No.** Sigue latiendo mientras editás. |
| ¿Las rutas con espacios necesitan `encodeURI`? | **No**, van crudas. |
| ¿Se puede confirmar visualmente? | **Sí**, `Exporter.exportSequenceFrame` funciona. |

## Instalar

**0. Dos cosas que hay que editar antes de nada**, y `node test.js` te las va a
reclamar a las dos:

```
plugin/index.js      RUTA_BRIDGE  ->  la ruta ABSOLUTA a tu copia + /intercambio
plugin/manifest.json id           ->  uno TUYO (com.tunombre.premierebridge)
```

La ruta la tiene escrita a mano el panel porque corre adentro de Premiere y no sabe
dónde está este repo. El `id` identifica al plugin para Premiere: si coincide con el de
otro plugin UXP instalado, uno pisa al otro.

**En un clon recién bajado, `node test.js` falla TRES veces a propósito**, y las tres
son la lista de lo que falta hacer:

```
el manifest colisiona con otro plugin UXP    -> poné tu propio `id`  (paso 0)
el panel y el servidor apuntan a distinto    -> poné tu `RUTA_BRIDGE` (paso 0)
server/index.js NO carga                     -> falta `npm install`   (paso 3)
```

Con esos tres resueltos tiene que decir **`todo ok`**.

**1. El plugin.** Cargá `plugin/` en el UXP Developer Tool (Add Plugin →
`plugin/manifest.json` → Load). Abrí el panel en Premiere: *Window > Extensions >
Claude Bridge*. Tiene que decir "vuelta N" subiendo.

**2. Los hooks** (opcional). git no versiona `.git/hooks/`, así que en un clone
nuevo hay que instalarlos:

```bash
herramientas/hooks/instalar.sh
```

Hay uno solo, `post-commit`, que respalda cada commit: un push a `origin` y, si configurás
`git config respaldo.bundle <ruta>`, un *bundle* de git —todo el historial en un archivo— en
esa ruta, que se relee después de escribirlo. Existe porque empujar a mano se olvida: un
respaldo llegó a quedar seis días y 24 commits atrás sin que nada lo avisara. Y es un bundle
y no un repo porque un push a un repo adentro de una carpeta sincronizada dijo "ok" y el
commit nunca quedó. Para recuperar: `git clone <el bundle>`. `test.js` compara el instalado
contra el del repo y falla si difieren.

**3. El servidor.**

```bash
cd /RUTA/A/TU/COPIA/premiere-bridge/server && npm install
```

El repo trae un `.mcp.json` que registra el servidor para las sesiones abiertas
en esta carpeta. Con eso alcanza: abrí Claude Code acá y aceptá el servidor
cuando lo pregunte.

Si preferís tenerlo en todas tus sesiones y **tenés el CLI instalado** (la app de
escritorio sola no lo instala):

```bash
claude mcp add premiere-bridge --scope user -- node /RUTA/A/TU/COPIA/premiere-bridge/server/index.js
```

## Las herramientas

| Herramienta | Qué hace |
|---|---|
| `premiere_estado` | Secuencia, medida, fps, pistas, clip seleccionado y su pista |
| `premiere_secuencias` | Lista las secuencias del proyecto, o cambia la activa |
| `premiere_clips` | Todos los clips con pista, índice, nombre y tiempos |
| `premiere_radiografia` | Una pista entera con TODO lo necesario para reconstruirla —Motion, efectos con valores, deshabilitado, velocidad— y el veredicto `intacto`: qué se perdería si la rehago |
| `premiere_leer_param` | UN param para un RANGO de clips en una llamada. `limite` 25 por defecto: el umbral que tira Premiere está entre 176 (medido bueno) y 560 (medido malo) |
| `premiere_seleccionar` | Cambia el clip seleccionado, por nombre o por pista+índice |
| `premiere_playhead` | Lee o mueve el playhead, en segundos |
| `premiere_frame` | El cuadro bajo el playhead, como imagen |
| `premiere_vistazo` | Varios cuadros repartidos, para ver de qué es el material |
| `premiere_analizar` | Cuadros Y el texto que se dice en cada uno, alineados |
| `premiere_catalogo` | Busca entre los efectos instalados (330 acá) |
| `premiere_agregar_efecto` | Le agrega un efecto al clip |
| `premiere_efectos` | Los efectos del clip y los nombres exactos de sus params |
| `premiere_param` | El valor de un param y en qué segundos tiene keyframes |
| `premiere_motion` | Atajo: Position y escala del clip, con sus keyframes |
| `premiere_keyframe` | Escribe uno o varios keyframes; con `lista`, anima |
| `premiere_borrar_keyframe` | Borra keyframes por tiempo, sin tocar los demás |
| `premiere_mover_keyframe` | Mueve un keyframe de tiempo, conservando su valor |
| `premiere_curva_keyframe` | Cambia la curva: lineal, bezier, hold o tiempo |
| `premiere_editar` | Mueve, recorta o apaga un clip |
| `premiere_medios` | Qué hay en el panel de proyecto, bin por bin |
| `premiere_insertar` | Pone un medio en una pista, en el segundo que se pida |
| `premiere_borrar` | Saca un clip y sus vinculados |
| `premiere_cortar` | Parte un clip en dos, en un segundo dado |
| `premiere_sacar_rangos` | Saca tramos de la secuencia cerrando el hueco |
| `premiere_cerrar_huecos` | Cierra las juntas de un frame que dejan los cortes |
| `premiere_resolucion` | Cambia el tamaño de cuadro de la secuencia |
| `premiere_escala` | Fija la escala del Motion en todos los clips |
| `premiere_fijar` | Fija un param del Motion en un clip, sin keyframes |
| `premiere_renombrar` | Le cambia el nombre a un clip del timeline, sin tocar el medio |
| `premiere_marcadores` | Los marcadores de la secuencia, con comentario y color |
| `premiere_marcar` | Deja un marcador en un segundo, con nombre, comentario y color |
| `premiere_desmarcar` | Saca marcadores por nombre, o todos |
| `premiere_editar_marcador` | Mueve un marcador, le cambia el color o el rango, sin rehacerlo |
| `premiere_transcripcion` | El texto del clip con tiempos de secuencia, o dónde dice algo |
| `premiere_armar_secuencia` | Crea una secuencia y le pega fragmentos de un medio |
| `premiere_borrar_secuencia` | Saca una secuencia del proyecto |
| `premiere_cortes_de_escena` | Detecta cambios de plano en un clip; `marcar` no toca el timeline, `cortar` lo parte, `subclips` los crea |
| `premiere_etiquetar` | Etiquetas de color en el panel de proyecto; sin `color` sólo lee |
| `premiere_interpretar` | Lee o cambia los fps con que Premiere lee un medio; sin `fps` sólo lee |
| `premiere_proxy` | Lee o adjunta el proxy de un medio; sin `archivo` sólo lee |
| `premiere_relink` | Repunta un medio a otro archivo; el archivo tiene que existir y NO hay Cmd+Z |
| `premiere_transicion` | Pone un fundido en un corte. Default Cross Dissolve moderno; el AUDIO no lo toca |
| `premiere_clonar` | Duplica un clip con sus efectos; el clon es INDEPENDIENTE del original |
| `premiere_subclip` | Un pedazo con nombre de un medio, en el panel; verifica que el item aparezca |
| `premiere_desactivar` | Apaga o prende el ojito DE UN CLIP, o de una pista entera en una sola transacción; existe para dejar los suplentes a la vista sin que tapen el corte |
| `premiere_renombrar_pista` | Le pone nombre a una pista de video o audio; relee para confirmar |
| `premiere_exportar` | Renderiza la secuencia con un preset `.epr`; comprueba que el archivo aparezca |
| `premiere_limpiar_rangos` | Saca los in/out de la secuencia (el Opt+X): `exportSequence` los RESPETA y un out viejo estira el export con negro al final |
| `premiere_quitar_efecto` | Saca un efecto de un clip; el simétrico de agregar |
| `premiere_abrir_proyecto` | Abre un .prproj por su ruta, o trae al frente uno ya abierto (no lo recarga) |
| `premiere_crear_proyecto` | Crea un .prproj nuevo y lo deja con el foco |
| `premiere_guardar` | Guarda el proyecto, y comprueba que el archivo se escribió |
| `premiere_importar` | Importa archivos al panel de proyecto, opcionalmente a un bin; no necesita secuencia activa |
| `premiere_bins` | Lista el árbol de bins, crea los que falten, mueve medios adentro y borra bins vacíos |
| `premiere_revisar` | Recorre la secuencia y devuelve lo que quedó mal: ceros, solapes, huecos en frames, juntas |

Las de Motion operan sobre **el clip seleccionado**. Empezá por `premiere_estado`
o `premiere_clips`: sin eso se escribe a ciegas.

### Verbos que NO son herramienta

El panel entiende diez verbos más que el servidor no expone. Existen y andan,
pero solo por el transporte directo:

```bash
node -e "require('./server/bridge.js').enviar('leerEscalas', { pista: 1 }).then(r=>console.log(r.resumen))"
```

| Verbo | Qué hace | Por qué no está expuesto |
|---|---|---|
| `aplicarEscalas` | Escala y posición a muchos clips, por tandas | Van por tandas desde un script con pausas: como herramienta suelta invitan a la ráfaga de transacciones que tira Premiere |
| `aplicarZooms` | Anima un zoom in en muchos clips, por tandas | idem |
| `aplicarAnim` | Aplica una animación calculada afuera, clip por clip | idem |
| `leerEscalas` | Lee escala y posición de toda una pista, en una pasada | idem |
| `unirVideo` | Fusiona clips de video contiguos, sin tocar el audio | idem |
| `unirAudio` | Une los pedazos de audio contiguos | idem |
| `ajustarAlCuadro` | *Fit to frame* sobre un clip | idem |
| `duplicarSecuencia` | Copia una secuencia entera | Toca el proyecto entero; un error cuesta caro |
| `mirarMedio` | Cuadros de un medio del panel, sin tocar el timeline | Diagnóstico |
| `api` | Refleja nombres de métodos sin llamarlos | Diagnóstico |

**Esta lista no se mantiene a mano.** `test.js` la cruza contra
`SIN_HERRAMIENTA_A_PROPOSITO` y contra las herramientas registradas, en las dos
direcciones: agregar un verbo sin decidir qué hacer con él rompe el test. Hasta
el 2026-08-15 esta tabla estaba mezclada con la de arriba y el README anunciaba
diez herramientas inexistentes —la de poner marcadores entre ellas— mientras se
comía las dos que sí existían.

Y `test.js` compara también **esta página contra las herramientas registradas**,
por eso los verbos de la tabla de acá van sin el prefijo `premiere_`: cualquier
cosa escrita como una herramienta entre comillas invertidas tiene que existir
de verdad.

`premiere_seleccionar` y `premiere_playhead` son las que hacen que el resto
sirva. Sin ellas, el bridge solo ve lo que el usuario dejó seleccionado y el
momento donde dejó el cursor — una mirilla que mueve otro.

## Transcribir en tanda — `herramientas/audio.js`

Desde Premiere 26.5 la API **crea** transcripciones, además de leerlas. Lo que sigue sin poder es
**recibir** una hecha afuera: `importFromJSON` devuelve un cascarón vacío, así que lo que transcribe
otro motor entra al panel Text solo a mano, con su Import. Esta herramienta transcribe en tanda y
deja, de cada medio, qué se dice y qué suena en cada segundo de la fuente, con tres motores:

| motor | dónde corre | lo que da |
|---|---|---|
| `premiere` (el default) | en Premiere: importa el medio al proyecto con foco si no está, dispara la transcripción y la relee | gratis, y queda incrustada en el proyecto. Pierde nombres propios y números |
| `scribe` | en la API de ElevenLabs | el más completo y el único que separa hablantes. Gasta créditos |
| `whisper` | local, sobre archivos que ni siquiera están importados | el único que toma glosario. Sobre audio difícil, su VAD se come habla real |

**El ranking cambia con el material**, y más palabras no quiere decir mejor: la cabecera de
`audio.js` tiene lo medido. Si el texto se va a LEER —subtítulos, una cita, una voz en off— no
alcanza con Premiere, porque un nombre de marca perdido o un número con un factor de mil se
entregan.

No es un verbo del panel a propósito: el panel corre adentro de Premiere y no
puede leer archivos de audio ni ejecutar `ffmpeg`, y de un wav sale la envolvente de
los tres motores.

**Instalar** (una vez por máquina). `ffmpeg` hace falta siempre; `whisper-cpp` y los dos
modelos, solo para `--motor whisper`:

```bash
brew install ffmpeg whisper-cpp
D="$HOME/Library/Application Support/whisper-cpp/models" && mkdir -p "$D"
curl -L -o "$D/ggml-large-v3-turbo.bin" https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin
curl -L -o "$D/ggml-silero-v5.1.2.bin"  https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v5.1.2.bin
```

Son ~1,5 GB el modelo y ~900 KB el VAD. La herramienta avisa con la ruta exacta
si falta alguno.

**Usar:**

```bash
node herramientas/audio.js material.mp4 --destino /ruta/donde/escribir

# whisper, con el glosario del proyecto
node herramientas/audio.js material.mp4 --motor whisper \
     --glosario @/ruta/proyecto/glosario.txt --destino /ruta/donde/escribir
```

Sin `--destino` escribe al lado del material, y en una tanda de 147 clips eso son
cientos de archivos nuevos entre los crudos. Los clips **sin palabras** solo
dejan el `.audio.json`: el `.srt` y el `.premiere.json` estarían vacíos.

Y **no pisa la transcripción de otro motor**: si en el destino ya hay una de otro, rebota
antes de transcribir —cuando pisar todavía no costó créditos ni minutos—, y `--pisar` la
reemplaza.

Deja tres archivos al lado del original, todos en segundos de la **fuente**:

| | |
|---|---|
| `.audio.json` | `palabras` (`texto`, `desde`, `dura`, `confianza`, `eos`) y `tramos` (`VOZ` / `SUENA` / `SIL`) |
| `.premiere.json` | lo mismo en el esquema de `Transcript`, para el día que se resuelva la importación por API |
| `.srt` | subtítulos, que es lo que Premiere SÍ importa a mano con `File > Import` |

El SRT corta por fin de oración y no por cantidad de palabras, y fusiona los
bloques huérfanos: el tope de caracteres puede cortar a mitad de frase y dejar
una palabra sola parpadeando (medido: quedó un bloque con "compases." de 0,45s).

**El glosario lo toma solo `whisper`**: con otro motor, la herramienta avisa y lo ignora. Y
es del PROYECTO, no del bridge, así que va en un archivo al lado del material y se pasa
con `@`. Los nombres propios de un curso de bajo no le
sirven a otro trabajo.

**Escribilo como PROSA, nunca terminando en una lista.** Un glosario que decía
"…Términos: porcellanato, cerámico, junta, mesada…" hizo que Whisper, sobre clips
sin voz, **siguiera la lista** en vez de transcribir: aparecieron tres clips cuyo
texto era *"Términos: por su piquito armado"*, uno de ellos repitiéndolo seis
veces. El prompt es contexto para continuar, así que una enumeración abierta
invita a continuarla. Medido el 2026-08-17 sobre 147 clips.

Y **no filtres por confianza para descartar alucinaciones**: no separan. En esa
misma tanda, una alucinación tenía confianza media 0,820 y una charla real de
rodaje 0,358. Lo que sí separa locución de todo lo demás es palabras por segundo.

### Las tres cosas que se midieron acá, y por qué están así

Se midieron con `whisper`, antes de que hubiera motor de Premiere. El umbral de silencio vale
para los tres, porque sale de la onda y no del motor.

**El VAD no es opcional.** Sin él, atravesando un pasaje largo sin voz el
timestamp **deriva 12 segundos** y el modelo **inventa texto** sobre la música
—apareció un "¡Gracias!" donde sólo hay bajo—. Con VAD no procesa lo que no es
voz: no deriva, no alucina, y tarda 3 veces menos.

**El glosario cambia el resultado.** Sin él salió "hito revé" y "los bamban"; con
él, "Elito Revé" y "Los Van Van", las tres menciones bien y con acento. Premiere
escribió ese nombre de tres formas distintas en el mismo módulo. Sesgar antes es
mejor que corregir después: una corrección que no se puede verificar se lee igual
de segura que una verificada.

**El umbral de silencio es RELATIVO al clip.** Un absoluto no generaliza: medido
sobre dos clips reales, uno de locución con música vive en −20 dB y uno de habla
seca en −40, así que el mismo número clasifica bien uno y mal el otro. Se usa el
percentil 5 del propio clip más un margen. Si hay música todo el tiempo, `SIL`
simplemente no aparece — que es la respuesta correcta, no una falla.

**Lo que NO hace:** distinguir un bajo de un piano. Dice "suena algo". Para
etiquetar el instrumento haría falta un clasificador (YAMNet, PANNs), y se
engancharía **sólo sobre los tramos `SUENA`**, que ya están aislados — el costo
es la instalación de Python, no el diseño.

### Los tiempos de palabra mienten en los arranques en falso, y el VAD lo caza

Cuando alguien empieza una frase, se corta y la repite, Whisper puede **pegar la
primera palabra del intento abortado al principio de la toma buena**. Medido el
2026-08-17 sobre el clip 68 de una jornada real: la frase salió como una sola,
pero adentro tenía un hueco de **5,8 segundos** entre `¿Sabías` (7,44s) y `que`
(14,75s). Tomar el `desde` de la primera palabra daba un in **siete segundos
antes de que empiece a hablar**.

Los tramos del VAD sirven de **verificación de afuera** porque se miden en dB
sobre la onda y no dependen de Whisper: ahí el tramo `VOZ` arrancaba en 14,40s,
exactamente donde había que cortar. La regla que salió de eso:

- si adentro de la frase elegida hay un hueco entre palabras **mayor a ~1,5s**, el
  in no es confiable: la parte útil es la de después del hueco, y el in va al
  arranque del tramo `VOZ` que la contiene;
- y si el in no cae en **ningún** tramo `VOZ`, se avisa en vez de entregar un
  número plausible.

Sobre 36 rangos, **2 tenían el in mal** —por 5,8s y por 3,2s— y los dos los
encontró este cruce. La prueba final fue de afuera: recortar cada rango y
**volver a transcribirlo**, que es la única forma de que el error no se confirme
solo, porque elegir y verificar con los mismos timestamps de Whisper no prueba
nada (es el modo de fallar nº2 del `CLAUDE.md`).

### La corrección hay que verificarla, y el chequeo tiene DOS lados

La regla de arriba asume que lo útil está **después** del hueco, que es cierto en
un arranque en falso. Pero un hueco también puede ser una **pausa en medio de la
frase**, y ahí mover el in se come el principio. Medido sobre una jornada con
guion leído: **16 de 51 rangos se "corrigieron" y 8 estaban mal**, uno moviendo
el in a un tramo de voz de 0,8 segundos para una frase de 10.

El arreglo es barato: después de corregir, contar qué fracción de las palabras
sigue adentro del rango. Si baja del 70%, la corrección se descarta — el hueco
era una pausa.

**Y el chequeo de densidad tiene un lado ciego.** Detecta palabras APIÑADAS
—demasiadas por segundo, señal de tiempos corrompidos— y no detectaba lo inverso:
un beat demasiado RALO, que es casi todo silencio. En esa misma jornada, 9 de 58
rangos tenían **68 segundos muertos adentro**; el peor eran 26 segundos para 23
palabras.

El "hueco mayor" **no sirve** como medida —el peor caso tenía su hueco más grande
en 2,1s y aun así era 88% silencio, porque estaba repartido—. Lo que sirve es la
**fracción del rango cubierta por tramos `VOZ`**, que además viene del VAD y no de
Whisper. Con eso: el silencio de las PUNTAS se recorta solo, que es inequívoco, y
el de adentro se informa con los números, porque sacarlo parte el corte en dos y
eso ya es montaje.

### Cuánto más largo sale un corte automático

Comparado contra el montaje real del mismo material, dos jornadas:

- gente hablando suelto → **+15 a +20%**
- una locutora **leyendo un guion** → **+40%**

**El predictor no es la cantidad de material sino si el locutor lee o improvisa**:
leyendo se pausa entre frase y frase para acordarse de la siguiente, y esas pausas
quedan adentro de un corte hecho a nivel de frase.

Y medido, **no es todo aire**: en la jornada del +40%, el montaje real tenía 20%
menos palabras. Las dos terceras partes de la diferencia eran texto —frases que el
editor sacó por repetir un beneficio ya dicho— y sólo un tercio, silencio.

**Sobre los tiempos, lo que quedó sin resolver:** con habla continua, Whisper y
Premiere discrepan ~140ms de mediana y **no se pudo determinar cuál es mejor** —
el clip de prueba no tenía silencios reales con los que arbitrar. Donde sí se
pudo medir, atravesando música, Premiere tenía razón y Whisper sin VAD estaba muy
mal; con VAD quedaron a 70ms.

## De los crudos al rough cut — las cinco `herramientas/`

`audio.js` transcribe un clip. Las otras cinco son la cadena que va de una
carpeta de crudos a las secuencias armadas en Premiere. Todas trabajan sobre la
carpeta del proyecto: la toman de `PROYECTO_DIR` o del directorio actual, y
deducen el prefijo del nombre de los propios archivos.

| | qué hace |
|---|---|
| `leer.js` | lista los clips de locución con sus frases, agrupando las tomas repetidas |
| `armar.js` | resuelve los beats a rangos exactos de palabra y escribe `VIDEOS.md` + `VIDEOS.json` |
| `verificar.js` | recorta cada rango y lo vuelve a transcribir — la prueba de afuera |
| `suplentes.js` | busca las otras tomas de cada línea, las que quedaron afuera |
| `construir.js` | arma las secuencias en Premiere, con los suplentes apagados en pistas de arriba |

**La lista de beats NO está en el código.** Es criterio editorial de cada jornada
y vive con el material, en un `beats.js` que exporta una función; hay un ejemplo
en `beats.ejemplo.js`, con contenido inventado. Es la misma regla que el glosario: lo del proyecto va
con el proyecto.

Corridas sobre dos jornadas reales de la misma empresa, con material muy
distinto: 147 clips de gente hablando suelto en su casa, y 142 de una locutora
leyendo guion en un showroom. Cotejadas contra el montaje que el editor había
hecho meses antes, **89% y 94% de acierto en qué clip usar**, y en la segunda,
cuatro de los seis videos idénticos clip por clip.

**Lo que rompió al pasar de una jornada a la otra fueron valores heredados**, no
el método: la carpeta por defecto, el prefijo del nombre, y un filtro que buscaba
`/Entrevistas/` en la ruta. Ninguno falló ruidosamente — dos leyeron lo
equivocado y contestaron con confianza, y el peor informó *"0 suplentes"*, que se
lee como resultado y era una lista vacía. Por eso ahora todo sale del entorno.

### La API de Premiere, medida

Las firmas y los comportamientos medidos de la API —qué hace y qué no hace cada acción del
timeline, el reloj del material, leer un valor animado, los marcadores, el vínculo, las firmas
que no se adivinan— están en [`docs/api.md`](docs/api.md). Este README es el manual: instalar,
qué hace cada herramienta y los flujos de trabajo.

### Imagen y texto dicen cosas distintas

`premiere_analizar` devuelve los cuadros con lo que se dice en cada uno, y el
cruce da más que las dos mitades. Medido con una pieza real: las imágenes
mostraban un taller de arte, el texto era una publicidad de porcelanato, y
alineados se veía que cada plano ilustra un argumento del guion —el primer plano
del piso cae justo cuando se nombra el producto—. Con los cuadros solos la
descripción salía bien del lugar y mal del video.

`createSequenceFromMedia` toma **`(nombre, medio)`**: con un solo argumento
contesta *"Illegal Parameter type"*. Eso ya se había medido en `mirarMedio`, que
probaba las dos formas — pero no informaba cuál andaba, así que el dato se
perdió y hubo que volver a descubrirlo. Ahora las dos usan la misma función.

## Las dos reglas que sostienen el diseño

**1. Verbos chicos sobre cosas que ya existen.** La tentación es exponer un
"ejecutá este JS en el panel" y que Claude improvise. Sería un error: el patrón
dominante de esta API es el **fallo silencioso** —la función devuelve éxito y no
hace nada, o hace otra cosa— así que un verbo genérico produce código plausible
que no pasó, sin que nada avise.

**2. Cada verbo devuelve QUÉ ENCONTRÓ, no si salió bien.** `premiere_keyframe`
contesta "keyframes 0 → 1", no "ok". Esa diferencia es la única prueba de que
pasó algo. Los errores siguen la misma regla: dicen qué había, no qué faltaba —
"el Motion no expuso Scale, tiene: Position, Rotation…" se diagnostica solo.

## Límites reales

- **El panel tiene que estar abierto.** Cerrarlo corta el acceso, a propósito.
  El servidor mira el latido y contesta al instante en vez de colgarse.
- **Claude ve FOTOS, no video.** Con `premiere_vistazo` reconoce de qué es el
  material —escenario, quién aparece, si hay gráficos, dónde cambia el
  contenido— pero un plano fijo y una cámara que volvió al mismo encuadre se ven
  igual, y lo que pasa entre dos muestras no existe. Para cortes con precisión
  está `performSceneEditDetectionOnSelection`, no el muestreo.
- **No escucha nada.** Música, tono y ritmo quedan afuera, y eso incluye juzgar
  si un corte "suena bien".
- **`keyframe`, `motion`, `agregarEfecto` y `transcripcion` usan el clip
  seleccionado**; los verbos destructivos lo exigen por nombre o por pista e índice.
- **El techo es la API de `premierepro`**, no el bridge.

## Estructura

```
server/
  index.js      servidor MCP: registra las herramientas
  bridge.js     el transporte sobre la carpeta, con el latido
plugin/
  manifest.json id PROPIO (com.tunombre.premierebridge) — poné el tuyo
  index.js      poll + despacho + latido
  lib/comandos.js  los verbos: lo único que toca la API
```

El `id` y el `shortname` del manifest identifican al plugin para Premiere:
cambiarlos lo instala como uno nuevo y deja dos conviviendo. Están congelados.

## `herramientas/desde_secuencia.js` — tu timeline reescribe la propuesta

Los tiempos salen de la secuencia y las anotaciones de la propuesta vieja, emparejadas por
nombre más número de aparición. Nunca al revés: si un tiempo discrepa, gana la secuencia,
porque ahí está la edición del usuario.

```
node herramientas/desde_secuencia.js --estado estado_V1.json --propuesta vieja.json \
     --salida nueva.json [--anterior captura_previa.json] [--secciones letra.json]
```

Con `--anterior` el diff es **exacto** (captura contra captura, no falta ningún campo). Contra
la propuesta es aproximado y lo dice: en 59 de 88 planos no había `entrada`, así que un cambio
de in-point no tenía con qué compararse.

Las anotaciones se copian **por exclusión**: todo lo que la herramienta no calcula ella misma.
Antes era una lista blanca de siete nombres de un videoclip, y las propuestas de un corporativo
—que anotan `bloque`, `grupo`, `texto` y `porQue`— habrían salido con los tiempos correctos y
**sin una sola anotación**. `test.js` exige que `desde`, `dura` y `entrada` sigan excluidos: si
uno se colara, los tiempos de la propuesta vieja le ganarían a la secuencia y la herramienta
haría lo contrario de lo que promete.

## `herramientas/exportar_dc.js` — animaciones de Claude Design a ProRes

Claude Design exporta video comprimido. Teniendo el HTML se saca mejor: se barre la animación
cuadro por cuadro y se arma un ProRes, sin compresión intermedia ni grabar pantalla.

```
node herramientas/exportar_dc.js --dir <carpeta del zip> --verificar
node herramientas/exportar_dc.js --dir <carpeta> --html "un estudio Intro.dc.html" \
     --salida intro.mov --props '{"titleLine1":"Video 1","titleLine2":""}'
```

Funciona porque los `.dc.html` traen un contrato de seek —`data-om-seek-to-time-frame` sobre la
raíz con `data-om-exportable-video-with-duration-secs`— y **`--verificar` comprueba que se cumpla**
antes de gastar quince minutos: exige que el render cambie al barrer y que volver al mismo tiempo
dé la misma firma.

**El flujo entero, las cinco trampas y las cinco guardas están en
`herramientas/EXPORTAR_CLAUDE_DESIGN.md`.** La que más importa: los dos peores defectos —el título
ausente y una barra de reproducción horneada— pasaron todos los chequeos numéricos y los encontró
mirar un contact sheet.

Validado el 2026-08-23 con los tres artboards de un estudio: 213, 110 y 1225 cuadros a 1920x1080,
ProRes 4444.

## `herramientas/comparar_corte.js` — qué le cambiaste al armado

Sólo lee y sólo informa. Contesta la pregunta que `desde_secuencia.js` no puede cuando la
propuesta no trae posiciones —las de un corporativo no las traen, los fragmentos se pegaron uno tras
otro— y ahí `dDesde` da cero siempre y **mover queda invisible**.

```
node herramientas/comparar_corte.js --propuesta corte_video3.json --estado clips_V3.json [--json]
```

El arreglo no es reconstruir las posiciones, es no necesitarlas:

```
reordenar   ->  el ORDEN de los nombres
recortar    ->  `dura`, exacta, está en la propuesta
in-point    ->  `entrada`, exacta, está en la propuesta
agregar     ->  lo que el timeline tiene y la propuesta no
borrar      ->  al revés
huecos      ->  NO los mira: eso es `revisar`, y es estado, no diff
```

**El emparejamiento va por IN-POINT, no por número de aparición**, y eso salió de una prueba
que falló. Emparejar por aparición es circular —el número depende del orden y el orden es lo
que se quiere medir—: en un corte donde un mismo medio se usa cinco veces, mover UN clip
renumeró todas sus apariciones y la herramienta informó **5 recortes donde había 1**, 5 cambios
de in-point donde había 1, y un clip movido "del 6º al 6º". El in-point es identidad: dice qué
pedazo del material se usa y no cambia al reordenar. Adentro de cada nombre las instancias se
emparejan por costo mínimo `|dEntrada| * 3 + |dDura|`.

Los movidos salen de la **subsecuencia creciente más larga**, no de comparar índices: mover un
clip del final al principio corre a todos los demás, y comparando índices eso informa "se
movieron 23 de 23", que es cierto y no sirve.

Y el aviso de emparejamiento dudoso salta **sólo cuando hay más de una instancia de qué
elegir**. La primera versión avisaba siempre que el costo fuera alto, y marcó como dudosos los
dos únicos clips editados de la prueba, que eran nombres únicos y por lo tanto pares forzados:
un aviso que salta en cada edición normal es ruido, y el ruido entrena a ignorarlo.

Probado en las dos direcciones: contra un timeline con **cinco ediciones puestas a propósito**
—un borrado, un agregado, una movida, un recorte de 1,40s y un in-point corrido 2,60s— encuentra
las cinco y nada más; y contra los tres cortes sin editar (26, 28 y 23 clips) informa "sin
cambios".

## `herramientas/revisar_medios.js` — qué defectos trae el material antes de armar

`revisar` mira la secuencia ya armada. Esto mira el material **antes**, que es donde estos
defectos son baratos: con 88 planos colocados, arreglarlos es tocar 88 clips.

Sólo lee, y **no usa el bridge**: es ffprobe puro, así que corre sin Premiere abierto y sin
riesgo de ninguno de los cinco modos de crash. `test.js` exige que siga así.

```
node herramientas/revisar_medios.js <carpeta ...> [--fps 25] [--deriva] [--json salida.json]
```

Los cuatro chequeos salieron de medir los dos proyectos reales, no de imaginar defectos:

```
                          un videoclip (140)   un corporativo (122)
flag de rotación                   5              12
r_frame_rate no creíble            0              13
VFR                                0              35
resoluciones distintas             1              13
```

- **El flag de rotación.** Premiere lo obedece igual que ffmpeg y el clip entra acostado. La
  firma es que el contenido ocupa **56% del ancho** (2160/3840); la herramienta la calcula y
  además imprime el `fijar` que lo arregla. En un videoclip esto se descubrió mirando el export, con el
  corte entero ya hecho.
- **`r_frame_rate` no creíble.** Trece archivos de un corporativo declaran **90000** o 120 fps donde hay
  25 o 30. Es el número que se lee primero, y una cuenta hecha con él en vez del promedio da
  hasta **91 segundos** de error.
- **VFR — medido, y NO es un defecto.** La sospecha era que un conform de cadencia fija corriera
  los in-points hasta 3,12s. Se midió: **Premiere respeta los PTS** (cuadro de Premiere contra el
  de ffmpeg, RMSE 13,95 contra 29,69, y confirmado mirando), así que un in-point calculado con
  ffmpeg cae bien. Se informa sin alarma. Con `--deriva` se ve cuánto se correría una herramienta
  que cuente CUADROS en vez de leer tiempos — hasta 6,20s. El detalle en `herramientas/VISION.md`.
- **Resoluciones mezcladas.** Dos planos pegados con esa diferencia se ven distintos aunque el
  encuadre coincida, y rompe el `--familia` de `foco.py`.

El fps distinto al de la secuencia se informa **aparte y sin alarma**: 121 de los 140 medios de
un videoclip no van a 25fps y el proyecto está bien. Una salida que grita sobre 121 archivos sanos enseña
a ignorarla.

## `herramientas/plancha_corte.js` — mirar el export entero de una

Un cuadro por plano, en plancha de contacto, etiquetado con el corte: número, nombre, minuto,
duración y de qué clase es el plano. Sólo lee, no usa el bridge.

```
node herramientas/plancha_corte.js --video <export.mp4> --corte <corte.json> [--por 12]
```

Existe porque **mirar es lo que encuentra lo que las guardas numéricas no**, y en este repo eso
está pagado dos veces: el flag de rotación de un videoclip apareció mirando el archivo exportado, y los
dos peores defectos de `exportar_dc.js` —cero texto y una barra de reproducción horneada— los
encontró una plancha después de que cinco chequeos numéricos dieran verde.

Lo que cambió es el **costo** de mirar. `premiere_frame` da un cuadro por llamada: 88 planos son
88 viajes al bridge. El export es un archivo suelto y muestrearlo es gratis. De ahí la regla:
**verificar el EXPORT, no el timeline** — y encima el export es lo que ve el cliente.

Tres decisiones que no son obvias:

- **Se muestrea el MEDIO del plano, no el corte.** Un cuadro en el punto de corte es ambiguo
  —puede ser el último del plano que termina o el primero del que empieza— y con eso la plancha no
  sirve para decir "el plano 34 salió acostado".
- **NO usa `-noautorotate`, al revés que las planchas de material.** Ahí se lee cámara con el flag
  mal puesto y hay que ignorarlo; acá se lee el resultado entregado y hay que hacer lo mismo que
  un reproductor. Ponerlo escondería justo el defecto que se vino a buscar. `test.js` sostiene las
  dos direcciones, y al escribir esa guarda apareció que **`broll.js` venía extrayendo sin la
  opción** mientras el resto la tenía.
- **Aborta si el corte no es de esa versión del export.** Si no, los tiempos caen en otros planos
  y la plancha sale plausible y equivocada. Se compara la duración contra el final del último
  plano; con `--tolerancia` se admite un export con placas de inicio o cola.

Probado sobre el ROUGH CUT 5 de un videoclip: 88 planos en 8 hojas, y confirmó mirando que los dos clips
con flag de rotación (`FX3_3555` y `FX3_3560`) salieron derechos en el archivo entregado.

## `herramientas/cotejar_export.js` — ¿el export muestra lo que el corte pide?

La verificación de la punta de la cadena, y desde **afuera** de Premiere: compara el archivo
entregado contra el material en disco.

```
node herramientas/cotejar_export.js --video <export.mp4> --corte <corte.json> \
  [--material <carpeta>] [--limite 20] [--todos]
```

En un corte de 88 planos armado por script, un `entrada` equivocado es **invisible**: el plano mide
lo que tiene que medir, se ve bien, y muestra otro momento del mismo material. Ni `revisar` ni la
plancha lo ven — la plancha sólo si conocés el material de memoria.

**Se juzga por RANGO, no por umbral**, y eso salió de medir. El cuadro del export se compara contra
el material en el instante pedido y contra señuelos —otros instantes del mismo medio—, y el pedido
tiene que dar el mínimo:

```
par correcto            0,76 a 10,33
señuelo, mismo medio   13,13 a 21,05
señuelo, otro medio    26,11 a 30,41
```

Los rangos no se solapan, pero el valor absoluto del par correcto **varía 13 veces** entre planos:
0,76 en un plano de percusión y 10,33 en un cantante con Lumetri. Un umbral global calibrado con el
primero rechazaría al segundo. El rango acertó 6 de 6, con el correcto siempre en menos de la mitad
del señuelo. Y el ~10 de base no es un in-point malo: es la corrección de color del export — lo
demostró el señuelo, que es el control sin el cual un 10 no se puede interpretar.

**Lo que NO puede hacer, y también está medido: verificar al cuadro.**

```
par correcto   0,76   6,62   9,91  10,33  10,23   9,86
+1 cuadro      3,68   8,32  10,06  11,51  10,25   9,83
```

En cuatro de seis no separa, y en uno el desfasado da menos. No es un defecto del metro: un cantante
quieto frente a un micrófono es casi el mismo cuadro 40 ms después. Así que el veredicto dice **"el
pedazo correcto"** y no "verificado" — prometer lo segundo dejaría creer que la sincro está
chequeada, y para eso está `sincro.py` sobre el audio.

La distancia de los señuelos también se midió en vez de elegirla: empezaron a ±15s y así **un tercio
de los planos quedaba sin cotejar** porque el material es más corto. El pedido gana desde **+0,5s**
(5 de 5), así que se usan ±3s como los más cercanos, donde el peor margen es x1,25.

---

## Licencia

MIT — ver [`LICENSE`](LICENSE). Usalo como quieras, incluso en algo comercial; lo
unico que pide es que mantengas el aviso de copyright.
