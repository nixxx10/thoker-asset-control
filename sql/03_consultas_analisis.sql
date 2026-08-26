-- ============================================================
-- Thoker Asset & Inventory Control — Consultas de análisis
-- Las consultas que sostienen los hallazgos del dashboard.
-- Ejecutar sobre la base de datos `thoker`.
-- ============================================================

USE thoker;

-- ------------------------------------------------------------
-- 0. DIAGNÓSTICO DE CALIDAD DE DATOS
--    Se ejecuta ANTES de analizar nada. Un modelo sin diagnóstico
--    previo produce conclusiones con la confianza equivocada.
-- ------------------------------------------------------------

-- 0.1 Huérfanos: hechos que apuntan a dimensiones inexistentes
SELECT COUNT(*) AS activos_huerfanos
FROM fact_registro_activos a
LEFT JOIN dim_clientes c ON a.client_id = c.client_id
WHERE c.client_id IS NULL;

-- 0.2 Coherencia contable unidad a unidad (esperado: 0)
SELECT COUNT(*) AS filas_incoherentes
FROM fact_registro_activos
WHERE ABS(coste_adquisicion - dep_acumulada - valor_neto_contable) > 0.01;

-- 0.3 Cruce entre hechos: registro vs depreciación mensual del último mes.
--     NOTA DE UMBRAL: comparar con > 0.01 devuelve 59 falsos positivos por
--     acumulación de redondeo mes a mes. El umbral correcto es de
--     MATERIALIDAD (> 1 €), no de exactitud binaria.
SELECT COUNT(*) AS discrepancias_materiales
FROM fact_registro_activos a
JOIN (
    SELECT asset_id, valor_neto_contable
    FROM fact_depreciacion_mensual
    WHERE mes = (SELECT MAX(mes) FROM fact_depreciacion_mensual)
) d ON a.asset_id = d.asset_id
WHERE ABS(a.valor_neto_contable - d.valor_neto_contable) > 1;

-- 0.4 Detección de mojibake (UTF-8 leído como latin1).
--     OJO: NO usar LIKE '%Ã%' — la collation utf8mb4_unicode_ci es
--     insensible a acentos y 'Ã' hace match con toda 'a'. Hay que
--     comparar BYTES, no caracteres.
SELECT COUNT(*) AS filas_con_mojibake
FROM dim_clientes
WHERE HEX(cliente) LIKE '%C383%';


-- ------------------------------------------------------------
-- 1. EL MURO DE RENOVACIÓN
--    ¿Cuándo y cuánto habrá que reinvertir para sostener la flota?
-- ------------------------------------------------------------

-- 1.1 Origen: cómo se construyó la flota (la causa)
SELECT
    YEAR(fecha_despliegue)                                   AS anio_despliegue,
    COUNT(*)                                                 AS unidades,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM fact_registro_activos), 1) AS pct_flota,
    ROUND(SUM(coste_adquisicion) / 1e6, 2)                   AS capex_millones
FROM fact_registro_activos
GROUP BY anio_despliegue
ORDER BY anio_despliegue;
-- Resultado: 2023=4 · 2024=36 · 2025=56 · 2026=29 (parcial, corte 31/07/2026)
-- 92 de 125 unidades (74%) desplegadas en solo dos años.

-- 1.2 Consecuencia: vencimientos de vida útil por año
SELECT
    YEAR(DATE_ADD(fecha_despliegue, INTERVAL vida_util_meses MONTH)) AS anio_fin_vida,
    COUNT(*)                                                         AS unidades,
    ROUND(SUM(coste_adquisicion) / 1e6, 2)                           AS capex_reposicion_millones
FROM fact_registro_activos
GROUP BY anio_fin_vida
ORDER BY anio_fin_vida;
-- Resultado: pico en 2030 (46 uds / 5,2 M€) y 2031 (42 uds / 3,8 M€).
-- 88 unidades = 70% de la flota en 24 meses = 9,0 M€.

-- 1.3 Concentración del riesgo por cliente en el pico
SELECT
    c.cliente,
    c.sla_tier,
    COUNT(*)                               AS unidades_que_vencen,
    ROUND(SUM(a.coste_adquisicion) / 1e6, 2) AS capex_millones
FROM fact_registro_activos a
JOIN dim_clientes c ON a.client_id = c.client_id
WHERE YEAR(DATE_ADD(a.fecha_despliegue, INTERVAL a.vida_util_meses MONTH)) BETWEEN 2030 AND 2031
GROUP BY c.cliente, c.sla_tier
ORDER BY capex_millones DESC;


-- ------------------------------------------------------------
-- 2. CONSUMO DE REPUESTOS: ¿MÁS ROBOTS O MÁS FALLOS?
-- ------------------------------------------------------------

-- Consumo bruto mensual de spares vs flota instalada acumulada.
-- El numerador es un FLUJO (consumo del mes); el denominador un
-- STOCK (flota a fin de mes). Lo estrictamente correcto sería flota
-- media del período — la diferencia es menor y se documenta.
SELECT
    DATE_FORMAT(m.fecha, '%Y-%m')  AS anio_mes,
    -SUM(m.cantidad)               AS consumo_spares_uds,
    (SELECT COUNT(*)
     FROM fact_registro_activos a
     WHERE a.fecha_despliegue <= LAST_DAY(m.fecha)) AS flota_instalada,
    ROUND(-SUM(m.cantidad) /
          (SELECT COUNT(*)
           FROM fact_registro_activos a
           WHERE a.fecha_despliegue <= LAST_DAY(m.fecha)), 2) AS spares_por_robot
FROM fact_movimientos_inventario m
JOIN dim_articulos_inventario i ON m.sku = i.sku
WHERE m.cantidad < 0
  AND i.categoria = 'Spare / Repuesto'
GROUP BY anio_mes, LAST_DAY(m.fecha)
ORDER BY anio_mes;
-- Consumo bruto: 227 → 465 uds/mes (+105%)
-- Por robot: 5,0 → 3,3 uds/robot/mes  →  el crecimiento es de FLOTA, no de fallos.


-- ------------------------------------------------------------
-- 3. ¿HAY UN MODELO QUE FALLE MÁS QUE LOS DEMÁS?
--    (Spoiler: no de forma distinguible del azar)
-- ------------------------------------------------------------

SELECT
    mo.modelo,
    COUNT(*)                                                          AS unidades,
    SUM(a.estado <> 'Operativo')                                      AS no_operativas,
    ROUND(100.0 * SUM(a.estado <> 'Operativo') / COUNT(*), 1)         AS pct_no_operativo,
    ROUND(SUM(CASE WHEN a.estado <> 'Operativo'
                   THEN a.valor_neto_contable ELSE 0 END) / 1e6, 2)   AS nbv_inmovilizado_millones
FROM fact_registro_activos a
JOIN dim_modelos mo ON a.model_id = mo.model_id
GROUP BY mo.modelo
ORDER BY pct_no_operativo DESC;
-- Tasas entre 21% y 31%, pero con n = 17-31 unidades por modelo los
-- intervalos de confianza de Wilson al 95% se solapan por completo.
-- CONCLUSIÓN: no priorizar por modelo con esta evidencia. Priorizar
-- por € en riesgo (la última columna), que sí discrimina.


-- ------------------------------------------------------------
-- 4. INVENTARIO: EXACTITUD Y ALERTAS DE REPOSICIÓN
-- ------------------------------------------------------------

-- 4.1 IRA (Inventory Record Accuracy) por trimestre de conteo
SELECT
    fecha_conteo,
    COUNT(*)                                                        AS lineas_contadas,
    SUM(causa_raiz <> 'Sin discrepancia')                           AS lineas_con_discrepancia,
    ROUND(100.0 * (1 - SUM(causa_raiz <> 'Sin discrepancia') / COUNT(*)), 1) AS ira_pct,
    ROUND(SUM(ABS(discrepancia_valor)), 2)                          AS valor_absoluto_discrepancias
FROM fact_conteos_fisicos
GROUP BY fecha_conteo
ORDER BY fecha_conteo;

-- 4.2 Pareto de causas raíz (dónde atacar primero el proceso)
SELECT
    causa_raiz,
    COUNT(*)                              AS incidencias,
    ROUND(SUM(ABS(discrepancia_valor)), 2) AS valor_absoluto
FROM fact_conteos_fisicos
WHERE causa_raiz <> 'Sin discrepancia'
GROUP BY causa_raiz
ORDER BY valor_absoluto DESC;

-- 4.3 SKUs bajo punto de pedido — el informe semanal para Compras
SELECT
    sku, descripcion, categoria, proveedor,
    stock_teorico_actual, punto_pedido, stock_seguridad, lead_time_dias,
    punto_pedido - stock_teorico_actual AS deficit_uds
FROM dim_articulos_inventario
WHERE stock_teorico_actual < punto_pedido
ORDER BY deficit_uds DESC;
