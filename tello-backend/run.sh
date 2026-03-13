#!/bin/bash

# Diagnostic script for Tello Backend + MCP Inspector setup
# Run this from your tello-backend directory

echo "🔍 Tello Backend + MCP Diagnostic Script"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check 1: Docker Container
echo -e "${BLUE}[1] Docker Container Status${NC}"
if docker ps | grep -q tello-backend; then
    echo -e "${GREEN}✓${NC} Container 'tello-backend' is running"
    
    # Get container details
    NETWORK_MODE=$(docker inspect tello-backend --format='{{.HostConfig.NetworkMode}}' 2>/dev/null)
    echo "   Network mode: $NETWORK_MODE"
    
    # Check if using port mapping
    PORT_BINDINGS=$(docker inspect tello-backend --format='{{.HostConfig.PortBindings}}' 2>/dev/null)
    if [ "$PORT_BINDINGS" != "map[]" ] && [ "$NETWORK_MODE" = "host" ]; then
        echo -e "${YELLOW}⚠${NC} Warning: Port bindings detected with host networking"
        echo "   Port bindings are ignored with host networking!"
        echo "   Consider removing -p flags from docker run command"
    fi
    
elif docker ps -a | grep -q tello-backend; then
    echo -e "${YELLOW}⚠${NC} Container 'tello-backend' exists but is not running"
    echo "   Status:"
    docker ps -a | grep tello-backend | sed 's/^/   /'
    echo ""
    echo "   Recent logs:"
    docker logs --tail 5 tello-backend 2>&1 | sed 's/^/   /'
else
    echo -e "${RED}✗${NC} Container 'tello-backend' not found"
fi
echo ""

# Check 2: Port Availability
echo -e "${BLUE}[2] Port Availability Check${NC}"
for port in 8080 3001 3002; do
    if lsof -i :$port >/dev/null 2>&1; then
        PROCESS=$(lsof -i :$port | tail -1 | awk '{print $1}')
        PID=$(lsof -i :$port | tail -1 | awk '{print $2}')
        echo -e "${GREEN}✓${NC} Port $port in use by: $PROCESS (PID: $PID)"
    else
        echo -e "${YELLOW}○${NC} Port $port available (nothing listening)"
    fi
done
echo ""

# Check 3: Backend API Accessibility
echo -e "${BLUE}[3] Backend API Accessibility${NC}"
for port in 8080 3001 3002; do
    for endpoint in health "" status; do
        url="http://localhost:$port/$endpoint"
        response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "$url" 2>/dev/null)
        if [ "$response" = "200" ] || [ "$response" = "301" ] || [ "$response" = "302" ]; then
            echo -e "${GREEN}✓${NC} $url responding (HTTP $response)"
        elif [ "$response" = "000" ]; then
            echo -e "${YELLOW}○${NC} $url not responding (connection failed)"
        else
            echo -e "${YELLOW}○${NC} $url returned HTTP $response"
        fi
    done
done
echo ""

# Check 4: Tello WiFi Connection
echo -e "${BLUE}[4] Tello WiFi Connection${NC}"
if ping -c 1 -W 2 192.168.10.1 >/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Connected to Tello at 192.168.10.1"
else
    echo -e "${RED}✗${NC} Cannot reach Tello at 192.168.10.1"
    echo "   Make sure you're connected to Tello WiFi (TELLO-XXXXXX)"
fi
echo ""

# Check 5: MCP Server Files
echo -e "${BLUE}[5] MCP Server Files${NC}"
if [ -f "start_servers.sh" ]; then
    echo -e "${GREEN}✓${NC} start_servers.sh found"
    if [ -x "start_servers.sh" ]; then
        echo -e "${GREEN}✓${NC} start_servers.sh is executable"
    else
        echo -e "${YELLOW}⚠${NC} start_servers.sh is not executable"
        echo "   Run: chmod +x start_servers.sh"
    fi
    
    # Check what it contains
    if grep -q "TELLO_BACKEND_URL" start_servers.sh; then
        echo -e "${GREEN}✓${NC} start_servers.sh references TELLO_BACKEND_URL"
    fi
else
    echo -e "${RED}✗${NC} start_servers.sh not found in current directory"
    echo "   Current directory: $(pwd)"
fi

# Check for MCP server files
for file in mcp-server.js mcp-server.py server.js server.py; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} Found $file"
    fi
done
echo ""

# Check 6: Environment Variables
echo -e "${BLUE}[6] Environment Variables${NC}"
if [ -n "$TELLO_BACKEND_URL" ]; then
    echo -e "${GREEN}✓${NC} TELLO_BACKEND_URL is set to: $TELLO_BACKEND_URL"
else
    echo -e "${YELLOW}○${NC} TELLO_BACKEND_URL not set in environment"
    echo "   Check if start_servers.sh sets it internally"
fi

if [ -n "$TELLO_IP" ]; then
    echo "   TELLO_IP: $TELLO_IP"
else
    echo "   TELLO_IP: not set (will use default)"
fi
echo ""

# Check 7: Node.js/Python Setup
echo -e "${BLUE}[7] Runtime Environment${NC}"
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo -e "${GREEN}✓${NC} Node.js installed: $NODE_VERSION"
else
    echo -e "${YELLOW}○${NC} Node.js not found"
fi

if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}✓${NC} Python installed: $PYTHON_VERSION"
else
    echo -e "${YELLOW}○${NC} Python3 not found"
fi

if [ -f "package.json" ]; then
    echo -e "${GREEN}✓${NC} package.json found"
    if [ -d "node_modules" ]; then
        echo -e "${GREEN}✓${NC} node_modules exists"
    else
        echo -e "${YELLOW}⚠${NC} node_modules missing - run: npm install"
    fi
fi
echo ""

# Summary and Recommendations
echo "=========================================="
echo -e "${BLUE}📋 Summary & Recommendations${NC}"
echo ""

# Determine likely issue
if ! docker ps | grep -q tello-backend; then
    echo -e "${RED}Issue:${NC} Docker container not running"
    echo "Fix: docker-compose up -d"
    echo "  or: docker start tello-backend"
    echo ""
fi

# Check for port mapping + host network issue
if docker inspect tello-backend --format='{{.HostConfig.NetworkMode}}' 2>/dev/null | grep -q "host"; then
    PORT_BINDINGS=$(docker inspect tello-backend --format='{{.HostConfig.PortBindings}}' 2>/dev/null)
    if [ "$PORT_BINDINGS" != "map[]" ]; then
        echo -e "${YELLOW}⚠ Issue:${NC} Port mappings with host networking"
        echo "Your docker run command has -p flags with --network host"
        echo ""
        echo -e "${GREEN}Fix:${NC} Remove port mappings:"
        echo "  docker stop tello-backend && docker rm tello-backend"
        echo "  docker run -d --network host --name tello-backend tello-backend"
        echo ""
    fi
fi

# Check if any API is responding
API_FOUND=false
for port in 8080 3001 3002; do
    if curl -s -o /dev/null --max-time 1 "http://localhost:$port/health" 2>/dev/null; then
        API_FOUND=true
        echo -e "${GREEN}✓ Backend API found at:${NC} http://localhost:$port"
        echo ""
        echo "To connect MCP Inspector:"
        echo "  export TELLO_BACKEND_URL=http://localhost:$port"
        echo "  npx @modelcontextprotocol/inspector ./start_servers.sh"
        echo ""
        break
    fi
done

if [ "$API_FOUND" = false ]; then
    echo -e "${YELLOW}Issue:${NC} Backend API not responding on ports 8080, 3001, 3002"
    echo ""
    echo "Check:"
    echo "  1. Container logs: docker logs tello-backend"
    echo "  2. What port your backend listens on (check code/Dockerfile)"
    echo "  3. If using host networking, ensure no port conflicts"
    echo ""
fi

if [ ! -f "start_servers.sh" ]; then
    echo -e "${YELLOW}Issue:${NC} start_servers.sh not found"
    echo "Make sure you're in the correct directory:"
    echo "  cd /Users/linsun/src/github.com/linsun/tello-backend"
    echo ""
fi

echo -e "${BLUE}Next Steps:${NC}"
echo "1. Fix any issues mentioned above"
echo "2. Run this diagnostic again to verify"
echo "3. Try connecting MCP Inspector with recommended commands"
echo ""
