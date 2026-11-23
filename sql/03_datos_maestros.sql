-- =====================================================================
-- 03_datos_maestros.sql
-- Datos maestros del núcleo ACID. Son los MISMOS pacientes, médicos, camas
-- y hospitalizaciones de la BD MongoDB hce_hospitalizacion_grupo_6 (U2/S1),
-- ahora con su identidad centralizada en PostgreSQL.
--   psql -U postgres -h localhost -d hce_core_grupo_6 -f sql/03_datos_maestros.sql
-- =====================================================================
SET client_encoding = 'UTF8';
SET search_path = core;

BEGIN;  -- todo el cargue es una sola transacción: o entra completo o no entra nada

INSERT INTO servicios (nombre) VALUES ('UCI'), ('Medicina Interna'), ('Cirugia General'), ('Ortopedia y Traumatologia');

-- Pacientes (identidad)
INSERT INTO pacientes (paciente_id, tipo_documento, numero_documento, nombre_completo, fecha_nacimiento, sexo, eps, telefono, direccion, contacto_nombre, contacto_parentesco, contacto_telefono) VALUES
  ('PAC001', 'CC', '43789123', 'Maria Fernanda Restrepo Gomez', '1958-03-12', 'F', 'EPS Sura', '3015558842', 'Calle 45 # 23-10, Medellin', 'Jorge Restrepo', 'hermano', '3017779911'),
  ('PAC002', 'CC', '1128456789', 'Carlos Andres Zapata Londono', '1990-07-22', 'M', 'Savia Salud', '3109876543', 'Carrera 80 # 12-45, Bello', 'Diana Zapata', 'esposa', '3121239988'),
  ('PAC003', 'CC', '32654112', 'Luz Dary Henao Cardona', '1975-11-05', 'F', 'Nueva EPS', '3137765521', 'Calle 10 # 34-21, Itagui', 'Camilo Henao', 'hijo', '3148891122'),
  ('PAC004', 'CC', '1036987654', 'Jhon Edison Patino Rios', '2001-02-18', 'M', 'EPS Sura', '3209988776', 'Transversal 5 # 60-15, Envigado', 'Marta Rios', 'madre', '3156677889'),
  ('PAC005', 'CC', '21345678', 'Rosa Elena Munoz Velez', '1949-09-30', 'F', 'Coosalud', '3012233445', 'Calle 70 # 45-30, Medellin', 'Felipe Munoz', 'nieto', '3199988776'),
  ('PAC006', 'CC', '71234567', 'Hector Ivan Castano Ramirez', '1982-04-02', 'M', 'Nueva EPS', '3119981122', 'Calle 33 # 70-12, Medellin', 'Liliana Castano', 'esposa', '3134456677'),
  ('PAC007', 'CC', '43988211', 'Gloria Patricia Arango Builes', '1965-12-19', 'F', 'EPS Sura', '3156612398', 'Carrera 52 # 40-21, Medellin', 'Andres Arango', 'hijo', '3002219988'),
  ('PAC008', 'CC', '98451267', 'Julian David Moreno Arias', '1995-06-08', 'M', 'Savia Salud', '3187741256', 'Calle 85 # 48-30, Bello', 'Paola Arias', 'madre', '3209987766'),
  ('PAC009', 'CC', '22678901', 'Alba Lucia Vargas Montoya', '1941-01-27', 'F', 'Coosalud', '3145567890', 'Transversal 24 # 15-55, Itagui', 'Ricardo Vargas', 'hijo', '3178812345'),
  ('PAC010', 'CC', '1098765432', 'Esteban Alejandro Quintero Soto', '1999-10-14', 'M', 'Nueva EPS', '3012245678', 'Calle 95 # 52-18, Medellin', 'Sandra Soto', 'madre', '3121198877'),
  ('PAC011', 'CC', '1152233445', 'Marcela Isabel Ochoa Ramirez', '1988-05-19', 'F', 'EPS Sura', '3142219988', 'Calle 60 # 28-14, Medellin', 'Daniel Ochoa', 'hermano', '3151122334');

-- Médicos
INSERT INTO medicos (medico_id, tipo_documento, numero_documento, nombre_completo, registro_medico, especialidad, servicio_id, telefono, activo) VALUES
  ('MED001', 'CC', '70556123', 'Dr. Andres Felipe Suarez', 'TP-45231-ANT', 'Medicina Interna', 2, '3011239876', TRUE),
  ('MED002', 'CC', '43221098', 'Dra. Camila Vasquez', 'TP-50112-ANT', 'Cirugia General', 3, '3022348765', TRUE),
  ('MED003', 'CC', '71004455', 'Dr. Oscar Giraldo', 'TP-38890-ANT', 'Medicina Interna', 2, '3033457890', TRUE),
  ('MED004', 'CC', '15778899', 'Dr. Santiago Lopera', 'TP-41256-ANT', 'Ortopedia y Traumatologia', 4, '3044567123', TRUE),
  ('MED005', 'CC', '43556712', 'Dra. Natalia Correa', 'TP-47765-ANT', 'Medicina Interna', 2, '3055678234', TRUE),
  ('MED006', 'CC', '1040223311', 'Dra. Laura Jaramillo', 'TP-52980-ANT', 'Medicina Interna', 2, '3066789345', TRUE),
  ('MED007', 'CC', '98123456', 'Dr. Felipe Montoya', 'TP-39871-ANT', 'Cirugia General', 3, '3077890456', TRUE);

-- Camas (el estado se ajusta al final según las hospitalizaciones activas)
INSERT INTO camas (cama_id, numero_cama, piso, servicio_id, estado) VALUES
  ('CAMA001', '101', 1, 1, 'libre'),
  ('CAMA002', '102', 1, 1, 'libre'),
  ('CAMA003', '201', 2, 3, 'libre'),
  ('CAMA004', '202', 2, 3, 'libre'),
  ('CAMA005', '203', 2, 3, 'libre'),
  ('CAMA006', '204', 2, 3, 'libre'),
  ('CAMA007', '301', 3, 2, 'libre'),
  ('CAMA008', '302', 3, 2, 'libre'),
  ('CAMA009', '303', 3, 2, 'libre'),
  ('CAMA010', '304', 3, 2, 'libre'),
  ('CAMA011', '305', 3, 2, 'libre'),
  ('CAMA012', '306', 3, 2, 'libre'),
  ('CAMA013', '307', 3, 2, 'libre'),
  ('CAMA014', '401', 4, 4, 'libre'),
  ('CAMA015', '402', 4, 4, 'libre'),
  ('CAMA016', '403', 4, 4, 'mantenimiento');

-- Hospitalizaciones
INSERT INTO hospitalizaciones (hospitalizacion_id, paciente_id, medico_id, cama_id, servicio_id, fecha_admision, motivo_admision, estado, fecha_alta, tipo_alta) VALUES
  ('HOSP001', 'PAC001', 'MED001', 'CAMA007', 2, '2026-10-10T08:15:00Z', 'Dificultad respiratoria y fiebre de 3 dias de evolucion', 'dada_de_alta', '2026-10-14T11:00:00Z', 'mejoria'),
  ('HOSP002', 'PAC002', 'MED002', 'CAMA003', 3, '2026-10-15T22:40:00Z', 'Dolor abdominal intenso en fosa iliaca derecha', 'dada_de_alta', '2026-10-18T09:30:00Z', 'mejoria'),
  ('HOSP003', 'PAC003', 'MED003', 'CAMA008', 2, '2026-10-22T06:50:00Z', 'Glicemia descompensada, debilidad y vomito', 'activa', NULL, NULL),
  ('HOSP004', 'PAC004', 'MED004', 'CAMA014', 4, '2026-10-12T19:05:00Z', 'Accidente de transito, dolor intenso e imposibilidad de mover pierna derecha', 'dada_de_alta', '2026-10-20T10:00:00Z', 'mejoria'),
  ('HOSP005', 'PAC005', 'MED005', 'CAMA009', 2, '2026-10-19T03:20:00Z', 'Dificultad para respirar y tos con flemas, antecedente de EPOC', 'dada_de_alta', '2026-10-23T12:15:00Z', 'mejoria'),
  ('HOSP006', 'PAC006', 'MED003', 'CAMA010', 2, '2026-10-11T13:20:00Z', 'Dolor lumbar intenso con fiebre y ardor al orinar', 'dada_de_alta', '2026-10-15T10:00:00Z', 'mejoria'),
  ('HOSP007', 'PAC007', 'MED005', 'CAMA011', 2, '2026-10-14T05:45:00Z', 'Cefalea intensa, cifras tensionales muy elevadas en casa', 'dada_de_alta', '2026-10-16T09:00:00Z', 'mejoria'),
  ('HOSP008', 'PAC008', 'MED001', 'CAMA012', 2, '2026-10-18T21:10:00Z', 'Fiebre alta, tos seca y malestar general de 4 dias', 'dada_de_alta', '2026-11-07T10:30:00Z', 'mejoria'),
  ('HOSP009', 'PAC009', 'MED004', 'CAMA015', 4, '2026-10-09T16:30:00Z', 'Caida en casa, dolor intenso en cadera e imposibilidad de caminar', 'dada_de_alta', '2026-10-19T11:30:00Z', 'mejoria'),
  ('HOSP010', 'PAC010', 'MED003', 'CAMA013', 2, '2026-10-23T02:50:00Z', 'Vomito y diarrea abundante con signos de deshidratacion', 'dada_de_alta', '2026-10-25T10:00:00Z', 'mejoria'),
  ('HOSP011', 'PAC011', 'MED006', 'CAMA007', 2, '2026-11-05T09:10:00Z', 'Enrojecimiento, dolor e hinchazon en pierna derecha de 2 dias', 'activa', NULL, NULL);

-- Diagnósticos CIE-10
INSERT INTO diagnosticos_hospitalizacion (hospitalizacion_id, codigo_cie10, descripcion, tipo) VALUES
  ('HOSP001', 'J18.9', 'Neumonia, no especificada', 'principal'),
  ('HOSP002', 'K35.80', 'Apendicitis aguda, no especificada', 'principal'),
  ('HOSP003', 'E11.65', 'Diabetes mellitus tipo 2 con hiperglicemia', 'principal'),
  ('HOSP004', 'S72.90', 'Fractura de femur, parte no especificada', 'principal'),
  ('HOSP005', 'J44.1', 'EPOC con exacerbacion aguda', 'principal'),
  ('HOSP006', 'N39.0', 'Infeccion de vias urinarias, sitio no especificado', 'principal'),
  ('HOSP007', 'I16.9', 'Crisis hipertensiva, no especificada', 'principal'),
  ('HOSP008', 'J12.9', 'Neumonia viral, no especificada', 'principal'),
  ('HOSP009', 'S72.00', 'Fractura del cuello del femur', 'principal'),
  ('HOSP010', 'A09', 'Gastroenteritis y colitis de origen infeccioso no especificado', 'principal'),
  ('HOSP011', 'L03.11', 'Celulitis de miembro inferior derecho', 'principal'),
  ('HOSP011', 'E11.9', 'Diabetes mellitus tipo 2 sin complicaciones', 'secundario');

-- Las camas de hospitalizaciones activas quedan ocupadas
UPDATE camas c SET estado = 'ocupada', hospitalizacion_actual_id = h.hospitalizacion_id
  FROM hospitalizaciones h WHERE h.cama_id = c.cama_id AND h.estado = 'activa';

-- Dispositivos médicos: 4 por hospitalización (monitor, pulsera, bomba, glucómetro)
INSERT INTO dispositivos (dispositivo_id, tipo_dispositivo, modelo, serial) VALUES
  ('MON-H01', 'monitor_multiparametro', 'Mindray BeneVision N12', 'SN-MON-2026-01'),
  ('PUL-H01', 'pulsera_wearable', 'Biobeat BB-613WP', 'SN-PUL-2026-01'),
  ('BOM-H01', 'bomba_infusion', 'B.Braun Infusomat Space', 'SN-BOM-2026-01'),
  ('GLU-H01', 'glucometro', 'Accu-Chek Inform II', 'SN-GLU-2026-01'),
  ('MON-H02', 'monitor_multiparametro', 'Mindray BeneVision N12', 'SN-MON-2026-02'),
  ('PUL-H02', 'pulsera_wearable', 'Biobeat BB-613WP', 'SN-PUL-2026-02'),
  ('BOM-H02', 'bomba_infusion', 'B.Braun Infusomat Space', 'SN-BOM-2026-02'),
  ('GLU-H02', 'glucometro', 'Accu-Chek Inform II', 'SN-GLU-2026-02'),
  ('MON-H03', 'monitor_multiparametro', 'Mindray BeneVision N12', 'SN-MON-2026-03'),
  ('PUL-H03', 'pulsera_wearable', 'Biobeat BB-613WP', 'SN-PUL-2026-03'),
  ('BOM-H03', 'bomba_infusion', 'B.Braun Infusomat Space', 'SN-BOM-2026-03'),
  ('GLU-H03', 'glucometro', 'Accu-Chek Inform II', 'SN-GLU-2026-03'),
  ('MON-H04', 'monitor_multiparametro', 'Mindray BeneVision N12', 'SN-MON-2026-04'),
  ('PUL-H04', 'pulsera_wearable', 'Biobeat BB-613WP', 'SN-PUL-2026-04'),
  ('BOM-H04', 'bomba_infusion', 'B.Braun Infusomat Space', 'SN-BOM-2026-04'),
  ('GLU-H04', 'glucometro', 'Accu-Chek Inform II', 'SN-GLU-2026-04'),
  ('MON-H05', 'monitor_multiparametro', 'Mindray BeneVision N12', 'SN-MON-2026-05'),
  ('PUL-H05', 'pulsera_wearable', 'Biobeat BB-613WP', 'SN-PUL-2026-05'),
  ('BOM-H05', 'bomba_infusion', 'B.Braun Infusomat Space', 'SN-BOM-2026-05'),
  ('GLU-H05', 'glucometro', 'Accu-Chek Inform II', 'SN-GLU-2026-05'),
  ('MON-H06', 'monitor_multiparametro', 'Mindray BeneVision N12', 'SN-MON-2026-06'),
  ('PUL-H06', 'pulsera_wearable', 'Biobeat BB-613WP', 'SN-PUL-2026-06'),
  ('BOM-H06', 'bomba_infusion', 'B.Braun Infusomat Space', 'SN-BOM-2026-06'),
  ('GLU-H06', 'glucometro', 'Accu-Chek Inform II', 'SN-GLU-2026-06'),
  ('MON-H07', 'monitor_multiparametro', 'Mindray BeneVision N12', 'SN-MON-2026-07'),
  ('PUL-H07', 'pulsera_wearable', 'Biobeat BB-613WP', 'SN-PUL-2026-07'),
  ('BOM-H07', 'bomba_infusion', 'B.Braun Infusomat Space', 'SN-BOM-2026-07'),
  ('GLU-H07', 'glucometro', 'Accu-Chek Inform II', 'SN-GLU-2026-07'),
  ('MON-H08', 'monitor_multiparametro', 'Mindray BeneVision N12', 'SN-MON-2026-08'),
  ('PUL-H08', 'pulsera_wearable', 'Biobeat BB-613WP', 'SN-PUL-2026-08'),
  ('BOM-H08', 'bomba_infusion', 'B.Braun Infusomat Space', 'SN-BOM-2026-08'),
  ('GLU-H08', 'glucometro', 'Accu-Chek Inform II', 'SN-GLU-2026-08'),
  ('MON-H09', 'monitor_multiparametro', 'Mindray BeneVision N12', 'SN-MON-2026-09'),
  ('PUL-H09', 'pulsera_wearable', 'Biobeat BB-613WP', 'SN-PUL-2026-09'),
  ('BOM-H09', 'bomba_infusion', 'B.Braun Infusomat Space', 'SN-BOM-2026-09'),
  ('GLU-H09', 'glucometro', 'Accu-Chek Inform II', 'SN-GLU-2026-09'),
  ('MON-H10', 'monitor_multiparametro', 'Mindray BeneVision N12', 'SN-MON-2026-10'),
  ('PUL-H10', 'pulsera_wearable', 'Biobeat BB-613WP', 'SN-PUL-2026-10'),
  ('BOM-H10', 'bomba_infusion', 'B.Braun Infusomat Space', 'SN-BOM-2026-10'),
  ('GLU-H10', 'glucometro', 'Accu-Chek Inform II', 'SN-GLU-2026-10'),
  ('MON-H11', 'monitor_multiparametro', 'Mindray BeneVision N12', 'SN-MON-2026-11'),
  ('PUL-H11', 'pulsera_wearable', 'Biobeat BB-613WP', 'SN-PUL-2026-11'),
  ('BOM-H11', 'bomba_infusion', 'B.Braun Infusomat Space', 'SN-BOM-2026-11'),
  ('GLU-H11', 'glucometro', 'Accu-Chek Inform II', 'SN-GLU-2026-11');

-- Qué dispositivo estuvo conectado a qué paciente y durante cuánto tiempo
INSERT INTO asignaciones_dispositivo (dispositivo_id, hospitalizacion_id, paciente_id, desde, hasta) VALUES
  ('MON-H01', 'HOSP001', 'PAC001', '2026-10-10T08:15:00Z', '2026-10-14T11:00:00Z'),
  ('PUL-H01', 'HOSP001', 'PAC001', '2026-10-10T08:15:00Z', '2026-10-14T11:00:00Z'),
  ('BOM-H01', 'HOSP001', 'PAC001', '2026-10-10T08:15:00Z', '2026-10-14T11:00:00Z'),
  ('GLU-H01', 'HOSP001', 'PAC001', '2026-10-10T08:15:00Z', '2026-10-14T11:00:00Z'),
  ('MON-H02', 'HOSP002', 'PAC002', '2026-10-15T22:40:00Z', '2026-10-18T09:30:00Z'),
  ('PUL-H02', 'HOSP002', 'PAC002', '2026-10-15T22:40:00Z', '2026-10-18T09:30:00Z'),
  ('BOM-H02', 'HOSP002', 'PAC002', '2026-10-15T22:40:00Z', '2026-10-18T09:30:00Z'),
  ('GLU-H02', 'HOSP002', 'PAC002', '2026-10-15T22:40:00Z', '2026-10-18T09:30:00Z'),
  ('MON-H03', 'HOSP003', 'PAC003', '2026-10-22T06:50:00Z', NULL),
  ('PUL-H03', 'HOSP003', 'PAC003', '2026-10-22T06:50:00Z', NULL),
  ('BOM-H03', 'HOSP003', 'PAC003', '2026-10-22T06:50:00Z', NULL),
  ('GLU-H03', 'HOSP003', 'PAC003', '2026-10-22T06:50:00Z', NULL),
  ('MON-H04', 'HOSP004', 'PAC004', '2026-10-12T19:05:00Z', '2026-10-20T10:00:00Z'),
  ('PUL-H04', 'HOSP004', 'PAC004', '2026-10-12T19:05:00Z', '2026-10-20T10:00:00Z'),
  ('BOM-H04', 'HOSP004', 'PAC004', '2026-10-12T19:05:00Z', '2026-10-20T10:00:00Z'),
  ('GLU-H04', 'HOSP004', 'PAC004', '2026-10-12T19:05:00Z', '2026-10-20T10:00:00Z'),
  ('MON-H05', 'HOSP005', 'PAC005', '2026-10-19T03:20:00Z', '2026-10-23T12:15:00Z'),
  ('PUL-H05', 'HOSP005', 'PAC005', '2026-10-19T03:20:00Z', '2026-10-23T12:15:00Z'),
  ('BOM-H05', 'HOSP005', 'PAC005', '2026-10-19T03:20:00Z', '2026-10-23T12:15:00Z'),
  ('GLU-H05', 'HOSP005', 'PAC005', '2026-10-19T03:20:00Z', '2026-10-23T12:15:00Z'),
  ('MON-H06', 'HOSP006', 'PAC006', '2026-10-11T13:20:00Z', '2026-10-15T10:00:00Z'),
  ('PUL-H06', 'HOSP006', 'PAC006', '2026-10-11T13:20:00Z', '2026-10-15T10:00:00Z'),
  ('BOM-H06', 'HOSP006', 'PAC006', '2026-10-11T13:20:00Z', '2026-10-15T10:00:00Z'),
  ('GLU-H06', 'HOSP006', 'PAC006', '2026-10-11T13:20:00Z', '2026-10-15T10:00:00Z'),
  ('MON-H07', 'HOSP007', 'PAC007', '2026-10-14T05:45:00Z', '2026-10-16T09:00:00Z'),
  ('PUL-H07', 'HOSP007', 'PAC007', '2026-10-14T05:45:00Z', '2026-10-16T09:00:00Z'),
  ('BOM-H07', 'HOSP007', 'PAC007', '2026-10-14T05:45:00Z', '2026-10-16T09:00:00Z'),
  ('GLU-H07', 'HOSP007', 'PAC007', '2026-10-14T05:45:00Z', '2026-10-16T09:00:00Z'),
  ('MON-H08', 'HOSP008', 'PAC008', '2026-10-18T21:10:00Z', '2026-11-07T10:30:00Z'),
  ('PUL-H08', 'HOSP008', 'PAC008', '2026-10-18T21:10:00Z', '2026-11-07T10:30:00Z'),
  ('BOM-H08', 'HOSP008', 'PAC008', '2026-10-18T21:10:00Z', '2026-11-07T10:30:00Z'),
  ('GLU-H08', 'HOSP008', 'PAC008', '2026-10-18T21:10:00Z', '2026-11-07T10:30:00Z'),
  ('MON-H09', 'HOSP009', 'PAC009', '2026-10-09T16:30:00Z', '2026-10-19T11:30:00Z'),
  ('PUL-H09', 'HOSP009', 'PAC009', '2026-10-09T16:30:00Z', '2026-10-19T11:30:00Z'),
  ('BOM-H09', 'HOSP009', 'PAC009', '2026-10-09T16:30:00Z', '2026-10-19T11:30:00Z'),
  ('GLU-H09', 'HOSP009', 'PAC009', '2026-10-09T16:30:00Z', '2026-10-19T11:30:00Z'),
  ('MON-H10', 'HOSP010', 'PAC010', '2026-10-23T02:50:00Z', '2026-10-25T10:00:00Z'),
  ('PUL-H10', 'HOSP010', 'PAC010', '2026-10-23T02:50:00Z', '2026-10-25T10:00:00Z'),
  ('BOM-H10', 'HOSP010', 'PAC010', '2026-10-23T02:50:00Z', '2026-10-25T10:00:00Z'),
  ('GLU-H10', 'HOSP010', 'PAC010', '2026-10-23T02:50:00Z', '2026-10-25T10:00:00Z'),
  ('MON-H11', 'HOSP011', 'PAC011', '2026-11-05T09:10:00Z', NULL),
  ('PUL-H11', 'HOSP011', 'PAC011', '2026-11-05T09:10:00Z', NULL),
  ('BOM-H11', 'HOSP011', 'PAC011', '2026-11-05T09:10:00Z', NULL),
  ('GLU-H11', 'HOSP011', 'PAC011', '2026-11-05T09:10:00Z', NULL);

COMMIT;

-- Verificación rápida
SELECT 'pacientes' AS tabla, count(*) FROM pacientes UNION ALL
SELECT 'medicos', count(*) FROM medicos UNION ALL
SELECT 'camas', count(*) FROM camas UNION ALL
SELECT 'hospitalizaciones', count(*) FROM hospitalizaciones UNION ALL
SELECT 'diagnosticos', count(*) FROM diagnosticos_hospitalizacion UNION ALL
SELECT 'dispositivos', count(*) FROM dispositivos UNION ALL
SELECT 'asignaciones', count(*) FROM asignaciones_dispositivo;
