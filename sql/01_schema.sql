-- ============================================================
-- THOKER Asset & Inventory Control — Base de datos completa
-- Esquema estrella: 3 dimensiones + 4 tablas de hechos
-- Generado el 2026-08-11 · Fecha de corte de datos: 31/07/2026
-- Uso: ejecutar el script entero en MySQL Workbench (Ctrl+Shift+Enter)
-- y luego Database -> Reverse Engineer para ver el diagrama EER.
-- ============================================================

DROP DATABASE IF EXISTS thoker;
CREATE DATABASE thoker CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE thoker;

-- ---------- DIMENSIONES ----------

CREATE TABLE dim_clientes (
  client_id        VARCHAR(10)  NOT NULL,
  cliente          VARCHAR(100) NOT NULL,
  sector           VARCHAR(50)  NOT NULL,
  ciudad           VARCHAR(60)  NOT NULL,
  pais             VARCHAR(60)  NOT NULL,
  lat              DECIMAL(9,4) NOT NULL,
  lon              DECIMAL(9,4) NOT NULL,
  inicio_contrato  DATE         NOT NULL,
  sla_tier         VARCHAR(20)  NOT NULL,
  PRIMARY KEY (client_id)
) ENGINE=InnoDB;

CREATE TABLE dim_modelos (
  model_id            VARCHAR(10)  NOT NULL,
  modelo              VARCHAR(60)  NOT NULL,
  familia             VARCHAR(60)  NOT NULL,
  coste_unitario      INT          NOT NULL,
  vida_util_meses     INT          NOT NULL,
  valor_residual_pct  DECIMAL(4,2) NOT NULL,
  PRIMARY KEY (model_id)
) ENGINE=InnoDB;

CREATE TABLE dim_articulos_inventario (
  sku                    VARCHAR(10)   NOT NULL,
  descripcion            VARCHAR(100)  NOT NULL,
  categoria              VARCHAR(40)   NOT NULL,
  coste_estandar         DECIMAL(10,2) NOT NULL,
  lead_time_dias         INT           NOT NULL,
  proveedor              VARCHAR(60)   NOT NULL,
  stock_inicial_ene25    INT           NOT NULL,
  stock_teorico_actual   INT           NOT NULL,
  demanda_media_mensual  DECIMAL(10,1) NOT NULL,
  stock_seguridad        INT           NOT NULL,
  punto_pedido           INT           NOT NULL,
  PRIMARY KEY (sku)
) ENGINE=InnoDB;

-- ---------- HECHOS ----------

-- Nota: fact_registro_activos es tabla de hechos respecto a las dimensiones
-- cliente/modelo, pero actúa a la vez como "dimensión" (1 fila por robot)
-- para fact_depreciacion_mensual. Por eso su PK es asset_id.
CREATE TABLE fact_registro_activos (
  asset_id             VARCHAR(12)   NOT NULL,
  model_id             VARCHAR(10)   NOT NULL,
  client_id            VARCHAR(10)   NOT NULL,
  fecha_despliegue     DATE          NOT NULL,
  coste_adquisicion    DECIMAL(12,2) NOT NULL,
  vida_util_meses      INT           NOT NULL,
  valor_residual       DECIMAL(12,2) NOT NULL,
  estado               VARCHAR(20)   NOT NULL,
  horas_operadas       INT           NOT NULL,
  dep_mensual          DECIMAL(10,2) NOT NULL,
  meses_depreciados    DECIMAL(6,1)  NOT NULL,
  dep_acumulada        DECIMAL(12,2) NOT NULL,
  valor_neto_contable  DECIMAL(12,2) NOT NULL,
  vida_restante_meses  DECIMAL(6,1)  NOT NULL,
  PRIMARY KEY (asset_id),
  CONSTRAINT fk_activos_modelo  FOREIGN KEY (model_id)  REFERENCES dim_modelos (model_id),
  CONSTRAINT fk_activos_cliente FOREIGN KEY (client_id) REFERENCES dim_clientes (client_id)
) ENGINE=InnoDB;

CREATE TABLE fact_depreciacion_mensual (
  id                   INT AUTO_INCREMENT NOT NULL,
  asset_id             VARCHAR(12)   NOT NULL,
  mes                  DATE          NOT NULL,
  dep_acumulada        DECIMAL(12,2) NOT NULL,
  valor_neto_contable  DECIMAL(12,2) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_dep_asset_mes (asset_id, mes),
  CONSTRAINT fk_dep_activo FOREIGN KEY (asset_id) REFERENCES fact_registro_activos (asset_id)
) ENGINE=InnoDB;

CREATE TABLE fact_movimientos_inventario (
  id        INT AUTO_INCREMENT NOT NULL,
  fecha     DATE        NOT NULL,
  sku       VARCHAR(10) NOT NULL,
  tipo      VARCHAR(40) NOT NULL,
  cantidad  INT         NOT NULL,
  PRIMARY KEY (id),
  KEY idx_mov_sku_fecha (sku, fecha),
  CONSTRAINT fk_mov_sku FOREIGN KEY (sku) REFERENCES dim_articulos_inventario (sku)
) ENGINE=InnoDB;

CREATE TABLE fact_conteos_fisicos (
  id                   INT AUTO_INCREMENT NOT NULL,
  fecha_conteo         DATE          NOT NULL,
  sku                  VARCHAR(10)   NOT NULL,
  stock_teorico        INT           NOT NULL,
  stock_fisico         INT           NOT NULL,
  discrepancia_uds     INT           NOT NULL,
  discrepancia_valor   DECIMAL(12,2) NOT NULL,
  causa_raiz           VARCHAR(60)   NOT NULL,
  estado_conciliacion  VARCHAR(40)   NOT NULL,
  PRIMARY KEY (id),
  KEY idx_conteo_sku_fecha (sku, fecha_conteo),
  CONSTRAINT fk_conteo_sku FOREIGN KEY (sku) REFERENCES dim_articulos_inventario (sku)
) ENGINE=InnoDB;

-- ---------- DATOS ----------



-- dim_clientes (14 filas)
