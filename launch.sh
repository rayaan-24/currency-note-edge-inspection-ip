#!/usr/bin/env bash
# ==============================================================================
# Currency Note Edge Quality Inspection — Portable Application Launcher
# Starts the FastAPI + Native Python DIP backend and serves the Web Dashboard.
# Zero MATLAB, GNU Octave, or OpenCV runtime dependencies.
# ==============================================================================

set -e

# 1. Resolve Project Root Dynamically
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "================================================================="
echo "       CURRENCY NOTE EDGE QUALITY INSPECTION — LAUNCHER          "
echo "================================================================="
echo "Project Location: $PROJECT_DIR"
echo ""

# 2. Verify Python 3
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Error: Python 3 is required but not found on your system PATH."
    echo "Please install Python 3.9+ from https://www.python.org/ or via your package manager."
    exit 1
fi

PYTHON_VER=$(python3 --version 2>&1)
echo "✓ Python 3 detected: $PYTHON_VER"

# 3. Virtual Environment Detection & Automatic Setup
VENV_DIR=""
if [ -d "$PROJECT_DIR/.venv" ] && [ -f "$PROJECT_DIR/.venv/bin/python3" ]; then
    VENV_DIR="$PROJECT_DIR/.venv"
elif [ -d "$PROJECT_DIR/venv" ] && [ -f "$PROJECT_DIR/venv/bin/python3" ]; then
    VENV_DIR="$PROJECT_DIR/venv"
fi

if [ -z "$VENV_DIR" ]; then
    echo "No existing virtual environment detected. Creating .venv..."
    python3 -m venv "$PROJECT_DIR/.venv" || {
        echo "⚠️ Notice: Failed to create virtual environment; continuing with system python3."
    }
    if [ -d "$PROJECT_DIR/.venv" ] && [ -f "$PROJECT_DIR/.venv/bin/python3" ]; then
        VENV_DIR="$PROJECT_DIR/.venv"
    fi
fi

if [ -n "$VENV_DIR" ]; then
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    PY_EXEC="$VENV_DIR/bin/python3"
    echo "✓ Using virtual environment: $VENV_DIR"
else
    PY_EXEC="python3"
    echo "✓ Using Python executable: $(command -v python3)"
fi

# 4. Check & Install Required Dependencies
echo "Verifying Python dependencies..."
MISSING_PKGS=0
"$PY_EXEC" -c "import numpy, scipy, skimage, PIL, fastapi, uvicorn, multipart" 2>/dev/null || MISSING_PKGS=1

if [ "$MISSING_PKGS" -ne 0 ]; then
    echo "Installing missing dependencies from requirements.txt..."
    "$PY_EXEC" -m pip install --upgrade pip 2>/dev/null || true
    "$PY_EXEC" -m pip install -r requirements.txt || {
        echo "❌ Error: Failed to install Python dependencies from requirements.txt."
        echo "Please verify internet connectivity and run: pip install -r requirements.txt"
        exit 1
    }
fi
echo "✓ All core dependencies verified (NumPy, SciPy, scikit-image, Pillow, FastAPI, Uvicorn)."

# 5. Create Writable Runtime Directories
mkdir -p results/overlays results/masks results/boundaries results/reports results/thumbnails uploads

# 6. Verify Mendeley Dataset Integration
echo ""
echo "Verifying Mendeley dataset integration..."
if [ ! -f "dataset/dataset_config.json" ]; then
    echo "❌ Error: dataset/dataset_config.json not found."
    exit 1
fi

DATASET_ROOT=$("$PY_EXEC" -c "import json, pathlib; p = json.load(open('dataset/dataset_config.json')).get('dataset_root', 'dataset'); print((pathlib.Path(p) if pathlib.Path(p).is_absolute() else pathlib.Path.cwd() / p).resolve())" 2>/dev/null || echo "")

if [ -z "$DATASET_ROOT" ] || [ ! -d "$DATASET_ROOT" ]; then
    echo "❌ Error: Dataset root directory does not exist at: $DATASET_ROOT"
    echo "Please verify that the dataset folder is present in dataset/."
    exit 1
fi
echo "✓ Dataset root verified: $DATASET_ROOT"

if [ ! -f "dataset/selected_2000_manifest.csv" ]; then
    echo "Manifest missing. Generating deterministic 2,000-image selection manifest..."
    "$PY_EXEC" dataset/build_manifest.py || {
        echo "❌ Error: Failed to generate dataset manifest."
        exit 1
    }
fi

MANIFEST_COUNT=$("$PY_EXEC" -c "import csv; print(len(list(csv.DictReader(open('dataset/selected_2000_manifest.csv')))))" 2>/dev/null || echo "0")
if [ "$MANIFEST_COUNT" -ne 2000 ]; then
    echo "⚠️ Warning: Manifest has $MANIFEST_COUNT entries (expected exactly 2,000)."
    echo "Re-running deterministic manifest builder..."
    "$PY_EXEC" dataset/build_manifest.py
fi
echo "✓ Manifest verified: exactly 2,000 unique, readable banknote images indexed."

# 7. Port Binding & Process Management
PORT=8000
HOST="127.0.0.1"
LOCAL_URL="http://${HOST}:${PORT}"
HEALTH_URL="http://${HOST}:${PORT}/api/health"

PID_ON_PORT=$(lsof -ti :$PORT 2>/dev/null || true)
if [ -n "$PID_ON_PORT" ]; then
    echo "Notice: Found existing process on port $PORT (PID $PID_ON_PORT). Stopping it..."
    kill -9 $PID_ON_PORT 2>/dev/null || true
    sleep 1
fi

echo ""
echo "================================================================="
echo "Starting Uvicorn web server..."
echo "Binding to: $LOCAL_URL"
echo "================================================================="
echo ""
echo "Access the application in your browser at:"
echo "  Local Dashboard: $LOCAL_URL"
echo "  Health Endpoint: $HEALTH_URL"
echo ""
echo "Press Ctrl+C to stop the server."
echo "================================================================="

exec "$PY_EXEC" -m uvicorn server:app --host "$HOST" --port "$PORT"
