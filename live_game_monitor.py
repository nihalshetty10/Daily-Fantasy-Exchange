#!/usr/bin/env python3
"""
Live Game Monitor
Continuously monitors game statuses and prop results, sending updates via WebSocket
"""

import asyncio
import time
import requests
import json
import os
from datetime import datetime, timedelta
import logging
import random
from websocket_server import live_update_server

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/live_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class LiveGameMonitor:
    def __init__(self):
        self.mlb_api_base = "https://statsapi.mlb.com/api/v1"
        self.update_interval = 30  # seconds
        self.last_check = {}
        
        # Ensure logs directory exists
        os.makedirs('logs', exist_ok=True)
        
    async def monitor_games(self):
        """Continuously monitor game statuses"""
        logger.info("🚀 Starting live game monitoring...")
        
        while True:
            try:
                await self.check_game_statuses()
                await asyncio.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Error monitoring games: {e}")
                await asyncio.sleep(60)  # Wait longer on error
                
    async def check_game_statuses(self):
        """Check current game statuses from MLB API and sync with real data"""
        try:
            # First, load current statuses from mlb_props.json
            current_statuses = self.load_current_game_statuses()
            
            # Get today's games from MLB API
            url = f"{self.mlb_api_base}/schedule"
            params = {
                'sportId': 1,  # MLB
                'date': datetime.now().strftime('%m/%d/%Y')
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            schedule_data = response.json()
            mlb_games = schedule_data.get('dates', [{}])[0].get('games', [])
            
            # Create a mapping of MLB game IDs to their statuses
            mlb_statuses = {}
            for game in mlb_games:
                game_id = str(game['gamePk'])
                current_status = game['status']['abstractGameState']
                
                # Map MLB status to our status
                status_mapping = {
                    'Scheduled': 'UPCOMING',
                    'Live': 'LIVE',
                    'Final': 'FINAL',
                    'Postponed': 'POSTPONED',
                    'Cancelled': 'CANCELLED',
                    'Delayed': 'DELAYED',
                    'Suspended': 'SUSPENDED'
                }
                
                new_status = status_mapping.get(current_status, current_status.upper())
                mlb_statuses[game_id] = new_status
            
            # Now check ALL games from mlb_props.json, not just MLB API
            for game_id, old_status in current_statuses.items():
                # Get status from MLB API if available, otherwise keep current
                new_status = mlb_statuses.get(game_id, old_status)
                
                if old_status != new_status:
                    # Update the WebSocket server
                    live_update_server.update_game_status(game_id, new_status)
                    
                    # Log the change
                    logger.info(f"Game {game_id} status changed: {old_status} -> {new_status}")
                    
                    # Also update mlb_props.json if we can
                    self.update_game_status_in_props(game_id, new_status)
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error checking game statuses: {e}")
        except Exception as e:
            logger.error(f"Error checking game statuses: {e}")
            
    def load_current_game_statuses(self):
        """Load current game statuses from mlb_props.json"""
        try:
            if os.path.exists('mlb_props.json'):
                with open('mlb_props.json', 'r') as f:
                    data = json.load(f)
                
                statuses = {}
                for game in data.get('games', []):
                    game_id = game.get('game_id')
                    status = game.get('status', 'UNKNOWN')
                    if game_id and status:
                        statuses[game_id] = status
                
                logger.info(f"Loaded {len(statuses)} current game statuses")
                return statuses
            else:
                logger.warning("mlb_props.json not found")
                return {}
        except Exception as e:
            logger.error(f"Error loading current game statuses: {e}")
            return {}
            
    def update_game_status_in_props(self, game_id: str, new_status: str):
        """Update game status in mlb_props.json"""
        try:
            if os.path.exists('mlb_props.json'):
                with open('mlb_props.json', 'r') as f:
                    data = json.load(f)
                
                # Find and update the game status
                for game in data.get('games', []):
                    if game.get('game_id') == game_id:
                        old_status = game.get('status', 'UNKNOWN')
                        game['status'] = new_status
                        logger.info(f"Updated mlb_props.json: Game {game_id} {old_status} -> {new_status}")
                        break
                
                # Write back to file
                with open('mlb_props.json', 'w') as f:
                    json.dump(data, f, indent=2)
                    
        except Exception as e:
            logger.error(f"Error updating game status in mlb_props.json: {e}")
            
    async def check_prop_results(self):
        """Check if props have hit their targets"""
        try:
            # Load current props
            if os.path.exists('mlb_props.json'):
                with open('mlb_props.json', 'r') as f:
                    props_data = json.load(f)
                
                # Check each game's props
                for game in props_data.get('games', []):
                    game_id = game.get('game_id')
                    game_status = live_update_server.game_statuses.get(game_id, 'UNKNOWN')
                    
                    # Only check props for live or final games
                    if game_status in ['LIVE', 'FINAL']:
                        await self.check_game_props(game)
                        
        except Exception as e:
            logger.error(f"Error checking prop results: {e}")
            
    async def check_game_props(self, game):
        """Check props for a specific game"""
        try:
            game_id = game.get('game_id')
            
            # Check live prop results for live games
            if game.get('status') == 'LIVE':
                await self.check_live_prop_results(game)
                
        except Exception as e:
            logger.error(f"Error checking game props: {e}")
            
    async def simulate_live_prop_updates(self, game):
        """Simulate live prop updates for demo purposes"""
        try:
            game_id = game.get('game_id')
            logger.info(f"Simulating live prop updates for game {game_id}")
            
            # For now, simulate some prop results
            # In production, you'd integrate with live stats API
            await asyncio.sleep(2)  # Simulate API delay
            
        except Exception as e:
            logger.error(f"Error simulating live prop updates: {e}")
            
    async def check_live_prop_results(self, game):
        """Check live prop results for a specific game"""
        try:
            game_id = game.get('game_id')
            game_status = game.get('status', 'UNKNOWN')
            
            if game_status != 'LIVE':
                return
                
            logger.info(f"Checking live prop results for game {game_id}")
            
            # Load current props for this game
            if os.path.exists('mlb_props.json'):
                with open('mlb_props.json', 'r') as f:
                    props_data = json.load(f)
                
                # Find props for this game
                game_props = []
                for prop in props_data.get('props', []):
                    if prop.get('game_id') == game_id:
                        game_props.append(prop)
                
                # For each prop, check if it has hit its target
                for prop in game_props:
                    prop_id = prop.get('prop_id')
                    prop_type = prop.get('prop_type')
                    prop_line = prop.get('prop_line')
                    direction = prop.get('direction')
                    
                    if not all([prop_id, prop_type, prop_line, direction]):
                        continue
                    
                    # Simulate live stats (in production, fetch from live stats API)
                    actual_value = await self.get_live_prop_value(prop_type, game_id)
                    
                    if actual_value is not None:
                        # Determine if prop hit
                        result = self.determine_prop_result(prop_type, actual_value, prop_line, direction)
                        
                        if result:
                            # Update prop result in WebSocket server
                            live_update_server.update_prop_result(prop_id, result, actual_value)
                            logger.info(f"Prop {prop_id} result: {result} (actual: {actual_value})")
                            
        except Exception as e:
            logger.error(f"Error checking live prop results: {e}")
            
    async def get_live_prop_value(self, prop_type, game_id):
        """Get live value for a prop type (simulated for now)"""
        try:
            # In production, this would fetch from live stats API
            # For now, simulate realistic values based on prop type
            
            if prop_type == 'strikeouts':
                # Simulate strikeouts (0-15 range)
                return random.randint(0, 15)
            elif prop_type == 'hits':
                # Simulate hits (0-6 range)
                return random.randint(0, 6)
            elif prop_type == 'runs':
                # Simulate runs (0-5 range)
                return random.randint(0, 5)
            elif prop_type == 'rbis':
                # Simulate RBIs (0-4 range)
                return random.randint(0, 4)
            elif prop_type == 'walks':
                # Simulate walks (0-4 range)
                return random.randint(0, 4)
            elif prop_type == 'era':
                # Simulate ERA (0.0-10.0 range)
                return round(random.uniform(0.0, 10.0), 2)
            else:
                # Default simulation
                return random.randint(0, 10)
                
        except Exception as e:
            logger.error(f"Error getting live prop value: {e}")
            return None
            
    def determine_prop_result(self, prop_type, actual_value, prop_line, direction):
        """Determine if a prop hit OVER, UNDER, or PUSH"""
        try:
            if direction == 'OVER':
                if actual_value > prop_line:
                    return 'OVER'
                elif actual_value == prop_line:
                    return 'PUSH'
                else:
                    return 'UNDER'
            elif direction == 'UNDER':
                if actual_value < prop_line:
                    return 'UNDER'
                elif actual_value == prop_line:
                    return 'PUSH'
                else:
                    return 'OVER'
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error determining prop result: {e}")
            return None
            
    async def check_user_balances(self):
        """Check and update user balances based on prop results"""
        try:
            # This would integrate with your user database
            # For now, just log that we're checking
            logger.info("Checking user balances...")
            
        except Exception as e:
            logger.error(f"Error checking user balances: {e}")

async def start_live_monitoring():
    """Start live game and prop monitoring"""
    monitor = LiveGameMonitor()
    
    logger.info("🚀 Starting live monitoring services...")
    
    # Start monitoring tasks
    game_monitor_task = asyncio.create_task(monitor.monitor_games())
    prop_monitor_task = asyncio.create_task(monitor.check_prop_results())
    balance_monitor_task = asyncio.create_task(monitor.check_user_balances())
    
    logger.info("✅ All monitoring tasks started")
    
    # Wait for all tasks
    await asyncio.gather(
        game_monitor_task, 
        prop_monitor_task, 
        balance_monitor_task,
        return_exceptions=True
    )

if __name__ == "__main__":
    try:
        asyncio.run(start_live_monitoring())
    except KeyboardInterrupt:
        logger.info("🛑 Live monitoring stopped by user")
    except Exception as e:
        logger.error(f"❌ Live monitoring failed: {e}") 