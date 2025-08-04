import os
from flask import Flask, render_template, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from config import config
from backend.models import db, User, Player, Prop, Contract, Portfolio, Trade
from backend.api.routes import app as api_app

def create_app(config_name='default'):
    """Create and configure the Flask application"""
    # Get the absolute path to the template directory
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend', 'templates')
    app = Flask(__name__, template_folder=template_dir)

    # Load configuration
    app.config.from_object(config[config_name])

    # Initialize extensions
    db.init_app(app)
    socketio = SocketIO(app, cors_allowed_origins="*")

    # Register blueprints
    app.register_blueprint(api_app, url_prefix='/api')

    # Add homepage route - redirect to login if not authenticated
    @app.route('/')
    def index():
        return redirect('/login')
    
    # Add login route
    @app.route('/login')
    def login():
        return render_template('login.html')
    
    # Add dashboard route - requires authentication
    @app.route('/dashboard')
    def dashboard():
        return render_template('dashboard.html')

    # Create database tables
    with app.app_context():
        db.create_all()

        # Create admin user if it doesn't exist
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(username='admin', email='admin@fantasyexchange.com', password='admin123')
            db.session.add(admin)
            db.session.commit()

    return app, socketio

def main():
    """Main application entry point"""
    app, socketio = create_app()

    # Run the application
    socketio.run(app, debug=True, host='127.0.0.1', port=8002)

if __name__ == '__main__':
    main() 