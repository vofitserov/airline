#!/usr/bin/env python3
import subprocess
import shutil
import socket
import sys
import os
import json
import time
from config import *

# Named global logger from config
logger = logging.getLogger("airline")

MOCK_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".mock_wifi_state.json")

def is_nmcli_available():
    """Check if nmcli is available on the system."""
    return shutil.which("nmcli") is not None

def _get_mock_state():
    """Get simulated Wi-Fi state for non-Linux or testing environments."""
    if os.path.exists(MOCK_STATE_FILE):
        try:
            with open(MOCK_STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    
    # Default mock state: disconnected
    default_state = {
        "connected": False,
        "ssid": "",
        "ip": "127.0.0.1",
        "mode": "Disconnected",
        "signal": 0
    }
    _save_mock_state(default_state)
    return default_state

def _save_mock_state(state):
    """Save simulated Wi-Fi state."""
    try:
        with open(MOCK_STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass

def get_local_ip():
    """Get the primary local IP address of the machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Does not actually establish a connection; just gets local IP used for routing
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def get_wifi_status():
    """Query current Wi-Fi status."""
    if not is_nmcli_available():
        return _get_mock_state()

    try:
        # Check active connections
        # nmcli -t -f ACTIVE,SSID,SIGNAL device wifi list
        res = subprocess.run(
            ["nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL,MODE", "device", "wifi", "list"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        
        connected = False
        ssid = ""
        signal = 0
        mode = "Disconnected"
        
        if res.returncode == 0:
            for line in res.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split(":")
                # Parts: ['yes'/'no', 'SSID', 'SIGNAL', 'MODE']
                if len(parts) >= 2 and parts[0] == "yes":
                    connected = True
                    ssid = parts[1].replace("\\:", ":") # Unescape colons
                    if len(parts) >= 3:
                        try:
                            signal = int(parts[2])
                        except ValueError:
                            signal = 0
                    mode = "Client"
                    break

        # Check if we are running in Hotspot mode
        if not connected:
            # Check devices to see if a hotspot connection is active
            res_dev = subprocess.run(
                ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            if res_dev.returncode == 0:
                for line in res_dev.stdout.strip().split("\n"):
                    if not line:
                        continue
                    parts = line.split(":")
                    # Parts: [DEVICE, TYPE, STATE, CONNECTION]
                    if len(parts) >= 4 and parts[1] == "wifi" and "connecting" in parts[2] or "connected" in parts[2]:
                        if "Hotspot" in parts[3] or "hotspot" in parts[3].lower():
                            connected = True
                            ssid = parts[3]
                            mode = "Hotspot"
                            break

        ip = get_local_ip() if connected else "127.0.0.1"
        
        return {
            "connected": connected,
            "ssid": ssid,
            "ip": ip,
            "mode": mode,
            "signal": signal
        }
    except Exception as e:
        logger.error(f"Error querying wifi status: {e}")
        return {
            "connected": False,
            "ssid": "",
            "ip": "127.0.0.1",
            "mode": "Error",
            "signal": 0,
            "error": str(e)
        }

def scan_wifi_networks():
    """Scan for available Wi-Fi networks."""
    if not is_nmcli_available():
        # Return mock list
        return [
            {"ssid": "Home-Network-5G", "signal": 95, "security": "WPA2"},
            {"ssid": "CoffeeShop_Free", "signal": 72, "security": "WPA1 WPA2"},
            {"ssid": "Neighbor-WiFi", "signal": 45, "security": "WPA2"},
            {"ssid": "Radio-Lab", "signal": 88, "security": "WPA2"},
            {"ssid": "Open-Access-Point", "signal": 60, "security": ""}
        ]

    try:
        # Trigger a rescan to get fresh results
        subprocess.run(["nmcli", "device", "wifi", "rescan"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        
        # Get networks list
        res = subprocess.run(
            ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        
        networks = []
        seen_ssids = set()
        
        if res.returncode == 0:
            for line in res.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split(":")
                if len(parts) >= 2:
                    ssid = parts[0].replace("\\:", ":").strip()
                    if not ssid or ssid in seen_ssids:
                        continue
                    seen_ssids.add(ssid)
                    
                    try:
                        signal = int(parts[1])
                    except ValueError:
                        signal = 0
                        
                    security = parts[2] if len(parts) >= 3 else ""
                    networks.append({
                        "ssid": ssid,
                        "signal": signal,
                        "security": security
                    })
        # Sort by signal strength
        networks.sort(key=lambda x: x["signal"], reverse=True)
        return networks
    except Exception as e:
        logger.error(f"Error scanning wifi: {e}")
        return []

def connect_to_wifi(ssid, password):
    """Attempt to connect to a Wi-Fi network."""
    logger.info(f"Attempting to connect to Wi-Fi SSID: {ssid}")
    
    if not is_nmcli_available():
        # Update mock state
        state = {
            "connected": True,
            "ssid": ssid,
            "ip": "192.168.1.145",
            "mode": "Client",
            "signal": 90
        }
        _save_mock_state(state)
        return {"success": True, "message": f"Connected to mock network '{ssid}'"}

    try:
        # Ensure hotspot is down if running
        stop_hotspot()
        
        # Delete existing connection by name before attempting to connect to avoid profile conflicts
        subprocess.run(["nmcli", "connection", "delete", ssid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Connect to wifi
        cmd = ["nmcli", "device", "wifi", "connect", ssid]
        if password:
            cmd.extend(["password", password])
            
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30 # Larger timeout for connection establishment
        )
        
        if res.returncode == 0:
            return {"success": True, "message": f"Successfully connected to '{ssid}'."}
        else:
            err = res.stderr.strip() or res.stdout.strip()
            return {"success": False, "message": f"Connection failed: {err}"}
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "Connection timed out."}
    except Exception as e:
        return {"success": False, "message": f"Error during connection: {str(e)}"}

def start_hotspot(ssid="RaspberryRadio", password="radio1234"):
    """Start Wi-Fi hotspot in AP mode."""
    logger.info(f"Starting fallback Wi-Fi hotspot: {ssid}")
    
    if not is_nmcli_available():
        # Update mock state
        state = {
            "connected": True,
            "ssid": ssid,
            "ip": "192.168.12.1",
            "mode": "Hotspot",
            "signal": 100
        }
        _save_mock_state(state)
        return {"success": True, "message": f"Mock hotspot '{ssid}' active"}

    try:
        # Bring down hotspot connection if it already exists, to reconfigure
        subprocess.run(["nmcli", "connection", "down", "Hotspot"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["nmcli", "connection", "delete", "Hotspot"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Start hotspot
        # nmcli device wifi hotspot ssid <SSID> password <PASSWORD>
        cmd = ["nmcli", "device", "wifi", "hotspot", "ssid", ssid, "password", password]
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=20
        )
        
        if res.returncode == 0:
            return {"success": True, "message": f"Hotspot '{ssid}' started successfully."}
        else:
            err = res.stderr.strip() or res.stdout.strip()
            return {"success": False, "message": f"Failed to start hotspot: {err}"}
    except Exception as e:
        return {"success": False, "message": f"Error starting hotspot: {str(e)}"}

def stop_hotspot():
    """Stop the Wi-Fi hotspot if active."""
    if not is_nmcli_available():
        state = _get_mock_state()
        if state["mode"] == "Hotspot":
            state = {
                "connected": False,
                "ssid": "",
                "ip": "127.0.0.1",
                "mode": "Disconnected",
                "signal": 0
            }
            _save_mock_state(state)
        return {"success": True, "message": "Mock hotspot stopped"}

    try:
        res = subprocess.run(
            ["nmcli", "connection", "down", "Hotspot"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        # Delete it to prevent conflict on next connections
        subprocess.run(["nmcli", "connection", "delete", "Hotspot"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if res.returncode == 0:
            return {"success": True, "message": "Hotspot stopped."}
        else:
            return {"success": False, "message": f"Failed to stop hotspot: {res.stderr.strip()}"}
    except Exception as e:
        return {"success": False, "message": f"Error stopping hotspot: {str(e)}"}

def setup_network_on_startup():
    """Startup routine: Check connection. If offline, try to connect to known networks. If fails, start Hotspot."""
    logger.info("Executing Wi-Fi startup check...")
    
    # 1. Check if we already have an active connection
    status = get_wifi_status()
    if status["connected"] and status["mode"] == "Client":
        logger.info(f"Already connected to Wi-Fi: {status['ssid']} (IP: {status['ip']})")
        return True
        
    # 2. If not connected, check if there are saved networks we can try to wake up
    if is_nmcli_available():
        # Get list of saved Wi-Fi connections
        res = subprocess.run(
            ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        
        wifi_connections = []
        if res.returncode == 0:
            for line in res.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split(":")
                if len(parts) >= 2 and "wifi" in parts[1]:
                    # Exclude the fallback Hotspot connection itself
                    if parts[0] != "Hotspot":
                        wifi_connections.append(parts[0])
        
        if wifi_connections:
            logger.info(f"Found saved Wi-Fi connection profile(s): {wifi_connections}. Attempting to connect...")
            for conn in wifi_connections:
                logger.info(f"Trying to bring up connection: {conn}")
                res_up = subprocess.run(
                    ["nmcli", "connection", "up", conn],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=20
                )
                if res_up.returncode == 0:
                    status = get_wifi_status()
                    if status["connected"]:
                        logger.info(f"Success! Connected to saved profile: {status['ssid']}")
                        return True
        
        logger.info("No active or saved Wi-Fi connections could be established.")
    else:
        # Mock behavior: we check mock state
        state = _get_mock_state()
        if state["connected"]:
            logger.info(f"Connected to mock Wi-Fi: {state['ssid']}")
            return True
        logger.info("Mock Wi-Fi state is offline.")

    # 3. Fallback: Start local hotspot
    logger.info("Starting fallback Access Point...")
    res_hs = start_hotspot()
    if res_hs["success"]:
        logger.info("Fallback Hotspot is active.")
        return False
    else:
        logger.error(f"CRITICAL: Failed to start hotspot fallback: {res_hs['message']}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--startup":
        setup_network_on_startup()
    else:
        # Simple status print
        logger.info("Wi-Fi Status:")
        logger.info(json.dumps(get_wifi_status(), indent=2))
        logger.info("\nScanning nearby networks:")
        logger.info(json.dumps(scan_wifi_networks()[:5], indent=2))
