#!/bin/bash
# Connect to a pod in the Kubernetes cluster
# Usage: connect-pod.sh <service-name> <namespace>

set -euo pipefail

SERVICE_NAME=$1
NAMESPACE=$2

# Color codes
BLUE='\033[0;34m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== ${SERVICE_NAME} Pods ===${NC}"
echo ""

# Get pods sorted by name
pods=$(kubectl get pods -n "$NAMESPACE" -l app="$SERVICE_NAME" --sort-by=.metadata.name --no-headers -o custom-columns=":metadata.name" 2>/dev/null || true)

if [ -z "$pods" ]; then
    echo -e "${RED}❌ No $SERVICE_NAME pods found${NC}"
    echo ""
    echo "Make sure the cluster is running and the service is deployed."
    echo "Run 'make cluster-status' to check system status."
    exit 1
fi

# Count pods
count=$(echo "$pods" | wc -l | tr -d ' ')

if [ "$count" -eq 1 ]; then
    # Only one pod - connect directly
    pod=$(echo "$pods")
    echo -e "${GREEN}Found 1 pod: $pod${NC}"
    echo ""
    echo "Connecting..."
    echo ""

    # Try bash first, fallback to sh
    if ! kubectl exec -it "$pod" -n "$NAMESPACE" -- /bin/bash 2>/dev/null; then
        kubectl exec -it "$pod" -n "$NAMESPACE" -- /bin/sh
    fi
else
    # Multiple pods - show selection menu
    echo -e "${YELLOW}Found $count pods:${NC}"
    echo ""

    i=1
    while IFS= read -r pod; do
        echo "  $i) $pod"
        i=$((i + 1))
    done <<< "$pods"

    echo ""
    echo -n "Select pod number (1-$count): "
    read -r num

    # Validate input is a number
    if ! [[ "$num" =~ ^[0-9]+$ ]]; then
        echo ""
        echo -e "${RED}❌ Invalid input - must be a number${NC}"
        exit 1
    fi

    # Validate input is in range
    if [ "$num" -lt 1 ] || [ "$num" -gt "$count" ]; then
        echo ""
        echo -e "${RED}❌ Invalid selection - must be between 1 and $count${NC}"
        exit 1
    fi

    # Get selected pod
    pod=$(echo "$pods" | sed -n "${num}p")

    echo ""
    echo -e "${GREEN}Connecting to: $pod${NC}"
    echo ""

    # Try bash first, fallback to sh
    if ! kubectl exec -it "$pod" -n "$NAMESPACE" -- /bin/bash 2>/dev/null; then
        kubectl exec -it "$pod" -n "$NAMESPACE" -- /bin/sh
    fi
fi
