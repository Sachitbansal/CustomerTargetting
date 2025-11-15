#!/usr/bin/env python3
"""
Stream All Tables - Main Entry Point

This is a simple wrapper that runs the async NATS publishers.

Usage:
    python publishers/stream_all.py [--delay SECONDS]
"""

import sys
import subprocess
import os

if __name__ == "__main__":
    # Run the async version
    script_dir = os.path.dirname(os.path.abspath(__file__))
    async_script = os.path.join(script_dir, 'stream_all_async.py')
    sys.exit(subprocess.call([sys.executable, async_script] + sys.argv[1:]))
