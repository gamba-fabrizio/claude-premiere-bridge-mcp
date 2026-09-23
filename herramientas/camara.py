#!/usr/bin/env python3
"""Movimiento de la CAMARA, no del cuadro: el TIRON, con puntos seguidos y RANSAC.

    python3 camara.py medir <clip|carpeta|lista.json>... [--salida camara.json] [--base DIR]
                            [--rotacion respetar|ignorar] [--ancho-secuencia 1080] [--hilos 3]
    python3 camara.py buscar --datos camara.json --largo 3 [clip ...] [--borde 0.5] [--cuantos 3]
    python3 camara.py control

Corre con el python3 del sistema (numpy 2 + OpenCV). Salio del armado de b-roll de un evento corporativo
(2026-09-22); el uso real esta en la PROPUESTA.md de ese armado y lo medido, en `VISION.md`.

## Por que hizo falta

`movimiento.js` —la receta de `MOVIMIENTO_ROTO.md`— mide la DIFERENCIA ENTRE CUADROS, y su falla
documentada nº1 es que no distingue la camara del sujeto. En un institucional la base de camara en mano
quieta daba 0,45-0,63; en el evento, con gente caminando por todo el cuadro, da de 0,74
a 12,25 (mediana 3,31, 54 clips), asi que el umbral 0,45 no se transfiere y casi todo salia "a
mirar". El remedio es el que ese archivo ya nombraba: estimar el movimiento dominante del FONDO
rechazando lo que se mueve distinto.

## Como mide

- gris a 270 px de ancho (con el material del evento, un pixel aca son 4 del 1080 de la secuencia)
- puntos de esquina (`goodFeaturesToTrack`) seguidos con Lucas-Kanade al cuadro siguiente
- semejanza con RANSAC (`estimateAffinePartial2D`): la gente que camina queda afuera como
  outlier. `inl` es la fraccion de puntos que respeta el movimiento de camara; **con `inl` por
  debajo de 0,5 la estimacion no vale** y ese tramo se mira.
- TIRON[k] = |v[k] - media(v en ±4 pasos)|, en px de la SECUENCIA, con pasos de 1/25 s: cuanto
  se aparta el movimiento de un paso del movimiento suave que lo rodea. Es el "rapido y brusco"
  que molesta; un paneo parejo da tiron bajo aunque se mueva mucho. `vel` es el movimiento suave,
  en px de secuencia por segundo.

La unidad supone que el clip LLENA el ancho de la secuencia (`--ancho-secuencia`, 1080 por
default). Si va recortado o achicado, el numero no es el que se ve.

Calibracion hecha mirando, en el evento: menos de 4 px no se nota, de 4 a 8 es leve, mas de 8 se
ve. **Nunca se probo a ciegas contra el juicio del editor.** Y ojo: se hizo con la version
original, la del artefacto de abajo, asi que los numeros de esta version no se le pueden aplicar
sin volver a mirar.

## La correccion: el muestreo PAREJO, medido al portarla

El original pedia `fps=25` a ffmpeg. Sobre material de 59,94 eso NO toma un cuadro cada 40 ms:
toma cuadros de fuente separados de a 2 y de a 3 —medido pintando el numero de cuadro en un video
de prueba: 30 saltos de 2 y 19 de 3 en dos segundos—, o sea pasos de 33 y de 50 ms. Un paneo
parejo recorre en cada paso una distancia distinta, y eso el tiron lo lee como tirones.

Control: paneos SIN NINGUN golpe, hechos desplazando sub-pixel un cuadro real del evento, y
golpes de 8 px puestos a proposito encima de un paneo de 300 px/s:

                                      fps=25 (original)    esta version
    paneo 100 px/s, fuente 59,94      max 1,38             max 0,25
    paneo 300 px/s, fuente 59,94      max 3,87             max 0,33
    paneo 600 px/s, fuente 59,94      max 7,76  "leve"     max 0,43
    paneo 300 px/s, fuente 29,97      max 9,06  "se ve"    max 0,27
    paneo 300 px/s, fuente 50         max 0,38             max 0,31   (50/25 es entero: no hay artefacto)
    zoom parejo 5%/s                  max 0,77             max 0,07
    GOLPE de 8 px, en un paso de 3    max 10,46            max 7,04   (lo teorico es 8·8/9 = 7,1)
    el mismo GOLPE, en un paso de 2   max 4,98             max 7,21

Son dos defectos en uno. Un paneo parejo lee tiron en proporcion a su velocidad (~1,2% de los
px/s sobre 59,94; sobre 29,97, lo normal en un telefono, 9 px sin un solo golpe). Y un golpe
REAL lee la mitad o una vez y media segun caiga en un paso de 2 o de 3 cuadros de fuente.

Esta version mide CADA PAR de cuadros de fuente, integra la posicion con el tiempo REAL de cada
cuadro (sale de `showinfo`, asi que un VFR tambien anda) y toma una ventana de 40 ms que arranca
en CADA cuadro: el paso nominal de la calibracion, sin elegir cuadros. De cada paso de la grilla
queda la peor de sus ventanas, asi que un golpe entra entero en alguna caiga donde caiga.
`camara.py control` corre esta bateria sobre un video sintetico, y `test.js` lo exige.

Sobre los 64 tramos elegidos en el evento la mediana del pico baja de 2,19 a 1,67, y los once que
la propuesta dejo como "movimiento leve, 4 a 7 px" dan entre 1,37 y 3,64: el leve era mayormente
el artefacto. Los que siguen en 4-8 son lentos (30 y 98 px/s) y casi no se mueven, que es lo que
tiene que pasar si el artefacto escala con la velocidad.

## Lo que NO hace

- **No garantiza haber medido la camara con `inl` por arriba de 0,5.** Si el sujeto que se mueve
  ocupa el cuadro y el fondo no tiene textura, el consenso de RANSAC salta entre los dos. En
  A001C114 (el conector entrando al auto, sobre chapa lisa) el cuadro entero daba tiron de 12 a
  46 con `inl` 0,57-0,73; con los puntos solo en la tapa, la camara hacia un paneo que frena
  parejo, y el tramo daba 4,46 con `inl` 0,93. Para eso cada item de la lista acepta
  `"region": [x0, y0, x1, y1]` en fracciones del cuadro, y los puntos se buscan solo ahi.
- No dice si un plano se puede usar. Es una lista de donde mirar, y el veredicto es mirando.
- No sabe del foco. Eso es `foco_tramo.py`.
- La traslacion se toma del origen de la semejanza, como en el original: un zoom o un giro se
  leen tambien como algo de `vel`. En el control, un zoom parejo da tiron 0,07.

## buscar

Los mejores tramos de L segundos de cada clip: hasta `--cuantos` que no se pisen, ordenados por
el tiron MAXIMO adentro, evitando `--borde` segundos al principio y al final. Una ventana donde
algun paso tiene `inl` < 0,5 NO compite: su tiron no vale, y recomendarla como la mejor seria
creerle a una estimacion que se sabe mala. Si no queda ninguna valida, se dice.
"""
import argparse, json, os, re, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import video_comun as vc

W = 270                 # ancho de medida: el de la calibracion
PASO = 1 / 25           # el paso nominal de la calibracion, en segundos
SUAVE = 4               # ±4 pasos para el movimiento suave
INL_MIN = 0.5           # por debajo, la estimacion de ese paso no vale
# Si cambia cualquiera de los de arriba, cambia METODO: un camara.json medido con otro metodo
# no se reusa, se vuelve a medir. Las entradas del original del evento no traen METODO.
METODO = "trayectoria 1/25s · 270px · RANSAC semejanza · v1"


def par(a, b, mascara=None):
    """Traslacion de camara entre dos cuadros, y la fraccion de puntos que la respetan."""
    p0 = cv2.goodFeaturesToTrack(a, 300, 0.01, 7, mask=mascara)
    if p0 is None or len(p0) < 12:
        return np.nan, np.nan, 0.0
    p1, st, _ = cv2.calcOpticalFlowPyrLK(a, b, p0, None, winSize=(21, 21), maxLevel=3)
    ok = st.reshape(-1) == 1
    if ok.sum() < 12:
        return np.nan, np.nan, 0.0
    M, mask = cv2.estimateAffinePartial2D(p0[ok], p1[ok], method=cv2.RANSAC, ransacReprojThreshold=1.5)
    if M is None:
        return np.nan, np.nan, 0.0
    return float(M[0, 2]), float(M[1, 2]), float(mask.sum()) / len(p0)


def _rellenar(v):
    # un par sin textura no se inventa: se interpola del vecino y queda marcado con inl 0
    for j in range(v.shape[1]):
        s = v[:, j]; m = np.isnan(s)
        if m.all():
            s[:] = 0
        elif m.any():
            s[m] = np.interp(np.flatnonzero(m), np.flatnonzero(~m), s[~m])
    return v


def mascara_de(region, H):
    """`"region": [x0, y0, x1, y1]` en fracciones del cuadro: los puntos se buscan SOLO ahi.

    Para cuando el sujeto que se mueve ocupa el cuadro y el fondo no tiene textura: en A001C114
    (el conector entrando al auto, sobre una chapa lisa) el cuadro entero daba tiron de 12 a 46
    con `inl` 0,57-0,73 —el consenso de RANSAC saltaba entre la camara y el conector— y con los
    puntos solo en la tapa, `[0, 0, 0.3, 1]`, un paneo que frena parejo: el tramo, 4,46 e `inl` 0,93.
    """
    if not region:
        return None
    x0, y0, x1, y1 = (float(v) for v in region)
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise RuntimeError(f"region {region}: van fracciones del cuadro, [x0, y0, x1, y1] con x0<x1 y y0<y1")
    m = np.zeros((H, W), np.uint8)
    m[int(y0 * H):int(np.ceil(y1 * H)), int(x0 * W):int(np.ceil(x1 * W))] = 255
    return m


def medir(x, f, ancho_sec):
    rot = x["rotacion"]
    H = vc.alto_par(W, f, rot)
    tam = W * H
    mascara = mascara_de(x.get("region"), H)
    cmd = (["ffmpeg", "-hide_banner", "-nostats", "-v", "info"] + vc.entrada_ffmpeg(x["ruta"], rot)
           # `-fps_mode passthrough`: sin eso, ffmpeg repite o tira cuadros para sacar cadencia
           # constante, y con un VFR los cuadros ya no alinean con los tiempos de `showinfo`.
           + ["-an", "-sn", "-dn", "-vf", f"scale={W}:{H},format=gray,showinfo",
              "-fps_mode", "passthrough", "-f", "rawvideo", "-"])
    d, n, prev = [], 0, None
    with tempfile.TemporaryFile() as err:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err)
        while True:
            b = p.stdout.read(tam)
            if len(b) < tam:
                sobra = len(b)
                break
            cuadro = np.frombuffer(b, np.uint8).reshape(H, W)
            if prev is not None:
                d.append(par(prev, cuadro, mascara))
            prev, n = cuadro, n + 1
        p.wait()
        err.seek(0)
        log = err.read().decode("utf8", "replace")
    if p.returncode != 0:
        raise RuntimeError("ffmpeg fallo: " + log.strip().splitlines()[-1][:200] if log.strip() else "ffmpeg fallo")
    if sobra:
        raise RuntimeError(f"sobraron {sobra} bytes: el cuadro no mide {W}x{H}, la geometria esta mal")
    pts = [float(m.group(1)) for m in (re.search(r"\bn:\s*\d+.*?pts_time:(\S+)", l)
           for l in log.splitlines() if "Parsed_showinfo" in l) if m]
    if len(pts) != n:
        raise RuntimeError(f"{n} cuadros y {len(pts)} tiempos: no alinean, no se mide a ciegas")
    if n < 3:
        raise RuntimeError(f"solo {n} cuadros")
    ts = np.array(pts) - pts[0]
    if not np.all(np.diff(ts) > 0):
        raise RuntimeError("los tiempos de los cuadros no crecen: no se puede integrar la trayectoria")

    dd = _rellenar(np.array([q[:2] for q in d], float))
    inl_f = np.array([q[2] for q in d])
    # La posicion en cada cuadro de fuente, con su tiempo REAL.
    P = np.vstack([[0.0, 0.0], np.cumsum(dd, axis=0)])
    # Un desplazamiento de 40 ms que ARRANCA EN CADA cuadro de fuente, no en una grilla fija. Con
    # la grilla fija, un golpe que cae entre dos cuadros de fuente justo sobre un borde se reparte
    # entre dos pasos y se lee a la mitad: el control lo agarro, 4,48 donde van 7,1. Con una
    # ventana por cuadro, el golpe entra entero en alguna, caiga donde caiga.
    t0 = ts[ts <= ts[-1] - PASO + 1e-9]
    if len(t0) < 3 or t0[-1] < (2 * SUAVE + 2) * PASO:
        raise RuntimeError(f"dura {ts[-1]:.2f}s: muy corto para el suavizado de ±{SUAVE} pasos")
    P0 = P[:len(t0)]
    v = np.stack([np.interp(t0 + PASO, ts, P[:, j]) - P0[:, j] for j in range(2)], axis=1) * (ancho_sec / W)
    # el movimiento suave: la media de las ventanas que arrancan a ±SUAVE pasos
    c = np.vstack([[0.0, 0.0], np.cumsum(v, axis=0)])
    lo = np.searchsorted(t0, t0 - SUAVE * PASO - 1e-9, side="left")
    hi = np.searchsorted(t0, t0 + SUAVE * PASO + 1e-9, side="right")
    suave = (c[hi] - c[lo]) / (hi - lo)[:, None]
    tir_f = np.hypot(*(v - suave).T)
    vel_f = np.hypot(*suave.T) / PASO
    # A la grilla de 40 ms, que es la unidad de `buscar`: de cada paso, la PEOR de sus ventanas.
    # Cada ventana se anota en el paso que contiene al cuadro SIGUIENTE a su arranque (menos un
    # pelo). Asi el paso k tiene exactamente la ventana del primer cuadro que se VE de un tramo que
    # arranca en k —en 59,94 ese cuadro cae antes del tiempo del in-point— y ninguna anterior. La
    # primera version anotaba por el arranque y `buscar` sumaba el paso previo para no perderse ese
    # cuadro: con eso entraban saltos de hasta 40 ms ANTES del corte, y A001C128 daba 5,43 por un
    # salto que no estaba en el tramo (adentro, 3,28).
    kf = np.floor((ts[1:len(t0) + 1] - 1e-6) / PASO).astype(int)
    npasos = int(kf.max()) + 1
    tiron = np.full(npasos, np.nan); np.fmax.at(tiron, kf, tir_f)
    cuenta = np.bincount(kf, minlength=npasos)
    vel = np.where(cuenta > 0, np.bincount(kf, vel_f, npasos) / np.maximum(cuenta, 1), np.nan)
    # el inl de una ventana es el PEOR de los pares de fuente que cubre; el de un paso, el peor
    # de sus ventanas
    fin = np.searchsorted(ts, t0 + PASO - 1e-9, side="left")
    inl_v = np.array([inl_f[i:max(f, i + 1)].min() for i, f in enumerate(fin)])
    inl = np.full(npasos, np.nan); np.fmin.at(inl, kf, inl_v)
    # un paso sin ningun cuadro (fuente de menos de 25 fps) toma los vecinos
    for s in (tiron, vel, inl):
        m = np.isnan(s)
        if m.any():
            s[m] = np.interp(np.flatnonzero(m), np.flatnonzero(~m), s[~m])
    k = int(np.argmax(tiron))
    return {
        **{c: val for c, val in x.items() if c not in ("tiron", "vel", "inl", "error")},
        "metodo": METODO, "paso": PASO, "anchoSecuencia": ancho_sec,
        "rotFlag": f["rot"], "fpsFuente": str(f["fps"]), "cuadrosFuente": n,
        "duraMedida": round(float(ts[-1]), 3),
        "resumen": {"mediana": round(float(np.median(tiron)), 2),
                    "p95": round(float(np.percentile(tiron, 95)), 2),
                    "max": round(float(tiron[k]), 2), "maxEn": round(k * PASO, 2),
                    "inlMediana": round(float(np.median(inl)), 2),
                    "pasosInlBajo": int((inl < INL_MIN).sum())},
        "tiron": np.round(tiron, 2).tolist(), "vel": np.round(vel, 1).tolist(),
        "inl": np.round(inl, 2).tolist(),
    }


def linea(r):
    s = r["resumen"]
    bajo = f"  · {s['pasosInlBajo']} pasos con inl<{INL_MIN}: ahi NO VALE" if s["pasosInlBajo"] else ""
    return (f"{r['clip'][:24]:24s} {r['duraMedida']:6.1f}s  tiron mediana {s['mediana']:5.2f}  "
            f"p95 {s['p95']:5.2f}  max {s['max']:6.2f} @{s['maxEn']:6.2f}s  inl {s['inlMediana']:.2f}{bajo}")


def cmd_medir(a):
    items = vc.resolver(a.entradas, a.base)
    fichas = vc.fichas_de(items)
    items = vc.decidir_rotacion(items, fichas, a.rotacion)
    # `<lista>.camara.json` y no `camara.json`: ese es el nombre que escribia el original, y un
    # default que cae sobre el archivo de un proyecto lo pisa. Y por las dudas, abajo se rebota
    # cualquier salida que ya tenga mediciones de OTRO metodo.
    jsons = [e for e in a.entradas if e.lower().endswith(".json")]
    sal = a.salida or (os.path.splitext(os.path.abspath(jsons[0]))[0] + ".camara.json" if jsons
                       else os.path.join(os.getcwd(), "camara.json"))
    previos = {}
    if os.path.exists(sal):
        viejo = json.load(open(sal))
        ajenos = [r for r in viejo if not isinstance(r, dict) or r.get("metodo") != METODO]
        if ajenos:
            sys.exit(f"{sal} ya tiene {len(ajenos)} medicion(es) de OTRO metodo "
                     f"({(ajenos[0].get('metodo') if isinstance(ajenos[0], dict) else None) or 'el original, fps=25'}). "
                     "No se pisa un registro que no es de esta version: pasa otra --salida.")
        previos = {r["ruta"]: r for r in viejo if r.get("ruta")}
    def vale(r, x):
        return (r and "error" not in r and r.get("rotacion") == x["rotacion"]
                and r.get("anchoSecuencia") == a.ancho_secuencia and r.get("region") == x.get("region"))
    hechos = {x["ruta"]: previos[x["ruta"]] for x in items if vale(previos.get(x["ruta"]), x)}
    faltan = [x for x in items if x["ruta"] not in hechos]
    viejos = sum(1 for x in items if x["ruta"] in previos and x["ruta"] not in hechos)
    print(f"{len(items)} clip(s): {len(hechos)} ya medidos, {len(faltan)} a medir"
          + (f" ({viejos} estaban medidos con otra rotacion o ancho: se rehacen)" if viejos else "")
          + f"\nsalida: {sal}\n", flush=True)
    def guardar():
        otros = [r for ru, r in previos.items() if ru not in hechos and ru not in {x["ruta"] for x in items}]
        json.dump(otros + [hechos[x["ruta"]] for x in items if x["ruta"] in hechos], open(sal, "w"))
    errores = 0
    with ThreadPoolExecutor(a.hilos) as ex:
        fut = {ex.submit(medir, x, fichas[x["ruta"]], a.ancho_secuencia): x for x in faltan}
        for fu in as_completed(fut):
            x = fut[fu]
            try:
                r = fu.result()
            except Exception as e:
                errores += 1
                print(f"{x['clip'][:24]:24s} ERROR: {e}", flush=True)
                continue
            hechos[x["ruta"]] = r
            guardar()
            print(linea(r), flush=True)
    guardar()
    print(f"\n{len(hechos)} de {len(items)} medidos" + (f" · {errores} con ERROR, no escritos" if errores else ""))
    sys.exit(1 if errores else 0)


def cmd_buscar(a):
    datos = [r for r in json.load(open(a.datos)) if isinstance(r, dict) and "tiron" in r]
    if a.clips:
        datos = [r for r in datos if r.get("clip") in a.clips or r.get("ruta") in a.clips
                 or os.path.basename(r.get("ruta", "")) in a.clips]
        faltan = [c for c in a.clips if not any(c in (r.get("clip"), r.get("ruta"), os.path.basename(r.get("ruta", ""))) for r in datos)]
        for c in faltan:
            print(f"{c}: SIN MEDIR en {a.datos}")
    for r in datos:
        paso = float(r.get("paso") or PASO)
        if r.get("metodo") != METODO:
            print(f"{r['clip'][:24]:24s} OJO: medido con otro metodo ({r.get('metodo') or 'el original, fps=25'}): "
                  "sus tirones traen el artefacto del muestreo")
        s, inl = r["tiron"], r["inl"]
        n = len(s); w = int(round(a.largo / paso)) + 1
        b = int(round(a.borde / paso))
        a0, a1 = b, n - b - w
        if a1 < a0:
            a0, a1 = 0, n - w
        if a1 < a0:
            print(f"{r['clip'][:24]:24s} dura {n * paso:.1f}s, no alcanza para {a.largo}s")
            continue
        # [k, k+w): el paso k ya incluye la ventana del primer cuadro visible (ver `medir`), asi
        # que no hace falta mirar el paso anterior, y mirarlo metia saltos de antes del corte.
        # La ventana tiene un paso de mas al final, como el original: de lado seguro.
        ven = lambda k: slice(k, k + w)
        cand = sorted((max(s[ven(k)]), k) for k in range(a0, a1 + 1) if min(inl[ven(k)]) >= INL_MIN)
        elegidos = []
        for pico, k in cand:
            if all(abs(k - k2) >= w for _, k2 in elegidos):
                elegidos.append((pico, k))
            if len(elegidos) == a.cuantos:
                break
        if not elegidos:
            print(f"{r['clip'][:24]:24s} dura {n * paso:5.1f}  NINGUNA ventana de {a.largo}s con inl >= {INL_MIN}: "
                  "el movimiento de camara no se pudo estimar, se mira")
            continue
        print(f"{r['clip'][:24]:24s} dura {n * paso:5.1f}  " + "  |  ".join(
            f"in {k * paso:6.2f} tiron {p:5.1f} inl {min(inl[ven(k)]):.2f}" for p, k in elegidos))


def cmd_control(a):
    """La bateria del encabezado sobre un video SINTETICO: el piso del instrumento y el golpe.

    No valida contra el juicio de nadie: valida que el INSTRUMENTO no invente tiron sobre un
    paneo parejo —CFR y VFR— y que siga viendo un golpe conocido. Sale con error si no.
    """
    rng = np.random.default_rng(7)
    lienzo = np.full((960, 1620), 120, np.uint8)
    for _ in range(900):
        x, y = rng.integers(0, 1600), rng.integers(0, 940)
        cv2.rectangle(lienzo, (int(x), int(y)), (int(x + rng.integers(6, 60)), int(y + rng.integers(6, 60))),
                      int(rng.integers(0, 255)), -1)
    lienzo = cv2.GaussianBlur(lienzo, (0, 0), 1.2)
    # 540 de ancho representa una secuencia de 1080: 1 px de video = 2 px de secuencia
    fps = 60000 / 1001
    def video(ruta, extra):
        p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", "540x960",
                              "-r", "60000/1001", "-i", "-", "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p",
                              "-video_track_timescale", "60000", ruta], stdin=subprocess.PIPE)
        for k in range(int(2.5 * fps)):
            t = k / fps
            dx = 150 * t + extra(t)            # 150 px/s de video = 300 px/s de secuencia
            p.stdin.write(cv2.warpAffine(lienzo, np.float32([[1, 0, -dx], [0, 1, 0]]), (540, 960),
                                         flags=cv2.INTER_CUBIC).tobytes())
        p.stdin.close(); p.wait()
    with tempfile.TemporaryDirectory() as d:
        parejo, golpe, vfr = (os.path.join(d, n) for n in ("parejo.mp4", "golpe.mp4", "vfr.mp4"))
        video(parejo, lambda t: 0.0)
        video(golpe, lambda t: 4.0 if t >= 1.25 else 0.0)          # 4 px de video = 8 de secuencia
        # VFR: se tiran cuadros salteados y quedan los tiempos originales de los que sobreviven
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", parejo, "-vf",
                        "select='not(eq(mod(n\\,7)\\,3))*not(eq(mod(n\\,11)\\,5))'", "-fps_mode", "vfr",
                        "-c:v", "libx264", "-crf", "12", vfr], check=True)
        res = {}
        for nom, ruta in (("parejo", parejo), ("vfr", vfr), ("golpe", golpe)):
            x = {"ruta": ruta, "clip": nom, "rotacion": "respetar"}
            r = medir(x, vc.ficha(ruta), 1080)
            t = np.array(r["tiron"])
            res[nom] = {"max": round(float(t.max()), 2), "maxEn": round(int(np.argmax(t)) * PASO, 2),
                        "mediana": round(float(np.median(t)), 2), "cuadros": r["cuadrosFuente"]}
    ok = res["parejo"]["max"] < 1.0 and res["vfr"]["max"] < 1.0 and 5.5 <= res["golpe"]["max"] <= 9.0 \
        and abs(res["golpe"]["maxEn"] - 1.24) <= 0.08
    print(json.dumps(res))
    print(("OK" if ok else "FALLA") + ": paneo parejo de 300 px/s a 59,94 -> tiron max "
          f"{res['parejo']['max']} (CFR) y {res['vfr']['max']} (VFR, {res['vfr']['cuadros']} cuadros); "
          f"golpe de 8 px en 1,25s -> {res['golpe']['max']} en {res['golpe']['maxEn']}s "
          "(lo teorico es 7,1)", file=sys.stderr)
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser(description="Tiron de CAMARA con RANSAC. Ver el encabezado.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("medir")
    m.add_argument("entradas", nargs="+", help="clips, carpetas o listas JSON")
    m.add_argument("--salida", help="default: camara.json al lado de la primera lista, o en la carpeta actual")
    m.add_argument("--base", help="carpeta contra la que se resuelven los `clip` relativos de una lista")
    m.add_argument("--rotacion", choices=vc.ROTACIONES,
                   help="obligatoria si algun clip trae flag de rotacion: ver video_comun.py")
    m.add_argument("--ancho-secuencia", type=int, default=1080,
                   help="el ancho que ocupa el clip en la secuencia; la unidad del tiron")
    m.add_argument("--hilos", type=int, default=3)
    b = sub.add_parser("buscar")
    b.add_argument("--datos", required=True)
    b.add_argument("--largo", type=float, required=True, help="segundos del tramo que se busca")
    b.add_argument("clips", nargs="*")
    b.add_argument("--borde", type=float, default=0.5, help="segundos que se evitan al principio y al final")
    b.add_argument("--cuantos", type=int, default=3)
    sub.add_parser("control")
    a = ap.parse_args()
    {"medir": cmd_medir, "buscar": cmd_buscar, "control": cmd_control}[a.cmd](a)


if __name__ == "__main__":
    main()
