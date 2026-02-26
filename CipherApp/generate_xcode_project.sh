#!/bin/bash

# Cipher iOS App v2.0 - Xcode Project Generator
# Elysian Protocol - Sovereign Intelligence
#
# Requirements:
# - XcodeGen: brew install xcodegen
# - Xcode 15+ with Command Line Tools
#
# Usage:
# cd CipherApp && ./generate_xcode_project.sh

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${BLUE}  ██████╗██╗██████╗ ██╗  ██╗███████╗██████╗ ${NC}"
echo -e "${BLUE} ██╔════╝██║██╔══██╗██║  ██║██╔════╝██╔══██╗${NC}"
echo -e "${BLUE} ██║     ██║██████╔╝███████║█████╗  ██████╔╝${NC}"
echo -e "${BLUE} ██║     ██║██╔═══╝ ██╔══██║██╔══╝  ██╔══██╗${NC}"
echo -e "${BLUE} ╚██████╗██║██║     ██║  ██║███████╗██║  ██║${NC}"
echo -e "${BLUE}  ╚═════╝╚═╝╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝${NC}"
echo -e "${BLUE}          Sovereign Intelligence v2.0          ${NC}"
echo -e "${BLUE}           by Elysian Protocol                 ${NC}"
echo ""

# Check XcodeGen
if ! command -v xcodegen &> /dev/null; then
    echo -e "${YELLOW}XcodeGen not found. Installing via Homebrew...${NC}"
    if command -v brew &> /dev/null; then
        brew install xcodegen
    else
        echo -e "${RED}ERROR: Homebrew is not installed.${NC}"
        echo "Install Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        echo "Then: brew install xcodegen"
        exit 1
    fi
fi

echo -e "${BLUE}XcodeGen:${NC} $(xcodegen version)"
echo ""

# Check project.yml
if [ ! -f "project.yml" ]; then
    echo -e "${RED}ERROR: project.yml not found${NC}"
    echo "Run this script from the CipherApp/ directory"
    exit 1
fi

# File count
SWIFT_FILES=$(find CipherApp -name "*.swift" | wc -l | tr -d ' ')
TOTAL_LINES=$(find CipherApp -name "*.swift" -exec cat {} + | wc -l | tr -d ' ')
echo -e "${BLUE}Swift files:${NC} ${SWIFT_FILES}"
echo -e "${BLUE}Total lines:${NC} ${TOTAL_LINES}"
echo ""

# Generate
echo -e "${BLUE}Generating Xcode project...${NC}"
xcodegen generate

if [ -d "CipherApp.xcodeproj" ]; then
    echo ""
    echo -e "${GREEN}CipherApp.xcodeproj generated successfully${NC}"
else
    echo -e "${RED}Failed to generate project${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Build complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  1. open CipherApp.xcodeproj"
echo "  2. Select your Apple Developer team"
echo "  3. Build & run (Cmd+R)"
echo ""
echo -e "${BLUE}Features in v2.0:${NC}"
echo "  - Streaming responses (token-by-token)"
echo "  - Voice mode with speech recognition"
echo "  - Rich markdown rendering with code blocks"
echo "  - Multi-model auto-routing (Claude/Groq/DeepSeek)"
echo "  - Conversation search & management"
echo "  - Face ID / Touch ID protection"
echo "  - Privacy-first architecture"
echo "  - 4-page onboarding flow"
echo "  - Premium glassmorphism UI"
echo ""
echo -e "${BLUE}Server:${NC} http://localhost:8000 (configurable in Settings)"
echo ""
