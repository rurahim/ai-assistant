#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo "=========================================="
echo "🚀 AI Assistant - Setup and Seed Script"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Creating .env from .env.example...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✓ .env created${NC}"
    echo -e "${YELLOW}⚠ Don't forget to add your OPENAI_API_KEY to .env${NC}"
    echo ""
fi

# Start Docker services (just postgres and redis for now)
echo "Starting PostgreSQL and Redis..."
docker-compose up -d postgres redis

# Wait for postgres to be ready
echo "Waiting for PostgreSQL to be ready..."
sleep 5

# Check if postgres is ready
until docker-compose exec -T postgres pg_isready -U ai_assistant -d ai_assistant_db > /dev/null 2>&1; do
    echo "Waiting for PostgreSQL..."
    sleep 2
done
echo -e "${GREEN}✓ PostgreSQL is ready${NC}"

# Check if redis is ready
until docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; do
    echo "Waiting for Redis..."
    sleep 2
done
echo -e "${GREEN}✓ Redis is ready${NC}"

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip install -r requirements.txt > /dev/null 2>&1
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Run seed script
echo ""
echo "Seeding database with test data..."
python -m scripts.seed_data

echo ""
echo -e "${GREEN}=========================================="
echo "✅ Setup Complete!"
echo "==========================================${NC}"
echo ""
echo "To start the API server, run:"
echo "  uvicorn app.main:app --reload"
echo ""
echo "Or with Docker:"
echo "  docker-compose up -d api"
echo ""
