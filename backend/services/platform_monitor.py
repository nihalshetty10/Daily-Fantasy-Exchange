#!/usr/bin/env python3
"""
Platform Stats Monitor - Internal tracking for creators only
Updates every 10 seconds and logs to local file
"""

import os
import time
import json
import datetime
from threading import Thread
from backend.services.profit_tracker import ProfitTracker
from backend.db import get_db_session
from sqlalchemy import text

class PlatformMonitor:
    def __init__(self, log_file="platform_stats.log"):
        self.log_file = log_file
        self.running = False
        self.monitor_thread = None
        
    def start_monitoring(self):
        """Start the platform monitoring in a separate thread"""
        if self.running:
            return
            
        self.running = True
        self.monitor_thread = Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("📊 Platform Stats Monitor started (internal logging only)")
        
    def stop_monitoring(self):
        """Stop the platform monitoring"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        print("📊 Platform Stats Monitor stopped")
        
    def _monitor_loop(self):
        """Main monitoring loop - runs every 10 seconds"""
        while self.running:
            try:
                stats = self._collect_platform_stats()
                self._log_stats(stats)
                time.sleep(10)  # Update every 10 seconds
            except Exception as e:
                print(f"❌ Error in platform monitoring: {e}")
                time.sleep(10)  # Continue even if there's an error
                
    def _collect_platform_stats(self):
        """Collect current platform statistics"""
        try:
            # Get platform net profit
            net_profit = ProfitTracker.get_net_profit()
            
            # Get total users
            with next(get_db_session()) as db:
                result = db.execute(text("SELECT COUNT(*) as total FROM users WHERE is_active = 1")).fetchone()
                total_users = result.total if result else 0
                
                # Get active users today (users who logged in today)
                today = datetime.date.today()
                result = db.execute(text("""
                    SELECT COUNT(DISTINCT user_id) as active_today 
                    FROM transactions 
                    WHERE DATE(timestamp) = :today
                """), {'today': today}).fetchone()
                active_today = result.active_today if result else 0
                
                # Get total transactions today
                result = db.execute(text("""
                    SELECT COUNT(*) as transactions_today 
                    FROM transactions 
                    WHERE DATE(timestamp) = :today
                """), {'today': today}).fetchone()
                transactions_today = result.transactions_today if result else 0
                
                # Get total volume today
                result = db.execute(text("""
                    SELECT COALESCE(SUM(ABS(amount)), 0) as volume_today 
                    FROM transactions 
                    WHERE DATE(timestamp) = :today
                """), {'today': today}).fetchone()
                volume_today = float(result.volume_today) if result else 0.0
                
            return {
                'timestamp': datetime.datetime.now().isoformat(),
                'net_profit': net_profit,
                'total_users': total_users,
                'active_today': active_today,
                'transactions_today': transactions_today,
                'volume_today': volume_today
            }
            
        except Exception as e:
            print(f"❌ Error collecting platform stats: {e}")
            return {
                'timestamp': datetime.datetime.now().isoformat(),
                'error': str(e)
            }
            
    def _log_stats(self, stats):
        """Log stats to local file"""
        try:
            # Create log entry
            log_entry = {
                'timestamp': stats['timestamp'],
                'platform_net_profit': stats.get('net_profit', 0),
                'total_users': stats.get('total_users', 0),
                'active_users_today': stats.get('active_today', 0),
                'transactions_today': stats.get('transactions_today', 0),
                'volume_today': stats.get('volume_today', 0)
            }
            
            # Write to log file
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
                
            # Print to console (for creators to see)
            print(f"📊 Platform Stats [{stats['timestamp']}]: "
                  f"Net Profit: ${stats.get('net_profit', 0):.2f}, "
                  f"Users: {stats.get('total_users', 0)}, "
                  f"Active Today: {stats.get('active_today', 0)}, "
                  f"Transactions: {stats.get('transactions_today', 0)}, "
                  f"Volume: ${stats.get('volume_today', 0):.2f}")
                  
        except Exception as e:
            print(f"❌ Error logging platform stats: {e}")
            
    def get_recent_stats(self, hours=24):
        """Get recent stats from log file (for creators to review)"""
        try:
            if not os.path.exists(self.log_file):
                return []
                
            stats = []
            cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=hours)
            
            with open(self.log_file, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        entry_time = datetime.datetime.fromisoformat(entry['timestamp'])
                        if entry_time >= cutoff_time:
                            stats.append(entry)
                    except:
                        continue
                        
            return stats[-100:]  # Return last 100 entries
            
        except Exception as e:
            print(f"❌ Error reading platform stats: {e}")
            return []

# Global instance
platform_monitor = PlatformMonitor()
