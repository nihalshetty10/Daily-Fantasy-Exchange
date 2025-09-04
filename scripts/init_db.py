#!/usr/bin/env python3
import os
from getpass import getpass
from sqlalchemy import text
from backend.db import engine, Base, SessionLocal
from backend.models.user import User


def create_tables():
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created (if not existing)")


def seed_admin():
    username = os.environ.get('ADMIN_USERNAME', 'admin')
    password = os.environ.get('ADMIN_PASSWORD')
    email = os.environ.get('ADMIN_EMAIL', None)

    if not password:
        try:
            password = getpass("Set admin password (ADMIN_PASSWORD env also supported): ")
        except Exception:
            # Non-interactive environments
            raise SystemExit("❌ ADMIN_PASSWORD not set and no TTY available")

    session = SessionLocal()
    try:
        # Check if exists
        existing = session.query(User).filter(User.username == username).first()
        if existing:
            print(f"ℹ️ Admin user '{username}' already exists. Skipping seed.")
            return
        user = User(username=username, email=email)
        user.set_password(password)
        user.is_admin = True
        session.add(user)
        session.commit()
        print(f"✅ Seeded admin user '{username}'")
    finally:
        session.close()


if __name__ == '__main__':
    print("🚀 Initializing database...")
    print(f"Using DATABASE_URL={os.environ.get('DATABASE_URL', 'sqlite:///proptrader.db')}")
    create_tables()
    seed_admin()
    print("🎉 Done.") 