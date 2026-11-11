"""
Server integration tests for Beep Locator.
"""

import asyncio
import json
import unittest
from aiohttp import web, ClientSession
from aiohttp.test_utils import make_mocked_request, AioHTTPTestCase, unittest_run_loop
from aiohttp.web import Application

from beep_locator.app import create_app


class TestServer(AioHTTPTestCase):
    
    async def setUpAsync(self):
        await super().setUpAsync()
        
    async def tearDownAsync(self):
        await super().tearDownAsync()

    async def get_application(self):
        """Create aiohttp application for testing."""
        app = create_app(type('Args', (), {
            'host': '127.0.0.1',
            'port': 8765,
            'tls_cert': None,
            'tls_key': None,
            'data_dir': 'data'
        })())
        return app

    @unittest_run_loop
    async def test_health_endpoint(self):
        """Test health endpoint."""
        response = await self.client.request("GET", "/health")
        assert response.status == 200
        data = await response.json()
        assert data["ok"] is True
        assert data["name"] == "beep-locator"
        assert data["version"] == "0.1.0"

    @unittest_run_loop
    async def test_admin_ui(self):
        """Test admin UI endpoint."""
        response = await self.client.request("GET", "/")
        assert response.status == 200

    @unittest_run_loop
    async def test_listener_ui(self):
        """Test listener UI endpoint."""
        response = await self.client.request("GET", "/listen")
        assert response.status == 200

    @unittest_run_loop
    async def test_room_state_not_found(self):
        """Test room state for non-existent room."""
        response = await self.client.request("GET", "/api/rooms/nonexistent/state")
        assert response.status == 404

    @unittest_run_loop
    async def test_room_state_exists(self):
        """Test room state for existing room."""
        # First create a room by connecting to WebSocket (this will create the room)
        ws_url = f"ws://{self.server.host}:{self.server.port}/ws?room=test"
        async with ClientSession() as session:
            async with session.ws_connect(ws_url) as ws:
                # Send hello message
                await ws.send_str(json.dumps({
                    "type": "hello",
                    "name": "test",
                    "capabilities": {"mic": True, "speaker": False},
                    "role": "listener"
                }))
                
                # Get response
                msg = await ws.receive()
                data = json.loads(msg.data)
                
                if data["type"] == "hello_ok":
                    # Now test room state
                    response = await self.client.request("GET", "/api/rooms/test/state")
                    assert response.status == 200
                    data = await response.json()
                    assert "room_id" in data
                    assert data["room_id"] == "test"

    @unittest_run_loop
    async def test_audio_endpoint_not_found(self):
        """Test audio endpoint for non-existent clip."""
        response = await self.client.request("GET", "/api/rooms/test/audio/nonexistent/node.wav")
        assert response.status == 404

    @unittest_run_loop
    async def test_install_module(self):
        """Test install module endpoint."""
        # Create a room first
        ws_url = f"ws://{self.server.host}:{self.server.port}/ws?room=test"
        async with ClientSession() as session:
            async with session.ws_connect(ws_url) as ws:
                await ws.send_str(json.dumps({
                    "type": "hello",
                    "name": "test",
                    "capabilities": {"mic": True, "speaker": False},
                    "role": "listener"
                }))
                
                # Get response
                msg = await ws.receive()
                data = json.loads(msg.data)
                
                if data["type"] == "hello_ok":
                    # Test install module
                    response = await self.client.request(
                        "POST",
                        "/api/rooms/test/install-module",
                        data="function test() { return 1; }"
                    )
                    assert response.status == 200

    @unittest_run_loop
    async def test_mystery_target(self):
        """Test mystery target endpoint."""
        # Create a room first
        ws_url = f"ws://{self.server.host}:{self.server.port}/ws?room=test"
        async with ClientSession() as session:
            async with session.ws_connect(ws_url) as ws:
                await ws.send_str(json.dumps({
                    "type": "hello",
                    "name": "test",
                    "capabilities": {"mic": True, "speaker": False},
                    "role": "listener"
                }))
                
                # Get response
                msg = await ws.receive()
                data = json.loads(msg.data)
                
                if data["type"] == "hello_ok":
                    # Test mystery target
                    response = await self.client.request(
                        "POST",
                        "/api/rooms/test/mystery",
                        json={
                            "event_id": "test-event",
                            "signature": {"freq_hz": 4200, "tolerance_hz": 80, "kind": "beep"}
                        }
                    )
                    assert response.status == 200


if __name__ == '__main__':
    unittest.main()