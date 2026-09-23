#!/usr/bin/env python3
"""Lo que comparten `camara.py`, `foco_tramo.py`, `foco_de_cerca.py` y `tira_clip.py`.

No es una herramienta: es la geometria del clip y la decision de la ROTACION, en UN lugar.
Esta en un modulo aparte por una razon que ya se pago en este repo: dos caminos para la misma
pregunta se separan siempre. Si cada herramienta decidiera la rotacion a su manera, la hoja que
se mira podria mostrar el cuadro rotado distinto del que se midio.

## La rotacion NO tiene default, y es a proposito

El flag de rotacion de la metadata a veces esta BIEN y a veces esta MAL, y no se puede deducir
del archivo:

    un videoclip y un institucional (FX3)   material HORIZONTAL con rotation=-90 o 90   ->  el flag MIENTE
    el evento (2026-09-22)  3840x2160 guardado con rotation=±90, el
                           contenido es VERTICAL de verdad             ->  el flag esta BIEN

`grilla_angulos.js` y `familias.py` lo IGNORAN por default, porque se escribieron sobre un videoclip.
Con ese default, estas herramientas habrian medido todo el evento acostado: el cuadro de medida
de 270 de ancho corresponde al lado LARGO y la conversion a px de secuencia sale 1,78 veces
corrida, sin ningun error.

Asi que si algun clip trae flag y no se dijo que hacer, se REBOTA antes de medir nada, con la
lista de los clips. Se decide mirando un cuadro (`tira_clip.py` con las dos opciones), no
leyendo el flag. Si ningun clip trae flag no hay nada que decidir y no se pide nada: rechazar
uso correcto es el peor modo de fallo de una guarda.

Un clip de una lista JSON puede traer su propia `"rotacion"`, para material mezclado.

`-noautorotate` va ANTES de `-i`: es opcion de demuxer, y puesta despues no hace nada y no avisa.
"""
import json, os, subprocess, sys
from fractions import Fraction

VIDEO = (".mp4", ".mov", ".mxf", ".m4v", ".avi", ".mts")
ROTACIONES = ("respetar", "ignorar")


def ficha(ruta):
    """Geometria del clip TAL COMO SE VA A VER con cada opcion de rotacion.

    Devuelve el ancho y alto GUARDADOS, el flag, los fps promedio como fraccion exacta y la
    duracion. Los fps van como `Fraction` porque 59,94 es 60000/1001 y redondearlo a 59.94
    cambia que cuadros elige el filtro `fps` despues.
    """
    p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,avg_frame_rate,r_frame_rate:stream_side_data=rotation"
                        ":format=duration", "-of", "json", ruta], capture_output=True, text=True)
    if p.returncode != 0:
        err = p.stderr.strip().splitlines()
        raise RuntimeError(f"ffprobe no pudo leer {ruta}: {err[-1][-200:] if err else 'sin detalle'}")
    j = json.loads(p.stdout)
    if not j.get("streams"):
        raise RuntimeError(f"{ruta} no tiene pista de video")
    s = j["streams"][0]
    rot = 0
    for sd in s.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(round(float(sd["rotation"])))
    fps = Fraction(s.get("avg_frame_rate") or "0/1")
    if fps <= 0:
        fps = Fraction(s.get("r_frame_rate") or "0/1")
    dur = float(j.get("format", {}).get("duration") or 0)
    return {"ruta": ruta, "ancho": int(s["width"]), "alto": int(s["height"]), "rot": rot,
            "fps": fps, "dura": dur}


def fichas_de(items):
    """La ficha de cada clip, o REBOTA nombrando TODOS los que ffprobe no puede leer, antes de medir
    nada: un traceback en el primero no dice si hay otros."""
    fichas, malas = {}, []
    for x in items:
        if x["ruta"] not in fichas:
            try:
                fichas[x["ruta"]] = ficha(x["ruta"])
            except RuntimeError as e:
                malas.append(f"{os.path.basename(x['ruta'])}: {str(e).split(': ')[-1][:140]}")
    if malas:
        raise SystemExit(f"{len(malas)} clip(s) que ffprobe no puede leer, y NO se midio nada:\n  "
                         + "\n  ".join(malas[:10]) + ("\n  ..." if len(malas) > 10 else ""))
    return fichas


def vista(f, rotacion):
    """(ancho, alto) del cuadro que entrega ffmpeg con esa opcion. Con `respetar` y un flag de
    ±90, ffmpeg transpone antes de cualquier filtro, asi que ancho y alto se intercambian."""
    if rotacion == "respetar" and abs(f["rot"]) % 180 == 90:
        return f["alto"], f["ancho"]
    return f["ancho"], f["alto"]


def alto_par(ancho, f, rotacion):
    """El alto que corresponde a `ancho`, par. Se PIDE explicito en el `scale` en vez de dejar
    `-2`: si la cuenta de aca y la de ffmpeg difirieran en un pixel, el buffer se leeria con
    las filas corridas y un clip quieto mediria un paneo (paso en `nitidez.py`: 272 px)."""
    w, h = vista(f, rotacion)
    return max(2, int(round(ancho * h / w / 2)) * 2)


def entrada_ffmpeg(ruta, rotacion, desde=None):
    """Los argumentos de ENTRADA de ffmpeg, con la rotacion donde tiene efecto."""
    a = []
    if rotacion == "ignorar":
        a.append("-noautorotate")
    if desde is not None:
        # `-ss 0.000` va igual si se pidio un tramo desde el arranque: es lo que hacia el original,
        # y sin el, el primer cuadro que elige el filtro `fps` puede no ser el mismo
        a += ["-ss", f"{desde:.3f}"]
    return a + ["-i", ruta]


def fps_de_medida(fps_fuente, tope=30):
    """Cada K cuadros de fuente, con K el menor entero que deja la cadencia en `tope` o menos.

    59,94 -> 29,97 (cada 2) · 50 -> 25 · 25 -> 25 · 29,97 -> 29,97 · 119,88 -> 29,97 (cada 4).
    Es un SUBMUESTREO PAREJO: el filtro `fps` con una cadencia que no divide a la de la fuente
    elige cuadros desparejos —medido: `fps=25` sobre 59,94 salta de a 2 y de a 3 cuadros, 30 y
    19 veces en 2 segundos—, y eso en `camara.py` fabricaba tiron sobre paneos parejos.
    """
    fps_fuente = Fraction(fps_fuente)
    k = 1
    while fps_fuente / k > tope:
        k += 1
    return fps_fuente / k


def _clips_de_carpeta(d):
    out = []
    for raiz, dirs, archivos in os.walk(d):
        dirs[:] = sorted(x for x in dirs if not x.startswith("."))
        for a in sorted(archivos):
            if not a.startswith(".") and a.lower().endswith(VIDEO):
                out.append(os.path.join(raiz, a))
    return out


def resolver(entradas, base=None):
    """Lo que se pasa por linea de comando -> lista de dicts con `ruta` (absoluta) y el resto de
    los campos que traiga cada item.

    Cada entrada puede ser un clip, una carpeta (se recorre entera) o una lista JSON. En la
    lista, cada item es una ruta, o un objeto con `ruta`, o un objeto con `clip` y opcionalmente
    `carpeta` —o `camara`, como la escribe el armado del evento— que se resuelven contra
    `--base`. No se busca un clip por nombre en el disco: con dos camaras, dos carpetas pueden
    tener archivos homonimos, y un nombre deducido es una hipotesis.
    """
    items, faltan = [], []
    for e in entradas:
        if os.path.isdir(e):
            items += [{"ruta": os.path.abspath(r)} for r in _clips_de_carpeta(e)]
        elif e.lower().endswith(".json"):
            datos = json.load(open(e))
            if isinstance(datos, dict):
                raise SystemExit(f"{e}: se esperaba una LISTA de clips o tramos, y es un objeto "
                                 f"con claves {list(datos)[:5]}. Aplanala primero.")
            for x in datos:
                if isinstance(x, str):
                    x = {"ruta": x}
                x = dict(x)
                if not x.get("ruta"):
                    if not x.get("clip"):
                        raise SystemExit(f"{e}: un item no trae ni `ruta` ni `clip`: {x}")
                    carpeta = x.get("carpeta") or x.get("camara") or ""
                    if not base and not os.path.isabs(os.path.join(carpeta, x["clip"])):
                        raise SystemExit(f"{e}: `{x['clip']}` es relativo y no se paso --base")
                    x["ruta"] = os.path.join(base or "", carpeta, x["clip"])
                x["ruta"] = os.path.abspath(x["ruta"])
                items.append(x)
        else:
            items.append({"ruta": os.path.abspath(e)})
    for x in items:
        x.setdefault("clip", os.path.basename(x["ruta"]))
        if not os.path.exists(x["ruta"]):
            faltan.append(x["ruta"])
    if faltan:
        raise SystemExit(f"{len(faltan)} clip(s) NO ESTAN en disco, no se midio nada:\n  "
                         + "\n  ".join(faltan[:10]) + ("\n  ..." if len(faltan) > 10 else ""))
    return items


def decidir_rotacion(items, fichas, opcion):
    """Le pone a cada item su `rotacion`, o REBOTA si hay un flag y nadie decidio.

    Devuelve los items con `rotacion` puesta. Sin flag da igual la opcion y se usa `respetar`,
    que ahi es lo mismo que ignorar.
    """
    ambiguos = []
    for x in items:
        f = fichas[x["ruta"]]
        r = x.get("rotacion") or opcion
        if r is not None and r not in ROTACIONES:
            raise SystemExit(f"rotacion `{r}` no existe: es {' o '.join(ROTACIONES)}")
        if f["rot"] == 0:
            x["rotacion"] = r or "respetar"
        elif r is None:
            ambiguos.append(f)
        else:
            x["rotacion"] = r
    if ambiguos:
        lista = "\n  ".join(f"{os.path.basename(f['ruta'])}  guardado {f['ancho']}x{f['alto']}, "
                            f"flag {f['rot']}" for f in ambiguos[:12])
        mas = f"\n  ... y {len(ambiguos) - 12} mas" if len(ambiguos) > 12 else ""
        sys.exit(
            f"ROTACION SIN DECIDIR en {len(ambiguos)} clip(s), y NO se midio nada:\n  {lista}{mas}\n\n"
            "El flag no se puede creer ni descartar a ciegas: en un videoclip y un institucional estaba MAL (material\n"
            "horizontal marcado ±90) y en el evento estaba BIEN (vertical de verdad). Mira un cuadro\n"
            "con `tira_clip.py --rotacion respetar` y con `--rotacion ignorar`, y pasa la que se vea\n"
            "derecha. Si el material esta mezclado, cada item de la lista JSON acepta su \"rotacion\".")
    return items
