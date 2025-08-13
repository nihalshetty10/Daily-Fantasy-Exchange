#!/usr/bin/env python3
"""
Setup database tables for Live Game Tracker
"""

import sqlite3
import os
from datetime import datetime

def setup_live_tracker_tables():
    """Create necessary tables for live game tracking"""
    
    # Ensure instance directory exists
    os.makedirs('instance', exist_ok=True)
    
    # Connect to database
    conn = sqlite3.connect('instance/proptrader.db')
    cursor = conn.cursor()
    
    try:
        # Create games table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS games (
                game_id INTEGER PRIMARY KEY,
                status TEXT DEFAULT 'Preview',
                game_date TEXT,
                home_team TEXT,
                away_team TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create contracts table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contracts (
                contract_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                prop_id INTEGER,
                direction TEXT,  -- 'over' or 'under'
                line REAL,       -- The line value
                quantity INTEGER DEFAULT 1,
                status TEXT DEFAULT 'active',  -- 'active', 'settled'
                result TEXT,     -- 'won' or 'lost'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                settled_at TIMESTAMP,
                game_id INTEGER
            )
        """)
        
        # Create users table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                email TEXT,
                password_hash TEXT,
                portfolio_balance REAL DEFAULT 1000.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create props table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS props (
                prop_id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER,
                stat TEXT,
                line REAL,
                direction TEXT,
                difficulty TEXT,
                game_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Add missing columns to existing tables
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN portfolio_balance REAL DEFAULT 1000.0")
            print("✅ Added portfolio_balance column to users table")
        except sqlite3.OperationalError:
            print("ℹ️ portfolio_balance column already exists in users table")
        
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            print("✅ Added created_at column to users table")
        except sqlite3.OperationalError:
            print("ℹ️ created_at column already exists in users table")
        
        # Insert demo user if not exists
        cursor.execute("""
            INSERT OR IGNORE INTO users (username, email, password_hash, portfolio_balance)
            VALUES ('admin', 'admin@fantasyexchange.com', 'demo_hash', 1000.0)
        """)
        
        # Commit changes
        conn.commit()
        print("✅ Live tracker database tables setup completed")
        
        # Show table info
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"📊 Database tables: {[table[0] for table in tables]}")
        
        # Show users table structure
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        print(f"👤 Users table columns: {[col[1] for col in columns]}")
        
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    setup_live_tracker_tables() 