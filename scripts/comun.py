"""
comun.py - Configuración y generador de eventos clínicos compartido por los scripts.
Grupo 6 - Bases de Datos II (G101)

Idea clave del ecosistema híbrido:
  * PostgreSQL (capa ACID) dice QUÉ dispositivo pertenece a QUÉ paciente y en qué
    hospitalización (tabla core.asignaciones_dispositivo).
  * El generador le pregunta eso a PostgreSQL y luego produce las lecturas
    masivas que van a MongoDB (capa BASE). Así la telemetría nunca inventa
    pacientes: siempre referencia identidades que existen en el núcleo ACID.
"""
import os
import random
from datetime import datetime, timedelta, timezone

import psycopg
from pymongo import MongoClient

# ---------------------------------------------------------------------------
# Conexiones (se pueden cambiar con variables de entorno)
# ---------------------------------------------------------------------------
PG_DSN = os.getenv("PG_DSN", "host=localhost dbname=hce_core_grupo_6 user=postgres")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = "hce_telemetria_grupo_6"

# Fin del periodo simulado para las hospitalizaciones que siguen activas
FIN_SIMULACION = datetime(2026, 11, 21, 23, 59, 59, tzinfo=timezone.utc)
SEMILLA = 2026  # misma semilla = mismos datos en cada corrida (comparación justa)


def conectar_pg(autocommit=False):
    return psycopg.connect(PG_DSN, autocommit=autocommit)


def conectar_mongo():
    cliente = MongoClient(MONGO_URI)
    return cliente, cliente[MONGO_DB]


# ---------------------------------------------------------------------------
# Datos de referencia desde la capa ACID
# ---------------------------------------------------------------------------
def leer_asignaciones(pg, solo_activas=False):
    """Devuelve la lista de dispositivos asignados (dispositivo -> paciente -> hospitalización)."""
    sql = """
        SELECT a.dispositivo_id, d.tipo_dispositivo, a.paciente_id, a.hospitalizacion_id,
               a.desde, COALESCE(a.hasta, %s) AS hasta, h.medico_id
        FROM core.asignaciones_dispositivo a
        JOIN core.dispositivos d       ON d.dispositivo_id = a.dispositivo_id
        JOIN core.hospitalizaciones h  ON h.hospitalizacion_id = a.hospitalizacion_id
        WHERE (%s = FALSE OR a.hasta IS NULL)
        ORDER BY a.hospitalizacion_id, a.dispositivo_id
    """
    with pg.cursor() as cur:
        cur.execute(sql, (FIN_SIMULACION, solo_activas))
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, fila)) for fila in cur.fetchall()]


# ---------------------------------------------------------------------------
# Perfil clínico de cada paciente (para que los datos se vean realistas)
# ---------------------------------------------------------------------------
PERFIL_BASE = dict(fc=78, spo2=97, pas=122, pad=76, fr=17, temp=36.8, glu=115)
PERFILES = {
    "PAC001": dict(spo2=91, temp=38.0, fc=96, fr=22),   # neumonía
    "PAC003": dict(glu=255, fc=88),                      # diabetes descompensada
    "PAC005": dict(spo2=89, fr=24, fc=94),               # EPOC exacerbado
    "PAC007": dict(pas=168, pad=102),                    # crisis hipertensiva
    "PAC008": dict(spo2=92, temp=38.3, fc=100),          # neumonía viral
    "PAC010": dict(fc=108, pas=102, pad=62),             # deshidratación
    "PAC011": dict(glu=190, temp=37.9, fc=92),           # celulitis + diabetes
}
MEDICAMENTOS = ["Ceftriaxona", "Solucion salina 0.9%", "Insulina cristalina",
                "Dipirona", "Lactato de Ringer", "Vancomicina", "Omeprazol"]

# Proporción de cada tipo de dispositivo en el flujo de eventos
PESO_TIPO = {"monitor_multiparametro": 0.45, "pulsera_wearable": 0.35,
             "bomba_infusion": 0.12, "glucometro": 0.08}


def _perfil(paciente_id):
    p = dict(PERFIL_BASE)
    p.update(PERFILES.get(paciente_id, {}))
    return p


def _alerta(codigo, nivel, mensaje):
    return {"codigo": codigo, "nivel": nivel, "mensaje": mensaje}


def generar_evento(rng, evento_id, asig, ts):
    """Crea UN documento de telemetría. Los campos de 'lecturas' cambian según el dispositivo."""
    tipo = asig["tipo_dispositivo"]
    p = _perfil(asig["paciente_id"])
    lect, alertas = {}, []

    if tipo == "monitor_multiparametro":
        lect["fc_lpm"] = int(rng.gauss(p["fc"], 9))
        lect["spo2_pct"] = min(100, int(rng.gauss(p["spo2"], 2)))
        lect["pa_sistolica"] = int(rng.gauss(p["pas"], 12))
        lect["pa_diastolica"] = int(rng.gauss(p["pad"], 8))
        lect["fr_rpm"] = int(rng.gauss(p["fr"], 3))
        if rng.random() < 0.3:  # la temperatura solo se toma a veces -> campo opcional
            lect["temperatura_c"] = round(rng.gauss(p["temp"], 0.4), 1)
    elif tipo == "pulsera_wearable":
        lect["fc_lpm"] = int(rng.gauss(p["fc"] - 3, 8))
        lect["pasos"] = max(0, int(rng.gauss(40, 35)))
        lect["temp_piel_c"] = round(rng.gauss(p["temp"] - 2.5, 0.4), 1)
        if ts.hour < 6:  # de noche la pulsera agrega calidad de sueño
            lect["calidad_sueno"] = rng.choice(["profundo", "ligero", "rem", "despierto"])
    elif tipo == "bomba_infusion":
        lect["medicamento"] = MEDICAMENTOS[int(asig["hospitalizacion_id"][-3:]) % len(MEDICAMENTOS)]
        lect["velocidad_ml_h"] = round(rng.choice([20, 42, 63, 83, 125]) * rng.uniform(0.95, 1.05), 1)
        lect["volumen_restante_ml"] = round(rng.uniform(0, 1000), 1)
    elif tipo == "glucometro":
        lect["glucosa_mg_dl"] = int(rng.gauss(p["glu"], 40))
        lect["momento_toma"] = rng.choice(["ayunas", "preprandial", "postprandial", "nocturna"])

    # Reglas de alerta (lo que haría el firmware del dispositivo o un servicio de reglas)
    fc, spo2 = lect.get("fc_lpm"), lect.get("spo2_pct")
    if spo2 is not None and spo2 < 90:
        alertas.append(_alerta("SPO2_BAJA", "critica" if spo2 < 88 else "advertencia", f"SpO2 {spo2}%"))
    if fc is not None and fc > 120:
        alertas.append(_alerta("TAQUICARDIA", "critica" if fc > 140 else "advertencia", f"FC {fc} lpm"))
    if lect.get("pa_sistolica", 0) > 170:
        alertas.append(_alerta("HTA_SEVERA", "critica", f"PAS {lect['pa_sistolica']} mmHg"))
    g = lect.get("glucosa_mg_dl")
    if g is not None and (g > 300 or g < 70):
        alertas.append(_alerta("HIPERGLUCEMIA" if g > 300 else "HIPOGLUCEMIA", "critica", f"Glucosa {g} mg/dL"))
    if lect.get("volumen_restante_ml", 999) < 30:
        alertas.append(_alerta("FIN_INFUSION", "advertencia", "Quedan menos de 30 mL"))

    bateria = rng.randint(5, 100)
    if bateria < 8:
        alertas.append(_alerta("BATERIA_BAJA", "info", f"Bateria {bateria}%"))

    doc = {
        "_id": evento_id,
        "paciente_id": asig["paciente_id"],
        "hospitalizacion_id": asig["hospitalizacion_id"],
        "dispositivo_id": asig["dispositivo_id"],
        "tipo_dispositivo": tipo,
        "ts": ts,
        "lecturas": lect,
        "meta": {"bateria_pct": bateria,
                 "firmware": rng.choice(["v2.1.0", "v2.1.3", "v3.0.1"]),
                 "red": rng.choice(["wifi", "wifi", "ethernet", "4g"])},
    }
    if alertas:  # el arreglo solo existe cuando hay alertas (documento autodescriptivo)
        doc["alertas"] = alertas
    return doc


def generar_eventos(asignaciones, n, semilla=SEMILLA, id_inicial=1):
    """Genera n eventos repartidos según la duración de cada hospitalización y el tipo de dispositivo."""
    rng = random.Random(semilla)
    pesos = []
    for a in asignaciones:
        horas = max(1.0, (a["hasta"] - a["desde"]).total_seconds() / 3600)
        pesos.append(horas * PESO_TIPO.get(a["tipo_dispositivo"], 0.05))
    elegidas = rng.choices(asignaciones, weights=pesos, k=n)
    eventos = []
    for i, a in enumerate(elegidas):
        seg = rng.uniform(0, (a["hasta"] - a["desde"]).total_seconds())
        ts = (a["desde"] + timedelta(seconds=seg)).astimezone(timezone.utc).replace(microsecond=0)
        eventos.append(generar_evento(rng, id_inicial + i, a, ts))
    eventos.sort(key=lambda e: e["ts"])  # llegan en orden de tiempo, como un flujo real
    for i, e in enumerate(eventos):      # ids consecutivos en orden de llegada
        e["_id"] = id_inicial + i
    return eventos


def a_timeseries(e):
    """Convierte un evento al formato de la colección time series (metaField = origen)."""
    d = {"ts": e["ts"],
         "origen": {"paciente_id": e["paciente_id"], "hospitalizacion_id": e["hospitalizacion_id"],
                    "dispositivo_id": e["dispositivo_id"], "tipo_dispositivo": e["tipo_dispositivo"]},
         "lecturas": e["lecturas"], "meta": e["meta"]}
    if "alertas" in e:
        d["alertas"] = e["alertas"]
    return d


def generar_teleconsultas(pg, n=400, semilla=SEMILLA):
    """Sesiones de teleconsulta post-alta: documentos con subdocumentos y arreglos de logs."""
    rng = random.Random(semilla + 1)
    with pg.cursor() as cur:
        cur.execute("""SELECT hospitalizacion_id, paciente_id, medico_id, fecha_alta
                       FROM core.hospitalizaciones WHERE estado = 'dada_de_alta'""")
        altas = cur.fetchall()
    sesiones = []
    for i in range(n):
        hosp, pac, med, alta = rng.choice(altas)
        inicio = alta + timedelta(days=rng.randint(2, 30), hours=rng.randint(7, 17), minutes=rng.choice([0, 20, 40]))
        estado = rng.choices(["completada", "interrumpida", "no_asistio"], [0.8, 0.12, 0.08])[0]
        s = {"_id": f"TLC-{i + 1:05d}", "paciente_id": pac, "medico_id": med,
             "hospitalizacion_origen": hosp, "inicio": inicio, "estado": estado,
             "plataforma": rng.choice(["web", "app_android", "app_ios"])}
        if estado != "no_asistio":
            dur = rng.randint(8, 35)
            s["duracion_min"] = dur
            log = [{"ts": inicio, "tipo": "conexion", "detalle": "Paciente ingresa a la sala"}]
            for _ in range(rng.randint(0, 4)):
                log.append({"ts": inicio + timedelta(minutes=rng.uniform(1, dur)),
                            "tipo": rng.choice(["reconexion", "cambio_resolucion", "compartir_pantalla"]),
                            "latencia_ms": rng.randint(40, 900)})
            log.append({"ts": inicio + timedelta(minutes=dur), "tipo": "desconexion"})
            s["eventos_conexion"] = sorted(log, key=lambda x: x["ts"])
            s["calidad"] = {"latencia_prom_ms": rng.randint(60, 450),
                            "cortes": sum(1 for x in log if x["tipo"] == "reconexion"),
                            "resolucion": rng.choice(["480p", "720p", "1080p"])}
            # Signos reportados por el propio paciente: cada sesión trae los que tenga a mano
            sr = {}
            if rng.random() < 0.7:
                sr["presion_arterial"] = f"{rng.randint(105, 160)}/{rng.randint(65, 100)}"
            if rng.random() < 0.5:
                sr["temperatura_c"] = round(rng.uniform(36.0, 38.2), 1)
            if rng.random() < 0.3:
                sr["glucometria_mg_dl"] = rng.randint(80, 260)
            if sr:
                s["signos_reportados"] = sr
            if rng.random() < 0.6:
                s["encuesta"] = {"satisfaccion_1a5": rng.randint(3, 5), "comentario": rng.choice(
                    ["Buena atencion", "Se corto el audio", "Muy util", "La app es lenta", None])}
        sesiones.append(s)
    return sesiones
