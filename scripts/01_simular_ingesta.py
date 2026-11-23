"""
01_simular_ingesta.py - Simulación automática de ingesta de eventos clínicos en MongoDB.
Grupo 6 - Bases de Datos II (G101)

Dos modos:
  masivo   -> carga histórica: N eventos de telemetría + sesiones de teleconsulta.
              py scripts/01_simular_ingesta.py masivo --n 200000
  continuo -> flujo "en vivo": los dispositivos de las hospitalizaciones ACTIVAS
              envían lecturas cada décima de segundo durante X segundos.
              py scripts/01_simular_ingesta.py continuo --segundos 30 --tasa 500

En ambos casos el script PRIMERO consulta PostgreSQL (capa ACID) para saber qué
dispositivos existen y a qué paciente pertenecen; luego escribe en MongoDB (capa BASE).
"""
import argparse
import random
import time
from datetime import datetime, timezone

from comun import (conectar_mongo, conectar_pg, generar_evento, generar_eventos,
                   generar_teleconsultas, leer_asignaciones)

LOTE = 1000  # documentos por insert_many


def modo_masivo(n, teleconsultas):
    with conectar_pg() as pg:
        asignaciones = leer_asignaciones(pg)
        print(f"[ACID] {len(asignaciones)} asignaciones dispositivo->paciente leídas de PostgreSQL")
        t0 = time.perf_counter()
        eventos = generar_eventos(asignaciones, n)
        print(f"[GEN ] {n:,} eventos generados en {time.perf_counter() - t0:.1f} s")
        sesiones = generar_teleconsultas(pg, teleconsultas)

    cliente, mdb = conectar_mongo()
    col = mdb.eventos_telemetria
    col.delete_many({})
    t0 = time.perf_counter()
    for i in range(0, n, LOTE):
        col.insert_many(eventos[i:i + LOTE], ordered=False)  # ordered=False: si un doc falla, siguen los demás
        if (i // LOTE) % 50 == 0:
            print(f"   ... {i + LOTE:>8,} eventos insertados")
    seg = time.perf_counter() - t0
    print(f"[BASE] eventos_telemetria: {n:,} docs en {seg:.2f} s  ->  {n / seg:,.0f} eventos/s")

    mdb.sesiones_teleconsulta.delete_many({})
    t0 = time.perf_counter()
    mdb.sesiones_teleconsulta.insert_many(sesiones, ordered=False)
    print(f"[BASE] sesiones_teleconsulta: {len(sesiones)} docs en {time.perf_counter() - t0:.2f} s")
    print(f"[OK  ] Total en MongoDB: {col.count_documents({}):,} eventos, "
          f"{mdb.sesiones_teleconsulta.count_documents({})} teleconsultas")
    cliente.close()


def modo_continuo(segundos, tasa):
    with conectar_pg() as pg:
        activas = leer_asignaciones(pg, solo_activas=True)
    print(f"[ACID] Dispositivos conectados a pacientes ACTIVOS: {[a['dispositivo_id'] for a in activas]}")
    cliente, mdb = conectar_mongo()
    col = mdb.eventos_telemetria
    rng = random.Random()
    sig_id = (col.find_one(sort=[("_id", -1)]) or {"_id": 0})["_id"] + 1
    por_tick = max(1, tasa // 10)
    total, fin, ultimo_print = 0, time.time() + segundos, 0
    t_inicio = time.perf_counter()
    while time.time() < fin:
        tick = time.perf_counter()
        ahora = datetime.now(timezone.utc).replace(microsecond=0)
        lote = []
        for _ in range(por_tick):
            lote.append(generar_evento(rng, sig_id, rng.choice(activas), ahora))
            sig_id += 1
        col.insert_many(lote, ordered=False)
        total += len(lote)
        criticas = sum(1 for e in lote for a in e.get("alertas", []) if a["nivel"] == "critica")
        if int(time.perf_counter() - t_inicio) > ultimo_print:  # un mensaje por segundo
            ultimo_print = int(time.perf_counter() - t_inicio)
            print(f"  t={time.perf_counter() - t_inicio:5.1f}s  insertados={total:>7,}  alertas críticas en el último lote={criticas}")
        time.sleep(max(0, 0.1 - (time.perf_counter() - tick)))
    seg = time.perf_counter() - t_inicio
    print(f"[BASE] Flujo continuo: {total:,} eventos en {seg:.1f} s ({total / seg:,.0f} eventos/s sostenidos)")
    cliente.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Simulador de ingesta de telemetría clínica")
    sub = ap.add_subparsers(dest="modo", required=True)
    m = sub.add_parser("masivo")
    m.add_argument("--n", type=int, default=200_000)
    m.add_argument("--teleconsultas", type=int, default=400)
    c = sub.add_parser("continuo")
    c.add_argument("--segundos", type=int, default=30)
    c.add_argument("--tasa", type=int, default=500, help="eventos por segundo")
    args = ap.parse_args()
    if args.modo == "masivo":
        modo_masivo(args.n, args.teleconsultas)
    else:
        modo_continuo(args.segundos, args.tasa)
