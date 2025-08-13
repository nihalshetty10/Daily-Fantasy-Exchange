#!/usr/bin/env python3
"""
Live Game Tracker Service
Monitors MLB game statuses and automatically settles contracts
"""

import requests
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sqlite3
import os

class LiveGameTracker:
    def __init__(self, db_path: str = "instance/proptrader.db"):
        self.db_path = db_path
        self.base_url = "https://statsapi.mlb.com/api/v1"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.running = False
        self.tracked_games = {}  # game_id -> game_info
        self.active_contracts = {}  # contract_id -> contract_info
        
    def start_tracking(self):
        """Start the live tracking service"""
        if self.running:
            return
            
            self.running = True
        self.tracked_games = self.load_tracked_games()
        self.active_contracts = self.load_active_contracts()
        
        # Start tracking thread
        tracking_thread = threading.Thread(target=self._tracking_loop, daemon=True)
        tracking_thread.start()
        
        print("🚀 Live Game Tracker started")
        
    def stop_tracking(self):
        """Stop the live tracking service"""
        self.running = False
        print("⏹️ Live Game Tracker stopped")
    
    def _tracking_loop(self):
        """Main tracking loop - runs every 30 seconds"""
        loop_count = 0
        while self.running:
            try:
                self.update_game_statuses()
                self.check_for_settlements()
                
                # Log status every 10 loops (5 minutes)
                loop_count += 1
                if loop_count % 10 == 0:
                    self.log_status()
                
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                print(f"Error in tracking loop: {e}")
                time.sleep(60)  # Wait longer on error
                
    def load_tracked_games(self) -> Dict:
        """Load games that need to be tracked from the database"""
        games = {}
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if games table exists and has the right structure
            cursor.execute("PRAGMA table_info(games)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'game_id' not in columns:
                print("Games table doesn't have required columns, creating sample data")
                # Create sample game data for testing
                cursor.execute("""
                    INSERT OR IGNORE INTO games (game_id, status, game_date, home_team, away_team)
                    VALUES (12345, 'Preview', '2025-08-11', 'New York Yankees', 'Boston Red Sox')
                """)
                conn.commit()
            
            # Get games from props that are still active
            cursor.execute("""
                SELECT DISTINCT g.game_id, g.status, g.game_date, g.home_team, g.away_team
                FROM games g
                WHERE g.status IN ('Preview', 'Live')
                ORDER BY g.game_date
            """)
            
            for row in cursor.fetchall():
                game_id, status, game_date, home_team, away_team = row
                games[game_id] = {
                    'game_id': game_id,
                    'status': status,
                    'game_date': game_date,
                    'home_team': home_team,
                    'away_team': away_team,
                    'last_checked': datetime.now()
                }
                
            conn.close()
        except Exception as e:
            print(f"Error loading tracked games: {e}")
            
        return games
        
    def load_active_contracts(self) -> Dict:
        """Load active contracts that need to be settled"""
        contracts = {}
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if contracts table exists and has the right structure
            cursor.execute("PRAGMA table_info(contracts)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'contract_id' not in columns:
                print("Contracts table doesn't have required columns, skipping")
                conn.close()
                return contracts
            
            # Get all active contracts
            cursor.execute("""
                SELECT c.contract_id, c.user_id, c.prop_id, c.direction, c.line, c.quantity,
                       p.stat, p.player_id, p.game_id, u.username
                FROM contracts c
                JOIN props p ON c.prop_id = p.prop_id
                JOIN users u ON c.user_id = u.user_id
                WHERE c.status = 'active'
            """)
            
            for row in cursor.fetchall():
                contract_id, user_id, prop_id, direction, line, quantity, stat, player_id, game_id, username = row
                contracts[contract_id] = {
                    'contract_id': contract_id,
                    'user_id': user_id,
                    'username': username,
                    'prop_id': prop_id,
                    'direction': direction,
                    'line': line,
                    'quantity': quantity,
                    'stat': stat,
                    'player_id': player_id,
                    'game_id': game_id
                }
                
            conn.close()
        except Exception as e:
            print(f"Error loading active contracts: {e}")
            
        return contracts
        
    def update_game_statuses(self):
        """Update status of tracked games"""
        if not self.tracked_games:
            return
        
        for game_id in list(self.tracked_games.keys()):
            try:
                # Get current game status from MLB API
                url = f"{self.base_url}/game/{game_id}/linescore"
                response = requests.get(url, headers=self.headers)
                
                if response.status_code == 200:
                    data = response.json()
                    current_status = data.get('gameData', {}).get('status', {}).get('abstractGameState', 'Unknown')
                    
                    old_status = self.tracked_games[game_id]['status']
                    
                    if current_status != old_status:
                        print(f"🔄 Game {game_id} status changed: {old_status} → {current_status}")
                        
                        # Update database
                        self.update_game_status_in_db(game_id, current_status)
                        
                        # Update local tracking
                        self.tracked_games[game_id]['status'] = current_status
                        self.tracked_games[game_id]['last_checked'] = datetime.now()
                        
                        # If game is final, mark for settlement
                        if current_status == 'Final':
                            print(f"🏁 Game {game_id} is FINAL - marking for settlement")
                            
                time.sleep(0.1)  # Rate limiting
                
            except Exception as e:
                print(f"Error updating game {game_id}: {e}")
                
    def update_game_status_in_db(self, game_id: int, status: str):
        """Update game status in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE games 
                SET status = ?, updated_at = ?
                WHERE game_id = ?
            """, (status, datetime.now(), game_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error updating game status in DB: {e}")
            
    def check_for_settlements(self):
        """Check if any games are final and settle contracts"""
        final_games = [g for g in self.tracked_games.values() if g['status'] == 'Final']
        
        for game in final_games:
            game_id = game['game_id']
            print(f"🔍 Checking settlements for final game {game_id}")
            
            # Get final stats for this game
            game_stats = self.get_final_game_stats(game_id)
            
            if game_stats:
                # Settle all contracts for this game
                self.settle_game_contracts(game_id, game_stats)
                
                # Remove from tracking (game is done)
                del self.tracked_games[game_id]
                
    def get_final_game_stats(self, game_id: int) -> Optional[Dict]:
        """Get final stats for a completed game"""
        try:
            # Get boxscore with final stats
            url = f"{self.base_url}/game/{game_id}/boxscore"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract player stats from both teams
                player_stats = {}
                
                for team_type in ['home', 'away']:
                    if team_type in data.get('teams', {}):
                        team_data = data['teams'][team_type]
                        
                        # Get player stats
                        if 'players' in team_data:
                            for player_id, player_data in team_data['players'].items():
                                if 'stats' in player_data and 'batting' in player_data['stats']:
                                    batting_stats = player_data['stats']['batting']
                                    player_stats[player_id] = {
                                        'hits': batting_stats.get('hits', 0),
                                        'runs': batting_stats.get('runs', 0),
                                        'rbi': batting_stats.get('rbi', 0),
                                        'doubles': batting_stats.get('doubles', 0),
                                        'triples': batting_stats.get('triples', 0),
                                        'homeRuns': batting_stats.get('homeRuns', 0)
                                    }
                                    
                                if 'stats' in player_data and 'pitching' in player_data['stats']:
                                    pitching_stats = player_data['stats']['pitching']
                                    if player_id not in player_stats:
                                        player_stats[player_id] = {}
                                    player_stats[player_id].update({
                                        'strikeouts': pitching_stats.get('strikeOuts', 0),
                                        'earnedRuns': pitching_stats.get('earnedRuns', 0),
                                        'inningsPitched': pitching_stats.get('inningsPitched', 0),
                                        'pitchesThrown': pitching_stats.get('pitchesThrown', 0)
                                    })
                
                return player_stats
                
        except Exception as e:
            print(f"Error getting final stats for game {game_id}: {e}")
            
        return None
        
    def settle_game_contracts(self, game_id: int, game_stats: Dict):
        """Settle all contracts for a completed game"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if contracts table has the right structure
            cursor.execute("PRAGMA table_info(contracts)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'contract_id' not in columns:
                print("Contracts table doesn't have required columns, skipping settlement")
                conn.close()
                return
            
            # Get all active contracts for this game
            cursor.execute("""
                SELECT c.contract_id, c.user_id, c.prop_id, c.direction, c.line, c.quantity,
                       p.stat, p.player_id, p.game_id, u.username, u.portfolio_balance
                FROM contracts c
                JOIN props p ON c.prop_id = p.prop_id
                JOIN users u ON c.user_id = u.user_id
                WHERE c.game_id = ? AND c.status = 'active'
            """, (game_id,))
            
            contracts_to_settle = cursor.fetchall()
            
            print(f"📊 Settling {len(contracts_to_settle)} contracts for game {game_id}")
            
            for contract_data in contracts_to_settle:
                contract_id, user_id, prop_id, direction, line, quantity, stat, player_id, game_id, username, portfolio_balance = contract_data
                
                # Check if contract won
                won = self.check_contract_result(player_id, stat, direction, line, game_stats)
                
                if won:
                    # Contract won - add $100 to portfolio
                    new_balance = portfolio_balance + 100
                    
                    cursor.execute("""
                        UPDATE users 
                        SET portfolio_balance = ?
                        WHERE user_id = ?
                    """, (new_balance, user_id))
                    
                    # Mark contract as settled
                    cursor.execute("""
                        UPDATE contracts 
                        SET status = 'settled', settled_at = ?, result = 'won'
                        WHERE contract_id = ?
                    """, (datetime.now(), contract_id))
                    
                    print(f"✅ {username} WON contract {contract_id} - +$100 (New balance: ${new_balance})")
                    
                else:
                    # Contract lost - mark as settled
                    cursor.execute("""
                        UPDATE contracts 
                        SET status = 'settled', settled_at = ?, result = 'lost'
                        WHERE contract_id = ?
                    """, (datetime.now(), contract_id))
                    
                    print(f"❌ {username} LOST contract {contract_id}")
                    
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error settling contracts for game {game_id}: {e}")
            
    def check_contract_result(self, player_id: int, stat: str, direction: str, line: float, game_stats: Dict) -> bool:
        """Check if a contract won based on final game stats"""
        if str(player_id) not in game_stats:
            return False
            
        player_final_stats = game_stats[str(player_id)]
        
        # Map stat names to game stats
        stat_mapping = {
            'Hits': 'hits',
            'Runs': 'runs', 
            'RBIs': 'rbi',
            'Total Bases': self._calculate_total_bases(player_final_stats),
            'Strikeouts': 'strikeouts',
            'ERA': self._calculate_game_era(player_final_stats),
            'Pitches': 'pitchesThrown'
        }
        
        if stat not in stat_mapping:
            return False
            
        actual_value = stat_mapping[stat]
        
        if isinstance(actual_value, str):
            actual_value = player_final_stats.get(actual_value, 0)
            
        # Check if contract won
        if direction == 'over':
            return actual_value > line
        elif direction == 'under':
            return actual_value < line
        else:
            return False
            
    def _calculate_total_bases(self, stats: Dict) -> int:
        """Calculate total bases from hits stats"""
        hits = stats.get('hits', 0)
        doubles = stats.get('doubles', 0)
        triples = stats.get('triples', 0)
        homers = stats.get('homeRuns', 0)
        
        singles = hits - doubles - triples - homers
        return singles + (doubles * 2) + (triples * 3) + (homers * 4)
        
    def _calculate_game_era(self, stats: Dict) -> float:
        """Calculate ERA for a single game"""
        earned_runs = stats.get('earnedRuns', 0)
        innings = stats.get('inningsPitched', 0)
        
        if innings > 0:
            return (earned_runs * 9) / innings
        return 0.0
        
    def get_tracking_status(self) -> Dict:
        """Get current tracking status for logging purposes"""
        return {
            'tracked_games': len(self.tracked_games),
            'active_contracts': len(self.active_contracts),
            'games_by_status': {
                'Preview': len([g for g in self.tracked_games.values() if g['status'] == 'Preview']),
                'Live': len([g for g in self.tracked_games.values() if g['status'] == 'Live']),
                'Final': len([g for g in self.tracked_games.values() if g['status'] == 'Final'])
            },
            'last_updated': datetime.now().isoformat()
        }
    
    def log_status(self):
        """Log current tracking status to console"""
        status = self.get_tracking_status()
        print(f"📊 Live Tracker Status: {status['tracked_games']} games, {status['active_contracts']} contracts")
        for game_status, count in status['games_by_status'].items():
            if count > 0:
                print(f"  - {game_status}: {count} games")

# Global instance
live_tracker = LiveGameTracker() 