#!/usr/bin/env python3
"""Hojas para MIRAR el foco de cerca: de cada tramo, su cuadro MAS nitido y su MENOS nitido.

    python3 foco_de_cerca.py --datos X.foco_tramo.json [--destino DIR] [--ancho 720] [grupo ...]

Lee lo que escribe `foco_tramo.py`. Una hoja por `grupo` —en el evento la frase de la locucion:
titular arriba, suplente abajo—; un tramo sin grupo va solo. A 720 de ancho por default, dos
tercios de una secuencia de 1080, que es como se ve en un telefono. Corre con el python3 del
sistema (Pillow).

Por que esos dos cuadros y no tres repartidos: un tramo blando de punta a punta no lo marca
ninguna medida relativa —su nitidez es pareja— y se ve en cualquier cuadro; uno que se va de foco
en el medio se ve en el peor. El par cubre los dos casos, y es lo que se miro en los 64 tramos del
evento, porque `foco_tramo.py` solo no alcanza.

Los cuadros son LOS MISMOS que se midieron: mismo `-ss`, mismo filtro `fps` y el indice con
`select`. El original los pedia con `-ss` al tiempo calculado; con un golpe que dura 1 a 3
cuadros, un cuadro de fuente de diferencia muestra otro, y con `select` no hay cuenta que se
pueda correr. La rotacion sale del JSON, la misma con que se midio.
"""
import argparse, json, os, re, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import video_comun as vc

RENGLON = 56          # dos lineas de rotulo
try:
    FUENTE = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 22)
except Exception:
    FUENTE = ImageFont.load_default()


def cabe(dr, texto, ancho):
    """El rotulo se RECORTA al ancho de su celda: uno largo se monta sobre el de al lado y deja
    ilegible justo lo que hay que leer (paso con esta misma hoja a 360 de ancho)."""
    while texto and dr.textlength(texto, font=FUENTE) > ancho:
        texto = texto[:-2] + "…"
    return texto


def cuadros(r, ancho):
    """Los cuadros mas y menos nitido del tramo, en ese orden, como imagenes."""
    rel = r["rel"]
    kmax = max(range(len(rel)), key=rel.__getitem__)
    kmin = min(range(len(rel)), key=rel.__getitem__)
    f = vc.ficha(r["ruta"])
    H = vc.alto_par(ancho, f, r["rotacion"])
    ks = sorted({kmax, kmin})
    sel = "+".join(f"eq(n\\,{k})" for k in ks)
    with tempfile.TemporaryDirectory() as d:
        cmd = (["ffmpeg", "-v", "error", "-y"] + vc.entrada_ffmpeg(r["ruta"], r["rotacion"], desde=r["entrada"])
               + ["-vf", f"fps={r['fps']},select='{sel}',scale={ancho}:{H}", "-fps_mode", "passthrough",
                  "-frames:v", str(len(ks)), "-q:v", "2", os.path.join(d, "%02d.jpg")])
        p = subprocess.run(cmd, capture_output=True, text=True)
        salen = sorted(os.listdir(d))
        if p.returncode != 0 or len(salen) != len(ks):
            raise RuntimeError(f"{r['clip']}: salieron {len(salen)} de {len(ks)} cuadros. {p.stderr.strip()[:200]}")
        im = {k: Image.open(os.path.join(d, n)).convert("RGB") for k, n in zip(ks, salen)}
    paso = 1 / float(eval(r["fps"]))
    return [(im[kmax], r["entrada"] + kmax * paso, rel[kmax], "mas nitido"),
            (im[kmin], r["entrada"] + kmin * paso, rel[kmin], "menos nitido")], H


def hoja(nombre, tramos, ancho, destino):
    filas = []
    with ThreadPoolExecutor(2) as ex:
        filas = list(ex.map(lambda r: (r, *cuadros(r, ancho)), tramos))
    alto_fila = max(H for _, _, H in filas) + RENGLON
    im = Image.new("RGB", (2 * ancho, len(filas) * alto_fila), (20, 20, 20))
    dr = ImageDraw.Draw(im)
    for n, (r, pares, H) in enumerate(filas):
        y = n * alto_fila
        quien = (r.get("rol") or r.get("etiqueta") or "").upper()
        for k, (c, t, v, que) in enumerate(pares):
            im.paste(c, (k * ancho, y + RENGLON))
            dr.text((k * ancho + 8, y + 4), cabe(dr, f"{quien} {r['clip']}".strip(), ancho - 16),
                    fill=(255, 225, 120), font=FUENTE)
            dr.text((k * ancho + 8, y + 29), cabe(dr, f"t={t:.2f}  {que} {v:.2f}", ancho - 16),
                    fill=(255, 225, 120), font=FUENTE)
    ruta = os.path.join(destino, "cerca_" + re.sub(r"[^\w.-]+", "_", nombre).strip("_") + ".jpg")
    im.save(ruta, quality=88)
    return ruta


def main():
    ap = argparse.ArgumentParser(description="El cuadro mas y menos nitido de cada tramo. Ver el encabezado.")
    ap.add_argument("--datos", required=True, help="lo que escribio foco_tramo.py")
    ap.add_argument("--destino", help="default: carpeta `cerca` al lado de --datos")
    ap.add_argument("--ancho", type=int, default=720)
    ap.add_argument("grupos", nargs="*", help="solo estos grupos (o etiquetas)")
    a = ap.parse_args()
    datos = json.load(open(a.datos))
    ajenos = [r for r in datos if not isinstance(r, dict) or r.get("herramienta") != "foco_tramo.py"]
    if ajenos:
        sys.exit(f"{a.datos} no lo escribio foco_tramo.py ({len(ajenos)} entrada(s) ajenas): no se sabe con que "
                 "rotacion ni cadencia se midio, y la hoja podria mostrar otro cuadro.")
    destino = a.destino or os.path.join(os.path.dirname(os.path.abspath(a.datos)), "cerca")
    os.makedirs(destino, exist_ok=True)
    grupos = {}
    for r in datos:
        if "error" in r:
            print(f"{r.get('clip')}: se salta, no se midio ({r['error'][:80]})")
            continue
        g = r.get("grupo") or r.get("etiqueta") or f"{os.path.splitext(r['clip'])[0]}_{r['entrada']:.2f}"
        if a.grupos and g not in a.grupos and r.get("etiqueta") not in a.grupos:
            continue
        grupos.setdefault(g, []).append(r)
    if not grupos:
        sys.exit("ningun tramo para mostrar" + (f" con {a.grupos}" if a.grupos else ""))
    for g, tramos in grupos.items():
        print(hoja(g, tramos, a.ancho, destino), flush=True)


if __name__ == "__main__":
    main()
