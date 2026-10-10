#!/usr/bin/env bash
# Starts the Magento + Mailpit environment and waits until it is ready for tests.
# Test-specific configuration is applied inside the container on start
# (docker/magento/custom-entrypoint.sh), so this script only has to wait.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Starting containers (first start can take a minute)..."
docker compose up -d --wait

echo
echo "Ready:"
echo "  Storefront  http://127.0.0.1:8080/"
echo "  Admin       http://127.0.0.1:8080/admin"
echo "  Mailpit     http://localhost:8025/"
