#!/bin/bash
set -euo pipefail

REQUIRED_PORTS=(8080 8081 8082 3000 9090 5000)
CONFLICTS=()

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

printf "  %-20s " "Port availability..."

# Check each port
for port in "${REQUIRED_PORTS[@]}"; do
    if lsof -iTCP:$port -sTCP:LISTEN -P -n >/dev/null 2>&1; then
        PROCESS=$(lsof -iTCP:$port -sTCP:LISTEN -P -n 2>/dev/null | tail -n 1 | awk '{print $1}' || echo "unknown")
        CONFLICTS+=("$port ($PROCESS)")
    fi
done

# Report conflicts
if [ ${#CONFLICTS[@]} -gt 0 ]; then
    echo -e "${RED}✗ CONFLICTS DETECTED${NC}"
    echo ""
    echo "  Ports in use:"
    for conflict in "${CONFLICTS[@]}"; do
        echo "    - Port $conflict"
    done
    echo ""
    echo "  Fix options:"
    echo "    1. Stop conflicting services"
    echo "    2. Run: make clean  # Remove old X-RAG cluster"
    echo "    3. Modify ports in infra/kind/cluster-config.yaml"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓ All ports available${NC}"
exit 0
