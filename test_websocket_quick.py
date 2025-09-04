#!/usr/bin/env python3
import asyncio
import websockets
import json

async def test_websocket():
    try:
        async with websockets.connect('ws://localhost:8765') as websocket:
            print("✅ Connected to WebSocket")
            
            # Wait for initial state
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(response)
            print(f"📥 Received: {data.get('type', 'unknown')}")
            
            if data.get('type') == 'initial_state':
                game_statuses = data.get('game_statuses', {})
                print(f"🎮 {len(game_statuses)} game statuses loaded")
                print("🎉 WebSocket is working perfectly!")
            else:
                print("⚠️ Unexpected response type")
                
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket()) 