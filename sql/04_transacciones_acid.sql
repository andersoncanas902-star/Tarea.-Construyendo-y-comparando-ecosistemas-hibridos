-- =====================================================================
-- 04_transacciones_acid.sql
-- Demostración de por qué la identidad y las camas viven en la capa ACID.
--   psql -U postgres -h localhost -d hce_core_grupo_6 -f sql/04_transacciones_acid.sql
-- (Los errores que aparecen en los casos 2 y 3 son ESPERADOS: es la BD protegiendo los datos.)
-- =====================================================================
SET client_encoding = 'UTF8';
SET search_path = core;

-- Limpieza para que el script se pueda correr varias veces
UPDATE camas SET estado = 'libre', hospitalizacion_actual_id = NULL WHERE hospitalizacion_actual_id = 'HOSP900';
DELETE FROM hospitalizaciones WHERE hospitalizacion_id IN ('HOSP900','HOSP901','HOSP902');

\echo '=== Estado inicial de las camas 301-303 ==='
SELECT cama_id, numero_cama, estado, hospitalizacion_actual_id FROM camas WHERE cama_id IN ('CAMA007','CAMA008','CAMA009') ORDER BY 1;

-- ---------------------------------------------------------------------
-- CASO 1 (éxito): admitir a PAC002 en la cama libre 303.
-- La hospitalización y la cama cambian JUNTAS (atomicidad).
-- ---------------------------------------------------------------------
\echo '=== CASO 1: admisión válida (debe funcionar) ==='
CALL sp_admitir_paciente('HOSP900', 'PAC002', 'MED001', 'CAMA009', 'Control post apendicectomía con fiebre');
SELECT h.hospitalizacion_id, h.paciente_id, h.estado, c.numero_cama, c.estado AS estado_cama
FROM hospitalizaciones h JOIN camas c ON c.cama_id = h.cama_id WHERE h.hospitalizacion_id = 'HOSP900';

-- ---------------------------------------------------------------------
-- CASO 2 (falla): admitir a PAC004 en la cama 302, que ya está ocupada.
-- El procedimiento lanza excepción -> NO se crea la hospitalización (consistencia).
-- ---------------------------------------------------------------------
\echo '=== CASO 2: cama ocupada (debe fallar y no dejar basura) ==='
CALL sp_admitir_paciente('HOSP901', 'PAC004', 'MED004', 'CAMA008', 'Dolor en rodilla');
SELECT count(*) AS hosp901_creadas FROM hospitalizaciones WHERE hospitalizacion_id = 'HOSP901';  -- debe dar 0

-- ---------------------------------------------------------------------
-- CASO 3 (falla): PAC003 ya tiene hospitalización activa; no puede tener otra.
-- Lo impide el índice único parcial uq_una_hosp_activa_por_paciente.
-- ---------------------------------------------------------------------
\echo '=== CASO 3: paciente con hospitalización activa (debe fallar) ==='
CALL sp_admitir_paciente('HOSP902', 'PAC003', 'MED003', 'CAMA010', 'Ingreso duplicado');
SELECT estado AS estado_cama_304_sigue_libre FROM camas WHERE cama_id = 'CAMA010';  -- debe seguir 'libre'

-- ---------------------------------------------------------------------
-- CASO 4 (falla de identidad): documento duplicado.
-- En la capa BASE esto podría colarse; aquí la restricción UNIQUE lo bloquea.
-- ---------------------------------------------------------------------
\echo '=== CASO 4: paciente con cédula repetida (debe fallar) ==='
INSERT INTO pacientes (paciente_id, tipo_documento, numero_documento, nombre_completo, fecha_nacimiento, sexo, eps)
VALUES ('PAC999', 'CC', '43789123', 'Registro duplicado', '1980-01-01', 'F', 'EPS Sura');

-- ---------------------------------------------------------------------
-- CASO 5 (éxito): alta de HOSP900 -> cierra hospitalización y libera la cama en una transacción.
-- ---------------------------------------------------------------------
\echo '=== CASO 5: alta (cierra hospitalización y libera la cama) ==='
CALL sp_dar_alta('HOSP900', 'mejoria');
SELECT h.hospitalizacion_id, h.estado, h.tipo_alta, c.numero_cama, c.estado AS estado_cama
FROM hospitalizaciones h JOIN camas c ON c.cama_id = h.cama_id WHERE h.hospitalizacion_id = 'HOSP900';

-- ---------------------------------------------------------------------
-- CASO 6: transacción explícita con ROLLBACK (aislamiento + atomicidad).
-- ---------------------------------------------------------------------
\echo '=== CASO 6: transacción manual que se deshace con ROLLBACK ==='
BEGIN;
  UPDATE camas SET estado = 'mantenimiento' WHERE cama_id = 'CAMA010';
  SELECT cama_id, estado FROM camas WHERE cama_id = 'CAMA010';   -- dentro de la transacción: mantenimiento
ROLLBACK;
SELECT cama_id, estado FROM camas WHERE cama_id = 'CAMA010';     -- después del ROLLBACK: libre otra vez

-- Limpieza final: se deja la BD como estaba
DELETE FROM hospitalizaciones WHERE hospitalizacion_id = 'HOSP900';
