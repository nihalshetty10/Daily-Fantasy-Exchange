#!/usr/bin/env python3
"""
Force database recreation with new schema
"""

from run import create_app
from backend.models import db

def recreate_database():
    """Recreate the database with the new schema"""
    app, socketio = create_app()
    
    with app.app_context():
        # Drop all tables
        db.drop_all()
        print("🗑️ Dropped all existing tables")
        
        # Create all tables with new schema
        db.create_all()
        print("✅ Created database with new schema")
        
        # Create admin user
        from backend.models import User
        admin = User(username='admin', email='admin@fantasyexchange.com', password='admin123')
        db.session.add(admin)
        db.session.commit()
        print("👤 Created admin user")

if __name__ == "__main__":
    recreate_database() 