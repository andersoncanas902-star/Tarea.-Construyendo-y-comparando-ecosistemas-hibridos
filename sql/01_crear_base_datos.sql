-- =====================================================================
-- 01_crear_base_datos.sql
-- Capa ACID del ecosistema híbrido (PostgreSQL)
-- Grupo 6 - Bases de Datos II (G101)
--
-- Ejecutar conectado a la base "postgres":
--   psql -U postgres -h localhost -f sql/01_crear_base_datos.sql
-- =====================================================================
SET client_encoding = 'UTF8';

-- Si existe de una corrida anterior, se elimina para empezar limpio
DROP DATABASE IF EXISTS hce_core_grupo_6 WITH (FORCE);

-- Base de datos del núcleo consistente (identidad, médicos, camas, hospitalizaciones)
CREATE DATABASE hce_core_grupo_6
    WITH ENCODING = 'UTF8'
         TEMPLATE = template0;
