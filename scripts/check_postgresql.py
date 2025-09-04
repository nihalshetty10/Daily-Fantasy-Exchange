#!/usr/bin/env python3
"""
Check PostgreSQL availability and provide setup instructions
"""

import subprocess
import sys

def check_postgresql():
    """Check if PostgreSQL is available"""
    
    print("🔍 Checking PostgreSQL availability...")
    
    # Check if PostgreSQL is installed
    try:
        result = subprocess.run(['psql', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ PostgreSQL installed: {result.stdout.strip()}")
        else:
            print("❌ PostgreSQL not found")
            return False
    except FileNotFoundError:
        print("❌ PostgreSQL not found")
        return False
    
    # Check if PostgreSQL service is running
    try:
        result = subprocess.run(['pg_isready'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ PostgreSQL service is running")
            return True
        else:
            print("❌ PostgreSQL service is not running")
            return False
    except FileNotFoundError:
        print("❌ pg_isready command not found")
        return False

def provide_instructions():
    """Provide setup instructions"""
    
    print("\n📋 PostgreSQL Setup Instructions:")
    print("=" * 50)
    
    print("\n1. Install PostgreSQL:")
    print("   macOS: brew install postgresql")
    print("   Ubuntu: sudo apt-get install postgresql postgresql-contrib")
    print("   Windows: Download from https://www.postgresql.org/download/")
    
    print("\n2. Start PostgreSQL service:")
    print("   macOS: brew services start postgresql")
    print("   Ubuntu: sudo systemctl start postgresql")
    print("   Windows: Start PostgreSQL service from Services")
    
    print("\n3. Set up database:")
    print("   python scripts/setup_postgresql.py")
    
    print("\n4. Set environment variable:")
    print("   export DATABASE_URL='postgresql://proptrader_user:proptrader_password@localhost:5432/proptrader'")
    
    print("\n5. Restart the application:")
    print("   python app.py")

if __name__ == "__main__":
    if check_postgresql():
        print("\n🎉 PostgreSQL is ready!")
        print("You can now run: python scripts/setup_postgresql.py")
    else:
        provide_instructions()
