// =====================================================================
// 02_documentos_ejemplo.js
// Documentos JSON de ejemplo de la capa BASE + demostración de flexibilidad.
// Ejecutar DESPUÉS de cargar los datos:  mongosh --file nosql/02_documentos_ejemplo.js
// =====================================================================
const tdb = db.getSiblingDB("hce_telemetria_grupo_6");

print("\n=== 1. Tres documentos reales con FORMAS DISTINTAS en la misma colección ===");
["monitor_multiparametro", "bomba_infusion", "glucometro"].forEach(tipo => {
  printjson(tdb.eventos_telemetria.findOne({ tipo_dispositivo: tipo, alertas: { $exists: true } }));
});

print("\n=== 2. Una sesión de teleconsulta (subdocumentos + arreglo de logs) ===");
printjson(tdb.sesiones_teleconsulta.findOne({ estado: "completada", signos_reportados: { $exists: true } }));

print("\n=== 3. Flexibilidad: llega un sensor NUEVO (capnógrafo) con un campo nuevo ===");
// No hay ALTER TABLE ni migración: el documento simplemente trae su campo etco2_mmhg.
const r = tdb.eventos_telemetria.insertOne({
  _id: 90000001,
  paciente_id: "PAC003", hospitalizacion_id: "HOSP003",
  dispositivo_id: "CAP-H03", tipo_dispositivo: "capnografo",
  ts: new Date(),
  lecturas: { etco2_mmhg: 38, fr_rpm: 18, curva_valida: true },   // campos que nunca habían existido
  meta: { bateria_pct: 95, firmware: "v1.0.0", red: "wifi" }
});
printjson(r);

print("\n=== 4. El validador $jsonSchema SÍ protege lo mínimo: sin paciente_id se rechaza ===");
try {
  tdb.eventos_telemetria.insertOne({ tipo_dispositivo: "monitor_multiparametro", lecturas: { fc_lpm: 80 } });
} catch (e) {
  print("RECHAZADO -> " + e.message);
}

print("\n=== 5. Pero NO conoce a PostgreSQL: un paciente inexistente pasa (consistencia la da la app) ===");
const h = tdb.eventos_telemetria.insertOne({
  _id: 90000002, paciente_id: "PAC999", hospitalizacion_id: "HOSP999", dispositivo_id: "MON-FALSO",
  tipo_dispositivo: "monitor_multiparametro", ts: new Date(), lecturas: { fc_lpm: 80 }
});
printjson(h);
print("Por eso el simulador de ingesta consulta core.asignaciones_dispositivo en PostgreSQL antes de escribir.");

// Limpieza de los documentos de demostración
tdb.eventos_telemetria.deleteMany({ _id: { $in: [90000001, 90000002] } });
print("\nDocumentos de demostración eliminados.");
