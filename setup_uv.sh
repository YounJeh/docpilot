#!/bin/bash

# Setup UV environment script
set -e

echo "🚀 Setting up UV environment..."

# Install UV if not already installed
if ! command -v uv &> /dev/null; then
    echo "📦 Installing UV..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
fi

# Clean slate: remove existing files to ensure fresh setup
echo "🧹 Cleaning existing environment..."
if [ -d ".venv" ]; then
    rm -rf .venv
fi
if [ -f "pyproject.toml" ]; then
    rm -f pyproject.toml
fi
if [ -f "uv.lock" ]; then
    rm -f uv.lock
fi

# Initialize Python project with pyproject.toml
echo "🔧 Initializing Python project..."
uv init --no-readme

# Install core dependencies from controller.py
echo "📚 Installing core dependencies..."
uv add loguru
uv add python-dotenv
uv add pyyaml
uv add psycopg2-binary
uv add sqlalchemy

# Install additional common dependencies
echo "📚 Installing additional dependencies..."
uv add fastapi uvicorn
uv add requests httpx
uv add pytest pytest-asyncio
uv add alembic
uv add jinja2
uv add python-multipart
uv add polars
uv add pandas
uv add typer
uv add nbformat
uv add python-dotenv
uv add google-api-python-client google-auth-httplib2 google-auth-oauthlib
uv add pypdf

# Install Jupyter dependencies (separate group for better error handling)
echo "📓 Installing Jupyter dependencies..."
uv add jupyter ipykernel notebook

# Development dependencies
echo "🛠️ Installing development dependencies..."
uv add --dev black flake8 mypy
uv add --dev pre-commit
uv add --dev pytest-cov

echo "✅ UV environment setup complete!"
echo "💡 Virtual environment is automatically managed by UV"
echo "💡 To run your controller: uv run python controller.py"