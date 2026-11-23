"""
02_benchmark_comparativo.py - Análisis comparativo ACID (PostgreSQL) vs BASE (MongoDB).
Grupo 6 - Bases de Datos II (G101)

Carga EXACTAMENTE los mismos eventos en 5 destinos y ejecuta las mismas operaciones:
  mongo        -> MongoDB, colección normal eventos_telemetria
  mongo_ts     -> MongoDB, colección time series eventos_telemetria_ts
  pg_columnas  -> PostgreSQL, tabla con columnas fijas + tabla hija de alertas
  pg_jsonb     -> PostgreSQL, documento JSONB
  pg_copy      -> PostgreSQL columnas, pero cargado con COPY (optimización)

Operaciones medidas:
  O1 ingesta masiva            O2 consulta puntual (paciente + ventana de tiempo)
  O3 agregación clínica        O4 alertas críticas + identidad (consulta híbrida)
  O5 flexibilidad (nuevo tipo de sensor)   O6 transacción multi-registro
  O7 integridad referencial    O8 almacenamiento

Uso (desde la carpeta raíz de la tarea):
  py scripts/02_benchmark_comparativo.py            (200.000 eventos)
  py scripts/02_benchmark_comparativo.py --n 50000  (prueba rápida)
Resultados: resultados/metricas.json, resultados/metricas_resumen.csv, resultados/explain_*.txt
"""
import argparse
import csv
import ctypes
import json
import platform
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from psycopg.types.json import Jsonb

from comun import (a_timeseries, conectar_mongo, conectar_pg, generar_eventos,
                   generar_teleconsultas, leer_asignaciones)

RAIZ = Path(__file__).resolve().parent.parent
RES = RAIZ / "resultados"
LOTE = 1000

# Parámetros de las consultas (iguales para todos los motores)
Q_PACIENTE = "PAC003"
Q_DESDE = datetime(2026, 11, 21, 18, 0, tzinfo=timezone.utc)
Q_HASTA = datetime(2026, 11, 22, 0, 0, tzinfo=timezone.utc)
Q_ALERTAS_DESDE = datetime(2026, 11, 21, 0, 0, tzinfo=timezone.utc)

COLS = ["evento_id", "paciente_id", "hospitalizacion_id", "dispositivo_id", "tipo_dispositivo", "ts",
        "fc_lpm", "spo2_pct", "pa_sistolica", "pa_diastolica", "fr_rpm", "temperatura_c",
        "pasos", "temp_piel_c", "calidad_sueno", "medicamento", "velocidad_ml_h", "volumen_restante_ml",
        "glucosa_mg_dl", "momento_toma", "bateria_pct", "firmware", "red"]
LECT = COLS[6:20]


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def log(msg):
    print(msg, flush=True)


def medir(fn, reps, calentamiento=2):
    """Ejecuta fn varias veces y devuelve estadísticas en milisegundos (con caché caliente)."""
    for _ in range(calentamiento):
        fn()
    tiempos, filas = [], None
    for _ in range(reps):
        t0 = time.perf_counter()
        filas = fn()
        tiempos.append((time.perf_counter() - t0) * 1000)
    tiempos.sort()
    return {"mediana_ms": round(statistics.median(tiempos), 3),
            "min_ms": round(tiempos[0], 3), "max_ms": round(tiempos[-1], 3),
            "p95_ms": round(tiempos[max(0, int(len(tiempos) * 0.95) - 1)], 3),
            "reps": reps, "filas": filas}


def correr_psql(archivo):
    subprocess.run(["psql", "-U", "postgres", "-h", "localhost", "-w", "-q", "-v", "ON_ERROR_STOP=1",
                    "-d", "hce_core_grupo_6", "-f", str(RAIZ / archivo)], check=True,
                   env={**__import__("os").environ, "PGCLIENTENCODING": "UTF8", "PGOPTIONS": "-c client_min_messages=warning"})


def correr_mongosh(archivo):
    subprocess.run(["mongosh", "--quiet", "--file", str(RAIZ / archivo)], check=True, stdout=subprocess.DEVNULL)


def a_fila(e):
    l, m = e["lecturas"], e["meta"]
    return (e["_id"], e["paciente_id"], e["hospitalizacion_id"], e["dispositivo_id"], e["tipo_dispositivo"],
            e["ts"], *[l.get(c) for c in LECT], m["bateria_pct"], m["firmware"], m["red"])


def a_json(e):
    d = dict(e)
    d["ts"] = e["ts"].isoformat()
    return d


def ram_gb():
    class M(ctypes.Structure):
        _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                    ("avail", ctypes.c_ulonglong), ("a", ctypes.c_ulonglong), ("b", ctypes.c_ulonglong),
                    ("c", ctypes.c_ulonglong), ("d", ctypes.c_ulonglong), ("e", ctypes.c_ulonglong)]
    try:
        m = M(); m.l = ctypes.sizeof(M)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return round(m.total / 1024 ** 3, 1)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# O1. Ingesta masiva
# ---------------------------------------------------------------------------
def ingesta(mdb, pg, eventos):
    r = {}
    n = len(eventos)
    filas = [a_fila(e) for e in eventos]
    alertas = [(e["_id"], i + 1, a["codigo"], a["nivel"], a["mensaje"])
               for e in eventos for i, a in enumerate(e.get("alertas", []))]
    docs_ts = [a_timeseries(e) for e in eventos]
    jsonb = [(e["_id"], e["paciente_id"], e["ts"], Jsonb(a_json(e))) for e in eventos]
    ins_ev = f"INSERT INTO comparativo.eventos_telemetria ({', '.join(COLS)}) VALUES ({', '.join(['%s'] * len(COLS))})"
    ins_al = "INSERT INTO comparativo.alertas_evento (evento_id, orden, codigo, nivel, mensaje) VALUES (%s,%s,%s,%s,%s)"

    # MongoDB colección normal: lotes de 1000, ordered=False, write concern por defecto (w:1)
    t0 = time.perf_counter()
    for i in range(0, n, LOTE):
        mdb.eventos_telemetria.insert_many(eventos[i:i + LOTE], ordered=False)
    r["mongo"] = time.perf_counter() - t0
    log(f"  mongo       {r['mongo']:7.2f} s")

    t0 = time.perf_counter()
    for i in range(0, n, LOTE):
        mdb.eventos_telemetria_ts.insert_many(docs_ts[i:i + LOTE], ordered=False)
    r["mongo_ts"] = time.perf_counter() - t0
    log(f"  mongo_ts    {r['mongo_ts']:7.2f} s")

    # PostgreSQL columnas: cada lote es UNA transacción (eventos + sus alertas juntos)
    al_por_lote = {}
    for a in alertas:
        al_por_lote.setdefault((a[0] - 1) // LOTE, []).append(a)
    t0 = time.perf_counter()
    with pg.cursor() as cur:
        for i in range(0, n, LOTE):
            with pg.transaction():
                cur.executemany(ins_ev, filas[i:i + LOTE])
                if al_por_lote.get(i // LOTE):
                    cur.executemany(ins_al, al_por_lote[i // LOTE])
    r["pg_columnas"] = time.perf_counter() - t0
    log(f"  pg_columnas {r['pg_columnas']:7.2f} s")

    t0 = time.perf_counter()
    with pg.cursor() as cur:
        for i in range(0, n, LOTE):
            with pg.transaction():
                cur.executemany("INSERT INTO comparativo.eventos_jsonb VALUES (%s,%s,%s,%s)", jsonb[i:i + LOTE])
    r["pg_jsonb"] = time.perf_counter() - t0
    log(f"  pg_jsonb    {r['pg_jsonb']:7.2f} s")

    # PostgreSQL con COPY (carga por flujo, sugerida como optimización)
    with pg.transaction():
        pg.execute("TRUNCATE comparativo.alertas_evento, comparativo.eventos_telemetria")
    t0 = time.perf_counter()
    with pg.transaction(), pg.cursor() as cur:
        with cur.copy(f"COPY comparativo.eventos_telemetria ({', '.join(COLS)}) FROM STDIN") as cp:
            for f in filas:
                cp.write_row(f)
        with cur.copy("COPY comparativo.alertas_evento (evento_id, orden, codigo, nivel, mensaje) FROM STDIN") as cp:
            for a in alertas:
                cp.write_row(a)
    r["pg_copy"] = time.perf_counter() - t0
    log(f"  pg_copy     {r['pg_copy']:7.2f} s")

    return {k: {"segundos": round(v, 3), "eventos_por_s": round(n / v)} for k, v in r.items()}, len(alertas)


# ---------------------------------------------------------------------------
# Definición de las consultas (la misma pregunta en cada motor)
# ---------------------------------------------------------------------------
SQL_O2_COL = """
SELECT e.*, (SELECT json_agg(json_build_object('codigo', a.codigo, 'nivel', a.nivel, 'mensaje', a.mensaje) ORDER BY a.orden)
             FROM comparativo.alertas_evento a WHERE a.evento_id = e.evento_id) AS alertas
FROM comparativo.eventos_telemetria e
WHERE e.paciente_id = %s AND e.ts >= %s AND e.ts < %s
ORDER BY e.ts DESC"""
SQL_O2_JSONB = """
SELECT doc FROM comparativo.eventos_jsonb
WHERE paciente_id = %s AND ts >= %s AND ts < %s ORDER BY ts DESC"""
SQL_O3_COL = """
SELECT paciente_id, count(*) AS lecturas, round(avg(fc_lpm), 1) AS fc_prom,
       min(spo2_pct) AS spo2_min, max(pa_sistolica) AS pas_max
FROM comparativo.eventos_telemetria
WHERE tipo_dispositivo = 'monitor_multiparametro'
GROUP BY paciente_id ORDER BY paciente_id"""
SQL_O3_JSONB = """
SELECT paciente_id, count(*) AS lecturas,
       round(avg((doc->'lecturas'->>'fc_lpm')::int), 1) AS fc_prom,
       min((doc->'lecturas'->>'spo2_pct')::int) AS spo2_min,
       max((doc->'lecturas'->>'pa_sistolica')::int) AS pas_max
FROM comparativo.eventos_jsonb
WHERE doc->>'tipo_dispositivo' = 'monitor_multiparametro'
GROUP BY paciente_id ORDER BY paciente_id"""
SQL_O4_SOLO_PG = """
SELECT v.nombre_completo, v.documento, v.numero_cama, v.medico_tratante,
       e.ts, e.dispositivo_id, a.codigo, a.mensaje
FROM comparativo.eventos_telemetria e
JOIN comparativo.alertas_evento a ON a.evento_id = e.evento_id
JOIN core.v_contexto_paciente v   ON v.paciente_id = e.paciente_id AND v.estado_hospitalizacion = 'activa'
WHERE e.ts >= %s AND a.nivel = 'critica'
ORDER BY e.ts DESC"""
SQL_CONTEXTO = """
SELECT paciente_id, nombre_completo, documento, numero_cama, medico_tratante
FROM core.v_contexto_paciente
WHERE paciente_id = ANY(%s) AND estado_hospitalizacion = 'activa'"""

PIPE_O3 = [{"$match": {"tipo_dispositivo": "monitor_multiparametro"}},
           {"$group": {"_id": "$paciente_id", "lecturas": {"$sum": 1},
                       "fc_prom": {"$avg": "$lecturas.fc_lpm"}, "spo2_min": {"$min": "$lecturas.spo2_pct"},
                       "pas_max": {"$max": "$lecturas.pa_sistolica"}}},
           {"$sort": {"_id": 1}}]
PIPE_O3_TS = [{"$match": {"origen.tipo_dispositivo": "monitor_multiparametro"}},
              {"$group": {"_id": "$origen.paciente_id", "lecturas": {"$sum": 1},
                          "fc_prom": {"$avg": "$lecturas.fc_lpm"}, "spo2_min": {"$min": "$lecturas.spo2_pct"},
                          "pas_max": {"$max": "$lecturas.pa_sistolica"}}},
              {"$sort": {"_id": 1}}]


def consultas(mdb, pg):
    def pg_q(sql, params=None):
        def f():
            with pg.cursor() as cur:
                cur.execute(sql, params)
                return len(cur.fetchall())
        return f

    f_o2 = {"paciente_id": Q_PACIENTE, "ts": {"$gte": Q_DESDE, "$lt": Q_HASTA}}
    f_o2_ts = {"origen.paciente_id": Q_PACIENTE, "ts": {"$gte": Q_DESDE, "$lt": Q_HASTA}}

    def o4_hibrida():
        # 1) MongoDB: eventos con alerta crítica en las últimas 24 h (capa BASE)
        evs = list(mdb.eventos_telemetria.find(
            {"ts": {"$gte": Q_ALERTAS_DESDE}, "alertas.nivel": "critica"},
            {"paciente_id": 1, "dispositivo_id": 1, "ts": 1, "alertas": 1}).sort("ts", -1))
        # 2) PostgreSQL: identidad y cama SOLO de los pacientes involucrados (capa ACID)
        ids = sorted({e["paciente_id"] for e in evs})
        with pg.cursor() as cur:
            cur.execute(SQL_CONTEXTO, (ids,))
            ctx = {f[0]: f for f in cur.fetchall()}
        # 3) La aplicación une ambos mundos
        filas = [(ctx[e["paciente_id"]][1], ctx[e["paciente_id"]][2], ctx[e["paciente_id"]][3],
                  ctx[e["paciente_id"]][4], e["ts"], e["dispositivo_id"], a["codigo"], a["mensaje"])
                 for e in evs if e["paciente_id"] in ctx for a in e["alertas"] if a["nivel"] == "critica"]
        return len(filas)

    return {
        "O2_consulta_puntual": {
            "mongo": lambda: len(list(mdb.eventos_telemetria.find(f_o2).sort("ts", -1))),
            "mongo_ts": lambda: len(list(mdb.eventos_telemetria_ts.find(f_o2_ts).sort("ts", -1))),
            "pg_columnas": pg_q(SQL_O2_COL, (Q_PACIENTE, Q_DESDE, Q_HASTA)),
            "pg_jsonb": pg_q(SQL_O2_JSONB, (Q_PACIENTE, Q_DESDE, Q_HASTA)),
        },
        "O3_agregacion": {
            "mongo": lambda: len(list(mdb.eventos_telemetria.aggregate(PIPE_O3))),
            "mongo_ts": lambda: len(list(mdb.eventos_telemetria_ts.aggregate(PIPE_O3_TS))),
            "pg_columnas": pg_q(SQL_O3_COL),
            "pg_jsonb": pg_q(SQL_O3_JSONB),
        },
        "O4_alertas_con_identidad": {
            "hibrida_mongo+pg": o4_hibrida,
            "solo_pg": pg_q(SQL_O4_SOLO_PG, (Q_ALERTAS_DESDE,)),
        },
    }


REPS = {"O2_consulta_puntual": 30, "O3_agregacion": 7, "O4_alertas_con_identidad": 20}


def crear_indices(mdb, pg):
    """Índices sugeridos en la fase de optimización asistida por IA."""
    t = {}
    t0 = time.perf_counter()
    mdb.eventos_telemetria.create_index([("paciente_id", 1), ("ts", -1)], name="ix_paciente_ts")
    mdb.eventos_telemetria.create_index([("alertas.nivel", 1), ("ts", -1)], name="ix_alerta_nivel_ts")
    mdb.eventos_telemetria_ts.create_index([("origen.paciente_id", 1), ("ts", -1)], name="ix_origen_paciente_ts")
    t["mongo"] = round(time.perf_counter() - t0, 3)
    t0 = time.perf_counter()
    with pg.transaction():
        pg.execute("CREATE INDEX ix_ev_paciente_ts ON comparativo.eventos_telemetria (paciente_id, ts DESC)")
        pg.execute("CREATE INDEX ix_ev_ts ON comparativo.eventos_telemetria (ts DESC)")
        pg.execute("CREATE INDEX ix_alerta_critica ON comparativo.alertas_evento (evento_id) WHERE nivel = 'critica'")
        pg.execute("CREATE INDEX ix_jsonb_paciente_ts ON comparativo.eventos_jsonb (paciente_id, ts DESC)")
    t["pg"] = round(time.perf_counter() - t0, 3)
    return t


def explicar(mdb, pg, fase):
    """Guarda los planes de ejecución (explain) para el informe."""
    out = {}
    exp = mdb.command("explain", {"find": "eventos_telemetria",
                                  "filter": {"paciente_id": Q_PACIENTE, "ts": {"$gte": Q_DESDE, "$lt": Q_HASTA}},
                                  "sort": {"ts": -1}}, verbosity="executionStats")
    es = exp["executionStats"]

    def etapas(p):
        s = [p.get("stage")]
        for k in ("inputStage",):
            if k in p:
                s += etapas(p[k])
        for k in ("inputStages",):
            for x in p.get(k, []):
                s += etapas(x)
        return s
    wp = exp["queryPlanner"]["winningPlan"]
    wp = wp.get("queryPlan", wp)
    out["mongo_O2"] = {"etapas": etapas(wp), "docs_examinados": es["totalDocsExamined"],
                       "claves_examinadas": es["totalKeysExamined"], "devueltos": es["nReturned"],
                       "ms_servidor": es["executionTimeMillis"]}
    texto = []
    for nombre, sql, params in [("O2 pg_columnas", SQL_O2_COL, (Q_PACIENTE, Q_DESDE, Q_HASTA)),
                                ("O3 pg_columnas", SQL_O3_COL, None),
                                ("O4 solo_pg", SQL_O4_SOLO_PG, (Q_ALERTAS_DESDE,))]:
        with pg.cursor() as cur:
            cur.execute("EXPLAIN (ANALYZE, BUFFERS) " + sql, params)
            plan = "\n".join(r[0] for r in cur.fetchall())
        texto.append(f"===== {nombre} ({fase}) =====\n{plan}\n")
        if nombre.startswith("O2"):
            out["pg_O2_plan_resumen"] = plan.splitlines()[0].strip()
            out["pg_O2_ms_servidor"] = float(plan.splitlines()[-1].split(":")[1].split()[0])
    (RES / f"explain_postgresql_{fase}.txt").write_text("\n".join(texto), encoding="utf-8")
    (RES / f"explain_mongodb_{fase}.json").write_text(
        json.dumps({"filtro": "paciente_id=PAC003 y ts en [2026-11-21 18:00, 2026-11-22 00:00)",
                    "plan_ganador": wp, "executionStats": {k: es[k] for k in
                    ("nReturned", "executionTimeMillis", "totalKeysExamined", "totalDocsExamined")}},
                   indent=2, default=str), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# O5 a O8
# ---------------------------------------------------------------------------
def flexibilidad(mdb, pg, n=1000):
    """Llega un sensor NUEVO (capnógrafo) con un campo que nadie había visto: etco2_mmhg."""
    import random
    rng = random.Random(7)
    base_id = 10_000_000
    # El dispositivo se registra en la capa ACID (dato maestro) - igual para ambos enfoques
    with pg.transaction():
        pg.execute("INSERT INTO core.dispositivos VALUES ('CAP-H03','capnografo','Masimo EMMA','SN-CAP-2026-03',TRUE) ON CONFLICT DO NOTHING")
        pg.execute("""INSERT INTO core.asignaciones_dispositivo (dispositivo_id, hospitalizacion_id, paciente_id, desde)
                      SELECT 'CAP-H03','HOSP003','PAC003', now()
                      WHERE NOT EXISTS (SELECT 1 FROM core.asignaciones_dispositivo WHERE dispositivo_id='CAP-H03' AND hasta IS NULL)""")
    ahora = datetime.now(timezone.utc).replace(microsecond=0)
    docs = [{"_id": base_id + i, "paciente_id": "PAC003", "hospitalizacion_id": "HOSP003",
             "dispositivo_id": "CAP-H03", "tipo_dispositivo": "capnografo", "ts": ahora,
             "lecturas": {"etco2_mmhg": rng.randint(30, 50), "fr_rpm": rng.randint(12, 26)},
             "meta": {"bateria_pct": 90, "firmware": "v1.0.0", "red": "wifi"}} for i in range(n)]
    r = {}
    t0 = time.perf_counter()
    mdb.eventos_telemetria.insert_many(docs, ordered=False)          # sin cambiar nada del esquema
    r["mongo"] = {"ms": round((time.perf_counter() - t0) * 1000, 2), "sentencias_ddl": 0,
                  "cambio_codigo": "ninguno: el documento trae su propio campo"}
    t0 = time.perf_counter()
    with pg.transaction():
        pg.execute("ALTER TABLE comparativo.eventos_telemetria ADD COLUMN IF NOT EXISTS etco2_mmhg SMALLINT")
    t_ddl = (time.perf_counter() - t0) * 1000
    filas = [(d["_id"], "PAC003", "HOSP003", "CAP-H03", "capnografo", ahora,
              d["lecturas"]["fr_rpm"], d["lecturas"]["etco2_mmhg"], 90, "v1.0.0", "wifi") for d in docs]
    t1 = time.perf_counter()
    with pg.transaction(), pg.cursor() as cur:
        cur.executemany("""INSERT INTO comparativo.eventos_telemetria (evento_id, paciente_id, hospitalizacion_id,
            dispositivo_id, tipo_dispositivo, ts, fr_rpm, etco2_mmhg, bateria_pct, firmware, red)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", filas)
    r["pg_columnas"] = {"ms": round(t_ddl + (time.perf_counter() - t1) * 1000, 2), "ms_ddl": round(t_ddl, 2),
                        "sentencias_ddl": 1,
                        "cambio_codigo": "ALTER TABLE + actualizar INSERT, mapeos y reportes (bloqueo ACCESS EXCLUSIVE durante el ALTER)"}
    t0 = time.perf_counter()
    with pg.transaction(), pg.cursor() as cur:
        cur.executemany("INSERT INTO comparativo.eventos_jsonb VALUES (%s,%s,%s,%s)",
                        [(d["_id"], "PAC003", ahora, Jsonb(a_json(d))) for d in docs])
    r["pg_jsonb"] = {"ms": round((time.perf_counter() - t0) * 1000, 2), "sentencias_ddl": 0,
                     "cambio_codigo": "ninguno en la tabla; las consultas deben extraer el campo con ->>"}
    # Se deshace para no alterar las siguientes corridas / mediciones de almacenamiento
    mdb.eventos_telemetria.delete_many({"tipo_dispositivo": "capnografo"})
    with pg.transaction():
        pg.execute("DELETE FROM comparativo.eventos_telemetria WHERE tipo_dispositivo = 'capnografo'")
        pg.execute("ALTER TABLE comparativo.eventos_telemetria DROP COLUMN etco2_mmhg")
        pg.execute("DELETE FROM comparativo.eventos_jsonb WHERE evento_id >= %s", (base_id,))
        pg.execute("DELETE FROM core.asignaciones_dispositivo WHERE dispositivo_id = 'CAP-H03'")
        pg.execute("DELETE FROM core.dispositivos WHERE dispositivo_id = 'CAP-H03'")
    return r


def transaccion(mdb, cliente, pg, reps=20):
    """Admisión = crear hospitalización + ocupar cama, todo o nada."""
    tiempos = []
    for _ in range(reps):
        t0 = time.perf_counter()
        with pg.cursor() as cur:
            cur.execute("CALL core.sp_admitir_paciente('HOSP950','PAC002','MED001','CAMA009','Prueba de rendimiento')")
            cur.execute("CALL core.sp_dar_alta('HOSP950','mejoria')")
        tiempos.append((time.perf_counter() - t0) * 1000)
        pg.rollback()  # se deshace: la prueba no deja rastro
    r = {"pg": {"mediana_ms": round(statistics.median(tiempos), 3), "resultado": "OK - atómica, aislada y reversible"}}
    # En MongoDB las transacciones multi-documento exigen replica set; esta instalación es standalone.
    try:
        with cliente.start_session() as s:
            with s.start_transaction():
                mdb.camas_demo.update_one({"_id": "CAMA009"}, {"$set": {"estado": "ocupada"}}, upsert=True, session=s)
        r["mongo"] = {"resultado": "OK"}
    except Exception as ex:
        r["mongo"] = {"resultado": "ERROR", "mensaje": str(ex).split(", full error")[0][:200]}
    mdb.camas_demo.drop()
    return r


def integridad(mdb, pg):
    """¿Qué pasa si llega una lectura de un paciente que NO existe?"""
    huerfano = {"_id": 99_999_999, "paciente_id": "PAC999", "hospitalizacion_id": "HOSP999",
                "dispositivo_id": "MON-FALSO", "tipo_dispositivo": "monitor_multiparametro",
                "ts": datetime.now(timezone.utc), "lecturas": {"fc_lpm": 80}}
    r = {}
    try:
        mdb.eventos_telemetria.insert_one(huerfano)
        r["mongo"] = "ACEPTADO: MongoDB no conoce la tabla de pacientes (no hay llaves foráneas)"
    except Exception as ex:
        r["mongo"] = f"RECHAZADO: {ex}"[:200]
    mdb.eventos_telemetria.delete_one({"_id": 99_999_999})
    try:
        with pg.transaction():
            pg.execute("""INSERT INTO comparativo.eventos_telemetria (evento_id, paciente_id, hospitalizacion_id,
                          dispositivo_id, tipo_dispositivo, ts, fc_lpm) VALUES (99999999,'PAC999','HOSP999',
                          'MON-FALSO','monitor_multiparametro', now(), 80)""")
        r["pg"] = "ACEPTADO"
    except Exception as ex:
        r["pg"] = "RECHAZADO: " + str(ex).splitlines()[0][:180]
    # Y si falta un campo obligatorio, el validador $jsonSchema de MongoDB sí lo rechaza
    try:
        mdb.eventos_telemetria.insert_one({"_id": 99_999_998, "tipo_dispositivo": "monitor_multiparametro",
                                           "lecturas": {"fc_lpm": 80}})
        r["mongo_sin_paciente_id"] = "ACEPTADO"
        mdb.eventos_telemetria.delete_one({"_id": 99_999_998})
    except Exception:
        r["mongo_sin_paciente_id"] = "RECHAZADO por el validador $jsonSchema (Document failed validation)"
    return r


def almacenamiento(mdb, pg):
    r = {}
    mdb.client.admin.command("fsync")  # obliga a MongoDB a escribir en disco antes de medir
    for c in ("eventos_telemetria", "eventos_telemetria_ts"):
        s = next(mdb[c].aggregate([{"$collStats": {"storageStats": {}}}]))["storageStats"]
        r[f"mongo:{c}"] = {"datos_mb": round(s["storageSize"] / 1024 ** 2, 2),
                           "datos_sin_comprimir_mb": round(s["size"] / 1024 ** 2, 2),
                           "indices_mb": round(s["totalIndexSize"] / 1024 ** 2, 2)}
    with pg.cursor() as cur:
        for t in ("comparativo.eventos_telemetria", "comparativo.alertas_evento", "comparativo.eventos_jsonb"):
            cur.execute("SELECT pg_table_size(%s), pg_indexes_size(%s)", (t, t))
            a, b = cur.fetchone()
            r[f"pg:{t.split('.')[1]}"] = {"datos_mb": round(a / 1024 ** 2, 2), "indices_mb": round(b / 1024 ** 2, 2)}
    return r


# ---------------------------------------------------------------------------
def main(n):
    RES.mkdir(exist_ok=True)
    M = {"fecha": datetime.now().isoformat(timespec="seconds"), "eventos": n}
    log("== Preparando estructuras (05_tablas_comparativas.sql y 01_crear_colecciones.js) ==")
    correr_psql("sql/05_tablas_comparativas.sql")
    correr_mongosh("nosql/01_crear_colecciones.js")

    cliente, mdb = conectar_mongo()
    pg = conectar_pg(autocommit=True)
    pgv = pg.execute("SHOW server_version").fetchone()[0]
    M["entorno"] = {"so": platform.platform(), "cpu": platform.processor(), "ram_gb": ram_gb(),
                    "python": platform.python_version(), "postgresql": pgv,
                    "mongodb": mdb.command("buildInfo")["version"], "mismo_equipo": True,
                    "nota": "Ambos motores en el mismo PC local, sin réplicas; tiempos con caché caliente"}

    asign = leer_asignaciones(pg)
    eventos = generar_eventos(asign, n)
    log(f"== O1 Ingesta masiva de {n:,} eventos ==")
    M["O1_ingesta"], M["alertas_totales"] = ingesta(mdb, pg, eventos)
    pg.execute("VACUUM ANALYZE comparativo.eventos_telemetria")
    pg.execute("VACUUM ANALYZE comparativo.alertas_evento")
    pg.execute("VACUUM ANALYZE comparativo.eventos_jsonb")
    # Verificación: los motores tienen la misma cantidad de datos
    M["verificacion_conteos"] = {
        "mongo": mdb.eventos_telemetria.count_documents({}),
        "mongo_ts": mdb.eventos_telemetria_ts.count_documents({}),
        "pg_columnas": pg.execute("SELECT count(*) FROM comparativo.eventos_telemetria").fetchone()[0],
        "pg_jsonb": pg.execute("SELECT count(*) FROM comparativo.eventos_jsonb").fetchone()[0],
        "alertas_pg": pg.execute("SELECT count(*) FROM comparativo.alertas_evento").fetchone()[0],
    }
    log(f"   conteos: {M['verificacion_conteos']}")

    pg.autocommit = False
    qs = consultas(mdb, pg)
    M["consultas"] = {}
    for fase in ("sin_indices", "con_indices"):
        if fase == "con_indices":
            pg.commit()
            M["tiempo_creacion_indices_s"] = crear_indices(mdb, pg)
            pg.commit(); pg.autocommit = True
            pg.execute("ANALYZE comparativo.eventos_telemetria"); pg.execute("ANALYZE comparativo.alertas_evento")
            pg.execute("ANALYZE comparativo.eventos_jsonb"); pg.autocommit = False
        log(f"== Consultas ({fase}) ==")
        M.setdefault("explain", {})[fase] = explicar(mdb, pg, fase)
        pg.commit()
        for op, motores in qs.items():
            for motor, fn in motores.items():
                st = medir(fn, REPS[op])
                pg.commit()
                M["consultas"].setdefault(op, {}).setdefault(fase, {})[motor] = st
                log(f"  {op:26s} {motor:18s} mediana={st['mediana_ms']:9.2f} ms  filas={st['filas']}")

    log("== O5 Flexibilidad / O6 Transacción / O7 Integridad / O8 Almacenamiento ==")
    pg.commit(); pg.autocommit = True
    M["O5_flexibilidad"] = flexibilidad(mdb, pg)
    pg.autocommit = False
    M["O6_transaccion"] = transaccion(mdb, cliente, pg)
    pg.commit(); pg.autocommit = True
    M["O7_integridad"] = integridad(mdb, pg)
    pg.execute("VACUUM ANALYZE comparativo.eventos_telemetria")
    M["O8_almacenamiento"] = almacenamiento(mdb, pg)
    for k in ("O5_flexibilidad", "O6_transaccion", "O7_integridad", "O8_almacenamiento"):
        log(f"  {k}: {json.dumps(M[k], ensure_ascii=False, default=str)}")

    # Dejar la capa BASE completa también con las teleconsultas
    mdb.sesiones_teleconsulta.insert_many(generar_teleconsultas(pg, 400), ordered=False)

    (RES / "metricas.json").write_text(json.dumps(M, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    with open(RES / "metricas_resumen.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["operacion", "fase", "motor", "mediana_ms", "p95_ms", "min_ms", "max_ms", "filas"])
        for k, v in M["O1_ingesta"].items():
            w.writerow(["O1_ingesta", "-", k, round(v["segundos"] * 1000, 1), "", "", "", n])
        for op, fases in M["consultas"].items():
            for fase, mot in fases.items():
                for motor, st in mot.items():
                    w.writerow([op, fase, motor, st["mediana_ms"], st["p95_ms"], st["min_ms"], st["max_ms"], st["filas"]])
    log(f"== Listo. Resultados en {RES} ==")
    pg.close(); cliente.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200_000)
    main(ap.parse_args().n)
