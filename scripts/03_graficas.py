"""
03_graficas.py - Genera las gráficas del análisis comparativo a partir de resultados/metricas.json
Grupo 6 - Bases de Datos II (G101)
Uso: py scripts/03_graficas.py   -> crea capturas/grafica_*.png
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
M = json.loads((RAIZ / "resultados" / "metricas.json").read_text(encoding="utf-8"))
OUT = RAIZ / "capturas"
OUT.mkdir(exist_ok=True)

# Colores: identidad del motor (MongoDB / PostgreSQL) y fase (sin / con índices)
C_MONGO, C_PG = "#1baf7a", "#eb6834"
C_SIN, C_CON = "#c9c7bf", "#2a78d6"
TXT, TXT2, GRID = "#0b0b0b", "#52514e", "#e6e5e0"
NOMBRES = {"mongo": "MongoDB (colección)", "mongo_ts": "MongoDB (time series)",
           "pg_columnas": "PostgreSQL (columnas)", "pg_jsonb": "PostgreSQL (JSONB)",
           "pg_copy": "PostgreSQL (COPY)", "hibrida_mongo+pg": "Híbrida MongoDB + PostgreSQL",
           "solo_pg": "Solo PostgreSQL (3 JOIN)"}

plt.rcParams.update({"font.family": "Segoe UI", "font.size": 10, "axes.edgecolor": GRID,
                     "axes.labelcolor": TXT2, "xtick.color": TXT2, "ytick.color": TXT,
                     "axes.spines.top": False, "axes.spines.right": False})


def color_motor(k):
    return C_MONGO if k.startswith("mongo") or k.startswith("hibrida") else C_PG


def base(titulo, subtitulo, alto=3.6):
    fig, ax = plt.subplots(figsize=(8, alto), dpi=200)
    fig.text(0.01, 0.97, titulo, fontsize=13, fontweight="bold", color=TXT, va="top")
    fig.text(0.01, 0.90, subtitulo, fontsize=9.5, color=TXT2, va="top")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    return fig, ax


def leyenda_motor(ax, loc="lower right"):
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=C_MONGO, label="MongoDB (capa BASE)"),
                       Patch(color=C_PG, label="PostgreSQL (capa ACID)")],
              loc=loc, frameon=False, fontsize=9)


def guardar(fig, nombre):
    fig.subplots_adjust(top=0.80, left=0.27, right=0.95, bottom=0.14)
    fig.savefig(OUT / nombre, facecolor="white")
    plt.close(fig)
    print("  ->", OUT / nombre)


# 1. Ingesta masiva -------------------------------------------------------------
ing = M["O1_ingesta"]
orden = sorted(ing, key=lambda k: ing[k]["eventos_por_s"])
fig, ax = base(f"O1. Ingesta masiva de {M['eventos']:,} eventos".replace(",", "."),
               "Eventos insertados por segundo (más es mejor). Lotes de 1.000; mismo equipo y mismos datos.")
vals = [ing[k]["eventos_por_s"] for k in orden]
ax.barh([NOMBRES[k] for k in orden], vals, color=[color_motor(k) for k in orden], height=0.6)
for i, k in enumerate(orden):
    ax.text(vals[i] + max(vals) * 0.01, i, f"{vals[i]:,} ev/s  ({ing[k]['segundos']:.1f} s)".replace(",", "."),
            va="center", fontsize=9, color=TXT)
ax.set_xlim(0, max(vals) * 1.3)
ax.set_xlabel("eventos por segundo")
leyenda_motor(ax)
guardar(fig, "grafica_01_ingesta.png")


# 2-4. Consultas sin / con índices ----------------------------------------------
def grafica_fases(op, titulo, sub, nombre):
    datos = M["consultas"][op]
    motores = list(datos["sin_indices"].keys())[::-1]
    fig, ax = base(titulo, sub, alto=0.75 * len(motores) + 1.6)
    y = range(len(motores))
    h = 0.36
    sin = [datos["sin_indices"][m]["mediana_ms"] for m in motores]
    con = [datos["con_indices"][m]["mediana_ms"] for m in motores]
    ax.barh([i + h / 2 for i in y], sin, height=h, color=C_SIN, label="Sin índices secundarios")
    ax.barh([i - h / 2 for i in y], con, height=h, color=C_CON, label="Con índices sugeridos")
    tope = max(sin + con)
    for i in y:
        ax.text(sin[i] + tope * 0.01, i + h / 2, f"{sin[i]:.1f} ms", va="center", fontsize=8.5, color=TXT2)
        ax.text(con[i] + tope * 0.01, i - h / 2, f"{con[i]:.1f} ms", va="center", fontsize=8.5, color=TXT)
    ax.set_yticks(list(y))
    ax.set_yticklabels([NOMBRES[m] for m in motores])
    ax.set_xlim(0, tope * 1.2)
    ax.set_xlabel("mediana en milisegundos (menos es mejor)")
    # leyenda debajo del eje para que nunca tape una barra
    fig.legend(*ax.get_legend_handles_labels(), loc="lower center", ncol=2, frameon=False, fontsize=9)
    fig.subplots_adjust(top=0.80, left=0.27, right=0.95, bottom=0.27)
    fig.savefig(OUT / nombre, facecolor="white")
    plt.close(fig)
    print("  ->", OUT / nombre)


grafica_fases("O2_consulta_puntual", "O2. Consulta puntual: lecturas de un paciente en 6 horas",
              "483 lecturas de PAC003. Mediana de 30 ejecuciones.", "grafica_02_consulta_puntual.png")
grafica_fases("O3_agregacion", "O3. Agregación: resumen de monitores por paciente",
              "Promedio FC, mínimo SpO2 y máximo PAS sobre ~90.000 lecturas. Mediana de 7 ejecuciones.",
              "grafica_03_agregacion.png")
grafica_fases("O4_alertas_con_identidad", "O4. Alertas críticas del último día + identidad del paciente",
              "Híbrida: MongoDB busca alertas y PostgreSQL pone nombre, cama y médico. Mediana de 20 ejecuciones.",
              "grafica_04_alertas_hibridas.png")

# 5. Almacenamiento ----------------------------------------------------------------
st = M["O8_almacenamiento"]
filas = [("MongoDB (colección)", st["mongo:eventos_telemetria"], C_MONGO),
         ("MongoDB (time series)", st["mongo:eventos_telemetria_ts"], C_MONGO),
         ("PostgreSQL (columnas + alertas)",
          {"datos_mb": st["pg:eventos_telemetria"]["datos_mb"] + st["pg:alertas_evento"]["datos_mb"],
           "indices_mb": st["pg:eventos_telemetria"]["indices_mb"] + st["pg:alertas_evento"]["indices_mb"]}, C_PG),
         ("PostgreSQL (JSONB)", st["pg:eventos_jsonb"], C_PG)][::-1]
fig, ax = base("O8. Espacio en disco para los mismos 200.000 eventos",
               "Datos + índices en MB (menos es mejor). MongoDB comprime con WiredTiger (snappy).")
for i, (n, v, c) in enumerate(filas):
    ax.barh(i, v["datos_mb"], color=c, height=0.6)
    ax.barh(i, v["indices_mb"], left=v["datos_mb"] + 0.4, color=c, alpha=0.45, height=0.6)
    tot = v["datos_mb"] + v["indices_mb"]
    ax.text(tot + 1.5, i, f"{tot:.1f} MB  (datos {v['datos_mb']:.1f} + índices {v['indices_mb']:.1f})",
            va="center", fontsize=8.5, color=TXT)
ax.set_yticks(range(len(filas)))
ax.set_yticklabels([f[0] for f in filas])
ax.set_xlim(0, max(f[1]["datos_mb"] + f[1]["indices_mb"] for f in filas) * 1.55)
ax.set_xlabel("MB en disco (tono fuerte = datos, tono claro = índices)")
leyenda_motor(ax, "upper right")
guardar(fig, "grafica_05_almacenamiento.png")
print("Gráficas generadas.")
