DROP TABLE IF EXISTS fs_daily_product_region;

-- Base diária agregada
CREATE TABLE fs_daily_product_region AS
WITH base AS (
  SELECT
    DATE(purchase_ts) AS ds,
    product_id,
    customer_state,
    COUNT(DISTINCT order_id) AS n_orders,
    COUNT(*) AS qty, -- itens
    SUM(price) AS sum_price,
    SUM(freight_value) AS sum_freight,
    AVG(price) AS avg_price,
    AVG(freight_value) AS avg_freight,
    COUNT(DISTINCT seller_id) AS n_sellers,
    -- cancelamentos: itens cujo pedido está cancelado
    SUM(CASE WHEN order_status = 'canceled' THEN 1 ELSE 0 END) AS cancel_qty,
    -- pagamentos agregados (média no grão)
    AVG(COALESCE(pay_total, 0.0)) AS pay_total_avg,
    AVG(COALESCE(pay_installments_avg, 0.0)) AS inst_avg,
    MAX(COALESCE(pay_installments_max, 0.0)) AS inst_max,
    AVG(COALESCE(share_credit_card, 0.0)) AS share_credit_card,
    AVG(COALESCE(share_boleto, 0.0)) AS share_boleto,
    AVG(COALESCE(share_voucher, 0.0)) AS share_voucher,
    AVG(COALESCE(share_debit_card, 0.0)) AS share_debit_card
  FROM fact_order_items
  GROUP BY DATE(purchase_ts), product_id, customer_state
),
feats AS (
  SELECT
    ds,
    product_id,
    customer_state,
    n_orders,
    qty,
    cancel_qty,
    (sum_price + sum_freight) AS revenue,
    avg_price,
    avg_freight,
    n_sellers,
    pay_total_avg,
    inst_avg,
    inst_max,
    share_credit_card,
    share_boleto,
    share_voucher,
    share_debit_card,
    CAST(STRFTIME('%w', ds) AS INTEGER) AS dow,
    CAST(STRFTIME('%m', ds) AS INTEGER) AS month,
    CAST(STRFTIME('%W', ds) AS INTEGER) AS week_of_year
  FROM base
)
SELECT
  f.*,

  -- LAGS (SQLite: via subquery correlacionada)
  (SELECT qty FROM feats x WHERE x.product_id=f.product_id AND x.customer_state=f.customer_state AND x.ds=DATE(f.ds,'-1 day'))  AS qty_lag_1,
  (SELECT qty FROM feats x WHERE x.product_id=f.product_id AND x.customer_state=f.customer_state AND x.ds=DATE(f.ds,'-7 day'))  AS qty_lag_7,
  (SELECT qty FROM feats x WHERE x.product_id=f.product_id AND x.customer_state=f.customer_state AND x.ds=DATE(f.ds,'-14 day')) AS qty_lag_14,
  (SELECT qty FROM feats x WHERE x.product_id=f.product_id AND x.customer_state=f.customer_state AND x.ds=DATE(f.ds,'-28 day')) AS qty_lag_28,

  -- Rolling mean 7/28 (média simples, incluindo ds-6..ds)
  (SELECT AVG(qty) FROM feats x
     WHERE x.product_id=f.product_id AND x.customer_state=f.customer_state
       AND x.ds BETWEEN DATE(f.ds,'-6 day') AND f.ds) AS qty_roll_mean_7,

  (SELECT AVG(qty) FROM feats x
     WHERE x.product_id=f.product_id AND x.customer_state=f.customer_state
       AND x.ds BETWEEN DATE(f.ds,'-27 day') AND f.ds) AS qty_roll_mean_28,

  -- Cancel lags
  (SELECT cancel_qty FROM feats x WHERE x.product_id=f.product_id AND x.customer_state=f.customer_state AND x.ds=DATE(f.ds,'-1 day'))  AS cancel_lag_1,
  (SELECT cancel_qty FROM feats x WHERE x.product_id=f.product_id AND x.customer_state=f.customer_state AND x.ds=DATE(f.ds,'-7 day'))  AS cancel_lag_7,
  (SELECT cancel_qty FROM feats x WHERE x.product_id=f.product_id AND x.customer_state=f.customer_state AND x.ds=DATE(f.ds,'-14 day')) AS cancel_lag_14

FROM feats f;

CREATE INDEX IF NOT EXISTS idx_fs_key ON fs_daily_product_region(ds, product_id, customer_state);
