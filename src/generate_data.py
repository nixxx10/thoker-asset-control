"""
Genera la BBDD sintética de THOKER Robotics para el dashboard de Power BI.
Fecha de corte: 31/07/2026. Todo determinista (seed fija).
Salida: CSVs en ./data (separador coma, decimal punto, UTF-8-BOM para Power BI).
"""
import numpy as np
import pandas as pd
from datetime import date

rng = np.random.default_rng(42)
CUTOFF = pd.Timestamp("2026-07-31")

# ----------------------------------------------------------------------
# 1. DIM CLIENTES (sedes con lat/lon reales de ciudades)
# ----------------------------------------------------------------------
clients = [
    # id, nombre, sector, ciudad, pais, lat, lon, inicio contrato, tier SLA
    ("C01", "Iberia Retail Logistics",   "Retail / Logística",    "Zaragoza",   "España",   41.6488,  -0.8891, "2023-06-01", "Oro"),
    ("C02", "MedFood Processing",        "Alimentación",          "Valencia",   "España",   39.4699,  -0.3763, "2023-09-15", "Plata"),
    ("C03", "EcoWaste Iberia",           "Gestión de residuos",   "Madrid",     "España",   40.4168,  -3.7038, "2024-01-10", "Oro"),
    ("C04", "CatPack Manufacturing",     "Manufactura",           "Terrassa",   "España",   41.5610,   2.0089, "2024-02-20", "Bronce"),
    ("C05", "Lisboa Fulfilment Hub",     "Retail / Logística",    "Lisboa",     "Portugal", 38.7223,  -9.1393, "2024-04-05", "Plata"),
    ("C06", "Rhône Agro Industries",     "Alimentación",          "Lyon",       "Francia",  45.7640,   4.8357, "2024-06-12", "Plata"),
    ("C07", "Hanse 3PL GmbH",            "Retail / Logística",    "Hamburgo",   "Alemania", 53.5511,   9.9937, "2024-09-01", "Oro"),
    ("C08", "Po Valley Components",      "Manufactura",           "Turín",      "Italia",   45.0703,   7.6869, "2024-11-18", "Bronce"),
    ("C09", "BeNe Sorting Center",       "Gestión de residuos",   "Amberes",    "Bélgica",  51.2194,   4.4025, "2025-01-27", "Plata"),
    ("C10", "Basque Steel Works",        "Manufactura",           "Bilbao",     "España",   43.2630,  -2.9350, "2025-03-14", "Bronce"),
    ("C11", "Andalus Fresh Produce",     "Alimentación",          "Sevilla",    "España",   37.3891,  -5.9845, "2025-05-22", "Plata"),
    ("C12", "Bavaria AutoParts AG",      "Manufactura",           "Múnich",     "Alemania", 48.1351,  11.5820, "2025-08-04", "Oro"),
    ("C13", "Loire Textile Group",       "Retail / Logística",    "Nantes",     "Francia",  47.2184,  -1.5536, "2025-10-19", "Bronce"),
    ("C14", "Warsaw Parcel Systems",     "Retail / Logística",    "Varsovia",   "Polonia",  52.2297,  21.0122, "2026-02-09", "Plata"),
]
df_clients = pd.DataFrame(clients, columns=[
    "client_id","cliente","sector","ciudad","pais","lat","lon","inicio_contrato","sla_tier"])

# ----------------------------------------------------------------------
# 2. DIM MODELOS DE ROBOT
# ----------------------------------------------------------------------
models = [
    # id, modelo, familia, coste unitario €, vida útil (meses), valor residual %
    ("M1", "TK-Pick 100",   "Brazo de picking",        95000, 72, 0.05),
    ("M2", "TK-Pick 200X",  "Brazo de picking",       140000, 72, 0.05),
    ("M3", "TK-Sort 300",   "Célula de clasificación",185000, 84, 0.05),
    ("M4", "TK-Move 50",    "Robot móvil (AMR)",       62000, 60, 0.10),
    ("M5", "TK-Vision QC",  "Inspección visual",       78000, 60, 0.05),
]
df_models = pd.DataFrame(models, columns=[
    "model_id","modelo","familia","coste_unitario","vida_util_meses","valor_residual_pct"])

# ----------------------------------------------------------------------
# 3. FACT REGISTRO DE ACTIVOS (unidad a unidad)
# ----------------------------------------------------------------------
# nº de unidades por cliente según tier
units_per_tier = {"Oro": (12, 18), "Plata": (7, 11), "Bronce": (4, 6)}
# mezcla de modelos según sector
sector_mix = {
    "Retail / Logística":  ["M1","M2","M4","M4","M3"],
    "Alimentación":        ["M1","M5","M4","M2"],
    "Gestión de residuos": ["M3","M3","M4","M5"],
    "Manufactura":         ["M2","M5","M4","M1"],
}
statuses = ["Operativo","Operativo","Operativo","Operativo","Operativo",
            "Operativo","Operativo","Mantenimiento","Standby"]

assets = []
serial = 1000
for _, c in df_clients.iterrows():
    lo, hi = units_per_tier[c.sla_tier]
    n_units = int(rng.integers(lo, hi + 1))
    contract_start = pd.Timestamp(c.inicio_contrato)
    for _ in range(n_units):
        m = df_models.set_index("model_id").loc[rng.choice(sector_mix[c.sector])]
        # despliegue entre el inicio de contrato y el corte (sesgo a primeros meses)
        max_days = max((CUTOFF - contract_start).days - 30, 30)
        offset = int(rng.beta(1.3, 2.2) * max_days)
        deploy = contract_start + pd.Timedelta(days=offset)
        status = rng.choice(statuses)
        # unas pocas unidades antiguas retiradas
        months_dep = (CUTOFF.year - deploy.year) * 12 + (CUTOFF.month - deploy.month)
        if months_dep > 30 and rng.random() < 0.06:
            status = "Retirado"
        serial += 1
        assets.append({
            "asset_id": f"TKR-{serial}",
            "model_id": m.name,
            "client_id": c.client_id,
            "fecha_despliegue": deploy.date(),
            "coste_adquisicion": float(m.coste_unitario),
            "vida_util_meses": int(m.vida_util_meses),
            "valor_residual": round(float(m.coste_unitario) * m.valor_residual_pct, 2),
            "estado": status,
            "horas_operadas": int(rng.integers(400, 6200)),
        })
df_assets = pd.DataFrame(assets)

# depreciación lineal a fecha de corte
def dep_fields(r):
    dep_base = r.coste_adquisicion - r.valor_residual
    dep_mensual = dep_base / r.vida_util_meses
    d = pd.Timestamp(r.fecha_despliegue)
    meses = max(0, (CUTOFF.year - d.year) * 12 + (CUTOFF.month - d.month))
    meses = min(meses, r.vida_util_meses)
    dep_acum = round(dep_mensual * meses, 2)
    return pd.Series({
        "dep_mensual": round(dep_mensual, 2),
        "meses_depreciados": meses,
        "dep_acumulada": dep_acum,
        "valor_neto_contable": round(r.coste_adquisicion - dep_acum, 2),
        "vida_restante_meses": int(r.vida_util_meses - meses),
    })
df_assets = pd.concat([df_assets, df_assets.apply(dep_fields, axis=1)], axis=1)

# ----------------------------------------------------------------------
# 4. FACT CALENDARIO DE DEPRECIACIÓN MENSUAL (para gráfico de evolución NBV)
# ----------------------------------------------------------------------
rows = []
for _, a in df_assets.iterrows():
    d0 = pd.Timestamp(a.fecha_despliegue).to_period("M")
    for k in range(int(a.meses_depreciados) + 1):
        p = (d0 + k).to_timestamp("M")
        if p > CUTOFF: break
        dep_a = round(min(k, a.vida_util_meses) * a.dep_mensual, 2)
        rows.append({
            "asset_id": a.asset_id,
            "mes": p.date(),
            "dep_acumulada": dep_a,
            "valor_neto_contable": round(a.coste_adquisicion - dep_a, 2),
        })
df_dep = pd.DataFrame(rows)

# ----------------------------------------------------------------------
# 5. DIM ARTÍCULOS DE INVENTARIO (almacén Barcelona)
# ----------------------------------------------------------------------
cat_specs = {
    # categoria: (n_items, coste unit rango, lead time rango, prefijo)
    "Materia prima":      (14, (8, 120),    (7, 30),  "MP"),
    "Componente":         (22, (40, 900),   (14, 60), "CP"),
    "Semi-acabado":       (12, (900, 6000), (10, 25), "SA"),
    "Producto acabado":   (5,  (62000, 185000), (30, 45), "PA"),
    "Spare / Repuesto":   (12, (60, 1500),  (7, 40),  "SP"),
}
nombres = {
    "Materia prima": ["Perfil aluminio 40x40","Chapa acero S235","Cable AWG16","Filamento PA12","Resina epoxi",
                      "Tornillería M6 inox","Guía lineal 600mm","Correa GT3","Rodamiento 6204","Grasa NLGI-2",
                      "Tubo neumático 8mm","Pintura RAL7016","Cinta LED 24V","Junta tórica kit"],
    "Componente": ["Servomotor 750W","Driver EtherCAT","Cámara industrial 5MP","Lente 8mm","PLC compacto",
                   "Fuente 48V 20A","Pinza eléctrica 2 dedos","Ventosa Ø40","Encoder absoluto","PC industrial",
                   "Switch gestionado 8p","Sensor LiDAR 2D","Batería LiFePO4 48V","Cargador inductivo",
                   "HMI 10''","Relé seguridad","Escáner 3D compacto","Motor rueda AMR","Chasis mecanizado",
                   "Tarjeta GPU edge","Antena 5G industrial","Botonera emergencia"],
    "Semi-acabado": ["Brazo 6DOF ensamblado","Cabezal picking premontado","Torreta visión calibrada",
                     "Base AMR con drivetrain","Armario eléctrico cableado","Célula seguridad premontada",
                     "Kit garra alimentaria","Módulo cinta 2m","Bastidor Sort 300","Pack baterías validado",
                     "Columna elevación","Conjunto sensórica QC"],
    "Producto acabado": ["TK-Pick 100 (FG)","TK-Pick 200X (FG)","TK-Sort 300 (FG)","TK-Move 50 (FG)","TK-Vision QC (FG)"],
    "Spare / Repuesto": ["Ventosa recambio","Correa recambio","Filtro vacío","Fusibles pack","Teclado servicio",
                         "Rueda AMR recambio","Cámara recambio","Driver recambio","Pinza dedos recambio",
                         "Cable troncal 10m","SSD industrial","Kit juntas"],
}
items = []
i = 0
for cat, (n, cost_rg, lt_rg, pref) in cat_specs.items():
    for j in range(n):
        i += 1
        cost = round(float(rng.uniform(*cost_rg)), 2)
        items.append({
            "sku": f"{pref}-{100+j}",
            "descripcion": nombres[cat][j],
            "categoria": cat,
            "coste_estandar": cost,
            "lead_time_dias": int(rng.integers(*lt_rg)),
            "proveedor": rng.choice(["Sumtec BCN","ElectroParts EU","RoboSupply DE","MecanoCat","AsiaComp Ltd","Interno (producción)"]) if cat != "Producto acabado" else "Interno (producción)",
        })
df_items = pd.DataFrame(items)

# ----------------------------------------------------------------------
# 6. FACT MOVIMIENTOS DE INVENTARIO (ene-2025 → jul-2026)
# ----------------------------------------------------------------------
months = pd.period_range("2025-01", "2026-07", freq="M")
mov_rows = []
for _, it in df_items.iterrows():
    # demanda mensual base por categoría (unidades)
    base = {"Materia prima": 120, "Componente": 40, "Semi-acabado": 9,
            "Producto acabado": 3, "Spare / Repuesto": 18}[it.categoria]
    base = base * float(rng.uniform(0.5, 1.6))
    trend = float(rng.uniform(0.01, 0.05))          # crecimiento (empresa escalando)
    for k, m in enumerate(months):
        season = 1 + 0.12 * np.sin(2 * np.pi * (m.month - 3) / 12)
        demand = max(0, rng.poisson(base * (1 + trend) ** k * season))
        receipt = max(0, int(demand * rng.uniform(0.8, 1.25)))
        mid = m.to_timestamp() + pd.Timedelta(days=int(rng.integers(3, 25)))
        if receipt:
            mov_rows.append({"fecha": mid.date(), "sku": it.sku, "tipo": "Entrada compra" if it.proveedor != "Interno (producción)" else "Entrada producción", "cantidad": receipt})
        if demand:
            mov_rows.append({"fecha": (mid + pd.Timedelta(days=3)).date(), "sku": it.sku, "tipo": "Salida consumo" if it.categoria != "Producto acabado" else "Salida despliegue", "cantidad": -int(demand)})
        # ajustes ocasionales (merma, rotura, error registro)
        if rng.random() < 0.05:
            mov_rows.append({"fecha": (mid + pd.Timedelta(days=5)).date(), "sku": it.sku, "tipo": "Ajuste", "cantidad": -int(rng.integers(1, max(2, int(demand * 0.1) + 2)))})
df_mov = pd.DataFrame(mov_rows).sort_values("fecha")

# stock actual = suma de movimientos + colchón inicial
stock0 = {it.sku: int({"Materia prima": 400, "Componente": 150, "Semi-acabado": 30,
                        "Producto acabado": 8, "Spare / Repuesto": 60}[it.categoria] * rng.uniform(0.8, 1.5))
          for _, it in df_items.iterrows()}
net = df_mov.groupby("sku")["cantidad"].sum().to_dict()
df_items["stock_inicial_ene25"] = df_items.sku.map(stock0)
df_items["stock_teorico_actual"] = df_items.apply(lambda r: max(0, stock0[r.sku] + net.get(r.sku, 0)), axis=1)

# safety stock y punto de pedido (para el dashboard)
dem_m = (-df_mov[df_mov.cantidad < 0].groupby("sku").cantidad.sum() / len(months)).to_dict()
df_items["demanda_media_mensual"] = df_items.sku.map(lambda s: round(dem_m.get(s, 0), 1))
df_items["stock_seguridad"] = (df_items.demanda_media_mensual * (df_items.lead_time_dias / 30) * 0.5).round().astype(int)
df_items["punto_pedido"] = (df_items.demanda_media_mensual * (df_items.lead_time_dias / 30) + df_items.stock_seguridad).round().astype(int)

# ----------------------------------------------------------------------
# 7. FACT CONTEOS FÍSICOS TRIMESTRALES (con discrepancias)
# ----------------------------------------------------------------------
count_dates = ["2025-03-31","2025-06-30","2025-09-30","2025-12-31","2026-03-31","2026-06-30"]
causas = ["Merma no registrada","Error de picking","Ubicación equivocada","Consumo sin vale",
          "Error de recepción","Rotura en manipulación","Sin discrepancia"]
cnt_rows = []
for d in count_dates:
    dts = pd.Timestamp(d)
    sample = df_items.sample(frac=0.7, random_state=int(dts.month + dts.year))
    for _, it in sample.iterrows():
        teorico = int(max(0, it.stock_teorico_actual * rng.uniform(0.7, 1.1)))
        if rng.random() < 0.72:
            fisico, causa = teorico, "Sin discrepancia"
        else:
            delta = int(rng.integers(1, max(2, int(teorico * 0.08) + 2))) * rng.choice([-1, -1, -1, 1])
            fisico = max(0, teorico + delta)
            causa = rng.choice(causas[:-1])
        cnt_rows.append({
            "fecha_conteo": d, "sku": it.sku,
            "stock_teorico": teorico, "stock_fisico": fisico,
            "discrepancia_uds": fisico - teorico,
            "discrepancia_valor": round((fisico - teorico) * it.coste_estandar, 2),
            "causa_raiz": causa,
            "estado_conciliacion": "Ajustado en ERP" if pd.Timestamp(d) < pd.Timestamp("2026-06-01") else rng.choice(["Ajustado en ERP","Pendiente investigación"]),
        })
df_counts = pd.DataFrame(cnt_rows)

# ----------------------------------------------------------------------
# EXPORT
# ----------------------------------------------------------------------
out = "data/"
df_clients.to_csv(out + "dim_clientes.csv", index=False, encoding="utf-8-sig")
df_models.to_csv(out + "dim_modelos.csv", index=False, encoding="utf-8-sig")
df_assets.to_csv(out + "fact_registro_activos.csv", index=False, encoding="utf-8-sig")
df_dep.to_csv(out + "fact_depreciacion_mensual.csv", index=False, encoding="utf-8-sig")
df_items.to_csv(out + "dim_articulos_inventario.csv", index=False, encoding="utf-8-sig")
df_mov.to_csv(out + "fact_movimientos_inventario.csv", index=False, encoding="utf-8-sig")
df_counts.to_csv(out + "fact_conteos_fisicos.csv", index=False, encoding="utf-8-sig")

# resumen de control
print("=== RESUMEN ===")
print(f"Clientes: {len(df_clients)}  |  Modelos: {len(df_models)}  |  Unidades desplegadas: {len(df_assets)}")
print(df_assets.estado.value_counts().to_dict())
print(f"Coste adquisición total: €{df_assets.coste_adquisicion.sum():,.0f}")
print(f"Dep. acumulada total:    €{df_assets.dep_acumulada.sum():,.0f}")
print(f"Valor neto contable:     €{df_assets.valor_neto_contable.sum():,.0f}")
assert (df_assets.coste_adquisicion - df_assets.dep_acumulada - df_assets.valor_neto_contable).abs().max() < 0.01
assert (df_assets.valor_neto_contable >= df_assets.valor_residual - 0.01).all()
print(f"Artículos: {len(df_items)}  |  Movimientos: {len(df_mov)}  |  Líneas de conteo: {len(df_counts)}")
disc = df_counts[df_counts.causa_raiz != "Sin discrepancia"]
print(f"Conteos con discrepancia: {len(disc)} ({len(disc)/len(df_counts):.0%})  |  Valor discrepancias: €{disc.discrepancia_valor.sum():,.0f}")
print("Filas depreciación mensual:", len(df_dep))
print("OK - todos los checks pasados")
