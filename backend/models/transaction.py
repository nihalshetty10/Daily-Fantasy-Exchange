import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey, Text
from backend.db import Base

class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    transaction_type = Column(String(50), nullable=False)  # 'bet', 'win', 'loss', 'cashout', 'deposit', 'withdrawal'
    amount = Column(Float, nullable=False)  # Positive for gains, negative for losses
    prop_id = Column(String(100), nullable=True)  # Reference to the prop bet
    player_name = Column(String(100), nullable=True)
    sport = Column(String(10), nullable=True)  # 'MLB' or 'NFL'
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'transaction_type': self.transaction_type,
            'amount': self.amount,
            'prop_id': self.prop_id,
            'player_name': self.player_name,
            'sport': self.sport,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
