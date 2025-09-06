import requests
import json
import time
from datetime import datetime, timedelta
import pytz
import numpy as np
from typing import Dict, List, Tuple, Optional
import random

class NBAModel:
    def __init__(self, logger=None):
        self.logger = logger or print
        self.nba_base_url = "https://stats.nba.com/stats"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.nba.com/',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site'
        }
        self.session = requests.Session()
        self.session.timeout = 10  # 10 second timeout
        
    def get_player_recent_stats(self, player_id: str, stat_type: str) -> Dict:
        """Get player's recent performance for a specific stat type from NBA API"""
        try:
            # Get current season stats
            current_season = datetime.now().year
            season_str = f"{current_season-1}-{str(current_season)[2:]}"
            
            # Make real NBA API call to get player stats
            return self._get_real_nba_player_stats(player_id, stat_type, season_str)
            
        except Exception as e:
            self.logger(f"Error getting player stats for {player_id}: {e}")
            return None
    
    def _get_real_nba_player_stats(self, player_id: str, stat_type: str, season: str) -> Dict:
        """Get real player stats from NBA API"""
        try:
            # Validate player_id is a valid NBA player ID (numeric)
            if not player_id or not str(player_id).isdigit():
                self.logger(f"⚠️ Invalid player ID '{player_id}'")
                return None
            
            # Try different NBA API approaches
            # First, try the player game log endpoint
            url = f"{self.nba_base_url}/playergamelog"
            
            params = {
                'PlayerID': player_id,
                'Season': season,
                'SeasonType': 'Regular Season'
            }
            
            self.logger(f"🔍 Fetching real NBA stats for player {player_id}, stat: {stat_type}")
            
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            if response.status_code != 200:
                self.logger(f"❌ NBA API error {response.status_code} for player {player_id}")
                return None
            
            data = response.json()
            
            # Parse the game log data
            recent_values = self._parse_nba_game_log(data, stat_type)
            
            if not recent_values or len(recent_values) < 5:
                self.logger(f"⚠️ Insufficient data for player {player_id}")
                return None
            
            # Calculate performance metrics from real data
            mean_value = np.mean(recent_values)
            std_value = np.std(recent_values)
            median_value = np.median(recent_values)
            
            # Calculate percentiles for different difficulty levels
            percentiles = {
                'EASY': np.percentile(recent_values, 25),  # 25th percentile (lower values = easier)
                'MEDIUM': np.percentile(recent_values, 50),  # 50th percentile (median)
                'HARD': np.percentile(recent_values, 75)   # 75th percentile (higher values = harder)
            }
            
            # Store the raw values for dynamic percentile calculation
            raw_values = recent_values
            
            self.logger(f"📊 Real stats for {player_id} {stat_type}: EASY={percentiles['EASY']:.2f}, MEDIUM={percentiles['MEDIUM']:.2f}, HARD={percentiles['HARD']:.2f}")
            
            return {
                'mean': mean_value,
                'std': std_value,
                'median': median_value,
                'percentiles': percentiles,
                'recent_values': np.array(recent_values).tolist(),
                'total_games': len(recent_values)
            }
            
        except Exception as e:
            self.logger(f"❌ Error fetching real NBA stats for {player_id}: {e} - using mock data")
            return self._generate_mock_player_stats(player_id, stat_type)
    
    def _parse_nba_game_log(self, data: Dict, stat_type: str) -> List[float]:
        """Parse NBA API response to extract stat values from game log"""
        try:
            recent_values = []
            
            # Navigate through the NBA API response structure
            if 'resultSets' in data and len(data['resultSets']) > 0:
                game_log = data['resultSets'][0]
                if 'rowSet' in game_log:
                    # Get the last 15 games (most recent)
                    game_rows = game_log['rowSet'][-15:]  # Last 15 games
                    
                    for row in game_rows:
                        if len(row) >= 30:  # Ensure we have enough columns
                            # Extract the specific stat value based on the actual API response
                            if stat_type == 'points':
                                value = row[26] if len(row) > 26 else 0  # PTS column
                            elif stat_type == 'rebounds':
                                value = row[20] if len(row) > 20 else 0  # REB column
                            elif stat_type == 'assists':
                                value = row[21] if len(row) > 21 else 0  # AST column
                            elif stat_type == 'steals':
                                value = row[22] if len(row) > 22 else 0  # STL column
                            elif stat_type == 'blocks':
                                value = row[23] if len(row) > 23 else 0  # BLK column
                            elif stat_type == 'threes_made':
                                value = row[11] if len(row) > 11 else 0  # FG3M column
                            else:
                                value = 0
                            
                            # Ensure value is numeric and non-negative
                            if isinstance(value, (int, float)) and value >= 0:
                                recent_values.append(float(value))
                            elif isinstance(value, str):
                                try:
                                    float_val = float(value)
                                    if float_val >= 0:
                                        recent_values.append(float_val)
                                except (ValueError, TypeError):
                                    continue
            
            self.logger(f"📈 Parsed {len(recent_values)} real game values for {stat_type}")
            if recent_values:
                self.logger(f"📊 Sample values: {recent_values[:10]}")
            return recent_values
            
        except Exception as e:
            self.logger(f"❌ Error parsing NBA game log: {e}")
            return []
    
    def _generate_mock_player_stats(self, player_id: str, stat_type: str) -> Dict:
        """Generate mock player stats when real data is unavailable"""
        # Mock data based on typical NBA player performance
        mock_stats = {
            'points': np.random.normal(15, 5),
            'rebounds': np.random.normal(6, 2),
            'assists': np.random.normal(4, 2),
            'steals': np.random.normal(1, 0.5),
            'blocks': np.random.normal(0.8, 0.4),
            'threes_made': np.random.normal(2, 1)
        }
        
        base_value = mock_stats.get(stat_type, 5)
        recent_values = [max(0, base_value + np.random.normal(0, base_value * 0.3)) for _ in range(15)]
        
        return {
            'mean': np.mean(recent_values),
            'std': np.std(recent_values),
            'median': np.median(recent_values),
            'percentiles': {
                'EASY': np.percentile(recent_values, 25),
                'MEDIUM': np.percentile(recent_values, 50),
                'HARD': np.percentile(recent_values, 75)
            },
            'recent_values': recent_values,
            'total_games': len(recent_values)
        }
    
    def calculate_realistic_prop_line(self, player_stats: Dict, stat_type: str, difficulty: str) -> Tuple[float, float]:
        """Calculate realistic prop line and implied probability based on player performance"""
        try:
            if not player_stats or 'recent_values' not in player_stats:
                return 0.0, 0.0
            
            raw_values = player_stats['recent_values']
            
            # First determine the implied probability
            if difficulty == 'EASY':
                implied_prob = random.uniform(75, 80)
            elif difficulty == 'MEDIUM':
                implied_prob = random.uniform(40, 60)
            elif difficulty == 'HARD':
                implied_prob = random.uniform(10, 25)
            else:
                implied_prob = 50
            
            # Calculate target value based on implied probability percentile
            # For NBA stats: higher percentile = harder to achieve (better performance)
            # 83% implied prob = 17th percentile (83% of data above the line)
            target_percentile = 100 - implied_prob
            target_value = np.percentile(raw_values, target_percentile)
            
            # Round to appropriate decimal places
            if stat_type in ['points', 'rebounds', 'assists']:
                # Round to nearest 0.5 for main stats
                target_value = round(target_value * 2) / 2
            else:
                # Round to nearest 0.5 for other stats
                target_value = round(target_value * 2) / 2
            
            # Ensure minimum values
            target_value = max(0.5, target_value)
            
            return target_value, implied_prob
            
        except Exception as e:
            self.logger(f"Error calculating prop line: {e}")
            return 0.0, 0.0
    
    def generate_realistic_props(self, player_id: str, player_name: str, team_name: str, position: str, game_id: str, game_time: str = None) -> List[Dict]:
        """Generate realistic props for a player based on their actual performance data"""
        try:
            props = []
            
            # Define stat types based on position
            if position in ['PG', 'SG', 'SF', 'PF', 'C']:  # All NBA positions
                stat_types = ['points', 'rebounds', 'assists', 'steals', 'blocks', 'threes_made']
                # NBA players: 1 EASY, 4 MEDIUM, 2 HARD
                easy_count = 1
                medium_count = 4
                hard_count = 2
            
            # Generate EASY props
            for _ in range(easy_count):
                # Random stat for EASY
                stat_type = np.random.choice(stat_types)
                
                prop_line, implied_prob = self._generate_easy_prop(player_id, stat_type)
                if prop_line > 0:
                    prop = self._create_prop(stat_type, prop_line, 'EASY', implied_prob, team_name, game_id, game_time)
                    props.append(prop)
            
            # Generate MEDIUM props
            for stat_type in stat_types:
                if len([p for p in props if p['type'] == 'MEDIUM']) >= medium_count:
                    break
                
                prop_line, implied_prob = self._generate_medium_prop(player_id, stat_type)
                if prop_line > 0:
                    prop = self._create_prop(stat_type, prop_line, 'MEDIUM', implied_prob, team_name, game_id, game_time)
                    props.append(prop)
            
            # Generate HARD props
            # Random 2 of the 6 stats for HARD
            selected_stats = np.random.choice(stat_types, size=2, replace=False)
            for stat_type in selected_stats:
                prop_line, implied_prob = self._generate_hard_prop(player_id, stat_type)
                if prop_line > 0:
                    prop = self._create_prop(stat_type, prop_line, 'HARD', implied_prob, team_name, game_id, game_time)
                    props.append(prop)
            
            return props
            
        except Exception as e:
            self.logger(f"Error generating realistic props for {player_name}: {e}")
            return []
    
    def _generate_easy_prop(self, player_id: str, stat_type: str) -> Tuple[float, float]:
        """Generate an EASY prop (lower line, high probability)"""
        player_stats = self.get_player_recent_stats(player_id, stat_type)
        if not player_stats:
            return 0.0, 0.0
        
        return self.calculate_realistic_prop_line(player_stats, stat_type, 'EASY')
    
    def _generate_medium_prop(self, player_id: str, stat_type: str) -> Tuple[float, float]:
        """Generate a MEDIUM prop (median line, balanced probability)"""
        player_stats = self.get_player_recent_stats(player_id, stat_type)
        if not player_stats:
            return 0.0, 0.0
        
        return self.calculate_realistic_prop_line(player_stats, stat_type, 'MEDIUM')
    
    def _generate_hard_prop(self, player_id: str, stat_type: str) -> Tuple[float, float]:
        """Generate a HARD prop (higher line, lower probability)"""
        player_stats = self.get_player_recent_stats(player_id, stat_type)
        if not player_stats:
            return 0.0, 0.0
        
        return self.calculate_realistic_prop_line(player_stats, stat_type, 'HARD')
    
    def _create_prop(self, stat_type: str, prop_line: float, difficulty: str, implied_prob: float, team_name: str, game_id: str, game_time: str = None) -> Dict:
        """Create a prop object with all required fields"""
        # Determine prop direction based on difficulty
        if difficulty in ['EASY', 'HARD']:
            # Rule: EASY/HARD are always OVER
            direction = 'over'
        else:
            # MEDIUM can be either
            direction = random.choice(['over', 'under'])
        
        return {
            'stat': stat_type.replace('_', ' ').title(),
            'line': prop_line,
            'type': difficulty,
            'price': implied_prob,
            'direction': direction,
            'implied_prob': implied_prob,
            'opponent': self._get_opponent_info(team_name, game_id),
            'game_time': game_time or 'TBD'
        }
    
    def _get_opponent_info(self, team_name: str, game_id: str) -> str:
        """Get opponent information for a game"""
        try:
            # This would be implemented based on your existing game data
            # For now, return a placeholder
            return "vs Opponent"
        except Exception as e:
            self.logger(f"Error getting opponent info: {e}")
            return "vs Opponent"
    
    def generate_todays_props(self):
        """Generate today's NBA props - placeholder for now"""
        try:
            self.logger("🏀 Starting NBA prop generation...")
            
            # This would integrate with NBA schedule API
            # For now, return empty structure matching MLB format
            return {
                'props': [],
                'total_players': 0,
                'total_games': 0,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger(f"Error generating NBA props: {e}")
            return {
                'props': [],
                'total_players': 0,
                'total_games': 0,
                'generated_at': datetime.now().isoformat()
            }

# Initialize the model
nba_model = NBAModel()
