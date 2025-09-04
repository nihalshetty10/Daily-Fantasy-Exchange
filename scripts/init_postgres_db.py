#!/usr/bin/env python3
"""
Initialize PostgreSQL database for PropTrader
"""

import os
import sys
import datetime
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.db import engine, Base, get_db_session
from backend.models.user import User
from backend.services.auth_service import AuthService

def init_database():
    """Initialize the database with tables and sample data"""
    print("🗄️  Initializing PropTrader database...")
    
    try:
        # Create all tables
        print("📋 Creating database tables...")
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully")
        
        # Create sample users
        print("👥 Creating sample users...")
        
        # Admin user
        admin_user = AuthService.create_user(
            username="admin",
            email="admin@proptrader.com",
            password="admin123",
            first_name="Admin",
            last_name="User",
            date_of_birth=datetime.date(1990, 1, 1),
            phone_number="555-0001",
            city="New York",
            state="NY",
            country="US"
        )
        
        if admin_user:
            # Make admin user an admin
            with next(get_db_session()) as db:
                admin_user.is_admin = True
                admin_user.is_verified = True
                db.add(admin_user)
                db.commit()
            print("✅ Admin user created: admin / admin123")
        
        # Demo user
        demo_user = AuthService.create_user(
            username="demo",
            email="demo@proptrader.com",
            password="demo123",
            first_name="Demo",
            last_name="User",
            date_of_birth=datetime.date(1995, 5, 15),
            phone_number="555-0002",
            city="Los Angeles",
            state="CA",
            country="US"
        )
        
        if demo_user:
            demo_user.is_verified = True
            with next(get_db_session()) as db:
                db.add(demo_user)
                db.commit()
            print("✅ Demo user created: demo / demo123")
        
        # Test user
        test_user = AuthService.create_user(
            username="testuser",
            email="test@proptrader.com",
            password="test123",
            first_name="Test",
            last_name="User",
            date_of_birth=datetime.date(1992, 8, 20),
            phone_number="555-0003",
            city="Chicago",
            state="IL",
            country="US"
        )
        
        if test_user:
            test_user.is_verified = True
            with next(get_db_session()) as db:
                db.add(test_user)
                db.commit()
            print("✅ Test user created: testuser / test123")
        
        print("\n🎉 Database initialization completed successfully!")
        print("\n📝 Sample users created:")
        print("   Admin:  admin / admin123")
        print("   Demo:   demo / demo123")
        print("   Test:   testuser / test123")
        print("\n🌐 You can now start the application with: python app.py")
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_database()
