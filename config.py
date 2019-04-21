
import logging
import logging.handlers

# daemon log and lock
LOGFILE = "/var/log/airline-daemon.log"
PIDFILE = "/var/run/airline-daemon.pid"
OUTFILE = "/var/log/airline-daemon.out"
ERRFILE = "/var/log/garage-daemon.err"

# http host and port to start http server
HTTP_HOST = "" # "airline.local"
HTTP_PORT = 8080
HTTP_HTML = "/home/pi/airline/html/"

WIFI_LAN = "wlan0"

logger = logging.getLogger("airline")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

handler = logging.handlers.RotatingFileHandler(
                  LOGFILE, maxBytes=100000, backupCount=5)

handler.setFormatter(formatter)
logger.addHandler(handler)

