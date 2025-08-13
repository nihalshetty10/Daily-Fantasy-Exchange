import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error
import requests
import logging
from datetime import datetime, timedelta
import json

class MLBModel:
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.prop_types = ['hits', 'total_bases', 'runs', 'strikeouts', 'earned_runs_allowed']
        
    def fetch_player_data(self, player_name, days_back=365):
        """Fetch MLB player data from API"""
        try:
            # This would integrate with MLB API or baseball-reference
            # For now, using mock data structure
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # Mock API call - replace with actual MLB API
            url = f"https://api.mlb.com/stats/player/{player_name}/gamelog"
            # response = requests.get(url)
            # data = response.json()
            
            # Mock data for demonstration
            mock_data = self._generate_mock_data(player_name, start_date, end_date)
            return mock_data
            
        except Exception as e:
            logging.error(f"Error fetching MLB data for {player_name}: {e}")
            return None
    
    def _generate_mock_data(self, player_name, start_date, end_date):
        """Generate mock MLB data for demonstration"""
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        data = []
        
        for date in dates:
            # Skip non-game days (simplified - MLB games are typically daily during season)
            if date.weekday() < 7:  # All days
                game_data = {
                    'date': date,
                    'player': player_name,
                    'hits': np.random.poisson(1.2) if 'Batter' in player_name else 0,
                    'total_bases': np.random.poisson(2.0) if 'Batter' in player_name else 0,
                    'runs': np.random.poisson(0.8) if 'Batter' in player_name else 0,
                    'strikeouts': np.random.poisson(1.0) if 'Batter' in player_name else np.random.poisson(6) if 'Pitcher' in player_name else 0,
                    'earned_runs_allowed': np.random.poisson(2.5) if 'Pitcher' in player_name else 0,
                    'at_bats': np.random.poisson(4) if 'Batter' in player_name else 0,
                    'innings_pitched': np.random.normal(6, 1) if 'Pitcher' in player_name else 0,
                    'opponent': np.random.choice(['NYY', 'BOS', 'LAD', 'SF', 'CHC']),
                    'home_away': np.random.choice(['home', 'away']),
                    'weather': np.random.choice(['clear', 'rain', 'windy']),
                    'temperature': np.random.normal(70, 15)
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
            
            # Trend (increasing/decreasing)
            df[f'{prop_type}_trend'] = df[prop_type].rolling(5).apply(
                lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) > 1 else 0
            )
            
            # Consistency (lower std = more consistent)
            df[f'{prop_type}_consistency'] = 1 / (1 + df[f'{prop_type}_5game_std'])
        
        # Additional features
        df['days_rest'] = df['date'].diff().dt.days
        df['is_home'] = (df['home_away'] == 'home').astype(int)
        df['is_warm'] = (df['temperature'] > 75).astype(int)
        df['is_windy'] = (df['weather'] == 'windy').astype(int)
        
        # Create feature matrix
        feature_columns = []
        for prop_type in self.prop_types:
            feature_columns.extend([
                f'{prop_type}_3game_avg', f'{prop_type}_5game_avg', f'{prop_type}_10game_avg',
                f'{prop_type}_3game_std', f'{prop_type}_5game_std', f'{prop_type}_form',
                f'{prop_type}_trend', f'{prop_type}_consistency'
            ])
        
        feature_columns.extend(['days_rest', 'is_home', 'is_warm', 'is_windy'])
        
        return df[feature_columns].fillna(0)
    
    def build_model(self):
        """Build Random Forest model"""
        model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
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
        self.model = self.build_model()
        
        self.model.fit(X_train_scaled, y_train)
        
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
        predicted_value = self.model.predict(X_recent_scaled)[0]
        
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