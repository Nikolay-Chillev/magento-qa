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

# The image warms the config cache at build time, so the new values only take
# effect after the config cache is cleaned.
php bin/magento cache:clean config > /dev/null

touch /tmp/qa-config-applied
