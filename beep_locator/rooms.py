"""
Room and node management for Beep Locator.
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import numpy as np
from aiohttp import web
from aiohttp.web import WebSocketResponse

from .audio import save_wav_clip, load_wav_clip
from .triangulate import triangulate


logger = logging.getLogger(__name__)


class Node:
    """Represents a connected node (listener or admin)."""
    
    def __init__(self, ws: WebSocketResponse, node_id: Optional[str] = None):
        self.id = node_id or str(uuid4())[:8]
        self.ws = ws
        self.name = "Unknown"
        self.role = "listener"  # or "admin"
        self.capabilities = {"mic": False, "speaker": False}
        self.position = (0.0, 0.0)  # normalized 0..1
        self.last_seen = time.time()
        self.rtt_samples: List[int] = []
        self.connected = True
        
    def to_dict(self):
        """Convert node to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "capabilities": self.capabilities,
            "position": self.position,
            "last_seen": self.last_seen,
            "rtt_ms": self.get_median_rtt(),
            "connected": self.connected
        }
        
    def update_rtt(self, rtt: int):
        """Add a new RTT sample."""
        self.rtt_samples.append(rtt)
        # Keep only the last 10 samples to prevent memory issues
        if len(self.rtt_samples) > 10:
            self.rtt_samples.pop(0)
            
    def get_median_rtt(self) -> Optional[int]:
        """Get median RTT, or None if no samples."""
        if not self.rtt_samples:
            return None
        return sorted(self.rtt_samples)[len(self.rtt_samples) // 2]


class Room:
    """Represents a single room with nodes and events."""
    
    def __init__(self, room_id: str, data_dir: str, width_m: float = 8.0, height_m: float = 6.0):
        self.id = room_id
        self.data_dir = data_dir
        self.width_m = width_m
        self.height_m = height_m
        self.grid_size_m = 0.5  # Grid size for visualization
        
        self.nodes: Dict[str, Node] = {}
        self.events: Dict[str, Dict[str, Any]] = {}
        self.target = None  # {event_id, signature}
        
        # Create room directory if it doesn't exist
        self.room_dir = os.path.join(data_dir, "rooms", room_id)
        self.clips_dir = os.path.join(self.room_dir, "clips")
        os.makedirs(self.clips_dir, exist_ok=True)
        
    def add_node(self, ws: WebSocketResponse, node_id: Optional[str] = None) -> Node:
        """Add a new node to the room."""
        node = Node(ws, node_id)
        self.nodes[node.id] = node
        logger.info(f"Added node {node.id} to room {self.id}")
        return node
        
    def remove_node(self, node_id: str):
        """Remove a node from the room."""
        if node_id in self.nodes:
            self.nodes[node_id].connected = False
            logger.info(f"Removed node {node_id} from room {self.id}")
            
    def update_node(self, node: Node):
        """Update an existing node's info."""
        if node.id in self.nodes:
            self.nodes[node.id] = node
            
    def add_event(self, event_id: str, data: Dict[str, Any]):
        """Add a new event to the room."""
        self.events[event_id] = data
        
    def set_target(self, event_id: str, signature: Dict[str, Any]):
        """Set the confirmed mystery-beep target."""
        self.target = {
            "event_id": event_id,
            "signature": signature
        }
        
    def broadcast_message(self, message: Dict[str, Any]):
        """Broadcast a message to all connected nodes."""
        for node in self.nodes.values():
            if node.connected and node.ws is not None:
                try:
                    node.ws.send_str(json.dumps(message))
                except Exception as e:
                    logger.error(f"Error broadcasting to node {node.id}: {e}")
                    
    def get_speaker_nodes(self) -> List[Node]:
        """Get all nodes with speaker capability."""
        return [n for n in self.nodes.values() if n.capabilities.get("speaker", False)]
        
    def get_lowest_rtt_speaker_node(self) -> Optional[Node]:
        """Get the node with the lowest median RTT that has a speaker."""
        speaker_nodes = self.get_speaker_nodes()
        if not speaker_nodes:
            return None
            
        # Sort by median RTT
        speaker_nodes.sort(key=lambda n: n.get_median_rtt() or float('inf'))
        
        # Return first one with speaker capability
        for node in speaker_nodes:
            if node.capabilities.get("speaker", False):
                return node
        return None
        
    async def trigger_chirp_if_needed(self, event_id: str):
        """Trigger a chirp if a speaker node is available and this is the first candidate."""
        # Check if this is the first event in the room (or it's not already a chirp)
        if len(self.events) < 1:
            return
            
        # Get anchor node
        anchor = self.get_lowest_rtt_speaker_node()
        if not anchor:
            logger.warning("No speaker-capable node found to trigger chirp")
            return
            
        # Broadcast chirp message
        await self._broadcast_chirp(anchor, event_id)
        
    async def _broadcast_chirp(self, anchor: Node, event_id: str):
        """Broadcast a chirp command to all nodes."""
        # Create a sample chirp reference (hardcoded for now)
        chirp_params = {
            "f_start_hz": 2500,
            "f_end_hz": 6000,
            "duration_ms": 120,
            "gain": 0.6,
            "window": "hann"
        }
        
        # Broadcast chirp message
        self.broadcast_message({
            "type": "chirp",
            "event_id": event_id,
            "anchor_node_id": anchor.id,
            "chirp": chirp_params,
            "record_window": {
                "before_ms": 600,
                "after_ms": 800
            },
            "play_at_ms": int(asyncio.get_event_loop().time() * 1000)
        })
        
    async def save_clip(self, event_id: str, node_id: str, wav_b64: str):
        """Save an audio clip to disk."""
        try:
            await save_wav_clip(self.clips_dir, event_id, node_id, wav_b64)
        except Exception as e:
            logger.error(f"Error saving clip for {event_id}/{node_id}: {e}")
            
    async def triangulate_if_needed(self, event_id: str):
        """Triangulate if we have enough clips."""
        # For now, just broadcast a placeholder
        self.broadcast_message({
            "type": "triangulation",
            "event_id": event_id,
            "x": 0.5,
            "y": 0.5,
            "error_m": 0.2,
            "gdop": 1.5,
            "confidence": 0.8,
            "clips": []
        })
        
    def to_dict(self):
        """Convert room state to dictionary."""
        return {
            "room_id": self.id,
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "events": [e for e in self.events.values()],
            "target": self.target,
            "join_url": f"http://localhost:8765/listen?room={self.id}"
        }


class RoomManager:
    """Manages multiple rooms."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.rooms: Dict[str, Room] = {}
        
    def get_room(self, room_id: str) -> Room:
        """Get or create a room."""
        if room_id not in self.rooms:
            self.rooms[room_id] = Room(room_id, self.data_dir)
        return self.rooms[room_id]