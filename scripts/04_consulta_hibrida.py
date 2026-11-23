"""
04_consulta_hibrida.py - La aplicación que une los dos mundos.
Grupo 6 - Bases de Datos II (G101)

Pregunta clínica: "¿Qué pacientes HOSPITALIZADOS tuvieron alertas críticas en el último día,
quiénes son, en qué cama están y quién es su médico?"

  Paso 1 (BASE / MongoDB):   buscar eventos con alerta crítica (millones de lecturas, índice multikey).
  Paso 2 (ACID / PostgreSQL): traer identidad, cama y médico SOLO de esos pacientes.
  Paso 3 (aplicación):        unir los resultados y mostrar un tablero.

Uso: py scripts/04_consulta_hibrida.py [--desde 2026-11-21T00:00:00]
"""
import argparse
import time
from collections import Counter
from datetime import datetime, timezone

from comun import conectar_mongo, conectar_pg


def main(desde):
    cliente, mdb = conectar_mongo()
    pg = conectar_pg()          # las conexiones se abren antes de medir (en una app real ya están abiertas)
    t0 = time.perf_counter()
    eventos = list(mdb.eventos_telemetria.find(
        {"ts": {"$gte": desde}, "alertas.nivel": "critica"},
        {"paciente_id": 1, "dispositivo_id": 1, "ts": 1, "alertas": 1}).sort("ts", -1))
    t1 = time.perf_counter()
    ids = sorted({e["paciente_id"] for e in eventos})
    print(f"[1] MongoDB: {len(eventos)} eventos con alerta crítica desde {desde:%Y-%m-%d %H:%M} UTC "
          f"-> pacientes {ids}  ({(t1 - t0) * 1000:.1f} ms)")

    with pg.cursor() as cur:
        cur.execute("""SELECT paciente_id, nombre_completo, documento, edad, servicio, numero_cama,
                              medico_tratante, contacto_nombre, contacto_telefono
                       FROM core.v_contexto_paciente
                       WHERE paciente_id = ANY(%s) AND estado_hospitalizacion = 'activa'""", (ids,))
        ctx = {f[0]: f for f in cur.fetchall()}
    t2 = time.perf_counter()
    print(f"[2] PostgreSQL: identidad de {len(ctx)} pacientes activos  ({(t2 - t1) * 1000:.1f} ms)")

    print("\n[3] TABLERO DE ALERTAS CRÍTICAS (unión hecha por la aplicación)")
    print("=" * 96)
    for pid in ids:
        if pid not in ctx:
            continue
        _, nombre, doc, edad, servicio, cama, medico, cnom, ctel = ctx[pid]
        crit = [(e, a) for e in eventos if e["paciente_id"] == pid for a in e["alertas"] if a["nivel"] == "critica"]
        conteo = Counter(a["codigo"] for _, a in crit)
        print(f"{nombre} ({doc}, {edad} años) | {servicio} - cama {cama} | Médico: {medico}")
        print(f"   Contacto: {cnom} {ctel}")
        print(f"   Alertas críticas: {dict(conteo)}")
        for e, a in crit[:3]:
            print(f"     - {e['ts']:%Y-%m-%d %H:%M:%S}  {e['dispositivo_id']:8s} {a['codigo']:14s} {a['mensaje']}")
        print("-" * 96)
    print(f"Tiempo total de la consulta híbrida: {(time.perf_counter() - t0) * 1000:.1f} ms")
    cliente.close()
    pg.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", default="2026-11-21T00:00:00")
    a = ap.parse_args()
    main(datetime.fromisoformat(a.desde).replace(tzinfo=timezone.utc))
