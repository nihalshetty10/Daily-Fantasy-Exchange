import requests
import json
import time
from datetime import datetime, timedelta
import pytz
import numpy as np
from ml.mlb_model import MLBModel

class RealisticPropGenerator:
    def __init__(self):
        self.mlb_base_url = "https://statsapi.mlb.com/api/v1"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.analyzer = MLBModel()
        
    def get_todays_games(self):
        """Get today's MLB games"""
        try:
            # Get today's date in the format MLB API expects
            today = datetime.now().strftime('%Y-%m-%d')
            url = f"{self.mlb_base_url}/schedule"
            params = {
                'sportIds': 1,  # MLB
                'date': today
            }
            
            print(f"Fetching MLB schedule for {today}...")
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code != 200:
                print(f"Failed to fetch MLB schedule: {response.status_code}")
                print(f"Response: {response.text[:200]}")
                return []
            
            data = response.json()
            games = []
            
            for date_data in data.get('dates', []):
                for game in date_data.get('games', []):
                    # Extract team names from the nested structure
                    home_team_name = game['teams']['home']['team']['name']
                    away_team_name = game['teams']['away']['team']['name']
                    
                    games.append({
                        'game_id': game['gamePk'],
                        'home_team': home_team_name,
                        'away_team': away_team_name,
                        'game_time': game.get('gameDate', ''),
                        'status': game['status']['abstractGameState']
                    })
            
            print(f"Found {len(games)} games for {today}")
            return games
            
        except Exception as e:
            print(f"Error getting today's games: {e}")
            return []

    def get_team_roster(self, team_id: str) -> list:
        """Get team roster for active players"""
        try:
            url = f"{self.mlb_base_url}/teams/{team_id}/roster"
            params = {
                'rosterType': 'active',
                'fields': 'roster,person,position,stats'
            }
            
            response = requests.get(url, headers=self.headers)
            if response.status_code != 200:
                return []
            
            data = response.json()
            roster = []
            
            for person in data.get('roster', []):
                player = person['person']
                position = person.get('position', {}).get('abbreviation', '')
                
                # Only include relevant positions
                if position in ['P', 'C', '1B', '2B', 'SS', 'LF', 'CF', 'RF', 'DH']:
                    player_id = player['id']
                    player_name = player['fullName']
                    print(f"🔍 Found player: {player_name} (ID: {player_id}) - Position: {position}")
                    
                    roster.append({
                        'player_id': player_id,
                        'name': player_name,
                        'position': position
                    })
            
            return roster
                            
        except Exception as e:
            print(f"Error getting team roster: {e}")
            return []
    
    def generate_realistic_props_for_player(self, player_id: str, player_name: str, team_name: str, position: str, game_id: str) -> list:
        """Generate realistic props for a player using MLB performance data"""
        try:
            # Use the MLB analyzer to get realistic props
            props = self.analyzer.generate_realistic_props(player_id, player_name, team_name, position, game_id)
            
            if not props:
                print(f"No realistic props generated for {player_name}")
                return []
            
            print(f"Generated {len(props)} realistic props for {player_name}")
            return props
            
        except Exception as e:
            print(f"Error generating realistic props for {player_name}: {e}")
            return []
    
    def get_team_id_from_name(self, team_name: str) -> str:
        """Get team ID from team name"""
        try:
            url = f"{self.mlb_base_url}/teams"
            params = {
                'sportId': 1,  # MLB
                'fields': 'teams,id,name'
            }
            
            response = requests.get(url, headers=self.headers)
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            for team in data.get('teams', []):
                if team['name'] == team_name:
                    return str(team['id'])
            
            return None
        
        except Exception as e:
            print(f"Error getting team ID for {team_name}: {e}")
            return None
    
    def generate_todays_props(self):
        """Generate realistic props for today's games"""
        try:
            print("🚀 Starting realistic prop generation...")
            
            # Get today's games
            games = self.get_todays_games()
            if not games:
                print("No games found for today")
                return
            
            print(f"Found {len(games)} games for today")
            
            all_props = {}
            games_data = []
            
            for game in games:
                print(f"\nProcessing game: {game['away_team']} @ {game['home_team']}")
                
                # Set current processing context for metadata
                self.current_processing_game = game
                
                # Add game to games data
                games_data.append({
                    'game_id': game['game_id'],
                    'game_date': datetime.now().isoformat(),
                    'game_time_et': self._convert_to_eastern_time(game['game_time']),
                    'game_datetime': game['game_time'],
                    'status': game['status'],
                    'home_team': {
                        'id': 0,  # Placeholder
                        'name': game['home_team'],
                        'abbreviation': game['home_team'][:3].upper()
                    },
                    'away_team': {
                        'id': 0,  # Placeholder
                        'name': game['away_team'],
                        'abbreviation': game['away_team'][:3].upper()
                    }
                })
                
                # Get rosters for both teams
                away_team_id = self.get_team_id_from_name(game['away_team'])
                home_team_id = self.get_team_id_from_name(game['home_team'])
                
                if away_team_id and home_team_id:
                    # Process away team
                    self.current_processing_team = game['away_team']
                    away_roster = self.get_team_roster(away_team_id)
                    for player in away_roster:
                        props = self.generate_realistic_props_for_player(
                            player['player_id'],
                            player['name'],
                            game['away_team'],
                            player['position'],
                            game['game_id']
                        )
                        
                        if props:
                            # Add opponent info to each prop
                            for prop in props:
                                self._add_prop_metadata(prop, game)
                            
                            all_props[player['player_id']] = {
                                'player_info': {
                                    'name': player['name'],
                                    'team_name': game['away_team'],
                                    'position': player['position'],
                                    'game_id': game['game_id'],
                                    'status': 'UPCOMING'
                                },
                                'props': props
                            }
                    
                    # Process home team
                    self.current_processing_team = game['home_team']
                    home_roster = self.get_team_roster(home_team_id)
                    for player in home_roster:
                        props = self.generate_realistic_props_for_player(
                            player['player_id'],
                            player['name'],
                            game['home_team'],
                            player['position'],
                            game['game_id']
                        )
                        
                        if props:
                            # Add opponent info to each prop
                            for prop in props:
                                self._add_prop_metadata(prop, game)
                            
                            all_props[player['player_id']] = {
                                'player_info': {
                                    'name': player['name'],
                                    'team_name': game['home_team'],
                                    'position': player['position'],
                                    'game_id': game['game_id'],
                                    'status': 'UPCOMING'
                                },
                                'props': props
                            }
                
                # Rate limiting
                time.sleep(0.1)  # Reduced delay
            
            # Save to mlb_props.json with both games and props
            output_data = {
                'generated_at': datetime.now().isoformat(),
                'total_players': len(all_props),
                'games': games_data,
                'props': all_props
            }
            
            with open('mlb_props.json', 'w') as f:
                json.dump(output_data, f, indent=2)
            
            print(f"\n✅ Successfully generated realistic props for {len(all_props)} players")
            print(f"📊 Props saved to mlb_props.json")
            print(f"🎮 Games data included: {len(games_data)} games")
            
        except Exception as e:
            print(f"Error generating today's props: {e}")

    def _add_prop_metadata(self, prop, game):
        """Add metadata to a prop based on game information"""
        try:
            # Convert UTC game time to Eastern Time
            if game.get('game_datetime'):
                # Parse the UTC time string
                utc_time = datetime.fromisoformat(game['game_datetime'].replace('Z', '+00:00'))
                # Convert to Eastern Time
                eastern_tz = pytz.timezone('US/Eastern')
                eastern_time = utc_time.astimezone(eastern_tz)
                # Format as readable time
                formatted_time = eastern_time.strftime('%-I:%M %p ET')
                prop['game_time'] = formatted_time
            else:
                prop['game_time'] = 'TBD'
            
            # Add opponent info
            if hasattr(self, 'current_processing_team') and hasattr(self, 'current_processing_game'):
                if self.current_processing_team == self.current_processing_game['away_team']:
                    prop['opponent'] = f"@ {self.current_processing_game['home_team']}"
                else:
                    prop['opponent'] = f"vs {self.current_processing_game['away_team']}"
            
        except Exception as e:
            print(f"Error adding prop metadata: {e}")
            prop['game_time'] = 'TBD'
            prop['opponent'] = 'vs Opponent'

    def _convert_to_eastern_time(self, utc_time_str: str) -> str:
        """Convert a UTC time string to Eastern Time"""
        try:
            # Parse the UTC time string
            utc_time = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
            # Convert to Eastern Time
            eastern_tz = pytz.timezone('US/Eastern')
            eastern_time = utc_time.astimezone(eastern_tz)
            # Format as readable time
            formatted_time = eastern_time.strftime('%-I:%M %p ET')
            return formatted_time
        except Exception as e:
            print(f"Error converting UTC time to Eastern Time: {e}")
            return 'TBD'

if __name__ == "__main__":
    generator = RealisticPropGenerator()
    generator.generate_todays_props()