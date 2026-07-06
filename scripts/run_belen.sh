#!/bin/bash
# Lanzador de desarrollo de Belen

set -e

cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
    echo "❌ .venv no existe. Corré scripts/install.sh primero."
    exit 1
fi

source .venv/bin/activate

# Cargar .env si existe
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

exec belen "$@"
