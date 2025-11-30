#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."

echo "=== Generating gRPC Code from Protocol Buffers ==="
echo ""

# Check prerequisites
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 is required but not installed."
    exit 1
fi

# Check if grpcio-tools is installed
if ! uv run python -c "import grpc_tools.protoc" 2>/dev/null; then
    echo "ERROR: grpcio-tools is not installed."
    echo "Install it with: uv sync"
    exit 1
fi

# Create output directory
mkdir -p "${PROJECT_ROOT}/src/proto_gen"

# Generate Python code
echo "[1/3] Generating Python gRPC code..."
cd "${PROJECT_ROOT}"

uv run python -m grpc_tools.protoc \
  -I proto \
  --python_out=src/proto_gen \
  --grpc_python_out=src/proto_gen \
  --mypy_out=src/proto_gen \
  proto/*.proto

echo "  ✓ Generated Python code and type stubs"

# Fix imports in generated files
echo "[2/3] Fixing imports in generated files..."

# For macOS (BSD sed) and Linux (GNU sed) compatibility
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    # Fix common_pb2 imports
    find src/proto_gen -name "*_pb2*.py" -type f -exec sed -i '' 's/^import common_pb2/from . import common_pb2/' {} \;
    # Fix embedding_pb2 imports in _grpc files
    find src/proto_gen -name "*_grpc.py" -type f -exec sed -i '' 's/^import embedding_pb2/from . import embedding_pb2/' {} \;
    # Fix search_pb2 imports in _grpc files
    find src/proto_gen -name "*_grpc.py" -type f -exec sed -i '' 's/^import search_pb2/from . import search_pb2/' {} \;
else
    # Linux
    # Fix common_pb2 imports
    find src/proto_gen -name "*_pb2*.py" -type f -exec sed -i 's/^import common_pb2/from . import common_pb2/' {} \;
    # Fix embedding_pb2 imports in _grpc files
    find src/proto_gen -name "*_grpc.py" -type f -exec sed -i 's/^import embedding_pb2/from . import embedding_pb2/' {} \;
    # Fix search_pb2 imports in _grpc files
    find src/proto_gen -name "*_grpc.py" -type f -exec sed -i 's/^import search_pb2/from . import search_pb2/' {} \;
fi

echo "  ✓ Fixed relative imports"

# Verify generated files
echo "[3/3] Verifying generated files..."

EXPECTED_FILES=(
    "common_pb2.py"
    "common_pb2.pyi"
    "embedding_pb2.py"
    "embedding_pb2.pyi"
    "embedding_pb2_grpc.py"
    "search_pb2.py"
    "search_pb2.pyi"
    "search_pb2_grpc.py"
)

ALL_EXIST=true
for file in "${EXPECTED_FILES[@]}"; do
    if [ -f "src/proto_gen/${file}" ]; then
        echo "  ✓ ${file}"
    else
        echo "  ✗ ${file} (MISSING)"
        ALL_EXIST=false
    fi
done

if [ "$ALL_EXIST" = true ]; then
    echo ""
    echo "=== gRPC Code Generation Complete! ==="
    echo ""
    echo "Generated files: src/proto_gen/"
    exit 0
else
    echo ""
    echo "ERROR: Some files were not generated correctly."
    exit 1
fi
