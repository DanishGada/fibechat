#!/bin/bash

# Colors and formatting
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/home/danishg/fibechat/"
DOCKER_CONTAINER_NAME="open-webui"
DEPLOY_BRANCH="release/prod"

echo -e "${GREEN}🚀 Starting production deployment script...${NC}"
echo -e "${CYAN}============================== PRODUCTION DEPLOYMENT START ==============================${NC}"

# Navigate to project directory
echo -e "\n${YELLOW}📂 Navigating to project directory...${NC}"
cd "$PROJECT_DIR" || { echo -e "${RED}❌ Failed to enter project directory!${NC}"; exit 1; }

# Git pull section
echo -e "\n${CYAN}======================= PULLING PRODUCTION CODE ========================${NC}"
echo -e "${YELLOW}🌐 Pulling latest code from ${DEPLOY_BRANCH} branch...${NC}"
git pull origin "$DEPLOY_BRANCH" || { echo -e "${RED}❌ Git pull failed!${NC}"; exit 1; }
echo -e "${GREEN}✅ Production code successfully updated!${NC}"

# Docker container section
echo -e "\n${CYAN}===================== DOCKER CONTAINER SETUP =======================${NC}"
echo -e "${YELLOW}🐳 Searching for Docker container...${NC}"
CONTAINER_ID=$(docker ps -q --filter "name=$DOCKER_CONTAINER_NAME")

if [ -z "$CONTAINER_ID" ]; then
    echo -e "${RED}❌ Error: Docker container '$DOCKER_CONTAINER_NAME' not found!${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Found production container: ${CONTAINER_ID}${NC}"

# File copy section
echo -e "\n${CYAN}===================== COPYING BACKEND FILES =======================${NC}"
echo -e "${YELLOW}📤 Updating production container files...${NC}"

echo -e "\n🔧 Copying backend files..."
docker cp backend/ "$CONTAINER_ID:/app/" || { echo -e "${RED}❌ Failed to copy backend files!${NC}"; exit 1; }

echo -e "\n${GREEN}✅ All production files successfully copied to container!${NC}"

# Restart section
echo -e "\n${CYAN}===================== RESTARTING PRODUCTION CONTAINER ========================${NC}"
echo -e "${YELLOW}🔄 Restarting production container...${NC}"
docker restart "$CONTAINER_ID" || { echo -e "${RED}❌ Failed to restart container!${NC}"; exit 1; }

echo -e "\n${GREEN}✅ Production container successfully restarted!${NC}"
echo -e "${CYAN}============================== PRODUCTION DEPLOYMENT COMPLETE ==============================${NC}"
echo -e "${GREEN}🎉 Production deployment successful! Container ${CONTAINER_ID} updated and running! 🎉${NC}"