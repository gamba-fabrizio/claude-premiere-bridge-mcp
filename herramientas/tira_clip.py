#!/usr/bin/env python3
"""Hoja de un clip ENTERO, un cuadro cada `--paso` segundos, con el tiempo de FUENTE en cada uno.

    python3 tira_clip.py <clip> [--rotacion respetar|ignorar] [--paso 0.4] [--ancho 240]
                         [--columnas 8] [--desde S] [--hasta S] [--destino DIR]

Para elegir un in-point mirando, y para decidir la ROTACION antes de medir nada: si el clip trae
flag, `camara.py` y `foco_tramo.py` rebotan hasta que se les diga que hacer, y lo que decide es
correr esto con `--rotacion respetar` y con `--rotacion ignorar` y ver cual sale derecha. Ver
`video_comun.py`. Corre con el python3 del sistema (Pillow).

El rotulo es `desde + k·paso`: el filtro `fps` entrega el cuadro k en ese tiempo, con el cuadro
de fuente mas cercano —medido: a lo sumo un cuadro de fuente corrido, 17 ms a 59,94—, asi que
alcanza para elegir un in-point a la decima.
"""
import argparse, os, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import video_comun as vc

RENGLON = 26
try:
    FUENTE = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 20)
except Exception:
    FUENTE = ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser(description="Tira de contacto de un clip, con tiempos de fuente.")
    ap.add_argument("clip")
    ap.add_argument("--rotacion", choices=vc.ROTACIONES, help="obligatoria si el clip trae flag")
    ap.add_argument("--paso", type=float, default=0.4)
    ap.add_argument("--ancho", type=int, default=240)
    ap.add_argument("--columnas", type=int, default=8)
    ap.add_argument("--desde", type=float, default=None)
    ap.add_argument("--hasta", type=float, default=None)
    ap.add_argument("--destino", default=os.getcwd())
    a = ap.parse_args()

    x = vc.resolver([a.clip])[0]
    f = vc.fichas_de([x])[x["ruta"]]
    x = vc.decidir_rotacion([x], {x["ruta"]: f}, a.rotacion)[0]
    H = vc.alto_par(a.ancho, f, x["rotacion"])
    desde = a.desde or 0.0
    lim = ["-t", f"{a.hasta - desde:.3f}"] if a.hasta else []
    base = os.path.splitext(os.path.basename(x["ruta"]))[0]
    # si el clip trae flag, el nombre dice con que rotacion se hizo: se hacen las dos para comparar
    sufijo = f"_{x['rotacion']}" if f["rot"] else ""
    os.makedirs(a.destino, exist_ok=True)
    salida = os.path.join(a.destino, f"tira_{base}{sufijo}.jpg")
    with tempfile.TemporaryDirectory() as d:
        cmd = (["ffmpeg", "-v", "error", "-y"] + vc.entrada_ffmpeg(x["ruta"], x["rotacion"], desde=a.desde)
               + lim + ["-vf", f"fps=1/{a.paso},scale={a.ancho}:{H}", "-q:v", "3", os.path.join(d, "%04d.jpg")])
        p = subprocess.run(cmd, capture_output=True, text=True)
        fs = sorted(os.listdir(d))
        if p.returncode != 0 or not fs:
            sys.exit(f"ffmpeg no saco cuadros: {p.stderr.strip()[:300]}")
        filas = (len(fs) + a.columnas - 1) // a.columnas
        im = Image.new("RGB", (a.columnas * a.ancho, filas * (H + RENGLON)), (20, 20, 20))
        dr = ImageDraw.Draw(im)
        for k, n in enumerate(fs):
            px, py = (k % a.columnas) * a.ancho, (k // a.columnas) * (H + RENGLON)
            im.paste(Image.open(os.path.join(d, n)), (px, py + RENGLON))
            dr.text((px + 4, py + 3), f"{desde + k * a.paso:.1f}s", fill=(255, 225, 120), font=FUENTE)
    im.save(salida, quality=85)
    print(salida, len(fs), "cuadros", f"(flag {f['rot']}, rotacion {x['rotacion']})" if f["rot"] else "")


if __name__ == "__main__":
    main()
