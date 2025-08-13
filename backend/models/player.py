from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

# Import the shared db instance instead of creating a new one
from .user import db

class Player(db.Model):
    __tablename__ = 'players'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    team = db.Column(db.String(50), nullable=False)
    sport = db.Column(db.String(10), nullable=False)  # NBA, NFL, MLB
    position = db.Column(db.String(20), nullable=True)
    jersey_number = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    props = db.relationship('Prop', backref='player', lazy='dynamic')
    
    def __init__(self, name, team, sport, position=None, jersey_number=None):
        self.name = name
        self.team = team
        self.sport = sport
        self.position = position
        self.jersey_number = jersey_number
    
    def get_active_props(self):
        """Get all active props for this player"""
        return self.props.filter_by(is_active=True).all()
    
    def get_props_by_sport(self, sport):
        """Get props for a specific sport"""
        return self.props.filter_by(sport=sport, is_active=True).all()
    
    def to_dict(self):
        """Convert player to dictionary for API responses"""
        return {
            'id': self.id,
            'name': self.name,
            'team': self.team,
            'sport': self.sport,
            'position': self.position,
            'jersey_number': self.jersey_number,
            'is_active': self.is_active,
            'active_props_count': self.get_active_props().count()
        }
    
    def __repr__(self):
        return f'<Player {self.name} ({self.team} - {self.sport})>' 