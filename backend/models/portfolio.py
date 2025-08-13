from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import enum

# Import the shared db instance instead of creating a new one
from .user import db

class TradeType(enum.Enum):
    BUY = 'buy'
    SELL = 'sell'
    CASH_OUT = 'cash_out'

class Portfolio(db.Model):
    __tablename__ = 'portfolios'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    contract_id = db.Column(db.String(36), db.ForeignKey('contracts.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    average_purchase_price = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __init__(self, user_id, contract_id, quantity, average_purchase_price):
        self.user_id = user_id
        self.contract_id = contract_id
        self.quantity = quantity
        self.average_purchase_price = average_purchase_price
    
    def get_current_value(self):
        """Get current value of this portfolio position"""
        from .contract import Contract
        contract = Contract.query.get(self.contract_id)
        if contract:
            return contract.current_price * self.quantity
        return 0
    
    def get_pnl(self):
        """Calculate profit/loss for this position"""
        current_value = self.get_current_value()
        cost_basis = self.average_purchase_price * self.quantity
        return current_value - cost_basis
    
    def get_pnl_percentage(self):
        """Calculate P&L as percentage"""
        cost_basis = self.average_purchase_price * self.quantity
        if cost_basis > 0:
            return (self.get_pnl() / cost_basis) * 100
        return 0
    
    def to_dict(self):
        """Convert portfolio to dictionary for API responses"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'contract_id': self.contract_id,
            'quantity': self.quantity,
            'average_purchase_price': self.average_purchase_price,
            'current_value': self.get_current_value(),
            'pnl': self.get_pnl(),
            'pnl_percentage': self.get_pnl_percentage(),
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Trade(db.Model):
    __tablename__ = 'trades'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    contract_id = db.Column(db.String(36), db.ForeignKey('contracts.id'), nullable=False)
    trade_type = db.Column(db.Enum(TradeType), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, user_id, contract_id, trade_type, quantity, price):
        self.user_id = user_id
        self.contract_id = contract_id
        self.trade_type = trade_type
        self.quantity = quantity
        self.price = price
        self.total_amount = quantity * price
    
    def to_dict(self):
        """Convert trade to dictionary for API responses"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'contract_id': self.contract_id,
            'trade_type': self.trade_type.value,
            'quantity': self.quantity,
            'price': self.price,
            'total_amount': self.total_amount,
            'timestamp': self.timestamp.isoformat()
        }
    
    def __repr__(self):
        return f'<Trade {self.trade_type.value} {self.quantity} @ ${self.price:.2f}>' 