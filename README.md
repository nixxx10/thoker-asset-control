# Thoker Asset & Inventory Control

Control de activos desplegados e inventario para una empresa ficticia de robótica industrial, de punta a punta: **generación del dataset → modelo dimensional en MySQL → dashboard y análisis en Power BI**.

> ⚠️ **Todos los datos de este repositorio son sintéticos.** Thoker Robotics no existe. Los clientes, ubicaciones, costes y movimientos fueron generados por un script propio para poder trabajar sobre un caso realista sin exponer información de ninguna empresa real. Cualquier parecido con datos reales es casualidad.

---

## El problema de negocio

Una empresa que despliega robots bajo modelo **RaaS** (*Robotics as a Service*) tiene un problema contable poco intuitivo: **el producto acabado no se vende**. Se instala en casa del cliente, el cliente paga una cuota por el servicio, pero el activo —y la obligación de mantenerlo— se queda en el balance del fabricante.

Eso obliga a sostener tres verdades sincronizadas:

| | Qué es | Dónde vive |
|---|---|---|
| **Físico** | El robot que está en la planta del cliente | Campo / telemetría |
| **Operativo** | Lo que el ERP cree que hay y en qué estado | Sistema |
| **Contable** | Coste, depreciación acumulada, valor neto contable | Libros |

Este proyecto construye el puente entre las tres.

---

## Qué contiene el repositorio

```
├── src/generate_data.py          Generador del dataset sintético (Python, reproducible)
├── data/                         7 CSV resultantes
├── sql/
│   ├── 01_schema.sql             DDL: 3 dimensiones + 4 tablas de hechos, PK/FK/UNIQUE
│   ├── 02_thoker_full_dump.sql   Dump completo (DDL + 4.885 filas) — un solo script
│   └── 03_consultas_analisis.sql Consultas que sostienen los hallazgos del dashboard
├── powerbi/medidas_dax.md        Todas las medidas y columnas calculadas del informe
└── docs/                         Diagrama EER y capturas del dashboard
```

---

## El modelo de datos: constelación, no estrella

El modelo tiene **cuatro tablas de hechos** compartiendo dimensiones conformadas — lo que Kimball llama esquema en *constelación* o *galaxia*.

La decisión de fondo: **cada proceso de negocio tiene su propio grano y no se puede meter en una sola tabla sin destruir información.**

| Tabla de hechos | Grano (1 fila = …) | Tipo | Filas |
|---|---|---|---|
| `fact_registro_activos` | un robot desplegado | Snapshot acumulativo | 125 |
| `fact_depreciacion_mensual` | un robot × un mes | Snapshot periódico | 1.879 |
| `fact_movimientos_inventario` | un movimiento de almacén | Transaccional | 2.521 |
| `fact_conteos_fisicos` | un SKU × un conteo trimestral | Transaccional | 276 |

Dimensiones conformadas: `dim_clientes` (14), `dim_modelos` (5), `dim_articulos_inventario` (65 SKUs).

**Un matiz que merece explicación:** `fact_registro_activos` es tabla de hechos frente a cliente y modelo, pero actúa como dimensión para `fact_depreciacion_mensual` (una fila por robot, PK = `asset_id`). No es una anomalía: es un *outrigger*, y es el motivo de que la clave primaria sea natural y no subrogada.

### Integridad garantizada por diseño

El script incluye tres consultas de verificación. La tercera es la importante:

```sql
SELECT COUNT(*) AS filas_incoherentes
FROM fact_registro_activos
WHERE ABS(coste_adquisicion - dep_acumulada - valor_neto_contable) > 0.01;
```

Devuelve 0. La identidad contable `coste − depreciación acumulada = valor neto contable` se cumple unidad a unidad, que es exactamente lo que Finanzas necesita poder auditar.

---

## Cómo reproducirlo

```bash
# 1. Regenerar el dataset (opcional — los CSV ya están en data/)
python src/generate_data.py

# 2. Cargar la base de datos en MySQL 8
mysql -u root -p < sql/02_thoker_full_dump.sql

# 3. Ver el diagrama
#    MySQL Workbench → Database → Reverse Engineer → esquema `thoker`

# 4. Power BI Desktop → Obtener datos → MySQL → localhost / thoker → modo Import
```

---

## Hallazgos del análisis

Tres conclusiones que el modelo permite sostener con datos, no con intuición:

**1. El muro de renovación (2030-2031).** El 74% de la flota (92 de 125 unidades) se desplegó entre 2024 y 2025. Con vidas útiles de 5-7 años, esas cohortes vencen juntas: **88 unidades — el 70% de la flota — alcanzan fin de vida en 24 meses, exigiendo 9,0 M€ de reposición**. No es una predicción: se deriva aritméticamente de fecha de despliegue + vida útil.

**2. El consumo de repuestos crece por flota, no por fallos.** El consumo bruto se duplicó (227 → 465 uds/mes). Normalizado por flota instalada, cae de 5,0 a 3,0 uds/robot/mes. La lectura ingenua ("comprar más") es la equivocada: hay que dimensionar sobre el plan de despliegues, no extrapolar la serie bruta.

**3. Ningún modelo de robot falla más que otro.** Las tasas de no operatividad oscilan entre 21% y 31%, pero con 17-31 unidades por modelo los intervalos de confianza al 95% se solapan por completo. **La diferencia no es distinguible del azar** — priorizar inversión sobre esa base sería vender ruido como señal. Lo que sí es accionable es el € en riesgo: un modelo concentra el 42% del valor inmovilizado con solo el 21% de las unidades.

### Lo que este modelo todavía no puede responder

Documentarlo importa tanto como los hallazgos:

- **¿Se renovará el contrato?** El muro asume reposición 1:1. Sin fechas de vencimiento contractual no se distingue *necesidad de CAPEX* de *activo varado*.
- **¿Por qué se para cada robot?** `estado` es una foto sin log de cambios, y los movimientos de inventario no llevan `asset_id`: el consumo de repuestos no es atribuible a una unidad concreta.
- **¿Hay estacionalidad en las averías?** 19 meses de histórico = 1,6 ciclos anuales. Holt-Winters necesita ≥2 ciclos completos.

*Siguiente iteración: tabla de órdenes de trabajo (causa, fecha, SKU, asset_id) + BOM modelo↔componente + fechas de contrato.*

---

## Stack

MySQL 8 · Power BI Desktop (DAX, Power Query) · Python 3 (pandas, numpy) · Claude Opus 5 para la generación asistida del dataset

---

## Autor

**Nízar El Ouarma Sorribas** — Supply Chain & Data Analyst, Barcelona
LinkedIn: `<pega aquí la URL de tu perfil>` · GitHub: [@nixxx10](https://github.com/nixxx10)
