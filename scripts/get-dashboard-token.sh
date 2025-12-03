#!/bin/bash
set -euo pipefail

# Get Kubernetes Dashboard access token
# This token is used to log in to the dashboard

NAMESPACE="kubernetes-dashboard"

# Color codes
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=============================================="
echo "  Kubernetes Dashboard Access Token"
echo -e "==============================================${NC}"
echo ""

# Check if dashboard is deployed
if ! kubectl get namespace ${NAMESPACE} &>/dev/null; then
    echo -e "${YELLOW}Kubernetes Dashboard is not deployed${NC}"
    echo "Run: make cluster-start"
    exit 1
fi

# Check if admin-user exists
if ! kubectl get serviceaccount admin-user -n ${NAMESPACE} &>/dev/null; then
    echo -e "${YELLOW}Admin user not found${NC}"
    echo "Creating admin user..."
    kubectl apply -f - <<EOF
apiVersion: v1
kind: ServiceAccount
metadata:
  name: admin-user
  namespace: ${NAMESPACE}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: admin-user
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: cluster-admin
subjects:
- kind: ServiceAccount
  name: admin-user
  namespace: ${NAMESPACE}
EOF
    echo ""
fi

# Get the token
echo -e "${GREEN}Access Token:${NC}"
echo ""

# For Kubernetes 1.24+ we need to create a token
TOKEN=$(kubectl -n ${NAMESPACE} create token admin-user 2>/dev/null || \
        kubectl -n ${NAMESPACE} get secret $(kubectl -n ${NAMESPACE} get sa admin-user -o jsonpath='{.secrets[0].name}') -o jsonpath='{.data.token}' | base64 --decode)

echo "$TOKEN"
echo ""
echo -e "${BLUE}Dashboard URL:${NC}"
echo "  https://localhost:8443"
echo ""
echo -e "${BLUE}How to access:${NC}"
echo "  1. Run: make open-k8-dashboard"
echo "  2. Click 'Token' option"
echo "  3. Paste the token above"
echo "  4. Click 'Sign In'"
echo ""
echo -e "${YELLOW}Note: You may need to accept the self-signed certificate${NC}"
echo ""
