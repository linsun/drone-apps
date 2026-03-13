#!/bin/bash

# Start Tello Backend Servers (for K8s)
# Runs both HTTP API and MCP server

set -e

echo "🚀 Starting Tello Backend Servers..."
echo "===================================="
echo ""

# Check proxy URL
PROXY_URL=${TELLO_PROXY_URL:-http://host.docker.internal:5000}
echo "📡 Proxy URL: $PROXY_URL"
echo ""

# Start HTTP server in background
echo "Starting HTTP API server on port ${HTTP_PORT:-3001}..."
python3 backend_http_server.py &
HTTP_PID=$!
echo "✅ HTTP Server PID: $HTTP_PID"

# Give HTTP server time to start
sleep 2

# Start MCP server in foreground
echo "Starting MCP server on port ${MCP_PORT:-3002}..."
python3 backend_mcp_server.py &
MCP_PID=$!
echo "✅ MCP Server PID: $MCP_PID"

# Wait for both processes
echo ""
echo "✅ Both servers running!"
echo "   HTTP API: http://0.0.0.0:${HTTP_PORT:-3001}/api/*"
echo "   MCP: http://0.0.0.0:${MCP_PORT:-3002}/sse"
echo ""
echo "Press Ctrl+C to stop both servers"

# Handle shutdown
trap "echo ''; echo 'Stopping servers...'; kill $HTTP_PID $MCP_PID 2>/dev/null; exit" INT TERM

# Wait for processes
wait
