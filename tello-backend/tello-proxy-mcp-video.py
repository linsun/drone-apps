#!/usr/bin/env python3
"""
Tello Proxy Service with MCP Support + Video Streaming

This service runs on your Mac and provides:
1. Traditional HTTP REST API endpoints
2. MCP (Model Context Protocol) tools
3. Video streaming via MJPEG
4. Photo capture

Usage:
    python3 tello-proxy-mcp-video.py

Endpoints:
    REST API:
        POST /api/connect          - Connect to Tello
        GET  /api/status           - Get status
        POST /api/start-stream     - Start video stream
        POST /api/stop-stream      - Stop video stream
        GET  /api/video-feed       - MJPEG video stream
        POST /api/capture          - Capture photo
        GET  /api/photo/<filename> - Get captured photo
        POST /api/disconnect       - Disconnect from Tello
        POST /api/takeoff          - Take off
        POST /api/land             - Land
        POST /api/move             - Move (up/down/forward/back/left/right)
        POST /api/rotate           - Rotate (left/right)
        POST /api/command           - Send raw command (for backward compatibility)
        GET  /health               - Health check

    MCP Server (Streamable HTTP):
        POST /mcp                  - MCP streamable HTTP endpoint
"""

import socket
import threading
import time
import json
import os
import base64
from typing import Optional
from flask import Flask, jsonify, request, Response, send_file
from flask_cors import CORS
from mcp.server.fastmcp import FastMCP
import cv2
from djitellopy import Tello
import uvicorn

# Tello configuration
TELLO_IP = '192.168.10.1'
TELLO_CMD_PORT = 8889
TELLO_STATE_PORT = 8890
TELLO_VIDEO_PORT = 11111
LOCAL_CMD_PORT = 9000
LOCAL_STATE_PORT = 9001

# Global state
tello_state = {}
state_lock = threading.Lock()
cmd_socket = None
state_socket = None
tello = None
is_connected = False
is_streaming = False
frame_read = None
latest_frame = None
frame_lock = threading.Lock()

# Create Flask app
flask_app = Flask(__name__)
CORS(flask_app)

# Create FastMCP server with streamable HTTP support
mcp = FastMCP(
    "tello-proxy",
    dependencies=["flask", "flask-cors", "djitellopy", "opencv-python"],
    stateless_http=True,  # Enable stateless HTTP mode
    json_response=True    # Use JSON responses
)

def init_sockets():
    """Initialize UDP sockets for Tello communication"""
    global cmd_socket, state_socket

    # Command socket (bidirectional)
    cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    cmd_socket.bind(('', LOCAL_CMD_PORT))
    cmd_socket.settimeout(0.5)

    # State socket (receive only)
    state_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    state_socket.bind(('', LOCAL_STATE_PORT))
    state_socket.settimeout(0.5)

    print(f"✅ Sockets initialized")

def state_receiver_thread():
    """Background thread to continuously receive Tello state updates"""
    global tello_state

    print("📡 State receiver thread started")

    while True:
        try:
            data, _ = state_socket.recvfrom(1024)
            state_str = data.decode('utf-8').strip()

            # Parse state string
            state_dict = {}
            for item in state_str.split(';'):
                if ':' in item:
                    key, value = item.split(':', 1)
                    state_dict[key.strip()] = value.strip()

            with state_lock:
                tello_state = state_dict
                tello_state['last_update'] = time.time()

        except socket.timeout:
            continue
        except Exception as e:
            print(f"State receiver error: {e}")
            time.sleep(1)

def video_frame_thread():
    """Background thread to continuously read video frames"""
    global latest_frame, frame_read, is_streaming

    print("📹 Video frame thread started")

    while True:
        try:
            if is_streaming and frame_read is not None:
                frame = frame_read.frame
                if frame is not None and frame.size > 0:
                    # Only update if we got a valid frame
                    with frame_lock:
                        latest_frame = frame.copy()
                # Small delay to prevent excessive CPU usage
                time.sleep(0.033)  # ~30fps
            else:
                time.sleep(0.1)
        except Exception as e:
            print(f"Video frame error: {e}")
            time.sleep(1)

def send_tello_command(command: str) -> tuple[bool, str]:
    """Send a command to Tello and get response"""
    try:
        print(f"📤 Sending: {command}")
        cmd_socket.sendto(command.encode('utf-8'), (TELLO_IP, TELLO_CMD_PORT))

        try:
            response, _ = cmd_socket.recvfrom(1024)
            response_str = response.decode('utf-8').strip()
            print(f"📥 Response: {response_str}")
            return True, response_str
        except socket.timeout:
            print(f"⏱️  Timeout")
            return False, "Tello did not respond (timeout)"

    except Exception as e:
        print(f"❌ Error: {e}")
        return False, str(e)

# ============================================================================
# Business Logic Functions (shared by REST API and MCP)
# ============================================================================

def connect_tello() -> tuple[bool, str, Optional[int]]:
    """Connect to Tello (business logic). Returns (success, message, battery)"""
    global is_connected, tello

    if is_connected and tello is not None:
        try:
            battery = tello.get_battery()
            return True, 'Already connected', battery
        except:
            pass

    try:
        print("Connecting to Tello...")
        tello = Tello()
        tello.connect()

        try:
            tello.set_video_resolution(tello.RESOLUTION_720P)
            time.sleep(0.3)
        except:
            pass

        is_connected = True
        battery = tello.get_battery()
        print(f"✅ Connected! Battery: {battery}%")

        return True, 'Connected to Tello', battery
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False, str(e), None

def get_battery_level() -> tuple[bool, Optional[int], Optional[str]]:
    """Get battery level. Returns (success, battery, error)"""
    global tello, is_connected

    if not is_connected or tello is None:
        return False, None, 'Not connected'

    try:
        battery = tello.get_battery()
        return True, battery, None
    except Exception as e:
        return False, None, str(e)

def start_video_stream() -> tuple[bool, str]:
    """Start video streaming. Returns (success, message)"""
    global tello, is_connected, is_streaming, frame_read, latest_frame

    if not is_connected or tello is None:
        return False, 'Not connected'

    if is_streaming:
        return True, 'Already streaming'

    try:
        print("Starting video stream...")

        # Clear any stale frames
        with frame_lock:
            latest_frame = None

        # Set video quality
        tello.set_video_resolution(tello.RESOLUTION_720P)
        tello.set_video_bitrate(tello.BITRATE_5MBPS)
        tello.set_video_fps(tello.FPS_30)

        tello.streamon()
        time.sleep(2)

        frame_read = tello.get_frame_read()
        time.sleep(1)

        # Wait for first valid frame to ensure stream is ready
        print("Waiting for first frame...")
        for i in range(30):  # Wait up to 3 seconds for first frame
            if frame_read is not None:
                frame = frame_read.frame
                if frame is not None and frame.size > 0:
                    with frame_lock:
                        latest_frame = frame.copy()
                    print("✅ First frame received")
                    break
            time.sleep(0.1)

        is_streaming = True
        print("✅ Video stream started")

        return True, 'Video stream started'
    except Exception as e:
        print(f"❌ Stream start failed: {e}")
        return False, str(e)

def stop_video_stream() -> tuple[bool, str]:
    """Stop video streaming. Returns (success, message)"""
    global tello, is_streaming, frame_read

    if not is_streaming:
        return True, 'Stream not active'

    try:
        if tello:
            tello.streamoff()
        if frame_read:
            frame_read.stop()
            frame_read = None
        is_streaming = False

        return True, 'Video stream stopped'
    except Exception as e:
        return False, str(e)

def takeoff_tello() -> tuple[bool, str]:
    """Take off and hover. Returns (success, message)"""
    global tello, is_connected

    if not is_connected or tello is None:
        return False, 'Not connected'

    try:
        tello.takeoff()
        return True, 'Drone has taken off and is hovering'
    except Exception as e:
        return False, str(e)

def land_tello() -> tuple[bool, str]:
    """Land the drone. Returns (success, message)"""
    global tello, is_connected

    if not is_connected or tello is None:
        return False, 'Not connected'

    try:
        tello.land()
        return True, 'Drone has landed safely'
    except Exception as e:
        return False, str(e)

def move_tello(direction: str, distance: int = 20) -> tuple[bool, str]:
    """Move the drone in a direction. Returns (success, message)"""
    global tello, is_connected

    if not is_connected or tello is None:
        return False, 'Not connected'

    try:
        direction_lower = direction.lower()
        if direction_lower == 'up':
            tello.move_up(distance)
            return True, f'Moved up {distance}cm'
        elif direction_lower == 'down':
            tello.move_down(distance)
            return True, f'Moved down {distance}cm'
        elif direction_lower == 'forward':
            tello.move_forward(distance)
            return True, f'Moved forward {distance}cm'
        elif direction_lower == 'back':
            tello.move_back(distance)
            return True, f'Moved back {distance}cm'
        elif direction_lower == 'left':
            tello.move_left(distance)
            return True, f'Moved left {distance}cm'
        elif direction_lower == 'right':
            tello.move_right(distance)
            return True, f'Moved right {distance}cm'
        else:
            return False, f'Invalid direction: {direction}'
    except Exception as e:
        return False, str(e)

def rotate_tello(direction: str, angle: int = 15) -> tuple[bool, str]:
    """Rotate the drone. Returns (success, message)"""
    global tello, is_connected

    if not is_connected or tello is None:
        return False, 'Not connected'

    try:
        direction_lower = direction.lower()
        if direction_lower == 'left' or direction_lower == 'counterclockwise' or direction_lower == 'ccw':
            tello.rotate_counter_clockwise(angle)
            return True, f'Rotated left {angle}°'
        elif direction_lower == 'right' or direction_lower == 'clockwise' or direction_lower == 'cw':
            tello.rotate_clockwise(angle)
            return True, f'Rotated right {angle}°'
        else:
            return False, f'Invalid direction: {direction}'
    except Exception as e:
        return False, str(e)

def disconnect_tello() -> tuple[bool, str]:
    """Disconnect from Tello. Returns (success, message)"""
    global tello, is_connected, is_streaming, frame_read

    if not is_connected or tello is None:
        return True, 'Not connected'

    try:
        # Stop video streaming if active
        if is_streaming:
            try:
                tello.streamoff()
                if frame_read:
                    frame_read.stop()
                    frame_read = None
                is_streaming = False
            except:
                pass

        # Disconnect from Tello
        try:
            tello.end()
        except:
            pass  # Some Tello instances don't have end() method

        # Clean up global state
        tello = None
        is_connected = False

        return True, 'Disconnected successfully'
    except Exception as e:
        # Even if there's an error, clean up state
        tello = None
        is_connected = False
        is_streaming = False
        frame_read = None
        return False, str(e)

def get_tello_status() -> dict:
    """Get Tello status. Returns status dict"""
    global tello, is_connected, is_streaming, tello_state

    status = {
        'battery': 'N/A',
        'wifi': 'N/A',
        'temperature': 'N/A',
        'height': 'N/A',
        'tof': 'N/A'
    }

    if is_connected and tello is not None:
        try:
            status['battery'] = str(tello.get_battery())
            status['wifi'] = 'Connected'
            status['temperature'] = str(tello.get_temperature())
            status['height'] = str(tello.get_height())
        except:
            pass

    # Add state data if available
    with state_lock:
        if tello_state:
            for key in ['battery', 'temp', 'h', 'tof']:
                if key in tello_state:
                    if key == 'temp':
                        status['temperature'] = tello_state[key]
                    elif key == 'h':
                        status['height'] = tello_state[key]
                    elif key == 'tof':
                        status['tof'] = tello_state[key]
                    else:
                        status[key] = tello_state[key]

    return status

def capture_photo_to_file(filename: str) -> tuple[bool, str]:
    """Capture a photo and save to file. Returns (success, message)"""
    global latest_frame, is_streaming
    import os

    if not is_streaming:
        return False, 'Video stream not active. Start stream first.'

    with frame_lock:
        if latest_frame is None:
            return False, 'No frame available'

        frame = latest_frame.copy()

    try:
        # Create photos directory if it doesn't exist
        photos_dir = 'photos'
        os.makedirs(photos_dir, exist_ok=True)

        # Save frame to file
        filepath = os.path.join(photos_dir, filename)
        cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, 100])

        return True, f'Photo saved as {filename}'
    except Exception as e:
        return False, str(e)

# ============================================================================
# REST API Endpoints
# ============================================================================

@flask_app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    with state_lock:
        has_state = bool(tello_state)
        last_update = tello_state.get('last_update', 0)
        age = time.time() - last_update if last_update else None

    return jsonify({
        'status': 'healthy',
        'connected': is_connected,
        'streaming': is_streaming,
        'receiving_state': has_state and (age is None or age < 5),
        'last_state_update': age
    })

# ============================================================================
# Frontend API Endpoints (matching frontend expectations)
# ============================================================================

@flask_app.route('/api/takeoff', methods=['POST'])
def api_takeoff():
    """Take off endpoint for frontend"""
    success, message = takeoff_tello()
    
    if success:
        return jsonify({
            'success': True,
            'message': message
        })
    else:
        return jsonify({
            'success': False,
            'error': message
        }), 500

@flask_app.route('/api/land', methods=['POST'])
def api_land():
    """Land endpoint for frontend"""
    success, message = land_tello()
    
    if success:
        return jsonify({
            'success': True,
            'message': message
        })
    else:
        return jsonify({
            'success': False,
            'error': message
        }), 500

@flask_app.route('/api/move', methods=['POST'])
def api_move():
    """Move endpoint for frontend"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Missing request body'}), 400
    
    direction = data.get('direction', 'up')
    distance = data.get('distance', 20)
    
    success, message = move_tello(direction, distance)
    
    if success:
        return jsonify({
            'success': True,
            'message': message
        })
    else:
        return jsonify({
            'success': False,
            'error': message
        }), 500

@flask_app.route('/api/rotate', methods=['POST'])
def api_rotate():
    """Rotate endpoint for frontend"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Missing request body'}), 400
    
    direction = data.get('direction', 'left')
    angle = data.get('angle', 15)
    
    success, message = rotate_tello(direction, angle)
    
    if success:
        return jsonify({
            'success': True,
            'message': message
        })
    else:
        return jsonify({
            'success': False,
            'error': message
        }), 500

# ============================================================================
# Frontend API Endpoints (matching frontend expectations)
# ============================================================================

@flask_app.route('/api/connect', methods=['POST'])
def api_connect():
    """Connect endpoint for frontend"""
    data = request.get_json() or {}
    source = data.get('source', 'tello')
    
    # Only support tello for now (webcam would need different implementation)
    if source != 'tello':
        return jsonify({
            'success': False,
            'error': f'Source {source} not supported. Only "tello" is supported.'
        }), 400
    
    success, message, battery = connect_tello()
    
    if success:
        return jsonify({
            'success': True,
            'source': 'tello',
            'battery': battery,
            'message': message
        })
    else:
        return jsonify({
            'success': False,
            'error': message
        }), 500

@flask_app.route('/api/status', methods=['GET'])
def api_status():
    """Status endpoint for frontend"""
    status = get_tello_status()
    
    return jsonify({
        'success': True,
        'status': status
    })

@flask_app.route('/api/start-stream', methods=['POST'])
def api_start_stream():
    """Start stream endpoint for frontend"""
    success, message = start_video_stream()
    
    if success:
        return jsonify({
            'success': True,
            'message': message
        })
    else:
        return jsonify({
            'success': False,
            'error': message
        }), 500

@flask_app.route('/api/stop-stream', methods=['POST'])
def api_stop_stream():
    """Stop stream endpoint for frontend"""
    success, message = stop_video_stream()
    
    if success:
        return jsonify({
            'success': True,
            'message': message
        })
    else:
        return jsonify({
            'success': False,
            'error': message
        }), 500

@flask_app.route('/api/video-feed')
def api_video_feed():
    """Video feed endpoint for frontend (MJPEG stream)"""
    def generate():
        last_frame_time = 0
        frame_interval = 0.033  # ~30fps
        
        while True:
            if not is_streaming:
                time.sleep(0.1)
                continue

            # Wait for a valid frame
            frame = None
            with frame_lock:
                if latest_frame is not None and latest_frame.size > 0:
                    frame = latest_frame.copy()
            
            if frame is None:
                # No frame available yet, wait a bit
                time.sleep(0.033)
                continue

            # Throttle frame rate to ~30fps
            current_time = time.time()
            elapsed = current_time - last_frame_time
            if elapsed < frame_interval:
                time.sleep(frame_interval - elapsed)
            
            # Encode frame as JPEG
            try:
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                if buffer is not None and len(buffer) > 0:
                    frame_bytes = buffer.tobytes()
                    last_frame_time = time.time()
                    
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                else:
                    time.sleep(0.033)
            except Exception as e:
                print(f"Error encoding frame: {e}")
                time.sleep(0.033)

    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@flask_app.route('/api/disconnect', methods=['POST'])
def api_disconnect():
    """Disconnect endpoint for frontend"""
    success, message = disconnect_tello()
    
    if success:
        return jsonify({
            'success': True,
            'message': message
        })
    else:
        return jsonify({
            'success': False,
            'error': message
        }), 500

@flask_app.route('/api/capture', methods=['POST'])
def api_capture():
    """Capture photo endpoint for frontend"""
    data = request.get_json()
    if not data or 'filename' not in data:
        return jsonify({'success': False, 'error': 'Missing filename'}), 400
    
    filename = data['filename']
    success, message = capture_photo_to_file(filename)
    
    if success:
        return jsonify({
            'success': True,
            'message': message
        })
    else:
        return jsonify({
            'success': False,
            'error': message
        }), 500

@flask_app.route('/api/photo/<filename>', methods=['GET'])
def api_photo(filename):
    """Get photo file endpoint for frontend"""
    filepath = os.path.join('photos', filename)
    
    if not os.path.exists(filepath):
        return jsonify({
            'success': False,
            'error': 'Photo not found'
        }), 404
    
    return send_file(filepath, mimetype='image/jpeg')

@flask_app.route('/api/command', methods=['POST'])
def api_command():
    """Command endpoint for backward compatibility with proxy adapter"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Missing request body'}), 400
    
    command = data.get('command', '')
    if not command:
        return jsonify({'success': False, 'error': 'Missing command'}), 400
    
    # Check if connected
    if not is_connected or tello is None:
        return jsonify({
            'success': False,
            'error': 'Not connected. Call /api/connect first.'
        }), 400
    
    try:
        response = tello.send_control_command(command)
        return jsonify({
            'success': True,
            'response': response
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# MCP Tools
# ============================================================================

@mcp.tool()
def connect() -> str:
    """Connect to the Tello drone via proxy"""
    success, message, battery = connect_tello()
    
    if success:
        return f"✅ {message}. Battery: {battery}%"
    else:
        return f"❌ Connection failed: {message}"

@mcp.tool()
def disconnect() -> str:
    """Disconnect from Tello"""
    global tello, is_connected, is_streaming, frame_read

    if is_streaming:
        try:
            tello.streamoff()
            if frame_read:
                frame_read.stop()
                frame_read = None
            is_streaming = False
        except:
            pass

    tello = None
    is_connected = False
    return "✅ Disconnected"

@mcp.tool()
def get_battery() -> str:
    """Get battery level"""
    success, battery, error = get_battery_level()
    
    if success:
        return f"🔋 Battery: {battery}%"
    else:
        return f"❌ {error}"

@mcp.tool()
def start_video() -> str:
    """Start video streaming"""
    success, message = start_video_stream()
    
    if success:
        return f"✅ {message}. Access at: /tello/video_feed"
    else:
        return f"❌ {message}"

@mcp.tool()
def stop_video() -> str:
    """Stop video streaming"""
    success, message = stop_video_stream()
    
    if success:
        return f"✅ {message}"
    else:
        return f"❌ {message}"

# ============================================================================
# Main
# ============================================================================

def main():
    print("🚁 Tello Proxy Service with MCP + Video Support")
    print("=" * 60)

    # Check Tello connectivity
    import subprocess
    result = subprocess.run(['ping', '-c', '1', '-W', '2', TELLO_IP],
                          capture_output=True)
    if result.returncode == 0:
        print(f"✅ Tello reachable at {TELLO_IP}")
    else:
        print(f"⚠️  Warning: Cannot ping Tello at {TELLO_IP}")
        print("   Make sure you're connected to Tello WiFi!")

    # Initialize sockets
    init_sockets()

    # Start state receiver thread
    state_thread = threading.Thread(target=state_receiver_thread, daemon=True)
    state_thread.start()

    # Start video frame thread
    video_thread = threading.Thread(target=video_frame_thread, daemon=True)
    video_thread.start()

    print("=" * 60)
    print("🌐 REST API: http://0.0.0.0:50000")
    print("")
    print("📋 REST Endpoints:")
    print("   POST /api/connect")
    print("   POST /api/start_stream")
    print("   GET  /api/video_feed       ← Video stream (MJPEG)")
    print("   POST /api/capture_photo")
    print("   POST /api/stop_stream")
    print("")
    print("🔧 MCP Server (Streamable HTTP): http://0.0.0.0:50001/mcp")
    print("=" * 60)

    # Run Flask in a separate thread
    flask_thread = threading.Thread(
        target=lambda: flask_app.run(host="0.0.0.0", port=50000, debug=False, threaded=True),
        daemon=True
    )
    flask_thread.start()

    print("✅ Flask REST API started on port 50000")
    print("✅ Starting MCP server (Streamable HTTP) on port 50001...")
    print("   MCP endpoint: http://localhost:50001/mcp")

    # Run MCP server with streamable HTTP using uvicorn
    app = mcp.streamable_http_app()
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=50001,
        log_level="info"
    )

if __name__ == '__main__':
    main()
