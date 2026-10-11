#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

if [ -f "$DIR/.venv/bin/python" ]; then
    PYTHON="$DIR/.venv/bin/python"
else
    PYTHON="python3"
fi

export PYTHONPATH="$DIR/libs/vigil_common/src:$DIR/services/market_ingest/src"
exec "$PYTHON" -m market_ingest.main "$@"
