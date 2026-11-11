"""
WebSocket protocol handler for Beep Locator.
"""

import asyncio
import json
import logging
from typing import Any, Dict

from aiohttp import web
from aiohttp.web import WebSocketResponse

from .rooms import RoomManager


logger = logging.getLogger(__name__)


async def websocket_handler(request):
    """Handle incoming WebSocket connections."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    # Get room from query parameter
    room_id = request.query.get("room")
    if not room_id:
        await ws.send_str(json.dumps({"type": "error", "message": "Missing room parameter"}))
        await ws.close()
        return ws
    
    # Get or create room
    room_manager: RoomManager = request.app["room_manager"]
    try:
        room = room_manager.get_room(room_id)
    except Exception as e:
        logger.error(f"Error getting room {room_id}: {e}")
        await ws.send_str(json.dumps({"type": "error", "message": "Room error"}))
        await ws.close()
        return ws

    # Create a node for this connection
    node = room.add_node(ws)
    
    try:
        # Send hello_ok message
        await ws.send_str(json.dumps({
            "type": "hello_ok",
            "node_id": node.id,
            "room": room_id,
            "config": {
                "room_width_m": room.width_m,
                "room_height_m": room.height_m,
                "grid_size_m": room.grid_size_m
            },
            "nodes": [n.to_dict() for n in room.nodes.values()],
            "events": [e.to_dict() for e in room.events.values()],
            "target": room.target
        }))
        
        # Send latency probes to the new node
        for i in range(5):
            probe_id = f"probe-{i}"
            await ws.send_str(json.dumps({
                "type": "latency_probe",
                "probe_id": probe_id,
                "t_server_ms": int(asyncio.get_event_loop().time() * 1000)
            }))
        
        # Process messages
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    await handle_message(room, node, data)
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
                    await ws.send_str(json.dumps({
                        "type": "error",
                        "message": "Invalid message format"
                    }))
            elif msg.type == web.WSMsgType.ERROR:
                logger.error(f"WebSocket error: {ws.exception()}")
                
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        # Remove node from room
        room.remove_node(node.id)
    
    return ws


async def handle_message(room, node, data):
    """Handle incoming WebSocket messages."""
    msg_type = data.get("type")
    
    if msg_type == "hello":
        await handle_hello(room, node, data)
    elif msg_type == "position":
        await handle_position(room, node, data)
    elif msg_type == "candidate":
        await handle_candidate(room, node, data)
    elif msg_type == "audio":
        await handle_audio(room, node, data)
    elif msg_type == "pong":
        await handle_pong(room, node, data)
    else:
        logger.warning(f"Unknown message type: {msg_type}")
        await node.ws.send_str(json.dumps({
            "type": "error",
            "message": f"Unknown message type: {msg_type}"
        }))


async def handle_hello(room, node, data):
    """Handle hello message."""
    # Update node info
    if "name" in data:
        node.name = data["name"]
    if "capabilities" in data:
        node.capabilities = data["capabilities"]
    if "role" in data:
        node.role = data["role"]
    
    # Store or update node in room
    room.update_node(node)
    
    # Send updated nodes list to all clients
    room.broadcast_message({
        "type": "nodes",
        "nodes": [n.to_dict() for n in room.nodes.values()]
    })


async def handle_position(room, node, data):
    """Handle position update."""
    if "x" in data and "y" in data:
        node.position = (data["x"], data["y"])
        node.last_seen = asyncio.get_event_loop().time()
        
        # Update node in room
        room.update_node(node)
        
        # Broadcast updated state to all clients
        room.broadcast_message({
            "type": "nodes",
            "nodes": [n.to_dict() for n in room.nodes.values()]
        })


async def handle_candidate(room, node, data):
    """Handle candidate detection."""
    event_id = data.get("event_id")
    if not event_id:
        return
        
    # Store candidate
    room.add_event(event_id, {
        "kind": data.get("kind"),
        "freq_hz": data.get("freq_hz"),
        "duration_ms": data.get("duration_ms"),
        "level": data.get("level"),
        "confidence": data.get("confidence"),
        "source_node_id": node.id,
        "t_client_ms": data.get("t_client_ms"),
        "t_server_ms": int(asyncio.get_event_loop().time() * 1000)
    })
    
    # Broadcast to all clients
    room.broadcast_message({
        "type": "event",
        "event_id": event_id,
        "data": {
            "kind": data.get("kind"),
            "freq_hz": data.get("freq_hz"),
            "duration_ms": data.get("duration_ms"),
            "level": data.get("level"),
            "confidence": data.get("confidence"),
            "source_node_id": node.id,
            "t_client_ms": data.get("t_client_ms"),
            "t_server_ms": int(asyncio.get_event_loop().time() * 1000)
        }
    })
    
    # Check if we can trigger a chirp
    await room.trigger_chirp_if_needed(event_id)


async def handle_audio(room, node, data):
    """Handle audio clip upload."""
    event_id = data.get("event_id")
    node_id = data.get("node_id")
    wav_b64 = data.get("wav_b64")
    
    if not all([event_id, node_id, wav_b64]):
        return
        
    # Store clip
    await room.save_clip(event_id, node_id, wav_b64)
    
    # Broadcast update to all clients
    room.broadcast_message({
        "type": "event_update",
        "event_id": event_id,
        "node_id": node_id,
        "clip_uploaded": True
    })
    
    # Check if we can triangulate now
    await room.triangulate_if_needed(event_id)


async def handle_pong(room, node, data):
    """Handle latency probe pong."""
    probe_id = data.get("probe_id")
    t_server_ms = data.get("t_server_ms")
    
    if not all([probe_id, t_server_ms]):
        return
        
    # Calculate RTT
    rtt = int(asyncio.get_event_loop().time() * 1000) - t_server_ms
    
    # Update node's RTT
    node.update_rtt(rtt)
    
    # Update node in room
    room.update_node(node)
    
    # Broadcast updated nodes list to all clients
    room.broadcast_message({
        "type": "nodes",
        "nodes": [n.to_dict() for n in room.nodes.values()]
    })