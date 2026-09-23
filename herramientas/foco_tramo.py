#!/usr/bin/env python3
"""Nitidez RELATIVA adentro de un tramo, cuadro por cuadro. NO dice si un plano esta en foco.

    python3 foco_tramo.py <lista.json | clip ...> [--salida X.json] [--base DIR]
                          [--rotacion respetar|ignorar] [--ancho 1080] [--fps 30000/1001] [--hilos 3]

    lista.json: [{"ruta" | "clip"+"carpeta", "entrada": s, "dura": s, "etiqueta", "grupo", "rol"}]
                sin `entrada` ni `dura` se mide el clip entero. Un clip suelto, tambien entero.

Corre con el python3 del sistema (numpy 2 + OpenCV). Salio del armado de b-roll de un evento corporativo
(2026-09-22), donde se llamaba `foco.py`; aca se llama distinto porque `foco.py` es otra cosa —
TOPIQ, compara tomas ENTRE si— y se pisaban. Lo medido esta en `VISION.md`.

## Que hace

La guarda que `nitidez.py` dejo escrita y nunca se construyo: la nitidez no se puede medir en
absoluto —una pared lisa puntua igual que un desenfoque—, pero adentro de 1 a 4 segundos del
MISMO plano el contenido casi no cambia, y ahi si se ve:

  - el foco que se va o que "respira" (la camara buscando): cae la nitidez de todo el cuadro
  - el motion blur de un golpe: una caida de 1 a 3 cuadros

Medida: Tenengrad (Sobel al cuadrado) en una grilla de 6x10 bloques —10x6 si el cuadro es
horizontal—, y el percentil 80 de los bloques: el sujeto, que es lo que esta en foco, y no el
promedio con un fondo blando a proposito. Cada cuadro se compara contra el MAXIMO del propio
tramo (`rel`). Tambien la luminancia media, para ver saltos de exposicion, y la diferencia media
con el cuadro anterior a 270 de ancho (`dif`), para ver si en la caida el contenido se movia.

A la resolucion en que se va a ver: `--ancho` es el ancho de la secuencia (1080 por default) y
el alto sale del clip. Muestreo parejo: cada K cuadros de fuente, con K el menor entero que deja
la cadencia en 30 o menos (59,94 -> 29,97, que es lo que usaba el original).

## Lo que NO hace, y hay que tenerlo presente

- **Un plano blando de punta a punta no lo ve**: la medida es relativa y su nitidez es pareja.
  Por eso en el evento se miraron los 64 tramos con `foco_de_cerca.py`, que muestra el cuadro mas
  nitido y el menos nitido de cada uno.
- **No filtra con `dif`, lo informa.** El encabezado del original decia que marcaba una caida
  "solo si la diferencia entre cuadros se mantiene chica", y el codigo no lo hacia: marcaba por
  `nitidezMin < 0,75` o `lumRango > 20` e imprimia el `dif` al lado. Aca queda dicho como es.
  `MIRAR` es "mirar", no "esta mal"; esos dos umbrales no se calibraron.
- **Falso positivo medido: el acercamiento lento.** C2452 dio 0,34 estando nitido. Cuando el
  objeto crece en cuadro baja la nitidez medida, y la `dif` entre cuadros CONSECUTIVOS no lo ve
  porque el cambio es lento.

## Aciertos, en el evento

Una pantalla que rota logos desenfocada a los 2,3 s (C2391); folletos cuyo foco cae de 92% a
51% en 2,5 s (A001C130); un conector que se desenfoca entre 8 y 10 s (A001C114); un detalle que
pierde foco a los 2 s (C2370). Ninguno se decidio por el numero solo: se miraron los cuadros.
"""
import argparse, json, os, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import video_comun as vc

ANCHO_DIF = 270          # la `dif` entre cuadros se mide chica: es para ver movimiento, no detalle
HERRAMIENTA = "foco_tramo.py"


def medir(x, f, ancho, fps_pedido):
    rot = x["rotacion"]
    if f["fps"] <= 0 and not fps_pedido:
        raise RuntimeError("ffprobe no dio los fps: pasa --fps")
    fps = Fraction(fps_pedido) if fps_pedido else vc.fps_de_medida(f["fps"])
    W, H = ancho, vc.alto_par(ancho, f, rot)
    filas, cols = (10, 6) if H >= W else (6, 10)
    Hd = vc.alto_par(ANCHO_DIF, f, rot)
    ent = float(x.get("entrada") or 0.0)
    dura = x.get("dura")
    cmd = (["ffmpeg", "-v", "error"] + vc.entrada_ffmpeg(x["ruta"], rot, desde=ent)
           + (["-t", f"{float(dura):.3f}"] if dura else [])
           + ["-an", "-vf", f"fps={fps},scale={W}:{H},format=gray", "-f", "rawvideo", "-"])
    ten, lum, dif, prev = [], [], [], None
    tam = W * H
    with tempfile.TemporaryFile() as fe:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=fe)
        # de a un cuadro: el original leia el tramo entero de una vez, y a 1080x1920 un clip de
        # 60 s son 3,7 GB en memoria
        while True:
            b = p.stdout.read(tam)
            if len(b) < tam:
                sobra = len(b)
                break
            c = np.frombuffer(b, np.uint8).reshape(H, W)
            g = c.astype(np.float32)
            gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
            gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
            m = gx * gx + gy * gy
            bl = m[:H // filas * filas, :W // cols * cols].reshape(filas, H // filas, cols, W // cols).mean(axis=(1, 3))
            ten.append(float(np.percentile(bl, 80)))
            lum.append(float(g.mean()))
            chico = cv2.resize(c, (ANCHO_DIF, Hd), interpolation=cv2.INTER_AREA).astype(np.float32)
            dif.append(0.0 if prev is None else float(np.abs(chico - prev).mean()))
            prev = chico
        p.wait()
        fe.seek(0)
        err = fe.read().decode("utf8", "replace")
    if p.returncode != 0:
        raise RuntimeError("ffmpeg fallo: " + (err.strip().splitlines() or ["?"])[-1][:200])
    if sobra:
        raise RuntimeError(f"sobraron {sobra} bytes: el cuadro no mide {W}x{H}, la geometria esta mal")
    if not ten:
        raise RuntimeError("no se leyo ningun cuadro")
    ten = np.array(ten)
    rel = ten / ten.max()
    paso = float(1 / fps)
    kmin, kmax = int(rel.argmin()), int(rel.argmax())
    return {
        **{c: v for c, v in x.items() if c not in ("rel", "dif", "ten", "error")},
        "herramienta": HERRAMIENTA, "entrada": ent, "fps": str(fps), "ancho": W, "alto": H,
        "cuadros": int(len(ten)),
        "nitidezMin": round(float(rel.min()), 3), "minEn": round(ent + kmin * paso, 3),
        "maxEn": round(ent + kmax * paso, 3),
        "difEnMin": round(dif[kmin], 2),
        "difMediana": round(float(np.median(dif[1:])) if len(dif) > 1 else 0.0, 2),
        "lumRango": round(float(max(lum) - min(lum)), 1), "lumMedia": round(float(np.mean(lum)), 1),
        "rel": np.round(rel, 3).tolist(), "dif": np.round(dif, 2).tolist(),
        "ten": np.round(ten, 2).tolist(),
    }


def main():
    ap = argparse.ArgumentParser(description="Nitidez relativa adentro de un tramo. Ver el encabezado.")
    ap.add_argument("entradas", nargs="+", help="lista JSON de tramos, o clips (se miden enteros)")
    ap.add_argument("--salida", help="default: <lista>.foco_tramo.json al lado de la lista, o ./foco_tramo.json")
    ap.add_argument("--base", help="carpeta contra la que se resuelven los `clip` relativos")
    ap.add_argument("--rotacion", choices=vc.ROTACIONES, help="obligatoria si algun clip trae flag: ver video_comun.py")
    ap.add_argument("--ancho", type=int, default=1080, help="el de la secuencia: se mide como se va a ver")
    ap.add_argument("--fps", help="cadencia de medida (p.ej. 30000/1001). Default: submuestreo parejo a <=30")
    ap.add_argument("--hilos", type=int, default=3)
    ap.add_argument("--umbral-nitidez", type=float, default=0.75, help="para marcar MIRAR; no calibrado")
    ap.add_argument("--umbral-luz", type=float, default=20, help="para marcar MIRAR; no calibrado")
    a = ap.parse_args()

    items = vc.resolver(a.entradas, a.base)
    fichas = vc.fichas_de(items)
    items = vc.decidir_rotacion(items, fichas, a.rotacion)
    jsons = [e for e in a.entradas if e.lower().endswith(".json")]
    sal = a.salida or (os.path.splitext(os.path.abspath(jsons[0]))[0] + ".foco_tramo.json" if jsons
                       else os.path.join(os.getcwd(), "foco_tramo.json"))
    if os.path.exists(sal):
        viejo = json.load(open(sal))
        if any(not isinstance(r, dict) or r.get("herramienta") != HERRAMIENTA for r in viejo):
            sys.exit(f"{sal} existe y no lo escribio {HERRAMIENTA} (el `foco.json` del armado del evento, por "
                     "ejemplo): no se pisa un registro ajeno. Pasa otra --salida.")
    print(f"{len(items)} tramo(s) · salida: {sal}\n", flush=True)

    def uno(x):
        try:
            return medir(x, fichas[x["ruta"]], a.ancho, a.fps)
        except Exception as e:
            # con `herramienta` tambien: si no, la corrida siguiente toma su propia salida por ajena
            return {**x, "herramienta": HERRAMIENTA, "error": str(e)}
    with ThreadPoolExecutor(a.hilos) as ex:
        res = list(ex.map(uno, items))
    json.dump(res, open(sal, "w"), indent=1, ensure_ascii=False)
    errores = 0
    for r in res:
        nom = (r.get("etiqueta") or r.get("grupo") or "") + (f" {r['rol']}" if r.get("rol") else "")
        nom = f"{nom.strip()[:18]:18s} " if nom.strip() else ""
        if "error" in r:
            errores += 1
            print(f"{nom}{r['clip'][:14]:14s} ERROR: {r['error']}")
            continue
        ojo = " <-MIRAR" if r["nitidezMin"] < a.umbral_nitidez or r["lumRango"] > a.umbral_luz else ""
        print(f"{nom}{r['clip'][:14]:14s} in {r['entrada']:6.2f} nitidez min {r['nitidezMin']:.2f} @{r['minEn']:6.2f} "
              f"(dif {r['difEnMin']:4.1f} / med {r['difMediana']:4.1f}) lum {r['lumMedia']:5.1f} "
              f"rango {r['lumRango']:4.1f}{ojo}")
    print(f"\nMIRAR es para mirar, no un veredicto: la medida es RELATIVA al tramo, asi que un plano blando\n"
          f"de punta a punta no aparece, y un acercamiento lento baja la nitidez sin estar fuera de foco.\n"
          f"Los cuadros: foco_de_cerca.py --datos {sal}")
    sys.exit(1 if errores else 0)


if __name__ == "__main__":
    main()
