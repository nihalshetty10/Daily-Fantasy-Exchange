import requests
import json
import time
from datetime import datetime, timedelta
import pytz
import numpy as np
from ml.mlb_model import MLBModel
from backend.services.lineup_scraper import LineupScraper
import re

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
            # Get the major league roster (not minor league)
            url = f"{self.mlb_base_url}/teams/{team_id}/roster"
            params = {
                'rosterType': 'active',
                'fields': 'roster,person,position,stats'
            }
            
            response = requests.get(url, headers=self.headers)
            if response.status_code != 200:
                print(f"❌ Could not get roster for team {team_id} - API returned {response.status_code}")
                return []
            
            data = response.json()
            roster = []
            
            for person in data.get('roster', []):
                player = person['person']
                position = person.get('position', {}).get('abbreviation', '')
                
                # Only include relevant positions
                if position in ['P', 'C', '1B', '2B', 'SS', '3B', 'LF', 'CF', 'RF', 'DH']:
                    player_id = player['id']
                    player_name = player['fullName']
                    
                    roster.append({
                                        'player_id': player_id,
                        'name': player_name,
                        'position': position
                    })
            
            print(f"✅ Found {len(roster)} major league players for team {team_id}")
            return roster
        
        except Exception as e:
            print(f"❌ Error getting team roster for {team_id}: {e}")
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
            # Use the correct MLB team IDs that we know work
            mlb_team_mapping = {
                # Abbreviations
                'MIL': '158',  # Milwaukee Brewers
                'CHC': '112',  # Chicago Cubs
                'HOU': '117',  # Houston Astros
                'DET': '116',  # Detroit Tigers
                'TOR': '141',  # Toronto Blue Jays
                'PIT': '134',  # Pittsburgh Pirates
                'STL': '138',  # St. Louis Cardinals
                'MIA': '146',  # Miami Marlins
                'SEA': '136',  # Seattle Mariners
                'PHI': '143',  # Philadelphia Phillies
                'BAL': '110',  # Baltimore Orioles
                'BOS': '111',  # Boston Red Sox
                'CWS': '145',  # Chicago White Sox
                'ATL': '144',  # Atlanta Braves
                'TEX': '140',  # Texas Rangers
                'KC': '118',   # Kansas City Royals
                'LAD': '119',  # Los Angeles Dodgers
                'COL': '115',  # Colorado Rockies
                'CIN': '113',  # Cincinnati Reds
                'LAA': '108',  # Los Angeles Angels
                'SF': '137',   # San Francisco Giants
                'SD': '135',   # San Diego Padres
                'CLE': '114',  # Cleveland Guardians
                'ARI': '109',  # Arizona Diamondbacks
                'NYY': '147',  # New York Yankees
                'MIN': '142',  # Minnesota Twins
                'TB': '139',   # Tampa Bay Rays
                'NYM': '121',  # New York Mets
                'WSH': '120',  # Washington Nationals
                'OAK': '133',  # Oakland Athletics
                
                # Full names
                'Milwaukee Brewers': '158',
                'Chicago Cubs': '112',
                'Houston Astros': '117',
                'Detroit Tigers': '116',
                'Toronto Blue Jays': '141',
                'Pittsburgh Pirates': '134',
                'St. Louis Cardinals': '138',
                'Miami Marlins': '146',
                'Seattle Mariners': '136',
                'Philadelphia Phillies': '143',
                'Baltimore Orioles': '110',
                'Boston Red Sox': '111',
                'Chicago White Sox': '145',
                'Atlanta Braves': '144',
                'Texas Rangers': '140',
                'Kansas City Royals': '118',
                'Los Angeles Dodgers': '119',
                'Colorado Rockies': '115',
                'Cincinnati Reds': '113',
                'Los Angeles Angels': '108',
                'San Francisco Giants': '137',
                'San Diego Padres': '135',
                'Cleveland Guardians': '114',
                'Arizona Diamondbacks': '109',
                'New York Yankees': '147',
                'Minnesota Twins': '142',
                'Tampa Bay Rays': '139',
                'New York Mets': '121',
                'Washington Nationals': '120',
                'Oakland Athletics': '133',
            }
            
            # Try to find the team ID
            if team_name in mlb_team_mapping:
                print(f"✅ Found team ID for {team_name}: {mlb_team_mapping[team_name]}")
                return mlb_team_mapping[team_name]
            
            print(f"❌ Could not find team ID for {team_name}")
            print(f"Available MLB teams: {list(mlb_team_mapping.keys())}")
            return None
        
        except Exception as e:
            print(f"Error getting team ID for {team_name}: {e}")
            return None

    def resolve_pitcher_id_directly(self, pitcher_name: str, team_name: str) -> tuple:
        """Directly resolve pitcher ID from team roster by name matching, with MLB people search fallback"""
        try:
            # Get team roster and search for the pitcher by name
            team_id = self.get_team_id_from_name(team_name)
            if not team_id:
                print(f"       ❌ No team ID found for {team_name}")
                return '', ''
            
            roster_url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster"
            response = requests.get(roster_url, timeout=10)
            
            if response.status_code != 200:
                print(f"       ❌ Failed to get roster for {team_name}")
                return '', ''
            
            roster_data = response.json()
            roster = roster_data.get('roster', [])
            
            if not roster:
                print(f"       ❌ Empty roster for {team_name}")
                return '', ''
            
            # Search for the pitcher in the roster
            for player in roster:
                player_name = player.get('person', {}).get('fullName', '')
                position = player.get('position', {}).get('abbreviation', '')
                
                # Check if this is a pitcher and if the name matches
                if position in ['P', 'SP', 'RP'] and player_name.lower() == pitcher_name.lower():
                    player_id = player.get('person', {}).get('id')
                    if player_id:
                        print(f"       🎯 Found pitcher {pitcher_name} -> ID: {player_id} on {team_name}")
                        return str(player_id), 'P'
            
            # If no exact match, try fuzzy matching on last name
            for player in roster:
                player_name = player.get('person', {}).get('fullName', '')
                position = player.get('position', {}).get('abbreviation', '')
                if position in ['P', 'SP', 'RP']:
                    player_last = player_name.split()[-1].lower() if player_name else ''
                    pitcher_last = pitcher_name.split()[-1].lower() if pitcher_name else ''
                    if player_last == pitcher_last:
                        player_id = player.get('person', {}).get('id')
                        if player_id:
                            print(f"       🎯 Found pitcher {pitcher_name} (fuzzy match) -> ID: {player_id} on {team_name}")
                            return str(player_id), 'P'
            
            # Final fallback: use MLB people search (ignore team) and pick best exact name match
            try:
                q = requests.utils.quote(pitcher_name)
                search_url = f"https://statsapi.mlb.com/api/v1/people/search?q={q}&sportIds=1"
                r = requests.get(search_url, timeout=10)
                if r.status_code == 200:
                    people = r.json().get('people', [])
                    for person in people:
                        full = (person.get('fullName') or '').strip()
                        if full.lower() == pitcher_name.lower():
                            pid = person.get('id')
                            if pid:
                                print(f"       🎯 People search matched {pitcher_name} -> ID: {pid}")
                                return str(pid), 'P'
            except Exception:
                pass
            
            print(f"       ❌ No pitcher found for {pitcher_name} on {team_name}")
            return '', ''
        
        except Exception as e:
            print(f"       ⚠️ Error in direct pitcher lookup: {e}")
            return '', ''

    def resolve_player_id_and_position(self, team_name: str, scraped_name: str) -> tuple:
        """Resolve MLB player ID and position using team roster by matching name heuristics.
        Returns (player_id or '', position or '').
        """
        try:
            if not scraped_name:
                return '', ''

            # Always use roster-based matching; do NOT assume pitcher based on name substrings
            team_id = self.get_team_id_from_name(team_name)
            if not team_id:
                print(f"❌ No team ID found for {team_name}")
                return '', ''
            
            roster_url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster"
            response = requests.get(roster_url, timeout=10)
            
            if response.status_code != 200:
                print(f"❌ Failed to get roster for {team_name}")
                return '', ''
            
            roster_data = response.json()
            roster = roster_data.get('roster', [])
            
            if not roster:
                print(f"❌ Empty roster for {team_name}")
                return '', ''
            
            print(f"✅ Found {len(roster)} major league players for team {team_id}")
            
            # Normalize helper
            def norm(s: str) -> str:
                return (s or '').strip().lower()
            target = norm(scraped_name)
            
            # 1) Exact full-name match
            for player in roster:
                player_name = player.get('person', {}).get('fullName', '')
                if norm(player_name) == target:
                    player_id = player.get('person', {}).get('id')
                    position = player.get('position', {}).get('abbreviation', '')
                    print(f"✅ Exact match found: {player_name} -> ID: {player_id}")
                    return str(player_id), position
            
            # 2) Last name + first initial match
            scraped_parts = scraped_name.split()
            if len(scraped_parts) >= 2:
                last_name = scraped_parts[-1]
                first_initial = scraped_parts[0][0] if scraped_parts[0] else ''
                for player in roster:
                    player_name = player.get('person', {}).get('fullName', '')
                    player_parts = player_name.split()
                    if len(player_parts) >= 2:
                        if (player_parts[-1].lower() == last_name.lower() and 
                            player_parts[0][0].lower() == first_initial.lower()):
                            player_id = player.get('person', {}).get('id')
                            position = player.get('position', {}).get('abbreviation', '')
                            print(f"✅ Last+initial match found: {player_name} -> ID: {player_id}")
                            return str(player_id), position
            
            # 3) Fuzzy last-name containment
            for player in roster:
                player_name = player.get('person', {}).get('fullName', '')
                player_parts = player_name.split()
                if len(player_parts) >= 2:
                    if player_parts[-1].lower() in target or target in player_parts[-1].lower():
                        player_id = player.get('person', {}).get('id')
                        position = player.get('position', {}).get('abbreviation', '')
                        print(f"✅ Fuzzy last name match found: {player_name} -> ID: {player_id}")
                        return str(player_id), position
            
            # 4) If nothing matched, do NOT default to pitcher search. Return empty and skip this player.
            print(f"❌ No match found for '{scraped_name}' in {team_name} roster")
            return '', ''
            
        except Exception as e:
            print(f"❌ Error resolving player ID for '{scraped_name}' in {team_name}: {e}")
            return '', ''
    
    def generate_todays_props(self):
        """Generate realistic props for today's games"""
        try:
            print("🚀 Starting realistic prop generation...")
            
            lineup_scraper = LineupScraper()
            official_lineups, official_times = lineup_scraper.get_lineups()
            lineup_cards = []
            try:
                # Use combined cards: Rotowire hitters + MLB.com pitchers
                lineup_cards = lineup_scraper.get_combined_cards()
            except Exception:
                lineup_cards = []

            def find_in(mapping: dict, team_name: str):
                if not team_name:
                    return None
                # Try full name
                v = mapping.get(team_name)
                if v:
                    return v
                # Try nickname (last token)
                nickname = team_name.split()[-1]
                v = mapping.get(nickname)
                if v:
                    return v
                # Try upper-case nickname (sometimes times map uses abbreviations; keep as fallback)
                v = mapping.get(nickname.upper())
                if v:
                    return v
                return None
            
            all_props = {}
            games_data = []

            if lineup_cards:
                print(f"Found {len(lineup_cards)} lineup cards (supports doubleheaders)")
                for idx, card in enumerate(lineup_cards):
                    away_team = card.get('away_label') or ''
                    home_team = card.get('home_label') or ''
                    game_time_et = card.get('time_et') or find_in(official_times, home_team) or find_in(official_times, away_team)
                    if not away_team or not home_team or not game_time_et:
                        continue
                    synthetic_game_id = f"{away_team}@{home_team}|{game_time_et}|{idx}"
                    game_ctx = {
                        'game_id': synthetic_game_id,
                        'game_date': datetime.now().isoformat(),
                        'game_time_et': game_time_et,
                        'game_datetime': None,
                        'status': 'UPCOMING',
                        'home_team': {'id': 0, 'name': home_team, 'abbreviation': home_team[:3].upper()},
                        'away_team': {'id': 0, 'name': away_team, 'abbreviation': away_team[:3].upper()}
                    }
                    games_data.append(game_ctx)
                    # Away hitters
                    self.current_processing_game = {
                        'away_team': away_team,
                        'home_team': home_team,
                        'game_id': synthetic_game_id,
                        'game_datetime': None,
                        'game_time_et': game_time_et,
                    }
                    self.current_processing_team = away_team
                    for player_name in card.get('away_hitters', []):
                        player_id, position = self.resolve_player_id_and_position(away_team, player_name)
                        
                        # Only try to generate props if we have a valid player ID
                        if player_id:
                            print(f"🎯 Generating props for {player_name} (ID: {player_id}) - {away_team}")
                            props = self.analyzer.generate_realistic_props(player_id, player_name, away_team, position, synthetic_game_id)
                            
                            if props:
                                for prop in props:
                                    self._add_prop_metadata(prop, self.current_processing_game)
                                all_props[str(player_id) + '|' + synthetic_game_id + '|A'] = {
                                    'player_info': {
                                        'name': player_name,
                                        'team_name': away_team,
                                        'position': position,
                                        'game_id': synthetic_game_id,
                                        'status': 'UPCOMING'
                                    },
                                    'props': props
                                }
                        else:
                            print(f"⚠️ Skipping {player_name} - no valid MLB player ID found")
                            continue
                    # Home hitters
                    self.current_processing_team = home_team
                    for player_name in card.get('home_hitters', []):
                        player_id, position = self.resolve_player_id_and_position(home_team, player_name)
                        
                        # Only try to generate props if we have a valid player ID
                        if player_id:
                            print(f"🎯 Generating props for {player_name} (ID: {player_id}) - {home_team}")
                            props = self.analyzer.generate_realistic_props(player_id, player_name, home_team, position, synthetic_game_id)
                            
                            if props:
                                for prop in props:
                                    self._add_prop_metadata(prop, self.current_processing_game)
                                all_props[str(player_id) + '|' + synthetic_game_id + '|H'] = {
                                    'player_info': {
                                        'name': player_name,
                                        'team_name': home_team,
                                        'position': position,
                                        'game_id': synthetic_game_id,
                                        'status': 'UPCOMING'
                                    },
                                    'props': props
                                }
                        else:
                            print(f"⚠️ Skipping {player_name} - no valid MLB player ID found")
                            continue
                            
                    # Away pitcher
                    if card.get('away_pitcher'):
                        pitcher_name = card.get('away_pitcher')
                        player_id, position = self.resolve_player_id_and_position(away_team, pitcher_name)
                        
                        if player_id:
                            print(f"🎯 Generating props for pitcher {pitcher_name} (ID: {player_id}) - {away_team}")
                            props = self.analyzer.generate_realistic_props(player_id, pitcher_name, away_team, 'P', synthetic_game_id)
                            
                            if props:
                                for prop in props:
                                    self._add_prop_metadata(prop, self.current_processing_game)
                                all_props[str(player_id) + '|' + synthetic_game_id + '|AP'] = {
                                    'player_info': {
                                        'name': pitcher_name,
                                        'team_name': away_team,
                                        'position': 'P',
                                        'game_id': synthetic_game_id,
                                        'status': 'UPCOMING'
                                    },
                                    'props': props
                                }
                        else:
                            print(f"⚠️ Skipping pitcher {pitcher_name} - no valid MLB player ID found")
                    
                    # Home pitcher
                    if card.get('home_pitcher'):
                        pitcher_name = card.get('home_pitcher')
                        player_id, position = self.resolve_player_id_and_position(home_team, pitcher_name)
                        
                        if player_id:
                            print(f"🎯 Generating props for pitcher {pitcher_name} (ID: {player_id}) - {home_team}")
                            props = self.analyzer.generate_realistic_props(player_id, pitcher_name, home_team, 'P', synthetic_game_id)
                            
                            if props:
                                for prop in props:
                                    self._add_prop_metadata(prop, self.current_processing_game)
                                all_props[str(player_id) + '|' + synthetic_game_id + '|HP'] = {
                                    'player_info': {
                                        'name': pitcher_name,
                                        'team_name': home_team,
                                        'position': 'P',
                                        'game_id': synthetic_game_id,
                                        'status': 'UPCOMING'
                                    },
                                    'props': props
                                }
                        else:
                            print(f"⚠️ Skipping pitcher {pitcher_name} - no valid MLB player ID found")
            else:
                # Fallback to schedule-based generation
                games = self.get_todays_games()
                if not games:
                    print("No games found for today")
                    return
                print(f"Found {len(games)} games for today")
                for game in games:
                    print(f"\nProcessing game: {game['away_team']} @ {game['home_team']}")
                    game_time_et = find_in(official_times, game['home_team']) or find_in(official_times, game['away_team'])
                    if not game_time_et:
                        print(f"⏰ Skipping game {game['away_team']} @ {game['home_team']} - No Rotowire ET time")
                        continue
                    self.current_processing_game = game
                    games_data.append({
                        'game_id': game['game_id'],
                        'game_date': datetime.now().isoformat(),
                        'game_time_et': game_time_et,
                        'game_datetime': game['game_time'],
                        'status': game['status'],
                        'home_team': {'id': 0, 'name': game['home_team'], 'abbreviation': game['home_team'][:3].upper()},
                        'away_team': {'id': 0, 'name': game['away_team'], 'abbreviation': game['away_team'][:3].upper()}
                    })
                    for side, team_name in [('away', game['away_team']), ('home', game['home_team'])]:
                        self.current_processing_team = team_name
                        starters = find_in(official_lineups, team_name) or []
                        for player in starters:
                            if isinstance(player, dict):
                                player_name = player['name']
                                player_id = player.get('player_id') or ''
                                position = player.get('position') or ''
                            else:
                                player_name = player
                                player_id, position = self.resolve_player_id_and_position(team_name, player_name)
                            props = self.analyzer.generate_realistic_props(player_id or player_name, player_name, team_name, position, game['game_id'])
                            if props:
                                for prop in props:
                                    self._add_prop_metadata(prop, game)
                                all_props[str(player_id or player_name)] = {
                                    'player_info': {
                                        'name': player_name,
                                        'team_name': team_name,
                                        'position': position,
                                        'game_id': game['game_id'],
                                        'status': 'UPCOMING'
                                    },
                                    'props': props
                                }
            
            # Save the props
            output_data = {
                'games': games_data,
                'props': all_props,
                'generated_at': datetime.now().isoformat(),
                'total_players': len(all_props),
                'total_games': len(games_data)
            }
            
            with open('mlb_props.json', 'w') as f:
                json.dump(output_data, f, indent=2)
            
            print(f"\n🎉 Successfully generated props for {len(all_props)} players across {len(games_data)} games")
            print(f"📁 Props saved to mlb_props.json")
        
        except Exception as e:
            print(f"Error generating props: {e}")
            import traceback
            traceback.print_exc()

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
            elif game.get('game_time_et'):
                # Fallback: already-formatted ET time from scraper
                prop['game_time'] = game.get('game_time_et')
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

    def get_team_lineup(self, team_id: str, game_id: str) -> list:
        """Get actual lineup for a team in a specific game - ONLY players in the lineup"""
        try:
            print(f"🔍 Attempting to get lineup for team {team_id} in game {game_id}")
            
            # Try to get lineup from MLB API
            url = f"{self.mlb_base_url}/game/{game_id}/feed/live"
            
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.status_code != 200:
                print(f"❌ Could not get lineup for team {team_id} - API returned {response.status_code}")
                return []
            
            data = response.json()
            lineup = []
            
            # Parse lineup from live feed data
            if 'liveData' in data and 'boxscore' in data['liveData']:
                boxscore = data['liveData']['boxscore']
                
                # Check both home and away teams
                for team_type in ['home', 'away']:
                    if team_type in boxscore and 'battingOrder' in boxscore[team_type]:
                        batting_order = boxscore[team_type]['battingOrder']
                        
                        # Get team info
                        team_info = boxscore[team_type].get('team', {})
                        if str(team_info.get('id')) == str(team_id):
                            # This is our team, get the lineup
                            print(f"✅ Found batting order for team {team_id}: {len(batting_order)} players")
                            
                            for player_id in batting_order:
                                # Get player details
                                player_info = self.get_player_info(player_id)
                                if player_info:
                                    lineup.append({
                                        'player_id': player_id,
                                        'name': player_info['name'],
                                        'position': player_info['position']
                                    })
                                    print(f"  - {player_info['name']} ({player_info['position']})")
                            break
                
                # Also check for pitchers in the lineup
                if 'pitchers' in boxscore:
                    for team_type in ['home', 'away']:
                        if team_type in boxscore and 'pitchers' in boxscore[team_type]:
                            team_info = boxscore[team_type].get('team', {})
                            if str(team_info.get('id')) == str(team_id):
                                pitchers = boxscore[team_type]['pitchers']
                                print(f"✅ Found {len(pitchers)} pitchers for team {team_id}")
                                
                                for player_id in pitchers:
                                    # Check if this pitcher is already in the lineup
                                    if not any(p['player_id'] == player_id for p in lineup):
                                        player_info = self.get_player_info(player_id)
                                        if player_info:
                                            lineup.append({
                                                'player_id': player_id,
                                                'name': player_info['name'],
                                                'position': player_info['position']
                                            })
                                            print(f"  - {player_info['name']} ({player_info['position']}) - Pitcher")
                                break
            
            if not lineup:
                print(f"⚠️ No lineup found for team {team_id} - this team will be skipped")
                return []
            
            print(f"✅ Successfully found {len(lineup)} players in lineup for team {team_id}")
            return lineup
            
        except Exception as e:
            print(f"❌ Error getting lineup for team {team_id}: {e}")
            print(f"⚠️ Team {team_id} will be skipped due to lineup retrieval error")
            return []
    
    def get_player_info(self, player_id: str) -> dict:
        """Get player information from MLB API"""
        try:
            url = f"{self.mlb_base_url}/people/{player_id}"
            
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.status_code != 200:
                return None
            
            data = response.json()
            person = data.get('people', [{}])[0]
            
            return {
                'name': person.get('fullName', 'Unknown'),
                'position': person.get('primaryPosition', {}).get('abbreviation', ''),
                'id': player_id
            }
            
        except Exception as e:
            print(f"Error getting player info for {player_id}: {e}")
            return None

if __name__ == "__main__":
    generator = RealisticPropGenerator()
    generator.generate_todays_props()