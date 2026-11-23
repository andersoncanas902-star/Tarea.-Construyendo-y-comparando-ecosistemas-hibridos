// =====================================================================
// 03_consultas_comparativas.js
// Las MISMAS preguntas que sql/06_consultas_comparativas.sql, pero en MongoDB.
// Ejecutar:  mongosh --file nosql/03_consultas_comparativas.js
// (Requiere haber corrido scripts/02_benchmark_comparativo.py o 01_simular_ingesta.py)
// =====================================================================
const tdb = db.getSiblingDB("hce_telemetria_grupo_6");
const desde = ISODate("2026-11-21T18:00:00Z"), hasta = ISODate("2026-11-22T00:00:00Z");

// ---------------------------------------------------------------------
// O2. Consulta puntual: lecturas de PAC003 en las últimas 6 horas simuladas
// ---------------------------------------------------------------------
print("\n=== O2. Lecturas de PAC003 entre 18:00 y 24:00 del 21-nov (3 más recientes) ===");
const filtroO2 = { paciente_id: "PAC003", ts: { $gte: desde, $lt: hasta } };
printjson(tdb.eventos_telemetria.find(filtroO2, { lecturas: 1, ts: 1, tipo_dispositivo: 1 })
  .sort({ ts: -1 }).limit(3).toArray());

// Plan de ejecución: ¿recorre toda la colección (COLLSCAN) o usa índice (IXSCAN)?
const ex = tdb.eventos_telemetria.find(filtroO2).sort({ ts: -1 }).explain("executionStats");
print("Docs examinados: " + ex.executionStats.totalDocsExamined +
      " | devueltos: " + ex.executionStats.nReturned +
      " | ms: " + ex.executionStats.executionTimeMillis);

// ---------------------------------------------------------------------
// O3. Agregación clínica: resumen de monitores por paciente
// ---------------------------------------------------------------------
print("\n=== O3. Resumen de monitores multiparámetro por paciente ===");
printjson(tdb.eventos_telemetria.aggregate([
  { $match: { tipo_dispositivo: "monitor_multiparametro" } },          // 1) solo monitores
  { $group: {                                                          // 2) un grupo por paciente
      _id: "$paciente_id",
      lecturas: { $sum: 1 },
      fc_prom:  { $avg: "$lecturas.fc_lpm" },
      spo2_min: { $min: "$lecturas.spo2_pct" },
      pas_max:  { $max: "$lecturas.pa_sistolica" } } },
  { $project: { lecturas: 1, spo2_min: 1, pas_max: 1, fc_prom: { $round: ["$fc_prom", 1] } } },
  { $sort: { _id: 1 } }
]).toArray());

// ---------------------------------------------------------------------
// O4. Alertas críticas del último día (parte BASE de la consulta híbrida).
//     La identidad (nombre, cama, médico) la pone PostgreSQL: ver scripts/04_consulta_hibrida.py
// ---------------------------------------------------------------------
print("\n=== O4. Alertas críticas desde el 21-nov 00:00 (solo IDs; la identidad está en PostgreSQL) ===");
printjson(tdb.eventos_telemetria.aggregate([
  { $match: { ts: { $gte: ISODate("2026-11-21T00:00:00Z") }, "alertas.nivel": "critica" } },
  { $unwind: "$alertas" },                                 // un documento por alerta
  { $match: { "alertas.nivel": "critica" } },
  { $group: { _id: { paciente: "$paciente_id", alerta: "$alertas.codigo" }, veces: { $sum: 1 },
              ultima: { $max: "$ts" } } },
  { $sort: { veces: -1 } }
]).toArray());

// ---------------------------------------------------------------------
// Pipeline complejo sugerido con IA: tendencia horaria con promedio móvil
// de 3 horas y conteo de alertas, para PAC003 en las últimas 24 h.
// ---------------------------------------------------------------------
print("\n=== Pipeline IA. Tendencia horaria de PAC003 (FC promedio, promedio móvil 3 h, alertas) ===");
printjson(tdb.eventos_telemetria.aggregate([
  { $match: { paciente_id: "PAC003", tipo_dispositivo: "monitor_multiparametro",
              ts: { $gte: ISODate("2026-11-21T00:00:00Z"), $lt: hasta } } },
  { $group: { _id: { $dateTrunc: { date: "$ts", unit: "hour" } },          // agrupa por hora
              fc_prom: { $avg: "$lecturas.fc_lpm" },
              spo2_prom: { $avg: "$lecturas.spo2_pct" },
              alertas: { $sum: { $size: { $ifNull: ["$alertas", []] } } } } },
  { $sort: { _id: 1 } },
  { $setWindowFields: {                                                    // ventana deslizante
      sortBy: { _id: 1 },
      output: { fc_movil_3h: { $avg: "$fc_prom", window: { documents: [-2, 0] } } } } },
  { $project: { _id: 0, hora: "$_id", fc_prom: { $round: ["$fc_prom", 1] },
                fc_movil_3h: { $round: ["$fc_movil_3h", 1] },
                spo2_prom: { $round: ["$spo2_prom", 1] }, alertas: 1 } },
  { $limit: 8 }
]).toArray());

// ---------------------------------------------------------------------
// Índices sugeridos (los crea también el benchmark). createIndex no falla si ya existen.
// ---------------------------------------------------------------------
print("\n=== Índices de eventos_telemetria ===");
tdb.eventos_telemetria.createIndex({ paciente_id: 1, ts: -1 }, { name: "ix_paciente_ts" });
tdb.eventos_telemetria.createIndex({ "alertas.nivel": 1, ts: -1 }, { name: "ix_alerta_nivel_ts" });
printjson(tdb.eventos_telemetria.getIndexes().map(i => i.name));
