#!/usr/bin/env python3
"""
Daily Prop Generator - Runs at 7:30 AM every day
Scrapes today's games and generates fresh props
"""

import os
import sys
from datetime import datetime, timedelta
from run import create_app
from backend.models import db, Prop, Player
from scrape_today_games import generate_today_props

def main():
    """Generate fresh props for today's games"""
    print(f"🔄 Starting daily prop generation at {datetime.now()}")
    
    # Create app context
    app, socketio = create_app()
    
    with app.app_context():
        try:
            # Clear existing props
            print("🗑️ Clearing existing props...")
            Prop.query.delete()
            Player.query.delete()
            db.session.commit()
            print(f"✅ Cleared {Prop.query.count()} props and {Player.query.count()} players")
            
            # Generate fresh props for today
            print("📊 Generating fresh props for today's games...")
            generate_today_props()
            
            # Verify props were created
            prop_count = Prop.query.count()
            player_count = Player.query.count()
            print(f"✅ Successfully generated {prop_count} props for {player_count} players")
            
            # Show sample props
            sample_props = Prop.query.limit(5).all()
            print("\n📋 Sample props generated:")
            for prop in sample_props:
                player = Player.query.get(prop.player_id)
                print(f"  • {player.name if player else 'Unknown'} ({prop.sport}) - {prop.prop_type} {prop.line_value} ({prop.difficulty})")
            
        except Exception as e:
            print(f"❌ Error generating daily props: {str(e)}")
            db.session.rollback()
            sys.exit(1)

if __name__ == "__main__":
    main() 