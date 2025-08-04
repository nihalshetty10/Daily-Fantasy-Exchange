from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import uuid

# Import the shared db instance instead of creating a new one
from .user import db

class Contract(db.Model):
    __tablename__ = 'contracts'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prop_id = db.Column(db.Integer, db.ForeignKey('props.id'), nullable=False)
    owner_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)  # Null if available for purchase
    quantity = db.Column(db.Integer, default=1)  # Number of contracts
    purchase_price = db.Column(db.Float, nullable=True)  # Price when purchased
    current_price = db.Column(db.Float, nullable=False)  # Current market price
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    purchased_at = db.Column(db.DateTime, nullable=True)
    sold_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    trades = db.relationship('Trade', backref='contract', lazy='dynamic')
    
    def __init__(self, prop_id, current_price, quantity=1):
        self.prop_id = prop_id
        self.current_price = current_price
        self.quantity = quantity
    
    def buy(self, user_id, price):
        """Buy this contract"""
        if self.owner_id is None and self.is_active:
            self.owner_id = user_id
            self.purchase_price = price
            self.current_price = price
            self.purchased_at = datetime.utcnow()
            return True
        return False
    
    def sell(self, price):
        """Sell this contract back to the market"""
        if self.owner_id is not None and self.is_active:
            self.owner_id = None
            self.current_price = price
            self.sold_at = datetime.utcnow()
            return True
        return False
    
    def get_pnl(self):
        """Calculate profit/loss for this contract"""
        if self.owner_id and self.purchase_price:
            return self.current_price - self.purchase_price
        return 0
    
    def get_potential_payout(self):
        """Get potential payout if prop hits"""
        from .prop import Prop
        prop = Prop.query.get(self.prop_id)
        if prop and prop.implied_probability:
            return 100  # Standard $100 payout
        return 0
    
    def is_available_for_purchase(self):
        """Check if contract is available for purchase"""
        return self.owner_id is None and self.is_active
    
    def can_be_sold(self, user_id):
        """Check if user can sell this contract"""
        return self.owner_id == user_id and self.is_active
    
    def update_price(self, new_price):
        """Update current market price"""
        self.current_price = new_price
    
    def to_dict(self):
        """Convert contract to dictionary for API responses"""
        return {
            'id': self.id,
            'prop_id': self.prop_id,
            'owner_id': self.owner_id,
            'quantity': self.quantity,
            'purchase_price': self.purchase_price,
            'current_price': self.current_price,
            'pnl': self.get_pnl(),
            'potential_payout': self.get_potential_payout(),
            'is_available': self.is_available_for_purchase(),
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'purchased_at': self.purchased_at.isoformat() if self.purchased_at else None,
            'sold_at': self.sold_at.isoformat() if self.sold_at else None
        }
    
    def __repr__(self):
        return f'<Contract {self.id} - Prop {self.prop_id} - Price ${self.current_price:.2f}>' 