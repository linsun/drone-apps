#!/usr/bin/env python3
"""
Tello Backend HTTP API Server - Runs in Kubernetes

This Flask server runs in K8s and provides REST API endpoints that communicate
with the Tello Proxy Service on the Mac.

Architecture:
    Frontend (K8s) → This Server (K8s) → Tello Proxy (Mac) → Tello Drone

Usage:
    python3 backend_http_server.py

Accessible at:
    http://localhost:3001/api/*
"""

import os
import sys

# Ensure script directory is on path so "github_pr" can be imported when run from any cwd (e.g. Docker /app)
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from flask import Flask, jsonify, request
from flask_cors import CORS
from tello_proxy_adapter import create_tello

app = Flask(__name__)
# Allow large JSON payloads (base64 photos) for /api/github-pr
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB
CORS(app)


@app.after_request
def add_private_network_access(resp):
    """Allow browser requests from other origins to this server (e.g. localhost:3000 → localhost:3001)."""
    if resp.headers.get('Access-Control-Allow-Origin') is not None:
        resp.headers['Access-Control-Allow-Private-Network'] = 'true'
    return resp

# Global Tello instance (will be TelloProxyAdapter)
tello = None
connected = False

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get server and drone status"""
    global tello, connected

    proxy_url = os.getenv('TELLO_PROXY_URL', 'http://host.docker.internal:50000')

    if not connected or tello is None:
        return jsonify({
            'success': True,
            'connected': False,
            'proxy_url': proxy_url,
            'message': 'Not connected to Tello'
        })

    try:
        battery = tello.get_battery()
        temp = tello.get_temperature()
        height = tello.get_height()
        flight_time = tello.get_flight_time()

        return jsonify({
            'success': True,
            'connected': True,
            'proxy_url': proxy_url,
            'battery': battery,
            'temperature': temp,
            'height': height,
            'flight_time': flight_time
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/connect', methods=['POST'])
def connect():
    """Connect to Tello via proxy"""
    global tello, connected

    if connected and tello is not None:
        return jsonify({
            'success': True,
            'message': 'Already connected',
            'battery': tello.get_battery()
        })

    try:
        print("Connecting to Tello via proxy...")
        tello = create_tello()
        tello.connect()
        connected = True

        battery = tello.get_battery()
        print(f"✅ Connected! Battery: {battery}%")

        return jsonify({
            'success': True,
            'message': 'Connected to Tello via proxy',
            'battery': battery
        })
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/disconnect', methods=['POST'])
def disconnect():
    """Disconnect from Tello"""
    global tello, connected

    tello = None
    connected = False

    return jsonify({
        'success': True,
        'message': 'Disconnected'
    })

@app.route('/api/battery', methods=['GET'])
def get_battery():
    """Get battery level"""
    global tello, connected

    if not connected or tello is None:
        return jsonify({
            'success': False,
            'error': 'Not connected'
        }), 400

    try:
        battery = tello.get_battery()
        return jsonify({
            'success': True,
            'battery': battery
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/command', methods=['POST'])
def send_command():
    """Send a command to Tello"""
    global tello, connected

    if not connected or tello is None:
        return jsonify({
            'success': False,
            'error': 'Not connected'
        }), 400

    data = request.get_json() or {}
    command = data.get('command', '').strip()

    if not command:
        return jsonify({
            'success': False,
            'error': 'Missing command'
        }), 400

    try:
        response = tello.send_control_command(command)
        return jsonify({
            'success': True,
            'command': command,
            'response': response
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'command': command,
            'error': str(e)
        }), 500

@app.route('/api/takeoff', methods=['POST'])
def takeoff():
    """Take off"""
    global tello, connected

    if not connected or tello is None:
        return jsonify({'success': False, 'error': 'Not connected'}), 400

    try:
        tello.takeoff()
        return jsonify({'success': True, 'message': 'Taking off'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/land', methods=['POST'])
def land():
    """Land"""
    global tello, connected

    if not connected or tello is None:
        return jsonify({'success': False, 'error': 'Not connected'}), 400

    try:
        tello.land()
        return jsonify({'success': True, 'message': 'Landing'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/move', methods=['POST'])
def move():
    """Move in a direction"""
    global tello, connected

    if not connected or tello is None:
        return jsonify({'success': False, 'error': 'Not connected'}), 400

    data = request.get_json() or {}
    direction = data.get('direction', '').lower()
    distance = int(data.get('distance', 30))

    if distance < 20 or distance > 500:
        return jsonify({'success': False, 'error': 'Distance must be 20-500 cm'}), 400

    try:
        if direction == "forward":
            tello.move_forward(distance)
        elif direction == "back":
            tello.move_back(distance)
        elif direction == "left":
            tello.move_left(distance)
        elif direction == "right":
            tello.move_right(distance)
        elif direction == "up":
            tello.move_up(distance)
        elif direction == "down":
            tello.move_down(distance)
        else:
            return jsonify({'success': False, 'error': f'Invalid direction: {direction}'}), 400

        return jsonify({'success': True, 'message': f'Moved {direction} {distance} cm'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rotate', methods=['POST'])
def rotate():
    """Rotate"""
    global tello, connected

    if not connected or tello is None:
        return jsonify({'success': False, 'error': 'Not connected'}), 400

    data = request.get_json() or {}
    direction = data.get('direction', '').lower()
    angle = int(data.get('angle', 90))

    if angle < 1 or angle > 360:
        return jsonify({'success': False, 'error': 'Angle must be 1-360 degrees'}), 400

    try:
        if direction in ['cw', 'clockwise']:
            tello.rotate_clockwise(angle)
        elif direction in ['ccw', 'counterclockwise']:
            tello.rotate_counter_clockwise(angle)
        else:
            return jsonify({'success': False, 'error': f'Invalid direction: {direction}'}), 400

        return jsonify({'success': True, 'message': f'Rotated {direction} {angle}°'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/flip', methods=['POST'])
def flip():
    """Flip"""
    global tello, connected

    if not connected or tello is None:
        return jsonify({'success': False, 'error': 'Not connected'}), 400

    data = request.get_json() or {}
    direction = data.get('direction', '').lower()

    try:
        if direction in ['f', 'forward']:
            tello.flip_forward()
        elif direction in ['b', 'back']:
            tello.flip_back()
        elif direction in ['l', 'left']:
            tello.flip_left()
        elif direction in ['r', 'right']:
            tello.flip_right()
        else:
            return jsonify({'success': False, 'error': f'Invalid direction: {direction}'}), 400

        return jsonify({'success': True, 'message': f'Flipped {direction}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/start-stream', methods=['POST'])
def start_stream():
    """Start video stream (via proxy)"""
    proxy_url = os.getenv('TELLO_PROXY_URL', 'http://host.docker.internal:50000')

    try:
        import requests
        response = requests.post(f'{proxy_url}/api/start-stream', timeout=10)
        data = response.json()

        if data.get('success'):
            # Return proxy video URL
            return jsonify({
                'success': True,
                'message': 'Video stream started',
                'video_url': f'{proxy_url}/api/video-feed'
            })
        else:
            return jsonify({
                'success': False,
                'error': data.get('error', 'Unknown error')
            }), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stop-stream', methods=['POST'])
def stop_stream():
    """Stop video stream (via proxy)"""
    proxy_url = os.getenv('TELLO_PROXY_URL', 'http://host.docker.internal:50000')

    try:
        import requests
        response = requests.post(f'{proxy_url}/api/stop-stream', timeout=10)
        data = response.json()

        return jsonify(data)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/video-feed')
def video_feed_proxy():
    """Proxy video feed from Mac proxy"""
    proxy_url = os.getenv('TELLO_PROXY_URL', 'http://host.docker.internal:50000')

    import requests
    from flask import Response

    def generate():
        try:
            response = requests.get(f'{proxy_url}/api/video-feed', stream=True, timeout=30)
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    yield chunk
        except Exception as e:
            print(f"Video feed error: {e}")

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/capture', methods=['POST'])
def capture_photo():
    """Capture photo (via proxy)"""
    proxy_url = os.getenv('TELLO_PROXY_URL', 'http://host.docker.internal:50000')

    try:
        import requests
        response = requests.post(f'{proxy_url}/api/capture', timeout=10)
        data = response.json()

        return jsonify(data)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/compare-photos', methods=['POST'])
def compare_photos():
    """
    Run LLaVA and Qwen3-VL analysis on two photos in parallel via Ollama.

    Expects JSON: { "photo1Base64": "...", "photo2Base64": "..." }
    Returns JSON:  { "success": true, "llava": { "text": "...", "summary": "..." },
                     "qwen": { "text": "...", "summary": "..." } }
    """
    import re
    import requests
    from concurrent.futures import ThreadPoolExecutor, as_completed

    ollama_url = os.getenv('OLLAMA_URL', 'http://localhost:11434')

    data = request.get_json() or {}
    photo1_b64 = data.get('photo1Base64', '')
    photo2_b64 = data.get('photo2Base64', '')

    if not photo1_b64 or not photo2_b64:
        return jsonify({'success': False, 'error': 'Missing photo1Base64 or photo2Base64'}), 400

    compare_prompt = (
        'Now compare Photo 1 and Photo 2 for audience engagement. '
        'Analyze key differences in facial expression, gesture, composition, lighting, positioning. '
        'Which photo is more engaging? Respond in less than 50 words, then provide a 10-word summary '
        'at the end in a new paragraph.'
    )

    def _build_messages(model_name):
        """Build model-specific message lists.

        LLaVA doesn't reliably distinguish image ordering when both images are
        in a single message, so we use multi-turn messages to label each image
        explicitly.  Qwen3-VL handles multi-image ordering correctly with both
        images in one message."""
        if model_name == 'llava':
            return [
                {'role': 'user', 'content': 'This is Photo 1.', 'images': [photo1_b64]},
                {'role': 'assistant', 'content': 'Got it, I see Photo 1.'},
                {'role': 'user', 'content': 'This is Photo 2.', 'images': [photo2_b64]},
                {'role': 'assistant', 'content': 'Got it, I see Photo 2.'},
                {'role': 'user', 'content': compare_prompt},
            ]
        else:
            return [
                {
                    'role': 'user',
                    'content': (
                        'I am providing two images. The first image is Photo 1 and '
                        'the second image is Photo 2. ' + compare_prompt
                    ),
                    'images': [photo1_b64, photo2_b64],
                },
            ]

    def _extract_summary(text):
        match = re.search(r'[Ss]ummary:\s*(.+?)(?:\.|$)', text)
        if match:
            words = match.group(1).strip().split()
            return ' '.join(words[:10])
        sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
        if sentences:
            words = sentences[-1].split()
            return ' '.join(words[:10])
        words = text.split()
        if len(words) >= 10:
            start = (len(words) - 10) // 2
            return ' '.join(words[start:start + 10])
        return ' '.join(words[:10])

    def _call_model(model_name):
        try:
            resp = requests.post(
                f'{ollama_url}/api/chat',
                json={
                    'model': model_name,
                    'messages': _build_messages(model_name),
                    'stream': False,
                },
                timeout=300,
            )
            if resp.ok:
                body = resp.json()
                text = body.get('message', {}).get('content') or body.get('response') or body.get('content', '')
                return {'text': text, 'summary': _extract_summary(text)}
            else:
                err = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {}
                msg = f'Error {resp.status_code}: {err.get("error", resp.reason)}'
                if resp.status_code == 404:
                    msg += f'. Model "{model_name}" may not be installed. Run: ollama pull {model_name}'
                return {'text': msg, 'summary': '', 'error': True}
        except Exception as e:
            return {'text': f'{model_name} error: {e}', 'summary': '', 'error': True}

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            pool.submit(_call_model, 'llava'): 'llava',
            pool.submit(_call_model, 'qwen3-vl'): 'qwen',
        }
        results = {}
        for future in as_completed(futures):
            key = futures[future]
            results[key] = future.result()

    return jsonify({
        'success': True,
        'llava': results.get('llava', {'text': '', 'summary': ''}),
        'qwen': results.get('qwen', {'text': '', 'summary': ''}),
    })


@app.route('/api/github-pr', methods=['POST'])
def github_pr():
    """
    Create a PR in a GitHub repo with photo1, photo2, and LLaVA/Qwen3-VL analysis.
    Uses GitHub MCP for branch + markdown; GitHub API for images and PR.
    """
    try:
        from github_pr import create_pr_payload
    except ImportError:
        return jsonify({'success': False, 'error': 'github_pr module not available'}), 500

    data = request.get_json() or {}
    repo = data.get('repo', '').strip()
    photo1_base64 = data.get('photo1Base64', '')
    photo2_base64 = data.get('photo2Base64', '')
    comparison_llava = data.get('comparisonLlava', '')
    comparison_qwen = data.get('comparisonQwen', '')

    if not repo:
        return jsonify({'success': False, 'error': 'Missing repo'}), 400
    if not photo1_base64 or not photo2_base64:
        return jsonify({'success': False, 'error': 'Missing photo1Base64 or photo2Base64'}), 400

    result = create_pr_payload(
        repo_slug=repo,
        photo1_base64=photo1_base64,
        photo2_base64=photo2_base64,
        comparison_llava=comparison_llava,
        comparison_qwen=comparison_qwen,
    )

    if result['success']:
        return jsonify({'success': True, 'prUrl': result['prUrl']})
    return jsonify({'success': False, 'error': result.get('error', 'Unknown error')}), 500


if __name__ == '__main__':
    proxy_url = os.getenv('TELLO_PROXY_URL', 'http://host.docker.internal:50000')
    http_port = int(os.getenv('HTTP_PORT', '3001'))

    print("=" * 60)
    print("🚀 Tello Backend HTTP Server Starting...")
    print("=" * 60)
    print(f"📡 Proxy URL: {proxy_url}")
    print(f"🌐 HTTP API: http://0.0.0.0:{http_port}/api/*")
    print("")
    print("Architecture:")
    print("  Frontend (K8s) → This Server (K8s) → Proxy (Mac) → Tello")
    print("")
    print("Available API Endpoints:")
    print("  GET  /api/status")
    print("  POST /api/connect")
    print("  POST /api/disconnect")
    print("  GET  /api/battery")
    print("  POST /api/command")
    print("  POST /api/takeoff")
    print("  POST /api/land")
    print("  POST /api/move")
    print("  POST /api/rotate")
    print("  POST /api/flip")
    print("  POST /api/start-stream       ← Start video")
    print("  POST /api/stop-stream        ← Stop video")
    print("  GET  /api/video-feed         ← Video stream (MJPEG)")
    print("  POST /api/capture            ← Take photo")
    print("  POST /api/compare-photos     ← AI comparison (LLaVA + Qwen3-VL via Ollama)")
    print("  POST /api/github-pr          ← Create PR (photos + LLaVA/Qwen analysis)")
    print("=" * 60)

    app.run(host='0.0.0.0', port=http_port, debug=False)
