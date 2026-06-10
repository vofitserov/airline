import sys
import os
import logging
import logging.handlers

# daemon log and lock
LOGFILE = "/var/log/airline.log"

# http host and port to start http server
HTTP_HOST = "airline.local"
HTTP_PORT = 8000
HTTP_CHECK = 600

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

logger = logging.getLogger("airline")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")