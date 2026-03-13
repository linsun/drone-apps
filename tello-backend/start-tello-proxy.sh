#!/bin/bash

# Start Tello Proxy Service on Mac
# This service runs natively and provides HTTP API for Tello drone control

set -e

echo "🚁 Tello Proxy Service Launcher"
echo "================================"
echo ""

# Check Python
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Python 3 not found"
    exit 1
fi

# Check Tello WiFi connection
echo "🔍 Checking Tello connectivity..."
if ping -c 1 -W 2 192.168.10.1 >/dev/null 2>&1; then
    echo "✅ Tello reachable at 192.168.10.1"
else
    echo "⚠️  Cannot reach Tello at 192.168.10.1"
    echo "   Please connect to Tello WiFi (TELLO-XXXXXX)"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi
echo ""

# Check dependencies
echo "📦 Checking dependencies..."
MISSING_DEPS=()

python3 -c "import flask" 2>/dev/null || MISSING_DEPS+=("flask")
python3 -c "import flask_cors" 2>/dev/null || MISSING_DEPS+=("flask-cors")
python3 -c "import mcp" 2>/dev/null || MISSING_DEPS+=("mcp")
python3 -c "import cv2" 2>/dev/null || MISSING_DEPS+=("opencv-python-headless")
python3 -c "import djitellopy" 2>/dev/null || MISSING_DEPS+=("djitellopy")

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    echo "Installing missing dependencies: ${MISSING_DEPS[*]}"
    pip3 install flask flask-cors mcp djitellopy
    # djitellopy pulls in opencv-python; replace with headless variant
    pip3 uninstall -y opencv-python 2>/dev/null || true
    pip3 install opencv-python-headless
fi

# Fix macOS ObjC class conflict between cv2 and av bundled libavdevice
CV2_AVDEVICE=$(python3 -c "import cv2, os; print(os.path.join(os.path.dirname(cv2.__file__), '.dylibs', 'libavdevice.61.3.100.dylib'))" 2>/dev/null || true)
if [ -n "$CV2_AVDEVICE" ] && [ -f "$CV2_AVDEVICE" ]; then
    if strings "$CV2_AVDEVICE" | grep -q "AVFFrameReceiver"; then
        echo "🔧 Patching cv2 libavdevice to fix ObjC class conflict with av..."
        python3 -c "
import sys
path = sys.argv[1]
with open(path, 'rb') as f:
    data = f.read()
data = data.replace(b'AVFFrameReceiver', b'CV2FrameReceiver')
data = data.replace(b'AVFAudioReceiver', b'CV2AudioReceiver')
with open(path, 'wb') as f:
    f.write(data)
" "$CV2_AVDEVICE"
        codesign --force --sign - "$CV2_AVDEVICE" 2>/dev/null
        echo "✅ Patched successfully"
    fi
fi

echo "✅ Dependencies OK"
echo ""

# Check if port 5000 is available
if lsof -Pi :50000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Port 50000 is already in use"
    echo ""
    lsof -i :50000
    echo ""
    read -p "Kill the process using port 50000? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        PID=$(lsof -ti :50000)
        kill $PID
        echo "✅ Killed process $PID"
        sleep 1
    else
        exit 1
    fi
fi
echo ""

# Start the proxy service
echo "🚀 Starting Tello Proxy Service with MCP + Video Support..."
echo "   Service will run on http://0.0.0.0:50000"
echo "   REST API + MCP Tools + Video Streaming available"
echo "   Press Ctrl+C to stop"
echo ""

python3 tello-proxy-mcp-video.py
