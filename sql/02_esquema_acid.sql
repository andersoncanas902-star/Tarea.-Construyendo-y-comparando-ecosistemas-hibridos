-- =====================================================================
-- 02_esquema_acid.sql
-- Núcleo consistente (ACID) del subsistema de hospitalización
-- Grupo 6 - Bases de Datos II (G101)
--
-- Aquí vive lo que NO puede quedar "eventualmente consistente":
--   identidad del paciente, médicos, servicios, camas, hospitalizaciones,
--   diagnósticos y la asignación de dispositivos (qué sensor es de quién).
--
-- Ejecutar:
--   psql -U postgres -h localhost -d hce_core_grupo_6 -f sql/02_esquema_acid.sql
-- =====================================================================
SET client_encoding = 'UTF8';

DROP SCHEMA IF EXISTS core CASCADE;
CREATE SCHEMA core;                       -- esquema "core" = capa ACID
SET search_path = core;

-- ---------------------------------------------------------------------
-- 1. Datos maestros
-- ---------------------------------------------------------------------

-- Servicios del hospital (catálogo pequeño y estable)
CREATE TABLE servicios (
    servicio_id   SMALLSERIAL PRIMARY KEY,
    nombre        VARCHAR(60) NOT NULL UNIQUE
);

-- Identidad del paciente: la "cédula" del sistema. Fuente única de verdad.
CREATE TABLE pacientes (
    paciente_id          VARCHAR(10)  PRIMARY KEY,            -- mismo ID que usa MongoDB (PAC001...)
    tipo_documento       VARCHAR(3)   NOT NULL CHECK (tipo_documento IN ('CC','TI','CE','PA','RC')),
    numero_documento     VARCHAR(15)  NOT NULL,
    nombre_completo      VARCHAR(120) NOT NULL,
    fecha_nacimiento     DATE         NOT NULL CHECK (fecha_nacimiento <= CURRENT_DATE),
    sexo                 CHAR(1)      NOT NULL CHECK (sexo IN ('F','M')),
    eps                  VARCHAR(60)  NOT NULL,
    telefono             VARCHAR(15),
    direccion            VARCHAR(150),
    contacto_nombre      VARCHAR(120),
    contacto_parentesco  VARCHAR(30),
    contacto_telefono    VARCHAR(15),
    creado_en            TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_paciente_documento UNIQUE (tipo_documento, numero_documento)  -- no hay dos pacientes con la misma cédula
);

-- Médicos (datos maestros con registro profesional único)
CREATE TABLE medicos (
    medico_id         VARCHAR(10)  PRIMARY KEY,
    tipo_documento    VARCHAR(3)   NOT NULL,
    numero_documento  VARCHAR(15)  NOT NULL UNIQUE,
    nombre_completo   VARCHAR(120) NOT NULL,
    registro_medico   VARCHAR(20)  NOT NULL UNIQUE,
    especialidad      VARCHAR(60)  NOT NULL,
    servicio_id       SMALLINT     NOT NULL REFERENCES servicios(servicio_id),
    telefono          VARCHAR(15),
    activo            BOOLEAN      NOT NULL DEFAULT TRUE
);

-- Camas: recurso físico que NUNCA puede quedar asignado a dos pacientes
CREATE TABLE camas (
    cama_id                   VARCHAR(10) PRIMARY KEY,
    numero_cama               VARCHAR(5)  NOT NULL UNIQUE,
    piso                      SMALLINT    NOT NULL CHECK (piso BETWEEN 1 AND 20),
    servicio_id               SMALLINT    NOT NULL REFERENCES servicios(servicio_id),
    estado                    VARCHAR(15) NOT NULL DEFAULT 'libre'
                              CHECK (estado IN ('libre','ocupada','mantenimiento')),
    hospitalizacion_actual_id VARCHAR(10)  -- la FK se agrega más abajo (referencia circular)
);

-- ---------------------------------------------------------------------
-- 2. Datos transaccionales críticos
-- ---------------------------------------------------------------------

CREATE TABLE hospitalizaciones (
    hospitalizacion_id  VARCHAR(10) PRIMARY KEY,
    paciente_id         VARCHAR(10) NOT NULL REFERENCES pacientes(paciente_id),
    medico_id           VARCHAR(10) NOT NULL REFERENCES medicos(medico_id),
    cama_id             VARCHAR(10) NOT NULL REFERENCES camas(cama_id),
    servicio_id         SMALLINT    NOT NULL REFERENCES servicios(servicio_id),
    fecha_admision      TIMESTAMPTZ NOT NULL,
    motivo_admision     TEXT        NOT NULL,
    estado              VARCHAR(15) NOT NULL DEFAULT 'activa'
                        CHECK (estado IN ('activa','dada_de_alta')),
    fecha_alta          TIMESTAMPTZ,
    tipo_alta           VARCHAR(20) CHECK (tipo_alta IN ('mejoria','remision','voluntaria','fallecimiento')),
    -- Regla de negocio: si está de alta debe tener fecha, y la fecha no puede ser antes del ingreso
    CONSTRAINT ck_alta_coherente CHECK (
        (estado = 'activa'       AND fecha_alta IS NULL) OR
        (estado = 'dada_de_alta' AND fecha_alta IS NOT NULL AND fecha_alta >= fecha_admision)
    )
);

-- Un paciente solo puede tener UNA hospitalización activa a la vez
CREATE UNIQUE INDEX uq_una_hosp_activa_por_paciente
    ON hospitalizaciones (paciente_id) WHERE estado = 'activa';

-- Una cama solo puede estar en UNA hospitalización activa a la vez
CREATE UNIQUE INDEX uq_una_hosp_activa_por_cama
    ON hospitalizaciones (cama_id) WHERE estado = 'activa';

-- Ahora sí la FK circular cama -> hospitalización actual (diferible al final de la transacción)
ALTER TABLE camas
    ADD CONSTRAINT fk_cama_hosp_actual
    FOREIGN KEY (hospitalizacion_actual_id) REFERENCES hospitalizaciones(hospitalizacion_id)
    DEFERRABLE INITIALLY DEFERRED;

-- Diagnósticos CIE-10 de cada hospitalización
CREATE TABLE diagnosticos_hospitalizacion (
    hospitalizacion_id VARCHAR(10) NOT NULL REFERENCES hospitalizaciones(hospitalizacion_id) ON DELETE CASCADE,
    codigo_cie10       VARCHAR(8)  NOT NULL,
    descripcion        VARCHAR(150) NOT NULL,
    tipo               VARCHAR(12) NOT NULL CHECK (tipo IN ('principal','secundario')),
    PRIMARY KEY (hospitalizacion_id, codigo_cie10)
);

-- ---------------------------------------------------------------------
-- 3. Dispositivos: el "puente" entre las dos capas
--    MongoDB recibe millones de lecturas con un dispositivo_id;
--    PostgreSQL garantiza a qué paciente pertenece ese dispositivo.
-- ---------------------------------------------------------------------

CREATE TABLE dispositivos (
    dispositivo_id   VARCHAR(12) PRIMARY KEY,
    tipo_dispositivo VARCHAR(30) NOT NULL CHECK (tipo_dispositivo IN
                     ('monitor_multiparametro','pulsera_wearable','bomba_infusion','glucometro','capnografo')),
    modelo           VARCHAR(40) NOT NULL,
    serial           VARCHAR(30) NOT NULL UNIQUE,
    activo           BOOLEAN     NOT NULL DEFAULT TRUE
);

CREATE TABLE asignaciones_dispositivo (
    asignacion_id      SERIAL      PRIMARY KEY,
    dispositivo_id     VARCHAR(12) NOT NULL REFERENCES dispositivos(dispositivo_id),
    hospitalizacion_id VARCHAR(10) NOT NULL REFERENCES hospitalizaciones(hospitalizacion_id),
    paciente_id        VARCHAR(10) NOT NULL REFERENCES pacientes(paciente_id),
    desde              TIMESTAMPTZ NOT NULL,
    hasta              TIMESTAMPTZ,
    CHECK (hasta IS NULL OR hasta >= desde)
);

-- Un dispositivo no puede estar conectado a dos pacientes al mismo tiempo
CREATE UNIQUE INDEX uq_dispositivo_asignacion_vigente
    ON asignaciones_dispositivo (dispositivo_id) WHERE hasta IS NULL;

-- Índices para las búsquedas más comunes desde la capa de integración
CREATE INDEX ix_hosp_paciente   ON hospitalizaciones (paciente_id);
CREATE INDEX ix_asig_paciente   ON asignaciones_dispositivo (paciente_id);

-- ---------------------------------------------------------------------
-- 4. Vista de contexto: lo que la aplicación híbrida le pide a PostgreSQL
--    para "enriquecer" los eventos que vienen de MongoDB.
-- ---------------------------------------------------------------------
CREATE VIEW v_contexto_paciente AS
SELECT p.paciente_id,
       p.tipo_documento || ' ' || p.numero_documento AS documento,
       p.nombre_completo,
       date_part('year', age(p.fecha_nacimiento))::int AS edad,
       p.eps,
       h.hospitalizacion_id,
       h.estado          AS estado_hospitalizacion,
       s.nombre          AS servicio,
       c.numero_cama,
       m.nombre_completo AS medico_tratante,
       p.contacto_nombre,
       p.contacto_telefono
FROM pacientes p
LEFT JOIN hospitalizaciones h ON h.paciente_id = p.paciente_id
LEFT JOIN servicios s ON s.servicio_id = h.servicio_id
LEFT JOIN camas c     ON c.cama_id     = h.cama_id
LEFT JOIN medicos m   ON m.medico_id   = h.medico_id;

-- ---------------------------------------------------------------------
-- 5. Procedimientos transaccionales (todo o nada)
-- ---------------------------------------------------------------------

-- Admitir un paciente: crea la hospitalización y ocupa la cama en UNA sola transacción.
CREATE OR REPLACE PROCEDURE sp_admitir_paciente(
    p_hosp_id   VARCHAR, p_paciente_id VARCHAR, p_medico_id VARCHAR,
    p_cama_id   VARCHAR, p_motivo      TEXT)
LANGUAGE plpgsql
SET search_path = core      -- el procedimiento siempre trabaja sobre el esquema core
AS $$
DECLARE
    v_estado_cama VARCHAR;
    v_servicio    SMALLINT;
BEGIN
    -- FOR UPDATE bloquea la fila de la cama: si dos admisiones llegan al mismo
    -- tiempo por la misma cama, la segunda espera y luego ve que ya está ocupada.
    SELECT estado, servicio_id INTO v_estado_cama, v_servicio
    FROM camas WHERE cama_id = p_cama_id FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'La cama % no existe', p_cama_id;
    END IF;
    IF v_estado_cama <> 'libre' THEN
        RAISE EXCEPTION 'La cama % no está libre (estado actual: %)', p_cama_id, v_estado_cama;
    END IF;

    INSERT INTO hospitalizaciones (hospitalizacion_id, paciente_id, medico_id, cama_id,
                                   servicio_id, fecha_admision, motivo_admision, estado)
    VALUES (p_hosp_id, p_paciente_id, p_medico_id, p_cama_id,
            v_servicio, now(), p_motivo, 'activa');

    UPDATE camas SET estado = 'ocupada', hospitalizacion_actual_id = p_hosp_id
    WHERE cama_id = p_cama_id;
END;
$$;

-- Dar de alta: cierra la hospitalización, libera la cama y desconecta los dispositivos.
CREATE OR REPLACE PROCEDURE sp_dar_alta(p_hosp_id VARCHAR, p_tipo_alta VARCHAR)
LANGUAGE plpgsql
SET search_path = core
AS $$
DECLARE
    v_cama VARCHAR;
BEGIN
    UPDATE hospitalizaciones
       SET estado = 'dada_de_alta', fecha_alta = now(), tipo_alta = p_tipo_alta
     WHERE hospitalizacion_id = p_hosp_id AND estado = 'activa'
    RETURNING cama_id INTO v_cama;

    IF v_cama IS NULL THEN
        RAISE EXCEPTION 'La hospitalización % no existe o no está activa', p_hosp_id;
    END IF;

    UPDATE camas SET estado = 'libre', hospitalizacion_actual_id = NULL WHERE cama_id = v_cama;
    UPDATE asignaciones_dispositivo SET hasta = now()
     WHERE hospitalizacion_id = p_hosp_id AND hasta IS NULL;
END;
$$;
