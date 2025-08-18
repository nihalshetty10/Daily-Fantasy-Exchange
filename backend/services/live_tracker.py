#!/usr/bin/env python3
"""
Live Game Tracker Service
Monitors MLB game statuses and automatically settles contracts
"""

import sqlite3
import json
import requests
import time
import threading
from datetime import datetime, timezone
import pytz

class LiveGameTracker:
    def __init__(self):
        self.db_path = 'instance/live_tracker.db'
        self.mlb_base_url = "https://statsapi.mlb.com/api/v1"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.init_database()
        
    def init_database(self):
        """Initialize the database with required tables"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Games table to track current status
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS games (
                    game_id TEXT PRIMARY KEY,
                    home_team TEXT,
                    away_team TEXT,
                    game_time TEXT,
                    status TEXT DEFAULT 'UPCOMING',
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Contracts table to track user positions
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS contracts (
                    contract_id TEXT PRIMARY KEY,
                    game_id TEXT,
                    player_name TEXT,
                    prop_type TEXT,
                    trade_type TEXT,
                    user_id TEXT,
                    quantity INTEGER,
                    avg_price REAL,
                    status TEXT DEFAULT 'ACTIVE',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (game_id) REFERENCES games (game_id)
                )
            ''')
            
            # Player status table to track who's playing/ruled out
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS player_status (
                    player_id TEXT PRIMARY KEY,
                    player_name TEXT,
                    team_name TEXT,
                    game_id TEXT,
                    status TEXT DEFAULT 'ACTIVE', -- ACTIVE, RULED_OUT, NOT_PLAYING
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (game_id) REFERENCES games (game_id)
                )
            ''')
            
            # Live stats table to track current player performance
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS live_stats (
                    player_id TEXT PRIMARY KEY,
                    game_id TEXT,
                    prop_type TEXT,
                    current_value REAL DEFAULT 0,
                    line_value REAL,
                    trade_type TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (game_id) REFERENCES games (game_id)
                )
            ''')
            
            conn.commit()
            print("Database initialized successfully")
        except Exception as e:
            print(f"Database initialization error: {e}")
        finally:
            if conn:
                conn.close()
    
    def check_live_prop_results(self):
        """Check live game stats to see if any over props have hit their targets"""
        try:
            print("Checking live prop results...")
            
            # Get all live games
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT game_id FROM games WHERE status = "LIVE"')
            live_games = cursor.fetchall()
            
            for (game_id,) in live_games:
                self.check_game_live_stats(game_id)
            
            conn.close()
            
        except Exception as e:
            print(f"Error checking live prop results: {e}")
    
    def check_game_live_stats(self, game_id):
        """Check live stats for a specific game to see if over props have hit"""
        try:
            # Get the game's live stats from MLB API
            url = f"{self.mlb_base_url}/game/{game_id}/boxscore"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code != 200:
                print(f"Failed to fetch live stats for game {game_id}")
                return
            
            data = response.json()
            
            # Process each team's players
            for team_type in ['home', 'away']:
                if team_type in data.get('teams', {}):
                    team_data = data['teams'][team_type]
                    
                    # Check all players in the game
                    if 'players' in team_data:
                        for player_id, player_data in team_data['players'].items():
                            self.check_player_live_props(str(player_id), game_id, player_data)
                            
        except Exception as e:
            print(f"Error checking live stats for game {game_id}: {e}")
    
    def check_player_live_props(self, player_id, game_id, player_data):
        """Check if a player's over props have hit their targets"""
        try:
            # Read current mlb_props.json to get this player's props
            with open('mlb_props.json', 'r') as f:
                props_data = json.load(f)
            
            if player_id not in props_data.get('props', {}):
                return
            
            player_props = props_data['props'][player_id]
            player_name = player_props['player_info']['name']
            
            # Get current stats for this player
            current_stats = self.extract_player_stats(player_data)
            
            # Check each prop to see if over has hit
            for prop in player_props.get('props', []):
                if prop.get('trade_type') == 'over':  # Only check over props
                    prop_type = prop['stat'].lower()
                    line_value = prop['line']
                    current_value = current_stats.get(prop_type, 0)
                    
                    print(f"Checking {player_name} {prop_type}: {current_value} vs {line_value}")
                    
                    # Check if over has hit
                    if self.has_over_hit(prop_type, current_value, line_value):
                        print(f"🎯 OVER HIT! {player_name} {prop_type}: {current_value} > {line_value}")
                        
                        # Process immediate cash out for all over contracts
                        self.process_over_hit_cashout(player_id, game_id, prop_type, line_value)
                        
                        # Remove all market contracts for this prop
                        self.remove_market_contracts(player_id, prop_type)
                        
        except Exception as e:
            print(f"Error checking player live props: {e}")
    
    def extract_player_stats(self, player_data):
        """Extract current stats from player data"""
        stats = {}
        
        # Batting stats
        if 'stats' in player_data and 'batting' in player_data['stats']:
            batting = player_data['stats']['batting']
            stats['hits'] = batting.get('hits', 0)
            stats['runs'] = batting.get('runs', 0)
            stats['rbis'] = batting.get('rbi', 0)
            stats['doubles'] = batting.get('doubles', 0)
            stats['triples'] = batting.get('triples', 0)
            stats['home_runs'] = batting.get('homeRuns', 0)
            
            # Calculate total bases
            singles = stats['hits'] - stats['doubles'] - stats['triples'] - stats['home_runs']
            stats['total_bases'] = singles + (stats['doubles'] * 2) + (stats['triples'] * 3) + (stats['home_runs'] * 4)
        
        # Pitching stats
        if 'stats' in player_data and 'pitching' in player_data['stats']:
            pitching = player_data['stats']['pitching']
            stats['strikeouts'] = pitching.get('strikeOuts', 0)
            stats['pitches'] = pitching.get('pitchesThrown', 0)
            
            # Calculate ERA for the game
            earned_runs = pitching.get('earnedRuns', 0)
            innings = pitching.get('inningsPitched', 0)
            if innings > 0:
                stats['era'] = (earned_runs * 9) / innings
            else:
                stats['era'] = 0
        
        return stats
    
    def has_over_hit(self, prop_type, current_value, line_value):
        """Check if an over prop has hit its target"""
        if prop_type == 'era':
            # For ERA, lower is better, so check if current ERA is below the line
            return current_value < line_value
        else:
            # For most stats, higher is better
            return current_value > line_value
    
    def process_over_hit_cashout(self, player_id, game_id, prop_type, line_value):
        """Process immediate cash out for all over contracts that have hit"""
        try:
            print(f"Processing over hit cashout for player {player_id}, {prop_type}")
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get all active over contracts for this player/prop
            cursor.execute('''
                SELECT contract_id, user_id, avg_price, quantity 
                FROM contracts 
                WHERE player_id = ? AND prop_type = ? AND trade_type = 'over' AND status = 'ACTIVE'
            ''', (player_id, prop_type))
            
            contracts = cursor.fetchall()
            
            for contract in contracts:
                contract_id, user_id, avg_price, quantity = contract
                payout = avg_price * quantity  # Full payout for hitting over
                
                print(f"Auto-cashing out user {user_id}: ${payout} for over hit")
                
                # Mark contract as cashed out
                cursor.execute('''
                    UPDATE contracts 
                    SET status = 'CASHED_OUT' 
                    WHERE contract_id = ?
                ''', (contract_id,))
                
                # In a real system, you'd also:
                # 1. Update user balance
                # 2. Send cashout notification
                # 3. Log the transaction
            
            conn.commit()
            
        except Exception as e:
            print(f"Error processing over hit cashout: {e}")
        finally:
            if conn:
                conn.close()
    
    def remove_market_contracts(self, player_id, prop_type):
        """Remove all market contracts for a prop that has already hit over"""
        try:
            print(f"Removing market contracts for {player_id} {prop_type} (over already hit)")
            
            # Read current mlb_props.json
            with open('mlb_props.json', 'r') as f:
                props_data = json.load(f)
            
            # Find and remove the specific prop
            if player_id in props_data.get('props', {}):
                player_props = props_data['props'][player_id]
                
                # Remove the specific prop that hit over
                player_props['props'] = [prop for prop in player_props['props'] 
                                       if not (prop['stat'].lower() == prop_type and prop.get('trade_type') == 'over')]
                
                # If no more props for this player, remove the player entirely
                if not player_props['props']:
                    del props_data['props'][player_id]
                    print(f"Removed all props for player {player_id}")
                else:
                    print(f"Removed {prop_type} over prop for player {player_id}")
                
                # Save updated data
                with open('mlb_props.json', 'w') as f:
                    json.dump(props_data, f, indent=2)
            
        except Exception as e:
            print(f"Error removing market contracts: {e}")
    
    def check_player_availability(self):
        """Check which players are available to play in upcoming games"""
        try:
            print("Checking player availability...")
            
            # Get today's date in Eastern Time
            et_tz = pytz.timezone('America/New_York')
            today = datetime.now(et_tz).strftime('%Y-%m-%d')
            
            # Fetch today's games
            url = f"{self.mlb_base_url}/schedule"
            params = {
                'sportId': 1,  # MLB
                'date': today,
                'fields': 'dates,games,gamePk,gameDate,status,abstractGameState'
            }
            
            response = requests.get(url, params=params, headers=self.headers)
            if response.status_code != 200:
                print(f"Failed to fetch MLB schedule: {response.status_code}")
                return
            
            data = response.json()
            
            # Process each game
            for date_data in data.get('dates', []):
                for game in date_data.get('games', []):
                    game_id = str(game['gamePk'])
                    game_status = game['status']['abstractGameState']
                    
                    # Only check player availability for upcoming games
                    if game_status == 'Preview':
                        self.check_game_lineup(game_id)
                        
        except Exception as e:
            print(f"Error checking player availability: {e}")
    
    def check_game_lineup(self, game_id):
        """Check the actual lineup for a specific game"""
        try:
            # Get the game's boxscore to see who's actually playing
            url = f"{self.mlb_base_url}/game/{game_id}/boxscore"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code != 200:
                print(f"Failed to fetch boxscore for game {game_id}")
                return
            
            data = response.json()
            
            # Get all players who are actually in the lineup
            active_players = set()
            
            for team_type in ['home', 'away']:
                if team_type in data.get('teams', {}):
                    team_data = data['teams'][team_type]
                    
                    # Check starting lineup
                    if 'battingOrder' in team_data:
                        for player_id in team_data['battingOrder']:
                            active_players.add(str(player_id))
                    
                    # Check bench players
                    if 'bench' in team_data:
                        for player_id in team_data['bench']:
                            active_players.add(str(player_id))
                    
                    # Check pitchers
                    if 'pitchers' in team_data:
                        for player_id in team_data['pitchers']:
                            active_players.add(str(player_id))
            
            # Update player statuses in database
            self.update_player_statuses(game_id, active_players)
            
        except Exception as e:
            print(f"Error checking lineup for game {game_id}: {e}")
    
    def update_player_statuses(self, game_id, active_players):
        """Update player statuses based on who's actually playing"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get all players for this game from our props
            cursor.execute('''
                SELECT DISTINCT player_id, player_name, team_name 
                FROM player_status 
                WHERE game_id = ?
            ''', (game_id,))
            
            existing_players = cursor.fetchall()
            
            for player_id, player_name, team_name in existing_players:
                if player_id in active_players:
                    # Player is active
                    new_status = 'ACTIVE'
                else:
                    # Player is ruled out or not playing
                    new_status = 'RULED_OUT'
                    
                    # Process refunds for this player
                    self.process_player_refunds(player_id, game_id)
                
                # Update player status
                cursor.execute('''
                    UPDATE player_status 
                    SET status = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE player_id = ?
                ''', (new_status, player_id))
                
                print(f"Updated {player_name} status: {new_status}")
            
            conn.commit()
            
        except Exception as e:
            print(f"Error updating player statuses: {e}")
        finally:
            if conn:
                conn.close()
    
    def process_player_refunds(self, player_id, game_id):
        """Process refunds for a player who is ruled out"""
        try:
            print(f"Processing refunds for ruled out player {player_id}")
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get all active contracts for this player
            cursor.execute('''
                SELECT contract_id, user_id, avg_price, quantity 
                FROM contracts 
                WHERE player_id = ? AND status = 'ACTIVE'
            ''', (player_id,))
            
            contracts = cursor.fetchall()
            
            for contract in contracts:
                contract_id, user_id, avg_price, quantity = contract
                refund_amount = avg_price * quantity
                
                print(f"Refunding user {user_id}: ${refund_amount} for ruled out player")
                
                # Mark contract as refunded
                cursor.execute('''
                    UPDATE contracts 
                    SET status = 'REFUNDED' 
                    WHERE contract_id = ?
                ''', (contract_id,))
                
                # In a real system, you'd also:
                # 1. Update user balance
                # 2. Send refund notification
                # 3. Log the refund transaction
            
            conn.commit()
            
            # Remove props for this player from mlb_props.json
            self.remove_player_props(player_id)
            
        except Exception as e:
            print(f"Error processing player refunds: {e}")
        finally:
            if conn:
                conn.close()
    
    def remove_player_props(self, player_id):
        """Remove all props for a ruled out player from mlb_props.json"""
        try:
            # Read current mlb_props.json
            with open('mlb_props.json', 'r') as f:
                props_data = json.load(f)
            
            # Remove the player's props
            if player_id in props_data.get('props', {}):
                player_name = props_data['props'][player_id]['player_info']['name']
                print(f"Removing props for ruled out player: {player_name}")
                
                del props_data['props'][player_id]
                
                # Save updated data
                with open('mlb_props.json', 'w') as f:
                    json.dump(props_data, f, indent=2)
                
                print(f"Removed {player_name} props from mlb_props.json")
            
        except Exception as e:
            print(f"Error removing player props: {e}")
    
    def update_game_statuses_from_mlb(self):
        """Fetch current game statuses from MLB API and update database"""
        try:
            print("Updating game statuses from MLB...")
            
            # Get today's date in Eastern Time
            et_tz = pytz.timezone('America/New_York')
            today = datetime.now(et_tz).strftime('%Y-%m-%d')
            
            # Fetch MLB schedule for today
            url = f"{self.mlb_base_url}/schedule"
            params = {
                'sportId': 1,  # MLB
                'date': today,
                'fields': 'dates,games,gamePk,gameDate,status,abstractGameState,detailedState,homeTeam,awayTeam'
            }
            
            response = requests.get(url, params=params, headers=self.headers)
            if response.status_code != 200:
                print(f"Failed to fetch MLB schedule: {response.status_code}")
                return
            
            data = response.json()
            
            # Process each game
            for date_data in data.get('dates', []):
                for game in date_data.get('games', []):
                    game_id = str(game['gamePk'])
                    game_status = game['status']['abstractGameState']
                    detailed_status = game['status'].get('detailedState', '')
                    
                    # Map MLB statuses to our statuses
                    status_mapping = {
                        'Preview': 'UPCOMING',
                        'Live': 'LIVE',
                        'Final': 'FINAL',
                        'Delayed': 'LIVE',  # Delayed games count as live
                        'Postponed': 'CANCELLED'  # Postponed games are cancelled
                    }
                    
                    mapped_status = status_mapping.get(game_status, 'UPCOMING')
                    
                    # Get team names
                    home_team = game['homeTeam']['name']
                    away_team = game['awayTeam']['name']
                    
                    # Get game time
                    game_time = game.get('gameDate', '')
                    if game_time:
                        # Convert UTC to Eastern Time
                        utc_time = datetime.fromisoformat(game_time.replace('Z', '+00:00'))
                        et_time = utc_time.astimezone(pytz.timezone('America/New_York'))
                        formatted_time = et_time.strftime('%I:%M %p ET')
                    else:
                        formatted_time = 'TBD'
                    
                    # Update game in database
                    self.update_game_status(game_id, mapped_status, home_team, away_team, formatted_time)
                    
                    # Handle status-specific actions
                    if mapped_status == 'FINAL':
                        self.handle_final_game(game_id)
                    elif mapped_status == 'CANCELLED':
                        self.handle_cancelled_game(game_id)
                    elif mapped_status == 'UPCOMING':
                        # Check player availability for upcoming games
                        self.check_game_lineup(game_id)
                    elif mapped_status == 'LIVE':
                        # Check live prop results for live games
                        self.check_game_live_stats(game_id)
            
            # Update mlb_props.json with current statuses
            self.update_props_with_game_statuses()
            
        except Exception as e:
            print(f"Error updating game statuses: {e}")
    
    def update_game_status(self, game_id, status, home_team, away_team, game_time):
        """Update game status in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO games (game_id, home_team, away_team, game_time, status, last_updated)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (game_id, home_team, away_team, game_time, status))
            
            conn.commit()
            print(f"Updated game {game_id}: {away_team} @ {home_team} - {status}")
            
        except Exception as e:
            print(f"Error updating game status: {e}")
        finally:
            if conn:
                conn.close()
    
    def get_game_status(self, game_id):
        """Get current status of a game"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT status FROM games WHERE game_id = ?', (game_id,))
            result = cursor.fetchone()
            
            return result[0] if result else 'UPCOMING'
            
        except Exception as e:
            print(f"Error getting game status: {e}")
            return 'UPCOMING'
        finally:
            if conn:
                conn.close()
    
    def handle_final_game(self, game_id):
        """Handle actions when a game goes final"""
        try:
            print(f"Game {game_id} is FINAL - enabling cash out for all contracts")
            
            # Update mlb_props.json to mark game as final
            self.update_props_with_game_statuses()
            
            # In a real system, you'd also:
            # 1. Calculate final results
            # 2. Determine contract payouts
            # 3. Update user balances
            # 4. Send notifications
            
        except Exception as e:
            print(f"Error handling final game: {e}")
    
    def handle_cancelled_game(self, game_id):
        """Handle actions when a game is cancelled/postponed"""
        try:
            print(f"Game {game_id} is CANCELLED - processing refunds")
            
            # Get all contracts for this game
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT contract_id, user_id, avg_price, quantity 
                FROM contracts 
                WHERE game_id = ? AND status = 'ACTIVE'
            ''', (game_id,))
            
            contracts = cursor.fetchall()
            
            for contract in contracts:
                contract_id, user_id, avg_price, quantity = contract
                refund_amount = avg_price * quantity
                
                print(f"Refunding user {user_id}: ${refund_amount} for contract {contract_id}")
                
                # Mark contract as cancelled
                cursor.execute('''
                    UPDATE contracts 
                    SET status = 'CANCELLED' 
                    WHERE contract_id = ?
                ''', (contract_id,))
                
                # In a real system, you'd also:
                # 1. Update user balance
                # 2. Send refund notification
                # 3. Log the refund transaction
            
            conn.commit()
            
            # Update mlb_props.json to mark game as cancelled
            self.update_props_with_game_statuses()
            
        except Exception as e:
            print(f"Error handling cancelled game: {e}")
        finally:
            if conn:
                conn.close()
    
    def update_props_with_game_statuses(self):
        """Update mlb_props.json with current game statuses"""
        try:
            # Read current mlb_props.json
            with open('mlb_props.json', 'r') as f:
                props_data = json.load(f)
            
            # Get current game statuses from database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT game_id, status FROM games')
            game_statuses = dict(cursor.fetchall())
            conn.close()
            
            updated = False
            
            # Update status for each player's props
            for player_id, player_data in props_data.get('props', {}).items():
                game_id = str(player_data['player_info']['game_id'])
                
                if game_id in game_statuses:
                    new_status = game_statuses[game_id]
                    
                    # Update status in player_info
                    if player_data['player_info'].get('status') != new_status:
                        player_data['player_info']['status'] = new_status
                        updated = True
                    
                    # Update status for each individual prop
                    for prop in player_data.get('props', []):
                        if prop.get('status') != new_status:
                            prop['status'] = new_status
                            updated = True
            
            # Save updated data
            if updated:
                with open('mlb_props.json', 'w') as f:
                    json.dump(props_data, f, indent=2)
                print("Updated mlb_props.json with current game statuses")
            
        except Exception as e:
            print(f"Error updating props with game statuses: {e}")
    
    def start_tracking(self):
        """Start the background tracking service"""
        print("🚀 Starting Live Game Tracker as background service...")
        
        def tracking_loop():
            while True:
                try:
                    # Check player availability first (for upcoming games)
                    self.check_player_availability()
                    
                    # Then update game statuses
                    self.update_game_statuses_from_mlb()
                    
                    # Check live prop results for live games
                    self.check_live_prop_results()
                    
                    time.sleep(30)  # Update every 30 seconds
                except Exception as e:
                    print(f"Error in tracking loop: {e}")
                    time.sleep(60)  # Wait longer on error
        
        # Start tracking in background thread
        tracking_thread = threading.Thread(target=tracking_loop, daemon=True)
        tracking_thread.start()
        
        print("🚀 Live Game Tracker started")
        return tracking_thread

# Initialize and start the tracker
if __name__ == "__main__":
    tracker = LiveGameTracker()
    tracker.start_tracking()
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping Live Game Tracker...") 