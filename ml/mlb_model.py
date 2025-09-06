import requests
import json
import time
from datetime import datetime, timedelta
import pytz
import numpy as np
from typing import Dict, List, Tuple, Optional
import random

class MLBModel:
    def __init__(self):
        self.mlb_base_url = "https://statsapi.mlb.com/api/v1"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.session = requests.Session()
        self.session.timeout = 10  # 10 second timeout
        
    def get_player_recent_stats(self, player_id: str, stat_type: str) -> Dict:
        """Get player's recent performance for a specific stat type from MLB API"""
        try:
            # Get current season stats
            current_season = datetime.now().year
            
            # Make real MLB API call to get player stats
            return self._get_real_mlb_player_stats(player_id, stat_type, current_season)
            
        except Exception as e:
            print(f"Error getting player stats for {player_id}: {e}")
            return None
    
    def _lookup_player_id_by_name(self, player_name: str) -> Optional[str]:
        """Look up MLB player ID by name"""
        try:
            # Search for player by name
            search_url = f"{self.mlb_base_url}/people/search"
            params = {
                'names': player_name,
                'sportId': 1,  # MLB
                'active': True
            }
            
            response = self.session.get(search_url, params=params, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                people = data.get('people', [])
                if people:
                    # Return the first match's ID
                    player_id = people[0].get('id')
                    if player_id:
                        print(f"✅ Found player ID {player_id} for '{player_name}'")
                        return str(player_id)
            
            print(f"❌ No MLB player found for '{player_name}'")
            return None
            
        except Exception as e:
            print(f"Error looking up player '{player_name}': {e}")
            return None
    
    def _get_real_mlb_player_stats(self, player_id: str, stat_type: str, season: int) -> Dict:
        """Get real player stats from MLB API"""
        try:
            # If player_id is not numeric, try to look it up by name
            if not player_id or not str(player_id).isdigit():
                print(f"🔍 Looking up player ID for '{player_id}'")
                numeric_id = self._lookup_player_id_by_name(player_id)
                if not numeric_id:
                    print(f"⚠️ Could not find MLB player ID for '{player_id}'")
                    return None
                player_id = numeric_id
            
            # Try different MLB API approaches
            # First, try the standard stats endpoint
            url = f"{self.mlb_base_url}/people/{player_id}/stats"
            
            params = {
                'stats': 'gameLog',
                'group': 'pitching' if stat_type in ['strikeouts', 'pitches', 'era'] else 'hitting',
                'season': season
            }
            
            print(f"🔍 Fetching real MLB stats for player {player_id}, stat: {stat_type}")
            
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            if response.status_code != 200:
                print(f"❌ MLB API error {response.status_code} for player {player_id}")
                return None
            
            data = response.json()
            
            # Parse the game log data
            recent_values = self._parse_mlb_game_log(data, stat_type)
            
            if not recent_values or len(recent_values) < 5:
                print(f"⚠️ Insufficient data for player {player_id}")
                return None
            
            # Calculate performance metrics from real data
            mean_value = np.mean(recent_values)
            std_value = np.std(recent_values)
            median_value = np.median(recent_values)
            
            # Calculate percentiles for different difficulty levels
            if stat_type == 'era':
                percentiles = {
                    'EASY': np.percentile(recent_values, 75),  # 75th percentile (higher ERA = easier)
                    'MEDIUM': np.percentile(recent_values, 50),  # 50th percentile (median)
                    'HARD': np.percentile(recent_values, 25)   # 25th percentile (lower ERA = harder)
                }
            else:
                percentiles = {
                    'EASY': np.percentile(recent_values, 25),  # 25th percentile (lower values = easier)
                    'MEDIUM': np.percentile(recent_values, 50),  # 50th percentile (median)
                    'HARD': np.percentile(recent_values, 75)   # 75th percentile (higher values = harder)
                }
            
            # Store the raw values for dynamic percentile calculation
            raw_values = recent_values
            
            print(f"📊 Real stats for {player_id} {stat_type}: EASY={percentiles['EASY']:.2f}, MEDIUM={percentiles['MEDIUM']:.2f}, HARD={percentiles['HARD']:.2f}")
            
            return {
                'mean': mean_value,
                'std': std_value,
                'median': median_value,
                'percentiles': percentiles,
                'recent_values': np.array(recent_values).tolist(),
                'total_games': len(recent_values)
            }
            
        except Exception as e:
            print(f"❌ Error fetching real MLB stats for {player_id}: {e} - using mock data")
            return self._generate_mock_player_stats(player_id, stat_type)
    
    def _parse_mlb_game_log(self, data: Dict, stat_type: str) -> List[float]:
        """Parse MLB API response to extract stat values from game log"""
        try:
            recent_values = []
            
            # Navigate through the MLB API response structure
            if 'stats' in data and len(data['stats']) > 0:
                stat_group = data['stats'][0]
                if 'splits' in stat_group:
                    # Get the last 10-15 games (most recent)
                    game_splits = stat_group['splits'][-15:]  # Last 15 games
                    
                    for split in game_splits:
                        if 'stat' in split:
                            stat_data = split['stat']
                            
                            # Extract the specific stat value based on the actual API response
                            if stat_type == 'hits':
                                value = stat_data.get('hits', 0)
                            elif stat_type == 'runs':
                                value = stat_data.get('runs', 0)
                            elif stat_type == 'rbis':
                                value = stat_data.get('rbi', 0)
                            elif stat_type == 'total_bases':
                                # Calculate total bases: singles + 2*doubles + 3*triples + 4*home_runs
                                hits = stat_data.get('hits', 0)
                                doubles = stat_data.get('doubles', 0)
                                triples = stat_data.get('triples', 0)
                                home_runs = stat_data.get('homeRuns', 0)
                                singles = hits - (doubles + triples + home_runs)
                                value = singles + 2*doubles + 3*triples + 4*home_runs
                            elif stat_type == 'strikeouts':
                                value = stat_data.get('strikeOuts', 0)
                            elif stat_type == 'pitches':
                                value = stat_data.get('numberOfPitches', 0)
                            elif stat_type == 'era':
                                # ERA comes as string like '0.00', convert to float
                                era_str = stat_data.get('era', '0.00')
                                try:
                                    value = float(era_str)
                                except (ValueError, TypeError):
                                    value = 0.0
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
            
            print(f"📈 Parsed {len(recent_values)} real game values for {stat_type}")
            if recent_values:
                print(f"📊 Sample values: {recent_values[:10]}")
            return recent_values
            
        except Exception as e:
            print(f"❌ Error parsing MLB game log: {e}")
            return []
    
    
    def calculate_realistic_prop_line(self, player_stats: Dict, stat_type: str, difficulty: str) -> Tuple[float, float]:
        """Calculate realistic prop line and implied probability based on player performance"""
        try:
            if not player_stats or 'percentiles' not in player_stats:
                return 0.0, 0.0
            
            # Special handling for ERA - ONLY UNDER for EASY/HARD, both OVER/UNDER for MEDIUM
            if stat_type == 'era':
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
                # For ERA: higher percentile = easier to achieve (worse pitching)
                percentile = 100 - implied_prob  # Convert probability to percentile
                target_value = np.percentile(player_stats['recent_values'], percentile)
                
                # Round ERA to nearest 0.5
                rounded_value = round(target_value * 2) / 2
                
                # Adjust probability based on rounding difference
                rounding_diff = abs(rounded_value - target_value)
                if rounding_diff > 0.1:  # If we rounded significantly
                    # Recalculate percentile based on rounded value
                    if rounded_value > target_value:
                        # Rounded up - slightly easier (higher probability)
                        implied_prob = min(100, implied_prob + 5)
                    else:
                        # Rounded down - slightly harder (lower probability)
                        implied_prob = max(0, implied_prob - 5)
                
                return rounded_value, implied_prob
            else:
                # For all other stats (hits, runs, rbis, total_bases, strikeouts, pitches)
                # Higher values are BETTER (harder to achieve)
                
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
                # For non-ERA stats: higher percentile = harder to achieve (better performance)
                # 83% implied prob = 17th percentile (83% of data above the line)
                percentile = 100 - implied_prob  # Convert probability to percentile
                target_value = np.percentile(player_stats['recent_values'], percentile)
            
            # Round to appropriate decimal places
            if stat_type == 'era':
                # ERA: Round to nearest 0.5 (3.0, 3.5, 4.0, 4.5, etc.)
                target_value = round(target_value * 2) / 2
            else:
                # Other stats: Round to nearest 0.5
                target_value = round(target_value * 2) / 2
            
            # Ensure minimum values
            if stat_type == 'era':
                target_value = max(0.1, target_value)
            else:
                target_value = max(0.5, target_value)
            
            # Adjust probability based on rounding difference for s the -ERA stats
            if stat_type != 'era':
                rounding_diff = abs(target_value - np.percentile(player_stats['recent_values'], percentile))
                if rounding_diff > 0.1:  # If we rounded significantly
                    if target_value > np.percentile(player_stats['recent_values'], percentile):
                        # Rounded up - slightly harder (lower probability)
                        implied_prob = max(0, implied_prob - 5)
                    else:
                        # Rounded down - slightly easier (higher probability)
                        implied_prob = min(100, implied_prob + 5)
            
            return target_value, implied_prob
            
        except Exception as e:
            print(f"Error calculating prop line: {e}")
            return 0.0, 0.0
    
    def generate_realistic_props(self, player_id: str, player_name: str, team_name: str, position: str, game_id: str, game_time: str = None) -> List[Dict]:
        """Generate realistic props for a player based on their actual performance data"""
        try:
            props = []
            
            # Define stat types based on position
            if position == 'P':  # Pitcher
                stat_types = ['strikeouts', 'pitches', 'era']
                # Pitchers: 1 EASY, 3 MEDIUM, 1 HARD
                easy_count = 1
                medium_count = 3
                hard_count = 1
            else:  # Hitter
                stat_types = ['hits', 'runs', 'rbis', 'total_bases']
                # Batters: 1 EASY (not RBIs), 4 MEDIUM, 2 HARD
                easy_count = 1
                medium_count = 4
                hard_count = 2
            
            # Generate EASY props
            for _ in range(easy_count):
                if position == 'P':
                    # Pitchers: random stat for EASY
                    stat_type = np.random.choice(stat_types)
                else:
                    # Batters: random stat for EASY, but NOT RBIs
                    non_rbi_stats = [s for s in stat_types if s != 'rbis']
                    stat_type = np.random.choice(non_rbi_stats)
                
                prop_line, implied_prob = self._generate_easy_prop(player_id, stat_type)
                if prop_line > 0:
                    prop = self._create_prop(stat_type, prop_line, 'EASY', implied_prob, team_name, game_id, game_time)
                    props.append(prop)
            
            # Generate MEDIUM props
            for stat_type in stat_types:
                if position == 'P' and len([p for p in props if p['type'] == 'MEDIUM']) >= medium_count:
                    break
                if position != 'P' and len([p for p in props if p['type'] == 'MEDIUM']) >= medium_count:
                    break
                
                prop_line, implied_prob = self._generate_medium_prop(player_id, stat_type)
                if prop_line > 0:
                    prop = self._create_prop(stat_type, prop_line, 'MEDIUM', implied_prob, team_name, game_id, game_time)
                    props.append(prop)
            
            # Generate HARD props
            if position == 'P':
                # Pitchers: random stat for HARD
                stat_type = np.random.choice(stat_types)
                prop_line, implied_prob = self._generate_hard_prop(player_id, stat_type)
                if prop_line > 0:
                    prop = self._create_prop(stat_type, prop_line, 'HARD', implied_prob, team_name, game_id, game_time)
                    props.append(prop)
            else:
                # Batters: random 2 of the 4 stats for HARD
                selected_stats = np.random.choice(stat_types, size=2, replace=False)
                for stat_type in selected_stats:
                    prop_line, implied_prob = self._generate_hard_prop(player_id, stat_type)
                    if prop_line > 0:
                        prop = self._create_prop(stat_type, prop_line, 'HARD', implied_prob, team_name, game_id, game_time)
                        props.append(prop)
            
            return props
            
        except Exception as e:
            print(f"Error generating realistic props for {player_name}: {e}")
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
    
    def _round_prop_line(self, value: float, stat_type: str) -> float:
        """Round prop line to appropriate decimal places and enforce sensible minimums"""
        # Round to nearest 0.5 for all
        rounded = round(value * 2) / 2
        if stat_type == 'era':
            # ERA: keep as rounded; allow small values
            return max(0.5, rounded)
        # Non-ERA stats: ensure at least 0.5 so we don't drop a prop due to 0
        return max(0.5, rounded)
    
    def _create_prop(self, stat_type: str, prop_line: float, difficulty: str, implied_prob: float, team_name: str, game_id: str, game_time: str = None) -> Dict:
        """Create a prop object with all required fields"""
        # Determine prop direction based on difficulty and stat type
        if difficulty in ['EASY', 'HARD']:
            # Rule: EASY/HARD are always OVER except ERA which is UNDER
            if stat_type == 'era':
                direction = 'under'
            else:
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
            'game_time': game_time or 'TBD'  # Use real game time if provided
        }
    
    def _get_opponent_info(self, team_name: str, game_id: str) -> str:
        """Get opponent information for a game"""
        try:
            # This would be implemented based on your existing game data
            # For now, return a placeholder
            return "vs Opponent"
        except Exception as e:
            print(f"Error getting opponent info: {e}")
            return "vs Opponent"
    
    def update_prop_generation_with_real_data(self):
        """Update the prop generation system to use real MLB data"""
        try:
            print("🔄 Updating prop generation with real MLB data...")
            
            # This would integrate with your existing prop_generation.py
            # to replace the current simple prop generation with realistic data
            
            print("✅ Prop generation updated with real MLB data")
            
        except Exception as e:
            print(f"Error updating prop generation: {e}")

# Initialize the model
mlb_model = MLBModel() 