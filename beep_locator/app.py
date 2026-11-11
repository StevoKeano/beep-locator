"""
Aiohttp application setup for Beep Locator.
"""

import logging
import os
from pathlib import Path

from aiohttp import web
from aiohttp.web import Application, FileResponse

from .rooms import RoomManager
from .protocol import websocket_handler


logger = logging.getLogger(__name__)


def create_app(args):
    app = web.Application()
    
    # Create room manager and attach to app
    room_manager = RoomManager(data_dir=args.data_dir)
    app["room_manager"] = room_manager

    # Add routes
    app.router.add_get("/health", health_handler)
    app.router.add_get("/", admin_handler)
    app.router.add_get("/listen", listener_handler)
    app.router.add_get("/api/rooms/{room}/state", room_state_handler)
    app.router.add_get("/api/rooms/{room}/audio/{event_id}/{node_id}.wav", audio_handler)
    app.router.add_post("/api/rooms/{room}/install-module", install_module_handler)
    app.router.add_post("/api/rooms/{room}/mystery", mystery_target_handler)
    app.router.add_get("/ws", websocket_handler)

    # Static files
    static_path = Path(__file__).parent.parent / "static"
    app.router.add_static("/static", str(static_path), name="static")

    return app


async def health_handler(request):
    """Return server health status."""
    room_manager = request.app["room_manager"]
    return web.json_response({
        "ok": True,
        "name": "beep-locator",
        "version": "0.1.0",
        "room_count": len(room_manager.rooms)
    })


async def admin_handler(request):
    """Serve the admin UI."""
    return FileResponse(path=Path(__file__).parent.parent / "static" / "admin.html")


async def listener_handler(request):
    """Serve the listener client."""
    return FileResponse(path=Path(__file__).parent.parent / "static" / "listen.html")


async def room_state_handler(request):
    """Return current room state."""
    room_id = request.match_info["room"]
    room_manager = request.app["room_manager"]
    
    try:
        room = room_manager.rooms[room_id]
    except KeyError:
        return web.json_response({"error": "Room not found"}, status=404)
    
    return web.json_response(room.to_dict())


async def audio_handler(request):
    """Serve stored audio clip."""
    room_id = request.match_info["room"]
    event_id = request.match_info["event_id"]
    node_id = request.match_info["node_id"]
    
    room_manager = request.app["room_manager"]
    try:
        room = room_manager.rooms[room_id]
    except KeyError:
        return web.json_response({"error": "Room not found"}, status=404)
    
    # Construct path to clip
    clip_path = os.path.join(
        room_manager.data_dir,
        "rooms",
        room_id,
        "clips",
        event_id,
        f"{node_id}.wav"
    )
    
    if not os.path.exists(clip_path):
        return web.json_response({"error": "Audio clip not found"}, status=404)
    
    # Read and return the file
    try:
        with open(clip_path, "rb") as f:
            data = f.read()
        return web.Response(body=data, content_type="audio/wav")
    except Exception as e:
        logger.error(f"Error reading audio clip {clip_path}: {e}")
        return web.json_response({"error": "Failed to read audio clip"}, status=500)


async def install_module_handler(request):
    """Push a new JS module to the room."""
    room_id = request.match_info["room"]
    room_manager = request.app["room_manager"]
    
    try:
        room = room_manager.rooms[room_id]
    except KeyError:
        return web.json_response({"error": "Room not found"}, status=404)
    
    # Read raw body
    body = await request.read()
    
    # Broadcast install_module message to all nodes in room
    await room.broadcast_message({
        "type": "install_module",
        "module": "detector",  # Hardcoded for now
        "version": "2",       # Versioning scheme
        "source": body.decode("utf-8")
    })
    
    return web.json_response({"status": "ok"})


async def mystery_target_handler(request):
    """Set the confirmed mystery-beep target."""
    room_id = request.match_info["room"]
    room_manager = request.app["room_manager"]
    
    try:
        room = room_manager.rooms[room_id]
    except KeyError:
        return web.json_response({"error": "Room not found"}, status=404)
    
    # Parse JSON body
    data = await request.json()
    
    # Validate
    if "event_id" not in data or "signature" not in data:
        return web.json_response({"error": "Missing event_id or signature"}, status=400)
    
    # Set target
    room.set_target(data["event_id"], data["signature"])
    
    # Broadcast to all clients
    await room.broadcast_message({
        "type": "target",
        "event_id": data["event_id"],
        "signature": data["signature"]
    })
    
    return web.json_response({"status": "ok"})