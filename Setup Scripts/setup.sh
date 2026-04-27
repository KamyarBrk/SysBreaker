#!/usr/bin/env bash
set -e

echo "Checking Python version..."
if ! command -v python3 &>/dev/null; then
    echo "Python 3.12+ required but not found."
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [[ "$(echo "$PY_VERSION < 3.12" | bc)" -eq 1 ]]; then
    echo "Python 3.12+ required. You have $PY_VERSION."
    exit 1
fi

VENV_DIR=".venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv $VENV_DIR
else
    echo "Virtual environment already exists."
fi

echo "Activating virtual environment..."
source $VENV_DIR/bin/activate

echo "Upgrading pip..."
pip install --upgrade pip

if [ -f "Setup_Scripts/requirements.txt" ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
else
    echo "requirements.txt not found!"
    exit 1
fi

echo "Installing Ollama models..."
ollama pull nomic-embed-text

echo "Environment setup complete."
