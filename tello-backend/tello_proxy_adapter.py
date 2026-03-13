"""
Tello Proxy Adapter

This adapter provides a djitellopy-like interface but communicates with the
Tello Proxy Service running on the Mac via HTTP instead of UDP.

This allows the backend to run in K8s while the proxy handles the WiFi connection.
"""

import os
import requests
import time
from typing import Optional


class TelloProxyAdapter:
    """
    Adapter that mimics djitellopy.Tello interface but calls the proxy service via HTTP
    """

    def __init__(self, proxy_url: Optional[str] = None):
        """
        Initialize the adapter

        Args:
            proxy_url: URL of the proxy service (default: from TELLO_PROXY_URL env var)
        """
        self.proxy_url = proxy_url or os.getenv(
            'TELLO_PROXY_URL',
            'http://host.docker.internal:50000'
        )
        self.connected = False
        print(f"TelloProxyAdapter initialized with proxy: {self.proxy_url}")

    def _call_proxy(self, endpoint: str, method: str = 'GET', json_data: dict = None) -> dict:
        """
        Internal method to call the proxy service

        Args:
            endpoint: API endpoint (e.g., '/tello/connect')
            method: HTTP method (GET or POST)
            json_data: JSON data for POST requests

        Returns:
            Response JSON

        Raises:
            Exception: If request fails
        """
        url = f"{self.proxy_url}{endpoint}"

        try:
            if method == 'POST':
                response = requests.post(url, json=json_data, timeout=10)
            else:
                response = requests.get(url, timeout=10)

            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            raise Exception(f"Proxy timeout: {url}")
        except requests.exceptions.ConnectionError:
            raise Exception(f"Cannot connect to proxy: {url}. Is the proxy running?")
        except requests.exceptions.HTTPError as e:
            raise Exception(f"Proxy HTTP error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise Exception(f"Proxy error: {str(e)}")

    def connect(self):
        """
        Connect to Tello via proxy

        Raises:
            Exception: If connection fails
        """
        print(f"Connecting to Tello via proxy: {self.proxy_url}")

        result = self._call_proxy('/api/connect', method='POST', json_data={'source': 'tello'})

        if result.get('success'):
            self.connected = True
            print(f"✅ Connected to Tello. Battery: {result.get('battery', 'N/A')}%")
        else:
            error = result.get('error', 'Unknown error')
            raise Exception(f"Connection failed: {error}")

    def send_control_command(self, command: str) -> str:
        """
        Send a control command to Tello

        Args:
            command: Command string (e.g., 'takeoff', 'land')

        Returns:
            Response from Tello (usually 'ok')

        Raises:
            Exception: If command fails
        """
        result = self._call_proxy('/api/command', method='POST', json_data={'command': command})

        if result.get('success'):
            return result.get('response', 'ok')
        else:
            error = result.get('error', 'Unknown error')
            raise Exception(f"Command '{command}' failed: {error}")

    def get_battery(self) -> int:
        """
        Get battery level

        Returns:
            Battery percentage (0-100)

        Raises:
            Exception: If request fails
        """
        result = self._call_proxy('/api/status')

        if result.get('success'):
            status = result.get('status', {})
            battery_str = status.get('battery', '0')
            # Handle 'N/A' or other non-numeric values
            try:
                return int(battery_str) if battery_str != 'N/A' else 0
            except (ValueError, TypeError):
                return 0
        else:
            error = result.get('error', 'Unknown error')
            raise Exception(f"Failed to get battery: {error}")

    def query_sdk_version(self) -> str:
        """
        Get SDK version (stubbed - proxy doesn't support this yet)

        Returns:
            SDK version string
        """
        return "proxy-adapter-1.0"

    def query_serial_number(self) -> str:
        """
        Get serial number (stubbed - proxy doesn't support this yet)

        Returns:
            Serial number string
        """
        return "via-proxy"

    def get_height(self) -> int:
        """
        Get current height from state

        Returns:
            Height in cm
        """
        result = self._call_proxy('/api/status')
        if result.get('success'):
            status = result.get('status', {})
            height_str = status.get('height', '0')
            try:
                return int(height_str) if height_str != 'N/A' else 0
            except (ValueError, TypeError):
                return 0
        return 0

    def get_temperature(self) -> int:
        """
        Get current temperature from state

        Returns:
            Average temperature in Celsius
        """
        result = self._call_proxy('/api/status')
        if result.get('success'):
            status = result.get('status', {})
            temp_str = status.get('temperature', '0')
            try:
                return int(temp_str) if temp_str != 'N/A' else 0
            except (ValueError, TypeError):
                return 0
        return 0

    def get_barometer(self) -> float:
        """
        Get barometer reading from state

        Returns:
            Barometer value
        """
        result = self._call_proxy('/api/status')
        if result.get('success'):
            status = result.get('status', {})
            # Status endpoint doesn't return barometer, return 0.0
            return 0.0
        return 0.0

    def get_flight_time(self) -> int:
        """
        Get flight time from state

        Returns:
            Flight time in seconds
        """
        result = self._call_proxy('/api/status')
        if result.get('success'):
            status = result.get('status', {})
            # Status endpoint doesn't return flight time, return 0
            return 0
        return 0

    # Movement commands

    def takeoff(self):
        """Take off"""
        return self.send_control_command('takeoff')

    def land(self):
        """Land"""
        return self.send_control_command('land')

    def move_up(self, distance: int):
        """Move up by distance cm"""
        return self.send_control_command(f'up {distance}')

    def move_down(self, distance: int):
        """Move down by distance cm"""
        return self.send_control_command(f'down {distance}')

    def move_forward(self, distance: int):
        """Move forward by distance cm"""
        return self.send_control_command(f'forward {distance}')

    def move_back(self, distance: int):
        """Move back by distance cm"""
        return self.send_control_command(f'back {distance}')

    def move_left(self, distance: int):
        """Move left by distance cm"""
        return self.send_control_command(f'left {distance}')

    def move_right(self, distance: int):
        """Move right by distance cm"""
        return self.send_control_command(f'right {distance}')

    def rotate_clockwise(self, angle: int):
        """Rotate clockwise by angle degrees"""
        return self.send_control_command(f'cw {angle}')

    def rotate_counter_clockwise(self, angle: int):
        """Rotate counter-clockwise by angle degrees"""
        return self.send_control_command(f'ccw {angle}')

    def flip_forward(self):
        """Flip forward"""
        return self.send_control_command('flip f')

    def flip_back(self):
        """Flip back"""
        return self.send_control_command('flip b')

    def flip_left(self):
        """Flip left"""
        return self.send_control_command('flip l')

    def flip_right(self):
        """Flip right"""
        return self.send_control_command('flip r')

    # Video commands (stubbed - proxy doesn't support video yet)

    def streamon(self):
        """Start video stream (not supported via proxy)"""
        print("⚠️  Video streaming not supported via proxy adapter")
        pass

    def streamoff(self):
        """Stop video stream (not supported via proxy)"""
        pass

    def set_video_bitrate(self, bitrate):
        """Set video bitrate (not supported via proxy)"""
        pass

    def set_video_fps(self, fps):
        """Set video FPS (not supported via proxy)"""
        pass

    def get_frame_read(self):
        """Get frame reader (not supported via proxy)"""
        print("⚠️  Video streaming not supported via proxy adapter")
        return None


# Factory function to create Tello instance
def create_tello(use_proxy: bool = None) -> object:
    """
    Factory function to create either a TelloProxyAdapter or real Tello

    Args:
        use_proxy: If True, use proxy. If False, use djitellopy. If None, decide based on env var.

    Returns:
        Tello instance (either proxy adapter or real djitellopy.Tello)
    """
    if use_proxy is None:
        # Decide based on environment variable
        use_proxy = os.getenv('USE_TELLO_PROXY', 'true').lower() == 'true'

    if use_proxy:
        print("Using TelloProxyAdapter (calls Mac proxy service)")
        return TelloProxyAdapter()
    else:
        print("Using djitellopy.Tello (direct connection)")
        from djitellopy import Tello
        tello_ip = os.getenv('TELLO_IP', '192.168.10.1')
        return Tello(host=tello_ip)
