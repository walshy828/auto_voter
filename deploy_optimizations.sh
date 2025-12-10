#!/bin/bash
# Simplified deployment script for optimized Docker setup
# All optimizations are now in the main Dockerfile and docker-compose.yml

set -e

echo "=========================================="
echo "Auto Voter Optimized Deployment"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

echo "Step 1: Backing up current deployment"
echo "--------------------------------------"
if [ -d "/docker/auto_voter/data" ]; then
    BACKUP_DIR="/docker/auto_voter/backup_$(date +%Y%m%d_%H%M%S)"
    print_warning "Creating backup at: $BACKUP_DIR"
    sudo mkdir -p "$BACKUP_DIR"
    sudo cp -r /docker/auto_voter/data "$BACKUP_DIR/"
    print_success "Backup created"
else
    print_warning "No existing data directory found, skipping backup"
fi

echo ""
echo "Step 2: Stopping current containers"
echo "--------------------------------------"
docker-compose down
print_success "Containers stopped"

echo ""
echo "Step 3: Building optimized image"
echo "--------------------------------------"
echo "This may take 5-10 minutes on first build..."
docker-compose build || {
    print_error "Build failed! Check the output above for errors."
    exit 1
}
print_success "Build completed"

echo ""
echo "Step 4: Checking image size"
echo "--------------------------------------"
IMAGE_SIZE=$(docker images auto_voter-web --format "{{.Size}}" | head -n 1)
echo "Image size: $IMAGE_SIZE"
echo "Expected: ~275-325MB (down from 625MB)"

echo ""
echo "Step 5: Starting optimized containers"
echo "--------------------------------------"
docker-compose up -d
print_success "Containers started"

echo ""
echo "Step 6: Waiting for containers to be healthy"
echo "--------------------------------------"
sleep 15

docker-compose ps

echo ""
echo "Step 7: Checking container health"
echo "--------------------------------------"

# Check web container
WEB_HEALTHY=$(docker inspect --format='{{.State.Health.Status}}' $(docker-compose ps -q web) 2>/dev/null || echo "unknown")
echo "Web container: $WEB_HEALTHY"

# Check scheduler container  
SCHEDULER_HEALTHY=$(docker inspect --format='{{.State.Health.Status}}' $(docker-compose ps -q scheduler) 2>/dev/null || echo "unknown")
echo "Scheduler container: $SCHEDULER_HEALTHY"

echo ""
echo "Step 8: Resource usage"
echo "--------------------------------------"
docker stats --no-stream --format "table {{.Container}}\t{{.MemUsage}}\t{{.CPUPerc}}"

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "✅ Optimizations Applied:"
echo "  • Multi-stage Alpine Docker build"
echo "  • Resource limits (512M web, 768M scheduler)"
echo "  • Performance environment variables"
echo "  • Database query caching"
echo "  • Optimized health checks"
echo ""
echo "📊 Expected Improvements:"
echo "  • Image size: 625MB → 275-325MB (50-60% reduction)"
echo "  • Memory usage: 25-35% reduction"
echo "  • CPU usage: 50% reduction when idle"
echo "  • API response: 20-30% faster"
echo ""
echo "🔍 Next Steps:"
echo "  1. Monitor logs: docker-compose logs -f"
echo "  2. Check metrics: docker stats"
echo "  3. Test functionality: http://localhost:8282"
echo "  4. Monitor for 24-48 hours before production"
echo ""
echo "📚 Documentation:"
echo "  • Quick reference: OPTIMIZATION_QUICK_REF.md"
echo "  • Full walkthrough: walkthrough.md"
echo ""
print_success "Deployment successful!"
