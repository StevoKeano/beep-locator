#!/usr/bin/env python3

"""
Beep Locator server entry point.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import aiohttp
from aiohttp import web

from beep_locator.app import create_app


logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Beep Locator server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="Port number (default: 8765)")
    parser.add_argument("--tls-cert", help="TLS certificate file")
    parser.add_argument("--tls-key", help="TLS private key file")
    parser.add_argument("--data-dir", default="data", help="Data directory (default: data/)")
    return parser.parse_args()


async def main():
    args = parse_args()
    os.makedirs(args.data_dir, exist_ok=True)
    os.makedirs(os.path.join(args.data_dir, "rooms"), exist_ok=True)

    app = create_app(args)
    
    if args.tls_cert and args.tls_key:
        ssl_context = aiohttp.web.AppRunner(app)
        logger.info(f"Starting HTTPS server on {args.host}:{args.port}")
        await web._run_app(app, host=args.host, port=args.port, ssl_context=ssl_context)
    else:
        logger.info(f"Starting HTTP server on {args.host}:{args.port}")
        await web._run_app(app, host=args.host, port=args.port)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())