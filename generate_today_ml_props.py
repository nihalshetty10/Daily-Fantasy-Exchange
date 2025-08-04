#!/usr/bin/env python3
"""
Generate today's props using ML generator
"""

import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.models import db, User, Player, Prop
from ml_prop_generator import MLPropGenerator

def generate_today_props():
    """Generate props for today using ML generator"""
    
    print("🚀 Starting ML-based prop generation for today...")
    
    # Initialize ML generator (using test version to avoid scraping issues)
    generator = MLPropGenerator()
    
    # Get today's date
    today = datetime.now().date()
    print(f"📅 Generating props for: {today}")
    
    try:
        # Generate props for today using test data
        props_data = generator.generate_tomorrow_props()
        
        print(f"✅ Generated {len(props_data)} props for today")
        
        # Convert to database format
        db_props = []
        for prop_data in props_data:
            # Convert the test data format to database format
            db_prop = {
                'player_id': 1,  # Default player ID
                'sport': prop_data.get('sport', 'MLB'),
                'prop_type': prop_data.get('prop_type', 'HITS'),
                'line_value': prop_data.get('line_value', 1.0),
                'difficulty': prop_data.get('difficulty', 'MEDIUM'),
                'implied_probability': prop_data.get('implied_probability', 0.45),
                'game_date': today,
                'game_time': datetime.now() + timedelta(hours=2),  # Default game time
                'model_prediction': prop_data.get('model_prediction', 1.0),
                'model_confidence': prop_data.get('model_confidence', 0.8),
                'historical_data_points': 10
            }
            db_props.append(db_prop)
        
        # Save to database
        from run import create_app
        app, socketio = create_app()
        
        with app.app_context():
            # Clear existing props for today
            existing_props = Prop.query.filter(
                Prop.game_date == today
            ).delete()
            
            # Add new props
            for prop_data in db_props:
                prop = Prop(**prop_data)
                db.session.add(prop)
            
            db.session.commit()
            print(f"💾 Saved {len(db_props)} props to database")
            
        return db_props
        
    except Exception as e:
        print(f"❌ Error generating props: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    generate_today_props() 