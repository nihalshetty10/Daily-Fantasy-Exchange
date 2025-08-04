#!/usr/bin/env python3
"""
Live Game Tracker Service
Updates prop odds in real-time during games
"""

import threading
import time
import random
from datetime import datetime, timedelta
from flask import current_app
from sqlalchemy.orm import sessionmaker
from ..models import db, Prop, GameStatus

class LiveGameTracker:
    def __init__(self):
        self.running = False
        self.update_thread = None
        self.update_interval = 30  # seconds
        
    def start(self):
        """Start the live tracking service"""
        if not self.running:
            self.running = True
            self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
            self.update_thread.start()
            print("🔄 Live Game Tracker started")
    
    def stop(self):
        """Stop the live tracking service"""
        self.running = False
        if self.update_thread:
            self.update_thread.join()
            print("🛑 Live Game Tracker stopped")
    
    def _update_loop(self):
        """Main update loop for live games"""
        while self.running:
            try:
                with current_app.app_context():
                    self._update_live_games()
                time.sleep(self.update_interval)
            except Exception as e:
                print(f"❌ Error in live tracker: {e}")
                time.sleep(5)  # Wait before retrying
    
    def _update_live_games(self):
        """Update all live games and their props"""
        # Get all props for games that should be live
        now = datetime.utcnow()
        
        # Find props that should be live (game time has started but not ended)
        live_props = Prop.query.filter(
            Prop.game_time <= now,
            Prop.game_time >= now - timedelta(hours=4),  # Within last 4 hours
            Prop.game_status.in_([GameStatus.SCHEDULED, GameStatus.LIVE])
        ).all()
        
        for prop in live_props:
            self._update_prop_live_data(prop)
        
        # Commit changes
        if live_props:
            db.session.commit()
            print(f"📊 Updated {len(live_props)} live props")
    
    def _update_prop_live_data(self, prop):
        """Update live data for a specific prop"""
        now = datetime.utcnow()
        game_start = prop.game_time
        
        # Determine game status and time
        if now < game_start:
            # Game hasn't started yet
            prop.update_game_status(GameStatus.SCHEDULED)
            return
        
        # Game has started - determine if it's live or finished
        game_duration = self._get_game_duration(prop.sport)
        game_end = game_start + timedelta(minutes=game_duration)
        
        if now > game_end:
            # Game is finished
            final_value = self._simulate_final_player_value(prop)
            prop.update_game_status(
                GameStatus.FINISHED,
                game_time="FINAL",
                score="FINAL",
                player_value=final_value
            )
        else:
            # Game is live
            current_time = self._get_current_game_time(prop.sport, game_start, now)
            current_score = self._simulate_current_score(prop.sport)
            current_value = self._simulate_current_player_value(prop, game_start, now)
            
            prop.update_game_status(
                GameStatus.LIVE,
                game_time=current_time,
                score=current_score,
                player_value=current_value
            )
    
    def _get_game_duration(self, sport):
        """Get typical game duration in minutes"""
        durations = {
            'NBA': 150,  # 2.5 hours
            'MLB': 180,  # 3 hours
            'NFL': 210   # 3.5 hours
        }
        return durations.get(sport, 150)
    
    def _get_current_game_time(self, sport, game_start, now):
        """Get current game time as string"""
        elapsed = now - game_start
        elapsed_minutes = elapsed.total_seconds() / 60
        
        if sport == 'NBA':
            # NBA: 4 quarters, 12 minutes each
            total_minutes = 48
            if elapsed_minutes >= total_minutes:
                return "FINAL"
            
            quarter = int(elapsed_minutes / 12) + 1
            quarter_time = elapsed_minutes % 12
            minutes = int(quarter_time)
            seconds = int((quarter_time - minutes) * 60)
            return f"Q{quarter} {minutes:02d}:{seconds:02d}"
            
        elif sport == 'MLB':
            # MLB: 9 innings, roughly 20 minutes per inning
            total_minutes = 180
            if elapsed_minutes >= total_minutes:
                return "FINAL"
            
            inning = int(elapsed_minutes / 20) + 1
            return f"T{inning} 2-1"  # Mock score
            
        elif sport == 'NFL':
            # NFL: 4 quarters, 15 minutes each
            total_minutes = 60
            if elapsed_minutes >= total_minutes:
                return "FINAL"
            
            quarter = int(elapsed_minutes / 15) + 1
            quarter_time = elapsed_minutes % 15
            minutes = int(quarter_time)
            seconds = int((quarter_time - minutes) * 60)
            return f"Q{quarter} {minutes:02d}:{seconds:02d}"
        
        return "LIVE"
    
    def _simulate_current_score(self, sport):
        """Simulate current game score"""
        if sport == 'NBA':
            team1_score = random.randint(80, 120)
            team2_score = random.randint(80, 120)
            return f"LAL {team1_score}-{team2_score} GSW"
        elif sport == 'MLB':
            team1_score = random.randint(2, 8)
            team2_score = random.randint(2, 8)
            return f"NYY {team1_score}-{team2_score} BOS"
        elif sport == 'NFL':
            team1_score = random.randint(14, 35)
            team2_score = random.randint(14, 35)
            return f"KC {team1_score}-{team2_score} BUF"
        return "LIVE"
    
    def _simulate_current_player_value(self, prop, game_start, now):
        """Simulate current player stat value"""
        elapsed = now - game_start
        elapsed_minutes = elapsed.total_seconds() / 60
        
        # Calculate expected progress based on game time
        game_duration = self._get_game_duration(prop.sport)
        progress_ratio = min(1.0, elapsed_minutes / (game_duration * 0.8))  # 80% of game time
        
        # Base value based on prop type and difficulty
        base_value = self._get_base_value(prop)
        
        # Add some randomness and performance variation
        performance_factor = random.uniform(0.7, 1.3)
        current_value = base_value * progress_ratio * performance_factor
        
        # Round based on prop type
        if prop.prop_type in ['POINTS', 'REBOUNDS', 'ASSISTS', 'STEALS', 'BLOCKS']:
            return round(current_value, 1)
        elif prop.prop_type in ['HITS', 'TOTAL_BASES', 'RUNS', 'STRIKEOUTS']:
            return round(current_value, 1)
        
        return round(current_value, 1)
    
    def _simulate_final_player_value(self, prop):
        """Simulate final player stat value"""
        base_value = self._get_base_value(prop)
        final_factor = random.uniform(0.8, 1.2)
        final_value = base_value * final_factor
        
        if prop.prop_type in ['POINTS', 'REBOUNDS', 'ASSISTS', 'STEALS', 'BLOCKS']:
            return round(final_value, 1)
        elif prop.prop_type in ['HITS', 'TOTAL_BASES', 'RUNS', 'STRIKEOUTS']:
            return round(final_value, 1)
        
        return round(final_value, 1)
    
    def _get_base_value(self, prop):
        """Get base expected value for prop type and difficulty"""
        if prop.sport == 'NBA':
            if prop.prop_type == 'POINTS':
                if prop.difficulty.value == 'EASY':
                    return random.uniform(15, 25)
                elif prop.difficulty.value == 'MEDIUM':
                    return random.uniform(25, 35)
                else:  # HARD
                    return random.uniform(35, 45)
            elif prop.prop_type == 'REBOUNDS':
                if prop.difficulty.value == 'EASY':
                    return random.uniform(3, 6)
                elif prop.difficulty.value == 'MEDIUM':
                    return random.uniform(6, 10)
                else:
                    return random.uniform(10, 15)
            elif prop.prop_type == 'ASSISTS':
                if prop.difficulty.value == 'EASY':
                    return random.uniform(3, 6)
                elif prop.difficulty.value == 'MEDIUM':
                    return random.uniform(6, 10)
                else:
                    return random.uniform(10, 15)
        
        elif prop.sport == 'MLB':
            if prop.prop_type == 'HITS':
                if prop.difficulty.value == 'EASY':
                    return random.uniform(0.5, 1.0)
                elif prop.difficulty.value == 'MEDIUM':
                    return random.uniform(1.0, 2.0)
                else:
                    return random.uniform(2.0, 3.0)
            elif prop.prop_type == 'TOTAL_BASES':
                if prop.difficulty.value == 'EASY':
                    return random.uniform(1.0, 2.0)
                elif prop.difficulty.value == 'MEDIUM':
                    return random.uniform(2.0, 4.0)
                else:
                    return random.uniform(4.0, 6.0)
            elif prop.prop_type == 'RUNS':
                if prop.difficulty.value == 'EASY':
                    return random.uniform(0.5, 0.8)
                elif prop.difficulty.value == 'MEDIUM':
                    return random.uniform(0.8, 1.2)
                else:
                    return random.uniform(1.2, 1.8)
            elif prop.prop_type == 'STRIKEOUTS':
                if prop.difficulty.value == 'EASY':
                    return random.uniform(3.0, 5.0)
                elif prop.difficulty.value == 'MEDIUM':
                    return random.uniform(5.0, 7.0)
                else:
                    return random.uniform(7.0, 9.0)
        
        return prop.line_value

# Global tracker instance
live_tracker = LiveGameTracker() 