#!/bin/bash
# Script to build and publish apple-smi to PyPI
#
# Usage:
#   ./scripts/publish.sh          # Build and upload to PyPI
#   ./scripts/publish.sh --test   # Build and upload to TestPyPI
#   ./scripts/publish.sh --build  # Build only (no upload)
#
# Prerequisites:
#   pip install build twine
#
# For PyPI upload, set these environment variables:
#   TWINE_USERNAME: PyPI username (use "__token__" for API token auth)
#   TWINE_PASSWORD: PyPI password or API token
#
# Or configure ~/.pypirc with your credentials.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo -e "${GREEN}=== apple-smi PyPI Publisher ===${NC}"
echo "Project root: $PROJECT_ROOT"

# Parse arguments
TEST_PYPI=false
BUILD_ONLY=false

for arg in "$@"; do
    case $arg in
        --test)
            TEST_PYPI=true
            ;;
        --build)
            BUILD_ONLY=true
            ;;
        --help|-h)
            echo "Usage: $0 [--test] [--build]"
            echo "  --test   Upload to TestPyPI instead of PyPI"
            echo "  --build  Build only, don't upload"
            exit 0
            ;;
    esac
done

# Check for required tools
echo -e "\n${YELLOW}Checking prerequisites...${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 not found${NC}"
    exit 1
fi

# Install build tools if needed
python3 -m pip install --quiet --upgrade build twine

# Clean previous builds
echo -e "\n${YELLOW}Cleaning previous builds...${NC}"
rm -rf dist/ build/ src/*.egg-info

# Build the package
echo -e "\n${YELLOW}Building package...${NC}"
python3 -m build

# Show built files
echo -e "\n${GREEN}Built packages:${NC}"
ls -la dist/

if [ "$BUILD_ONLY" = true ]; then
    echo -e "\n${GREEN}Build complete. Packages are in dist/${NC}"
    exit 0
fi

# Upload to PyPI
if [ "$TEST_PYPI" = true ]; then
    echo -e "\n${YELLOW}Uploading to TestPyPI...${NC}"
    python3 -m twine upload --repository testpypi dist/*
    echo -e "\n${GREEN}Upload complete!${NC}"
    echo "Install with: pip install --index-url https://test.pypi.org/simple/ apple-smi"
else
    echo -e "\n${YELLOW}Uploading to PyPI...${NC}"
    python3 -m twine upload dist/*
    echo -e "\n${GREEN}Upload complete!${NC}"
    echo "Install with: pip install apple-smi"
fi
