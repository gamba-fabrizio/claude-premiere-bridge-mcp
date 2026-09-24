#!/usr/bin/env python3
"""Subtítulos de HABLA: el texto final, la división en bloques y el SRT que Premiere importa.

    python3 herramientas/subtitular.py <proyecto.json> "<video>"

Es la vía de la entrevista, el testimonio, la locución y el reel. La de la letra cantada —PNG
colocados como clips— es otra, y las dos están en `herramientas/SUBTITULOS.md`, con los criterios
que se validaron.

TEXTO. Sale de una de dos fuentes, y encima van los CAMBIOS de `<video> - ajustes.json`, uno por
uno y con su motivo: lo que el motor oyó mal y lo que se limpia —una grafía, el voseo, una
muletilla, un tartamudeo—.
  - La MEZCLA exportada de la secuencia, transcripta con `audio.js`: oye el audio YA EDITADO.
  - Las transcripciones de cada CLIP entero, si ya existen (`transcripcion_por_clip`): se pasan
    por los cortes de la línea de tiempo y no se gasta en transcribir la mezcla. Entra la palabra
    que ARRANCA adentro del corte, con 0,12 s de gracia, porque Scribe marca tarde el arranque.
Scribe es el que mejor oye y puntúa, y el motor esperado se fija en el proyecto. La locución no se
transcribe: si el proyecto la declara, va el texto EXACTO del guion con los tiempos de `locucion.js`.

DIVISIÓN. Por oración y por contenido. Cada bloque se elige minimizando un costo:
  - cortar donde termina una oración o hay una pausa no cuesta nada; después de una coma, poco;
    antes de "que / porque / pero / y..." algo más; en cualquier otro lado, mucho;
  - cortar después de un artículo, una preposición, un clítico, un «no» o un auxiliar, casi nunca;
    adentro de una frase hecha o de una marca, nunca (las del idioma están acá; las del cliente, en
    `pegadas` del proyecto);
  - el cambio de hablante corta SIEMPRE, y el corte del editor adentro de un mismo hablante ayuda;
  - hasta 2 líneas de 42 caracteres —o las que diga el proyecto, medidas en píxeles de la fuente
    real—, entre ~1 y 7 s, cerca de 17 caracteres por segundo, y la velocidad NO le gana a la
    sintaxis: un testimonio rápido se lee igual, manda la frase.
Lo que el automático no resuelve —acierta ~85 %— se divide a mano: un turno en `manual`, o el
video entero en `bloques`.

TIEMPOS. En cuadros enteros de la secuencia, enganchados a los cortes de plano. Hay DOS modelos, y
salieron de dos trabajos (ver `SUBTITULOS.md`):
  - "entrevista", el de siempre: entra en el cuadro de la primera palabra, sale 0,30 s después de la
    última, dura al menos 0,8 s, y se engancha a un corte hasta 0,32 s antes o 0,36 s cerca.
  - "reel": entra 40 ms antes (Scribe marca tarde), el fin de la frase se MIDE en la envolvente de la
    voz —Scribe estira la última palabra sobre la pausa—, con menos de 0,7 s de pausa queda pegado
    al siguiente y, si no, se sostiene 0,35 s. Engancha al corte más cercano, contando el primer
    cuadro, los bordes adentro de los nested y sin los que tapa una pista de arriba.

EL PROYECTO, un JSON al lado del material (las rutas, relativas a él). Se llama como se quiera —se
recomienda `subtitulos.proyecto.json`—, pero NO `subtitulos.json`, que otras herramientas escriben:

    {
      "carpeta":       ".",                                  donde están los archivos de cada video
      "timeline":      "{video} - timeline.json",            de `timeline_subtitulos.js` o `timeline_prproj.py`
      "transcripcion": "{video} - audio.audio.json",         `audio.js` sobre la MEZCLA exportada
      "transcripcion_por_clip": "transcripciones/{medio}.audio.json",  en vez de la mezcla, la de cada clip
      "motor":         "scribe",                             el que se espera en esa transcripción
      "ajustes":       "{video} - ajustes.json",
      "pistas":        {"habla": ["A1"], "locucion": ["A2"]},
      "locucion":      "../LOCUCION/{medio}.palabras.json",  opcional: el guion con sus tiempos
      "pegadas":       [["nombre", "de marca"], ["el", "6u"]],  las del CLIENTE
      "lineas":        2,                                    1 para el estilo de una sola línea
      "ancho":         {"fuente": "~/Library/Fonts/X.ttf", "cuerpo": 48, "px": 770},
      "tiempos":       "entrevista",                         o "reel"
      "envolvente":    true,                                 sólo "reel": el fin de voz, medido
      "salida":        ".",                                  donde van el SRT y la lista para revisar
      "videos":        {"<video>": {"secuencia": "…", "pistas": {"habla": ["A3"]}}}
    }

`ancho` mide cada línea con la fuente y el cuerpo del estilo, en píxeles: los caracteres no alcanzan
—en Montserrat 48, 29 caracteres midieron 763 px y 31, 707—. Sin `ancho`, el tope es de 42
caracteres. `videos` pisa, para ese video, cualquier clave de arriba. `envolvente` lee la voz de los
medios —`rutas` de la línea de tiempo o el patrón `{"medios": ".../{medio}"}`— y necesita numpy y
scipy (`~/.venvs/audio/bin/python`).

LOS AJUSTES, uno por video, escritos a mano: son decisiones sobre ESE material, no reglas.

    {
      "cambios":       [[segundo, "lo que oyó el motor", "lo que va", "por qué"], ...],
      "agregados":     [["medio", desde_fuente, hasta_fuente, "palabra", "por qué"], ...],
      "para_escuchar": [[segundo, "qué hay que oír"], ...],
      "manual":        [["un bloque / con su salto de línea", "el bloque siguiente"], ...],
      "bloques":       ["el video entero", "dividido a mano", ...],
      "pausa_turno":   1.5
    }

El `segundo` de un cambio es de la secuencia, y el cambio busca a ±3 s. O va `["medio", segundo]`,
un segundo del CLIP: sobrevive a que el editor recorte, que corre todo lo de después. Un cambio a
"" saca la palabra. `agregados` pone lo que suena y el motor no escribió, en tiempo del clip.
Cada lista de `manual` es un turno ENTERO dividido a mano; " / " es el salto de línea. `bloques`
divide el video entero y deja sin uso los turnos. Si el texto no calza palabra por palabra, los dos
rebotan. `pausa_turno` es cuánto silencio parte un turno de un mismo hablante: 1,5 s por defecto; con
testimonios pausados, 2.

Escribe `<video> - subtitulos.srt` y `<video> - revisar.txt`: lo que hay que ESCUCHAR, cada cambio
sobre lo que oyó el motor con su motivo, y los avisos de tiempo.
"""
import json, math, os, re, subprocess, sys, unicodedata
from fractions import Fraction


def cargar_proyecto(ruta, video):
    P0 = json.load(open(ruta, encoding="utf-8"))
    if "videos" in P0 and video not in P0["videos"]:
        # seguir con lo general tomaría otras pistas sin avisar: un nombre mal escrito rebota
        raise SystemExit(f"«{video}» no está en `videos` del proyecto: {', '.join(P0['videos'])}")
    P = dict(P0, **P0.get("videos", {}).get(video, {}))      # lo de un video pisa lo del proyecto
    base = os.path.dirname(os.path.abspath(ruta))
    carpeta = os.path.join(base, P.get("carpeta", "."))
    def archivo(clave, defecto, en=None):
        return os.path.join(en or carpeta, P.get(clave, defecto).format(video=video))
    tiempos = P.get("tiempos", "entrevista")
    if tiempos not in ("entrevista", "reel"):
        raise SystemExit(f"`tiempos` es «entrevista» o «reel», no «{tiempos}»")
    if P.get("envolvente") and tiempos != "reel":
        raise SystemExit("`envolvente` es del modelo de tiempos «reel»: el de entrevista no la usa")
    return {
        "P": P,
        "base": base,
        "timeline": archivo("timeline", "{video} - timeline.json"),
        "transcripcion": archivo("transcripcion", "{video} - audio.audio.json"),
        "por_clip": os.path.join(base, P["transcripcion_por_clip"]) if P.get("transcripcion_por_clip") else None,
        "ajustes": archivo("ajustes", "{video} - ajustes.json"),
        "salida": os.path.join(base, P.get("salida", P.get("carpeta", "."))),
        "motor": P.get("motor", "scribe"),
        "habla": list(P.get("pistas", {}).get("habla", ["A1"])),
        "locucion": list(P.get("pistas", {}).get("locucion", [])),
        "guion": os.path.join(base, P["locucion"]) if P.get("locucion") else None,
        "pegadas": {tuple(x) for x in P.get("pegadas", [])},
        "lineas": int(P.get("lineas", 2)),
        "ancho": P.get("ancho"),
        "tiempos": tiempos,
        "envolvente": P.get("envolvente"),
    }


# ---- la sintaxis que decide dónde se puede cortar: es del IDIOMA, no de un proyecto ----
# palabras que NO pueden quedar al final de una línea o de un bloque: piden lo que viene después
CONJ = set("y o u e pero porque que cuando aunque si como mientras entonces donde ni".split())
NO_FINAL = set("""el la los las lo le les un una unos unas de del a al en con por para sin sobre entre hasta desde
    me te se nos mi mis tu tus su sus muy tan más mas cada este esta estos estas ese esa esos esas
    aquel aquella no es son era fue sea ser está están estaba estar voy va vas vamos tengo tiene tenés tenía hay he
    ha has había hace hacer algún alguna algunos algunas otro otra otros otras todo toda todos todas propia propio
    mismo misma según""".split()) | CONJ
PREP = set("a en con por para sin sobre entre hasta desde según".split())   # «de» va aparte: se pega al sustantivo
DET = set("el la los las un una unos unas este esta estos estas ese esa mi mis su sus tu tus".split())
CLITICO = set("me te se nos lo la le les".split())
COPULA = set("es son está están era fue".split())
# expresiones que no se parten nunca, ni con coma en el medio. Las de una MARCA o un PRODUCTO no van
# acá: van en `pegadas` del proyecto, porque este archivo es de todos los proyectos.
PEGADAS_IDIOMA = {
    ("así", "que"), ("miti", "y"), ("y", "miti"), ("sin", "embargo"), ("más", "o"), ("o", "menos"),
    ("a", "través"), ("un", "par"), ("par", "de"), ("para", "que"), ("lo", "que"), ("bien", "bien"),
    ("tengo", "que"), ("tenés", "que"), ("tenía", "que"), ("salva", "las"), ("las", "papas"),
    ("la", "verdad"), ("un", "poquito"), ("poquito", "más"), ("ya", "no"), ("no", "sé"), ("me", "lo"),
    ("se", "me"), ("se", "nos"), ("que", "me"), ("que", "te"), ("tres", "cuatro"), ("así", "y"),
    ("y", "así"), ("deja", "de"), ("vendría", "a"), ("a", "ser"),
}
MULETILLAS = {"eh", "em", "mm", "ehm", "mmm"}
MAXL = 42
# Las palabras de un CLIP que entran en un corte: la que ARRANCA adentro. Con gracia al principio,
# porque Scribe marca el arranque tarde (mediana 40 ms, medida en los reels), y sin la que arranca en
# los últimos 30 ms, que es la del plano siguiente.
GRACIA_ENTRADA, GRACIA_SALIDA = 0.12, 0.03


def norm(s):
    s = unicodedata.normalize("NFD", str(s).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s)


def palabra(t): return norm(t)


def palabra_cruda(t):
    """Minúsculas y sin puntuación, pero CON tildes: «más» no es «mas»."""
    return re.sub(r"[^\wáéíóúüñ]", "", str(t).lower())


def hacer_fuerza(pegadas):
    def fuerza(u, s, gap=0.0, corte=False, sig=None):
        """Qué tan natural es cortar entre la palabra u y la palabra s (10 = fin de oración).
        `sig` son las palabras que siguen a s: sirven para ver si una coma es de ENUMERACIÓN."""
        tu = u["t"]; nu, ns = palabra_cruda(tu), palabra_cruda(s["t"])
        if (nu, ns) in pegadas:
            return -12.0
        if re.search(r"[.?!…][”»]?$", tu): f = 10.0
        elif re.search(r"[:;][”»]?$", tu): f = 8.0
        elif re.search(r",[”»]?$", tu):
            siguen = [palabra_cruda(x["t"]) for x in (sig or [])[:2]]
            # «suavidad, brillo y…» es una lista; «así”, y me tiño» no: ahí la «y» arranca otra oración
            f = 3.5 if (ns not in CONJ and set(siguen[:1]) & {"y", "o", "e", "u"}) else 6.0
        elif ns in CONJ: f = 4.0
        elif ns in COPULA and nu not in NO_FINAL: f = 3.0
        elif ns in PREP: f = 3.0
        elif re.search(r"(ar|er|ir)(me|te|se|lo|la|le|nos)?$", ns) and len(ns) > 4: f = 3.0   # arranca un infinitivo
        elif ns in CLITICO or ns == "cada": f = 2.5
        elif ns in DET: f = 2.0
        elif ns in ("de", "del"): f = 1.5
        else: f = 0.0
        if not re.search(r"[.,;:?!…]", tu) and nu in NO_FINAL:
            f -= 12.0
        if gap > 0.5 and f > -5: f += 2.0
        if corte and f > -5: f += 3.0 if re.search(r"[.,;:?!…][”»]?$", tu) else 2.0   # el corte del editor
        return f
    return fuerza


def tramos_de(T, cfg):
    """Los clips de habla y de locución, en orden. Cada clip de habla es un hablante: el medio."""
    audio = T["A"]
    tramos, n = [], 0
    for pista in cfg["habla"]:
        for x in audio.get(pista, []):
            m, a, b, e = x[:4]
            tramos.append(dict(k="C%d" % n, quien=os.path.splitext(m)[0], medio=m, desde=a, hasta=b, entrada=e,
                               salida=round(e + b - a, 4), velocidad=x[4] if len(x) > 4 else 1.0)); n += 1
    n = 0
    for pista in cfg["locucion"]:
        for x in audio.get(pista, []):
            m, a, b, e = x[:4]
            tramos.append(dict(k="L%d" % n, quien="LOCUCION", medio=m, desde=a, hasta=b, entrada=e,
                               salida=round(e + b - a, 4), wav=m)); n += 1
    tramos.sort(key=lambda x: x["desde"])
    return tramos


def cuadros_ms(fps):
    """El milisegundo que cae ADENTRO de cada cuadro: redondee o trunque Premiere al leer el SRT, da el
    mismo cuadro. Con 29,97 no hay ms exactos, y redondear a centésimas corría cuadros sin aviso."""
    q = Fraction(fps).limit_denominator(1001)
    return lambda k: -(-k * 1000 * q.denominator // q.numerator)


def envolvente(tramos, largo, ruta_de):
    """La energía de la voz en la banda del habla, de a 10 ms, rearmada desde los CLIPS: la mezcla trae
    música y el piso no se mide. El umbral es 10 dB sobre el tono de sala (el percentil 15 adentro de
    los cortes)."""
    try:
        import numpy as np
        from scipy.signal import butter, sosfiltfilt
    except ImportError:
        raise SystemExit("la envolvente necesita numpy y scipy: corré subtitular.py con ~/.venvs/audio/bin/python")
    SR = 16000
    voz = np.zeros(int(largo * SR) + SR)
    for f in tramos:
        ruta = ruta_de(f["medio"])
        cmd = ["ffmpeg", "-v", "error", "-ss", f"{f['entrada']:.6f}", "-i", ruta,
               "-t", f"{f['salida'] - f['entrada']:.6f}", "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode != 0 or not r.stdout:
            raise SystemExit(f"la envolvente no pudo leer la voz de «{ruta}»: {r.stderr.decode(errors='replace').strip()[:200]}")
        seg = np.frombuffer(r.stdout, dtype=np.float32)
        a = int(round(f["desde"] * SR)); voz[a:a + len(seg)] += seg
    y = sosfiltfilt(butter(4, [300, 3400], btype="band", fs=SR, output="sos"), voz)
    n = SR // 100; m = len(y) // n
    db = 10 * np.log10((y[:m * n].reshape(m, n) ** 2).mean(1) + 1e-12)
    dentro = np.zeros(m, bool)
    for f in tramos: dentro[int(f["desde"] * 100):int(f["hasta"] * 100)] = True
    return db, np.percentile(db[dentro], 15) + 10


def fin_de_voz(env, desde, hasta):
    import numpy as np
    db, umbral = env
    i0, i1 = int(desde * 100), int(hasta * 100)
    sobre = np.where(db[i0:i1] > umbral)[0]
    return (i0 + sobre[-1] + 1) / 100 if len(sobre) else None


def cortes_reel(T):
    """Donde cambia lo que se VE: un borde tapado por un clip de una pista de arriba no cuenta, los
    bordes adentro de un nested sí. Con el primer cuadro y el último."""
    V = T["V"]
    def tapado(p, t):
        return any(int(q[1:]) > int(p[1:]) and c < t - 1e-3 and d > t + 1e-3 for q in V for c, d in V[q])
    bordes = {round(t, 3) for p, rs in V.items() for a, b in rs for t in (a, b) if not tapado(p, t)}
    bordes |= {round(t, 3) for t, p in T.get("internos", []) if not tapado(p, t)}
    return sorted(bordes)


def tiempos_reel(bloques, T, fps, env):
    """El modelo de los reels, en cuadros. Deja `in`/`out` en cada bloque y `hab`, el fin de la voz."""
    fin = T["fin"]
    cortes = cortes_reel(T)
    def cuadro(t, modo="abajo"):
        return int(math.floor(t * fps + 1e-6)) if modo == "abajo" else int(math.ceil(t * fps - 1e-6))
    for i, b in enumerate(bloques):
        b["voz_desde"] = b["ws"][0]["a"]
        sig = bloques[i + 1]["ws"][0]["a"] if i + 1 < len(bloques) else fin
        medido = fin_de_voz(env, b["ws"][-1]["a"], min(sig - 0.03, b["ws"][-1]["a"] + 2.5)) if env else None
        b["hab"] = medido if medido else b["ws"][-1]["b"]
    prev = 0.0
    for b in bloques:                                  # entradas: 40 ms antes de lo que marca Scribe
        t = b["voz_desde"] - 0.04
        cand = [c for c in cortes if t - 0.20 <= c <= b["voz_desde"] + 0.067 and c >= prev]
        b["in"] = int(round(min(cand, key=lambda c: abs(c - t)) * fps)) if cand else cuadro(t)
        prev = b["hab"]
    parpadeo = int(round(0.2 * fps))                   # menos de 0,2 s de pantalla vacía es un parpadeo
    for i, b in enumerate(bloques):                    # salidas
        sig = bloques[i + 1] if i + 1 < len(bloques) else None
        if sig and sig["voz_desde"] - b["hab"] < 0.7:
            b["out"] = sig["in"]
            continue
        cand = [c for c in cortes if b["hab"] + 0.05 <= c <= b["hab"] + 0.7]
        out = int(round(cand[0] * fps)) if cand else cuadro(b["hab"] + 0.35, "arriba")
        if sig:
            out = min(out, sig["in"])
            if sig["in"] - out < parpadeo: out = sig["in"]
        b["out"] = min(out, cuadro(fin))


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__.split("\n\n")[1])
    video = sys.argv[2]
    cfg = cargar_proyecto(sys.argv[1], video)
    T = json.load(open(cfg["timeline"], encoding="utf-8"))
    if "A" not in T:
        raise SystemExit(f"{cfg['timeline']}: le falta la clave «A» con las pistas de audio. "
                         "Se arma con herramientas/timeline_subtitulos.js o timeline_prproj.py.")
    FPS = T["fps"]
    F = 1.0 / FPS
    AJ = json.load(open(cfg["ajustes"], encoding="utf-8"))
    CAMBIOS = [tuple(x) for x in AJ.get("cambios", [])]
    AGREGADOS = [tuple(x) for x in AJ.get("agregados", [])]
    PARA_ESCUCHAR = [tuple(x) for x in AJ.get("para_escuchar", [])]
    MANUAL = AJ.get("manual", [])
    BLOQUES = AJ.get("bloques")
    fuerza = hacer_fuerza(PEGADAS_IDIOMA | cfg["pegadas"])
    if cfg["locucion"] and not cfg["guion"]:
        raise SystemExit("el proyecto declara pistas de locución pero no `locucion`: la ruta del guion con sus tiempos.")
    LINEAS = cfg["lineas"]
    if cfg["ancho"]:
        try:
            from PIL import ImageFont
        except ImportError:
            raise SystemExit("`ancho` mide con la fuente y necesita Pillow (PIL)")
        A_ = cfg["ancho"]
        fuente_px = ImageFont.truetype(os.path.expanduser(A_["fuente"]), int(A_["cuerpo"]))
        ancho, TOPE, UNIDAD = fuente_px.getlength, float(A_["px"]), "px"
    else:
        ancho, TOPE, UNIDAD = len, MAXL, "caracteres"

    # ---------------- el texto ----------------
    tramos = tramos_de(T, cfg)
    toks, huerfanas = [], []
    if cfg["por_clip"]:
        # las palabras de cada clip entero, pasadas por los cortes
        cache = {}
        for tr in tramos:
            if tr["quien"] == "LOCUCION": continue
            if abs(tr["velocidad"] - 1.0) > 1e-9:
                raise SystemExit(f"«{tr['medio']}» corre a {tr['velocidad']}x en {tr['desde']:.2f} s: las palabras "
                                 "de un clip no se proyectan sobre un clip que no corre a 1x")
            ruta = cfg["por_clip"].format(medio=tr["quien"])
            if ruta not in cache:
                if not os.path.exists(ruta):
                    raise SystemExit(f"no está la transcripción de «{tr['medio']}»: {ruta}")
                datos = json.load(open(ruta, encoding="utf-8"))
                if datos.get("motor") != cfg["motor"]:
                    raise SystemExit(f"{ruta} es de «{datos.get('motor')}» y el proyecto espera «{cfg['motor']}».")
                cache[ruta] = datos["palabras"]
            for w in cache[ruta]:
                if not str(w["texto"]).strip(): continue
                a = float(w["desde"]); b = a + float(w.get("dura") or 0)
                if tr["entrada"] - GRACIA_ENTRADA <= a < tr["salida"] - GRACIA_SALIDA:
                    toks.append(dict(t=str(w["texto"]).strip(), a=tr["desde"] + a - tr["entrada"],
                                     b=min(tr["hasta"], tr["desde"] + b - tr["entrada"]),
                                     k=tr["k"], quien=tr["quien"], medio=tr["quien"], fuente=a))
    else:
        datos = json.load(open(cfg["transcripcion"], encoding="utf-8"))
        if datos.get("motor") != cfg["motor"]:
            raise SystemExit(f"{cfg['transcripcion']} es de «{datos.get('motor')}» y el proyecto espera «{cfg['motor']}».")
        sc = [w for w in datos["palabras"] if str(w["texto"]).strip()]

        def tramo_de(t):
            for tr in tramos:
                if tr["desde"] - 0.05 <= t < tr["hasta"] - 0.04:
                    return tr
            return None

        for w in sc:
            tr = tramo_de(w["desde"])
            if tr is None:
                huerfanas.append((w["texto"], w["desde"])); continue
            if tr["quien"] == "LOCUCION":
                continue
            toks.append(dict(t=w["texto"].strip(), a=float(w["desde"]), b=float(w["desde"]) + float(w.get("dura") or 0),
                             k=tr["k"], quien=tr["quien"], medio=tr["quien"],
                             fuente=tr["entrada"] + float(w["desde"]) - tr["desde"]))
    for tr in tramos:
        if tr["quien"] != "LOCUCION": continue
        f = cfg["guion"].format(medio=os.path.splitext(tr["wav"])[0])
        for w in json.load(open(f, encoding="utf-8"))["palabras"]:
            if w["desde"] < (tr["hasta"] - tr["desde"]) - 0.03:
                toks.append(dict(t=w["texto"], a=tr["desde"] + w["desde"], b=min(tr["hasta"], tr["desde"] + w["hasta"]),
                                 k=tr["k"], quien="LOCUCION", medio=os.path.splitext(tr["wav"])[0],
                                 fuente=w["desde"]))
    toks.sort(key=lambda x: x["a"])

    def ancla(t0):
        """Dónde busca un cambio: un segundo de la secuencia, o ["medio", segundo] del clip."""
        if isinstance(t0, (list, tuple)):
            medio, s = str(t0[0]), float(t0[1])
            return lambda x: x["medio"].startswith(medio) and abs(x["fuente"] - s) <= 3.0
        return lambda x: abs(x["a"] - t0) <= 3.0

    def donde(t0):
        return f"{t0[0]} @ {float(t0[1]):.2f} s" if isinstance(t0, (list, tuple)) else tc(t0)[:8]

    aplicados, obsoletos = [], []
    for t0, de, a, por in CAMBIOS:
        dn = [palabra(x) for x in de.split()]
        cerca = ancla(t0)
        if isinstance(t0, (list, tuple)) and not any(cerca(x) for x in toks):
            # anclado al clip y sin nada de ese clip a ±3 s: el editor sacó ese momento del corte
            obsoletos.append((t0, de, a, por)); continue
        hits = [i for i in range(len(toks) - len(dn) + 1)
                if cerca(toks[i]) and [palabra(toks[i + j]["t"]) for j in range(len(dn))] == dn]
        if len(hits) != 1:
            raise SystemExit(f"CAMBIO que no encontré una sola vez ({len(hits)}): {t0} «{de}»")
        i = hits[0]
        viejos = toks[i:i + len(dn)]
        nuevas = a.split()
        if not nuevas:                                 # un cambio a "" saca la palabra
            del toks[i:i + len(dn)]
            aplicados.append((t0, de, a, por)); continue
        # conserva las comillas de apertura que traía el original
        if viejos[0]["t"].startswith('"') and not nuevas[0].startswith('"'): nuevas[0] = '"' + nuevas[0]
        t_a, t_b = viejos[0]["a"], viejos[-1]["b"]
        pesos = [max(1, len(x)) for x in nuevas]
        acc, nuevos = t_a, []
        for x, p in zip(nuevas, pesos):
            d = (t_b - t_a) * p / sum(pesos)
            nuevos.append(dict(t=x, a=round(acc, 3), b=round(acc + d, 3), k=viejos[0]["k"], quien=viejos[0]["quien"],
                               medio=viejos[0]["medio"], fuente=viejos[0]["fuente"], cambio=por))
            acc += d
        if len(nuevos) == 1 and len(viejos) == 1:     # una palabra por otra: los tiempos, los del motor
            nuevos[0].update(a=viejos[0]["a"], b=viejos[0]["b"])
        toks[i:i + len(dn)] = nuevos
        aplicados.append((t0, de, a, por))

    for medio, fa, fb, texto, por in AGREGADOS:
        dentro = [tr for tr in tramos if tr["quien"] != "LOCUCION" and tr["quien"].startswith(str(medio))
                  and tr["entrada"] <= fa < tr["salida"]]
        if not dentro:
            obsoletos.append(([medio, fa], "", texto, por)); continue
        if len(dentro) != 1:
            raise SystemExit(f"AGREGADO que cae en {len(dentro)} cortes, el mismo momento usado dos veces: {medio} {fa} «{texto}»")
        tr = dentro[0]
        toks.append(dict(t=texto, a=tr["desde"] + fa - tr["entrada"], b=tr["desde"] + fb - tr["entrada"],
                         k=tr["k"], quien=tr["quien"], medio=tr["quien"], fuente=fa, cambio=por))
        toks.sort(key=lambda x: x["a"])
        aplicados.append(([medio, fa], "", texto, por))

    if obsoletos:   # antes de dividir: si la división rebota, esto ya se vio
        print(f"OJO: {len(obsoletos)} cambios ya no aplican, ese momento del clip no quedó en el corte: "
              + ", ".join(f"«{de or a}» en {t0[0]} @ {float(t0[1]):.2f} s" for t0, de, a, por in obsoletos))

    # muletillas sueltas que no estén en la lista (red de seguridad)
    sueltas = [x for x in toks if palabra(x["t"]) in MULETILLAS]
    toks = [x for x in toks if palabra(x["t"]) not in MULETILLAS]

    # comillas tipográficas
    for x in toks:
        if x["t"].startswith('"'): x["t"] = "“" + x["t"][1:]
        x["t"] = re.sub(r'"([,.;:!?]*)$', r"”\1", x["t"])

    # ---------------- turnos: un hablante sin pausa larga ----------------
    turnos, cur = [], []
    for x in toks:
        if cur and (x["quien"] != cur[-1]["quien"] or x["a"] - cur[-1]["b"] > AJ.get("pausa_turno", 1.5)):
            turnos.append(cur); cur = []
        cur.append(x)
    if cur: turnos.append(cur)

    if os.environ.get("DUMP_TURNOS"):
        for ws in turnos:
            print(f'{ws[0]["a"]:7.2f} {ws[0]["quien"][:12]:12s} | ' + " ".join(w["t"] for w in ws))
        raise SystemExit(0)

    def partir_lineas(ws):
        """El mejor salto de línea de un bloque, o None si no entra en las líneas del estilo."""
        txt = " ".join(w["t"] for w in ws)
        if ancho(txt) <= TOPE:
            return [txt], 0.0
        if LINEAS < 2:
            return None, float("inf")
        best = None
        for p in range(1, len(ws)):
            l1, l2 = " ".join(w["t"] for w in ws[:p]), " ".join(w["t"] for w in ws[p:])
            if ancho(l1) > TOPE or ancho(l2) > TOPE: continue
            c = (10 - fuerza(ws[p - 1], ws[p], sig=ws[p + 1:])) * 2.0 + abs(len(l1) - len(l2)) * 0.15
            if len(l1) > len(l2) + 10: c += 2            # mejor la de abajo más larga
            if min(len(l1), len(l2)) < 10: c += 8          # una línea de una sola palabra no
            if best is None or c < best[1]: best = ([l1, l2], c)
        return best if best else (None, float("inf"))

    def costo_corte(ws, j):
        """Lo que cuesta terminar un bloque entre ws[j-1] y ws[j]."""
        if j >= len(ws): return 0.0
        u, s_ = ws[j - 1], ws[j]
        return (10 - fuerza(u, s_, s_["a"] - u["b"], s_["k"] != u["k"], ws[j + 1:])) * 2.5

    def costo_bloque(ws, i, j, n):
        seg = ws[i:j]
        txt = " ".join(w["t"] for w in seg)
        if ancho(txt) > TOPE * min(LINEAS, 2) and j - i > 1: return float("inf"), None
        lineas, cl = partir_lineas(seg)
        if lineas is None: return float("inf"), None
        dur = (seg[-1]["b"] - seg[0]["a"]) + 0.3
        c = 4.0 + cl * 1.0                           # cada bloque cuesta algo: no fragmentar de más
        if dur > 7.0: c += 40 + (dur - 7.0) * 20
        if dur < 1.0: c += (1.0 - dur) * 15
        cps = len(txt) / max(dur, 0.6)
        if cps > 20: c += (cps - 20) * 1.2             # un testimonio rápido se lee igual: manda la frase
        if cps > 26: c += 10
        completo = (i == 0 or fuerza(ws[i - 1], ws[i]) >= 6) and (j == n or fuerza(ws[j - 1], ws[j]) >= 6)
        if len(txt) < 20 and not completo: c += 8
        # una oración que ARRANCA adentro del bloque y sigue en el próximo: el bloque mezcla dos oraciones
        internos = [x for x in range(i, j - 1) if re.search(r"[.?!…][”»]?$", ws[x]["t"])]
        if internos and j < n and not re.search(r"[.?!…][”»]?$", ws[j - 1]["t"]):
            c += 14
        c += costo_corte(ws, j)
        return c, lineas

    def sin_espacios(x): return re.sub(r"\s+", "", x.replace(" / ", " "))

    def lineas_de(cue):
        return [x.strip() for x in cue.split(" / ")]

    def fuera_de_estilo(cue):
        """Por qué un bloque escrito a mano no entra en las líneas del estilo, o None si entra."""
        lineas = lineas_de(cue)
        if len(lineas) <= LINEAS and all(ancho(x) <= TOPE for x in lineas):
            return None
        return f"«{cue}» (" + ", ".join(f"{ancho(x):.0f}" for x in lineas) + ")"

    def aplicar_manual(ws):
        """Si el turno tiene división a mano, la devuelve como [(palabras, líneas)]; si no, None."""
        texto_turno = sin_espacios(" ".join(w["t"] for w in ws))
        for lista in MANUAL:
            if sin_espacios(" ".join(lista)) != texto_turno:
                continue
            out, k = [], 0
            for cue in lista:
                n = len(cue.replace(" / ", " ").split())
                seg = ws[k:k + n]
                if sin_espacios(" ".join(w["t"] for w in seg)) != sin_espacios(cue):
                    raise SystemExit(f"la división a mano no calza: «{cue}» contra «{' '.join(w['t'] for w in seg)}»")
                if fuera_de_estilo(cue):
                    raise SystemExit(f"la división a mano se pasa de {LINEAS} x {TOPE:g} {UNIDAD}: {fuera_de_estilo(cue)}")
                out.append((seg, lineas_de(cue))); k += n
            return out
        return None

    bloques, manuales = [], 0
    if BLOQUES is not None:
        # el video entero dividido a mano: palabra por palabra contra lo que se oye, ya corregido
        dichas = [p for cue in BLOQUES for p in cue.replace(" / ", " ").split()]
        for i, (d, w) in enumerate(zip(dichas, toks)):
            if d != w["t"]:
                raise SystemExit(f"la división dice «{d}» y se oye «{w['t']}» (palabra {i + 1}, {w['a']:.2f} s)")
        if len(dichas) != len(toks):
            sobra = toks[len(dichas)] if len(toks) > len(dichas) else None
            raise SystemExit(f"la división tiene {len(dichas)} palabras y se oyen {len(toks)}"
                             + (f": falta desde «{sobra['t']}» ({sobra['a']:.2f} s)" if sobra else ""))
        grandes = [x for x in map(fuera_de_estilo, BLOQUES) if x]
        if grandes:
            raise SystemExit(f"bloques que se pasan de {LINEAS} x {TOPE:g} {UNIDAD}: " + "; ".join(grandes))
        k = 0
        for cue in BLOQUES:
            n = len(cue.replace(" / ", " ").split())
            bloques.append(dict(ws=toks[k:k + n], lineas=lineas_de(cue), quien=toks[k]["quien"], manual=True)); k += n
        manuales = len(bloques)
    for ws in (turnos if BLOQUES is None else []):
        man = aplicar_manual(ws)
        if man:
            manuales += 1
            for seg, lin in man:
                bloques.append(dict(ws=seg, lineas=lin, quien=seg[0]["quien"], manual=True))
            continue
        n = len(ws)
        best = [0.0] + [float("inf")] * n
        desde = [None] * (n + 1)
        for j in range(1, n + 1):
            for i in range(max(0, j - 30), j):
                if best[i] == float("inf"): continue
                c, lin = costo_bloque(ws, i, j, n)
                if best[i] + c < best[j]:
                    best[j], desde[j] = best[i] + c, (i, lin)
        if best[n] == float("inf"):
            raise SystemExit(f"un turno no se puede dividir en {LINEAS} x {TOPE:g} {UNIDAD}: «{' '.join(w['t'] for w in ws)[:80]}»")
        j, partes = n, []
        while j > 0:
            i, lin = desde[j]
            partes.append((ws[i:j], lin)); j = i
        for seg, lin in reversed(partes):
            bloques.append(dict(ws=seg, lineas=lin, quien=seg[0]["quien"]))

    # ---------------- tiempos, en cuadros y con los cortes de plano ----------------
    if cfg["tiempos"] == "reel":
        env = None
        if cfg["envolvente"]:
            patron = cfg["envolvente"].get("medios") if isinstance(cfg["envolvente"], dict) else None
            rutas = T.get("rutas", {})
            def ruta_de(medio):
                if patron: return os.path.expanduser(patron.format(medio=medio))
                if medio in rutas: return rutas[medio]
                raise SystemExit(f"la envolvente no sabe dónde está «{medio}»: la línea de tiempo no trae su "
                                 "ruta (sí la de timeline_prproj.py) y el proyecto no dice `envolvente.medios`")
            env = envolvente([tr for tr in tramos if tr["quien"] != "LOCUCION"], T["fin"], ruta_de)
        tiempos_reel(bloques, T, FPS, env)
        for bl in bloques:
            bl["ent"], bl["sal"] = bl["in"] / FPS, bl["out"] / FPS
        corto, rapido = 0.6, 25
    else:
        cortes = sorted({round(x, 2) for pista in T["V"].values() for a, b in pista for x in (a, b)} - {0.0, T["fin"]})
        def cuadro(t, modo="cerca"):
            q = t / F
            return (int(q + 1e-6) if modo == "abajo" else int(q + 0.999999) if modo == "arriba" else int(round(q))) * F

        for i, bl in enumerate(bloques):
            bl["ent"] = cuadro(bl["ws"][0]["a"], "abajo")
            bl["hab"] = bl["ws"][-1]["b"]                 # fin del habla
            bl["sal"] = cuadro(bl["hab"] + 0.30, "arriba")
        for i, bl in enumerate(bloques):
            sig = bloques[i + 1]["ent"] if i + 1 < len(bloques) else T["fin"]
            # entrada con el corte de plano si el habla arranca apenas después
            ant = bloques[i - 1]["sal"] if i else 0.0
            for c in cortes:
                if 0 < bl["ent"] - c <= 0.32 and c >= ant:
                    bl["ent"] = c
            # salida: con el corte de plano si cae cerca y el habla ya terminó
            for c in cortes:
                if bl["hab"] + 0.04 <= c and abs(bl["sal"] - c) <= 0.36 and c <= sig:
                    bl["sal"] = c
            bl["sal"] = min(bl["sal"], sig)
            if bl["sal"] - bl["ent"] < 0.8:
                bl["sal"] = min(sig, bl["ent"] + 0.8)
            if 0 < sig - bl["sal"] < 0.3:                  # sin parpadeo entre dos bloques
                bl["sal"] = sig
        for bl in bloques:                              # al cuadro: un corte de plano redondeado no es un cuadro a 29,97
            bl["in"], bl["out"] = int(round(bl["ent"] * FPS)), int(round(bl["sal"] * FPS))
            bl["ent"], bl["sal"] = round(bl["ent"], 2), round(bl["sal"], 2)
        corto, rapido = 0.8, 20

    # ---------------- SRT y lista para revisar ----------------
    def tc(t):
        ms = int(round(t * 1000))
        return "%02d:%02d:%02d,%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)

    ms_de = cuadros_ms(FPS)
    def tc_cuadro(k):
        ms = ms_de(k)
        return "%02d:%02d:%02d,%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)

    os.makedirs(cfg["salida"], exist_ok=True)
    with open(os.path.join(cfg["salida"], f"{video} - subtitulos.srt"), "w", encoding="utf-8") as f:
        for n, bl in enumerate(bloques, 1):
            f.write(f"{n}\n{tc_cuadro(bl['in'])} --> {tc_cuadro(bl['out'])}\n" + "\n".join(bl["lineas"]) + "\n\n")

    avisos = []
    for n, bl in enumerate(bloques, 1):
        txt = " ".join(bl["lineas"]); d = bl["sal"] - bl["ent"]
        cps = len(txt) / max(d, 0.01)
        if d < corto: avisos.append(f"#{n} dura {d:.2f} s")
        if cps > rapido: avisos.append(f"#{n} {cps:.0f} caracteres por segundo")
        # pegado al siguiente en el reel, lo que queda de la voz ya lo cubre el que entra
        pegado = cfg["tiempos"] == "reel" and n < len(bloques) and bloques[n]["in"] == bl["out"]
        if bl["sal"] < bl["hab"] - 0.02 and not pegado:
            avisos.append(f"#{n} se va antes de que termine el habla ({bl['sal']:.2f} < {bl['hab']:.2f})")

    with open(os.path.join(cfg["salida"], f"{video} - revisar.txt"), "w", encoding="utf-8") as f:
        f.write("PARA ESCUCHAR\n")
        for t, q in PARA_ESCUCHAR:
            f.write(f"  {tc(t)[:8]}  {q}\n")
        f.write(f"\nCAMBIOS SOBRE LO QUE OYÓ {cfg['motor'].upper()}\n")
        for t0, de, a, por in aplicados:
            if not de: f.write(f"  {donde(t0)}  + «{a}» · {por}\n")
            else: f.write(f"  {donde(t0)}  «{de}» → «{a or '(sale)'}» · {por}\n")
        if obsoletos:
            f.write("\nCAMBIOS QUE YA NO APLICAN: ese momento del clip no quedó en el corte\n")
            for t0, de, a, por in obsoletos:
                f.write(f"  {donde(t0)}  " + (f"+ «{a}»" if not de else f"«{de}» → «{a or '(sale)'}»") + f" · {por}\n")
        if sueltas:
            f.write("\nMULETILLAS SACADAS FUERA DE LA LISTA: " + ", ".join(f'{x["t"]}@{x["a"]:.1f}' for x in sueltas) + "\n")
        if avisos:
            f.write("\nAVISOS DE TIEMPO\n" + "".join(f"  {x}\n" for x in avisos))

    print(f"turnos divididos a mano: {manuales} de {len(MANUAL)} · turnos en total: {len(turnos)}" if BLOQUES is None
          else f"el video entero dividido a mano: {len(bloques)} bloques")
    print(f"{len(bloques)} subtítulos · {len(aplicados)} cambios · {len(sueltas)} muletillas sueltas · "
          f"palabras de la transcripción fuera de todo clip: {huerfanas}")
    for n, bl in enumerate(bloques, 1):
        print(f"{n:3d} {bl['ent']:7.2f}-{bl['sal']:7.2f} {'M' if bl.get('manual') else ' '} {bl['quien'][:10]:10s} | " + " / ".join(bl["lineas"]))
    print("\nAVISOS:", avisos or "ninguno")


if __name__ == "__main__":
    main()
