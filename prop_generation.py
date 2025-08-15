import requests
import json
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import time
import re
from typing import List, Dict, Tuple
import warnings
import pytz
warnings.filterwarnings('ignore')

class MLBPropScraper:
    def __init__(self):
        self.base_url = "https://statsapi.mlb.com/api/v1"
        self.games_today = []
        self.players_today = []
        self.player_stats = {}
        self.predictions = {}
        self.props = {}
        
        # Headers to avoid being blocked
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def get_todays_games(self, date_str=None):
        """Step 1: Scrape games from MLB API for today"""
        if not date_str:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        url = f"{self.base_url}/schedule?sportId=1&date={date_str}&hydrate=team,linescore,decisions"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            

            
            self.games_today = []
            
            for date_data in data.get('dates', []):
                for game in date_data.get('games', []):
                    # Extract game time from gameDate
                    game_datetime = datetime.fromisoformat(game['gameDate'].replace('Z', '+00:00'))
                    # Convert to Eastern Time explicitly
                    eastern_tz = pytz.timezone('America/New_York')
                    game_time_et = game_datetime.astimezone(eastern_tz).strftime('%I:%M %p ET')
                    
                    game_info = {
                        'game_id': game['gamePk'],
                        'game_date': game['gameDate'],
                        'game_time_et': game_time_et,
                        'game_datetime': game_datetime.isoformat(),
                        'status': game['status']['abstractGameState'],
                        'home_team': {
                            'id': game['teams']['home']['team']['id'],
                            'name': game['teams']['home']['team']['name'],
                            'abbreviation': game['teams']['home']['team']['abbreviation']
                        },
                        'away_team': {
                            'id': game['teams']['away']['team']['id'],
                            'name': game['teams']['away']['team']['name'],
                            'abbreviation': game['teams']['away']['team']['abbreviation']
                        }
                    }
                    self.games_today.append(game_info)
            
            print(f"Found {len(self.games_today)} games for {date_str}")
            return self.games_today
            
        except Exception as e:
            print(f"Error fetching games: {e}")
            return []

    def get_players_from_games(self):
        """Step 2: Get list of players from actual game lineups and starting pitchers"""
        self.players_today = []
        
        for game in self.games_today:
            if game['status'] != 'Preview':  # Skip completed/in-progress games for props
                continue
                
            game_id = game['game_id']
            
            try:
                # Get probable pitchers from the schedule (this is the correct way)
                schedule_url = f"{self.base_url}/schedule?sportId=1&date={game['game_date'][:10]}&hydrate=probablePitcher"
                schedule_response = requests.get(schedule_url, headers=self.headers)
                
                probable_pitchers = []
                if schedule_response.status_code == 200:
                    schedule_data = schedule_response.json()
                    # Find this specific game in the schedule
                    for date_data in schedule_data.get('dates', []):
                        for schedule_game in date_data.get('games', []):
                            if schedule_game['gamePk'] == game_id:
                                # Check for probable pitchers
                                if 'probablePitcher' in schedule_game.get('teams', {}).get('home', {}):
                                    home_pitcher = schedule_game['teams']['home']['probablePitcher']
                                    probable_pitchers.append({
                                        'player_id': home_pitcher['id'],
                                        'name': home_pitcher['fullName'],
                                        'team_id': game['home_team']['id'],
                                        'team_name': game['home_team']['name'],
                                        'position': 'P',
                                        'game_id': game_id,
                                        'is_starter': True
                                    })
                                
                                if 'probablePitcher' in schedule_game.get('teams', {}).get('away', {}):
                                    away_pitcher = schedule_game['teams']['away']['probablePitcher']
                                    probable_pitchers.append({
                                        'player_id': away_pitcher['id'],
                                        'name': away_pitcher['fullName'],
                                        'team_id': game['away_team']['id'],
                                        'team_name': game['away_team']['name'],
                                        'position': 'P',
                                        'game_id': game_id,
                                        'is_starter': True
                                    })
                                break
                
                # Add probable pitchers to players list
                self.players_today.extend(probable_pitchers)
                
                # Get position players from team rosters (likely starters)
                for team_type in ['home', 'away']:
                    team_id = game[f'{team_type}_team']['id']
                    team_name = game[f'{team_type}_team']['name']
                    
                    # Get team roster to find likely starters
                    roster_url = f"{self.base_url}/teams/{team_id}/roster"
                    roster_response = requests.get(roster_url, headers=self.headers)
                    
                    if roster_response.status_code == 200:
                        roster_data = roster_response.json()
                        
                        # Get likely starters (focus on key positions and recent players)
                        for player in roster_data.get('roster', []):
                            position = player['position']['abbreviation']
                            
                            # Focus on position players (not pitchers - we already have them)
                            if position in ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH', 'OF']:
                                # Get player stats to determine if they're likely to start
                                player_id = player['person']['id']
                                
                                # Add position players (we'll filter by stats later)
                                self.players_today.append({
                                    'player_id': player_id,
                                    'name': player['person']['fullName'],
                                    'team_id': team_id,
                                    'team_name': team_name,
                                    'position': position,
                                    'game_id': game_id,
                                    'is_starter': True  # Assume they're starters for now
                                })
                
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                print(f"Error fetching players for game {game_id}: {e}")
                continue
        
        # Remove duplicates
        unique_players = {}
        for player in self.players_today:
            key = f"{player['player_id']}_{player['game_id']}"
            if key not in unique_players:
                unique_players[key] = player
        
        self.players_today = list(unique_players.values())
        
        # Count starters vs bench players
        starters = [p for p in self.players_today if p.get('is_starter', False)]
        bench_players = [p for p in self.players_today if not p.get('is_starter', False)]
        pitchers = [p for p in self.players_today if p['position'] == 'P']
        position_players = [p for p in self.players_today if p['position'] != 'P']
        
        print(f"Found {len(self.players_today)} total players playing today")
        print(f"  - Starting pitchers: {len(pitchers)}")
        print(f"  - Position players: {len(position_players)}")
        print(f"  - Bench players: {len(bench_players)}")
        
        return self.players_today

    def get_player_stats(self, player_id: int, seasons: List[int] = None):
        """Step 3: Get player stats from last 10 games and last 2 seasons"""
        if not seasons:
            current_year = datetime.now().year
            seasons = [current_year, current_year - 1]
        
        player_data = {
            'recent_games': [],
            'season_stats': {},
            'career_stats': {}
        }
        
        try:
            # Get recent game logs (last 10 games)
            current_season = datetime.now().year
            gamelog_url = f"{self.base_url}/people/{player_id}/stats?stats=gameLog&season={current_season}&gameType=R"
            
            response = requests.get(gamelog_url, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                
                if data.get('stats') and len(data['stats']) > 0:
                    game_logs = data['stats'][0].get('splits', [])
                    # Get last 10 games
                    recent_games = game_logs[-10:] if len(game_logs) > 10 else game_logs
                    player_data['recent_games'] = recent_games
            
            # Get season stats for last 2 seasons
            for season in seasons:
                season_url = f"{self.base_url}/people/{player_id}/stats?stats=season&season={season}&gameType=R"
                
                response = requests.get(season_url, headers=self.headers)
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('stats') and len(data['stats']) > 0:
                        season_stats = data['stats'][0].get('splits', [])
                        if season_stats:
                            player_data['season_stats'][season] = season_stats[0]['stat']
            
            self.player_stats[player_id] = player_data
            time.sleep(0.3)  # Rate limiting
            
        except Exception as e:
            print(f"Error fetching stats for player {player_id}: {e}")
            
        return player_data

    def calculate_predictions(self, player_id: int):
        """Step 4: Use historical data to predict player performance (80% recent 10 games, 20% past 2 seasons)"""
        if player_id not in self.player_stats:
            return None
        
        stats = self.player_stats[player_id]
        predictions = {}
        
        try:
            # Get player info to determine position
            player = None
            for p in self.players_today:
                if p['player_id'] == player_id:
                    player = p
                    break
            
            if not player:
                return None
            
            is_pitcher = player['position'] == 'P'
            
            if is_pitcher:
                # PITCHER STATS ONLY: Strikeouts, ERA, Pitches
                recent_k = []
                recent_pitches = []
                recent_era = []
                
                # Get recent 10 games (80% weight)
                if stats['recent_games']:
                    for game in stats['recent_games']:
                        game_stat = game.get('stat', {})
                        if 'strikeOuts' in game_stat:  # This is a pitcher
                            recent_k.append(float(game_stat.get('strikeOuts', 0)))
                            
                            # Get pitches thrown - handle missing data
                            pitches = game_stat.get('pitchesThrown', 0)
                            if pitches and pitches > 0:
                                recent_pitches.append(float(pitches))
                            else:
                                # If no pitches data, estimate based on innings (typical: 15-20 pitches per inning)
                                innings = float(game_stat.get('inningsPitched', 0))
                                if innings > 0:
                                    estimated_pitches = innings * 17.5  # Average of 17.5 pitches per inning
                                    recent_pitches.append(estimated_pitches)
                            
                            # Calculate game ERA
                            earned_runs = float(game_stat.get('earnedRuns', 0))
                            innings = float(game_stat.get('inningsPitched', 0))
                            if innings > 0:
                                game_era = (earned_runs * 9) / innings
                                recent_era.append(game_era)
                
                # Get season stats (20% weight)
                season_k = []
                season_pitches = []
                season_era = []
                
                for season, season_stat in stats['season_stats'].items():
                    if 'strikeOuts' in season_stat:
                        season_k.append(float(season_stat.get('strikeOuts', 0)))
                        
                        # Get season pitches - handle missing data
                        season_pitches_val = season_stat.get('pitchesThrown', 0)
                        if season_pitches_val and season_pitches_val > 0:
                            season_pitches.append(float(season_pitches_val))
                        else:
                            # If no season pitches data, estimate based on innings
                            innings = float(season_stat.get('inningsPitched', 0))
                            if innings > 0:
                                estimated_pitches = innings * 17.5
                                season_pitches.append(estimated_pitches)
                        
                        # Calculate season ERA
                        earned_runs = float(season_stat.get('earnedRuns', 0))
                        innings = float(season_stat.get('inningsPitched', 0))
                        if innings > 0:
                            season_era_val = (earned_runs * 9) / innings
                            season_era.append(season_era_val)
                
                # Calculate weighted predictions: 80% recent games, 20% season stats
                if recent_k:
                    # Recent games weight (80%)
                    recent_weights = np.array([0.3, 0.25, 0.2, 0.15, 0.1] + [0.05] * (len(recent_k) - 5))
                    recent_weights = recent_weights[:len(recent_k)]
                    recent_weights = recent_weights / recent_weights.sum()
                    
                    recent_k_avg = np.average(recent_k, weights=recent_weights)
                    recent_pitches_avg = np.average(recent_pitches, weights=recent_weights) if recent_pitches else 0
                    recent_era_avg = np.average(recent_era, weights=recent_weights) if recent_era else 0
                    
                    # Season stats weight (20%)
                    season_k_avg = np.average(season_k) if season_k else recent_k_avg
                    season_pitches_avg = np.average(season_pitches) if season_pitches else recent_pitches_avg
                    season_era_avg = np.average(season_era) if season_era else recent_era_avg
                    
                    # Final weighted average: 80% recent + 20% season
                    predictions['strikeouts'] = 0.8 * recent_k_avg + 0.2 * season_k_avg
                    
                    # Always calculate pitches - use estimated if no real data
                    if recent_pitches_avg > 0 or season_pitches_avg > 0:
                        predictions['pitches'] = 0.8 * recent_pitches_avg + 0.2 * season_pitches_avg
                    else:
                        # Fallback: estimate based on strikeouts (typical: 4-5 pitches per strikeout)
                        predictions['pitches'] = recent_k_avg * 4.5
                    
                    if recent_era_avg > 0 or season_era_avg > 0:
                        predictions['era'] = 0.8 * recent_era_avg + 0.2 * season_era_avg
                
            else:
                # HITTER STATS ONLY: Runs, RBIs, Hits, Total Bases
                recent_hitting = []
                recent_rbis = []
                recent_runs = []
                recent_total_bases = []
                
                # Get recent 10 games (80% weight)
                if stats['recent_games']:
                    for game in stats['recent_games']:
                        game_stat = game.get('stat', {})
                        # Handle hitting stats
                        if 'hits' in game_stat:
                            recent_hitting.append(float(game_stat.get('hits', 0)))
                            recent_rbis.append(float(game_stat.get('rbi', 0)))
                            recent_runs.append(float(game_stat.get('runs', 0)))
                            
                            # Calculate total bases - ensure all values are numbers
                            hits = float(game_stat.get('hits', 0))
                            doubles = float(game_stat.get('doubles', 0))
                            triples = float(game_stat.get('triples', 0))
                            homers = float(game_stat.get('homeRuns', 0))
                            
                            singles = hits - doubles - triples - homers
                            total_bases = singles + (doubles * 2) + (triples * 3) + (homers * 4)
                            recent_total_bases.append(total_bases)
                
                # Get season stats (20% weight)
                season_hits = []
                season_rbis = []
                season_runs = []
                season_total_bases = []
                
                for season, season_stat in stats['season_stats'].items():
                    if 'hits' in season_stat:
                        season_hits.append(float(season_stat.get('hits', 0)))
                        season_rbis.append(float(season_stat.get('rbi', 0)))
                        season_runs.append(float(season_stat.get('runs', 0)))
                        
                        # Calculate season total bases
                        hits = float(season_stat.get('hits', 0))
                        doubles = float(season_stat.get('doubles', 0))
                        triples = float(season_stat.get('triples', 0))
                        homers = float(season_stat.get('homeRuns', 0))
                        
                        singles = hits - doubles - triples - homers
                        total_bases = singles + (doubles * 2) + (triples * 3) + (homers * 4)
                        season_total_bases.append(total_bases)
                
                # Calculate weighted predictions: 80% recent games, 20% season stats
                if recent_hitting:
                    # Recent games weight (80%)
                    recent_weights = np.array([0.3, 0.25, 0.2, 0.15, 0.1] + [0.05] * (len(recent_hitting) - 5))
                    recent_weights = recent_weights[:len(recent_hitting)]
                    recent_weights = recent_weights / recent_weights.sum()
                    
                    recent_hits_avg = np.average(recent_hitting, weights=recent_weights)
                    recent_rbis_avg = np.average(recent_rbis, weights=recent_weights)
                    recent_runs_avg = np.average(recent_runs, weights=recent_weights)
                    recent_total_bases_avg = np.average(recent_total_bases, weights=recent_weights)
                    
                    # Season stats weight (20%)
                    season_hits_avg = np.average(season_hits) if season_hits else recent_hits_avg
                    season_rbis_avg = np.average(season_rbis) if season_rbis else recent_rbis_avg
                    season_runs_avg = np.average(season_runs) if season_runs else recent_runs_avg
                    season_total_bases_avg = np.average(season_total_bases) if season_total_bases else recent_total_bases_avg
                    
                    # Final weighted average: 80% recent + 20% season
                    predictions['hits'] = 0.8 * recent_hits_avg + 0.2 * season_hits_avg
                    predictions['rbis'] = 0.8 * recent_rbis_avg + 0.2 * season_rbis_avg
                    predictions['runs'] = 0.8 * recent_runs_avg + 0.2 * season_runs_avg
                    predictions['total_bases'] = 0.8 * recent_total_bases_avg + 0.2 * season_total_bases_avg
        
        except Exception as e:
            print(f"Error calculating predictions for player {player_id}: {e}")
        
        self.predictions[player_id] = predictions
        return predictions

    def calculate_implied_probabilities(self, player_id: int, predictions: Dict):
        """Step 5: Calculate implied probabilities for easy, medium, hard tiers"""
        if not predictions:
            return {}
        
        # Get player info for opponent details
        player = None
        for p in self.players_today:
            if p['player_id'] == player_id:
                player = p
                break
        
        if not player:
            return {}
        
        # Determine if player is pitcher or non-pitcher
        is_pitcher = player['position'] == 'P'
        
        props = []
        
        if is_pitcher:
            # PITCHER PROPS: Strikeouts, ERA, Pitches
            pitcher_stats = ['strikeouts', 'era', 'pitches']
            
            # Always create MEDIUM props for all pitcher stats
            for stat in pitcher_stats:
                if stat in predictions:
                    expected_value = predictions[stat]
                    
                    if stat == 'strikeouts':
                        medium_line = 6.5
                        over_prob = 1 / (1 + np.exp(-(expected_value - medium_line)))
                        # Dynamic probability based on player performance - no hard limits
                        # Better players get higher probabilities, worse players get lower
                        over_prob = max(0.40, min(0.60, over_prob))  # Tighter range: 40-60%
                        
                        prop = {
                            'type': 'medium',
                            'stat': 'Strikeouts',
                            'line': medium_line,
                            'direction': 'over',
                            'implied_prob': over_prob,
                            'price': int(over_prob * 100)
                        }
                        props.append(self._add_prop_metadata(prop, player))
                    
                    elif stat == 'era':
                        medium_line = 3.25
                        under_prob = 1 / (1 + np.exp((expected_value - medium_line)))
                        # Dynamic probability based on player performance
                        under_prob = max(0.40, min(0.60, under_prob))  # Tighter range: 40-60%
                        
                        prop = {
                            'type': 'medium',
                            'stat': 'ERA',
                            'line': medium_line,
                            'direction': 'under',
                            'implied_prob': under_prob,
                            'price': int(under_prob * 100)
                        }
                        props.append(self._add_prop_metadata(prop, player))
                    
                    elif stat == 'pitches':
                        medium_line = 95.5
                        over_prob = 1 / (1 + np.exp(-(expected_value - medium_line) / 10))
                        # Dynamic probability based on player performance
                        over_prob = max(0.40, min(0.60, over_prob))  # Tighter range: 40-60%
                        
                        prop = {
                            'type': 'medium',
                            'stat': 'Pitches',
                            'line': medium_line,
                            'direction': 'over',
                            'implied_prob': over_prob,
                            'price': int(over_prob * 100)
                        }
                        props.append(self._add_prop_metadata(prop, player))
            
            # Randomly select 1 EASY prop from the 3 pitcher stats
            available_easy_stats = [s for s in pitcher_stats if s in predictions]
            if available_easy_stats:
                import random
                random.seed(player_id)  # Consistent for each player
                easy_stat = random.choice(available_easy_stats)
                expected_value = predictions[easy_stat]
                
                if easy_stat == 'strikeouts':
                    easy_line = 3.5
                    easy_prob = 1 / (1 + np.exp(-(expected_value - easy_line)))
                    # Dynamic probability based on player performance - better players get higher odds
                    easy_prob = max(0.65, min(0.85, easy_prob))  # Range: 65-85%
                    
                    prop = {
                        'type': 'easy',
                        'stat': 'Strikeouts',
                        'line': easy_line,
                        'direction': 'over',
                        'implied_prob': easy_prob,
                        'price': int(easy_prob * 100)
                    }
                    props.append(self._add_prop_metadata(prop, player))
                elif easy_stat == 'era':
                    easy_line = 4.5
                    easy_prob = 1 / (1 + np.exp((expected_value - easy_line)))
                    # Dynamic probability based on player performance
                    easy_prob = max(0.65, min(0.85, easy_prob))  # Range: 65-85%
                    
                    prop = {
                        'type': 'easy',
                        'stat': 'ERA',
                        'line': easy_line,
                        'direction': 'under',
                        'implied_prob': easy_prob,
                        'price': int(easy_prob * 100)
                    }
                    props.append(self._add_prop_metadata(prop, player))
                elif easy_stat == 'pitches':
                    easy_line = 85.5
                    easy_prob = 1 / (1 + np.exp(-(expected_value - easy_line) / 10))
                    # Dynamic probability based on player performance
                    easy_prob = max(0.65, min(0.85, easy_prob))  # Range: 65-85%
                    
                    prop = {
                        'type': 'easy',
                        'stat': 'Pitches',
                        'line': easy_line,
                        'direction': 'over',
                        'implied_prob': easy_prob,
                        'price': int(easy_prob * 100)
                    }
                    props.append(self._add_prop_metadata(prop, player))
            
            # Randomly select 1 HARD prop from the 3 pitcher stats
            available_hard_stats = [s for s in pitcher_stats if s in predictions]
            if available_hard_stats:
                random.seed(player_id + 1000)  # Different seed for hard props
                hard_stat = random.choice(available_hard_stats)
                expected_value = predictions[hard_stat]
                
                if hard_stat == 'strikeouts':
                    hard_line = 8.5
                    hard_prob = 1 / (1 + np.exp(-(expected_value - hard_line)))
                    # Dynamic probability based on player performance - worse players get lower odds
                    hard_prob = max(0.10, min(0.25, hard_prob))  # Range: 10-25%
                    
                    prop = {
                        'type': 'hard',
                        'stat': 'Strikeouts',
                        'line': hard_line,
                        'direction': 'over',
                        'implied_prob': hard_prob,
                        'price': int(hard_prob * 100)
                    }
                    props.append(self._add_prop_metadata(prop, player))
                elif hard_stat == 'era':
                    hard_line = 1.5
                    # Since 1.5 is much harder than 2.25, adjust probability calculation
                    # Use a more aggressive sigmoid curve for the tougher line
                    hard_prob = 1 / (1 + np.exp((expected_value - hard_line) * 2))
                    # Dynamic probability based on player performance
                    hard_prob = max(0.08, min(0.20, hard_prob))  # Range: 8-20%
                    
                    prop = {
                        'type': 'hard',
                        'stat': 'ERA',
                        'line': hard_line,
                        'direction': 'under',
                        'implied_prob': hard_prob,
                        'price': int(hard_prob * 100)
                    }
                    props.append(self._add_prop_metadata(prop, player))
                elif hard_stat == 'pitches':
                    hard_line = 105.5
                    hard_prob = 1 / (1 + np.exp(-(expected_value - hard_line) / 10))
                    # Dynamic probability based on player performance
                    hard_prob = max(0.10, min(0.25, hard_prob))  # Range: 10-25%
                    
                    prop = {
                        'type': 'hard',
                        'stat': 'Pitches',
                        'line': hard_line,
                        'direction': 'over',
                        'implied_prob': hard_prob,
                        'price': int(hard_prob * 100)
                    }
                    props.append(self._add_prop_metadata(prop, player))
        
        else:
            # NON-PITCHER PROPS: Runs, RBIs, Hits, Total Bases
            batter_stats = ['runs', 'rbis', 'hits', 'total_bases']
            
            # Always create MEDIUM props for all batter stats
            for stat in batter_stats:
                if stat in predictions:
                    expected_value = predictions[stat]
                    
                    if stat == 'hits':
                        medium_line = 1.5
                        over_prob = 1 / (1 + np.exp(-(expected_value - medium_line)))
                        # Dynamic probability based on player performance
                        over_prob = max(0.40, min(0.60, over_prob))  # Range: 40-60%
                        
                        prop = {
                            'type': 'medium',
                            'stat': 'Hits',
                            'line': medium_line,
                            'direction': 'over',
                            'implied_prob': over_prob,
                            'price': int(over_prob * 100)
                        }
                        props.append(self._add_prop_metadata(prop, player))
                    
                    elif stat == 'rbis':
                        medium_line = 1.5
                        over_prob = 1 / (1 + np.exp(-(expected_value - medium_line)))
                        # Dynamic probability based on player performance
                        over_prob = max(0.40, min(0.60, over_prob))  # Range: 40-60%
                        
                        prop = {
                            'type': 'medium',
                            'stat': 'RBIs',
                            'line': medium_line,
                            'direction': 'over',
                            'implied_prob': over_prob,
                            'price': int(over_prob * 100)
                        }
                        props.append(self._add_prop_metadata(prop, player))
                    
                    elif stat == 'runs':
                        medium_line = 1.5
                        over_prob = 1 / (1 + np.exp(-(expected_value - medium_line)))
                        # Dynamic probability based on player performance
                        over_prob = max(0.40, min(0.60, over_prob))  # Range: 40-60%
                        
                        prop = {
                            'type': 'medium',
                            'stat': 'Runs',
                            'line': medium_line,
                            'direction': 'over',
                            'implied_prob': over_prob,
                            'price': int(over_prob * 100)
                        }
                        props.append(self._add_prop_metadata(prop, player))
                    
                    elif stat == 'total_bases':
                        medium_line = 1.5
                        over_prob = 1 / (1 + np.exp(-(expected_value - medium_line)))
                        # Dynamic probability based on player performance
                        over_prob = max(0.40, min(0.60, over_prob))  # Range: 40-60%
                        
                        prop = {
                            'type': 'medium',
                            'stat': 'Total Bases',
                            'line': medium_line,
                            'direction': 'over',
                            'implied_prob': over_prob,
                            'price': int(over_prob * 100)
                        }
                        props.append(self._add_prop_metadata(prop, player))
            
            # Randomly select 1 EASY prop from the 3 batter stats (runs, hits, total_bases - no RBIs)
            available_easy_stats = [s for s in ['runs', 'hits', 'total_bases'] if s in predictions]
            if available_easy_stats:
                import random
                random.seed(player_id)  # Consistent for each player
                easy_stat = random.choice(available_easy_stats)
                expected_value = predictions[easy_stat]
                
                if easy_stat == 'hits':
                    easy_line = 0.5
                    easy_prob = 1 - np.exp(-expected_value * 2)
                    # Dynamic probability based on player performance
                    easy_prob = max(0.65, min(0.85, easy_prob))  # Range: 65-85%
                    
                    prop = {
                        'type': 'easy',
                        'stat': 'Hits',
                        'line': easy_line,
                        'direction': 'over',
                        'implied_prob': easy_prob,
                        'price': int(easy_prob * 100)
                    }
                    props.append(self._add_prop_metadata(prop, player))
                elif easy_stat == 'runs':
                    easy_line = 0.5
                    easy_prob = 1 - np.exp(-expected_value * 2)
                    # Dynamic probability based on player performance
                    easy_prob = max(0.65, min(0.85, easy_prob))  # Range: 65-85%
                    
                    prop = {
                        'type': 'easy',
                        'stat': 'Runs',
                        'line': easy_line,
                        'direction': 'over',
                        'implied_prob': easy_prob,
                        'price': int(easy_prob * 100)
                    }
                    props.append(self._add_prop_metadata(prop, player))
                elif easy_stat == 'total_bases':
                    easy_line = 0.5
                    easy_prob = 1 - np.exp(-expected_value / 2)
                    # Dynamic probability based on player performance
                    easy_prob = max(0.65, min(0.85, easy_prob))  # Range: 65-85%
                    
                    prop = {
                        'type': 'easy',
                        'stat': 'Total Bases',
                        'line': easy_line,
                        'direction': 'over',
                        'implied_prob': easy_prob,
                        'price': int(easy_prob * 100)
                    }
                    props.append(self._add_prop_metadata(prop, player))
            
            # Randomly select 2 HARD props from the 3 batter stats (runs, rbis, total_bases - no hits for hard props)
            available_hard_stats = [s for s in ['runs', 'rbis', 'total_bases'] if s in predictions]
            if len(available_hard_stats) >= 2:
                import random
                random.seed(player_id + 2000)  # Different seed for hard props
                hard_stats = random.sample(available_hard_stats, 2)
                
                for hard_stat in hard_stats:
                    expected_value = predictions[hard_stat]
                    
                    if hard_stat == 'runs':
                        hard_line = 2.5
                        hard_prob = np.exp(-((hard_line - expected_value) ** 2) / 2)
                        # Dynamic probability based on player performance
                        hard_prob = max(0.10, min(0.25, hard_prob))  # Range: 10-25%
                        
                        prop = {
                            'type': 'hard',
                            'stat': 'Runs',
                            'line': hard_line,
                            'direction': 'over',
                            'implied_prob': hard_prob,
                            'price': int(hard_prob * 100)
                        }
                        props.append(self._add_prop_metadata(prop, player))
                    elif hard_stat == 'rbis':
                        hard_line = 2.5
                        hard_prob = np.exp(-((hard_line - expected_value) ** 2) / 2)
                        # Dynamic probability based on player performance
                        hard_prob = max(0.10, min(0.25, hard_prob))  # Range: 10-25%
                        
                        prop = {
                            'type': 'hard',
                            'stat': 'RBIs',
                            'line': hard_line,
                            'direction': 'over',
                            'implied_prob': hard_prob,
                            'price': int(hard_prob * 100)
                        }
                        props.append(self._add_prop_metadata(prop, player))
                    elif hard_stat == 'total_bases':
                        hard_line = 3.5
                        hard_prob = 1 - np.exp(-expected_value / 3)
                        # Dynamic probability based on player performance
                        if expected_value > hard_line:
                            hard_prob = min(0.25, hard_prob * 1.5)
                        hard_prob = max(0.10, min(0.25, hard_prob))  # Range: 10-25%
                        
                        prop = {
                            'type': 'hard',
                            'stat': 'Total Bases',
                            'line': hard_line,
                            'direction': 'over',
                            'implied_prob': hard_prob,
                            'price': int(hard_prob * 100)
                        }
                        props.append(self._add_prop_metadata(prop, player))
        
        return props

    def _get_opponent_info(self, player):
        """Get opponent information for a player"""
        for game in self.games_today:
            if game['game_id'] == player['game_id']:
                if player['team_id'] == game['home_team']['id']:
                    return f"vs {game['away_team']['name']}"
                else:
                    return f"@ {game['home_team']['name']}"
        return "vs Unknown"
    
    def _get_game_time(self, player):
        """Get game time for a player"""
        for game in self.games_today:
            if game['game_id'] == player['game_id']:
                return game.get('game_time_et', 'TBD')
        return 'TBD'
    
    def _add_prop_metadata(self, prop, player):
        """Add game time and opponent to a prop"""
        prop['game_time'] = self._get_game_time(player)
        prop['opponent'] = self._get_opponent_info(player)
        return prop

    def run_full_pipeline(self, date_str=None):
        """Run the complete pipeline"""
        print("Starting MLB Prop Generator Pipeline...")
        
        # Step 1: Get today's games
        print("\n=== Step 1: Fetching today's games ===")
        games = self.get_todays_games(date_str)
        
        if not games:
            print("No games found for today")
            return
        
        # Step 2: Get players from games
        print("\n=== Step 2: Fetching players ===")
        players = self.get_players_from_games()
        
        if not players:
            print("No players found")
            return
        
        # Process ALL players for complete coverage of all 14 games
        # No limit on total players - process everyone found
        
        # Prioritize starters over bench players
        starters = [p for p in players if p.get('is_starter', False)]
        bench_players = [p for p in players if not p.get('is_starter', False)]
        
        # Process starters first, then bench players if needed
        players_to_process = starters + bench_players  # No limit on bench players
        
        print(f"Processing {len(players_to_process)} players:")
        print(f"  - Starters: {len(starters)}")
        print(f"  - Bench players: {len(players_to_process) - len(starters)}")
        
        all_props = {}
        
        # Steps 3-5: For each player, get stats, predict, and calculate props
        print(f"\n=== Steps 3-5: Processing {len(players_to_process)} players ===")
        
        for i, player in enumerate(players_to_process):
            player_id = player['player_id']
            player_name = player['name']
            
            print(f"Processing {player_name} ({i+1}/{len(players_to_process)})")
            
            # Step 3: Get player stats
            stats = self.get_player_stats(player_id)
            
            if not stats or not stats.get('recent_games'):
                print(f"  No recent stats found for {player_name}")
                continue
            
            # Step 4: Calculate predictions
            predictions = self.calculate_predictions(player_id)
            
            if not predictions:
                print(f"  No predictions generated for {player_name}")
                continue
            
            # Step 5: Calculate props
            props = self.calculate_implied_probabilities(player_id, predictions)
            
            if props:
                all_props[player_id] = {
                    'player_info': player,
                    'predictions': predictions,
                    'props': props
                }
                print(f"  Generated {len(props)} props for {player_name}")
            else:
                print(f"  No props generated for {player_name}")
        
        self.props = all_props
        
        print(f"\n=== Pipeline Complete ===")
        print(f"Total players with props: {len(all_props)}")
        
        return all_props

    def display_results(self):
        """Display the generated props in a readable format"""
        if not self.props:
            print("No props to display")
            return
        
        for player_id, data in self.props.items():
            player = data['player_info']
            predictions = data['predictions']
            props = data['props']
            
            print(f"\n{'='*50}")
            print(f"Player: {player['name']} ({player['position']}) - {player['team_name']}")
            print(f"{'='*50}")
            
            print(f"\nPredictions (80% recent 10 games, 20% past 2 seasons):")
            for stat, value in predictions.items():
                print(f"  {stat}: {value:.2f}")
            
            print(f"\nProps ({len(props)} total):")
            for prop in props:
                if isinstance(prop, dict) and 'type' in prop and 'stat' in prop and 'direction' in prop and 'line' in prop and 'price' in prop and 'implied_prob' in prop:
                    print(f"  [{prop['type'].upper()}] {prop['stat']} {prop['direction'].upper()} {prop['line']} - ${prop['price']} ({prop['implied_prob']:.1%})")
                else:
                    print(f"  [INVALID PROP] {prop}")
            
            # Show weight breakdown for first few players
            if player_id == list(self.props.keys())[0]:  # Only show for first player as example
                print(f"\n📊 Weight Calculation Example ({player['name']}):")
                print(f"  Recent 10 games: 80% weight")
                print(f"  Past 2 seasons: 20% weight")
                print(f"  Final prediction = (0.8 × recent_avg) + (0.2 × season_avg)")

def main():
    # Initialize scraper
    scraper = MLBPropScraper()
    
    # Run the full pipeline
    props = scraper.run_full_pipeline()
    
    # Display results
    scraper.display_results()
    
    # Save to JSON for web app
    if props:
        # Preserve the original games list before any modifications
        original_games = scraper.games_today.copy()
        
        output = {
            'generated_at': datetime.now().isoformat(),
            'games': original_games,
            'props': {str(k): v for k, v in props.items()}
        }
        
        with open('mlb_props.json', 'w') as f:
            json.dump(output, f, indent=2, default=str)
        
        print(f"\nResults saved to mlb_props.json")

if __name__ == "__main__":
    main()