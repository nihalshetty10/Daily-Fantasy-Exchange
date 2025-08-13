from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    balance = db.Column(db.Float, default=1000.0)  # Starting balance $1000
    total_pnl = db.Column(db.Float, default=0.0)   # Total profit/loss
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    portfolios = db.relationship('Portfolio', backref='user', lazy='dynamic')
    trades = db.relationship('Trade', backref='user', lazy='dynamic')
    
    def __init__(self, username, email, password):
        self.username = username
        self.email = email
        self.password_hash = generate_password_hash(password)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def can_buy_contract(self, contract_price):
        """Check if user has enough balance to buy a contract"""
        return self.balance >= contract_price
    
    def buy_contract(self, contract_price):
        """Deduct balance when buying a contract"""
        if self.can_buy_contract(contract_price):
            self.balance -= contract_price
            return True
        return False
    
    def sell_contract(self, contract_price):
        """Add balance when selling a contract"""
        self.balance += contract_price
    
    def get_portfolio_value(self):
        """Calculate total portfolio value"""
        total_value = self.balance
        for portfolio in self.portfolios:
            if portfolio.contract and portfolio.contract.is_active:
                total_value += portfolio.contract.current_price
        return total_value
    
    def get_portfolio_size(self):
        """Get number of active contracts in portfolio"""
        return self.portfolios.filter_by(is_active=True).count()
    
    def can_add_to_portfolio(self):
        """Check if user can add more contracts to portfolio"""
        return self.get_portfolio_size() < 10
    
    def has_minimum_portfolio(self):
        """Check if user has minimum required contracts"""
        return self.get_portfolio_size() >= 2
    
    def to_dict(self):
        """Convert user to dictionary for API responses"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'balance': self.balance,
            'total_pnl': self.total_pnl,
            'portfolio_size': self.get_portfolio_size(),
            'portfolio_value': self.get_portfolio_value(),
            'created_at': self.created_at.isoformat(),
            'last_login': self.last_login.isoformat()
        } 