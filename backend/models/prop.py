from datetime import datetime, timedelta
from enum import Enum
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from .user import db

class DifficultyLevel(Enum):
    EASY = 'EASY'
    MEDIUM = 'MEDIUM'
    HARD = 'HARD'

class GameStatus(Enum):
    UPCOMING = 'UPCOMING'
    LIVE = 'LIVE'
    FINAL = 'FINAL'

class Prop(db.Model):
    __tablename__ = 'props'
    
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    sport = db.Column(db.String(10), nullable=False)  # NBA, NFL, MLB
    prop_type = db.Column(db.String(50), nullable=False)  # points, rebounds, etc.
    line_value = db.Column(db.Float, nullable=False)  # The over/under line (rounded to 0.5)
    difficulty = db.Column(db.Enum(DifficultyLevel), nullable=False)
    implied_probability = db.Column(db.Float, nullable=False)  # ML predicted probability
    game_date = db.Column(db.DateTime, nullable=False)
    game_time = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # ML Model Data
    model_prediction = db.Column(db.Float, nullable=True)
    model_confidence = db.Column(db.Float, nullable=True)
    historical_data_points = db.Column(db.Integer, default=0)
    
    # Game and player info
    player_position = db.Column(db.String(10), nullable=True)  # P, 1B, 2B, SS, 3B, OF, C
    opponent_info = db.Column(db.String(100), nullable=True)  # "vs PHI" or "@ DET"
    game_start_time = db.Column(db.String(20), nullable=True)  # "7:10 PM ET"
    
    # Game Status and Trading
    game_status = db.Column(db.Enum(GameStatus), default=GameStatus.UPCOMING)
    total_contracts = db.Column(db.Integer, default=10)  # Total contracts available
    sold_contracts = db.Column(db.Integer, default=0)  # Contracts sold so far
    available_contracts = db.Column(db.Integer, default=10)  # Available for trading
    
    # Live Game Data
    current_game_time = db.Column(db.String(20), default="")  # e.g., "Q2 8:30", "T7 2-1"
    live_score = db.Column(db.String(20), default="")  # e.g., "LAL 45-42 GSW"
    player_current_value = db.Column(db.Float, default=0.0)  # Current player stat
    live_implied_probability = db.Column(db.Float, default=0.0)  # Updated probability
    
    # Game tracking
    game_end_time = db.Column(db.DateTime, nullable=True)
    last_update = db.Column(db.DateTime, default=datetime.utcnow)
    update_frequency = db.Column(db.Integer, default=30)  # seconds between updates
    
    # Relationships
    contracts = db.relationship('Contract', backref='prop', lazy='dynamic')
    
    def __init__(self, player_id, sport, prop_type, line_value, difficulty, 
                 implied_probability, game_date, game_time, model_prediction=None):
        self.player_id = player_id
        self.sport = sport
        self.prop_type = prop_type
        # Round line value to nearest 0.5
        self.line_value = round(line_value * 2) / 2
        self.difficulty = difficulty
        self.implied_probability = implied_probability
        self.game_date = game_date
        self.game_time = game_time
        self.model_prediction = model_prediction
        self.live_implied_probability = self.implied_probability
        self.game_status = GameStatus.UPCOMING
        self.available_contracts = 10
        self.sold_contracts = 0
    
    def get_game_day_of_week(self):
        """Get the day of week for the game"""
        return self.game_time.strftime('%A')
    
    def get_formatted_game_time(self):
        """Get formatted game time with day of week"""
        return f"{self.get_game_day_of_week()} {self.game_start_time}"
    
    def update_game_status(self):
        """Update game status based on current time"""
        now = datetime.utcnow()
        
        if self.game_status == GameStatus.FINAL:
            return  # Already final
        
        # Check if game should be live (within 5 minutes of start time)
        game_start = self.game_time
        five_min_before = game_start - timedelta(minutes=5)
        
        if now >= game_start:
            self.game_status = GameStatus.LIVE
        elif now >= five_min_before:
            self.game_status = GameStatus.LIVE
        else:
            self.game_status = GameStatus.UPCOMING
    
    def can_trade(self):
        """Check if prop can be traded based on status"""
        if self.game_status == GameStatus.FINAL:
            return False
        return True
    
    def can_buy_contracts(self, quantity=1):
        """Check if contracts can be bought based on game status"""
        if not self.can_trade():
            return False
        
        if self.game_status == GameStatus.UPCOMING:
            # UPCOMING: Can buy any available contracts
            return self.available_contracts >= quantity
        elif self.game_status == GameStatus.LIVE:
            # LIVE: Can only buy contracts that were previously sold and are back on market
            # (i.e., contracts that were sold mid-game)
            return self.available_contracts >= quantity and self.sold_contracts > 0
        elif self.game_status == GameStatus.FINAL:
            # FINAL: No new purchases allowed
            return False
        
        return False
    
    def can_sell_contracts(self, user_id, quantity=1):
        """Check if contracts can be sold based on game status"""
        if not self.can_trade():
            return False
        
        # Check if user has contracts to sell
        from .portfolio import Portfolio
        user_contracts = Portfolio.query.filter_by(
            user_id=user_id, 
            prop_id=self.id
        ).first()
        
        if not user_contracts:
            return False
        
        if self.game_status == GameStatus.UPCOMING:
            # UPCOMING: Can sell contracts back to market
            return user_contracts.quantity >= quantity
        elif self.game_status == GameStatus.LIVE:
            # LIVE: Can sell contracts mid-game (they go back to market)
            return user_contracts.quantity >= quantity
        elif self.game_status == GameStatus.FINAL:
            # FINAL: Can only cash out, not sell back to market
            return False
        
        return False
    
    def handle_live_game_start(self):
        """Handle what happens when game goes live"""
        if self.game_status == GameStatus.LIVE:
            # When game goes live, any unsold contracts vanish from market
            # but remain available for users who already own them
            vanished_contracts = self.available_contracts
            self.available_contracts = 0
            return vanished_contracts
        return 0
    
    def get_trading_availability(self):
        """Get trading availability based on game status"""
        if self.game_status == GameStatus.UPCOMING:
            return {
                'can_buy': True,
                'can_sell': True,
                'can_cash_out': False,
                'message': 'Full trading available'
            }
        elif self.game_status == GameStatus.LIVE:
            return {
                'can_buy': self.sold_contracts > 0,  # Only if contracts were sold mid-game
                'can_sell': True,
                'can_cash_out': False,
                'message': 'Limited trading - can sell owned contracts, buy only previously sold contracts'
            }
        elif self.game_status == GameStatus.FINAL:
            return {
                'can_buy': False,
                'can_sell': False,
                'can_cash_out': True,
                'message': 'Game finished - cash out your contracts'
            }
        return {
            'can_buy': False,
            'can_sell': False,
            'can_cash_out': False,
            'message': 'Trading not available'
        }
    
    def get_contract_price(self):
        """Get current contract price based on status"""
        if self.game_status == GameStatus.LIVE:
            return self.live_implied_probability
        return self.implied_probability
    
    def get_available_contracts(self):
        """Get number of available contracts"""
        return self.available_contracts
    
    def buy_contracts(self, quantity=1):
        """Buy contracts and update availability"""
        if self.can_buy_contracts(quantity):
            self.available_contracts -= quantity
            self.sold_contracts += quantity
            return True
        return False
    
    def sell_contracts(self, quantity=1):
        """Sell contracts and update availability"""
        self.available_contracts += quantity
        self.sold_contracts -= quantity
        return True
    
    def get_status_badge(self):
        """Get status badge for display"""
        if self.game_status == GameStatus.LIVE:
            return 'LIVE'
        elif self.game_status == GameStatus.FINAL:
            return 'FINAL'
        else:
            return 'UPCOMING'
    
    def get_status_color(self):
        """Get status color for display"""
        if self.game_status == GameStatus.LIVE:
            return 'danger'
        elif self.game_status == GameStatus.FINAL:
            return 'secondary'
        else:
            return 'success'
    
    def to_dict(self):
        """Convert to dictionary for API"""
        return {
            'id': self.id,
            'player_id': self.player_id,
            'sport': self.sport,
            'prop_type': self.prop_type,
            'line_value': self.line_value,
            'difficulty': self.difficulty.value,
            'implied_probability': self.implied_probability,
            'game_date': self.game_date.isoformat(),
            'game_time': self.game_time.isoformat(),
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'model_prediction': self.model_prediction,
            'model_confidence': self.model_confidence,
            'historical_data_points': self.historical_data_points,
            'game_status': self.game_status.value,
            'total_contracts': self.total_contracts,
            'sold_contracts': self.sold_contracts,
            'available_contracts': self.available_contracts,
            'current_game_time': self.current_game_time,
            'live_score': self.live_score,
            'player_current_value': self.player_current_value,
            'live_implied_probability': self.live_implied_probability,
            'status_badge': self.get_status_badge(),
            'status_color': self.get_status_color(),
            'formatted_game_time': self.get_formatted_game_time()
        } 