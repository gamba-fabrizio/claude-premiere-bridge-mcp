#!/usr/bin/env python3
"""La línea de tiempo que necesita `subtitular.py`, leída del .prproj GUARDADO y con los NESTED
abiertos. Sólo LEE, y no necesita Premiere.

    python3 herramientas/timeline_prproj.py <proyecto.json> "<video>" [--prproj <archivo>] [--secuencia "<nombre>"]

Deja lo mismo que `timeline_subtitulos.js`, que la lee por el bridge, con dos diferencias que son la
razón de este lector:

  - ABRE LOS NESTED. Cuando el editor anida la voz para mezclarla, el bridge ve UN clip con el nombre
    del nested, y sin los clips de adentro no hay de dónde sacar las palabras de cada toma. Acá cada
    clip de adentro sale en tiempo de la secuencia y RECORTADO a lo que el nested deja ver: si el
    editor le recortó la cabeza, lo recortado no suena y no cuenta. El lector del proyecto que esto
    generaliza no recortaba, y con el primer recorte de cabeza metió un fragmento en -5,97 s.
  - Lee lo GUARDADO: lo que el editor no guardó no está. Sin `--prproj` toma el más nuevo entre el
    .prproj del proyecto y sus autoguardados, y dice cuál leyó y de qué hora es.

## Qué deja, en «<video> - timeline.json» (la ruta sale del proyecto)

  fps       los de la secuencia, del FrameRate de sus pistas de video.
  fin       dónde termina el último clip, contando los desactivados (como el bridge).
  A         cada pista de audio con sus clips, `[medio, desde, hasta, entrada]`, con los nested abiertos:
            lo de adentro sale en la pista del nested. Los streams de un medio multicanal dejan un clip
            por pista adentro del nested, y se juntan en uno. Un clip que no corre a 1x lleva su
            velocidad de quinto elemento, y `subtitular.py` no proyecta palabras sobre él.
  V         los rangos de las pistas de video, nested incluidos como un rango: los cortes de plano.
  internos  los bordes de los planos ADENTRO de cada nested de video, `[segundo, pista del nested]`:
            son cortes que se ven y que el bridge no ve.
  titulos   los clips cuyo nombre empieza con uno de los `titulos` del proyecto: no son planos.
  rutas     el archivo de cada medio de audio, como lo tiene el proyecto: la envolvente de
            `subtitular.py` lee la voz de ahí.

Quedan afuera de V, como en el bridge, los clips DESACTIVADOS y los títulos. Y las capas de ajuste
—«Adjustment Layer» o «Capa de ajuste» en el nombre—: no cambian el plano, y una que tape toda la
secuencia taparía todos los cortes de abajo.

## Del proyecto (el JSON de `subtitular.py`)

  prproj       el .prproj, relativo al JSON: se usa si no se pasa `--prproj`.
  secuencia    el nombre EXACTO de la secuencia; va por video en `videos` (ver `subtitular.py`).
  titulos      los prefijos de los clips que no son planos: títulos, zócalos, logos.
"""
import glob, gzip, json, os, sys, time
import xml.etree.ElementTree as ET

TPS = 254016000000                        # ticks por segundo de Premiere
AJUSTE = ("Adjustment Layer", "Capa de ajuste")
PROFUNDIDAD = 3                           # nested adentro de nested: más que esto no se abre


class Prproj:
    def __init__(self, ruta):
        self.root = ET.fromstring(gzip.open(ruta).read())
        self.id, self.uid = {}, {}
        for el in self.root:
            if "ObjectID" in el.attrib: self.id[el.attrib["ObjectID"]] = el
            if "ObjectUID" in el.attrib: self.uid[el.attrib["ObjectUID"]] = el

    def ref(self, el):
        if el is None: return None
        if "ObjectRef" in el.attrib: return self.id.get(el.attrib["ObjectRef"])
        if "ObjectURef" in el.attrib: return self.uid.get(el.attrib["ObjectURef"])
        return None

    @staticmethod
    def seg(el, camino):
        e = el.find(camino)   # un clip que arranca en 0 no trae <Start>: Premiere omite el valor por defecto
        return int(e.text) / TPS if e is not None and e.text else 0.0

    def secuencia(self, nombre):
        s = [e for e in self.root.iter("Sequence") if e.findtext("Name") == nombre and "ObjectUID" in e.attrib]
        if len(s) != 1:
            parecidas = sorted({e.findtext("Name") for e in self.root.iter("Sequence")
                                if nombre.lower() in (e.findtext("Name") or "").lower()})
            raise SystemExit(f"«{nombre}»: {len(s)} secuencias con ese nombre EXACTO"
                             + (f"; parecidas: {', '.join(parecidas)}" if parecidas else ""))
        return s[0]

    def grupo(self, seq, tipo):
        for tg in seq.findall("TrackGroups/TrackGroup"):
            g = self.ref(tg.find("Second"))
            if g is not None and g.tag == tipo + "TrackGroup":
                return g
        return None

    def fps(self, seq):
        g = self.grupo(seq, "Video")
        ticks = g.findtext("TrackGroup/FrameRate") if g is not None else None
        if not ticks:
            raise SystemExit("la secuencia no trae el FrameRate de sus pistas de video")
        return TPS / int(ticks)

    def ruta(self, src):
        """El archivo del medio de un clip, o None (una secuencia, un medio sintético)."""
        if src is None: return None
        media = self.ref(src.find("MediaSource/Media"))
        if media is None: return None
        r = media.findtext("ActualMediaFilePath") or media.findtext("FilePath")
        return r if r and r.startswith("/") else None

    def items(self, seq, tipo):
        """Los clips de `seq`, en tiempo de ESA secuencia."""
        g = self.grupo(seq, tipo)
        if g is None: return []
        res = []
        for i, t in enumerate(g.findall("TrackGroup/Tracks/Track")):
            tr = self.ref(t)
            if tr is None: continue
            for ti in tr.findall("ClipTrack/ClipItems/TrackItems/TrackItem"):
                it = self.ref(ti)
                if it is None or it.tag != tipo + "ClipTrackItem": continue
                cti = it.find("ClipTrackItem")
                sub = self.ref(cti.find("SubClip"))
                envoltorio = self.ref(sub.find("Clip")) if sub is not None else None
                clip = envoltorio.find("Clip") if envoltorio is not None else None
                if clip is None: continue
                src = self.ref(clip.find("Source"))
                anidada = None
                if src is not None and src.tag.endswith("SequenceSource"):
                    anidada = self.ref(src.find("SequenceSource/Sequence"))
                res.append(dict(pista=f"{tipo[0]}{i + 1}", desde=self.seg(cti, "TrackItem/Start"),
                                hasta=self.seg(cti, "TrackItem/End"), entrada=self.seg(clip, "InPoint"),
                                velocidad=float(clip.findtext("PlaybackSpeed") or 1.0),
                                nombre=sub.findtext("Name") or "", apagado=cti.findtext("IsMuted") == "true",
                                anidada=anidada, ruta=self.ruta(src)))
        return res


def al_padre(c, u):
    """Un instante de adentro del nested `c`, en tiempo de la secuencia que lo contiene."""
    return c["desde"] + (u - c["entrada"]) / c["velocidad"]


def aplanar(P, seq, tipo, prof=0):
    """Los clips de `seq` con los nested abiertos, en tiempo de `seq` y recortados a lo que cada nested
    deja ver. Lo de adentro hereda la pista del nested; un nested apagado apaga lo de adentro."""
    out = []
    for c in P.items(seq, tipo):
        if c["anidada"] is None or prof >= PROFUNDIDAD:
            out.append(c)
            continue
        for d in aplanar(P, c["anidada"], tipo, prof + 1):
            a, b = al_padre(c, d["desde"]), al_padre(c, d["hasta"])
            a2, b2 = max(a, c["desde"]), min(b, c["hasta"])
            if b2 - a2 <= 1e-6:
                continue                   # lo que el nested no deja ver no suena ni se ve
            v = d["velocidad"] * c["velocidad"]
            out.append(dict(d, desde=a2, hasta=b2, entrada=d["entrada"] + (a2 - a) * v, velocidad=v,
                            pista=c["pista"], apagado=d["apagado"] or c["apagado"]))
    return out


def elegir(ruta):
    """El .prproj o su autoguardado más nuevo: el autoguardado tiene lo que el editor todavía no guardó."""
    madre = os.path.join(os.path.dirname(ruta), "Adobe Premiere Pro Auto-Save")
    base = os.path.splitext(os.path.basename(ruta))[0]
    cand = [ruta] + glob.glob(os.path.join(madre, glob.escape(base) + "--*.prproj"))
    return max(cand, key=os.path.getmtime)


def ahora():
    return time.strftime("%Y-%m-%d %H:%M")


def main():
    args = sys.argv[1:]
    def opt(n):
        return args[args.index("--" + n) + 1] if "--" + n in args and args.index("--" + n) + 1 < len(args) else None
    if len(args) < 2 or args[0].startswith("--") or args[1].startswith("--"):
        raise SystemExit(__doc__.split("\n\n")[1])
    ruta_proyecto, video = args[0], args[1]
    P0 = json.load(open(ruta_proyecto, encoding="utf-8"))
    if "videos" in P0 and video not in P0["videos"]:
        raise SystemExit(f"«{video}» no está en `videos` del proyecto: {', '.join(P0['videos'])}")
    cfg = dict(P0, **P0.get("videos", {}).get(video, {}))
    base = os.path.dirname(os.path.abspath(ruta_proyecto))
    carpeta = os.path.join(base, cfg.get("carpeta", "."))
    salida = os.path.join(carpeta, cfg.get("timeline", "{video} - timeline.json").replace("{video}", video))
    prefijos = tuple(str(x) for x in cfg.get("titulos", []))

    if opt("prproj"):
        ruta = opt("prproj")                                   # explícito: ése y no otro
    elif cfg.get("prproj"):
        ruta = elegir(os.path.join(base, cfg["prproj"]))
    else:
        raise SystemExit("falta el .prproj: `--prproj <archivo>` o `prproj` en el proyecto")
    nombre = opt("secuencia") or cfg.get("secuencia")
    if not nombre:
        raise SystemExit(f"falta la secuencia de «{video}»: `--secuencia` o `secuencia` en `videos` del proyecto")

    P = Prproj(ruta)
    seq = P.secuencia(nombre)
    fps = P.fps(seq)
    arriba_v, arriba_a = P.items(seq, "Video"), P.items(seq, "Audio")
    fin = max([c["hasta"] for c in arriba_v + arriba_a] or [0.0])

    # ---- audio: cada pista con los nested abiertos ----
    A, rutas, lentos, nested_a = {}, {}, [], 0
    for c in arriba_a:
        if c["anidada"] is not None: nested_a += 1
    for c in aplanar(P, seq, "Audio"):
        if c["apagado"] or c["anidada"] is not None: continue
        e = [c["nombre"], round(c["desde"], 4), round(c["hasta"], 4), round(c["entrada"], 4)]
        if abs(c["velocidad"] - 1.0) > 1e-9:
            e.append(c["velocidad"]); lentos.append(f"{c['pista']} {c['nombre']} {c['velocidad']}x")
        A.setdefault(c["pista"], {})[(e[0], e[1], e[3])] = e      # un medio multicanal: un clip por stream
        if c["ruta"]: rutas[c["nombre"]] = c["ruta"]
    A = {p: sorted(d.values(), key=lambda e: e[1]) for p, d in A.items()}

    # ---- video: los rangos de arriba, y los bordes de adentro de los nested ----
    V, titulos, internos, ajustes = {}, [], [], 0
    for c in arriba_v:
        if c["apagado"]: continue
        if any(x in c["nombre"] for x in AJUSTE):
            ajustes += 1; continue
        if prefijos and c["nombre"].startswith(prefijos):
            titulos.append([c["nombre"], round(c["desde"], 6), round(c["hasta"], 6)]); continue
        V.setdefault(c["pista"], []).append([round(c["desde"], 6), round(c["hasta"], 6)])
        if c["anidada"] is not None:
            for d in aplanar(P, c["anidada"], "Video", 1):
                if d["apagado"]: continue
                for u in (d["desde"], d["hasta"]):
                    t = al_padre(c, u)
                    if c["desde"] + 0.05 < t < c["hasta"] - 0.05:   # el borde del nested ya está en V
                        internos.append([round(t, 3), c["pista"]])
    internos = sorted({tuple(x) for x in internos})

    T = {
        "secuencia": nombre,
        "leido": f"{ahora()}, timeline_prproj.py de {os.path.basename(ruta)} "
                 f"(guardado {time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(ruta)))})",
        "fin": fin, "fps": fps, "A": A, "V": V, "internos": [list(x) for x in internos],
        "titulos": titulos, "rutas": rutas,
    }
    os.makedirs(os.path.dirname(salida), exist_ok=True)
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(T, f, ensure_ascii=False, indent=1)

    cuenta = lambda o: " · ".join(f"{k} {len(v)}" for k, v in sorted(o.items(), key=lambda kv: int(kv[0][1:]))) or "ninguna"
    pedidas = list(cfg.get("pistas", {}).get("habla", ["A1"])) + list(cfg.get("pistas", {}).get("locucion", []))
    faltan = [p for p in pedidas if p not in A]
    print(f"leído: {ruta}  (guardado {time.ctime(os.path.getmtime(ruta))})")
    print(f"{video} «{nombre}»: {fps:.3f} fps · fin {fin:.3f} s · audio: {cuenta(A)} · video: {cuenta(V)} · "
          f"bordes adentro de nested: {len(internos)} · títulos {len(titulos)} · capas de ajuste {ajustes}"
          + (f" · nested de audio abiertos: {nested_a}" if nested_a else "")
          + (f" · OJO: el proyecto pide {', '.join(faltan)} y no tienen clips" if faltan else "")
          + (f" · OJO: clips de audio que no corren a 1x: {', '.join(lentos)}" if lentos else ""))
    print(f"escrito: {salida}")


if __name__ == "__main__":
    main()
