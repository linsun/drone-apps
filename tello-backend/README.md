# Tello Python Backend Setup

This is a **much more reliable** approach using the DJITelloPy SDK, which is specifically designed for Tello drones.

## Why This is Better

✅ **Built-in video streaming** - No ffmpeg fighting  
✅ **Automatic frame handling** - SDK manages the H.264 decoding  
✅ **Reliable connection** - Tested with thousands of Tello drones  
✅ **Simpler code** - Less than half the complexity  
✅ **Better error handling** - SDK handles quirks and edge cases  

## Prerequisites

- Python 3.7 or higher
- pip (Python package manager)
- Tello drone
- Connected to Tello WiFi

## Installation

### Step 1: Create Python Backend Directory

```bash
# If you want to keep Node.js version, create alongside it
mkdir tello-python-backend
cd tello-python-backend
```

### Step 2: Create requirements.txt

Create a file named `requirements.txt`:

```
djitellopy==2.5.0
flask==3.0.0
flask-cors==4.0.0
flask-sock==0.7.0
opencv-python==4.8.1.78
```

### Step 3: Install Dependencies

```bash
# Create virtual environment (recommended)
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

### Step 4: Create server.py

Copy the entire Python code from the "Tello Python Backend (server.py)" artifact into a file named `server.py`.

### Step 5: Create Directories

```bash
mkdir photos
mkdir videos
```

## Running the Server

```bash
# Make sure virtual environment is activated
source venv/bin/activate  # macOS/Linux
# or
# venv\Scripts\activate  # Windows

# Run the server
python server.py
```

You should see:
```
Tello Python Backend Server
Make sure you are connected to the Tello WiFi network
Starting server on http://localhost:3001
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:3001
```

## Using with Your React App

**Good news:** Your React app doesn't need ANY changes! It will work exactly the same because the API endpoints are identical:

- `POST /api/connect`
- `GET /api/status`
- `POST /api/start-stream`
- `POST /api/stop-stream`
- `POST /api/capture`
- `GET /api/photo/:filename`
- `WS /video`

## Testing

1. **Start Python backend:**
   ```bash
   python server.py
   ```

2. **Keep React frontend running:**
   ```bash
   # In tello-frontend directory
   npm start
   ```

3. **Open React app:** http://localhost:3000

4. **Test the flow:**
   - Click "Connect to Drone"
   - Click "Start Camera" → Should see smooth video!
   - Click "Capture Photo 1"
   - Click "Capture Photo 2"
   - Click "Compare with AI"

## Advantages Over Node.js Version

| Feature | Node.js + FFmpeg | Python + DJITelloPy |
|---------|------------------|---------------------|
| Setup complexity | High | Low |
| Video reliability | Inconsistent | Very reliable |
| Frame processing | Manual | Automatic |
| Error handling | Manual | Built-in |
| Dependencies | FFmpeg, WebSocket, etc. | Just Python packages |
| Code lines | ~250 | ~180 |

## Troubleshooting

### Issue: "No module named 'djitellopy'"
**Solution:**
```bash
pip install djitellopy
```

### Issue: "No module named 'cv2'"
**Solution:**
```bash
pip install opencv-python
```

### Issue: Port 3001 already in use
**Solution:**
```bash
# Kill the Node.js server if it's still running
# On macOS/Linux:
lsof -ti:3001 | xargs kill -9

# On Windows:
# netstat -ano | findstr :3001
# taskkill /PID <PID> /F
```

### Issue: Video still not smooth
**Solutions:**
- Make sure you're close to the drone (within 10 feet)
- Ensure no other apps are using Tello video
- Try restarting the drone
- Check WiFi signal strength

## File Structure

```
tello-python-backend/
├── venv/                 # Virtual environment (created)
├── photos/              # Captured photos
├── videos/              # Recorded videos (future)
├── server.py            # Main server code
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Next Steps

Once the Python backend is working smoothly, you can:

1. ✅ Keep using your existing React frontend
2. ✅ Add video recording (much easier with Python!)
3. ✅ Add drone control (takeoff, land, move)
4. ✅ Add advanced features like face detection
5. ❌ Delete the Node.js backend if you want

## Video Recording (Bonus)

To add video recording with Python, it's super easy:

```python
# Add to server.py
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
video_writer = cv2.VideoWriter('video.mp4', fourcc, 30, (960, 720))

# In video_stream_worker, add:
if recording:
    video_writer.write(frame)
```

Much simpler than the Node.js version!

## Resources

- DJITelloPy Docs: https://github.com/damiafuentes/DJITelloPy
- OpenCV Tutorial: https://docs.opencv.org/
- Flask Documentation: https://flask.palletsprojects.com/

Happy flying! 🚁

