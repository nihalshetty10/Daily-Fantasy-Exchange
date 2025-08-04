#!/usr/bin/env python3
"""
ML-Based Prop Generator
Scrapes real games, gets real player data, uses ML to predict props
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import re
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import warnings
warnings.filterwarnings('ignore')

class MLPropGenerator:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        self.scaler = StandardScaler()
        self.models = {}
        
    def scrape_mlb_games(self, target_date):
        """Scrape MLB games from MLB.com/scores"""
        try:
            print(f"🔍 Scraping MLB games from MLB.com for {target_date}")
            
            # Use MLB.com/scores URL - the site shows different dates, we want today
            url = "https://www.mlb.com/scores"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            games = []
            
            # Look for game cards on MLB.com/scores page
            # Based on the image, games are displayed as cards with team info
            game_containers = soup.find_all('div', class_=lambda x: x and ('game' in x.lower() or 'card' in x.lower()))
            
            if not game_containers:
                # Try alternative selectors for game cards
                game_containers = soup.find_all('div', {'data-testid': lambda x: x and ('game' in x.lower() or 'card' in x.lower())})
            
            if not game_containers:
                # Look for containers with team names and game times
                game_containers = soup.find_all('div', string=re.compile(r'(Giants|Pirates|Twins|Tigers|Astros|Marlins|Orioles|Phillies|Royals|Red Sox|Guardians|Mets|Brewers|Braves|Reds|Cubs|Yankees|Rangers|Blue Jays|Rockies|Rays|Angels|Padres|D-backs|Cardinals|Dodgers)', re.I))
            
            # Track unique games to avoid duplicates
            unique_games = set()
            
            for container in game_containers:
                try:
                    # Extract team names from the game card
                    team_elements = container.find_all(['span', 'div', 'h3', 'h4'], string=re.compile(r'(Giants|Pirates|Twins|Tigers|Astros|Marlins|Orioles|Phillies|Royals|Red Sox|Guardians|Mets|Brewers|Braves|Reds|Cubs|Yankees|Rangers|Blue Jays|Rockies|Rays|Angels|Padres|D-backs|Cardinals|Dodgers)', re.I))
                    
                    if len(team_elements) >= 2:
                        away_team = team_elements[0].get_text().strip()
                        home_team = team_elements[1].get_text().strip()
                        
                        # Extract game time from the card
                        time_element = container.find(['span', 'div'], string=re.compile(r'\d{1,2}:\d{2}\s*(PM|AM|ET)', re.I))
                        game_time = time_element.get_text().strip() if time_element else "7:05 PM"
                        
                        # Extract probable pitchers from the card
                        pitcher_elements = container.find_all(['span', 'div'], string=re.compile(r'(RHP|LHP|TBD)', re.I))
                        away_pitcher = pitcher_elements[0].get_text().strip() if len(pitcher_elements) > 0 else "TBD"
                        home_pitcher = pitcher_elements[1].get_text().strip() if len(pitcher_elements) > 1 else "TBD"
                        
                        # Create unique key for deduplication
                        game_key = f"{away_team}@{home_team}"
                        
                        # Only add if we haven't seen this game before
                        if game_key not in unique_games:
                            unique_games.add(game_key)
                            
                            game = {
                                'away_team': away_team,
                                'home_team': home_team,
                                'game_time': game_time,
                                'away_pitcher': away_pitcher,
                                'home_pitcher': home_pitcher,
                                'date': target_date
                            }
                            
                            games.append(game)
                            print(f"✅ Found game: {away_team} @ {home_team} at {game_time}")
                        else:
                            print(f"⏭️ Skipping duplicate: {away_team} @ {home_team}")
                
                except Exception as e:
                    print(f"⚠️ Error parsing game container: {e}")
                    continue
            
            if not games:
                print("⚠️ No games found for the target date")
                return []
            
            print(f"✅ Scraped {len(games)} MLB games from MLB.com/scores")
            return games
            
        except Exception as e:
            print(f"❌ Error scraping MLB games from MLB.com/scores: {e}")
            return []
    

    
    def get_player_historical_data(self, player_name, team, position):
        """Get 2 seasons of historical data + last 10 games for player"""
        try:
            # Clean player name for URL
            clean_name = player_name.replace(' ', '-').replace('.', '').replace('\'', '')
            
            historical_data = []
            
            # Get data for 2023 and 2024 seasons
            for year in [2023, 2024]:
                try:
                    url = f"https://www.baseball-reference.com/players/{clean_name[0].lower()}/{clean_name.lower()}.shtml"
                    response = requests.get(url, headers=self.headers)
                    
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        
                        # Find batting stats table
                        if position != 'P':
                            stats_table = soup.find('table', {'id': 'batting_standard'})
                        else:
                            stats_table = soup.find('table', {'id': 'pitching_standard'})
                        
                        if stats_table:
                            rows = stats_table.find_all('tr')
                            for row in rows:
                                year_cell = row.find('td', {'data-stat': 'year_ID'})
                                if year_cell and year_cell.text.strip() == str(year):
                                    # Extract relevant stats
                                    if position == 'P':
                                        strikeouts = row.find('td', {'data-stat': 'SO'})
                                        earned_runs = row.find('td', {'data-stat': 'ER'})
                                        hits_allowed = row.find('td', {'data-stat': 'H'})
                                        
                                        if strikeouts and earned_runs:
                                            historical_data.append({
                                                'year': year,
                                                'strikeouts': float(strikeouts.text),
                                                'earned_runs_allowed': float(earned_runs.text),
                                                'hits_allowed': float(hits_allowed.text) if hits_allowed else 0,
                                                'games': 1
                                            })
                                    else:
                                        hits = row.find('td', {'data-stat': 'H'})
                                        rbis = row.find('td', {'data-stat': 'RBI'})
                                        runs = row.find('td', {'data-stat': 'R'})
                                        total_bases = row.find('td', {'data-stat': 'TB'})
                                        
                                        if hits and rbis:
                                            historical_data.append({
                                                'year': year,
                                                'hits': float(hits.text),
                                                'rbis': float(rbis.text),
                                                'runs': float(runs.text) if runs else 0,
                                                'total_bases': float(total_bases.text) if total_bases else 0,
                                                'games': 1
                                            })
                    
                    time.sleep(1)  # Be respectful to the server
                    
                except Exception as e:
                    print(f"⚠️ Error getting {year} data for {player_name}: {e}")
                    continue
            
            # Get last 10 games data (simulated for now)
            recent_games = self.get_recent_games_data(player_name, team, position)
            historical_data.extend(recent_games)
            
            return historical_data
            
        except Exception as e:
            print(f"❌ Error getting historical data for {player_name}: {e}")
            return []
    
    def get_recent_games_data(self, player_name, team, position):
        """Get last 10 games data for player"""
        # This would require scraping individual game logs
        # For now, return empty list - would need to implement game log scraping
        return []
    
    def prepare_features(self, historical_data, position):
        """Prepare features for ML model"""
        if not historical_data:
            return None, None
        
        df = pd.DataFrame(historical_data)
        
        # Create features
        features = []
        targets = []
        
        if position == 'P':
            # Pitcher features
            for _, row in df.iterrows():
                features.append([
                    row['year'],
                    row.get('strikeouts', 0),
                    row.get('earned_runs_allowed', 0),
                    row.get('hits_allowed', 0),
                    row.get('games', 1)
                ])
                targets.append(row.get('strikeouts', 0))  # Predict strikeouts
        else:
            # Batter features
            for _, row in df.iterrows():
                features.append([
                    row['year'],
                    row.get('hits', 0),
                    row.get('rbis', 0),
                    row.get('runs', 0),
                    row.get('total_bases', 0),
                    row.get('games', 1)
                ])
                targets.append(row.get('hits', 0))  # Predict hits
        
        return np.array(features), np.array(targets)
    
    def train_model(self, position, prop_type):
        """Train ML model for specific position and prop type"""
        try:
            # This would be trained on historical data
            # For now, create a simple model
            model = RandomForestRegressor(n_estimators=100, random_state=42)
            
            # In real implementation, you'd train on historical data
            # For now, return a placeholder model
            return model
            
        except Exception as e:
            print(f"❌ Error training model for {position} {prop_type}: {e}")
            return None
    
    def predict_player_prop(self, player_name, team, position, prop_type, historical_data):
        """Predict player prop using ML"""
        try:
            if not historical_data:
                return None
            
            df = pd.DataFrame(historical_data)
            
            # Create features
            features = []
            targets = []
            
            if position == 'P':
                # Pitcher features
                for _, row in df.iterrows():
                    features.append([
                        row['year'],
                        row.get('strikeouts', 0),
                        row.get('earned_runs_allowed', 0),
                        row.get('hits_allowed', 0),
                        row.get('games', 1)
                    ])
                    
                    # Target based on prop type
                    if prop_type == 'STRIKEOUTS':
                        targets.append(row.get('strikeouts', 0))
                    elif prop_type == 'EARNED_RUNS_ALLOWED':
                        targets.append(row.get('earned_runs_allowed', 0))
                    elif prop_type == 'HITS_ALLOWED':
                        targets.append(row.get('hits_allowed', 0))
            else:
                # Batter features
                for _, row in df.iterrows():
                    features.append([
                        row['year'],
                        row.get('hits', 0),
                        row.get('rbis', 0),
                        row.get('runs', 0),
                        row.get('total_bases', 0),
                        row.get('games', 1)
                    ])
                    
                    # Target based on prop type
                    if prop_type == 'HITS':
                        targets.append(row.get('hits', 0))
                    elif prop_type == 'RBIS':
                        targets.append(row.get('rbis', 0))
                    elif prop_type == 'RUNS':
                        targets.append(row.get('runs', 0))
                    elif prop_type == 'TOTAL_BASES':
                        targets.append(row.get('total_bases', 0))
            
            if len(features) < 2:
                print(f"⚠️ Insufficient data for {player_name} {prop_type}")
                return None
            
            # Train model
            model = RandomForestRegressor(n_estimators=100, random_state=42)
            model.fit(features, targets)
            
            # Predict based on recent performance
            recent_features = features[-1:]  # Use most recent data
            prediction = model.predict(recent_features)[0]
            
            # Calculate implied probability based on historical variance
            if len(targets) > 1:
                std_dev = np.std(targets)
                mean_val = np.mean(targets)
                
                # Calculate probability of exceeding prediction
                z_score = (prediction - mean_val) / std_dev if std_dev > 0 else 0
                implied_prob = 1 - (0.5 * (1 + np.tanh(z_score)))
                
                return {
                    'prediction': prediction,
                    'implied_probability': implied_prob,
                    'confidence': model.score(features, targets)
                }
            else:
                return {
                    'prediction': prediction,
                    'implied_probability': 0.5,
                    'confidence': 0.5
                }
                
        except Exception as e:
            print(f"❌ Error predicting prop for {player_name} {prop_type}: {e}")
            return None
    
    def calculate_prop_line(self, prediction, implied_prob, target_prob, prop_type):
        """Calculate prop line to achieve target probability"""
        try:
            # For baseball props, we need realistic ranges
            if prop_type == "HITS":
                # Hits per game typically 0-4, season total 0-200
                base_prediction = prediction / 162  # Convert season total to per-game
                std_dev = 0.8  # Typical variance for hits per game
            elif prop_type == "RBIS":
                # RBIs per game typically 0-4, season total 0-150
                base_prediction = prediction / 162
                std_dev = 0.7
            elif prop_type == "RUNS":
                # Runs per game typically 0-3, season total 0-120
                base_prediction = prediction / 162
                std_dev = 0.6
            elif prop_type == "TOTAL_BASES":
                # Total bases per game typically 0-8, season total 0-300
                base_prediction = prediction / 162
                std_dev = 1.2
            elif prop_type == "STRIKEOUTS":
                # Strikeouts per game typically 3-12, season total 100-300
                base_prediction = prediction / 30  # Convert season total to per-game
                std_dev = 2.0
            elif prop_type == "EARNED_RUNS_ALLOWED":
                # ER per game typically 0-6, season total 0-100
                base_prediction = prediction / 30
                std_dev = 1.5
            elif prop_type == "HITS_ALLOWED":
                # Hits allowed per game typically 3-12, season total 100-250
                base_prediction = prediction / 30
                std_dev = 2.0
            else:
                base_prediction = prediction
                std_dev = prediction * 0.15
            
            # Calculate z-score needed for target probability
            if target_prob == 0.75:  # EASY - 75% probability
                z_score = -0.67  # 75th percentile
            elif target_prob == 0.45:  # MEDIUM - 45% probability  
                z_score = 0.13   # 45th percentile
            elif target_prob == 0.15:  # HARD - 15% probability
                z_score = 1.04   # 15th percentile
            else:
                z_score = 0
            
            # Calculate line value based on z-score
            line = base_prediction + (z_score * std_dev)
            
            # Ensure realistic bounds
            if prop_type in ["HITS", "RBIS", "RUNS"]:
                line = max(0.5, min(4.0, line))  # 0.5 to 4.0 range
            elif prop_type == "TOTAL_BASES":
                line = max(0.5, min(8.0, line))  # 0.5 to 8.0 range
            elif prop_type == "STRIKEOUTS":
                line = max(3.0, min(12.0, line))  # 3.0 to 12.0 range
            elif prop_type in ["EARNED_RUNS_ALLOWED", "HITS_ALLOWED"]:
                line = max(0.5, min(8.0, line))  # 0.5 to 8.0 range
            
            # Round to nearest 0.5
            return round(line * 2) / 2
            
        except Exception as e:
            print(f"❌ Error calculating prop line: {e}")
            return 1.5  # Default fallback
    
    def generate_props_for_player(self, player, game_info, historical_data):
        """Generate props for a specific player"""
        props = []
        
        position = player['position']
        player_name = player['name']
        team = player['team']
        
        # Determine prop types based on position
        if position == 'P':
            prop_types = ['STRIKEOUTS', 'EARNED_RUNS_ALLOWED', 'HITS_ALLOWED']
        else:
            prop_types = ['HITS', 'RBIS', 'RUNS', 'TOTAL_BASES']
        
        # Determine if player is home or away
        is_home = team == game_info['home_team']
        opponent = game_info['away_team'] if is_home else game_info['home_team']
        
        # Format opponent display
        if is_home:
            opponent_display = f"vs {opponent}"
        else:
            opponent_display = f"@ {opponent}"
        
        # Track if we've already generated an EASY prop for this player
        easy_prop_generated = False
        
        for prop_type in prop_types:
            # Predict prop using ML
            prediction_result = self.predict_player_prop(
                player_name, team, position, prop_type, historical_data
            )
            
            if prediction_result:
                # Generate props for different difficulty levels
                difficulties = [
                    ('EASY', 0.75),    # 75% probability
                    ('MEDIUM', 0.45),  # 45% probability
                    ('HARD', 0.15)     # 15% probability
                ]
                
                for difficulty, target_prob in difficulties:
                    # Skip EASY props if we've already generated one for this player
                    if difficulty == 'EASY' and easy_prop_generated:
                        continue
                    
                    line_value = self.calculate_prop_line(
                        prediction_result['prediction'],
                        prediction_result['implied_probability'],
                        target_prob,
                        prop_type
                    )
                    
                    props.append({
                        'player_name': player_name,
                        'team': team,
                        'position': position,
                        'prop_type': prop_type,
                        'line_value': line_value,
                        'difficulty': difficulty,
                        'implied_probability': target_prob,
                        'opponent': opponent_display,
                        'game_time': game_info['game_time'],
                        'prediction': prediction_result['prediction'],
                        'confidence': prediction_result['confidence']
                    })
                    
                    # Mark that we've generated an EASY prop for this player
                    if difficulty == 'EASY':
                        easy_prop_generated = True
        
        return props
    
    def generate_today_props(self):
        """Generate props for today's games"""
        print("🚀 Starting ML-based prop generation for today...")
        
        # Get today's date
        today = datetime.now()
        target_date = today.strftime('%Y-%m-%d')
        
        # Scrape MLB games from today's schedule
        mlb_games = self.scrape_mlb_games(target_date)
        
        all_props = []
        
        for game in mlb_games:
            print(f"📊 Processing game: {game['away_team']} @ {game['home_team']}")
            
            # Get lineups for both teams from MLB.com/scores
            lineups = self.scrape_mlb_lineups(game)
            away_players = lineups['away_team']['batters'] + lineups['away_team']['pitchers']
            home_players = lineups['home_team']['batters'] + lineups['home_team']['pitchers']
            
            all_players = away_players + home_players
            
            for player in all_players:
                print(f"🔍 Processing player: {player['name']} ({player['position']})")
                
                # Get historical data
                historical_data = self.get_player_historical_data(
                    player['name'], player['team'], player['position']
                )
                
                if historical_data:
                    # Generate props for player
                    player_props = self.generate_props_for_player(
                        player, game, historical_data
                    )
                    
                    all_props.extend(player_props)
                    print(f"✅ Generated {len(player_props)} props for {player['name']}")
                else:
                    print(f"⚠️ No historical data for {player['name']}")
                
                time.sleep(0.5)  # Be respectful to servers
        
        print(f"🎯 Generated {len(all_props)} total props")
        return all_props

    def scrape_mlb_lineups(self, game_info):
        """Scrape lineups from MLB.com/scores for a specific game"""
        try:
            away_team = game_info['away_team']
            home_team = game_info['home_team']
            
            print(f"🔍 Scraping lineups for {away_team} @ {home_team}")
            
            # Get lineups from MLB.com/scores game preview pages
            lineups = {
                'away_team': {
                    'batters': self.get_team_lineup_from_mlb(away_team, game_info),
                    'pitchers': [game_info['away_pitcher']] if game_info['away_pitcher'] != 'TBD' else []
                },
                'home_team': {
                    'batters': self.get_team_lineup_from_mlb(home_team, game_info),
                    'pitchers': [game_info['home_pitcher']] if game_info['home_pitcher'] != 'TBD' else []
                }
            }
            
            return lineups
            
        except Exception as e:
            print(f"❌ Error scraping lineups: {e}")
            return {'away_team': {'batters': [], 'pitchers': []}, 'home_team': {'batters': [], 'pitchers': []}}
    
    def get_team_lineup_from_mlb(self, team, game_info):
        """Get team lineup from MLB.com/scores game preview"""
        try:
            # Try to get lineup from the game preview page
            # MLB.com/scores has "Preview" links that lead to detailed game pages with lineups
            away_team = game_info['away_team']
            home_team = game_info['home_team']
            
            # Construct URL for game preview (this would need to be adapted based on actual MLB.com structure)
            # For now, we'll try to scrape from the main scores page
            url = "https://www.mlb.com/scores"
            
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for lineup information in the game cards
            # This is a placeholder - would need to be adapted based on actual MLB.com structure
            lineup = []
            
            # Try to find lineup data in the game cards
            game_containers = soup.find_all('div', class_=lambda x: x and ('game' in x.lower() or 'card' in x.lower()))
            
            for container in game_containers:
                # Look for team names to match our game
                team_elements = container.find_all(['span', 'div'], string=re.compile(f'({away_team}|{home_team})', re.I))
                
                if team_elements:
                    # Look for lineup information in this game card
                    # This would need to be adapted based on actual MLB.com structure
                    pass
            
            return lineup
            
        except Exception as e:
            print(f"❌ Error getting lineup for {team}: {e}")
            return []
    
    def get_team_batters(self, team):
        """Get batters for a team from MLB.com (placeholder for real implementation)"""
        # This would scrape real lineup data from MLB.com
        # For now, return empty list to avoid sample data
        return []

if __name__ == "__main__":
    generator = MLPropGenerator()
    props = generator.generate_today_props()
    
    print(f"\n📋 Generated {len(props)} props for today's games")
    if props:
        print("Sample props:")
        for prop in props[:5]:
            print(f"  • {prop['player_name']} ({prop['position']}) - {prop['prop_type']} {prop['line_value']} ({prop['difficulty']}) - {prop['opponent']}")
    else:
        print("No props generated - no games found or insufficient data") 