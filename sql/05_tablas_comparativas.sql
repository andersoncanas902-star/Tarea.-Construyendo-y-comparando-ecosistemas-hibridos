-- =====================================================================
-- 05_tablas_comparativas.sql
-- Tablas SOLO para el análisis comparativo: guardan la MISMA telemetría que
-- MongoDB, pero "a la manera relacional", para medir qué pasa si todo se
-- quisiera meter en la capa ACID.
--
--   comparativo.eventos_telemetria  -> columnas fijas (esquema rígido)
--   comparativo.alertas_evento      -> tabla hija para el arreglo de alertas (1:N)
--   comparativo.eventos_jsonb       -> alternativa híbrida dentro de PostgreSQL (JSONB)
--
-- El script de benchmark (scripts/02_benchmark_comparativo.py) lo ejecuta
-- automáticamente antes de cada corrida.
-- =====================================================================
SET client_encoding = 'UTF8';

DROP SCHEMA IF EXISTS comparativo CASCADE;
CREATE SCHEMA comparativo;
SET search_path = comparativo;

-- Una columna por cada lectura posible. Cada tipo de dispositivo llena solo
-- algunas; el resto queda en NULL (síntoma típico de forzar datos variables
-- en un esquema rígido).
CREATE TABLE eventos_telemetria (
    evento_id           BIGINT       PRIMARY KEY,
    paciente_id         VARCHAR(10)  NOT NULL REFERENCES core.pacientes(paciente_id),
    hospitalizacion_id  VARCHAR(10)  NOT NULL REFERENCES core.hospitalizaciones(hospitalizacion_id),
    dispositivo_id      VARCHAR(12)  NOT NULL REFERENCES core.dispositivos(dispositivo_id),
    tipo_dispositivo    VARCHAR(30)  NOT NULL,
    ts                  TIMESTAMPTZ  NOT NULL,
    -- monitor multiparámetro
    fc_lpm              SMALLINT,
    spo2_pct            SMALLINT,
    pa_sistolica        SMALLINT,
    pa_diastolica       SMALLINT,
    fr_rpm              SMALLINT,
    temperatura_c       NUMERIC(4,1),
    -- pulsera wearable
    pasos               INTEGER,
    temp_piel_c         NUMERIC(4,1),
    calidad_sueno       VARCHAR(10),
    -- bomba de infusión
    medicamento         VARCHAR(40),
    velocidad_ml_h      NUMERIC(6,1),
    volumen_restante_ml NUMERIC(7,1),
    -- glucómetro
    glucosa_mg_dl       SMALLINT,
    momento_toma        VARCHAR(20),
    -- metadatos del dispositivo
    bateria_pct         SMALLINT,
    firmware            VARCHAR(12),
    red                 VARCHAR(8)
);

-- Las alertas son una lista de tamaño variable: en relacional necesitan tabla aparte.
CREATE TABLE alertas_evento (
    evento_id  BIGINT      NOT NULL REFERENCES eventos_telemetria(evento_id) ON DELETE CASCADE,
    orden      SMALLINT    NOT NULL,
    codigo     VARCHAR(20) NOT NULL,
    nivel      VARCHAR(12) NOT NULL CHECK (nivel IN ('info','advertencia','critica')),
    mensaje    VARCHAR(120),
    PRIMARY KEY (evento_id, orden)
);

-- Alternativa: el documento completo en JSONB + columnas clave para indexar.
CREATE TABLE eventos_jsonb (
    evento_id    BIGINT      PRIMARY KEY,
    paciente_id  VARCHAR(10) NOT NULL,
    ts           TIMESTAMPTZ NOT NULL,
    doc          JSONB       NOT NULL
);

-- NOTA: los índices secundarios NO se crean aquí a propósito.
-- El benchmark mide primero la consulta SIN índice y luego crea los índices
-- sugeridos (ver sql/06_consultas_comparativas.sql, sección "Índices").
