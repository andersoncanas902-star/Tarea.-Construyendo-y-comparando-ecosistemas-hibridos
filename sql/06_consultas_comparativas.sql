-- =====================================================================
-- 06_consultas_comparativas.sql
-- Las MISMAS preguntas que nosql/03_consultas_comparativas.js, en PostgreSQL.
--   psql -U postgres -h localhost -d hce_core_grupo_6 -f sql/06_consultas_comparativas.sql
-- (Requiere haber corrido scripts/02_benchmark_comparativo.py, que llena el esquema comparativo)
-- =====================================================================
SET client_encoding = 'UTF8';
SET search_path = comparativo, core;
\timing on

-- ---------------------------------------------------------------------
-- O2. Consulta puntual: lecturas de PAC003 entre 18:00 y 24:00 UTC del 21-nov.
-- Para devolver el "evento completo" hay que reconstruir el arreglo de alertas
-- desde la tabla hija (en MongoDB ya viene dentro del documento).
-- ---------------------------------------------------------------------
\echo '=== O2. Lecturas de PAC003 (3 más recientes) ==='
SELECT e.evento_id, e.ts, e.tipo_dispositivo, e.fc_lpm, e.spo2_pct, e.glucosa_mg_dl,
       (SELECT json_agg(json_build_object('codigo', a.codigo, 'nivel', a.nivel) ORDER BY a.orden)
          FROM alertas_evento a WHERE a.evento_id = e.evento_id) AS alertas
FROM eventos_telemetria e
WHERE e.paciente_id = 'PAC003'
  AND e.ts >= '2026-11-21 18:00+00' AND e.ts < '2026-11-22 00:00+00'
ORDER BY e.ts DESC
LIMIT 3;

\echo '--- Plan de ejecución de O2 (busque Seq Scan vs Index Scan) ---'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT * FROM eventos_telemetria
WHERE paciente_id = 'PAC003' AND ts >= '2026-11-21 18:00+00' AND ts < '2026-11-22 00:00+00'
ORDER BY ts DESC;

-- ---------------------------------------------------------------------
-- O3. Agregación clínica: resumen de monitores por paciente
-- ---------------------------------------------------------------------
\echo '=== O3. Resumen de monitores multiparámetro por paciente ==='
SELECT paciente_id,
       count(*)                 AS lecturas,
       round(avg(fc_lpm), 1)    AS fc_prom,
       min(spo2_pct)            AS spo2_min,
       max(pa_sistolica)        AS pas_max
FROM eventos_telemetria
WHERE tipo_dispositivo = 'monitor_multiparametro'
GROUP BY paciente_id
ORDER BY paciente_id;

-- La misma agregación sobre JSONB: hay que extraer y convertir cada campo (más lento y más verboso)
\echo '=== O3 (variante JSONB) ==='
SELECT paciente_id, count(*) AS lecturas,
       round(avg((doc->'lecturas'->>'fc_lpm')::int), 1) AS fc_prom,
       min((doc->'lecturas'->>'spo2_pct')::int)         AS spo2_min
FROM eventos_jsonb
WHERE doc->>'tipo_dispositivo' = 'monitor_multiparametro'
GROUP BY paciente_id ORDER BY paciente_id;

-- ---------------------------------------------------------------------
-- O4. Alertas críticas del último día + identidad del paciente (todo en PostgreSQL).
-- Requiere 3 JOIN: evento -> alerta (tabla hija) -> vista de contexto (paciente, cama, médico).
-- ---------------------------------------------------------------------
\echo '=== O4. Alertas críticas con identidad (solo PostgreSQL) ==='
SELECT v.nombre_completo, v.numero_cama, v.medico_tratante,
       e.ts, e.dispositivo_id, a.codigo, a.mensaje
FROM eventos_telemetria e
JOIN alertas_evento a        ON a.evento_id = e.evento_id
JOIN core.v_contexto_paciente v ON v.paciente_id = e.paciente_id AND v.estado_hospitalizacion = 'activa'
WHERE e.ts >= '2026-11-21 00:00+00' AND a.nivel = 'critica'
ORDER BY e.ts DESC
LIMIT 10;

-- ---------------------------------------------------------------------
-- Equivalente SQL del pipeline sugerido con IA: tendencia horaria con
-- promedio móvil de 3 horas (función de ventana) y conteo de alertas.
-- ---------------------------------------------------------------------
\echo '=== Pipeline IA en SQL: tendencia horaria de PAC003 ==='
WITH por_hora AS (
    SELECT date_trunc('hour', e.ts)          AS hora,
           avg(e.fc_lpm)                     AS fc_prom,
           avg(e.spo2_pct)                   AS spo2_prom,
           count(a.evento_id)                AS alertas
    FROM eventos_telemetria e
    LEFT JOIN alertas_evento a ON a.evento_id = e.evento_id
    WHERE e.paciente_id = 'PAC003' AND e.tipo_dispositivo = 'monitor_multiparametro'
      AND e.ts >= '2026-11-21 00:00+00' AND e.ts < '2026-11-22 00:00+00'
    GROUP BY 1
)
SELECT hora AT TIME ZONE 'UTC' AS hora_utc,
       round(fc_prom, 1)   AS fc_prom,
       round(avg(fc_prom) OVER (ORDER BY hora ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 1) AS fc_movil_3h,
       round(spo2_prom, 1) AS spo2_prom,
       alertas
FROM por_hora
ORDER BY hora
LIMIT 8;

-- ---------------------------------------------------------------------
-- Índices sugeridos (el benchmark ya los crea; IF NOT EXISTS evita errores)
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS ix_ev_paciente_ts ON eventos_telemetria (paciente_id, ts DESC);
CREATE INDEX IF NOT EXISTS ix_ev_ts          ON eventos_telemetria (ts DESC);
CREATE INDEX IF NOT EXISTS ix_alerta_critica ON alertas_evento (evento_id) WHERE nivel = 'critica';

-- Tamaño en disco de cada tabla (costo de almacenamiento)
\echo '=== Tamaño de las tablas comparativas ==='
SELECT relname AS tabla,
       pg_size_pretty(pg_table_size(c.oid))   AS datos,
       pg_size_pretty(pg_indexes_size(c.oid)) AS indices
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'comparativo' AND c.relkind = 'r'
ORDER BY pg_table_size(c.oid) DESC;
