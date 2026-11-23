// =====================================================================
// 01_crear_colecciones.js
// Capa BASE del ecosistema híbrido (MongoDB)
// Grupo 6 - Bases de Datos II (G101)
//
// Ejecutar:   mongosh --file nosql/01_crear_colecciones.js
//
// Aquí vive lo que llega en volumen masivo y con forma variable:
//   - eventos_telemetria     : lecturas de monitores, pulseras, bombas, glucómetros...
//   - eventos_telemetria_ts  : la misma telemetría en una colección "time series"
//   - sesiones_teleconsulta  : logs de teleconsultas post-alta (documentos con arreglos)
//
// IMPORTANTE: aquí NO se guarda la identidad del paciente (nombre, cédula, EPS).
// Solo se guarda paciente_id / dispositivo_id, que apuntan a PostgreSQL (capa ACID).
// =====================================================================

const BD = "hce_telemetria_grupo_6";
const tdb = db.getSiblingDB(BD);

// Empezar limpio (el benchmark vuelve a llamar este script antes de cada corrida)
tdb.dropDatabase();

// ---------------------------------------------------------------------
// 1. eventos_telemetria: esquema FLEXIBLE pero con un mínimo obligatorio.
//    Solo exigimos los campos que sirven para unir con la capa ACID y para
//    ordenar en el tiempo. El contenido de "lecturas" puede variar libremente.
// ---------------------------------------------------------------------
tdb.createCollection("eventos_telemetria", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["paciente_id", "hospitalizacion_id", "dispositivo_id", "tipo_dispositivo", "ts", "lecturas"],
      properties: {
        paciente_id:        { bsonType: "string", pattern: "^PAC[0-9]{3}$", description: "ID del paciente en PostgreSQL" },
        hospitalizacion_id: { bsonType: "string" },
        dispositivo_id:     { bsonType: "string", description: "ID del dispositivo registrado en PostgreSQL" },
        tipo_dispositivo:   { bsonType: "string" },
        ts:                 { bsonType: "date",   description: "Momento de la lectura" },
        lecturas:           { bsonType: "object", description: "Campos variables según el dispositivo" },
        alertas:            { bsonType: "array" },
        meta:               { bsonType: "object" }
      }
      // OJO: no ponemos additionalProperties:false -> se pueden agregar campos nuevos sin migrar
    }
  },
  validationLevel: "moderate",   // valida inserciones y documentos que ya cumplían
  validationAction: "error"      // si falta un campo obligatorio, se rechaza
});

// ---------------------------------------------------------------------
// 2. eventos_telemetria_ts: colección de series de tiempo (MongoDB 5+).
//    Agrupa internamente las lecturas por dispositivo y por intervalos de
//    tiempo -> ocupa menos disco y acelera consultas por rango de fechas.
//    expireAfterSeconds = retención automática de 2 años (política de datos crudos).
// ---------------------------------------------------------------------
tdb.createCollection("eventos_telemetria_ts", {
  timeseries: {
    timeField: "ts",          // campo de tiempo
    metaField: "origen",      // {paciente_id, hospitalizacion_id, dispositivo_id, tipo_dispositivo}
    granularity: "seconds"
  },
  expireAfterSeconds: 60 * 60 * 24 * 730
});

// ---------------------------------------------------------------------
// 3. sesiones_teleconsulta: documentos con subdocumentos y arreglos de logs.
// ---------------------------------------------------------------------
tdb.createCollection("sesiones_teleconsulta", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["paciente_id", "medico_id", "inicio", "estado"],
      properties: {
        paciente_id: { bsonType: "string" },
        medico_id:   { bsonType: "string" },
        inicio:      { bsonType: "date" },
        estado:      { enum: ["completada", "interrumpida", "no_asistio"] },
        eventos_conexion: { bsonType: "array" }
      }
    }
  },
  validationLevel: "moderate"
});

// Índices de teleconsulta (los de telemetría los crea el benchmark DESPUÉS de medir sin índice)
tdb.sesiones_teleconsulta.createIndex({ paciente_id: 1, inicio: -1 });

print("Base " + BD + " creada con colecciones:");
printjson(tdb.getCollectionNames().sort());
