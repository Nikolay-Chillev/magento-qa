#!/bin/bash
# Runs inside the Magento container on every start, through the custom-entrypoint
# hook of magento2-in-a-box. Applies the configuration the test suite relies on and
# then writes a marker that the healthcheck waits for.
# Each setting deviates from Magento defaults on purpose; see "Test environment" in the README.
set -e

rm -f /tmp/qa-config-applied

mysql -u root magento -e "
INSERT INTO core_config_data (scope, scope_id, path, value) VALUES
  ('default', 0, 'system/smtp/transport', 'smtp'),
  ('default', 0, 'system/smtp/host', 'mailpit'),
  ('default', 0, 'system/smtp/port', '1025'),
  ('default', 0, 'system/smtp/auth', 'none'),
  ('default', 0, 'admin/security/password_lifetime', '0'),
  ('default', 0, 'customer/password/password_reset_protection_type', '3')
ON DUPLICATE KEY UPDATE value = VALUES(value);"

# Every order reserves stock and no queue consumer ever releases it, so repeated
# test runs on one store would sell products out. Give all simple products plenty
# of stock, except one kept small for the stock-limit test.
LOW_STOCK_SKU="24-UG04"
mysql -u root magento -e "
UPDATE inventory_source_item SET quantity = 100000;
UPDATE cataloginventory_stock_item si
  JOIN catalog_product_entity e ON e.entity_id = si.product_id
  SET si.qty = 100000 WHERE e.type_id IN ('simple', 'virtual');
UPDATE cataloginventory_stock_status ss
  JOIN catalog_product_entity e ON e.entity_id = ss.product_id
  SET ss.qty = 100000 WHERE e.type_id IN ('simple', 'virtual');
UPDATE inventory_source_item SET quantity = 5 WHERE sku = '$LOW_STOCK_SKU';
UPDATE cataloginventory_stock_item si
  JOIN catalog_product_entity e ON e.entity_id = si.product_id
  SET si.qty = 5 WHERE e.sku = '$LOW_STOCK_SKU';
UPDATE cataloginventory_stock_status ss
  JOIN catalog_product_entity e ON e.entity_id = ss.product_id
  SET ss.qty = 5 WHERE e.sku = '$LOW_STOCK_SKU';"

# Bulgarian VAT: 20% on taxable goods for every customer group. Catalog prices stay
# net (Magento's default), so VAT is added at checkout. Idempotent across restarts.
mysql -u root magento -e "
INSERT INTO tax_calculation_rate (tax_country_id, tax_region_id, tax_postcode, code, rate)
  SELECT 'BG', 0, '*', 'BG-VAT-20', 20.0000 FROM DUAL
  WHERE NOT EXISTS (SELECT 1 FROM tax_calculation_rate WHERE code = 'BG-VAT-20');
INSERT INTO tax_calculation_rule (code, priority, position, calculate_subtotal)
  SELECT 'Bulgarian VAT', 0, 0, 0 FROM DUAL
  WHERE NOT EXISTS (SELECT 1 FROM tax_calculation_rule WHERE code = 'Bulgarian VAT');
INSERT INTO tax_calculation
    (tax_calculation_rate_id, tax_calculation_rule_id, customer_tax_class_id, product_tax_class_id)
  SELECT rate.tax_calculation_rate_id, rule.tax_calculation_rule_id, customer.class_id, product.class_id
  FROM tax_calculation_rate rate, tax_calculation_rule rule, tax_class customer, tax_class product
  WHERE rate.code = 'BG-VAT-20' AND rule.code = 'Bulgarian VAT'
    AND customer.class_name = 'Retail Customer' AND customer.class_type = 'CUSTOMER'
    AND product.class_name = 'Taxable Goods' AND product.class_type = 'PRODUCT'
    AND NOT EXISTS (
      SELECT 1 FROM tax_calculation existing
      WHERE existing.tax_calculation_rate_id = rate.tax_calculation_rate_id
        AND existing.tax_calculation_rule_id = rule.tax_calculation_rule_id);"

# The image warms the config cache at build time, so the new values only take
# effect after the config cache is cleaned.
php bin/magento cache:clean config > /dev/null

touch /tmp/qa-config-applied
