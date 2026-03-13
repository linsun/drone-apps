#!/usr/bin/env python3
"""
Tello Backend MCP Server - Runs in Kubernetes

This MCP server runs in K8s and communicates with the Tello Proxy Service
on the Mac. It provides MCP tools for AI assistants to control the Tello drone.

Architecture:
    MCP Client → This Server (K8s) → Tello Proxy (Mac) → Tello Drone

Usage:
    python3 backend_mcp_server.py

Accessible at:
    http://localhost:3002/mcp (MCP streamable HTTP endpoint)
"""

import os
from typing import Optional
from tello_proxy_adapter import create_tello
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
import time

# Global Tello instance (will be TelloProxyAdapter)
tello: Optional[object] = None
connected = False

# Create FastMCP server
mcp = FastMCP(
    "tello-backend",
    dependencies=["requests"],  # Only need requests for proxy calls
    stateless_http=True,  # Enable stateless HTTP mode
    json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        # Add your specific gateway or domain here
        allowed_hosts=["localhost:*", "127.0.0.1:*", "agw.mcp.svc.cluster.local:*", "tello-backend.mcp.svc.cluster.local:*", "backend.mcp.svc.cluster.local:*", "backend.default.svc.cluster.local:*"],
        allowed_origins=["http://localhost:*", "http://agw.mcp.svc.cluster.local:*"],
    )
)

def ensure_connected() -> tuple[bool, str]:
    """Ensure Tello is connected via proxy. Returns (success, message)"""
    global tello, connected

    if connected and tello is not None:
        return True, "Already connected"

    try:
        # Create Tello instance (uses TelloProxyAdapter by default)
        tello = create_tello()
        tello.connect()

        connected = True
        battery = tello.get_battery()
        return True, f"Connected successfully (via proxy). Battery: {battery}%"
    except Exception as e:
        return False, f"Connection failed: {str(e)}"

# ============================================================================
# MCP Tools
# ============================================================================

@mcp.tool()
def connect() -> str:
    """Connect to the Tello drone via proxy. Must be called before any other commands."""
    success, message = ensure_connected()
    return f"{'✅' if success else '❌'} {message}"

@mcp.tool()
def disconnect() -> str:
    """Disconnect from the Tello drone."""
    global tello, connected

    if not connected or tello is None:
        return "ℹ️ Not connected to Tello."

    tello = None
    connected = False
    return "✅ Disconnected from Tello."

@mcp.tool()
def get_battery() -> str:
    """Get the current battery level."""
    if not connected or tello is None:
        return "❌ Not connected. Call 'connect' first."

    try:
        battery = tello.get_battery()
        return f"🔋 Battery: {battery}%"
    except Exception as e:
        return f"❌ Failed to get battery: {str(e)}"

@mcp.tool()
def get_status() -> str:
    """Get comprehensive drone status including battery, temperature, height, and flight time."""
    if not connected or tello is None:
        return "❌ Not connected. Call 'connect' first."

    try:
        battery = tello.get_battery()
        temp = tello.get_temperature()
        height = tello.get_height()
        flight_time = tello.get_flight_time()

        return f"""📊 Tello Status (via proxy):
• Battery: {battery}%
• Temperature: {temp}°C
• Height: {height} cm
• Flight Time: {flight_time}s"""
    except Exception as e:
        return f"❌ Failed to get status: {str(e)}"

@mcp.tool()
def takeoff() -> str:
    """Take off and hover. The drone will rise to about 1 meter."""
    if not connected or tello is None:
        return "❌ Not connected. Call 'connect' first."

    try:
        tello.takeoff()
        return "✅ Taking off!"
    except Exception as e:
        return f"❌ Takeoff failed: {str(e)}"

@mcp.tool()
def land() -> str:
    """Land the drone."""
    if not connected or tello is None:
        return "❌ Not connected. Call 'connect' first."

    try:
        tello.land()
        return "✅ Landing!"
    except Exception as e:
        return f"❌ Land failed: {str(e)}"

@mcp.tool()
def move(direction: str, distance: int = 30) -> str:
    """
    Move the drone in a specified direction.

    Args:
        direction: Direction to move (forward, back, left, right, up, down)
        distance: Distance in cm (20-500)
    """
    if not connected or tello is None:
        return "❌ Not connected. Call 'connect' first."

    if distance < 20 or distance > 500:
        return "❌ Distance must be between 20 and 500 cm"

    direction = direction.lower()
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
            return f"❌ Invalid direction: {direction}. Use: forward, back, left, right, up, down"

        return f"✅ Moved {direction} {distance} cm"
    except Exception as e:
        return f"❌ Move {direction} failed: {str(e)}"

@mcp.tool()
def rotate(direction: str, angle: int = 90) -> str:
    """
    Rotate the drone.

    Args:
        direction: Rotation direction (cw for clockwise, ccw for counter-clockwise)
        angle: Rotation angle in degrees (1-360)
    """
    if not connected or tello is None:
        return "❌ Not connected. Call 'connect' first."

    if angle < 1 or angle > 360:
        return "❌ Angle must be between 1 and 360 degrees"

    direction = direction.lower()
    try:
        if direction == "cw" or direction == "clockwise":
            tello.rotate_clockwise(angle)
            return f"✅ Rotated clockwise {angle}°"
        elif direction == "ccw" or direction == "counterclockwise":
            tello.rotate_counter_clockwise(angle)
            return f"✅ Rotated counter-clockwise {angle}°"
        else:
            return f"❌ Invalid direction: {direction}. Use: cw, ccw"
    except Exception as e:
        return f"❌ Rotate failed: {str(e)}"

@mcp.tool()
def flip(direction: str) -> str:
    """
    Perform a flip.

    Args:
        direction: Flip direction (f=forward, b=back, l=left, r=right)
    """
    if not connected or tello is None:
        return "❌ Not connected. Call 'connect' first."

    direction = direction.lower()
    try:
        if direction in ["f", "forward"]:
            tello.flip_forward()
            return "✅ Flipped forward!"
        elif direction in ["b", "back"]:
            tello.flip_back()
            return "✅ Flipped back!"
        elif direction in ["l", "left"]:
            tello.flip_left()
            return "✅ Flipped left!"
        elif direction in ["r", "right"]:
            tello.flip_right()
            return "✅ Flipped right!"
        else:
            return f"❌ Invalid direction: {direction}. Use: f, b, l, r"
    except Exception as e:
        return f"❌ Flip failed: {str(e)}"

@mcp.tool()
def send_command(command: str) -> str:
    """
    Send a raw SDK command to the Tello drone.

    Args:
        command: Raw Tello SDK command (e.g., "battery?", "speed 50")
    """
    if not connected or tello is None:
        return "❌ Not connected. Call 'connect' first."

    try:
        response = tello.send_control_command(command)
        return f"✅ Command '{command}' → Response: {response}"
    except Exception as e:
        return f"❌ Command '{command}' failed: {str(e)}"

# ============================================================================
# Server Startup
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    proxy_url = os.getenv('TELLO_PROXY_URL', 'http://host.docker.internal:50000')

    print("=" * 60)
    print("🚀 Tello Backend MCP Server Starting...")
    print("=" * 60)
    print(f"📡 Proxy URL: {proxy_url}")
    print(f"🌐 MCP Endpoint: http://0.0.0.0:3002/mcp")
    print("")
    print("Architecture:")
    print("  MCP Client → This Server (K8s) → Proxy (Mac) → Tello")
    print("")
    print("Available MCP Tools:")
    print("  • connect() - Connect to Tello")
    print("  • disconnect() - Disconnect")
    print("  • get_battery() - Get battery level")
    print("  • get_status() - Get full status")
    print("  • takeoff() - Take off")
    print("  • land() - Land")
    print("  • move(direction, distance) - Move")
    print("  • rotate(direction, angle) - Rotate")
    print("  • flip(direction) - Flip")
    print("  • send_command(command) - Raw command")
    print("")
    print("🧪 Test with MCP Inspector:")
    print("   npx @modelcontextprotocol/inspector streamable-http http://localhost:3002/mcp")
    print("=" * 60)

    # Run the FastMCP server
    app = mcp.streamable_http_app()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv('MCP_PORT', '3002')),
        log_level="info"
    )
