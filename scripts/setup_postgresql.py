#!/usr/bin/env python3
"""
Setup PostgreSQL database for PropTrader
"""

import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def setup_postgresql():
    """Setup PostgreSQL database and user"""
    
    # Database configuration
    DB_NAME = "proptrader"
    DB_USER = "proptrader_user"
    DB_PASSWORD = "proptrader_password"
    DB_HOST = "localhost"
    DB_PORT = "5432"
    
    print("🐘 Setting up PostgreSQL database...")
    
    try:
        # Connect to PostgreSQL server (default database)
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user="nihal",  # macOS default user
            database="postgres"  # Connect to default database
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Create database
        print(f"📊 Creating database '{DB_NAME}'...")
        cursor.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
        cursor.execute(f"CREATE DATABASE {DB_NAME}")
        print(f"✅ Database '{DB_NAME}' created successfully")
        
        # Create user
        print(f"👤 Creating user '{DB_USER}'...")
        cursor.execute(f"DROP USER IF EXISTS {DB_USER}")
        cursor.execute(f"CREATE USER {DB_USER} WITH PASSWORD '{DB_PASSWORD}'")
        cursor.execute(f"GRANT ALL PRIVILEGES ON DATABASE {DB_NAME} TO {DB_USER}")
        print(f"✅ User '{DB_USER}' created successfully")
        
        cursor.close()
        conn.close()
        
        # Test connection to new database
        print("🔗 Testing connection to new database...")
        test_conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        test_conn.close()
        print("✅ Connection test successful")
        
        # Set environment variable
        DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        print(f"\n🔧 Set this environment variable:")
        print(f"export DATABASE_URL='{DATABASE_URL}'")
        print(f"\nOr add to your .env file:")
        print(f"DATABASE_URL={DATABASE_URL}")
        
        return DATABASE_URL
        
    except psycopg2.OperationalError as e:
        print(f"❌ PostgreSQL connection error: {e}")
        print("\n💡 Make sure PostgreSQL is installed and running:")
        print("   - Install: brew install postgresql")
        print("   - Start: brew services start postgresql")
        print("   - Or use: pg_ctl -D /usr/local/var/postgres start")
        return None
    except Exception as e:
        print(f"❌ Error setting up PostgreSQL: {e}")
        return None

if __name__ == "__main__":
    setup_postgresql()
