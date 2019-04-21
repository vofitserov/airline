from BaseHTTPServer import BaseHTTPRequestHandler
from BaseHTTPServer import HTTPServer
from SocketServer import ThreadingMixIn

import urlparse
import time
import threading
import wifi
import wifi.exceptions
import cgi
import subprocess

from config import *

# Named global logger from config
logger = logging.getLogger("airline")

html = """
<!DOCTYPE html>
<html>
<body>

<h1>%s</h1>

<form action="/">
  <input type="submit" name="action" value="Open">
  <input type="submit" name="action" value="Close">
  <input type="submit" name="action" value="Refresh">
</form>

<br>
<br>
%s

</body>
</html>
"""



class HTTPConfigHandler(BaseHTTPRequestHandler):
    def respond_html(self, content):
        # Instance of global GarageDoor object is on server.
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(content)
        return

    def get_mimetype(self, filename):
        mimetype = None
        if filename.endswith(".html"):
            mimetype='text/html'
        if filename.endswith(".jpg"):
            mimetype='image/jpg'
        if filename.endswith(".gif"):
            mimetype='image/gif'
        if filename.endswith(".js"):
            mimetype='application/javascript'
        if filename.endswith(".css"):
            mimetype='text/css'
        if filename.endswith(".ttf"):
            mimetype="application/x-font-ttf"
        if filename.endswith(".woff"):
            mimetype="application/font-woff"
        if filename.endswith(".woff2"):
            mimetype="application/font-woff2"
        return mimetype

    def respond_file(self, filename):
        try:
            mimetype = self.get_mimetype(filename)
            if not mimetype: raise IOError("Unknown mimetype")
            f = open(HTTP_HTML + filename)
            self.send_response(200)
            self.send_header("Content-type", mimetype)
            self.end_headers()
            self.wfile.write(f.read())
            f.close()
        except IOError as e:
            self.send_error(404, "%s: %s" % (str(e), filename))
            pass
        return

    def log_message(self, format, *args):
        return logger.info(self.address_string() + " - " + (format % args))

    def get_quality(self, n):
        quality = n.quality
        try:
            (rec_signal, max_signal) = n.quality.split("/")
            strength = float(rec_signal)/float(max_signal)*100.0
            quality = "%.0f%%" % strength
        except:
            pass
        return quality
            
    def get_network_options(self):
        html = ""
        networks = self.server.get_networks()
        networks.sort(key=lambda n: n.signal, reverse=True) 
        for n in networks:
            if len(n.ssid) < 3: continue
            print n.ssid, n.signal, n.quality, n.encrypted, n.address
            encrypted = "Encrypted" if n.encrypted else "Open"
            quality = self.get_quality(n)
            html += "<option value=\"%s\">%s (%s, %s)</option>\n" % \
                (n.ssid, n.ssid, quality, encrypted)
            pass
        html += "<option value=\"Airline\">Airline (Host)</option>\n"
        return html

    def do_POST(self):
        length = int(self.headers.getheader('content-length'))
        field_data = self.rfile.read(length)
        fields = urlparse.parse_qs(field_data)
        if self.path == "/network":
            ssid = fields["ssid"][0]
            password = fields["password"][0]
            html = "<html><body><h1>Configuring WiFi</h1>"
            html += "Network: %s<br>" % (ssid)
            status = self.server.set_network(ssid, password)
            html += "Status: %s<br>" % (status)
            html += "</body></html>"
            self.respond_html(html)
        else:
            self.send_error(404, "Unknown path: %s" % (self.path))
            pass
        return
    
    def do_GET(self):
        if self.path == "/":
            content = open(HTTP_HTML + "index.html").read().decode("utf8")
            print self.get_network_options()
            networks = self.get_network_options()
            content = content.replace("<!--{NETWORKS}-->", networks)
            self.respond_html(content)
            return
        else:
            self.respond_file(self.path)
            return
        return

class HTTPConfigServer(ThreadingMixIn, HTTPServer):
    def __init__(self, address, handler_class):
        HTTPServer.__init__(self, address, handler_class)
        self.last_time = 0 
        self.networks = None
        return

    def get_networks(self):
        current_time = time.time()
        try:
            if current_time - self.last_time > 60:
                self.networks = wifi.Cell.all(WIFI_LAN)
                self.last_time = current_time
                pass
        except wifi.exceptions.InterfaceError, e:
            logger.info("Error scanning interfaces: %s" % str(e));
            self.networks = []
            pass
        return self.networks

    def set_network(self, ssid, password):
        try:
            networks = self.get_networks()
            cell = [n for n in networks if n.ssid == ssid]
            logger.info("Found %d cells matching ssid=%s among %d networks" % (len(cell), ssid, len(networks)))
            if len(cell) != 1: 
                return "Cell with %s not found" % (ssid)
            scheme = wifi.Scheme.find(WIFI_LAN, 'airline')
            if scheme:
                logger.info("Wifi Scheme \'airline\' found, deleting.")
                scheme.delete()
                pass
            scheme = wifi.Scheme.for_cell(WIFI_LAN, 'airline', cell[0], password)
            logger.info("Wifi Scheme \'airline\' created for %s" % (ssid))
            scheme.save()
            logger.info("Wifi Scheme \'airline\' saved, activating...")
            scheme.activate()
            logger.info("Wifi Scheme \'airline\' successfully activated.")
        except subprocess.CalledProcessError, e:
            return "Error %d while executing %s: %s" % (e.returncode, e.cmd, e.output)
        return "OK"

class HTTPConfigController(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        logger.info("created http controller")
        return
    
    def run(self):
        logger.info("starting HTTP server: %s:%d" % (HTTP_HOST, HTTP_PORT))
        self.httpserver = HTTPConfigServer(("", HTTP_PORT), HTTPConfigHandler)
        logger.info("starting serve forever...")
        self.httpserver.serve_forever()
        logger.info("...done serve forever")
        return

    def shutdown(self):
        self.httpserver.shutdown()
        return
