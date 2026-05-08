#!/bin/bash
WORK_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$WORK_DIR" || exit
docker compose down
echo "aigen_server stopped"
