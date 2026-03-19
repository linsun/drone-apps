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


def _resize_base64_image(b64_data, max_dim=512, quality=85):
    """Downscale a base64-encoded JPEG/PNG so the longest side is at most *max_dim* pixels.

    Returns a base64-encoded JPEG string (no data-URI prefix).  If the image is
    already small enough, it is re-encoded at the target quality to keep payload
    size down.
    """
    import base64
    import io
    from PIL import Image

    raw = base64.b64decode(b64_data)
    img = Image.open(io.BytesIO(raw))

    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')

    w, h = img.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=quality)
    return base64.b64encode(buf.getvalue()).decode('ascii')


def _label_base64_image(b64_data, label):
    """Burn a bold text label (e.g. 'PHOTO 1') into the top-left corner of the image.

    This gives the VLM a visual anchor so it cannot confuse which image is which.
    Returns a base64-encoded JPEG string.
    """
    import base64
    import io
    from PIL import Image, ImageDraw, ImageFont

    raw = base64.b64decode(b64_data)
    img = Image.open(io.BytesIO(raw))
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')

    draw = ImageDraw.Draw(img)
    w, _ = img.size
    font_size = max(20, w // 12)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except (OSError, IOError):
        try:
            font = ImageFont.truetype("Arial Bold.ttf", font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), label, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = 8
    draw.rectangle([0, 0, text_w + pad * 2, text_h + pad * 2], fill=(0, 0, 0))
    draw.text((pad, pad), label, fill=(255, 255, 255), font=font)

    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=90)
    return base64.b64encode(buf.getvalue()).decode('ascii')


_VISION_MODEL = os.getenv('VISION_MODEL', 'qwen3-vl:4b')

_COMPARE_PROMPT = (
    'I am sending you two photos. The first image is Photo 1 and the second image is Photo 2. '
    'Compare them for audience engagement. '
    'You MUST respond with EXACTLY this format:\n'
    'Photo 1 score: <number from 1 to 10>\n'
    'Photo 1 expression: <one sentence about facial expression and emotion>\n'
    'Photo 1 energy: <one sentence about how dynamic or attention-grabbing it feels>\n'
    'Photo 2 score: <number from 1 to 10>\n'
    'Photo 2 expression: <one sentence about facial expression and emotion>\n'
    'Photo 2 energy: <one sentence about how dynamic or attention-grabbing it feels>'
)


def _call_vision_model(req_lib, ollama_url, messages):
    """Make a single Ollama chat call and return (text, error_msg)."""
    resp = req_lib.post(
        f'{ollama_url}/api/chat',
        json={
            'model': _VISION_MODEL,
            'messages': messages,
            'stream': False,
            'keep_alive': '30m',
            'options': {
                'temperature': 0,
            },
        },
        timeout=300,
    )
    if resp.ok:
        import re as _re
        body = resp.json()
        text = (body.get('message', {}).get('content')
                or body.get('response')
                or body.get('content', ''))
        text = _re.sub(r'<think>.*?</think>\s*', '', text, flags=_re.DOTALL)
        return text.strip(), None
    err = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {}
    msg = f'Error {resp.status_code}: {err.get("error", resp.reason)}'
    if resp.status_code == 404:
        msg += f'. Model "{_VISION_MODEL}" may not be installed. Run: ollama pull {_VISION_MODEL}'
    return None, msg


def _parse_comparison(text):
    """Parse the structured comparison response from the vision model."""
    import re
    result = {}

    match = re.search(r'Photo 1 score:\s*(\d+(?:\.\d+)?)', text)
    if match:
        result['score1'] = float(match.group(1))
    match = re.search(r'Photo 2 score:\s*(\d+(?:\.\d+)?)', text)
    if match:
        result['score2'] = float(match.group(1))

    for key in ('expression', 'energy'):
        match = re.search(rf'Photo 1 {key}:\s*(.+)', text, re.IGNORECASE)
        if match:
            result[f'photo1_{key}'] = match.group(1).strip()
        match = re.search(rf'Photo 2 {key}:\s*(.+)', text, re.IGNORECASE)
        if match:
            result[f'photo2_{key}'] = match.group(1).strip()

    return result


def _build_display_text(parsed):
    """Build the user-facing analysis text from parsed comparison data."""
    lines = []
    score1 = parsed.get('score1')
    score2 = parsed.get('score2')

    if score1 is not None:
        lines.append(f'Photo 1 score: {score1}/10')
    for key in ('expression', 'energy'):
        val = parsed.get(f'photo1_{key}')
        if val:
            lines.append(f'Photo 1 {key}: {val}')

    lines.append('')

    if score2 is not None:
        lines.append(f'Photo 2 score: {score2}/10')
    for key in ('expression', 'energy'):
        val = parsed.get(f'photo2_{key}')
        if val:
            lines.append(f'Photo 2 {key}: {val}')

    return '\n'.join(lines)


def _extract_summary(text):
    import re
    match = re.search(r'[Ss]ummary:\s*(.+)', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
    if sentences:
        return sentences[-1]
    return text.strip()


@app.route('/api/compare-photos', methods=['POST'])
def compare_photos():
    """
    Compare two photos in a single vision model call.

    Uses chunked transfer encoding with periodic keepalive newlines to prevent
    ztunnel / Nginx / intermediate proxies from closing idle connections.

    Expects JSON: { "photo1Base64": "...", "photo2Base64": "..." }
    Returns JSON:  { "success": true, "text": "...", "summary": "..." }
    """
    import json as _json
    import threading
    import time
    import requests as req_lib
    from flask import Response, stream_with_context

    ollama_url = os.getenv('OLLAMA_URL', 'http://localhost:11434')

    data = request.get_json() or {}
    photo1_b64 = data.get('photo1Base64', '')
    photo2_b64 = data.get('photo2Base64', '')

    if not photo1_b64 or not photo2_b64:
        return jsonify({'success': False, 'error': 'Missing photo1Base64 or photo2Base64'}), 400

    result_holder = {}
    done = threading.Event()

    print(f"[compare] Starting analysis, photo1 size={len(photo1_b64)}, photo2 size={len(photo2_b64)}", flush=True)

    try:
        messages = [
            {
                'role': 'user',
                'content': _COMPARE_PROMPT,
                'images': [photo1_b64, photo2_b64],
            },
        ]

        text, err = _call_vision_model(req_lib, ollama_url, messages)
        print(f"[compare] Model returned, err={err}, text length={len(text) if text else 0}", flush=True)

        if err:
            print(f"[compare] Model error: {err}", flush=True)
            return jsonify({'success': False, 'text': err, 'summary': '', 'error': err}), 502

        print(f"[compare] Raw model output: {text[:500]}", flush=True)

        parsed = _parse_comparison(text)
        print(f"[compare] Parsed: {parsed}", flush=True)

        score1 = parsed.get('score1')
        score2 = parsed.get('score2')
        display = _build_display_text(parsed)

        if score1 is not None and score2 is not None:
            diff = abs(score1 - score2)
            if diff < 0.5:
                summary = 'The two photos are nearly equal in engagement with no clear winner.'
            else:
                w = 1 if score1 > score2 else 2
                reason = parsed.get(f'photo{w}_expression', '') or parsed.get(f'photo{w}_energy', '')
                reason = reason.rstrip('.').lower()
                summary = f'Photo {w} is more engaging because {reason}.' if reason else f'Photo {w} is more engaging overall.'
            final_text = f'{display}\n\nSummary: {summary}'
        else:
            final_text = display or text

        result_summary = _extract_summary(final_text)
        print(f"[compare] Final text length={len(final_text)}, summary={result_summary}", flush=True)

        return jsonify({
            'success': True,
            'text': final_text,
            'summary': result_summary,
        })
    except Exception as e:
        print(f"[compare] Exception: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'text': f'Vision model error: {e}', 'summary': '', 'error': str(e)}), 500


@app.route('/api/github-pr', methods=['POST'])
def github_pr():
    """
    Create a PR in a GitHub repo with photo1, photo2, and AI analysis.
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
    comparison_result = data.get('comparisonResult', '') or data.get('comparisonLlava', '')

    if not repo:
        return jsonify({'success': False, 'error': 'Missing repo'}), 400
    if not photo1_base64 or not photo2_base64:
        return jsonify({'success': False, 'error': 'Missing photo1Base64 or photo2Base64'}), 400

    result = create_pr_payload(
        repo_slug=repo,
        photo1_base64=photo1_base64,
        photo2_base64=photo2_base64,
        comparison_text=comparison_result,
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
    print("  POST /api/compare-photos     ← AI comparison (LLaVA via Ollama)")
    print("  POST /api/github-pr          ← Create PR (photos + LLaVA analysis)")
    print("=" * 60)

    app.run(host='0.0.0.0', port=http_port, debug=False)
