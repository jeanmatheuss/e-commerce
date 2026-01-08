-- Agregação de pagamentos por order_id
DROP TABLE IF EXISTS agg_payments_by_order;
CREATE TABLE agg_payments_by_order AS
SELECT
  order_id,
  SUM(payment_value) AS pay_total,
  MAX(payment_installments) AS pay_installments_max,
  AVG(payment_installments) AS pay_installments_avg,
  -- shares por tipo (proporção de linhas de pagamento do tipo)
  AVG(CASE WHEN payment_type = 'credit_card' THEN 1.0 ELSE 0.0 END) AS share_credit_card,
  AVG(CASE WHEN payment_type = 'boleto' THEN 1.0 ELSE 0.0 END) AS share_boleto,
  AVG(CASE WHEN payment_type = 'voucher' THEN 1.0 ELSE 0.0 END) AS share_voucher,
  AVG(CASE WHEN payment_type = 'debit_card' THEN 1.0 ELSE 0.0 END) AS share_debit_card
FROM stg_payments
GROUP BY order_id;

CREATE INDEX IF NOT EXISTS idx_agg_payments_order_id ON agg_payments_by_order(order_id);

-- Fato principal: itens + pedido + região + produto
DROP TABLE IF EXISTS fact_order_items;
CREATE TABLE fact_order_items AS
SELECT
  oi.order_id,
  oi.order_item_id,
  o.customer_id,
  cr.customer_state,
  cr.customer_city,
  cr.customer_zip_code_prefix,
  oi.product_id,
  oi.seller_id,
  o.order_status,
  o.order_purchase_timestamp AS purchase_ts,
  oi.price,
  oi.freight_value,
  p.product_category_name,
  p.product_weight_g,
  p.product_length_cm,
  p.product_height_cm,
  p.product_width_cm,
  ap.pay_total,
  ap.pay_installments_max,
  ap.pay_installments_avg,
  ap.share_credit_card,
  ap.share_boleto,
  ap.share_voucher,
  ap.share_debit_card
FROM stg_order_items oi
JOIN stg_orders o
  ON o.order_id = oi.order_id
LEFT JOIN dim_customer_region cr
  ON cr.customer_id = o.customer_id
LEFT JOIN stg_products p
  ON p.product_id = oi.product_id
LEFT JOIN agg_payments_by_order ap
  ON ap.order_id = oi.order_id;

CREATE INDEX IF NOT EXISTS idx_fact_ds ON fact_order_items(purchase_ts);
CREATE INDEX IF NOT EXISTS idx_fact_prod_state ON fact_order_items(product_id, customer_state);
CREATE INDEX IF NOT EXISTS idx_fact_order_status ON fact_order_items(order_status);
