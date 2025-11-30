#!/bin/bash
set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Get Docker resources
DOCKER_MEM_BYTES=$(docker info --format '{{.MemTotal}}' 2>/dev/null || echo "0")
DOCKER_CORES=$(docker info --format '{{.NCPU}}' 2>/dev/null || echo "0")
DOCKER_MEM_GB=$((DOCKER_MEM_BYTES / 1024 / 1024 / 1024))

# Get system RAM (platform-specific)
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    SYSTEM_MEM_BYTES=$(sysctl -n hw.memsize 2>/dev/null || echo "0")
    SYSTEM_MEM_GB=$((SYSTEM_MEM_BYTES / 1024 / 1024 / 1024))
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    SYSTEM_MEM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}' || echo "0")
    SYSTEM_MEM_GB=$((SYSTEM_MEM_KB / 1024 / 1024))
else
    SYSTEM_MEM_GB=0
fi

# Requirements
MIN_MEM_GB=6
MIN_CORES=4
RECOMMENDED_MEM_GB=10
RECOMMENDED_CORES=8

printf "  %-20s " "Docker resources..."

# Check memory
if [ "$DOCKER_MEM_GB" -lt "$MIN_MEM_GB" ]; then
    echo -e "${RED}✗ INSUFFICIENT${NC}"
    echo ""
    echo "  System RAM: ${SYSTEM_MEM_GB}GB"
    echo "  Docker allocated: ${DOCKER_MEM_GB}GB (minimum: ${MIN_MEM_GB}GB)"
    echo ""
    echo "  Fix: Increase Docker's memory allocation"
    echo "    macOS:  Docker Desktop → Settings → Resources → Memory → ${MIN_MEM_GB}GB+"
    echo "    Linux:  Edit /etc/docker/daemon.json"
    echo ""
    exit 1
fi

# Check cores
if [ "$DOCKER_CORES" -lt "$MIN_CORES" ]; then
    echo -e "${RED}✗ INSUFFICIENT${NC}"
    echo ""
    echo "  Docker cores: ${DOCKER_CORES} (minimum: ${MIN_CORES})"
    echo ""
    echo "  Fix: Increase Docker's core allocation"
    echo "    Docker Desktop → Settings → Resources → CPUs → ${MIN_CORES}+"
    echo ""
    exit 1
fi

# Build status message
if [ "$SYSTEM_MEM_GB" -gt 0 ]; then
    STATUS_MSG="System has ${SYSTEM_MEM_GB}GB, Docker allocated ${DOCKER_MEM_GB}GB, ${DOCKER_CORES} cores"
else
    STATUS_MSG="Docker allocated ${DOCKER_MEM_GB}GB, ${DOCKER_CORES} cores"
fi

# Warnings for recommended specs
if [ "$DOCKER_MEM_GB" -lt "$RECOMMENDED_MEM_GB" ] || [ "$DOCKER_CORES" -lt "$RECOMMENDED_CORES" ]; then
    echo -e "${YELLOW}✓ ${STATUS_MSG}${NC}"
    echo ""
    echo -e "    ${YELLOW}⚠  Recommended: ${RECOMMENDED_MEM_GB}GB RAM, ${RECOMMENDED_CORES} cores${NC}"
    echo -e "    ${YELLOW}⚠  You have: ${DOCKER_MEM_GB}GB RAM allocated to Docker${NC}"
    echo -e "    ${YELLOW}⚠  Fix: Docker Desktop → Settings → Resources → Memory${NC}"
else
    echo -e "${GREEN}✓ ${STATUS_MSG}${NC}"
fi

exit 0
