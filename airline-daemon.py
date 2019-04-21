#!/usr/bin/python
# -*- coding: utf-8 -*-

import signal
import sys
import logging

from daemon import runner

from config import *
from httpserver import *

# Named global logger from config
logger = logging.getLogger("airline")

class AirlineDaemon:
    def __init__(self):
        self.stdin_path = '/dev/null'
        self.stdout_path = OUTFILE
        self.stderr_path = ERRFILE
        self.pidfile_path = PIDFILE
        self.pidfile_timeout = 10
        return
    
    def run(self):
        # signal handler can be set only in main thread
        signal.signal(signal.SIGTERM, self.shutdown)    
        signal.signal(signal.SIGINT, self.shutdown)    

        self.httpserver = HTTPConfigController()
        self.httpserver.setDaemon(True)
        self.httpserver.start()

        # join() with is_alive() is only way catch signals
        while self.httpserver.is_alive():
            self.httpserver.join(2**31)
            pass
            
        logger.critical("staring airline shutdown")
        return

    def shutdown(self, signum, frame):
        logger.critical("starting shutdown by %d" % signum)
        self.httpserver.shutdown()
        logger.critical("finished shutdown by %d" % signum)
        return
    
try:
    airline_daemon = AirlineDaemon()
    if sys.argv[1] == "test":
        stderrHandler = logging.StreamHandler(sys.stderr)
        logger.addHandler(stderrHandler)
        logger.info("running in test mode, logging to stderr")
        airline_daemon.run()
    else:
        daemon_runner = runner.DaemonRunner(airline_daemon)
        daemon_runner.daemon_context.files_preserve = [handler.stream]
        daemon_runner.do_action()
        pass
    
except Exception as e:
    logger.error("failed: \"%s\"" % str(e))
    pass

