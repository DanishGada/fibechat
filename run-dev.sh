#!/bin/bash

# Define color and formatting codes
BOLD='\033[1m'
GREEN='\033[1;32m'
WHITE='\033[1;37m'
RED='\033[0;31m'
NC='\033[0m' # No Color
TICK='\u2713'

echo -e "${WHITE}${BOLD}Starting Open WebUI in development mode...${NC}"

# First build the image with frontend included
echo -e "${GREEN}${BOLD}Step 1:${NC} Building the base image with frontend (one-time setup)..."
docker compose build

# Then run with the dev override
echo -e "${GREEN}${BOLD}Step 2:${NC} Starting services with development configuration..."
docker compose -f docker-compose.yaml -f docker-compose.dev.yaml up -d

echo -e "${GREEN}${BOLD}${TICK} Development environment is running!${NC}"
echo -e "Backend code changes will be reflected immediately without rebuilding."
echo -e "Access the WebUI at http://localhost:3000"
echo
echo -e "To view logs: docker compose logs -f"
echo -e "To stop: docker compose -f docker-compose.yaml -f docker-compose.dev.yaml down"
