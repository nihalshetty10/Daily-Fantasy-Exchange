from datetime import datetime
from enum import Enum
from .user import db

class OrderSide(Enum):
    BID = 'bid'
    ASK = 'ask'

class OrderStatus(Enum):
    OPEN = 'open'
    PARTIAL = 'partial'
    FILLED = 'filled'
    CANCELED = 'canceled'

class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    prop_id = db.Column(db.Integer, db.ForeignKey('props.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    side = db.Column(db.Enum(OrderSide), nullable=False)
    price = db.Column(db.Float, nullable=False)  # dollars (0-100)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    remaining = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.Enum(OrderStatus), nullable=False, default=OrderStatus.OPEN)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'prop_id': self.prop_id,
            'user_id': self.user_id,
            'side': self.side.value,
            'price': self.price,
            'quantity': self.quantity,
            'remaining': self.remaining,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
        } 