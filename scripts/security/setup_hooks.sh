#!/bin/bash
# Setup git hooks for secret scanning

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔧 Setting up git hooks for secret scanning...${NC}"

# Configure git to use custom hooks directory
git config core.hooksPath .githooks

echo -e "${GREEN}✅ Git hooks configured!${NC}"
echo ""
echo "Hooks enabled:"
echo "  • pre-push: Secret scanning with gitleaks"
echo ""
echo "To test manually:"
echo "  ./scripts/security/check_secrets.sh"
echo ""
echo "To disable hooks temporarily:"
echo "  git push --no-verify"