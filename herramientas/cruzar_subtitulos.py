#!/usr/bin/env python3
"""Cruza las transcripciones de un video y arma la lista de lo que hay que REVISAR antes de subtitular.

    python3 herramientas/cruzar_subtitulos.py <proyecto.json> "<video>"

Es el paso de antes de `subtitular.py`, con el mismo proyecto. Ver `herramientas/SUBTITULOS.md`.

LA COLUMNA es la transcripción de la MEZCLA exportada de la secuencia: da el orden, los tiempos y
qué palabras quedaron adentro de cada corte. Es Scribe si está; si no, la de Premiere sobre la mezcla.

Contra ella se votan las transcripciones del MEDIO ENTERO de cada clip —la de Premiere y la de
Whisper con glosario—, que se hicieron con todo el contexto. Sus tiempos vienen corridos (medido: una
mediana de 0,26 s y hasta 1,4 s entre palabras vecinas), así que no sirven para decidir los bordes:
se usan SOLO para el texto, emparejadas palabra por palabra con la columna.

**Y el voto NO es independiente**, que es lo que más importa de esta herramienta: el clip y Whisper
salen del mismo medio y fallan JUNTOS. Medido en un video de 21 cambios: unos diez eran errores del
cruce, y la frase de Scribe tenía sentido. Por eso `subtitular.py` parte de Scribe y no de esto: lo
que sale acá es la LISTA de lo que discrepa, para revisar uno por uno —si la frase de Scribe tiene
sentido, gana Scribe—, y lo que resulte cierto va a mano a `cambios` de los ajustes. Y ojo con la
cabeza de cada clip: el cruce suele meterle la última palabra del clip anterior.

Entre dos palabras en las que coinciden la columna y el clip, lo que haya en el medio se vota:
  clip == whisper          -> clip
  columna == whisper       -> columna
  columna == otra mezcla   -> columna (con Scribe, la otra mezcla es la de Premiere)
  si no                    -> clip, y a la lista de lo que hay que ESCUCHAR

EL PROYECTO es el de `subtitular.py`, con tres claves más (las rutas, relativas a él):

    "mezcla":        "premiere/{video} - audio.audio.json",   Premiere sobre la mezcla
    "medio_premiere": "../MATERIAL/*/{base}.premiere.json",    la del medio entero de cada clip
    "medio_whisper":  "../TRANSCRIPCIONES/* — {base}.json",    `audio.js --motor whisper` del medio

`{base}` es el nombre del medio del clip sin la extensión, y el patrón admite `*`: tiene que
encontrar UN archivo por medio.

Escribe `<video> - texto.json` en la salida y lista en pantalla, clip por clip, el texto elegido y
los tramos SIN MAYORÍA.
"""
import glob, json, os, re, statistics as st, sys, unicodedata

NUM = {"0": "cero", "1": "uno", "2": "dos", "3": "tres", "4": "cuatro", "5": "cinco", "6": "seis",
       "7": "siete", "8": "ocho", "9": "nueve", "10": "diez", "15": "quince", "20": "veinte",
       "30": "treinta", "35": "treintaycinco"}


def norm(s):
    s = unicodedata.normalize("NFD", str(s).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]", "", s)
    return NUM.get(s, s)


def lcs(a, b):
    n, m = len(a), len(b)
    Lm = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            Lm[i][j] = Lm[i + 1][j + 1] + 1 if a[i]["n"] and a[i]["n"] == b[j]["n"] else max(Lm[i + 1][j], Lm[i][j + 1])
    out, i, j = [], 0, 0
    while i < n and j < m:
        if a[i]["n"] and a[i]["n"] == b[j]["n"]:
            out.append((i, j)); i += 1; j += 1
        elif Lm[i + 1][j] >= Lm[i][j + 1]:
            i += 1
        else:
            j += 1
    return out


def tok(t, a, b=None, **k):
    d = {"t": str(t).strip(), "n": norm(t), "a": float(a), "b": float(b if b is not None else a)}
    d.update(k)
    return d


def uno(patron, que):
    hallados = glob.glob(patron)
    if len(hallados) != 1:
        raise SystemExit(f"{que}: se esperaba UN archivo para «{patron}» y hay {len(hallados)}")
    return hallados[0]


def de_premiere(f):
    ws = [w for s in json.load(open(f, encoding="utf-8"))["segments"] for w in s["words"] if w.get("type", "word") == "word"]
    return [tok(w["text"], w["start"], w["start"] + w["duration"]) for w in ws]


def de_audio_json(f):
    return [tok(p["texto"], p["desde"], p["desde"] + (p.get("dura") or 0), c=p.get("confianza"))
            for p in json.load(open(f, encoding="utf-8"))["palabras"] if str(p["texto"]).strip()]


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__.split("\n\n")[1])
    video = sys.argv[2]
    ruta = sys.argv[1]
    P = json.load(open(ruta, encoding="utf-8"))
    base = os.path.dirname(os.path.abspath(ruta))
    carpeta = os.path.join(base, P.get("carpeta", "."))
    salida = os.path.join(base, P.get("salida", P.get("carpeta", ".")))
    en = lambda clave, defecto: os.path.join(carpeta, P.get(clave, defecto).format(video=video))
    T = json.load(open(en("timeline", "{video} - timeline.json"), encoding="utf-8"))
    for clave in ("mezcla", "medio_premiere", "medio_whisper"):
        if not P.get(clave):
            raise SystemExit(f"al proyecto le falta «{clave}»: ver la cabecera de esta herramienta")
    guion = os.path.join(base, P["locucion"]) if P.get("locucion") else None
    medio_premiere = lambda m: de_premiere(uno(os.path.join(base, P["medio_premiere"].format(base=os.path.splitext(m)[0])), m))
    medio_whisper = lambda m: de_audio_json(uno(os.path.join(base, P["medio_whisper"].format(base=os.path.splitext(m)[0])), m))

    MEZCLA_PR = de_audio_json(en("mezcla", ""))
    SCRIBE = None
    f_sc = en("transcripcion", "{video} - audio.audio.json")
    if os.path.exists(f_sc) and json.load(open(f_sc, encoding="utf-8")).get("motor") == "scribe":
        SCRIBE = de_audio_json(f_sc)
    COLUMNA, OTRA = (SCRIBE, MEZCLA_PR) if SCRIBE else (MEZCLA_PR, None)
    NCOL = "scribe" if SCRIBE else "mezcla"

    pistas = P.get("pistas", {})
    tramos, n = [], 0
    for pista in pistas.get("habla", ["A1"]):
        for m, a, b, e in T["A"].get(pista, []):
            tramos.append(dict(k="C%d" % n, quien=m, desde=a, hasta=b, ent=e)); n += 1
    n = 0
    for pista in pistas.get("locucion", []):
        for m, a, b, e in T["A"].get(pista, []):
            tramos.append(dict(k="L%d" % n, quien="LOCUCION", desde=a, hasta=b, ent=e, wav=m)); n += 1
    tramos.sort(key=lambda x: x["desde"])

    def del_tramo(ws, tr):
        return [w for w in ws if tr["desde"] - 0.05 <= w["a"] < tr["hasta"] - 0.04]

    def ventana(src, tr, antes=3.0, despues=3.0):
        sal = tr["ent"] + (tr["hasta"] - tr["desde"])
        return [dict(w, s=tr["desde"] + (w["a"] - tr["ent"])) for w in src if tr["ent"] - antes <= w["a"] <= sal + despues]

    def anclar(col, win):
        """Empareja la columna con la ventana del clip. Los tiempos del clip son RUIDOSOS, así que no se
        filtra con un umbral fijo: primero un LCS común estima el corrimiento de cada zona, y después un
        LCS PESADO prefiere, entre dos palabras iguales, la que cae más cerca de ese corrimiento. Es lo
        que evita anclar en la primera de dos "ahí empieza" cuando la columna oyó una sola."""
        p = lcs(col, win)
        if not p: return p
        offs = [(j, col[i]["a"] - win[j]["s"]) for i, j in p]
        def ref(j):
            cerca = [o for jj, o in offs if abs(jj - j) <= 8] or [o for _, o in offs]
            return st.median(cerca)
        n, m = len(col), len(win)
        R = [ref(j) for j in range(m)]
        D = [[0.0] * (m + 1) for _ in range(n + 1)]
        for i in range(n - 1, -1, -1):
            for j in range(m - 1, -1, -1):
                best = max(D[i + 1][j], D[i][j + 1])
                if col[i]["n"] and col[i]["n"] == win[j]["n"]:
                    dev = abs((col[i]["a"] - win[j]["s"]) - R[j])
                    if dev <= 2.5:
                        best = max(best, D[i + 1][j + 1] + 1.0 - 0.25 * min(dev, 3.2))
                D[i][j] = best
        out, i, j = [], 0, 0
        while i < n and j < m:
            if col[i]["n"] and col[i]["n"] == win[j]["n"]:
                dev = abs((col[i]["a"] - win[j]["s"]) - R[j])
                if dev <= 2.5 and abs(D[i][j] - (D[i + 1][j + 1] + 1.0 - 0.25 * min(dev, 3.2))) < 1e-9:
                    out.append((i, j)); i += 1; j += 1; continue
            if D[i + 1][j] >= D[i][j + 1]: i += 1
            else: j += 1
        return out

    def entre(al, lo, hi, o):
        """Lo de `o` que queda entre las posiciones de la referencia `lo` y `hi` (exclusivas), usando
        el vecino alineado más cercano de cada lado."""
        izq = [r for r in al if r <= lo]
        der = [r for r in al if r >= hi]
        jl = al[max(izq)] + 1 if izq else 0
        jh = al[min(der)] if der else len(o)
        return o[jl:jh] if jh >= jl else []

    def junto(ws): return "".join(w["n"] for w in ws)
    def texto(ws): return " ".join(w["t"] for w in ws)

    def repartir(ws, t0, t1):
        """Tiempos para palabras que la columna no tiene: parejos entre sus vecinos."""
        n = len(ws)
        for i, w in enumerate(ws):
            w["a"] = round(t0 + (t1 - t0) * i / max(1, n), 3)
            w["b"] = round(t0 + (t1 - t0) * (i + 1) / max(1, n), 3)
        return ws

    salida_ws, dudas = [], []
    for tr in tramos:
        if tr["quien"] == "LOCUCION":
            if not guion:
                continue
            f = guion.format(medio=os.path.splitext(tr["wav"])[0])
            for w in json.load(open(f, encoding="utf-8"))["palabras"]:
                if w["desde"] < (tr["hasta"] - tr["desde"]) - 0.03:
                    salida_ws.append(dict(tok(w["texto"], tr["desde"] + w["desde"], min(tr["hasta"], tr["desde"] + w["hasta"])),
                                          k=tr["k"], quien="LOCUCION", voto="guion"))
            continue

        col = del_tramo(COLUMNA, tr)
        otra = del_tramo(OTRA, tr) if OTRA else []
        Pm = ventana(medio_premiere(tr["quien"]), tr)
        W = ventana(medio_whisper(tr["quien"]), tr)
        aCP = dict(anclar(col, Pm))                    # columna -> clip
        aPW = dict(lcs(Pm, W))                         # clip -> whisper (misma fuente, tiempos parecidos)
        aCO = dict(lcs(col, otra)) if otra else {}     # columna -> la otra mezcla
        anc = sorted(aCP.items())
        quien = os.path.splitext(tr["quien"])[0]

        def votar(c_seg, p_seg, w_seg, o_seg, t0, t1, borde):
            """Devuelve las palabras elegidas para un tramo entre anclajes."""
            jc, jp, jw, jo = junto(c_seg), junto(p_seg), junto(w_seg), junto(o_seg)
            alt = {NCOL: texto(c_seg), "clip": texto(p_seg), "whisper": texto(w_seg)}
            if otra: alt["mezcla" if SCRIBE else "otra"] = texto(o_seg)
            if not c_seg and not p_seg: return []
            if jp and jp == jc:
                return [dict(w, voto="todas") for w in c_seg]
            # las dos que oyeron la MEZCLA coinciden: es lo que suena en el corte
            if c_seg and otra and jc == jo:
                return [dict(w, voto=NCOL + "+mezcla") for w in c_seg]
            if c_seg and jc == jw:
                return [dict(w, voto=NCOL + "+whisper") for w in c_seg]
            # las dos del medio entero coinciden contra la columna: su texto, con los tiempos de la columna
            if p_seg and jp == jw and c_seg:
                ws = [dict(x, voto="clip+whisper") for x in p_seg]
                return repartir(ws, t0, t1) if len(ws) != len(c_seg) else [dict(x, a=c["a"], b=c["b"]) for x, c in zip(ws, c_seg)]
            if not c_seg:
                # palabras que la columna NO oyó: sólo se agregan si otras dos las tienen
                if p_seg and jp == jw and (not otra or jp == jo):
                    return repartir([dict(x, voto="clip+whisper+mezcla") for x in p_seg], t0, t1)
                dudas.append(dict(desde=round(t0, 2), quien=quien, borde=borde, eligio="no se agrega", **alt))
                return []
            # sin mayoría: con Scribe gana la columna; con la mezcla de Premiere, el clip
            elegido = c_seg if SCRIBE else (p_seg if p_seg else c_seg)
            dudas.append(dict(desde=round(t0, 2), quien=quien, borde=borde,
                              eligio=NCOL if elegido is c_seg else "clip", **alt))
            ws = [dict(x, voto="sin mayoria", dudoso=True, alt=alt) for x in elegido]
            if elegido is c_seg:
                return ws
            if p_seg and len(ws) == len(c_seg):
                return [dict(x, a=c["a"], b=c["b"]) for x, c in zip(ws, c_seg)]
            return repartir(ws, t0, t1)

        out = []
        if not anc:
            # un pedacito sin ningún anclaje (p. ej. un clip de 0,4 s): la columna, votada con whisper
            wv = [w for w in W if tr["desde"] - 0.4 <= w["s"] < tr["hasta"] + 0.4]
            out += votar(col, [], wv, otra, tr["desde"], tr["hasta"], "sin anclaje")
        else:
            # cabeza: las palabras de la columna antes del primer anclaje, contra las ÚLTIMAS k del clip
            i0, j0 = anc[0]
            k = i0
            p_cab = Pm[max(0, j0 - k):j0] if k else []
            w_cab = entre(aPW, j0 - k - 1, j0, W) if k else []
            o_cab = [o for o in otra if o["a"] < col[i0]["a"] - 0.02 and o["a"] >= tr["desde"] - 0.05] if otra else []
            out += votar(col[:i0], p_cab, w_cab, o_cab, col[0]["a"] if i0 else tr["desde"], col[i0]["a"], "cabeza")
            for (ia, ja), (ib, jb) in zip(anc, anc[1:] + [(None, None)]):
                out.append(dict(col[ia], t=Pm[ja]["t"], voto="todas"))   # el anclaje, con la grafía del clip
                if ib is None:
                    break
                c_seg, p_seg = col[ia + 1:ib], Pm[ja + 1:jb]
                w_seg = entre(aPW, ja, jb, W)
                o_seg = entre(aCO, ia, ib, otra) if otra else []
                out += votar(c_seg, p_seg, w_seg, o_seg, col[ia]["b"], col[ib]["a"], "medio")
            # cola: lo de la columna después del último anclaje, contra las PRIMERAS k del clip
            il, jl = anc[-1]
            k = len(col) - 1 - il
            p_col = Pm[jl + 1:jl + 1 + k] if k else []
            w_col = entre(aPW, jl, jl + k + 1, W) if k else []
            o_col = [o for o in otra if o["a"] > col[il]["a"] + 0.02] if otra else []
            out += votar(col[il + 1:], p_col, w_col, o_col, col[il]["b"], tr["hasta"], "cola")
        for w in out:
            w.update(k=tr["k"], quien=tr["quien"])
        salida_ws += out

    os.makedirs(salida, exist_ok=True)
    json.dump({"columna": NCOL, "palabras": salida_ws, "dudas": dudas, "tramos": tramos},
              open(os.path.join(salida, f"{video} - texto.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"columna: {NCOL} · palabras: {len(salida_ws)} · tramos sin mayoría: {len(dudas)}")
    for tr in tramos:
        ws = [w for w in salida_ws if w["k"] == tr["k"]]
        if tr["quien"] != "LOCUCION":
            print(f'{tr["desde"]:6.2f}-{tr["hasta"]:6.2f} {tr["quien"][:20]:20s} ' +
                  " ".join(w["t"] + ("⁇" if w.get("dudoso") else "") for w in ws))
    print("\nSIN MAYORÍA (para escuchar):")
    for d in dudas:
        resto = " · ".join(f"{k} «{v}»" for k, v in d.items() if k not in ("desde", "quien", "borde", "eligio"))
        print(f'  {d["desde"]:7.2f} {d["quien"][:14]:14s} [{d["borde"]}] {resto} → {d["eligio"]}')


if __name__ == "__main__":
    main()
