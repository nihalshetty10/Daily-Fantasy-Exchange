import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras.optimizers import Adam
import requests
import logging
from datetime import datetime, timedelta
import json

class NBAModel:
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.prop_types = ['points', 'rebounds', 'assists', 'steals', 'blocks', 'threes_made']
        
    def fetch_player_data(self, player_name, days_back=365):
        """Fetch NBA player data from API"""
        try:
            # This would integrate with NBA API or basketball-reference
            # For now, using mock data structure
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # Mock API call - replace with actual NBA API
            url = f"https://api.nba.com/stats/playergamelog?PlayerID={player_name}&Season=2023-24"
            # response = requests.get(url)
            # data = response.json()
            
            # Mock data for demonstration
            mock_data = self._generate_mock_data(player_name, start_date, end_date)
            return mock_data
            
        except Exception as e:
            logging.error(f"Error fetching NBA data for {player_name}: {e}")
            return None
    
    def _generate_mock_data(self, player_name, start_date, end_date):
        """Generate mock NBA data for demonstration"""
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        data = []
        
        for date in dates:
            # Skip non-game days (simplified)
            if date.weekday() < 5:  # Monday-Friday
                game_data = {
                    'date': date,
                    'player': player_name,
                    'points': np.random.poisson(20),  # Average 20 points
                    'rebounds': np.random.poisson(5),  # Average 5 rebounds
                    'assists': np.random.poisson(4),   # Average 4 assists
                    'steals': np.random.poisson(1),    # Average 1 steal
                    'blocks': np.random.poisson(0.5),  # Average 0.5 blocks
                    'threes_made': np.random.poisson(2), # Average 2 threes
                    'minutes': np.random.normal(30, 5),  # Average 30 minutes
                    'opponent': np.random.choice(['LAL', 'BOS', 'GSW', 'MIA', 'PHX']),
                    'home_away': np.random.choice(['home', 'away'])
                }
                data.append(game_data)
        
        return pd.DataFrame(data)
    
    def prepare_features(self, df):
        """Prepare features for ML model"""
        features = []
        
        for prop_type in self.prop_types:
            # Rolling averages
            df[f'{prop_type}_3game_avg'] = df[prop_type].rolling(3, min_periods=1).mean()
            df[f'{prop_type}_5game_avg'] = df[prop_type].rolling(5, min_periods=1).mean()
            df[f'{prop_type}_10game_avg'] = df[prop_type].rolling(10, min_periods=1).mean()
            
            # Rolling standard deviations
            df[f'{prop_type}_3game_std'] = df[prop_type].rolling(3, min_periods=1).std()
            df[f'{prop_type}_5game_std'] = df[prop_type].rolling(5, min_periods=1).std()
            
            # Recent form (last 3 games vs last 10 games)
            df[f'{prop_type}_form'] = df[f'{prop_type}_3game_avg'] / df[f'{prop_type}_10game_avg']
        
        # Additional features
        df['days_rest'] = df['date'].diff().dt.days
        df['is_home'] = (df['home_away'] == 'home').astype(int)
        
        # Create feature matrix
        feature_columns = []
        for prop_type in self.prop_types:
            feature_columns.extend([
                f'{prop_type}_3game_avg', f'{prop_type}_5game_avg', f'{prop_type}_10game_avg',
                f'{prop_type}_3game_std', f'{prop_type}_5game_std', f'{prop_type}_form'
            ])
        
        feature_columns.extend(['days_rest', 'is_home'])
        
        return df[feature_columns].fillna(0)
    
    def build_model(self, input_dim):
        """Build neural network model"""
        model = Sequential([
            Dense(64, activation='relu', input_dim=input_dim),
            Dropout(0.2),
            Dense(32, activation='relu'),
            Dropout(0.2),
            Dense(16, activation='relu'),
            Dense(1, activation='linear')
        ])
        
        model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss='mse',
            metrics=['mae']
        )
        
        return model
    
    def train(self, player_name, prop_type):
        """Train model for specific player and prop type"""
        # Fetch player data
        df = self.fetch_player_data(player_name)
        if df is None or df.empty:
            logging.error(f"No data available for {player_name}")
            return False
        
        # Prepare features
        X = self.prepare_features(df)
        y = df[prop_type].values
        
        # Remove rows with NaN values
        valid_indices = ~(X.isna().any(axis=1) | pd.isna(y))
        X = X[valid_indices]
        y = y[valid_indices]
        
        if len(X) < 10:
            logging.error(f"Insufficient data for {player_name} {prop_type}")
            return False
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Build and train model
        self.model = self.build_model(X_train.shape[1])
        
        history = self.model.fit(
            X_train_scaled, y_train,
            validation_data=(X_test_scaled, y_test),
            epochs=100,
            batch_size=32,
            verbose=0
        )
        
        # Evaluate model
        y_pred = self.model.predict(X_test_scaled)
        mse = mean_squared_error(y_test, y_pred)
        mae = mean_absolute_error(y_test, y_pred)
        
        logging.info(f"Model trained for {player_name} {prop_type}")
        logging.info(f"MSE: {mse:.2f}, MAE: {mae:.2f}")
        
        self.is_trained = True
        return True
    
    def predict(self, player_name, prop_type, line_value):
        """Predict probability of going over the line"""
        if not self.is_trained:
            if not self.train(player_name, prop_type):
                return None
        
        # Get recent data for prediction
        df = self.fetch_player_data(player_name, days_back=30)
        if df is None or df.empty:
            return None
        
        # Prepare features
        X = self.prepare_features(df)
        if X.empty:
            return None
        
        # Use most recent data point
        X_recent = X.iloc[-1:].values
        X_recent_scaled = self.scaler.transform(X_recent)
        
        # Predict expected value
        predicted_value = self.model.predict(X_recent_scaled)[0][0]
        
        # Calculate probability of going over the line
        # Using historical standard deviation for uncertainty
        historical_std = df[prop_type].std()
        
        # Calculate probability using normal distribution
        from scipy.stats import norm
        probability = 1 - norm.cdf(line_value, predicted_value, historical_std)
        
        return {
            'predicted_value': predicted_value,
            'probability': probability,
            'confidence': 1 - historical_std / predicted_value if predicted_value > 0 else 0,
            'historical_std': historical_std
        }
    
    def get_difficulty_level(self, probability):
        """Determine difficulty level based on probability"""
        if probability >= 0.75:
            return 'easy'
        elif probability >= 0.35:
            return 'medium'
        else:
            return 'hard' 