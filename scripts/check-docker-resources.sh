#!/bin/bash
set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Get Docker resources
DOCKER_MEM_BYTES=$(docker info --format '{{.MemTotal}}' 2>/dev/null || echo "0")
DOCKER_CPU=$(docker info --format '{{.NCPU}}' 2>/dev/null || echo "0")
DOCKER_MEM_GB=$((DOCKER_MEM_BYTES / 1024 / 1024 / 1024))

# Requirements
MIN_MEM_GB=6
MIN_CPU=4
RECOMMENDED_MEM_GB=10
RECOMMENDED_CPU=8

printf "  %-20s " "Docker resources..."

# Check memory
if [ "$DOCKER_MEM_GB" -lt "$MIN_MEM_GB" ]; then
    echo -e "${RED}✗ INSUFFICIENT${NC}"
    echo ""
    echo "  Docker memory too low: ${DOCKER_MEM_GB}GB (minimum: ${MIN_MEM_GB}GB)"
    echo ""
    echo "  Fix:"
    echo "    macOS:  Docker Desktop → Settings → Resources → Memory → ${MIN_MEM_GB}GB+"
    echo "    Linux:  Edit /etc/docker/daemon.json"
    echo ""
    exit 1
fi

# Check CPU
if [ "$DOCKER_CPU" -lt "$MIN_CPU" ]; then
    echo -e "${RED}✗ INSUFFICIENT${NC}"
    echo ""
    echo "  Docker CPUs too low: ${DOCKER_CPU} (minimum: ${MIN_CPU})"
    echo ""
    echo "  Fix:"
    echo "    Docker Desktop → Settings → Resources → CPUs → ${MIN_CPU}+"
    echo ""
    exit 1
fi

# Warnings for recommended specs
if [ "$DOCKER_MEM_GB" -lt "$RECOMMENDED_MEM_GB" ] || [ "$DOCKER_CPU" -lt "$RECOMMENDED_CPU" ]; then
    echo -e "${YELLOW}✓ ${DOCKER_MEM_GB}GB, ${DOCKER_CPU} CPUs (below recommended)${NC}"
else
    echo -e "${GREEN}✓ ${DOCKER_MEM_GB}GB, ${DOCKER_CPU} CPUs${NC}"
fi

exit 0
