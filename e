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
                    game_info = {
                        'game_id': game['gamePk'],
                        'game_date': game['gameDate'],
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
        """Step 2: Get list of players from all games playing today"""
        self.players_today = []
        
        for game in self.games_today:
            if game['status'] != 'Preview':  # Skip completed/in-progress games for props
                continue
                
            game_id = game['game_id']
            url = f"{self.base_url}/game/{game_id}/boxscore"
            
            try:
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                
                # Get probable pitchers
                if 'probablePitchers' in data.get('teams', {}).get('home', {}):
                    home_pitcher = data['teams']['home']['probablePitchers']
                    if home_pitcher:
                        self.players_today.append({
                            'player_id': home_pitcher['id'],
                            'name': home_pitcher['fullName'],
                            'team_id': game['home_team']['id'],
                            'team_name': game['home_team']['name'],
                            'position': 'P',
                            'game_id': game_id
                        })
                
                if 'probablePitchers' in data.get('teams', {}).get('away', {}):
                    away_pitcher = data['teams']['away']['probablePitchers']
                    if away_pitcher:
                        self.players_today.append({
                            'player_id': away_pitcher['id'],
                            'name': away_pitcher['fullName'],
                            'team_id': game['away_team']['id'],
                            'team_name': game['away_team']['name'],
                            'position': 'P',
                            'game_id': game_id
                        })
                
                # Get roster for both teams
                for team_type in ['home', 'away']:
                    team_id = game[f'{team_type}_team']['id']
                    roster_url = f"{self.base_url}/teams/{team_id}/roster"
                    
                    roster_response = requests.get(roster_url, headers=self.headers)
                    if roster_response.status_code == 200:
                        roster_data = roster_response.json()
                        
                        for player in roster_data.get('roster', []):
                            # Focus on position players and starting pitchers
                            position = player['position']['abbreviation']
                            if position in ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH', 'OF', 'P']:
                                self.players_today.append({
                                    'player_id': player['person']['id'],
                                    'name': player['person']['fullName'],
                                    'team_id': team_id,
                                    'team_name': game[f'{team_type}_team']['name'],
                                    'position': position,
                                    'game_id': game_id
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
        print(f"Found {len(self.players_today)} players playing today")
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
        """Step 4: Use historical data to predict player performance (simplified LSTM concept)"""
        if player_id not in self.player_stats:
            return None
        
        stats = self.player_stats[player_id]
        predictions = {}
        
        try:
            # For batters
            if stats['recent_games']:
                recent_hitting = []
                recent_rbis = []
                recent_runs = []
                recent_total_bases = []
                
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
                
                if recent_hitting:
                    # Simple prediction using weighted average (more weight on recent games)
                    weights = np.array([0.3, 0.25, 0.2, 0.15, 0.1] + [0.05] * (len(recent_hitting) - 5))
                    weights = weights[:len(recent_hitting)]
                    weights = weights / weights.sum()
                    
                    predictions['hits'] = np.average(recent_hitting, weights=weights)
                    predictions['rbis'] = np.average(recent_rbis, weights=weights)
                    predictions['runs'] = np.average(recent_runs, weights=weights)
                    predictions['total_bases'] = np.average(recent_total_bases, weights=weights)
            
            # For pitchers - check if they have pitching stats
            if stats['recent_games']:
                recent_k = []
                recent_pitches = []
                recent_era = []
                
                for game in stats['recent_games']:
                    game_stat = game.get('stat', {})
                    if 'strikeOuts' in game_stat:  # This is a pitcher
                        recent_k.append(float(game_stat.get('strikeOuts', 0)))
                        recent_pitches.append(float(game_stat.get('pitchesThrown', 0)))
                        
                        # Calculate game ERA
                        earned_runs = float(game_stat.get('earnedRuns', 0))
                        innings = float(game_stat.get('inningsPitched', 0))
                        if innings > 0:
                            game_era = (earned_runs * 9) / innings
                            recent_era.append(game_era)
                
                if recent_k:
                    weights = np.array([0.3, 0.25, 0.2, 0.15, 0.1] + [0.05] * (len(recent_k) - 5))
                    weights = weights[:len(recent_k)]
                    weights = weights / weights.sum()
                    
                    predictions['strikeouts'] = np.average(recent_k, weights=weights)
                    if recent_pitches:
                        predictions['pitches'] = np.average(recent_pitches, weights=weights)
                    if recent_era:
                        predictions['era'] = np.average(recent_era, weights=weights)
        
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
                        over_prob = max(0.45, min(0.55, over_prob))
                        
                        props.append({
                            'type': 'medium',
                            'stat': 'Strikeouts',
                            'line': medium_line,
                            'direction': 'over',
                            'implied_prob': over_prob,
                            'price': int(over_prob * 100),
                            'opponent': self._get_opponent_info(player)
                        })
                    
                    elif stat == 'era':
                        medium_line = 3.25
                        under_prob = 1 / (1 + np.exp((expected_value - medium_line)))
                        under_prob = max(0.45, min(0.55, under_prob))
                        
                        props.append({
                            'type': 'medium',
                            'stat': 'ERA',
                            'line': medium_line,
                            'direction': 'under',
                            'implied_prob': under_prob,
                            'price': int(under_prob * 100),
                            'opponent': self._get_opponent_info(player)
                        })
                    
                    elif stat == 'pitches':
                        medium_line = 95.5
                        over_prob = 1 / (1 + np.exp(-(expected_value - medium_line) / 10))
                        over_prob = max(0.45, min(0.55, over_prob))
                        
                        props.append({
                            'type': 'medium',
                            'stat': 'Pitches',
                            'line': medium_line,
                            'direction': 'over',
                            'implied_prob': over_prob,
                            'price': int(over_prob * 100),
                            'opponent': self._get_opponent_info(player)
                        })
            
            # Randomly select 1 EASY prop from the 3 pitcher stats
            available_easy_stats = [s for s in pitcher_stats if s in predictions]
            if available_easy_stats:
                import random
                random.seed(player_id)  # Consistent for each player
                easy_stat = random.choice(available_easy_stats)
                expected_value = predictions[easy_stat]
                
                if easy_stat == 'strikeouts':
                    easy_line = 3.5
                    easy_prob = min(0.80, max(0.75, 1 / (1 + np.exp(-(expected_value - easy_line)))))
                    props.append({
                        'type': 'easy',
                        'stat': 'Strikeouts',
                        'line': easy_line,
                        'direction': 'over',
                        'implied_prob': easy_prob,
                        'price': int(easy_prob * 100),
                        'opponent': self._get_opponent_info(player)
                    })
                elif easy_stat == 'era':
                    easy_line = 4.5
                    easy_prob = min(0.80, max(0.75, 1 / (1 + np.exp((expected_value - easy_line)))))
                    props.append({
                        'type': 'easy',
                        'stat': 'ERA',
                        'line': easy_line,
                        'direction': 'under',
                        'implied_prob': easy_prob,
                        'price': int(easy_prob * 100),
                        'opponent': self._get_opponent_info(player)
                    })
                elif easy_stat == 'pitches':
                    easy_line = 85.5
                    easy_prob = min(0.80, max(0.75, 1 / (1 + np.exp(-(expected_value - easy_line) / 10))))
                    props.append({
                        'type': 'easy',
                        'stat': 'Pitches',
                        'line': easy_line,
                        'direction': 'over',
                        'implied_prob': easy_prob,
                        'price': int(easy_prob * 100),
                        'opponent': self._get_opponent_info(player)
                    })
            
            # Randomly select 1 HARD prop from the 3 pitcher stats
            available_hard_stats = [s for s in pitcher_stats if s in predictions]
            if available_hard_stats:
                random.seed(player_id + 1000)  # Different seed for hard props
                hard_stat = random.choice(available_hard_stats)
                expected_value = predictions[hard_stat]
                
                if hard_stat == 'strikeouts':
                    hard_line = 8.5
                    hard_prob = max(0.15, min(0.20, 1 / (1 + np.exp(-(expected_value - hard_line)))))
                    props.append({
                        'type': 'hard',
                        'stat': 'Strikeouts',
                        'line': hard_line,
                        'direction': 'over',
                        'implied_prob': hard_prob,
                        'price': int(hard_prob * 100),
                        'opponent': self._get_opponent_info(player)
                    })
                elif hard_stat == 'era':
                    hard_line = 2.25
                    hard_prob = max(0.15, min(0.20, 1 / (1 + np.exp((expected_value - hard_line)))))
                    props.append({
                        'type': 'hard',
                        'stat': 'ERA',
                        'line': hard_line,
                        'direction': 'under',
                        'implied_prob': hard_prob,
                        'price': int(hard_prob * 100),
                        'opponent': self._get_opponent_info(player)
                    })
                elif hard_stat == 'pitches':
                    hard_line = 105.5
                    hard_prob = max(0.15, min(0.20, 1 / (1 + np.exp(-(expected_value - hard_line) / 10))))
                    props.append({
                        'type': 'hard',
                        'stat': 'Pitches',
                        'line': hard_line,
                        'direction': 'over',
                        'implied_prob': hard_prob,
                        'price': int(hard_prob * 100),
                        'opponent': self._get_opponent_info(player)
                    })
        
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
                        over_prob = max(0.45, min(0.55, over_prob))
                        
                        props.append({
                            'type': 'medium',
                            'stat': 'Hits',
                            'line': medium_line,
                            'direction': 'over',
                            'implied_prob': over_prob,
                            'price': int(over_prob * 100),
                            'opponent': self._get_opponent_info(player)
                        })
                    
                    elif stat == 'rbis':
                        medium_line = 1.5
                        over_prob = 1 / (1 + np.exp(-(expected_value - medium_line)))
                        over_prob = max(0.45, min(0.55, over_prob))
                        
                        props.append({
                            'type': 'medium',
                            'stat': 'RBIs',
                            'line': medium_line,
                            'direction': 'over',
                            'implied_prob': over_prob,
                            'price': int(over_prob * 100),
                            'opponent': self._get_opponent_info(player)
                        })
                    
                    elif stat == 'runs':
                        medium_line = 1.5
                        over_prob = 1 / (1 + np.exp(-(expected_value - medium_line)))
                        over_prob = max(0.45, min(0.55, over_prob))
                        
                        props.append({
                            'type': 'medium',
                            'stat': 'Runs',
                            'line': medium_line,
                            'direction': 'over',
                            'implied_prob': over_prob,
                            'price': int(over_prob * 100),
                            'opponent': self._get_opponent_info(player)
                        })
                    
                    elif stat == 'total_bases':
                        medium_line = 1.5
                        over_prob = 1 / (1 + np.exp(-(expected_value - medium_line)))
                        over_prob = max(0.45, min(0.55, over_prob))
                        
                        props.append({
                            'type': 'medium',
                            'stat': 'Total Bases',
                            'line': medium_line,
                            'direction': 'over',
                            'implied_prob': over_prob,
                            'price': int(over_prob * 100),
                            'opponent': self._get_opponent_info(player)
                        })
            
            # Randomly select 1 EASY prop from the 3 batter stats (runs, hits, total_bases - no RBIs)
            available_easy_stats = [s for s in ['runs', 'hits', 'total_bases'] if s in predictions]
            if available_easy_stats:
                import random
                random.seed(player_id)  # Consistent for each player
                easy_stat = random.choice(available_easy_stats)
                expected_value = predictions[easy_stat]
                
                if easy_stat == 'hits':
                    easy_line = 0.5
                    easy_prob = min(0.80, max(0.75, 1 - np.exp(-expected_value * 2)))
                    props.append({
                        'type': 'easy',
                        'stat': 'Hits',
                        'line': easy_line,
                        'direction': 'over',
                        'implied_prob': easy_prob,
                        'price': int(easy_prob * 100),
                        'opponent': self._get_opponent_info(player)
                    })
                elif easy_stat == 'runs':
                    easy_line = 0.5
                    easy_prob = min(0.80, max(0.75, 1 - np.exp(-expected_value * 2)))
                    props.append({
                        'type': 'easy',
                        'stat': 'Runs',
                        'line': easy_line,
                        'direction': 'over',
                        'implied_prob': easy_prob,
                        'price': int(easy_prob * 100),
                        'opponent': self._get_opponent_info(player)
                    })
                elif easy_stat == 'total_bases':
                    easy_line = 0.5
                    easy_prob = min(0.80, max(0.75, 1 - np.exp(-expected_value / 2)))
                    props.append({
                        'type': 'easy',
                        'stat': 'Total Bases',
                        'line': easy_line,
                        'direction': 'over',
                        'implied_prob': easy_prob,
                        'price': int(easy_prob * 100),
                        'opponent': self._get_opponent_info(player)
                    })
            
            # Randomly select 2 HARD props from the 4 batter stats (runs, rbis, hits, total_bases - RBIs can be hard props)
            available_hard_stats = [s for s in ['runs', 'rbis', 'hits', 'total_bases'] if s in predictions]
            if len(available_hard_stats) >= 2:
                import random
                random.seed(player_id + 2000)  # Different seed for hard props
                hard_stats = random.sample(available_hard_stats, 2)
                
                for hard_stat in hard_stats:
                    expected_value = predictions[hard_stat]
                    
                    if hard_stat == 'hits':
                        hard_line = 2.5
                        hard_prob = max(0.15, min(0.20, np.exp(-((hard_line - expected_value) ** 2) / 2)))
                        props.append({
                            'type': 'hard',
                            'stat': 'Hits',
                            'line': hard_line,
                            'direction': 'over',
                            'implied_prob': hard_prob,
                            'price': int(hard_prob * 100),
                            'opponent': self._get_opponent_info(player)
                        })
                    elif hard_stat == 'runs':
                        hard_line = 2.5
                        hard_prob = max(0.15, min(0.20, np.exp(-((hard_line - expected_value) ** 2) / 2)))
                        props.append({
                            'type': 'hard',
                            'stat': 'Runs',
                            'line': hard_line,
                            'direction': 'over',
                            'implied_prob': hard_prob,
                            'price': int(hard_prob * 100),
                            'opponent': self._get_opponent_info(player)
                        })
                    elif hard_stat == 'rbis':
                        hard_line = 2.5
                        hard_prob = max(0.15, min(0.20, np.exp(-((hard_line - expected_value) ** 2) / 2)))
                        props.append({
                            'type': 'hard',
                            'stat': 'RBIs',
                            'line': hard_line,
                            'direction': 'over',
                            'implied_prob': hard_prob,
                            'price': int(hard_prob * 100),
                            'opponent': self._get_opponent_info(player)
                        })
                    elif hard_stat == 'total_bases':
                        hard_line = 3.5
                        hard_prob = max(0.15, min(0.20, 1 - np.exp(-expected_value / 3)))
                        if expected_value > hard_line:
                            hard_prob = min(0.20, hard_prob * 1.5)
                        props.append({
                            'type': 'hard',
                            'stat': 'Total Bases',
                            'line': hard_line,
                            'direction': 'over',
                            'implied_prob': hard_prob,
                            'price': int(hard_prob * 100),
                            'opponent': self._get_opponent_info(player)
                        })
        
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
        
        # Process more players for better prop coverage
        players = players[:100]  # Increased from 20 to 100
        
        all_props = {}
        
        # Steps 3-5: For each player, get stats, predict, and calculate props
        print(f"\n=== Steps 3-5: Processing {len(players)} players ===")
        
        for i, player in enumerate(players):
            player_id = player['player_id']
            player_name = player['name']
            
            print(f"Processing {player_name} ({i+1}/{len(players)})")
            
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
            
            print(f"\nPredictions:")
            for stat, value in predictions.items():
                print(f"  {stat}: {value:.2f}")
            
            print(f"\nProps ({len(props)} total):")
            for prop in props:
                print(f"  [{prop['type'].upper()}] {prop['stat']} {prop['direction'].upper()} {prop['line']} - ${prop['price']} ({prop['implied_prob']:.1%})")

def main():
    # Initialize scraper
    scraper = MLBPropScraper()
    
    # Run the full pipeline
    props = scraper.run_full_pipeline()
    
    # Display results
    scraper.display_results()
    
    # Save to JSON for web app
    if props:
        output = {
            'generated_at': datetime.now().isoformat(),
            'games': scraper.games_today,
            'props': {str(k): v for k, v in props.items()}
        }
        
        with open('mlb_props.json', 'w') as f:
            json.dump(output, f, indent=2, default=str)
        
        print(f"\nResults saved to mlb_props.json")

if __name__ == "__main__":
    main()