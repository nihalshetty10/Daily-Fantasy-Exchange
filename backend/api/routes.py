from flask import Blueprint, request, jsonify, current_app
from flask_socketio import emit
from datetime import datetime, timedelta
import jwt
from functools import wraps
from ..models import db, User, Player, Prop, Contract, Portfolio, Trade, GameStatus
from ..utils.trading_engine import TradingEngine
from config import Config

app = Blueprint('api', __name__)
trading_engine = TradingEngine()

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token or not token.startswith('Bearer '):
            return jsonify({'error': 'No token provided'}), 401
        
        try:
            token = token.split(' ')[1]
            payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            request.user_id = payload['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(*args, **kwargs)
    
    decorated_function.__name__ = f.__name__
    return decorated_function

def create_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(days=1)
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')

def verify_token(token):
    try:
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload['user_id']
    except:
        return None

@app.route('/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        if not username or not email or not password:
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Check if user already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return jsonify({'error': 'Username already exists'}), 400
        
        # Create new user
        user = User(username=username, email=email, password=password)
        db.session.add(user)
        db.session.commit()
        
        token = create_token(user.id)
        return jsonify({
            'message': 'Registration successful',
            'token': token,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'balance': user.balance
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        token = create_token(user.id)
        return jsonify({
            'token': token,
            'message': 'Login successful',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'balance': user.balance
            }
        })
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/market/props')
def get_props():
    """Get all props with live data from database"""
    try:
        # Get query parameters
        sport = request.args.get('sport', '').upper()
        difficulty = request.args.get('difficulty', '').upper()
        limit = request.args.get('limit', 50, type=int)
        
        # Build query
        query = Prop.query
        
        if sport:
            query = query.filter(Prop.sport == sport)
        if difficulty:
            query = query.filter(Prop.difficulty == difficulty)
        
        # Order by creation date and limit results
        props = query.order_by(Prop.created_at.desc()).limit(limit).all()
        
        # Convert to dictionary with live data
        props_data = []
        for prop in props:
            # Get player info
            player = Player.query.get(prop.player_id)
            player_name = player.name if player else f"Player {prop.player_id}"
            player_team = player.team if player else "Unknown"
            
            prop_dict = prop.to_dict()
            
            # Add player info
            prop_dict['player_name'] = player_name
            prop_dict['player_team'] = player_team
            
            # Add game and player details
            prop_dict['player_position'] = prop.player_position
            prop_dict['opponent_info'] = prop.opponent_info
            prop_dict['game_start_time'] = prop.game_start_time
            
            # Add live trading status
            prop_dict['is_tradeable'] = prop.is_tradeable()
            prop_dict['live_contract_price'] = prop.get_live_contract_price()
            
            # Update game status
            prop.update_game_status()
            
            # Add game status info
            prop_dict['status_badge'] = prop.get_status_badge()
            prop_dict['status_color'] = prop.get_status_color()
            prop_dict['formatted_game_time'] = prop.get_formatted_game_time()
            prop_dict['available_contracts'] = prop.get_available_contracts()
            prop_dict['total_contracts'] = prop.total_contracts
            prop_dict['sold_contracts'] = prop.sold_contracts
            
            props_data.append(prop_dict)
        
        return jsonify({
            'props': props_data,
            'total_count': len(props_data)
        })
        
    except Exception as e:
        return jsonify({'error': f'Error loading props: {str(e)}'}), 500

@app.route('/market/trade', methods=['POST'])
@require_auth
def execute_trade():
    """Execute a trade with live odds - Limited to 1 contract per player"""
    try:
        data = request.get_json()
        prop_id = data.get('prop_id')
        # Force quantity to 1 (1 contract limit per player)
        quantity = 1
        trade_type = data.get('trade_type', 'over')  # over/under
        action = data.get('action', 'buy')  # buy/sell
        
        if not prop_id:
            return jsonify({'error': 'Prop ID required'}), 400
        
        # Get the prop
        prop = Prop.query.get(prop_id)
        if not prop:
            return jsonify({'error': 'Prop not found'}), 404
        
        # Check if prop is still tradeable
        if not prop.is_tradeable():
            return jsonify({'error': 'Prop is no longer tradeable'}), 400
        
        # Check if user already owns this contract (1 contract limit)
        from ..models import Portfolio
        existing_position = Portfolio.query.filter_by(
            user_id=request.user_id, 
            prop_id=prop_id
        ).first()
        
        if action == 'buy' and existing_position:
            return jsonify({'error': 'Maximum 1 contract per player allowed'}), 400
        
        # Get current live price
        current_price = prop.get_live_contract_price()
        
        # Execute trade
        user_id = request.user_id
        if action == 'buy':
            result = trading_engine.buy_contract(user_id, prop_id, quantity)
        else:
            result = trading_engine.sell_contract(user_id, prop_id, quantity)
        
        if result['success']:
            return jsonify({
                'message': f'{action.title()} successful (1 contract limit)',
                'trade': result.get('trade'),
                'new_balance': result['new_balance'],
                'live_price': current_price
            })
        else:
            return jsonify({'error': result['error']}), 400
            
    except Exception as e:
        return jsonify({'error': f'Trade failed: {str(e)}'}), 500

@app.route('/market/cash-out', methods=['POST'])
@require_auth
def cash_out_contract():
    """Cash out contracts when game is final"""
    try:
        data = request.get_json()
        prop_id = data.get('prop_id')
        
        if not prop_id:
            return jsonify({'error': 'Prop ID required'}), 400
        
        # Get the prop
        prop = Prop.query.get(prop_id)
        if not prop:
            return jsonify({'error': 'Prop not found'}), 404
        
        # Check if game is final
        if prop.game_status.value != 'FINAL':
            return jsonify({'error': 'Can only cash out contracts when game is final'}), 400
        
        # Execute cash out
        user_id = request.user_id
        result = trading_engine.cash_out_contract(user_id, prop_id)
        
        if result['success']:
            return jsonify({
                'message': result['message'],
                'payout': result['payout'],
                'new_balance': result['new_balance']
            })
        else:
            return jsonify({'error': result['error']}), 400
            
    except Exception as e:
        return jsonify({'error': f'Cash out failed: {str(e)}'}), 500

@app.route('/portfolio')
@require_auth
def get_portfolio():
    """Get user portfolio with live data"""
    try:
        user_id = request.user_id
        portfolio_data = trading_engine.get_user_portfolio(user_id)
        
        # Add live data to portfolio items
        for item in portfolio_data['portfolio']:
            prop = Prop.query.get(item['prop_id'])
            if prop:
                item['live_price'] = prop.get_live_contract_price()
                item['game_status'] = prop.game_status.value
                item['current_game_time'] = prop.current_game_time
                item['live_score'] = prop.live_score
                item['player_current_value'] = prop.player_current_value
                item['is_tradeable'] = prop.is_tradeable()
        
        return jsonify(portfolio_data)
        
    except Exception as e:
        return jsonify({'error': f'Error loading portfolio: {str(e)}'}), 500

@app.route('/portfolio/trades')
@require_auth
def get_trades():
    """Get user trade history"""
    try:
        user_id = request.user_id
        trades = Trade.query.filter_by(user_id=user_id).order_by(Trade.timestamp.desc()).limit(50).all()
        
        trades_data = []
        for trade in trades:
            trade_dict = {
                'id': trade.id,
                'prop_id': trade.prop_id,
                'quantity': trade.quantity,
                'price': trade.price,
                'trade_type': trade.trade_type.value,
                'action': trade.trade_type.value,
                'created_at': trade.timestamp.isoformat() if trade.timestamp else None
            }
            
            # Add prop info
            prop = Prop.query.get(trade.prop_id)
            if prop:
                player = Player.query.get(prop.player_id)
                trade_dict['player_name'] = player.name if player else f"Player {prop.player_id}"
                trade_dict['prop_type'] = prop.prop_type
                trade_dict['line_value'] = prop.line_value
                trade_dict['sport'] = prop.sport
            
            trades_data.append(trade_dict)
        
        return jsonify({'trades': trades_data})
        
    except Exception as e:
        return jsonify({'error': f'Error loading trades: {str(e)}'}), 500

@app.route('/market/live-updates')
def get_live_updates():
    """Get live updates for all active props"""
    try:
        # Get props that are currently live or recently finished
        now = datetime.utcnow()
        live_props = Prop.query.filter(
            Prop.game_status.in_([GameStatus.LIVE, GameStatus.FINISHED]),
            Prop.game_time >= now - timedelta(hours=4)
        ).all()
        
        updates = []
        for prop in live_props:
            updates.append({
                'prop_id': prop.id,
                'game_status': prop.game_status.value,
                'current_game_time': prop.current_game_time,
                'live_score': prop.live_score,
                'player_current_value': prop.player_current_value,
                'live_implied_probability': prop.live_implied_probability,
                'live_contract_price': prop.get_live_contract_price(),
                'trading_active': prop.trading_active,
                'last_update': prop.last_update.isoformat() if prop.last_update else None
            })
        
        return jsonify({'updates': updates})
        
    except Exception as e:
        return jsonify({'error': f'Error getting live updates: {str(e)}'}), 500 

@app.route('/market/order', methods=['POST'])
def place_order():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        prop_id = data.get('prop_id')
        side = data.get('side')  # 'bid' or 'ask'
        price = float(data.get('price'))
        # Force quantity to 1 (1 contract limit per player)
        quantity = 1
        
        if not all([user_id, prop_id, side, price]):
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Check if user already has an order for this prop (1 contract limit)
        from ..models import Order
        existing_order = Order.query.filter_by(
            user_id=user_id, 
            prop_id=prop_id
        ).first()
        
        if existing_order:
            return jsonify({'error': 'Maximum 1 contract per player allowed'}), 400
            
        engine = TradingEngine()
        result = engine.place_order(user_id=user_id, prop_id=prop_id, side=side, price=price, quantity=quantity)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'Order failed: {str(e)}'}), 500

@app.route('/market/orderbook')
def get_orderbook():
    prop_id = request.args.get('prop_id', type=int)
    if not prop_id:
        return jsonify({'error': 'prop_id required'}), 400
    engine = TradingEngine()
    ob = engine.get_order_book(prop_id)
    mid = engine.get_mid_price(prop_id)
    return jsonify({'order_book': ob, 'mid_price': mid}) 