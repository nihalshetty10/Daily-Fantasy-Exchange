#!/usr/bin/env python3
"""
Generate Live Props for Testing
Creates sample props with realistic game times for live trading testing
"""

import os
import sys
from datetime import datetime, timedelta
import random

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.models import db, User, Player, Prop, GameStatus, DifficultyLevel
from run import create_app

def generate_live_props():
    """Generate sample props with realistic game times"""
    
    # Create Flask app context
    app, socketio = create_app()
    
    with app.app_context():
        # Clear existing props and players
        Prop.query.delete()
        Player.query.delete()
        db.session.commit()
        
        # Sample players data
        mlb_players_data = [
            {'name': 'Mike Trout', 'team': 'Los Angeles Angels'},
            {'name': 'Shohei Ohtani', 'team': 'Los Angeles Angels'},
            {'name': 'Aaron Judge', 'team': 'New York Yankees'},
            {'name': 'Juan Soto', 'team': 'New York Yankees'},
            {'name': 'Rafael Devers', 'team': 'Boston Red Sox'}
        ]
        
        nba_players_data = [
            {'name': 'LeBron James', 'team': 'Los Angeles Lakers'},
            {'name': 'Stephen Curry', 'team': 'Golden State Warriors'},
            {'name': 'Kevin Durant', 'team': 'Phoenix Suns'},
            {'name': 'Giannis Antetokounmpo', 'team': 'Milwaukee Bucks'},
            {'name': 'Nikola Jokić', 'team': 'Denver Nuggets'}
        ]
        
        # Create Player records
        players = {}
        
        # Create MLB players
        for player_data in mlb_players_data:
            player = Player(
                name=player_data['name'],
                team=player_data['team'],
                sport='MLB',
                position='Player'
            )
            db.session.add(player)
            db.session.flush()  # Get the ID
            players[player_data['name']] = player.id
        
        # Create NBA players
        for player_data in nba_players_data:
            player = Player(
                name=player_data['name'],
                team=player_data['team'],
                sport='NBA',
                position='Player'
            )
            db.session.add(player)
            db.session.flush()  # Get the ID
            players[player_data['name']] = player.id
        
        # Generate props with different game times
        now = datetime.utcnow()
        props_created = 0
        
        # MLB Props - Some in the past (finished), some now (live), some future (upcoming)
        for i, player_data in enumerate(mlb_players_data):
            player_id = players[player_data['name']]
            
            for prop_type in ['HITS', 'TOTAL_BASES', 'RUNS', 'STRIKEOUTS']:
                for difficulty, prob in [('EASY', 0.80), ('MEDIUM', 0.45), ('HARD', 0.20)]:
                    
                    # Vary game times
                    if i < 2:  # First 2 players - games in the past (finished)
                        game_time = now - timedelta(hours=random.randint(2, 4))
                        game_status = GameStatus.FINISHED
                    elif i < 4:  # Next 2 players - games happening now (live)
                        game_time = now - timedelta(minutes=random.randint(30, 90))
                        game_status = GameStatus.LIVE
                    else:  # Last player - games in the future (upcoming)
                        game_time = now + timedelta(hours=random.randint(1, 6))
                        game_status = GameStatus.SCHEDULED
                    
                    # Generate line values based on prop type and difficulty
                    if prop_type == 'HITS':
                        if difficulty == 'EASY':
                            line_value = round(random.uniform(0.5, 1.0), 1)
                        elif difficulty == 'MEDIUM':
                            line_value = round(random.uniform(1.0, 2.0), 1)
                        else:
                            line_value = round(random.uniform(2.0, 3.0), 1)
                    elif prop_type == 'TOTAL_BASES':
                        if difficulty == 'EASY':
                            line_value = round(random.uniform(1.0, 2.0), 1)
                        elif difficulty == 'MEDIUM':
                            line_value = round(random.uniform(2.0, 4.0), 1)
                        else:
                            line_value = round(random.uniform(4.0, 6.0), 1)
                    elif prop_type == 'RUNS':
                        if difficulty == 'EASY':
                            line_value = round(random.uniform(0.5, 0.8), 1)
                        elif difficulty == 'MEDIUM':
                            line_value = round(random.uniform(0.8, 1.2), 1)
                        else:
                            line_value = round(random.uniform(1.2, 1.8), 1)
                    elif prop_type == 'STRIKEOUTS':
                        if difficulty == 'EASY':
                            line_value = round(random.uniform(3.0, 5.0), 1)
                        elif difficulty == 'MEDIUM':
                            line_value = round(random.uniform(5.0, 7.0), 1)
                        else:
                            line_value = round(random.uniform(7.0, 9.0), 1)
                    
                    prop = Prop(
                        player_id=player_id,
                        sport='MLB',
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
        
        # NBA Props
        for i, player_data in enumerate(nba_players_data):
            player_id = players[player_data['name']]
            
            for prop_type in ['POINTS', 'REBOUNDS', 'ASSISTS', 'STEALS', 'BLOCKS']:
                for difficulty, prob in [('EASY', 0.80), ('MEDIUM', 0.45), ('HARD', 0.20)]:
                    
                    # Vary game times
                    if i < 2:  # First 2 players - games in the past (finished)
                        game_time = now - timedelta(hours=random.randint(2, 4))
                        game_status = GameStatus.FINISHED
                    elif i < 4:  # Next 2 players - games happening now (live)
                        game_time = now - timedelta(minutes=random.randint(30, 90))
                        game_status = GameStatus.LIVE
                    else:  # Last player - games in the future (upcoming)
                        game_time = now + timedelta(hours=random.randint(1, 6))
                        game_status = GameStatus.SCHEDULED
                    
                    # Generate line values based on prop type and difficulty
                    if prop_type == 'POINTS':
                        if difficulty == 'EASY':
                            line_value = round(random.uniform(15.0, 25.0), 1)
                        elif difficulty == 'MEDIUM':
                            line_value = round(random.uniform(25.0, 35.0), 1)
                        else:
                            line_value = round(random.uniform(35.0, 45.0), 1)
                    elif prop_type == 'REBOUNDS':
                        if difficulty == 'EASY':
                            line_value = round(random.uniform(3.0, 6.0), 1)
                        elif difficulty == 'MEDIUM':
                            line_value = round(random.uniform(6.0, 10.0), 1)
                        else:
                            line_value = round(random.uniform(10.0, 15.0), 1)
                    elif prop_type == 'ASSISTS':
                        if difficulty == 'EASY':
                            line_value = round(random.uniform(3.0, 6.0), 1)
                        elif difficulty == 'MEDIUM':
                            line_value = round(random.uniform(6.0, 10.0), 1)
                        else:
                            line_value = round(random.uniform(10.0, 15.0), 1)
                    elif prop_type == 'STEALS':
                        if difficulty == 'EASY':
                            line_value = round(random.uniform(0.5, 1.5), 1)
                        elif difficulty == 'MEDIUM':
                            line_value = round(random.uniform(1.5, 2.5), 1)
                        else:
                            line_value = round(random.uniform(2.5, 4.0), 1)
                    elif prop_type == 'BLOCKS':
                        if difficulty == 'EASY':
                            line_value = round(random.uniform(0.5, 1.5), 1)
                        elif difficulty == 'MEDIUM':
                            line_value = round(random.uniform(1.5, 2.5), 1)
                        else:
                            line_value = round(random.uniform(2.5, 4.0), 1)
                    
                    prop = Prop(
                        player_id=player_id,
                        sport='NBA',
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
        
        # Commit all props
        db.session.commit()
        
        print(f"✅ Generated {props_created} props with live game times")
        print(f"📊 Game Status Breakdown:")
        print(f"   - SCHEDULED (Upcoming): {Prop.query.filter_by(game_status=GameStatus.SCHEDULED).count()}")
        print(f"   - LIVE (In Progress): {Prop.query.filter_by(game_status=GameStatus.LIVE).count()}")
        print(f"   - FINISHED (Completed): {Prop.query.filter_by(game_status=GameStatus.FINISHED).count()}")
        print(f"🎯 Ready for live trading testing!")

if __name__ == '__main__':
    generate_live_props() 