#!/bin/bash
# Returns a list of service names by discovering Dockerfiles
# Usage: SERVICES=($(./scripts/list-services.sh))

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."

cd "${PROJECT_ROOT}"

# Discover services from Dockerfiles and output them sorted
for dockerfile in infra/docker/Dockerfile.*; do
    if [ -f "$dockerfile" ]; then
        basename "$dockerfile" | sed 's/Dockerfile\.//'
    fi
done | sort
