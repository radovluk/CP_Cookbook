#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build-context"
IMAGE_NAME="optalcp-solver"
IMAGE_TAG="latest"
VENV_SITEPACKAGES="$HOME/optacp/lib/python3.12/site-packages"

echo "=== Assembling Docker build context ==="
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# 1. IBM CP Optimizer binary
echo "  Copying IBM CP Optimizer binary..."
cp ~/cplex_full/CPLEX_Studio2211/cpoptimizer/bin/x86-64_linux/cpoptimizer "$BUILD_DIR/cpoptimizer"

# 2. OptalCP Python API v2026.1.0 (from installed venv site-packages)
echo "  Copying OptalCP Python API (2026.1.0) from venv..."
OPTALCP_PKG="$BUILD_DIR/optalcp-py"
mkdir -p "$OPTALCP_PKG/optalcp"
cp "$VENV_SITEPACKAGES"/optalcp/*.py "$OPTALCP_PKG/optalcp/"
cp "$VENV_SITEPACKAGES"/optalcp/py.typed "$OPTALCP_PKG/optalcp/" 2>/dev/null || true
cat > "$OPTALCP_PKG/pyproject.toml" <<'PYPROJECT'
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "optalcp"
version = "2026.1.0"
description = "Python API for OptalCP constraint programming solver"
requires-python = ">=3.11"
dependencies = ["typing-extensions>=4.0.0"]

[tool.setuptools.packages.find]
include = ["optalcp*"]

[tool.setuptools.package-data]
optalcp = ["py.typed"]
PYPROJECT

# 3. OptalCP binary package (copy from installed site-packages, Linux binary only)
#    Structure: optalcp_bin_pkg/pyproject.toml + optalcp_bin_pkg/optalcp_bin_academic/{__init__.py, bin/}
echo "  Copying OptalCP binary package..."
PKG_DIR="$BUILD_DIR/optalcp_bin_academic/optalcp_bin_academic"
mkdir -p "$PKG_DIR/bin/linux-x64"
cp "$VENV_SITEPACKAGES/optalcp_bin_academic/__init__.py" "$PKG_DIR/"
cp "$VENV_SITEPACKAGES/optalcp_bin_academic/bin/linux-x64/optalcp" "$PKG_DIR/bin/linux-x64/optalcp"
cat > "$BUILD_DIR/optalcp_bin_academic/pyproject.toml" <<'PYPROJECT'
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "optalcp-bin-academic"
version = "2026.1.0"
description = "OptalCP solver binaries - Academic edition"
requires-python = ">=3.11"
dependencies = ["optalcp"]

[tool.setuptools.packages.find]
include = ["optalcp_bin_academic*"]

[tool.setuptools.package-data]
optalcp_bin_academic = ["bin/linux-x64/*"]
PYPROJECT

# 4. Dockerfile
cp "$SCRIPT_DIR/Dockerfile" "$BUILD_DIR/Dockerfile"

echo "=== Build context ready ($(du -sh "$BUILD_DIR" | cut -f1)) ==="
echo ""
echo "=== Building Docker image: $IMAGE_NAME:$IMAGE_TAG ==="
docker build -t "$IMAGE_NAME:$IMAGE_TAG" "$BUILD_DIR"

echo ""
echo "=== Build complete ==="
docker images "$IMAGE_NAME:$IMAGE_TAG"

echo ""
echo "To save and transfer to cluster:"
echo "  docker save $IMAGE_NAME:$IMAGE_TAG | gzip > $SCRIPT_DIR/$IMAGE_NAME.tar.gz"
echo "  rsync -avP -e 'ssh -p 2229' $SCRIPT_DIR/$IMAGE_NAME.tar.gz radovluk@rtime.ciirc.cvut.cz:~/"
echo "  # On the cluster:"
echo "  docker load < ~/$IMAGE_NAME.tar.gz"
echo ""
echo "To run (mounting data from cluster):"
echo "  docker run --rm -v /path/to/data:/workspace $IMAGE_NAME:$IMAGE_TAG python your_script.py"
