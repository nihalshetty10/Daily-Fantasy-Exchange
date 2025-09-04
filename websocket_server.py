#!/usr/bin/env python3
"""
WebSocket Server for Live Updates
Handles real-time game status, prop results, and user balance updates
"""

import asyncio
import websockets
import json
import logging
from datetime import datetime
from typing import Dict, Set
import threading
import time
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/websocket.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class LiveUpdateServer:
    def __init__(self):
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.game_statuses = {}
        self.prop_results = {}
        self.user_balances = {}
        self.user_subscriptions = {}  # user_id -> websocket mapping
        self.logger = logging.getLogger(__name__)
        
        # Ensure logs directory exists
        os.makedirs('logs', exist_ok=True)
        
    async def register(self, websocket: websockets.WebSocketServerProtocol):
        """Register a new client connection"""
        self.clients.add(websocket)
        self.logger.info(f"Client connected. Total clients: {len(self.clients)}")
        
        # Send current state to new client
        await self.send_initial_state(websocket)
        
    async def unregister(self, websocket: websockets.WebSocketServerProtocol):
        """Unregister a client connection"""
        self.clients.remove(websocket)
        
        # Remove from user subscriptions
        user_id = None
        for uid, ws in self.user_subscriptions.items():
            if ws == websocket:
                user_id = uid
                break
        
        if user_id:
            del self.user_subscriptions[user_id]
            
        self.logger.info(f"Client disconnected. Total clients: {len(self.clients)}")
        
    async def send_initial_state(self, websocket: websockets.WebSocketServerProtocol):
        """Send current game statuses and prop results to new client"""
        try:
            self.logger.info("Sending initial state to new client...")
            
            # Load real game statuses from mlb_props.json
            real_game_statuses = self.load_real_game_statuses()
            
            initial_state = {
                'type': 'initial_state',
                'game_statuses': real_game_statuses,
                'prop_results': self.prop_results,
                'timestamp': datetime.now().isoformat()
            }
            
            self.logger.info(f"Initial state prepared: {len(real_game_statuses)} games, {len(self.prop_results)} props")
            
            await websocket.send(json.dumps(initial_state))
            self.logger.info("Initial state sent successfully")
            
        except Exception as e:
            self.logger.error(f"Error sending initial state: {e}")
            # Send a minimal error response instead of crashing
            try:
                error_response = {
                    'type': 'error',
                    'message': 'Failed to load initial state',
                    'timestamp': datetime.now().isoformat()
                }
                await websocket.send(json.dumps(error_response))
            except:
                pass  # If we can't even send error, just let it fail
            
    def load_real_game_statuses(self):
        """Load real game statuses from mlb_props.json"""
        try:
            self.logger.info("Loading real game statuses from mlb_props.json...")
            
            if os.path.exists('mlb_props.json'):
                self.logger.info("mlb_props.json exists, reading file...")
                
                with open('mlb_props.json', 'r') as f:
                    data = json.load(f)
                
                self.logger.info(f"File loaded, parsing {len(data.get('games', []))} games...")
                
                game_statuses = {}
                for game in data.get('games', []):
                    game_id = game.get('game_id')
                    status = game.get('status', 'UNKNOWN')
                    if game_id and status:
                        game_statuses[game_id] = status
                        # Also update our internal state
                        self.game_statuses[game_id] = status
                
                self.logger.info(f"Successfully loaded {len(game_statuses)} real game statuses")
                return game_statuses
            else:
                self.logger.warning("mlb_props.json not found")
                return self.game_statuses
        except Exception as e:
            self.logger.error(f"Error loading real game statuses: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return self.game_statuses
        
    async def broadcast_update(self, update_data: Dict):
        """Broadcast update to all connected clients"""
        if not self.clients:
            return
            
        message = json.dumps(update_data)
        disconnected_clients = set()
        
        for client in self.clients:
            try:
                await client.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.add(client)
            except Exception as e:
                self.logger.error(f"Error broadcasting to client: {e}")
                disconnected_clients.add(client)
                
        # Clean up disconnected clients
        for client in disconnected_clients:
            await self.unregister(client)
            
    async def send_user_update(self, user_id: str, update_data: Dict):
        """Send update to specific user"""
        if user_id in self.user_subscriptions:
            websocket = self.user_subscriptions[user_id]
            try:
                await websocket.send(json.dumps(update_data))
            except Exception as e:
                self.logger.error(f"Error sending user update: {e}")
                # Remove failed subscription
                del self.user_subscriptions[user_id]
            
    async def handle_client(self, websocket: websockets.WebSocketServerProtocol, path: str):
        """Handle individual client connection"""
        await self.register(websocket)
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.handle_client_message(websocket, data)
                except json.JSONDecodeError:
                    self.logger.error(f"Invalid JSON received: {message}")
                    
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            self.logger.error(f"Error handling client: {e}")
        finally:
            await self.unregister(websocket)
            
    async def handle_client_message(self, websocket: websockets.WebSocketServerProtocol, data: Dict):
        """Handle messages from clients"""
        message_type = data.get('type')
        
        if message_type == 'subscribe_user':
            user_id = data.get('user_id')
            await self.subscribe_user_updates(websocket, user_id)
            
        elif message_type == 'ping':
            await websocket.send(json.dumps({'type': 'pong', 'timestamp': datetime.now().isoformat()}))
            
        elif message_type == 'get_status':
            # Client requesting current status
            status_data = {
                'type': 'status_response',
                'game_statuses': self.game_statuses,
                'prop_results': self.prop_results,
                'timestamp': datetime.now().isoformat()
            }
            await websocket.send(json.dumps(status_data))
            
    async def subscribe_user_updates(self, websocket: websockets.WebSocketServerProtocol, user_id: str):
        """Subscribe a client to user-specific updates"""
        self.user_subscriptions[user_id] = websocket
        self.logger.info(f"User {user_id} subscribed to updates")
        
        # Send confirmation
        await websocket.send(json.dumps({
            'type': 'subscription_confirmed',
            'user_id': user_id,
            'message': 'Subscribed to user updates'
        }))
        
    def update_game_status(self, game_id: str, new_status: str):
        """Update game status and broadcast to all clients"""
        old_status = self.game_statuses.get(game_id)
        self.game_statuses[game_id] = new_status
        
        if old_status != new_status:
            update_data = {
                'type': 'game_status_update',
                'game_id': game_id,
                'old_status': old_status,
                'new_status': new_status,
                'timestamp': datetime.now().isoformat()
            }
            
            # Broadcast update asynchronously
            asyncio.create_task(self.broadcast_update(update_data))
            self.logger.info(f"Game {game_id} status changed: {old_status} -> {new_status}")
            
    def update_prop_result(self, prop_id: str, result: str, actual_value: float):
        """Update prop result and broadcast to all clients"""
        self.prop_results[prop_id] = {
            'result': result,  # 'OVER', 'UNDER', 'PUSH'
            'actual_value': actual_value,
            'timestamp': datetime.now().isoformat()
        }
        
        update_data = {
            'type': 'prop_result_update',
            'prop_id': prop_id,
            'result': result,
            'actual_value': actual_value,
            'timestamp': datetime.now().isoformat()
        }
        
        asyncio.create_task(self.broadcast_update(update_data))
        self.logger.info(f"Prop {prop_id} result: {result} (actual: {actual_value})")
        
    def update_user_balance(self, user_id: str, new_balance: float, change_reason: str):
        """Update user balance and broadcast to subscribed clients"""
        old_balance = self.user_balances.get(user_id, 0)
        self.user_balances[user_id] = new_balance
        
        update_data = {
            'type': 'balance_update',
            'user_id': user_id,
            'old_balance': old_balance,
            'new_balance': new_balance,
            'change_amount': new_balance - old_balance,
            'change_reason': change_reason,
            'timestamp': datetime.now().isoformat()
        }
        
        # Send to specific user
        asyncio.create_task(self.send_user_update(user_id, update_data))
        self.logger.info(f"User {user_id} balance: ${old_balance} -> ${new_balance} ({change_reason})")

# Global instance
live_update_server = LiveUpdateServer()

async def start_websocket_server():
    """Start the WebSocket server"""
    try:
        # Create the server with the correct handler signature
        # Bind the method to the instance to preserve 'self' context
        handler = lambda websocket, path: live_update_server.handle_client(websocket, path)
        
        server = await websockets.serve(
            handler,
            "localhost",
            8765
        )
        logger.info("🚀 WebSocket server started on ws://localhost:8765")
        await server.wait_closed()
    except Exception as e:
        logger.error(f"Failed to start WebSocket server: {e}")

if __name__ == "__main__":
    asyncio.run(start_websocket_server()) 