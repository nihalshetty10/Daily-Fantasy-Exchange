#!/usr/bin/env python3
"""
ML Prop Trader - Complete Web Application
Integrates ML prop generation with live trading platform
"""

import os
from flask import Flask, render_template, redirect, jsonify, request, session
from backend.services.live_tracker import LiveGameTracker
from backend.db import Base, engine, SessionLocal
from backend.models.user import User
from backend.api.auth_routes import auth_bp


def create_app():
    app = Flask(__name__, template_folder='frontend/templates')

    # Basic configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')
    
    # Register blueprints
    app.register_blueprint(auth_bp)

    # Ensure tables exist (safe to call repeatedly)
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"DB init error: {e}")

    # Routes
    @app.route('/')
    def index():
        return redirect('/i')
    
    @app.route('/i')
    def website_i():
        return render_template('i.html')
    
    @app.route('/i8')
    def website_i8():
        return render_template('i8.html')
    
    @app.route('/login')
    def login():
        return redirect('/i8')
    
    @app.route('/mlb_props.json')
    def serve_mlb_props():
        """Serve the MLB props JSON file"""
        try:
            with open('mlb_props.json', 'r') as f:
                return f.read(), 200, {'Content-Type': 'application/json'}
        except FileNotFoundError:
            return jsonify({'error': 'MLB props not found'}), 404

    @app.route('/nfl_props.json')
    def serve_nfl_props():
        """Serve the NFL props JSON file"""
        try:
            with open('nfl_props.json', 'r') as f:
                return f.read(), 200, {'Content-Type': 'application/json'}
        except FileNotFoundError:
            return jsonify({'error': 'NFL props not found'}), 404

    # Minimal API: create user (POST)
    @app.route('/api/users', methods=['POST'])
    def api_create_user():
        payload = request.get_json(silent=True) or {}
        username = (payload.get('username') or '').strip()
        password = payload.get('password') or ''
        email = (payload.get('email') or '').strip() or None
        if not username or not password:
            return jsonify({'error': 'username and password required'}), 400
        session = SessionLocal()
        try:
            # Check duplicates
            exists = session.query(User).filter(User.username == username).first()
            if exists:
                return jsonify({'error': 'username already exists'}), 409
            user = User(username=username, email=email)
            user.set_password(password)
            session.add(user)
            session.commit()
            return jsonify({'id': user.id, 'username': user.username}), 201
        except Exception as e:
            session.rollback()
            return jsonify({'error': 'failed to create user', 'details': str(e)}), 500
        finally:
            session.close()

    return app

# Create the Flask app instance
app = create_app()

if __name__ == '__main__':
    # Start the live tracker automatically as a background service
    print("🚀 Starting Live Game Tracker as background service...")
    live_tracker = LiveGameTracker()
    live_tracker.start_tracking()
    
    # Production settings for AWS
    port = int(os.environ.get('PORT', 8007))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Start the Flask web app
    app.run(debug=debug, host='0.0.0.0', port=port) 