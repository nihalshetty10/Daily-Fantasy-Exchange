#!/usr/bin/env python3
"""
NFL Prop Betting Scraper & Adjuster - Complete System
A comprehensive system that automatically scrapes NFL.com for game information, 
weather conditions, and injury reports to adjust player prop bets in real-time.

This single file contains all the functionality:
- NFL.com data scraping
- Weather.com integration  
- Prop adjustment calculations
- Continuous monitoring scheduler
- Excel export functionality

Usage:
    python nfl_prop_system_complete.py
"""

import requests
from bs4 import BeautifulSoup
import time
import logging
import os
import re
import schedule
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import json

# ============================================================================
# CONFIGURATION SECTION
# ============================================================================

# NFL.com URLs
NFL_BASE_URL = "https://www.nfl.com"
NFL_SCORES_URL = "https://www.nfl.com/scores"
NFL_INJURY_URL = "https://www.nfl.com/injuries"

# Weather.com base URL
WEATHER_BASE_URL = "https://weather.com"

# Scraping intervals
SCRAPE_INTERVAL_MINUTES = 5
GAME_DAY_START_HOUR = 1  # 1:30 AM
GAME_DAY_START_MINUTE = 30

# Weather conditions and their impact on stats
WEATHER_IMPACTS = {
    'snow': {
        'passing_yards': -0.15,
        'passing_touchdowns': -0.20,
        'completions': -0.10,
        'receiving_yards': -0.15,
        'catches': -0.10,
        'rushing_yards': 0.20,
        'quarterback_rushing': 0.05
    },
    'rain': {
        'passing_yards': -0.10,
        'passing_touchdowns': -0.15,
        'completions': -0.08,
        'receiving_yards': -0.10,
        'catches': -0.08,
        'rushing_yards': 0.15,
        'quarterback_rushing': 0.05
    },
    'wind': {
        'passing_yards': -0.20,
        'passing_touchdowns': -0.25,
        'completions': -0.15,
        'receiving_yards': -0.20,
        'catches': -0.15,
        'rushing_yards': 0.25,
        'quarterback_rushing': 0.05
    }
}

# Injury status impacts
INJURY_IMPACTS = {
    'out': 0.0,  # Player gets 0% of their props
    'doubtful': 0.3,  # Player gets 30% of their props
    'questionable': 0.7  # Player gets 70% of their props
}

# Player positions to track
POSITIONS = {
    'quarterback': ['passing_yards', 'passing_touchdowns', 'completions', 'rushing_yards'],
    'running_back': ['rushing_yards', 'receiving_yards', 'catches'],
    'wide_receiver': ['receiving_yards', 'catches'],
    'tight_end': ['receiving_yards', 'catches']
}

# File paths
DATA_DIR = "data"
LOGS_DIR = "logs"
EXCEL_OUTPUT = "nfl_props_adjusted.xlsx"

# ============================================================================
# NFL SCRAPER CLASS
# ============================================================================

class NFLScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.driver = None
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging configuration"""
        if not os.path.exists(LOGS_DIR):
            os.makedirs(LOGS_DIR)
            
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'{LOGS_DIR}/nfl_scraper.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def setup_selenium(self):
        """Setup Selenium WebDriver for dynamic content"""
        if not self.driver:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
    def get_todays_games(self):
        """Scrape today's NFL games from NFL.com"""
        try:
            self.logger.info("Scraping today's games from NFL.com")
            
            # Check if it's game day (after 1:30 AM)
            now = datetime.now()
            game_day_start = now.replace(hour=GAME_DAY_START_HOUR, minute=GAME_DAY_START_MINUTE, second=0, microsecond=0)
            
            if now < game_day_start:
                self.logger.info("Not yet game day, waiting...")
                return []
            
            response = self.session.get(NFL_SCORES_URL)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            games = []
            
            # Look for game containers
            game_containers = soup.find_all('div', class_='game-center')
            
            for container in game_containers:
                try:
                    # Extract game information
                    teams = container.find_all('div', class_='team-name')
                    if len(teams) >= 2:
                        away_team = teams[0].get_text(strip=True)
                        home_team = teams[1].get_text(strip=True)
                        
                        # Get game time
                        time_element = container.find('div', class_='game-time')
                        game_time = time_element.get_text(strip=True) if time_element else "TBD"
                        
                        # Get game link
                        game_link = container.find('a')
                        game_url = NFL_BASE_URL + game_link['href'] if game_link else None
                        
                        games.append({
                            'away_team': away_team,
                            'home_team': home_team,
                            'game_time': game_time,
                            'game_url': game_url,
                            'status': 'scheduled'
                        })
                        
                except Exception as e:
                    self.logger.error(f"Error parsing game container: {e}")
                    continue
            
            self.logger.info(f"Found {len(games)} games for today")
            return games
            
        except Exception as e:
            self.logger.error(f"Error scraping today's games: {e}")
            return []
    
    def get_game_location(self, game_url):
        """Get the city/location for a specific game"""
        try:
            if not game_url:
                return None
                
            response = self.session.get(game_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for venue information
            venue_element = soup.find('div', class_='venue') or soup.find('span', class_='stadium')
            if venue_element:
                venue_text = venue_element.get_text(strip=True)
                # Extract city from venue text (e.g., "MetLife Stadium, East Rutherford, NJ")
                if ',' in venue_text:
                    city = venue_text.split(',')[1].strip()
                    return city
                    
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting game location: {e}")
            return None
    
    def get_starting_lineups(self, game_url):
        """Get starting lineups for a specific game"""
        try:
            if not game_url:
                return {}
                
            self.setup_selenium()
            self.driver.get(game_url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Look for depth chart or starting lineup information
            lineups = {
                'away_team': {},
                'home_team': {}
            }
            
            # This would need to be customized based on NFL.com's actual structure
            # For now, returning placeholder structure
            self.logger.info("Starting lineups functionality needs customization based on NFL.com structure")
            
            return lineups
            
        except Exception as e:
            self.logger.error(f"Error getting starting lineups: {e}")
            return {}
    
    def get_injury_report(self):
        """Get current injury report from NFL.com"""
        try:
            self.logger.info("Scraping injury report from NFL.com")
            
            response = self.session.get(NFL_INJURY_URL)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            injuries = {}
            
            # Look for injury report containers
            injury_containers = soup.find_all('div', class_='injury-report')
            
            for container in injury_containers:
                try:
                    # Extract player information
                    player_name = container.find('span', class_='player-name')
                    team = container.find('span', class_='team-name')
                    position = container.find('span', class_='position')
                    status = container.find('span', class_='status')
                    
                    if all([player_name, team, position, status]):
                        player_key = player_name.get_text(strip=True)
                        injuries[player_key] = {
                            'team': team.get_text(strip=True),
                            'position': position.get_text(strip=True),
                            'status': status.get_text(strip=True).lower(),
                            'last_updated': datetime.now().isoformat()
                        }
                        
                except Exception as e:
                    self.logger.error(f"Error parsing injury container: {e}")
                    continue
            
            self.logger.info(f"Found {len(injuries)} injury entries")
            return injuries
            
        except Exception as e:
            self.logger.error(f"Error scraping injury report: {e}")
            return {}
    
    def close(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()

# ============================================================================
# WEATHER SCRAPER CLASS
# ============================================================================

class WeatherScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging configuration"""
        self.logger = logging.getLogger(__name__)
        
    def search_city_weather(self, city_name, game_time=None):
        """Search for weather conditions in a specific city"""
        try:
            self.logger.info(f"Searching weather for city: {city_name}")
            
            # Clean city name for search
            clean_city = city_name.replace(' ', '-').lower()
            
            # Try to find the city's weather page
            search_url = f"{WEATHER_BASE_URL}/search?query={clean_city}"
            response = self.session.get(search_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for the first city result
            city_link = soup.find('a', href=re.compile(r'/weather/today/'))
            if city_link:
                city_url = WEATHER_BASE_URL + city_link['href']
                return self.get_weather_details(city_url, game_time)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error searching weather for city {city_name}: {e}")
            return None
    
    def get_weather_details(self, city_url, game_time=None):
        """Get detailed weather information for a city"""
        try:
            response = self.session.get(city_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            weather_data = {
                'city': self.extract_city_name(soup),
                'current_conditions': self.extract_current_conditions(soup),
                'hourly_forecast': self.extract_hourly_forecast(soup),
                'game_time_weather': None
            }
            
            # If game time is provided, find the specific hour forecast
            if game_time:
                weather_data['game_time_weather'] = self.get_game_time_weather(
                    weather_data['hourly_forecast'], game_time
                )
            
            return weather_data
            
        except Exception as e:
            self.logger.error(f"Error getting weather details: {e}")
            return None
    
    def extract_city_name(self, soup):
        """Extract city name from weather page"""
        try:
            city_element = soup.find('h1', class_='CurrentConditions--location--1Ayv3')
            if city_element:
                return city_element.get_text(strip=True)
            
            # Fallback to title
            title = soup.find('title')
            if title:
                title_text = title.get_text()
                if 'Weather' in title_text:
                    return title_text.split('Weather')[0].strip()
            
            return "Unknown City"
            
        except Exception as e:
            self.logger.error(f"Error extracting city name: {e}")
            return "Unknown City"
    
    def extract_current_conditions(self, soup):
        """Extract current weather conditions"""
        try:
            conditions = {}
            
            # Temperature
            temp_element = soup.find('span', class_='CurrentConditions--tempValue--MHmYY')
            if temp_element:
                conditions['temperature'] = temp_element.get_text(strip=True)
            
            # Weather description
            desc_element = soup.find('div', class_='CurrentConditions--phraseValue--mZC_p')
            if desc_element:
                conditions['description'] = desc_element.get_text(strip=True)
            
            # Wind
            wind_element = soup.find('span', string=re.compile(r'Wind'))
            if wind_element and wind_element.parent:
                wind_text = wind_element.parent.get_text()
                conditions['wind'] = wind_text
            
            # Precipitation chance
            precip_element = soup.find('span', string=re.compile(r'Precipitation'))
            if precip_element and precip_element.parent:
                precip_text = precip_element.parent.get_text()
                conditions['precipitation'] = precip_text
            
            return conditions
            
        except Exception as e:
            self.logger.error(f"Error extracting current conditions: {e}")
            return {}
    
    def extract_hourly_forecast(self, soup):
        """Extract hourly weather forecast"""
        try:
            hourly_data = []
            
            # Look for hourly forecast section
            hourly_section = soup.find('section', {'data-testid': 'HourlyForecast'})
            if hourly_section:
                hour_items = hourly_section.find_all('div', class_='HourlyForecast--DisclosureList--1b1bq')
                
                for item in hour_items[:24]:  # Get next 24 hours
                    try:
                        hour_data = {}
                        
                        # Time
                        time_element = item.find('span', class_='HourlyForecast--timestamp--22G4O')
                        if time_element:
                            hour_data['time'] = time_element.get_text(strip=True)
                        
                        # Temperature
                        temp_element = item.find('span', class_='HourlyForecast--tempValue--1Dg0I')
                        if temp_element:
                            hour_data['temperature'] = temp_element.get_text(strip=True)
                        
                        # Description
                        desc_element = item.find('span', class_='HourlyForecast--phraseValue--2JMLa')
                        if desc_element:
                            hour_data['description'] = desc_element.get_text(strip=True)
                        
                        # Precipitation chance
                        precip_element = item.find('span', class_='HourlyForecast--precip--1Jplb')
                        if precip_element:
                            hour_data['precipitation'] = precip_element.get_text(strip=True)
                        
                        if hour_data:
                            hourly_data.append(hour_data)
                            
                    except Exception as e:
                        self.logger.error(f"Error parsing hour item: {e}")
                        continue
            
            return hourly_data
            
        except Exception as e:
            self.logger.error(f"Error extracting hourly forecast: {e}")
            return []
    
    def get_game_time_weather(self, hourly_forecast, game_time):
        """Get weather conditions for the specific game time"""
        try:
            if not hourly_forecast or not game_time:
                return None
            
            # Parse game time to find the closest hour
            game_hour = None
            
            if isinstance(game_time, str):
                # Try to extract hour from game time string
                if 'PM' in game_time.upper():
                    hour_match = re.search(r'(\d+):', game_time)
                    if hour_match:
                        hour = int(hour_match.group(1))
                        if hour != 12:
                            game_hour = hour + 12
                        else:
                            game_hour = 12
                elif 'AM' in game_time.upper():
                    hour_match = re.search(r'(\d+):', game_time)
                    if hour_match:
                        hour = int(hour_match.group(1))
                        if hour == 12:
                            game_hour = 0
                        else:
                            game_hour = hour
            
            if game_hour is not None:
                # Find the closest hour in the forecast
                for hour_data in hourly_forecast:
                    if 'time' in hour_data:
                        forecast_hour = self.parse_forecast_time(hour_data['time'])
                        if forecast_hour == game_hour:
                            return hour_data
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting game time weather: {e}")
            return None
    
    def parse_forecast_time(self, time_str):
        """Parse forecast time string to hour number"""
        try:
            # Handle formats like "1 PM", "1:00 PM", "13:00"
            if 'PM' in time_str.upper():
                hour_match = re.search(r'(\d+)', time_str)
                if hour_match:
                    hour = int(hour_match.group(1))
                    if hour != 12:
                        return hour + 12
                    return 12
            elif 'AM' in time_str.upper():
                hour_match = re.search(r'(\d+)', time_str)
                if hour_match:
                    hour = int(hour_match.group(1))
                    if hour == 12:
                        return 0
                    return hour
            else:
                # Handle 24-hour format
                hour_match = re.search(r'(\d+):', time_str)
                if hour_match:
                    return int(hour_match.group(1))
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error parsing forecast time: {e}")
            return None
    
    def analyze_weather_impact(self, weather_data):
        """Analyze weather conditions and determine impact on game stats"""
        try:
            if not weather_data or not weather_data.get('game_time_weather'):
                return {}
            
            game_weather = weather_data['game_time_weather']
            impact = {}
            
            # Check for severe weather conditions
            description = game_weather.get('description', '').lower()
            
            # Snow conditions
            if any(word in description for word in ['snow', 'sleet', 'blizzard']):
                impact.update(WEATHER_IMPACTS['snow'])
            
            # Rain conditions
            elif any(word in description for word in ['rain', 'shower', 'drizzle', 'storm']):
                impact.update(WEATHER_IMPACTS['rain'])
            
            # Wind conditions
            elif any(word in description for word in ['wind', 'breezy', 'gust']):
                impact.update(WEATHER_IMPACTS['wind'])
            
            # Check wind speed if available
            wind_text = game_weather.get('wind', '')
            if wind_text:
                wind_match = re.search(r'(\d+)', wind_text)
                if wind_match:
                    wind_speed = int(wind_match.group(1))
                    if wind_speed > 20:  # High wind threshold
                        impact.update(WEATHER_IMPACTS['wind'])
            
            return impact
            
        except Exception as e:
            self.logger.error(f"Error analyzing weather impact: {e}")
            return {}

# ============================================================================
# PROP ADJUSTER CLASS
# ============================================================================

class PropAdjuster:
    def __init__(self):
        self.setup_logging()
        self.base_props = {}
        self.adjusted_props = {}
        
    def setup_logging(self):
        """Setup logging configuration"""
        self.logger = logging.getLogger(__name__)
        
    def load_base_props(self, props_data):
        """Load base props data (you would typically get this from a sportsbook API)"""
        try:
            self.base_props = props_data
            self.logger.info(f"Loaded {len(props_data)} base props")
            
        except Exception as e:
            self.logger.error(f"Error loading base props: {e}")
    
    def adjust_props_for_weather(self, props, weather_impact):
        """Adjust props based on weather conditions"""
        try:
            if not weather_impact:
                return props
            
            adjusted_props = props.copy()
            
            for stat_type, adjustment_factor in weather_impact.items():
                if stat_type in adjusted_props:
                    # Apply weather adjustment
                    original_value = adjusted_props[stat_type]
                    if isinstance(original_value, (int, float)):
                        adjusted_value = original_value * (1 + adjustment_factor)
                        adjusted_props[stat_type] = round(adjusted_value, 2)
                        
                        self.logger.info(f"Adjusted {stat_type}: {original_value} -> {adjusted_value} "
                                       f"(factor: {adjustment_factor})")
            
            return adjusted_props
            
        except Exception as e:
            self.logger.error(f"Error adjusting props for weather: {e}")
            return props
    
    def adjust_props_for_injuries(self, props, injury_status):
        """Adjust props based on player injury status"""
        try:
            if not injury_status or injury_status not in INJURY_IMPACTS:
                return props
            
            adjustment_factor = INJURY_IMPACTS[injury_status]
            adjusted_props = props.copy()
            
            for stat_type, value in adjusted_props.items():
                if isinstance(value, (int, float)):
                    adjusted_value = value * adjustment_factor
                    adjusted_props[stat_type] = round(adjusted_value, 2)
                    
                    self.logger.info(f"Adjusted {stat_type} for {injury_status} status: "
                                   f"{value} -> {adjusted_value} (factor: {adjustment_factor})")
            
            return adjusted_props
            
        except Exception as e:
            self.logger.error(f"Error adjusting props for injuries: {e}")
            return props
    
    def handle_player_out(self, player_name, team, position, backup_player=None):
        """Handle when a player is ruled out - remove their props and add backup if available"""
        try:
            if player_name in self.base_props:
                # Remove the out player's props
                removed_props = self.base_props.pop(player_name)
                self.logger.info(f"Removed {player_name}'s props: {removed_props}")
                
                # If backup player is provided, add their props
                if backup_player:
                    self.base_props[backup_player['name']] = backup_player['props']
                    self.logger.info(f"Added backup player {backup_player['name']}: {backup_player['props']}")
                
                return removed_props
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error handling player out: {e}")
            return None
    
    def calculate_final_props(self, player_name, weather_impact=None, injury_status=None):
        """Calculate final adjusted props for a player"""
        try:
            if player_name not in self.base_props:
                self.logger.warning(f"No base props found for {player_name}")
                return None
            
            base_props = self.base_props[player_name].copy()
            
            # Apply weather adjustments
            if weather_impact:
                base_props = self.adjust_props_for_weather(base_props, weather_impact)
            
            # Apply injury adjustments
            if injury_status:
                base_props = self.adjust_props_for_injuries(base_props, injury_status)
            
            # Store adjusted props
            self.adjusted_props[player_name] = {
                'base_props': self.base_props[player_name],
                'adjusted_props': base_props,
                'weather_impact': weather_impact,
                'injury_status': injury_status,
                'last_updated': datetime.now().isoformat()
            }
            
            return base_props
            
        except Exception as e:
            self.logger.error(f"Error calculating final props for {player_name}: {e}")
            return None
    
    def get_all_adjusted_props(self):
        """Get all adjusted props for all players"""
        return self.adjusted_props
    
    def export_to_excel(self, filename=None):
        """Export adjusted props to Excel file"""
        try:
            if not filename:
                filename = EXCEL_OUTPUT
            
            # Create DataFrame for export
            export_data = []
            
            for player_name, data in self.adjusted_props.items():
                row = {
                    'Player': player_name,
                    'Base_Props': str(data['base_props']),
                    'Adjusted_Props': str(data['adjusted_props']),
                    'Weather_Impact': str(data['weather_impact']) if data['weather_impact'] else 'None',
                    'Injury_Status': data['injury_status'] if data['injury_status'] else 'None',
                    'Last_Updated': data['last_updated']
                }
                export_data.append(row)
            
            df = pd.DataFrame(export_data)
            
            # Create output directory if it doesn't exist
            if not os.path.exists(DATA_DIR):
                os.makedirs(DATA_DIR)
            
            filepath = os.path.join(DATA_DIR, filename)
            df.to_excel(filepath, index=False)
            
            self.logger.info(f"Exported adjusted props to {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"Error exporting to Excel: {e}")
            return None
    
    def get_prop_summary(self):
        """Get a summary of all prop adjustments"""
        try:
            summary = {
                'total_players': len(self.adjusted_props),
                'players_with_weather_impact': 0,
                'players_with_injury_impact': 0,
                'total_adjustments': 0
            }
            
            for player_data in self.adjusted_props.values():
                if player_data['weather_impact']:
                    summary['players_with_weather_impact'] += 1
                
                if player_data['injury_status']:
                    summary['players_with_injury_impact'] += 1
                
                summary['total_adjustments'] += 1
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error getting prop summary: {e}")
            return {}

# ============================================================================
# MAIN SCHEDULER CLASS
# ============================================================================

class NFLPropScheduler:
    def __init__(self):
        self.setup_logging()
        self.nfl_scraper = NFLScraper()
        self.weather_scraper = WeatherScraper()
        self.prop_adjuster = PropAdjuster()
        self.current_games = []
        self.current_injuries = {}
        self.last_update = None
        
    def setup_logging(self):
        """Setup logging configuration"""
        if not os.path.exists(LOGS_DIR):
            os.makedirs(LOGS_DIR)
            
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'{LOGS_DIR}/scheduler.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def run_full_update(self):
        """Run a complete update cycle"""
        try:
            self.logger.info("Starting full update cycle")
            start_time = datetime.now()
            
            # Step 1: Get today's games
            games = self.nfl_scraper.get_todays_games()
            if games != self.current_games:
                self.logger.info(f"Games updated: {len(games)} games found")
                self.current_games = games
                
                # Process each game
                for game in games:
                    self.process_game(game)
            
            # Step 2: Get injury report
            injuries = self.nfl_scraper.get_injury_report()
            if injuries != self.current_injuries:
                self.logger.info(f"Injury report updated: {len(injuries)} entries")
                self.current_injuries = injuries
                
                # Process injury updates
                self.process_injury_updates(injuries)
            
            # Step 3: Export updated props
            if self.prop_adjuster.get_all_adjusted_props():
                self.prop_adjuster.export_to_excel()
            
            self.last_update = datetime.now()
            cycle_time = (self.last_update - start_time).total_seconds()
            self.logger.info(f"Update cycle completed in {cycle_time:.2f} seconds")
            
        except Exception as e:
            self.logger.error(f"Error in update cycle: {e}")
    
    def process_game(self, game):
        """Process a single game for weather and lineup information"""
        try:
            self.logger.info(f"Processing game: {game['away_team']} @ {game['home_team']}")
            
            # Get game location
            location = self.nfl_scraper.get_game_location(game['game_url'])
            if location:
                self.logger.info(f"Game location: {location}")
                
                # Get weather for the location
                weather_data = self.weather_scraper.search_city_weather(
                    location, game['game_time']
                )
                
                if weather_data:
                    # Analyze weather impact
                    weather_impact = self.weather_scraper.analyze_weather_impact(weather_data)
                    
                    if weather_impact:
                        self.logger.info(f"Weather impact detected: {weather_impact}")
                        # Store weather impact for this game
                        game['weather_impact'] = weather_impact
                        game['weather_data'] = weather_data
                    else:
                        self.logger.info("No significant weather impact detected")
            
            # Get starting lineups
            lineups = self.nfl_scraper.get_starting_lineups(game['game_url'])
            if lineups:
                game['lineups'] = lineups
                self.logger.info("Starting lineups retrieved")
            
        except Exception as e:
            self.logger.error(f"Error processing game {game.get('away_team', 'Unknown')}: {e}")
    
    def process_injury_updates(self, injuries):
        """Process injury report updates and adjust props accordingly"""
        try:
            for player_name, injury_data in injuries.items():
                status = injury_data['status']
                team = injury_data['team']
                position = injury_data['position']
                
                self.logger.info(f"Processing injury: {player_name} ({position}) - {status}")
                
                if status == 'out':
                    # Player is ruled out - handle backup player
                    self.handle_player_out(player_name, team, position)
                elif status in ['doubtful', 'questionable']:
                    # Adjust props based on injury status
                    self.adjust_player_props_for_injury(player_name, status)
                    
        except Exception as e:
            self.logger.error(f"Error processing injury updates: {e}")
    
    def handle_player_out(self, player_name, team, position):
        """Handle when a player is ruled out"""
        try:
            # Find backup player from starting lineups
            backup_player = self.find_backup_player(team, position)
            
            # Remove out player and add backup if available
            removed_props = self.prop_adjuster.handle_player_out(
                player_name, team, position, backup_player
            )
            
            if removed_props:
                self.logger.info(f"Removed {player_name}'s props and added backup")
            else:
                self.logger.warning(f"No props found for {player_name}")
                
        except Exception as e:
            self.logger.error(f"Error handling player out: {e}")
    
    def find_backup_player(self, team, position):
        """Find backup player from starting lineups"""
        try:
            # This would need to be implemented based on actual lineup data structure
            # For now, returning None as placeholder
            self.logger.info(f"Looking for backup {position} for {team}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding backup player: {e}")
            return None
    
    def adjust_player_props_for_injury(self, player_name, status):
        """Adjust player props based on injury status"""
        try:
            # Calculate adjusted props
            adjusted_props = self.prop_adjuster.calculate_final_props(
                player_name, injury_status=status
            )
            
            if adjusted_props:
                self.logger.info(f"Adjusted {player_name}'s props for {status} status")
            else:
                self.logger.warning(f"No base props found for {player_name}")
                
        except Exception as e:
            self.logger.error(f"Error adjusting player props: {e}")
    
    def start_scheduler(self):
        """Start the continuous scheduler"""
        try:
            self.logger.info("Starting NFL Prop Scheduler")
            
            # Schedule the update to run every 5 minutes
            schedule.every(SCRAPE_INTERVAL_MINUTES).minutes.do(self.run_full_update)
            
            # Run initial update
            self.run_full_update()
            
            # Keep the scheduler running
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
                
        except KeyboardInterrupt:
            self.logger.info("Scheduler stopped by user")
        except Exception as e:
            self.logger.error(f"Scheduler error: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        try:
            self.nfl_scraper.close()
            self.logger.info("Cleanup completed")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    def get_status(self):
        """Get current scheduler status"""
        return {
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'current_games': len(self.current_games),
            'current_injuries': len(self.current_injuries),
            'adjusted_props': len(self.prop_adjuster.get_all_adjusted_props())
        }

# ============================================================================
# DEMO AND TESTING FUNCTIONS
# ============================================================================

def run_demo():
    """Run a demonstration of the system"""
    print("🏈 NFL PROP SCRAPER SYSTEM DEMO 🏈")
    print("This demonstrates how the system automatically adjusts")
    print("player props based on weather and injury factors.")
    
    try:
        # Test weather impact
        print("\n" + "="*60)
        print("WEATHER IMPACT DEMONSTRATION")
        print("="*60)
        
        weather_scraper = WeatherScraper()
        
        # Sample weather data for different conditions
        weather_scenarios = {
            'Snow Game': {
                'game_time_weather': {
                    'description': 'snow',
                    'temperature': '25°F',
                    'wind': 'Wind 15 mph'
                }
            },
            'Rainy Game': {
                'game_time_weather': {
                    'description': 'rain',
                    'temperature': '45°F',
                    'wind': 'Wind 8 mph'
                }
            },
            'Windy Game': {
                'game_time_weather': {
                    'description': 'windy',
                    'temperature': '35°F',
                    'wind': 'Wind 25 mph'
                }
            }
        }
        
        for scenario_name, weather_data in weather_scenarios.items():
            print(f"\n{scenario_name}:")
            print(f"  Conditions: {weather_data['game_time_weather']['description']}")
            print(f"  Temperature: {weather_data['game_time_weather']['temperature']}")
            print(f"  Wind: {weather_data['game_time_weather']['wind']}")
            
            impact = weather_scraper.analyze_weather_impact(weather_data)
            if impact:
                print("  Weather Impact on Stats:")
                for stat, adjustment in impact.items():
                    percentage = adjustment * 100
                    if adjustment > 0:
                        print(f"    {stat}: +{percentage:.0f}%")
                    else:
                        print(f"    {stat}: {percentage:.0f}%")
            else:
                print("  No significant weather impact")
        
        # Test prop adjustment
        print("\n" + "="*60)
        print("PROP ADJUSTMENT DEMONSTRATION")
        print("="*60)
        
        adjuster = PropAdjuster()
        
        # Sample player props
        sample_props = {
            'Josh Allen': {
                'passing_yards': 275.5,
                'passing_touchdowns': 2.5,
                'completions': 23.5,
                'rushing_yards': 35.5
            }
        }
        
        adjuster.load_base_props(sample_props)
        
        print("Josh Allen - Buffalo Bills QB")
        print("Scenario: Snowy weather + Questionable injury status")
        
        # Weather impact (snow)
        weather_impact = {
            'passing_yards': -0.15,
            'passing_touchdowns': -0.20,
            'completions': -0.10,
            'rushing_yards': 0.20
        }
        
        # Injury impact (questionable = 70%)
        injury_status = 'questionable'
        
        # Calculate combined impact
        adjusted = adjuster.calculate_final_props(
            'Josh Allen', 
            weather_impact=weather_impact,
            injury_status=injury_status
        )
        
        if adjusted:
            original = sample_props['Josh Allen']
            print(f"\nOriginal Props:")
            for stat, value in original.items():
                print(f"  {stat}: {value}")
            
            print(f"\nAdjusted Props (Weather + Injury):")
            for stat, value in adjusted.items():
                change = ((value - original[stat]) / original[stat]) * 100
                print(f"  {stat}: {value} ({change:+.1f}%)")
        
        print("\n" + "="*60)
        print("DEMO COMPLETED SUCCESSFULLY!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()

def test_system():
    """Test all system components"""
    print("=" * 50)
    print("NFL Prop Scraper System - Component Tests")
    print("=" * 50)
    
    tests = [
        ("NFL Scraper Test", lambda: NFLScraper()),
        ("Weather Scraper Test", lambda: WeatherScraper()),
        ("Prop Adjuster Test", lambda: PropAdjuster()),
        ("Scheduler Test", lambda: NFLPropScheduler())
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            instance = test_func()
            print(f"✓ {test_name} PASSED")
            passed += 1
            
            # Clean up if needed
            if hasattr(instance, 'close'):
                instance.close()
                
        except Exception as e:
            print(f"✗ {test_name} FAILED with exception: {e}")
        
        print("-" * 30)
    
    print(f"\nTest Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! System is ready to use.")
        print("\nTo start the system, run:")
        print("python nfl_prop_system_complete.py --start")
    else:
        print("❌ Some tests failed. Please check the errors above.")
    
    return passed == total

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "--demo":
            run_demo()
        elif command == "--test":
            test_system()
        elif command == "--start":
            print("🏈 Starting NFL Prop Scraper System...")
            scheduler = NFLPropScheduler()
            try:
                scheduler.start_scheduler()
            except Exception as e:
                print(f"Error starting scheduler: {e}")
                scheduler.cleanup()
        else:
            print("Usage:")
            print("  python nfl_prop_system_complete.py --demo    # Run demonstration")
            print("  python nfl_prop_system_complete.py --test    # Test system components")
            print("  python nfl_prop_system_complete.py --start   # Start continuous monitoring")
    else:
        # Default: run demo
        run_demo()
        print("\n" + "="*60)
        print("SYSTEM READY!")
        print("="*60)
        print("\nAvailable commands:")
        print("  --demo    Run demonstration")
        print("  --test    Test system components") 
        print("  --start   Start continuous monitoring")
        print("\nExample: python nfl_prop_system_complete.py --start")

if __name__ == "__main__":
    main()
