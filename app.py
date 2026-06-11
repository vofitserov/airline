#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from socketserver import ThreadingMixIn
from socketserver import TCPServer
import json
import os
import subprocess
import shutil
import urllib.parse
import sys
import threading
import wifi_manager
import socket
from config import *

# Named global logger from config
logger = logging.getLogger("airline")

# Playback State
current_process = None
current_stream_id = None
current_stream_name = None
current_stream_url = None

# Wi-Fi connection task state
wifi_connect_thread = None
wifi_connect_status = {"status": "idle", "message": ""}

# Config lock for thread safety
config_lock = threading.Lock()

def load_config():
    with config_lock:
        if not os.path.exists(CONFIG_FILE):
            logger.warning(f"Config file not found at {CONFIG_FILE}")   
            # Fallback if config.json is missing
            default_config = {
                "streams": [
                    {"id": "kcsm", "name": "KCSM Jazz 91.1", "url": "http://ice5.securenetsystems.net/KCSM", "default": True}
                ],
                "last_played_id": "kcsm"
            }
            with open(CONFIG_FILE, "w") as f:
                json.dump(default_config, f, indent=2)
            return default_config
        
        try:
            logger.info(f"Loading config from {CONFIG_FILE}")
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading config: {e}")
            return {"streams": [], "last_played_id": None}

def save_config(config):
    with config_lock:
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=2)
            logger.info(f"Config saved to {CONFIG_FILE}")
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False

def is_ffplay_available():
    return shutil.which("ffplay") is not None

def get_current_status():
    global current_process, current_stream_id, current_stream_name, current_stream_url
    
    playing = False
    if current_process:
        if current_process.poll() is None:
            playing = True
        else:
            # Process terminated externally
            current_process = None
            current_stream_id = None
            current_stream_name = None
            current_stream_url = None
            
    wifi_status = wifi_manager.get_wifi_status()
    
    return {
        "playing": playing,
        "current_stream": {
            "id": current_stream_id,
            "name": current_stream_name,
            "url": current_stream_url
        } if playing else None,
        "wifi": wifi_status,
        "wifi_connect_status": wifi_connect_status,
        "ffplay_available": is_ffplay_available()
    }

def stop_playback():
    global current_process, current_stream_id, current_stream_name, current_stream_url
    if current_process:
        logger.info(f"Stopping current playback: {current_stream_name}")
        try:
            current_process.terminate()
            current_process.wait(timeout=2)
        except Exception:
            try:
                current_process.kill()
            except Exception:
                pass
        current_process = None
    current_stream_id = None
    current_stream_name = None
    current_stream_url = None
    return True

def start_playback(stream_id, name, url):
    global current_process, current_stream_id, current_stream_name, current_stream_url
    
    stop_playback()
    
    current_stream_id = stream_id
    current_stream_name = name
    current_stream_url = url
    
    # Save as last played stream in config
    config = load_config()
    config["last_played_id"] = stream_id
    save_config(config)
    
    if is_ffplay_available():
        try:
            # Run ffplay with -nodisp parameter (no graphics output)
            # This is critical for headless linux devices like Raspberry Pi
            cmd = ["ffplay", "-nodisp", url]
            current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            logger.info(f"Started ffplay (PID {current_process.pid}) for stream '{name}': {url}")
            return True, "Playback started"
        except Exception as e:
            current_process = None
            current_stream_id = None
            current_stream_name = None
            current_stream_url = None
            return False, f"Error spawning ffplay: {str(e)}"
    else:
        # Fallback Mock Process for non-ffplay systems
        logger.info(f"Mocking playback of '{name}' at {url} (ffplay not installed)")
        class MockProcess:
            pid = 1234
            def poll(self):
                return None
            def terminate(self):
                pass
            def wait(self, timeout=None):
                pass
        current_process = MockProcess()
        return True, "Mock playback started (ffplay missing on this system)"

def connect_wifi_worker(ssid, password):
    global wifi_connect_status
    wifi_connect_status = {"status": "connecting", "message": f"Connecting to '{ssid}'..."}
    try:
        res = wifi_manager.connect_to_wifi(ssid, password)
        logger.info(f"Wifi connect result {res} for ssid {ssid}")
        if res["success"]:
            wifi_connect_status = {"status": "success", "message": res["message"]}
        else:
            wifi_connect_status = {"status": "failed", "message": res["message"]}
    except Exception as e:
        wifi_connect_status = {"status": "failed", "message": f"Error: {str(e)}"}

class HTTPAirlineHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        req = format % args
        if req.find('/api/status') != -1: return
        logger.info(f"HTTP Request {req}")
        return

    def send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def serve_static_file(self, path):
        # Resolve absolute path and prevent directory traversal
        rel_path = path.lstrip("/")
        if not rel_path or rel_path == "index.html":
            file_path = os.path.join(STATIC_DIR, "index.html")
        else:
            # Clean path to avoid security issues
            clean_path = os.path.normpath(rel_path)
            if clean_path.startswith(".."):
                self.send_error(403, "Access Forbidden")
                return
            file_path = os.path.join(STATIC_DIR, clean_path)

        if not os.path.exists(file_path) or os.path.isdir(file_path):
            self.send_error(404, f"File Not Found: {path}")
            return

        # Determine MIME type
        _, ext = os.path.splitext(file_path)
        mime_types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css",
            ".js": "application/javascript",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".ico": "image/x-icon",
            ".json": "application/json"
        }
        content_type = mime_types.get(ext.lower(), "application/octet-stream")

        try:
            with open(file_path, "rb") as f:
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(os.path.getsize(file_path)))
                self.end_headers()
                self.wfile.write(f.read())
        except IOError:
            self.send_error(500, "Error reading file")

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        # API Routes
        if path == "/api/status":
            self.send_json(200, get_current_status())
        elif path == "/api/streams":
            config = load_config()
            self.send_json(200, config.get("streams", []))
        elif path == "/api/wifi/status":
            self.send_json(200, wifi_manager.get_wifi_status())
        elif path == "/api/wifi/scan":
            networks = wifi_manager.scan_wifi_networks()
            self.send_json(200, networks)
        elif path == "/api/wifi/connect/status":
            self.send_json(200, wifi_connect_status)
        else:
            # Fallback to serving static files
            self.serve_static_file(path)

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        # Read content length
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = b""
        if content_length > 0:
            post_data = self.rfile.read(content_length)

        # Parse JSON helper
        def get_json_body():
            try:
                return json.loads(post_data.decode("utf-8"))
            except Exception:
                return {}

        if path == "/api/play":
            body = get_json_body()
            stream_id = body.get("id")
            
            config = load_config()
            target_stream = None
            
            if stream_id:
                for stream in config.get("streams", []):
                    if stream["id"] == stream_id:
                        target_stream = stream
                        break
            
            # If a direct URL/Name was supplied instead of an ID
            if not target_stream and body.get("url") and body.get("name"):
                target_stream = {
                    "id": "temp_stream",
                    "name": body.get("name"),
                    "url": body.get("url")
                }
                
            if target_stream:
                success, msg = start_playback(target_stream["id"], target_stream["name"], target_stream["url"])
                if success:
                    self.send_json(200, {"success": True, "message": msg, "stream": target_stream})
                else:
                    self.send_json(500, {"success": False, "message": msg})
            else:
                self.send_json(400, {"success": False, "message": "Invalid stream specified."})

        elif path == "/api/stop":
            stop_playback()
            self.send_json(200, {"success": True, "message": "Playback stopped."})

        elif path == "/api/streams":
            body = get_json_body()
            name = body.get("name", "").strip()
            url = body.get("url", "").strip()
            
            if not name or not url:
                self.send_json(400, {"success": False, "message": "Name and URL are required."})
                return
                
            config = load_config()
            # Generate clean unique ID
            clean_name = "".join(e for e in name.lower() if e.isalnum() or e == " ").replace(" ", "_")
            stream_id = f"custom_{clean_name}_{int(time.time())}"
            
            new_stream = {
                "id": stream_id,
                "name": name,
                "url": url,
                "default": False
            }
            
            config["streams"].append(new_stream)
            if save_config(config):
                self.send_json(201, {"success": True, "message": "Stream added successfully", "stream": new_stream})
            else:
                self.send_json(500, {"success": False, "message": "Failed to update configuration file."})

        elif path == "/api/wifi/scan":
            networks = wifi_manager.scan_wifi_networks()
            self.send_json(200, networks)
 
        elif path == "/api/wifi/connect":
            global wifi_connect_thread
            body = get_json_body()
            ssid = body.get("ssid", "").strip()
            password = body.get("password", "").strip()
            
            if not ssid:
                self.send_json(400, {"success": False, "message": "SSID is required."})
                return
                
            # Start background connection thread so we don't lock HTTP server
            wifi_connect_thread = threading.Thread(target=connect_wifi_worker, args=(ssid, password))
            wifi_connect_thread.daemon = True
            wifi_connect_thread.start()
            
            self.send_json(200, {"success": True, "status": "connecting", "message": f"Connection to {ssid} initiated."})

        elif path == "/api/wifi/hotspot/stop":
            # Allow user to stop the hotspot mode manually
            res = wifi_manager.stop_hotspot()
            self.send_json(200, res)

        else:
            self.send_json(404, {"error": "Not Found"})

    def do_DELETE(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        # Check if route matches DELETE /api/streams/<id>
        if path.startswith("/api/streams/"):
            stream_id = path.replace("/api/streams/", "")
            
            config = load_config()
            found = False
            updated_streams = []
            
            for stream in config.get("streams", []):
                if stream["id"] == stream_id:
                    found = True
                    # Do not delete default streams
                    if stream.get("default", False):
                        self.send_json(403, {"success": False, "message": "Cannot delete preconfigured default streams."})
                        return
                else:
                    updated_streams.append(stream)
            
            if found:
                config["streams"] = updated_streams
                # If deleted stream was the last played, reset it
                if config.get("last_played_id") == stream_id:
                    config["last_played_id"] = None
                
                if save_config(config):
                    self.send_json(200, {"success": True, "message": "Stream deleted."})
                else:
                    self.send_json(500, {"success": False, "message": "Failed to update configuration file."})
            else:
                self.send_json(404, {"success": False, "message": "Stream not found."})
        else:
            self.send_json(404, {"error": "Not Found"})

    def do_OPTIONS(self):
        # Handle CORS preflight if needed
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


class HTTPWatcher(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        logger.info("created airline.local watcher")
        return

    def check(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(10)
        s.connect((HTTP_HOST, HTTP_PORT))
        s.close()
        return

    def run(self):
        logger.info("watcher checking %s:%d every %d seconds" % (HTTP_HOST, HTTP_PORT, HTTP_CHECK))
        while True:
            try:
                # sleep on start up, otherwise we'll hang in dns
                time.sleep(HTTP_CHECK)
                self.check()
                # logger.info("watcher successfully connected to %s" % LOCAL_HOST)
            except Exception as e:
                logger.error("watcher exception: " + str(e))
                os.system("service avahi-daemon restart")
                logger.info("watcher restarted avahi-daemon")
                pass
            pass
        return

class HTTPAirlineServer(ThreadingMixIn, HTTPServer):
    address_family = socket.AF_INET6
    def __init__(self, address, handler_class):
        HTTPServer.__init__(self, address, handler_class)
        return

def run_server():
    with HTTPAirlineServer(("", HTTP_PORT), HTTPAirlineHandler) as httpd:
        logger.info(f"Web server running at http://localhost:{HTTP_PORT}/")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.critical("Shutting down server...")
        finally:
            stop_playback()

if __name__ == "__main__":
    import time
    if os.access(LOGFILE, os.W_OK):
        handler = logging.handlers.RotatingFileHandler(LOGFILE, maxBytes=100000, backupCount=5)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.info("logging to " + LOGFILE)
    else:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.info("logging to stderr")

    # 1. Execute Wi-Fi startup orchestration
    # If no Wi-Fi is active and no saved connection works, it starts fallback hotspot.
    # We execute this in a separate thread so the web server starts immediately, 
    # making the UI available for setup.
    logger.info("Initializing network startup sequence...")
    network_thread = threading.Thread(target=wifi_manager.setup_network_on_startup)
    network_thread.daemon = True
    network_thread.start()

    logger.info("Starting HTTP watcher...")
    httpwatcher = HTTPWatcher()
    httpwatcher.setDaemon(True)
    httpwatcher.start()    

    # 2. Autoplay the most recently played stream on startup
    config = load_config()
    last_played_id = config.get("last_played_id")
    if last_played_id:
        # Find stream URL and Name
        streams = config.get("streams", [])
        last_stream = None
        for stream in streams:
            if stream["id"] == last_played_id:
                last_stream = stream
                break
        if last_stream:
            logger.info(f"Startup autoplay: Attempting to play last played stream '{last_stream['name']}'...")
            start_playback(last_stream["id"], last_stream["name"], last_stream["url"])

    # 3. Start the Web Server
    run_server()
