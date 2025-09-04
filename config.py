import os
from datetime import timedelta

class Config:
    """Base configuration class"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///proptrader.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT Configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=1)
    
    # Trading Configuration
    STANDARD_PAYOUT = 100  # $100 payout for winning contracts
    MAX_CONTRACTS_PER_PROP = 10  # Maximum contracts per prop
    MIN_PORTFOLIO_SIZE = 2
    MAX_PORTFOLIO_SIZE = 10
    INITIAL_BALANCE = 10000  # Starting balance for new users
    
    # Sports Configuration
    SPORTS = {
        'NBA': {
            'prop_types': ['POINTS', 'REBOUNDS', 'ASSISTS', 'STEALS', 'BLOCKS'],
            'difficulty_levels': {
                'EASY': {'min_prob': 0.75, 'max_prob': 0.85},
                'MEDIUM': {'min_prob': 0.40, 'max_prob': 0.50},
                'HARD': {'min_prob': 0.15, 'max_prob': 0.25}
            }
        },
        'MLB': {
            'prop_types': ['HITS', 'TOTAL_BASES', 'RUNS', 'RBIS', 'WALKS'],
            'difficulty_levels': {
                'EASY': {'min_prob': 0.75, 'max_prob': 0.85},
                'MEDIUM': {'min_prob': 0.40, 'max_prob': 0.50},
                'HARD': {'min_prob': 0.15, 'max_prob': 0.25}
            }
        },
        'NFL': {
            'prop_types': ['PASSING_YARDS', 'RUSHING_YARDS', 'RECEIVING_YARDS', 'TOUCHDOWNS'],
            'difficulty_levels': {
                'EASY': {'min_prob': 0.75, 'max_prob': 0.85},
                'MEDIUM': {'min_prob': 0.40, 'max_prob': 0.50},
                'HARD': {'min_prob': 0.15, 'max_prob': 0.25}
            }
        }
    }
    
    # ML Model Configuration
    MODEL_UPDATE_FREQUENCY = 3600  # Update models every hour
    PREDICTION_CONFIDENCE_THRESHOLD = 0.6
    
    # Redis Configuration (for SocketIO)
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379'

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    # Use absolute path to instance/proptrader.db
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'proptrader.db')}"

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if not SQLALCHEMY_DATABASE_URI:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'proptrader.db')}"
    # Normalize legacy postgres scheme
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
} 