#!/usr/bin/env python3
"""
ML Prop Trader - Complete Web Application
Integrates ML prop generation with live trading platform
"""

import os
from flask import Flask, render_template, redirect, jsonify
from backend.services.live_tracker import LiveGameTracker

def create_app():
    app = Flask(__name__, template_folder='frontend/templates')

    # Basic configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')

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

    return app

# Create the Flask app instance
app = create_app()

if __name__ == '__main__':
    # Start the live tracker automatically as a background service
    print("🚀 Starting Live Game Tracker as background service...")
    live_tracker = LiveGameTracker()
    live_tracker.start_tracking()
    
    # Production settings for AWS
    port = int(os.environ.get('PORT', 8000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Start the Flask web app
    app.run(debug=debug, host='0.0.0.0', port=port) 