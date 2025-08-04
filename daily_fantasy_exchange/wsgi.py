#!/usr/bin/env python3
"""
WSGI entry point for AWS deployment
"""

import os
from run import create_app

app, socketio = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    socketio.run(app, host="0.0.0.0", port=port) 