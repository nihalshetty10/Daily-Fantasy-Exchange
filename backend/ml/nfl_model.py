"""
NFL LSTM Model for Player Prop Predictions
Uses LSTM to analyze player performance trends and predict prop values
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import logging
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.optimizers import Adam
import tensorflow as tf

logger = logging.getLogger(__name__)

class NFLModel:
    def __init__(self):
        self.scaler = MinMaxScaler()
        self.models = {}
        self.prop_types = ['PASSING_YARDS', 'RUSHING_YARDS', 'RECEIVING_YARDS', 'TOUCHDOWNS', 'INTERCEPTIONS']
        
    def scrape_player_stats(self, player_name, days_back=30):
        """Scrape player's recent performance data from Pro-Football-Reference"""
        try:
            # Search for player on Pro-Football-Reference
            search_url = f"https://www.pro-football-reference.com/search/search.fcgi?search={player_name.replace(' ', '+')}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(search_url, headers=headers)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find player link
            player_link = soup.find('a', href=True)
            if not player_link:
                return None
                
            player_url = f"https://www.pro-football-reference.com{player_link['href']}"
            
            # Get player's game log
            game_log_url = player_url.replace('.htm', '/gamelog/')
            response = requests.get(game_log_url, headers=headers)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Parse game log table
            stats = []
            table = soup.find('table', {'id': 'stats'})
            if table:
                rows = table.find_all('tr')[1:]  # Skip header
                for row in rows[:days_back]:  # Last 30 games
                    cells = row.find_all('td')
                    if len(cells) > 10:
                        game_stats = {
                            'date': cells[0].text.strip(),
                            'passing_yards': float(cells[3].text.strip() or 0),
                            'rushing_yards': float(cells[7].text.strip() or 0),
                            'receiving_yards': float(cells[11].text.strip() or 0),
                            'touchdowns': float(cells[8].text.strip() or 0),
                            'interceptions': float(cells[4].text.strip() or 0)
                        }
                        stats.append(game_stats)
            
            return pd.DataFrame(stats)
            
        except Exception as e:
            logger.error(f"Error scraping stats for {player_name}: {e}")
            return None
    
    def prepare_lstm_data(self, data, sequence_length=10):
        """Prepare data for LSTM model"""
        if len(data) < sequence_length:
            return None, None
            
        # Normalize data
        scaled_data = self.scaler.fit_transform(data)
        
        X, y = [], []
        for i in range(sequence_length, len(scaled_data)):
            X.append(scaled_data[i-sequence_length:i])
            y.append(scaled_data[i])
            
        return np.array(X), np.array(y)
    
    def build_lstm_model(self, input_shape):
        """Build LSTM model for time series prediction"""
        model = Sequential([
            LSTM(50, return_sequences=True, input_shape=input_shape),
            Dropout(0.2),
            LSTM(50, return_sequences=False),
            Dropout(0.2),
            Dense(25),
            Dense(1)
        ])
        
        model.compile(optimizer=Adam(learning_rate=0.001), loss='mse')
        return model
    
    def train_model(self, player_name, prop_type):
        """Train LSTM model for specific player and prop type"""
        try:
            # Get player data
            player_data = self.scrape_player_stats(player_name)
            if player_data is None or len(player_data) < 10:
                return None
            
            # Prepare data for specific prop type
            prop_data = player_data[prop_type.lower()].values.reshape(-1, 1)
            
            # Prepare LSTM data
            X, y = self.prepare_lstm_data(prop_data)
            if X is None:
                return None
            
            # Build and train model
            model = self.build_lstm_model((X.shape[1], X.shape[2]))
            model.fit(X, y, epochs=50, batch_size=32, verbose=0)
            
            return model
            
        except Exception as e:
            logger.error(f"Error training model for {player_name} {prop_type}: {e}")
            return None
    
    def predict(self, player_name, prop_type):
        """Predict prop value using LSTM model"""
        try:
            # Get or train model
            model_key = f"{player_name}_{prop_type}"
            if model_key not in self.models:
                model = self.train_model(player_name, prop_type)
                if model is None:
                    return None
                self.models[model_key] = model
            
            model = self.models[model_key]
            
            # Get recent data for prediction
            player_data = self.scrape_player_stats(player_name, days_back=15)
            if player_data is None:
                return None
            
            prop_data = player_data[prop_type.lower()].values.reshape(-1, 1)
            
            # Prepare input for prediction
            if len(prop_data) < 10:
                return None
                
            recent_data = prop_data[-10:].reshape(1, 10, 1)
            scaled_data = self.scaler.transform(recent_data.reshape(-1, 1))
            scaled_input = scaled_data.reshape(1, 10, 1)
            
            # Make prediction
            prediction = model.predict(scaled_input)
            predicted_value = self.scaler.inverse_transform(prediction)[0][0]
            
            return max(0, round(predicted_value, 1))
            
        except Exception as e:
            logger.error(f"Error predicting for {player_name} {prop_type}: {e}")
            return None
    
    def calculate_implied_probability(self, predicted_value, prop_type, player_name):
        """Calculate implied probability based on LSTM prediction and historical variance"""
        try:
            # Get historical data
            player_data = self.scrape_player_stats(player_name, days_back=50)
            if player_data is None:
                return 0.5
            
            prop_data = player_data[prop_type.lower()].values
            
            # Calculate historical mean and standard deviation
            mean_value = np.mean(prop_data)
            std_value = np.std(prop_data)
            
            if std_value == 0:
                return 0.5
            
            # Calculate probability using normal distribution
            from scipy.stats import norm
            
            # Probability of achieving the predicted value or higher
            z_score = (predicted_value - mean_value) / std_value
            probability = 1 - norm.cdf(z_score)
            
            return max(0.01, min(0.99, probability))
            
        except Exception as e:
            logger.error(f"Error calculating probability: {e}")
            return 0.5
    
    def get_prop_value_at_probability(self, player_name, prop_type, target_probability):
        """Get prop value that corresponds to target probability"""
        try:
            # Get historical data
            player_data = self.scrape_player_stats(player_name, days_back=50)
            if player_data is None:
                return None
            
            prop_data = player_data[prop_type.lower()].values
            
            # Calculate historical mean and standard deviation
            mean_value = np.mean(prop_data)
            std_value = np.std(prop_data)
            
            if std_value == 0:
                return mean_value
            
            # Calculate value at target probability
            from scipy.stats import norm
            
            z_score = norm.ppf(1 - target_probability)
            prop_value = mean_value + (z_score * std_value)
            
            return max(0, round(prop_value, 1))
            
        except Exception as e:
            logger.error(f"Error calculating prop value: {e}")
            return None 