
CREATE INDEX IF NOT EXISTS idx_orders_order_id ON stg_orders(order_id);
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON stg_orders(customer_id); 
CREATE INDEX IF NOT EXISTS idx_items_order_id ON stg_order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_items_product_id ON stg_order_items(product_id); 
CREATE INDEX IF NOT EXISTS idx_items_seller_id ON stg_order_items(seller_id); 
CREATE INDEX IF NOT EXISTS idx_customers_customer_id ON stg_customers(customer_id);
CREATE INDEX IF NOT EXISTS idx_geo_zip ON stg_geolocation(geolocation_zip_code_prefix);
CREATE INDEX IF NOT EXISTS idx_payments_order_id ON stg_payments(order_id); 