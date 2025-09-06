import requests
import json
import logging
from datetime import datetime, timedelta
import re
from bs4 import BeautifulSoup
import numpy as np
import random

class NFLModel:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        
        # Team abbreviation mapping (city names)
        self.TEAM_ABBREVIATIONS = {
            'KC': 'Kansas City', 'LAC': 'Los Angeles', 'TB': 'Tampa Bay', 'ATL': 'Atlanta',
            'BUF': 'Buffalo', 'MIA': 'Miami', 'NE': 'New England', 'NYJ': 'New York',
            'BAL': 'Baltimore', 'CIN': 'Cincinnati', 'CLE': 'Cleveland', 'PIT': 'Pittsburgh',
            'HOU': 'Houston', 'IND': 'Indianapolis', 'JAX': 'Jacksonville', 'TEN': 'Tennessee',
            'DEN': 'Denver', 'LV': 'Las Vegas', 'DAL': 'Dallas', 'NYG': 'New York',
            'PHI': 'Philadelphia', 'WAS': 'Washington', 'CHI': 'Chicago', 'DET': 'Detroit',
            'GB': 'Green Bay', 'MIN': 'Minnesota', 'NO': 'New Orleans', 'CAR': 'Carolina',
            'ARI': 'Arizona', 'LAR': 'Los Angeles', 'SF': 'San Francisco', 'SEA': 'Seattle'
        }
        
        # Weather impact multipliers
        self.WEATHER_IMPACTS = {
            'snow': {'passing_yards': 0.85, 'rushing_yards': 1.1, 'receiving_yards': 0.9},
            'rain': {'passing_yards': 0.9, 'rushing_yards': 1.05, 'receiving_yards': 0.95},
            'wind': {'passing_yards': 0.8, 'rushing_yards': 1.0, 'receiving_yards': 0.85},
            'cold': {'passing_yards': 0.95, 'rushing_yards': 1.0, 'receiving_yards': 0.95},
            'dome': {'passing_yards': 1.0, 'rushing_yards': 1.0, 'receiving_yards': 1.0}
        }
        
        # Injury impact multipliers
        self.INJURY_IMPACTS = {
            'questionable': 0.9,
            'doubtful': 0.7,
            'out': 0.0,
            'probable': 0.95
        }

    def generate_todays_props(self):
        """Generate today's NFL props using lineup scraper"""
        try:
            self.logger.info("🏈 Starting NFL prop generation...")
            
            # Get NFL players from lineup scraper
            from backend.services.lineup_scraper import LineupScraper
            scraper = LineupScraper()
            nfl_players = scraper.get_nfl_players_today()
            
            if not nfl_players:
                self.logger.warning("No NFL players found for today")
                return {
                    'props': [],
                    'total_players': 0,
                    'total_games': 0,
                    'generated_at': datetime.now().isoformat()
                }
            
            # If we have players, assume there are games (lineup scraper already filters for today)
            self.logger.info(f"Found {len(nfl_players)} NFL players - assuming games exist")
            all_props = []
            
            for player in nfl_players:
                player_name = player['name']
                position = player['position']
                team_raw = player.get('team', 'Unknown')
                injury = player.get('injury', '')
                
                # Use team directly from lineup scraper (already clean)
                team = team_raw
                
                self.logger.info(f"Generating props for {player_name} ({position}) - {team}")
                
                # Generate props for this player
                props = self._generate_player_props(
                    player_name=player_name,
                    position=position,
                    team=team,
                    injury=injury,
                    game_id="nfl_friday_sept5_1"  # Friday Sept 5th game
                )
                
                if props:
                    all_props.extend(props)
                    self.logger.info(f"  Generated {len(props)} props")
                else:
                    self.logger.warning(f"  No props generated for {player_name}")
            
            self.logger.info(f"Total NFL props generated: {len(all_props)}")
            
            return {
                'props': all_props,
                'total_players': len(nfl_players),
                'total_games': 1 if nfl_players else 0,
                'generated_at': datetime.now().isoformat()
            }
            except Exception as e:
            self.logger.error(f"Error generating NFL props: {e}")
            return {
                'props': [],
                'total_players': 0,
                'total_games': 0,
                'generated_at': datetime.now().isoformat()
            }

    def _generate_player_props(self, player_name, position, team, injury='', game_id=''):
        """Generate props for a single NFL player"""
        try:
            # Get player stats
            stats = self._get_nfl_player_stats(player_name, position)
            if not stats:
                self.logger.warning(f"No stats found for {player_name}")
                return []

            # Apply injury impact
            injury_multiplier = self.INJURY_IMPACTS.get(injury.lower(), 1.0) if injury else 1.0
            
            props = []
            
            # Generate props based on position
            if position == 'QB':
                props.extend(self._generate_qb_props(player_name, stats, injury_multiplier, game_id, team))
            elif position == 'RB':
                props.extend(self._generate_rb_props(player_name, stats, injury_multiplier, game_id, team))
            elif position in ['WR', 'TE']:
                props.extend(self._generate_wr_te_props(player_name, stats, injury_multiplier, game_id, team))
            
            return props
            
        except Exception as e:
            self.logger.error(f"Error generating props for {player_name}: {e}")
            return []
    
    def _generate_qb_props(self, player_name, stats, injury_multiplier, game_id='', team='Unknown'):
        """Generate QB props (4 medium, 1 easy, 1 hard)"""
        props = []
        
        # Easy prop (75-80% implied prob)
        easy_prob = random.uniform(0.75, 0.80)
        easy_percentile = (1 - easy_prob) * 100  # Convert to percentile
        
        # Medium props (40-60% implied prob) 
        medium_probs = [random.uniform(0.40, 0.60) for _ in range(4)]
        medium_percentiles = [(1 - prob) * 100 for prob in medium_probs]
        
        # Hard prop (10-25% implied prob)
        hard_prob = random.uniform(0.10, 0.25)
        hard_percentile = (1 - hard_prob) * 100
        
        # Generate passing yards props
        if 'passing_yards' in stats and stats['passing_yards']:
            passing_data = stats['passing_yards']
            if len(passing_data) >= 8:  # Need at least 8 games
                # Easy passing yards
                easy_line = np.percentile(passing_data, easy_percentile)
                props.append({
                    'player_name': player_name,
                    'prop_type': 'passing_yards',
                    'line': round(easy_line * injury_multiplier),
                    'difficulty': 'easy',
                    'implied_probability': easy_prob,
                    'game_id': game_id,
                    'position': 'QB',
                    'team': team
                })
                
                # Medium passing yards
                for i, percentile in enumerate(medium_percentiles[:2]):
                    line = np.percentile(passing_data, percentile)
                    props.append({
                        'player_name': player_name,
                        'prop_type': 'passing_yards',
                        'line': round(line * injury_multiplier),
                        'difficulty': 'medium',
                        'implied_probability': medium_probs[i]
                    })
                
                # Hard passing yards
                hard_line = np.percentile(passing_data, hard_percentile)
                props.append({
                    'player_name': player_name,
                    'prop_type': 'passing_yards',
                    'line': round(hard_line * injury_multiplier),
                    'difficulty': 'hard',
                    'implied_probability': hard_prob,
                    'game_id': game_id,
                    'game_id': game_id
                })
        
        # Generate passing TDs props
        if 'passing_tds' in stats:
            td_data = stats['passing_tds']
            if len(td_data) >= 6:
                # Medium passing TDs
                for i, percentile in enumerate(medium_percentiles[2:4]):
                    line = np.percentile(td_data, percentile)
                    props.append({
                        'player_name': player_name,
                        'prop_type': 'passing_tds',
                        'line': round(line * injury_multiplier),
                        'difficulty': 'medium',
                        'implied_probability': medium_probs[i+2]
                    })
        
        return props

    def _generate_rb_props(self, player_name, stats, injury_multiplier, game_id='', team='Unknown'):
        """Generate RB props (3 medium, 1 easy, 1 hard)"""
        props = []
        
        # Easy prop (75-80% implied prob)
        easy_prob = random.uniform(0.75, 0.80)
        easy_percentile = (1 - easy_prob) * 100
        
        # Medium props (40-60% implied prob)
        medium_probs = [random.uniform(0.40, 0.60) for _ in range(3)]
        medium_percentiles = [(1 - prob) * 100 for prob in medium_probs]
        
        # Hard prop (10-25% implied prob)
        hard_prob = random.uniform(0.10, 0.25)
        hard_percentile = (1 - hard_prob) * 100
        
        # Generate rushing yards props
        if 'rushing_yards' in stats:
            rushing_data = stats['rushing_yards']
            if len(rushing_data) >= 6:
                # Easy rushing yards
                easy_line = np.percentile(rushing_data, easy_percentile)
                props.append({
                    'player_name': player_name,
                    'prop_type': 'rushing_yards',
                    'line': round(easy_line * injury_multiplier),
                    'difficulty': 'easy',
                    'implied_probability': easy_prob,
                    'game_id': game_id
                })
                
                # Medium rushing yards
                for i, percentile in enumerate(medium_percentiles[:2]):
                    line = np.percentile(rushing_data, percentile)
                    props.append({
                        'player_name': player_name,
                        'prop_type': 'rushing_yards',
                        'line': round(line * injury_multiplier),
                        'difficulty': 'medium',
                        'implied_probability': medium_probs[i]
                    })
                
                # Hard rushing yards
                hard_line = np.percentile(rushing_data, hard_percentile)
                props.append({
                    'player_name': player_name,
                    'prop_type': 'rushing_yards',
                    'line': round(hard_line * injury_multiplier),
                    'difficulty': 'hard',
                    'implied_probability': hard_prob,
                    'game_id': game_id,
                    'game_id': game_id
                })
        
        # Generate rushing TDs props
        if 'rushing_tds' in stats:
            td_data = stats['rushing_tds']
            if len(td_data) >= 6:
                # Medium rushing TDs
                line = np.percentile(td_data, medium_percentiles[2])
                props.append({
                    'player_name': player_name,
                    'prop_type': 'rushing_tds',
                    'line': round(line * injury_multiplier),
                    'difficulty': 'medium',
                    'implied_probability': medium_probs[2],
                    'game_id': game_id
                })
        
                return props
            
    def _generate_wr_te_props(self, player_name, stats, injury_multiplier, game_id='', team='Unknown'):
        """Generate WR/TE props (2 medium, 1 easy, 1 hard)"""
        props = []
        
        # Easy prop (75-80% implied prob)
        easy_prob = random.uniform(0.75, 0.80)
        easy_percentile = (1 - easy_prob) * 100
        
        # Medium props (40-60% implied prob)
        medium_probs = [random.uniform(0.40, 0.60) for _ in range(2)]
        medium_percentiles = [(1 - prob) * 100 for prob in medium_probs]
        
        # Hard prop (10-25% implied prob)
        hard_prob = random.uniform(0.10, 0.25)
        hard_percentile = (1 - hard_prob) * 100
        
        # Generate receiving yards props
        if 'receiving_yards' in stats:
            receiving_data = stats['receiving_yards']
            if len(receiving_data) >= 6:
                # Easy receiving yards
                easy_line = np.percentile(receiving_data, easy_percentile)
                props.append({
                    'player_name': player_name,
                    'prop_type': 'receiving_yards',
                    'line': round(easy_line * injury_multiplier),
                    'difficulty': 'easy',
                    'implied_probability': easy_prob,
                    'game_id': game_id
                })
                
                # Medium receiving yards
                for i, percentile in enumerate(medium_percentiles):
                    line = np.percentile(receiving_data, percentile)
                    props.append({
                        'player_name': player_name,
                        'prop_type': 'receiving_yards',
                        'line': round(line * injury_multiplier),
                        'difficulty': 'medium',
                        'implied_probability': medium_probs[i]
                    })
                
                # Hard receiving yards
                hard_line = np.percentile(receiving_data, hard_percentile)
                props.append({
                    'player_name': player_name,
                    'prop_type': 'receiving_yards',
                    'line': round(hard_line * injury_multiplier),
                    'difficulty': 'hard',
                    'implied_probability': hard_prob,
                    'game_id': game_id,
                    'game_id': game_id
                })
        
            return props
    
    def _get_nfl_player_stats(self, player_name, position):
        """Get NFL player stats from RapidAPI NFL API"""
        try:
            import requests
            
            # RapidAPI NFL Live Statistics API
            api_url = "https://tank01-nfl-live-in-game-real-time-statistics-nfl.p.rapidapi.com"
            
            # First, get player list to find player ID
            player_id = self._get_player_id_from_api(player_name)
            if not player_id:
                self.logger.warning(f"Player {player_name} not found in NFL API")
                return {}
            
            # Get player's game stats
            stats_url = f"{api_url}/getNFLGamesForPlayer"
            params = {
                'playerID': player_id,
                'fantasyPoints': 'true',
                'passYards': '.04',
                'passTD': '4',
                'rushYards': '.1',
                'rushTD': '6',
                'receivingYards': '.1',
                'receivingTD': '6',
                'targets': '0',
                'carries': '.2'
            }
            
            headers = {
                'x-rapidapi-host': 'tank01-nfl-live-in-game-real-time-statistics-nfl.p.rapidapi.com',
                'x-rapidapi-key': '0af1c6c382msh67676e1ee73f00ap13d06bjsnccac7c258767'
            }
            
            response = requests.get(stats_url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_rapidapi_stats(data, position)
                        else:
                self.logger.warning(f"API request failed for {player_name}: {response.status_code}")
                return {}
            
        except Exception as e:
            self.logger.error(f"Error getting NFL stats for {player_name}: {e}")
            return {}

    def _get_player_id_from_api(self, player_name):
        """Search for player ID by trying different ID ranges and checking names"""
        try:
            import requests
            
            api_url = "https://tank01-nfl-live-in-game-real-time-statistics-nfl.p.rapidapi.com"
            player_games_url = f"{api_url}/getNFLGamesForPlayer"
            
            headers = {
                'x-rapidapi-host': 'tank01-nfl-live-in-game-real-time-statistics-nfl.p.rapidapi.com',
                'x-rapidapi-key': '0af1c6c382msh67676e1ee73f00ap13d06bjsnccac7c258767'
            }
            
            # Try different ID ranges to find the player
            # Start with a reasonable range around known working IDs
            base_ids = [3121422, 4426348, 2576980, 4426875, 2565969, 2573079, 2578570, 3124084, 15835, 3975763, 3821683]
            
            # Add some range around these IDs
            test_ids = []
            for base_id in base_ids:
                # Try IDs around the base ID
                for offset in range(-10, 11):
                    test_ids.append(str(base_id + offset))
            
            # Remove duplicates and limit to reasonable number
            test_ids = list(set(test_ids))[:100]  # Limit to 100 IDs to test
            
            player_name_lower = player_name.lower()
            
            for player_id in test_ids:
                try:
                    params = {
                        'playerID': player_id,
                        'fantasyPoints': 'true'
                    }
                    
                    response = requests.get(player_games_url, params=params, headers=headers, timeout=3)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if 'body' in data and data['body']:
                            # Get player name from first game
                            first_game = list(data['body'].values())[0]
                            api_player_name = first_game.get('longName', '').lower()
                            
                            # Check if this matches our search
                            if (player_name_lower in api_player_name or 
                                api_player_name in player_name_lower or
                                any(part in api_player_name for part in player_name_lower.split()) or
                                any(part in player_name_lower for part in api_player_name.split())):
                                self.logger.info(f"Found player {api_player_name} with ID {player_id}")
                                return player_id
            
        except Exception as e:
                    # Continue to next ID if this one fails
                    continue
            
            self.logger.warning(f"Player {player_name} not found in API search")
            return None
            
        except Exception as e:
            self.logger.error(f"Error searching for player ID for {player_name}: {e}")
            return None
    
    def _parse_rapidapi_stats(self, data, position):
        """Parse RapidAPI response to extract player stats"""
        try:
            stats = {}
            games_dict = data.get('body', {})
            
            if not games_dict:
            return {}

            # Convert dict to list and get last 10 games
            games_list = list(games_dict.values())
            recent_games = games_list[:10]
            
            if position == 'QB':
                # Look for passing stats in each game
                passing_yards = []
                passing_tds = []
                rushing_yards = []
                completions = []
                
                for game in recent_games:
                    # Check for passing stats
                    if 'Passing' in game:
                        passing_yards.append(int(game['Passing'].get('passYards', 0)))
                        passing_tds.append(int(game['Passing'].get('passTD', 0)))
                        completions.append(int(game['Passing'].get('completions', 0)))
                    else:
                        passing_yards.append(0)
                        passing_tds.append(0)
                        completions.append(0)
                    
                    # Check for rushing stats
                    if 'Rushing' in game:
                        rushing_yards.append(int(game['Rushing'].get('rushYards', 0)))
                    else:
                        rushing_yards.append(0)
                
                stats['passing_yards'] = passing_yards
                stats['passing_tds'] = passing_tds
                stats['rushing_yards'] = rushing_yards
                stats['completions'] = completions
                
            elif position == 'RB':
                # Look for rushing and receiving stats
                rushing_yards = []
                rushing_tds = []
                receiving_yards = []
                catches = []
                
                for game in recent_games:
                    # Check for rushing stats
                    if 'Rushing' in game:
                        rushing_yards.append(int(game['Rushing'].get('rushYards', 0)))
                        rushing_tds.append(int(game['Rushing'].get('rushTD', 0)))
                    else:
                        rushing_yards.append(0)
                        rushing_tds.append(0)
                    
                    # Check for receiving stats
                    if 'Receiving' in game:
                        receiving_yards.append(int(game['Receiving'].get('recYds', 0)))
                        catches.append(int(game['Receiving'].get('receptions', 0)))
            else:
                        receiving_yards.append(0)
                        catches.append(0)
                
                stats['rushing_yards'] = rushing_yards
                stats['rushing_tds'] = rushing_tds
                stats['receiving_yards'] = receiving_yards
                stats['catches'] = catches
                
            elif position in ['WR', 'TE']:
                # Look for receiving stats
                receiving_yards = []
                receiving_tds = []
                catches = []
                
                for game in recent_games:
                    if 'Receiving' in game:
                        receiving_yards.append(int(game['Receiving'].get('recYds', 0)))
                        receiving_tds.append(int(game['Receiving'].get('recTD', 0)))
                        catches.append(int(game['Receiving'].get('receptions', 0)))
            else:
                        receiving_yards.append(0)
                        receiving_tds.append(0)
                        catches.append(0)
                
                stats['receiving_yards'] = receiving_yards
                stats['receiving_tds'] = receiving_tds
                stats['catches'] = catches
            
            # Filter out games with no stats (keep 0 values as they're valid)
            for stat_type, values in stats.items():
                stats[stat_type] = [v for v in values if v is not None]
            
            self.logger.info(f"Found {len(recent_games)} games with stats for position {position}")
            return stats
            
        except Exception as e:
            self.logger.error(f"Error parsing RapidAPI stats: {e}")
            return {}
    
    
    def _get_player_game_logs(self, player_id, position):
        """Get player's recent game logs from ESPN API"""
        try:
            import requests
            
            # Get player's recent games
            api_url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/athletes/{player_id}/gamelog"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(api_url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                games = data.get('games', [])
                
                if not games:
                    return {}
                
                # Get last 10 games
                recent_games = games[:10]
                
                stats = {}
                
                if position == 'QB':
                    stats['passing_yards'] = [game.get('stats', {}).get('passingYards', 0) for game in recent_games]
                    stats['passing_tds'] = [game.get('stats', {}).get('passingTouchdowns', 0) for game in recent_games]
                    stats['rushing_yards'] = [game.get('stats', {}).get('rushingYards', 0) for game in recent_games]
                    stats['completions'] = [game.get('stats', {}).get('completions', 0) for game in recent_games]
                elif position == 'RB':
                    stats['rushing_yards'] = [game.get('stats', {}).get('rushingYards', 0) for game in recent_games]
                    stats['rushing_tds'] = [game.get('stats', {}).get('rushingTouchdowns', 0) for game in recent_games]
                    stats['receiving_yards'] = [game.get('stats', {}).get('receivingYards', 0) for game in recent_games]
                    stats['catches'] = [game.get('stats', {}).get('receptions', 0) for game in recent_games]
                elif position in ['WR', 'TE']:
                    stats['receiving_yards'] = [game.get('stats', {}).get('receivingYards', 0) for game in recent_games]
                    stats['receiving_tds'] = [game.get('stats', {}).get('receivingTouchdowns', 0) for game in recent_games]
                    stats['catches'] = [game.get('stats', {}).get('receptions', 0) for game in recent_games]
                
                # Filter out games with no stats
                for stat_type, values in stats.items():
                    stats[stat_type] = [v for v in values if v is not None and v > 0]
                
                self.logger.info(f"Found {len(recent_games)} games for player {player_id}")
                return stats
            
            return {}
        
    except Exception as e:
            self.logger.error(f"Error getting game logs for player {player_id}: {e}")
            return {}

    def _parse_team_name(self, team_raw):
        """Parse team name from raw team string"""
        if not team_raw or team_raw == 'Unknown':
            return 'Unknown'
        
        # Look for team abbreviations in the string
        for abbrev, city_name in self.TEAM_ABBREVIATIONS.items():
            if abbrev in team_raw:
                return city_name
        
        # If no abbreviation found, return the raw string
        return team_raw

    def _get_todays_nfl_games(self):
        """Get today's NFL games from Rotowire (simplified, as lineup scraper handles game detection)"""
        # This method is simplified as the LineupScraper is now responsible for identifying players
        # for today's games. If players are found, we assume a game exists.
        # The Rotowire lineups page does not have a clear "games" table to parse here.
        return []

    def _get_stadium_for_team(self, team_name):
        """Get stadium name for team (simplified mapping)"""
        stadiums = {
            'Bills': 'Highmark Stadium', 'Dolphins': 'Hard Rock Stadium', 'Patriots': 'Gillette Stadium',
            'Jets': 'MetLife Stadium', 'Ravens': 'M&T Bank Stadium', 'Bengals': 'Paul Brown Stadium',
            'Browns': 'FirstEnergy Stadium', 'Steelers': 'Heinz Field', 'Texans': 'NRG Stadium',
            'Colts': 'Lucas Oil Stadium', 'Jaguars': 'TIAA Bank Field', 'Titans': 'Nissan Stadium',
            'Broncos': 'Empower Field at Mile High', 'Chiefs': 'Arrowhead Stadium', 'Raiders': 'Allegiant Stadium',
            'Chargers': 'SoFi Stadium', 'Cowboys': 'AT&T Stadium', 'Giants': 'MetLife Stadium',
            'Eagles': 'Lincoln Financial Field', 'Commanders': 'FedExField', 'Bears': 'Soldier Field',
            'Lions': 'Ford Field', 'Packers': 'Lambeau Field', 'Vikings': 'U.S. Bank Stadium',
            'Falcons': 'Mercedes-Benz Stadium', 'Panthers': 'Bank of America Stadium', 'Saints': 'Caesars Superdome',
            'Buccaneers': 'Raymond James Stadium', 'Cardinals': 'State Farm Stadium', 'Rams': 'SoFi Stadium',
            '49ers': 'Levi\'s Stadium', 'Seahawks': 'Lumen Field'
        }
        return stadiums.get(team_name, 'Unknown Stadium')

    def _get_weather_data(self, stadium):
        """Get weather data for stadium"""
        try:
            weather_conditions = ['clear', 'rain', 'snow', 'wind', 'cold', 'dome']
            return {
                'condition': random.choice(weather_conditions),
                'temperature': random.randint(20, 80),
                'wind_speed': random.randint(0, 20)
            }
        except Exception as e:
            self.logger.error(f"Error getting weather data: {e}")
            return {'condition': 'dome', 'temperature': 72, 'wind_speed': 0}

    def _get_team_lineup(self, team_name):
        """Get team lineup (simplified - would normally scrape from Rotowire)"""
        positions = {'QB': 1, 'RB': 2, 'WR': 3, 'TE': 1}
        lineup = []
        for pos, count in positions.items():
            for i in range(count):
                lineup.append({'name': f'{pos} Player {i+1}', 'position': pos, 'team': team_name})
        return lineup
        """Generate props for a single player (similar to MLB structure)"""
