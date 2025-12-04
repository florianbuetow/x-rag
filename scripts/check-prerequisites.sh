#!/bin/bash
set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

HAS_ERROR=0

check_command() {
    local cmd=$1
    local min_version=$2
    local install_hint=$3
    
    printf "  %-20s " "$cmd..."
    
    if ! command -v "$cmd" &> /dev/null; then
        echo -e "${RED}✗ NOT FOUND${NC}"
        echo ""
        echo "  $cmd is required but not installed."
        echo "  Install: $install_hint"
        echo ""
        HAS_ERROR=1
        return 1
    fi
    
    # Get version based on command
    case $cmd in
        docker)
            version=$(docker --version 2>/dev/null | cut -d' ' -f3 | tr -d ',')
            ;;
        kubectl)
            version=$(kubectl version --client -o yaml 2>/dev/null | grep gitVersion | cut -d':' -f2 | tr -d ' ' | head -1)
            ;;
        kind)
            version=$(kind version 2>/dev/null | cut -d' ' -f2)
            ;;
        helm)
            version=$(helm version --short 2>/dev/null | cut -d':' -f2 | tr -d ' ' | cut -d'+' -f1)
            ;;
        python3)
            version=$(python3 --version 2>/dev/null | cut -d' ' -f2)
            ;;
        uv)
            version=$(uv --version 2>/dev/null | cut -d' ' -f2)
            ;;
        *)
            version="unknown"
            ;;
    esac
    
    echo -e "${GREEN}✓ $version${NC}"
    return 0
}

echo "Checking prerequisites..."
echo ""

# Check Docker
if ! check_command "docker" "24.0+" "https://docs.docker.com/get-docker/"; then
    :  # Error already printed
elif ! docker info &> /dev/null; then
    echo -e "${RED}✗ Docker daemon not running${NC}"
    echo ""
    echo "  Docker is installed but the daemon is not running."
    echo ""
    echo "  Fix:"
    echo "    macOS:  Start Docker Desktop application"
    echo "    Linux:  sudo systemctl start docker"
    echo ""
    HAS_ERROR=1
fi

# Check kubectl
check_command "kubectl" "1.28+" "brew install kubectl (macOS) | https://kubernetes.io/docs/tasks/tools/" || true

# Check Kind
check_command "kind" "0.20+" "brew install kind (macOS) | curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.23.0/kind-linux-amd64 && chmod +x ./kind && sudo mv ./kind /usr/local/bin/" || true

# Check Helm
check_command "helm" "3.12+" "brew install helm (macOS) | curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash" || true

# Check uv (it will manage Python for us)
check_command "uv" "latest" "curl -LsSf https://astral.sh/uv/install.sh | sh" || true

echo ""

# Check Docker resources
if command -v docker &> /dev/null && docker info &> /dev/null; then
    ./scripts/check-docker-resources.sh || HAS_ERROR=1
fi

echo ""

# Check ports
./scripts/check-ports.sh || HAS_ERROR=1

echo ""

# Check optional tools
echo "Optional tools:"
printf "  %-20s " "grpcurl..."
if command -v grpcurl &> /dev/null; then
    version=$(grpcurl --version 2>&1 | head -1 | cut -d' ' -f2)
    echo -e "${GREEN}✓ $version${NC}"
else
    echo -e "${YELLOW}! NOT FOUND (optional)${NC}"
    echo ""
    echo "  grpcurl is recommended for debugging gRPC services."
    echo "  Install: brew install grpcurl (macOS) | go install github.com/fullstorydev/grpcurl/cmd/grpcurl@latest"
    echo ""
fi

echo ""

if [ $HAS_ERROR -eq 0 ]; then
    echo -e "${GREEN}✓ All prerequisites met${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Copy .env.example to .env"
    echo "  2. Add your OPENAI_API_KEY to .env"
    echo "  3. Run: make init           # Initialize dev environment"
    echo "  4. Run: make cluster-init   # Build Docker images"
    exit 0
else
    echo -e "${RED}✗ Some prerequisites are missing${NC}"
    echo ""
    echo "Please install the missing tools and try again."
    exit 1
fi
