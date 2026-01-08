DROP TABLE IF EXISTS dim_customer_region;
CREATE TABLE dim_customer_region AS 
SELECT 
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix,
    customer_city,
    customer_state
FROM stg_customers;

CREATE INDEX IF NOT EXISTS idx_dim_customer_region_customer_id
ON dim_customer_region(customer_id);

DROP TABLE IF EXISTS dim_zip_geo;
CREATE TABLE dim_zip_geo AS
SELECT 
    geolocation_zip_code_prefix as zip_code_prefix,
    AVG(geolocation_lat) as lat,
    AVG(geolocation_lng) as lng
FROM stg_geolocation
GROUP BY geolocation_zip_code_prefix;

CREATE INDEX IF NOT EXISTS idx_dim_zip_geo_zip
ON dim_zip_geo(zip_code_prefix);