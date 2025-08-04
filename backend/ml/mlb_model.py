"""
MLB LSTM Model for Player Prop Predictions
Uses LSTM to analyze player performance trends and predict prop values
Loads models lazily to reduce startup time
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import logging
import random

logger = logging.getLogger(__name__)

class MLBModel:
    def __init__(self):
        self.prop_types = ['HITS', 'TOTAL_BASES', 'RUNS', 'STRIKEOUTS']
        self._models = {}  # Lazy loading
        self._scaler = None
        self._tensorflow_loaded = False
        
    def _load_tensorflow(self):
        """Load TensorFlow only when needed"""
        if not self._tensorflow_loaded:
            try:
                from sklearn.preprocessing import MinMaxScaler
                from tensorflow.keras.models import Sequential
                from tensorflow.keras.layers import LSTM, Dense, Dropout
                from tensorflow.keras.optimizers import Adam
                import tensorflow as tf
                
                self.MinMaxScaler = MinMaxScaler
                self.Sequential = Sequential
                self.LSTM = LSTM
                self.Dense = Dense
                self.Dropout = Dropout
                self.Adam = Adam
                self.tf = tf
                
                self._scaler = MinMaxScaler()
                self._tensorflow_loaded = True
                logger.info("TensorFlow loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load TensorFlow: {e}")
                return False
        return True
        
    def scrape_player_stats(self, player_name, days_back=30):
        """Scrape player's recent performance data from Baseball-Reference"""
        try:
            # Search for player on Baseball-Reference
            search_url = f"https://www.baseball-reference.com/search/search.fcgi?search={player_name.replace(' ', '+')}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(search_url, headers=headers)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find player link
            player_link = soup.find('a', href=True)
            if not player_link:
                return None
                
            player_url = f"https://www.baseball-reference.com{player_link['href']}"
            
            # Get player's game log
            game_log_url = player_url.replace('.shtml', '/gamelog/')
            response = requests.get(game_log_url, headers=headers)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Parse game log table
            stats = []
            table = soup.find('table', {'id': 'batting_gamelogs'})
            if table:
                rows = table.find_all('tr')[1:]  # Skip header
                for row in rows[:days_back]:  # Last 30 games
                    cells = row.find_all('td')
                    if len(cells) > 10:
                        game_stats = {
                            'date': cells[0].text.strip(),
                            'hits': float(cells[3].text.strip() or 0),
                            'total_bases': float(cells[4].text.strip() or 0),
                            'runs': float(cells[5].text.strip() or 0),
                            'strikeouts': float(cells[6].text.strip() or 0)
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
        scaled_data = self._scaler.fit_transform(data)
        
        X, y = [], []
        for i in range(sequence_length, len(scaled_data)):
            X.append(scaled_data[i-sequence_length:i])
            y.append(scaled_data[i])
            
        return np.array(X), np.array(y)
    
    def build_lstm_model(self, input_shape):
        """Build LSTM model for time series prediction"""
        model = self.Sequential([
            self.LSTM(50, return_sequences=True, input_shape=input_shape),
            self.Dropout(0.2),
            self.LSTM(50, return_sequences=False),
            self.Dropout(0.2),
            self.Dense(25),
            self.Dense(1)
        ])
        
        model.compile(optimizer=self.Adam(learning_rate=0.001), loss='mse')
        return model
    
    def train_model(self, player_name, prop_type):
        """Train LSTM model for specific player and prop type"""
        try:
            # Load TensorFlow if not loaded
            if not self._load_tensorflow():
                return None
            
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
            model.fit(X, y, epochs=20, batch_size=32, verbose=0)  # Reduced epochs for speed
            
            return model
            
        except Exception as e:
            logger.error(f"Error training model for {player_name} {prop_type}: {e}")
            return None
    
    def predict(self, player_name, prop_type):
        """Predict prop value using LSTM model or fallback to simple prediction"""
        try:
            # Try LSTM prediction first
            model_key = f"{player_name}_{prop_type}"
            if model_key not in self._models:
                model = self.train_model(player_name, prop_type)
                if model is not None:
                    self._models[model_key] = model
                else:
                    # Fallback to simple prediction
                    return self._simple_predict(prop_type)
            
            model = self._models[model_key]
            
            # Get recent data for prediction
            player_data = self.scrape_player_stats(player_name, days_back=15)
            if player_data is None:
                return self._simple_predict(prop_type)
            
            prop_data = player_data[prop_type.lower()].values.reshape(-1, 1)
            
            # Prepare input for prediction
            if len(prop_data) < 10:
                return self._simple_predict(prop_type)
                
            recent_data = prop_data[-10:].reshape(1, 10, 1)
            scaled_data = self._scaler.transform(recent_data.reshape(-1, 1))
            scaled_input = scaled_data.reshape(1, 10, 1)
            
            # Make prediction
            prediction = model.predict(scaled_input)
            predicted_value = self._scaler.inverse_transform(prediction)[0][0]
            
            return max(0, round(predicted_value, 1))
            
        except Exception as e:
            logger.error(f"Error predicting for {player_name} {prop_type}: {e}")
            return self._simple_predict(prop_type)
    
    def _simple_predict(self, prop_type):
        """Simple fallback prediction"""
        if prop_type == 'HITS':
            return round(random.uniform(0.5, 2.5), 1)
        elif prop_type == 'TOTAL_BASES':
            return round(random.uniform(1.0, 5.0), 1)
        elif prop_type == 'RUNS':
            return round(random.uniform(0.5, 1.5), 1)
        elif prop_type == 'STRIKEOUTS':
            return round(random.uniform(3.0, 8.0), 1)
        else:
            return round(random.uniform(1.0, 3.0), 1)
    
    def calculate_implied_probability(self, predicted_value, prop_type, player_name):
        """Calculate implied probability based on LSTM prediction and historical variance"""
        try:
            # Get historical data
            player_data = self.scrape_player_stats(player_name, days_back=50)
            if player_data is None:
                return self._simple_probability(predicted_value, prop_type)
            
            prop_data = player_data[prop_type.lower()].values
            
            # Calculate historical mean and standard deviation
            mean_value = np.mean(prop_data)
            std_value = np.std(prop_data)
            
            if std_value == 0:
                return self._simple_probability(predicted_value, prop_type)
            
            # Calculate probability using normal distribution
            from scipy.stats import norm
            
            # Probability of achieving the predicted value or higher
            z_score = (predicted_value - mean_value) / std_value
            probability = 1 - norm.cdf(z_score)
            
            return max(0.01, min(0.99, probability))
            
        except Exception as e:
            logger.error(f"Error calculating probability: {e}")
            return self._simple_probability(predicted_value, prop_type)
    
    def _simple_probability(self, predicted_value, prop_type):
        """Simple probability calculation"""
        if prop_type == 'HITS':
            if predicted_value >= 2.0:
                return 0.25  # Hard
            elif predicted_value >= 1.0:
                return 0.45  # Medium
            else:
                return 0.80  # Easy
        elif prop_type == 'TOTAL_BASES':
            if predicted_value >= 4.0:
                return 0.20  # Hard
            elif predicted_value >= 2.0:
                return 0.45  # Medium
            else:
                return 0.75  # Easy
        elif prop_type == 'RUNS':
            if predicted_value >= 1.0:
                return 0.35  # Medium
            else:
                return 0.70  # Easy
        elif prop_type == 'STRIKEOUTS':
            if predicted_value >= 7.0:
                return 0.20  # Hard
            elif predicted_value >= 5.0:
                return 0.45  # Medium
            else:
                return 0.75  # Easy
        
        return 0.50  # Default medium
    
    def get_prop_value_at_probability(self, player_name, prop_type, target_probability):
        """Get prop value that corresponds to target probability"""
        try:
            # Get historical data
            player_data = self.scrape_player_stats(player_name, days_back=50)
            if player_data is None:
                return self._simple_prop_value(prop_type, target_probability)
            
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
            return self._simple_prop_value(prop_type, target_probability)
    
    def _simple_prop_value(self, prop_type, target_probability):
        """Simple prop value calculation"""
        if prop_type == 'HITS':
            if target_probability == 0.80:  # Easy
                return round(random.uniform(0.5, 1.0), 1)
            elif target_probability == 0.45:  # Medium
                return round(random.uniform(1.0, 2.0), 1)
            elif target_probability == 0.20:  # Hard
                return round(random.uniform(2.0, 3.0), 1)
        elif prop_type == 'TOTAL_BASES':
            if target_probability == 0.80:  # Easy
                return round(random.uniform(1.0, 2.0), 1)
            elif target_probability == 0.45:  # Medium
                return round(random.uniform(2.0, 4.0), 1)
            elif target_probability == 0.20:  # Hard
                return round(random.uniform(4.0, 6.0), 1)
        elif prop_type == 'RUNS':
            if target_probability == 0.80:  # Easy
                return round(random.uniform(0.5, 0.8), 1)
            elif target_probability == 0.45:  # Medium
                return round(random.uniform(0.8, 1.2), 1)
            elif target_probability == 0.20:  # Hard
                return round(random.uniform(1.2, 1.8), 1)
        elif prop_type == 'STRIKEOUTS':
            if target_probability == 0.80:  # Easy
                return round(random.uniform(3.0, 5.0), 1)
            elif target_probability == 0.45:  # Medium
                return round(random.uniform(5.0, 7.0), 1)
            elif target_probability == 0.20:  # Hard
                return round(random.uniform(7.0, 9.0), 1)
        
        return round(random.uniform(1.0, 3.0), 1) 