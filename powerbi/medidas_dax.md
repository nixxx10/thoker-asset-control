# Medidas y columnas calculadas (DAX)

Todas las medidas viven en una tabla vacía `_Medidas`. Las columnas calculadas están indicadas explícitamente.

## Modelo

Relaciones (todas 1 → *, dirección única):

```
dim_clientes[client_id]            1 → *  fact_registro_activos[client_id]
dim_modelos[model_id]              1 → *  fact_registro_activos[model_id]
fact_registro_activos[asset_id]    1 → *  fact_depreciacion_mensual[asset_id]
dim_articulos_inventario[sku]      1 → *  fact_movimientos_inventario[sku]
dim_articulos_inventario[sku]      1 → *  fact_conteos_fisicos[sku]
Calendario[Date]                   1 → *  fact_depreciacion_mensual[mes]
Calendario[Date]                   1 → *  fact_movimientos_inventario[fecha]
```

Tabla de fechas (marcarla como tabla de fechas):

```dax
Calendario =
ADDCOLUMNS(
    CALENDAR(DATE(2023,1,1), DATE(2026,12,31)),
    "Año",       YEAR([Date]),
    "MesNum",    MONTH([Date]),
    "Mes",       FORMAT([Date],"MMM"),
    "AñoMes",    FORMAT([Date],"YYYY-MM"),
    "Trimestre", "T" & FORMAT([Date],"Q")
)
```

---

## Activos

```dax
NBV = SUM(fact_registro_activos[valor_neto_contable])
```
```dax
Coste Bruto = SUM(fact_registro_activos[coste_adquisicion])
```
```dax
Dep. Acumulada = SUM(fact_registro_activos[dep_acumulada])
```
```dax
Unidades Desplegadas = COUNTROWS(fact_registro_activos)
```
```dax
Unidades Operativas = CALCULATE([Unidades Desplegadas], fact_registro_activos[estado] = "Operativo")
```
```dax
Unidades No Operativas = [Unidades Desplegadas] - [Unidades Operativas]
```
```dax
% Disponibilidad Flota = DIVIDE([Unidades Operativas], [Unidades Desplegadas])
```
```dax
% No Operativo = DIVIDE([Unidades No Operativas], [Unidades Desplegadas])
```

`COALESCE` evita que las tarjetas queden en blanco cuando un cliente no tiene ninguna unidad en ese estado:

```dax
U. Mantenimiento = COALESCE(CALCULATE([Unidades Desplegadas], fact_registro_activos[estado] = "Mantenimiento"), 0)
```
```dax
U. Standby = COALESCE(CALCULATE([Unidades Desplegadas], fact_registro_activos[estado] = "Standby"), 0)
```

## Vida útil y renovación

Columnas calculadas en `fact_registro_activos`:

```dax
Fin Vida = EDATE(fact_registro_activos[fecha_despliegue], fact_registro_activos[vida_util_meses])
```
```dax
Anio Fin Vida = YEAR(fact_registro_activos[Fin Vida])
```
```dax
Anio Despliegue = YEAR(fact_registro_activos[fecha_despliegue])
```

## Repuestos

```dax
Consumo Spares =
CALCULATE(
    -SUM(fact_movimientos_inventario[cantidad]),
    fact_movimientos_inventario[cantidad] < 0,
    dim_articulos_inventario[categoria] = "Spare / Repuesto"
)
```

La tabla de movimientos usa signo: entradas positivas, salidas negativas. La medida aísla las negativas y les invierte el signo.

```dax
Flota Instalada =
CALCULATE(
    COUNTROWS(fact_registro_activos),
    FILTER(
        ALL(fact_registro_activos),
        fact_registro_activos[fecha_despliegue] <= MAX(Calendario[Date])
    )
)
```

`ALL()` es imprescindible: sin él, el contexto de fecha del eje filtraría también el registro de activos y devolvería solo las altas del mes en lugar de la flota acumulada.

```dax
Spares por Robot = DIVIDE([Consumo Spares], [Flota Instalada])
```

## Alertas de SLA

Umbral de disponibilidad dependiente del tier contratado:

```dax
Alerta SLA =
VAR d = [% Disponibilidad Flota]
VAR t = MIN(dim_clientes[sla_tier])
RETURN
SWITCH(TRUE(),
    t = "Oro"    && d < 1.00, 1,
    t = "Plata"  && d < 0.90, 1,
    t = "Bronce" && d < 0.70, 1,
    0
)
```
```dax
Clientes en Alerta = COUNTROWS(FILTER(VALUES(dim_clientes[client_id]), [Alerta SLA] = 1))
```

## Formato condicional

Medidas que devuelven un color hexadecimal, aplicadas con **Formato condicional → Valor de campo**:

```dax
Color Tier =
SWITCH(MIN(dim_clientes[sla_tier]),
    "Oro",    "#E8B923",
    "Plata",  "#A8B8C8",
    "Bronce", "#C87941",
    "#FFFFFF"
)
```
```dax
Color Disponibilidad =
VAR d = [% Disponibilidad Flota]
RETURN SWITCH(TRUE(), d >= 0.9, "#2ECC71", d >= 0.7, "#E67E22", "#E74C3C")
```

Columna calculada en `dim_clientes` para ordenar el tier como escala ordinal en vez de alfabéticamente (**Ordenar por columna**):

```dax
Orden Tier = SWITCH(dim_clientes[sla_tier], "Oro", 1, "Plata", 2, "Bronce", 3, 4)
```

## Inventario y conciliación

```dax
Valor Inventario = SUMX(dim_articulos_inventario, dim_articulos_inventario[stock_teorico_actual] * dim_articulos_inventario[coste_estandar])
```
```dax
SKUs Bajo Punto de Pedido = COUNTROWS(FILTER(dim_articulos_inventario, dim_articulos_inventario[stock_teorico_actual] < dim_articulos_inventario[punto_pedido]))
```
```dax
Líneas Contadas = COUNTROWS(fact_conteos_fisicos)
```
```dax
Líneas con Discrepancia = CALCULATE([Líneas Contadas], fact_conteos_fisicos[causa_raiz] <> "Sin discrepancia")
```
```dax
% Exactitud Inventario (IRA) = 1 - DIVIDE([Líneas con Discrepancia], [Líneas Contadas])
```
