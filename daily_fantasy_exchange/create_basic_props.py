#!/usr/bin/env python3
"""
Create Basic Props for Testing
Simple prop generation without complex player management
"""

import os
import sys
from datetime import datetime, timedelta
import random

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.models import db, User, Player, Prop, GameStatus, DifficultyLevel
from run import create_app

def create_basic_props():
    """Create basic props for testing"""
    
    # Create Flask app context
    app, socketio = create_app()
    
    with app.app_context():
        # Clear existing data
        Prop.query.delete()
        Player.query.delete()
        db.session.commit()
        
        # Create a few basic players
        players = []
        player_names = [
            ('LeBron James', 'Los Angeles Lakers', 'NBA'),
            ('Stephen Curry', 'Golden State Warriors', 'NBA'),
            ('Mike Trout', 'Los Angeles Angels', 'MLB'),
            ('Shohei Ohtani', 'Los Angeles Angels', 'MLB')
        ]
        
        for name, team, sport in player_names:
            player = Player(
                name=name,
                team=team,
                sport=sport,
                position='Player'
            )
            db.session.add(player)
            players.append(player)
        
        db.session.flush()  # Get IDs
        
        # Create some basic props
        now = datetime.utcnow()
        props_created = 0
        
        for i, player in enumerate(players):
            # Create 2 props per player with different game times
            for j in range(2):
                if j == 0:  # First prop - live game
                    game_time = now - timedelta(minutes=random.randint(30, 90))
                    game_status = GameStatus.LIVE
                else:  # Second prop - upcoming game
                    game_time = now + timedelta(hours=random.randint(1, 6))
                    game_status = GameStatus.SCHEDULED
                
                # Create prop based on sport
                if player.sport == 'NBA':
                    prop_type = 'POINTS'
                    line_value = round(random.uniform(20.0, 35.0), 1)
                else:  # MLB
                    prop_type = 'HITS'
                    line_value = round(random.uniform(1.0, 2.5), 1)
                
                # Random difficulty
                difficulty = random.choice(['EASY', 'MEDIUM', 'HARD'])
                if difficulty == 'EASY':
                    prob = 0.80
                elif difficulty == 'MEDIUM':
                    prob = 0.45
                else:
                    prob = 0.20
                
                prop = Prop(
                    player_id=player.id,
                    sport=player.sport,
                    prop_type=prop_type,
                    line_value=line_value,
                    difficulty=DifficultyLevel(difficulty),
                    implied_probability=prob,
                    game_date=game_time.date(),
                    game_time=game_time,
                    model_prediction=line_value * random.uniform(0.8, 1.2)
                )
                
                # Set live trading fields
                prop.game_status = game_status
                prop.live_implied_probability = prob
                prop.trading_active = True
                
                db.session.add(prop)
                props_created += 1
        
        # Commit all
        db.session.commit()
        
        print(f"✅ Created {props_created} basic props")
        print(f"📊 Players: {len(players)}")
        print(f"🎯 Ready for testing!")

if __name__ == '__main__':
    create_basic_props() 