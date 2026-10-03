#!/usr/bin/env bash
# Starts the Magento + Mailpit environment and applies the configuration
# the tests rely on. Safe to run repeatedly.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Starting containers (first start can take a minute)..."
docker compose up -d --wait

magento() {
  docker exec magento php bin/magento "$@"
}

echo "Routing outgoing email to Mailpit..."
magento config:set system/smtp/transport smtp
magento config:set system/smtp/host mailpit
magento config:set system/smtp/port 1025
magento config:set system/smtp/auth none
magento cache:flush config > /dev/null

echo
echo "Ready:"
echo "  Storefront  http://localhost:8080/"
echo "  Admin       http://localhost:8080/admin"
echo "  Mailpit     http://localhost:8025/"
