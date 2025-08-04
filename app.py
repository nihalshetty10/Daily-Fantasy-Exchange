#!/usr/bin/env python3
"""
ML Prop Trader - Complete Web Application
Integrates ML prop generation with live trading platform
"""

import os
from flask import Flask, render_template, redirect, request, jsonify
from datetime import datetime, timedelta
import threading
import time
import json

# Import our ML prop generator
from ml_prop_generator import MLPropGenerator

def create_app():
    """Create and configure the Flask application"""
    # Get the absolute path to the template directory
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend', 'templates')
    app = Flask(__name__, template_folder=template_dir)

    # Simple configuration
    app.config['SECRET_KEY'] = 'your-secret-key-here'
    app.config['PROPS_FILE'] = 'generated_props.json'
    
    # Initialize ML prop generator
    ml_generator = MLPropGenerator()
    
    # Global variables to store props and status
    app.generated_props = []
    app.last_generation = None
    app.generation_running = False
    
    # User tracking for purchases
    app.user_purchases = {}  # {user_id: {prop_id: quantity}}
    app.prop_purchases = {}  # {prop_id: {user_id: quantity}}
    
    def save_props_to_file():
        """Save props to JSON file"""
        try:
            with open(app.config['PROPS_FILE'], 'w') as f:
                json.dump({
                    'props': app.generated_props,
                    'last_generation': app.last_generation.isoformat() if app.last_generation else None
                }, f, indent=2)
        except Exception as e:
            print(f"Error saving props: {e}")
    
    def load_props_from_file():
        """Load props from JSON file"""
        try:
            if os.path.exists(app.config['PROPS_FILE']):
                with open(app.config['PROPS_FILE'], 'r') as f:
                    data = json.load(f)
                    app.generated_props = data.get('props', [])
                    last_gen = data.get('last_generation')
                    app.last_generation = datetime.fromisoformat(last_gen) if last_gen else None
        except Exception as e:
            print(f"Error loading props: {e}")
    
    def auto_generate_props():
        """Automatically generate props in background"""
        while True:
            try:
                # Check if it's a new day (after 6 AM)
                now = datetime.now()
                if now.hour >= 6:  # Generate after 6 AM
                    # Check if we already generated props today
                    if (app.last_generation is None or 
                        app.last_generation.date() < now.date()):
                        
                        print("🔄 Auto-generating today's props...")
                        app.generation_running = True
                        
                        # Generate props
                        props = ml_generator.generate_today_props()
                        
                        if props:
                            app.generated_props = props
                            app.last_generation = now
                            save_props_to_file()
                            print(f"✅ Auto-generated {len(props)} props")
                        else:
                            print("⚠️ No props generated in auto-run")
                        
                        app.generation_running = False
                
                # Sleep for 1 hour before checking again
                time.sleep(3600)  # 1 hour
                
            except Exception as e:
                print(f"❌ Error in auto-generation: {e}")
                app.generation_running = False
                time.sleep(3600)  # Sleep for 1 hour on error
    
    # Start auto-generation thread
    auto_thread = threading.Thread(target=auto_generate_props, daemon=True)
    auto_thread.start()
    
    # Load existing props on startup
    load_props_from_file()

    # Routes
    @app.route('/')
    def index():
        return redirect('/dashboard')
    
    @app.route('/login')
    def login():
        return render_template('login.html')
    
    @app.route('/dashboard')
    def dashboard():
        return render_template('dashboard.html')

    @app.route('/api/test')
    def test_api():
        """Test endpoint to verify API is working"""
        return jsonify({
            'success': True,
            'message': 'API is working!',
            'timestamp': datetime.utcnow().isoformat()
        })

    @app.route('/api/generate-today-props', methods=['POST'])
    def generate_today_props():
        """Generate today's props using ML (manual trigger)"""
        try:
            if app.generation_running:
                return jsonify({
                    'success': False,
                    'message': 'Generation already in progress'
                }), 400
            
            print("🚀 Starting manual ML prop generation...")
            app.generation_running = True
            
            # Generate props using ML
            props = ml_generator.generate_today_props()
            
            if not props:
                app.generation_running = False
                return jsonify({
                    'success': False,
                    'message': 'No props generated - no games found or insufficient data'
                }), 400
            
            # Save props
            app.generated_props = props
            app.last_generation = datetime.utcnow()
            save_props_to_file()
            
            app.generation_running = False
            
            return jsonify({
                'success': True,
                'message': f'Generated {len(props)} props successfully',
                'props_count': len(props),
                'sample_props': [
                    {
                        'player_name': prop['player_name'],
                        'prop_type': prop['prop_type'],
                        'line_value': prop['line_value'],
                        'difficulty': prop['difficulty'],
                        'opponent': prop['opponent']
                    } for prop in props[:5]
                ]
            })
            
        except Exception as e:
            app.generation_running = False
            return jsonify({
                'success': False,
                'message': f'Error generating props: {str(e)}'
            }), 500

    @app.route('/api/ml-status')
    def get_ml_status():
        """Get ML generation status"""
        try:
            recent_props = len(app.generated_props)
            last_gen = app.last_generation.strftime('%Y-%m-%d %H:%M') if app.last_generation else 'None'
            
            return jsonify({
                'ml_active': True,
                'recent_props': recent_props,
                'last_generation': last_gen,
                'generation_running': app.generation_running
            })
            
        except Exception as e:
            return jsonify({
                'ml_active': False,
                'error': str(e)
            }), 500

    @app.route('/api/clear-props', methods=['POST'])
    def clear_props():
        """Clear all props"""
        try:
            app.generated_props = []
            app.last_generation = None
            save_props_to_file()
            
            return jsonify({
                'success': True,
                'message': 'All props cleared successfully'
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error clearing props: {str(e)}'
            }), 500

    @app.route('/api/market/props')
    def get_props():
        """Get all generated props"""
        try:
            # Convert props to display format
            props_data = []
            for prop in app.generated_props:
                props_data.append({
                    'id': len(props_data) + 1,
                    'player_name': prop['player_name'],
                    'player_team': prop['team'],
                    'player_position': prop['position'],
                    'sport': 'MLB',
                    'prop_type': prop['prop_type'],
                    'line_value': prop['line_value'],
                    'difficulty': prop['difficulty'],
                    'implied_probability': prop['implied_probability'],
                    'opponent_info': prop['opponent'],
                    'game_time': prop['game_time'],
                    'status_badge': 'UPCOMING',
                    'game_status': 'UPCOMING',
                    'is_tradeable': True,
                    'live_contract_price': 0.50,  # Default price
                    'available_contracts': 100 - sum(app.prop_purchases.get(len(props_data) + 1, {}).values()),
                    'total_contracts': 100,
                    'sold_contracts': sum(app.prop_purchases.get(len(props_data) + 1, {}).values()),
                    'formatted_game_time': prop['game_time'],
                    'current_game_time': None,
                    'live_score': None,
                    'player_current_value': None
                })
            
            return jsonify({
                'props': props_data,
                'total_count': len(props_data)
            })
            
        except Exception as e:
            return jsonify({'error': f'Error loading props: {str(e)}'}), 500

    @app.route('/api/market/live-updates')
    def get_live_updates():
        """Get live updates for props"""
        try:
            updates = []
            for i, prop in enumerate(app.generated_props):
                updates.append({
                    'prop_id': i + 1,
                    'game_status': 'UPCOMING',
                    'current_game_time': None,
                    'live_score': None,
                    'player_current_value': None,
                    'live_implied_probability': prop['implied_probability'],
                    'live_contract_price': 0.50,
                    'trading_active': True,
                    'last_update': datetime.utcnow().isoformat()
                })
            
            return jsonify({'updates': updates})
            
        except Exception as e:
            return jsonify({'error': f'Error getting live updates: {str(e)}'}), 500

    @app.route('/api/portfolio')
    def get_portfolio():
        """Get user portfolio"""
        try:
            user_id = request.args.get('user_id', 'default_user')
            
            # Get user's holdings
            user_holdings = app.user_purchases.get(user_id, {})
            portfolio = []
            
            for prop_id, quantity in user_holdings.items():
                if quantity > 0 and prop_id <= len(app.generated_props):
                    prop = app.generated_props[prop_id - 1]  # prop_id is 1-indexed
                    portfolio.append({
                        'prop_id': prop_id,
                        'player_name': prop['player_name'],
                        'prop_type': prop['prop_type'],
                        'line_value': prop['line_value'],
                        'difficulty': prop['difficulty'],
                        'quantity': quantity,
                        'current_value': 0.50,  # Default value
                        'total_value': quantity * 0.50
                    })
            
            return jsonify({
                'balance': 1000.0,
                'portfolio': portfolio,
                'total_holdings': len(portfolio),
                'rule': 'You can only one prop per team'
            })
            
        except Exception as e:
            return jsonify({
                'balance': 1000.0,
                'portfolio': [],
                'error': str(e)
            })

    @app.route('/api/portfolio/trades')
    def get_trades():
        """Get trade history (simplified)"""
        return jsonify({'trades': []})
    
    def can_user_buy_prop(user_id, prop_id):
        """Check if user can buy a specific prop"""
        if user_id not in app.user_purchases:
            return True, None
        
        # Check if already owns this specific prop
        if app.user_purchases[user_id].get(prop_id, 0) >= 1:
            return False, "You already own this specific prop"
        
        # Check if owns any prop for this team
        current_prop = app.generated_props[prop_id - 1]
        current_team = current_prop['team']
        
        for owned_prop_id, owned_quantity in app.user_purchases[user_id].items():
            if owned_quantity > 0 and owned_prop_id <= len(app.generated_props):
                owned_prop = app.generated_props[owned_prop_id - 1]
                if owned_prop['team'] == current_team:
                    return False, f"You already own a prop for {owned_prop['player_name']} ({current_team})"
        
        return True, None

    @app.route('/api/market/trade', methods=['POST'])
    def execute_trade():
        """Execute a trade (buy/sell contract)"""
        try:
            data = request.get_json()
            user_id = data.get('user_id', 'default_user')  # Default user for demo
            prop_id = data.get('prop_id')
            action = data.get('action')  # 'buy' or 'sell'
            quantity = data.get('quantity', 1)
            
            if not prop_id or not action:
                return jsonify({
                    'success': False,
                    'message': 'Missing prop_id or action'
                }), 400
            
            # Validate prop_id exists
            if prop_id > len(app.generated_props):
                return jsonify({
                    'success': False,
                    'message': 'Invalid prop_id'
                }), 400
            
            # Initialize user tracking if needed
            if user_id not in app.user_purchases:
                app.user_purchases[user_id] = {}
            
            if prop_id not in app.prop_purchases:
                app.prop_purchases[prop_id] = {}
            
            if action == 'buy':
                # Check if user already owns this contract
                current_quantity = app.user_purchases[user_id].get(prop_id, 0)
                if current_quantity >= 1:
                    return jsonify({
                        'success': False,
                        'message': 'You can only buy one of each contract type'
                    }), 400
                
                # Check if user already owns a prop for this team
                current_prop = app.generated_props[prop_id - 1]  # prop_id is 1-indexed
                current_team = current_prop['team']
                
                # Check all user's holdings for this team
                for owned_prop_id, owned_quantity in app.user_purchases[user_id].items():
                    if owned_quantity > 0 and owned_prop_id <= len(app.generated_props):
                        owned_prop = app.generated_props[owned_prop_id - 1]
                        if owned_prop['team'] == current_team:
                            return jsonify({
                                'success': False,
                                'message': f'You already own a prop for {owned_prop["player_name"]} ({current_team}). You can only own one prop per team.'
                            }), 400
                
                # Check if prop has available contracts
                total_sold = sum(app.prop_purchases[prop_id].values())
                if total_sold >= 100:  # Max 100 contracts per prop
                    return jsonify({
                        'success': False,
                        'message': 'No contracts available for this prop'
                    }), 400
                
                # Execute purchase
                app.user_purchases[user_id][prop_id] = current_quantity + quantity
                app.prop_purchases[prop_id][user_id] = app.prop_purchases[prop_id].get(user_id, 0) + quantity
                
                return jsonify({
                    'success': True,
                    'message': f'Successfully purchased {quantity} contract(s) for prop {prop_id}',
                    'user_quantity': app.user_purchases[user_id][prop_id],
                    'total_sold': sum(app.prop_purchases[prop_id].values())
                })
            
            elif action == 'sell':
                # Check if user owns this contract
                current_quantity = app.user_purchases[user_id].get(prop_id, 0)
                if current_quantity < quantity:
                    return jsonify({
                        'success': False,
                        'message': 'You do not own enough contracts to sell'
                    }), 400
                
                # Execute sale
                app.user_purchases[user_id][prop_id] = current_quantity - quantity
                if app.user_purchases[user_id][prop_id] <= 0:
                    del app.user_purchases[user_id][prop_id]
                
                app.prop_purchases[prop_id][user_id] = app.prop_purchases[prop_id].get(user_id, 0) - quantity
                if app.prop_purchases[prop_id][user_id] <= 0:
                    del app.prop_purchases[prop_id][user_id]
                
                return jsonify({
                    'success': True,
                    'message': f'Successfully sold {quantity} contract(s) for prop {prop_id}',
                    'user_quantity': app.user_purchases[user_id].get(prop_id, 0),
                    'total_sold': sum(app.prop_purchases[prop_id].values())
                })
            
            else:
                return jsonify({
                    'success': False,
                    'message': 'Invalid action. Use "buy" or "sell"'
                }), 400
                
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error executing trade: {str(e)}'
            }), 500

    @app.route('/api/market/can-buy/<int:prop_id>')
    def check_can_buy(prop_id):
        """Check if user can buy a specific prop"""
        try:
            user_id = request.args.get('user_id', 'default_user')
            
            if prop_id > len(app.generated_props):
                return jsonify({
                    'can_buy': False,
                    'reason': 'Invalid prop_id'
                }), 400
            
            can_buy, reason = can_user_buy_prop(user_id, prop_id)
            
            return jsonify({
                'can_buy': can_buy,
                'reason': reason,
                'prop_id': prop_id,
                'user_id': user_id
            })
            
        except Exception as e:
            return jsonify({
                'can_buy': False,
                'reason': f'Error checking: {str(e)}'
            }), 500

    return app

def main():
    """Main application entry point"""
    app = create_app()

    # Run the application
    print("🚀 Starting ML Prop Trader...")
    print("📊 Access the application at: http://127.0.0.1:8003")
    print("🔧 Auto-generation is enabled - props will be generated automatically")
    print("=" * 50)
    
    app.run(debug=True, host='127.0.0.1', port=8003)

if __name__ == '__main__':
    main() 