#!/bin/bash
set -euo pipefail

REQUIRED_PORTS=(8080 8081 8082 3000 9090 5000)
CONFLICTS=()
CLUSTER_NAME="xrag-k8"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

printf "  %-20s " "Port availability..."

# Check if our cluster is running
CLUSTER_RUNNING=false
if docker ps --format '{{.Names}}' | grep -q "^${CLUSTER_NAME}-control-plane$"; then
    CLUSTER_RUNNING=true
fi

# Check each port
for port in "${REQUIRED_PORTS[@]}"; do
    if lsof -iTCP:$port -sTCP:LISTEN -P -n >/dev/null 2>&1; then
        PROCESS=$(lsof -iTCP:$port -sTCP:LISTEN -P -n 2>/dev/null | tail -n 1 | awk '{print $1}' || echo "unknown")

        # Check if it's Docker using the port (pattern matching for various Docker processes)
        if [[ "$PROCESS" == *"docker"* ]] || [[ "$PROCESS" == "com.docke"* ]]; then
            # Check if it's our cluster
            if $CLUSTER_RUNNING; then
                # Port is being used by Docker, and our cluster is running
                # This is expected - don't report as conflict
                continue
            else
                # Docker is using the port but our cluster isn't running
                # Likely an old/different cluster
                CONFLICTS+=("$port ($PROCESS - likely old cluster)")
            fi
        else
            # Not Docker - definitely a conflict
            CONFLICTS+=("$port ($PROCESS)")
        fi
    fi
done

# Report conflicts
if [ ${#CONFLICTS[@]} -gt 0 ]; then
    echo -e "${RED}✗ CONFLICTS DETECTED${NC}"
    echo ""
    echo "  Ports in use by external processes:"
    for conflict in "${CONFLICTS[@]}"; do
        echo "    - Port $conflict"
    done
    echo ""
    echo "  Fix options:"
    echo "    1. Stop conflicting services"
    echo "    2. Run: make clean  # Remove old clusters"
    echo "    3. Modify ports in infra/kind/cluster-config.yaml"
    echo ""
    exit 1
fi

# All ports are either free or being used by our cluster
if $CLUSTER_RUNNING; then
    echo -e "${GREEN}✓ Ports available (cluster running)${NC}"
else
    echo -e "${GREEN}✓ All ports available${NC}"
fi
exit 0
