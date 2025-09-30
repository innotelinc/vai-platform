#!/usr/bin/env bash
#
# check_pipecat_sync.sh
#
# Verifies that the pipecat submodule commit SHA matches the one in Dockerfile.
# Used by CI/CD to ensure versions are synchronized before merging.
# Exit code 0 = versions match, 1 = mismatch or error
#

set -euo pipefail

# Colors for output (work in both terminal and CI)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🔍 Checking pipecat version synchronization..."

# Check if pipecat submodule exists
if [ ! -d "$PROJECT_ROOT/pipecat" ]; then
    echo -e "${RED}❌ ERROR: pipecat submodule not found at $PROJECT_ROOT/pipecat${NC}"
    echo "Please run: git submodule update --init --recursive"
    exit 1
fi

# Get the commit from the submodule (use short form - 7 chars)
cd "$PROJECT_ROOT/pipecat"
SUBMODULE_COMMIT=$(git rev-parse HEAD)
SUBMODULE_SHORT=$(git rev-parse --short=7 HEAD)

echo "📦 Submodule commit: $SUBMODULE_SHORT"

# Check if Dockerfile exists
DOCKERFILE="$PROJECT_ROOT/api/Dockerfile"
if [ ! -f "$DOCKERFILE" ]; then
    echo -e "${RED}❌ ERROR: Dockerfile not found at $DOCKERFILE${NC}"
    exit 1
fi

# Check if pipecat is installed in Dockerfile
if ! grep -q 'pipecat\.git@' "$DOCKERFILE"; then
    echo -e "${RED}❌ ERROR: No pipecat installation found in api/Dockerfile${NC}"
    echo "Expected to find a line like: RUN pip install 'git+https://github.com/dograh-hq/pipecat.git@<commit>'"
    exit 1
fi

# Get the commit from the Dockerfile (extract whatever length is there)
DOCKERFILE_COMMIT=$(grep -oE 'pipecat\.git@[a-f0-9]+' "$DOCKERFILE" | cut -d'@' -f2)
# Normalize to 7 chars for comparison
DOCKERFILE_SHORT=$(echo "$DOCKERFILE_COMMIT" | cut -c1-7)

echo "🐳 Dockerfile commit: $DOCKERFILE_SHORT"

# Compare the short commits (7 chars)
if [ "$SUBMODULE_SHORT" != "$DOCKERFILE_SHORT" ]; then
    echo ""
    echo -e "${RED}❌ ERROR: Version mismatch detected!${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${YELLOW}Submodule:${NC}  $SUBMODULE_SHORT"
    echo -e "${YELLOW}Dockerfile:${NC} $DOCKERFILE_SHORT"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo -e "${BLUE}👉 TO FIX: Update the pipecat commit in api/Dockerfile to match the submodule${NC}"
    echo ""
    echo "Update api/Dockerfile line with pipecat installation to use commit: $SUBMODULE_SHORT"
    echo "Then commit and push the updated api/Dockerfile"
    echo ""
    
    # For GitHub Actions, output in annotation format for PR checks
    if [ "${GITHUB_ACTIONS:-false}" == "true" ]; then
        echo "::error file=api/Dockerfile,title=Pipecat Version Mismatch::Dockerfile has pipecat@$DOCKERFILE_SHORT but submodule is at $SUBMODULE_SHORT. Please update api/Dockerfile to use commit $SUBMODULE_SHORT"
    fi
    
    exit 1
fi

# Success!
echo ""
echo -e "${GREEN}✅ SUCCESS: Pipecat versions are synchronized!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}Both using commit: $SUBMODULE_SHORT${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

exit 0