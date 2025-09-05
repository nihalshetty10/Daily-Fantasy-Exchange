from flask import Blueprint, request, jsonify, session
from backend.services.profit_tracker import ProfitTracker
from backend.services.auth_service import AuthService

transaction_bp = Blueprint('transaction', __name__, url_prefix='/api/transaction')

@transaction_bp.route('/record', methods=['POST'])
def record_transaction():
    """Record a transaction (bet, win, loss, cashout)"""
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            return jsonify({'error': 'User not authenticated'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        transaction_type = data.get('transaction_type')
        amount = data.get('amount')
        prop_id = data.get('prop_id')
        player_name = data.get('player_name')
        sport = data.get('sport')
        description = data.get('description')
        
        if not transaction_type or amount is None:
            return jsonify({'error': 'transaction_type and amount are required'}), 400
        
        user_id = session['user_id']
        
        # Record the transaction
        success = ProfitTracker.record_transaction(
            user_id=user_id,
            transaction_type=transaction_type,
            amount=amount,
            prop_id=prop_id,
            player_name=player_name,
            sport=sport,
            description=description
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Transaction recorded successfully'
            }), 200
        else:
            return jsonify({'error': 'Failed to record transaction'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@transaction_bp.route('/bet', methods=['POST'])
def record_bet():
    """Record a prop bet transaction"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'User not authenticated'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        prop_id = data.get('prop_id')
        player_name = data.get('player_name')
        sport = data.get('sport')
        bet_amount = data.get('bet_amount')
        
        if not all([prop_id, player_name, sport, bet_amount]):
            return jsonify({'error': 'prop_id, player_name, sport, and bet_amount are required'}), 400
        
        user_id = session['user_id']
        
        # Record the bet (negative amount for money going out)
        success = ProfitTracker.record_prop_bet(
            user_id=user_id,
            prop_id=prop_id,
            player_name=player_name,
            sport=sport,
            bet_amount=bet_amount
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Bet recorded successfully'
            }), 200
        else:
            return jsonify({'error': 'Failed to record bet'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@transaction_bp.route('/win', methods=['POST'])
def record_win():
    """Record a prop win transaction"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'User not authenticated'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        prop_id = data.get('prop_id')
        player_name = data.get('player_name')
        sport = data.get('sport')
        win_amount = data.get('win_amount')
        
        if not all([prop_id, player_name, sport, win_amount]):
            return jsonify({'error': 'prop_id, player_name, sport, and win_amount are required'}), 400
        
        user_id = session['user_id']
        
        # Record the win (positive amount for money coming in)
        success = ProfitTracker.record_prop_win(
            user_id=user_id,
            prop_id=prop_id,
            player_name=player_name,
            sport=sport,
            win_amount=win_amount
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Win recorded successfully'
            }), 200
        else:
            return jsonify({'error': 'Failed to record win'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@transaction_bp.route('/loss', methods=['POST'])
def record_loss():
    """Record a prop loss transaction (platform gains)"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'User not authenticated'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        prop_id = data.get('prop_id')
        player_name = data.get('player_name')
        sport = data.get('sport')
        loss_amount = data.get('loss_amount')
        
        if not all([prop_id, player_name, sport, loss_amount]):
            return jsonify({'error': 'prop_id, player_name, sport, and loss_amount are required'}), 400
        
        user_id = session['user_id']
        
        # Record the loss (positive amount for platform)
        success = ProfitTracker.record_prop_loss(
            user_id=user_id,
            prop_id=prop_id,
            player_name=player_name,
            sport=sport,
            loss_amount=loss_amount
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Loss recorded successfully'
            }), 200
        else:
            return jsonify({'error': 'Failed to record loss'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@transaction_bp.route('/cashout', methods=['POST'])
def record_cashout():
    """Record a cashout transaction"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'User not authenticated'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        amount = data.get('amount')
        description = data.get('description', 'Cashout')
        
        if not amount:
            return jsonify({'error': 'amount is required'}), 400
        
        user_id = session['user_id']
        
        # Record the cashout (negative amount for money going out)
        success = ProfitTracker.record_cashout(
            user_id=user_id,
            amount=amount,
            description=description
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Cashout recorded successfully'
            }), 200
        else:
            return jsonify({'error': 'Failed to record cashout'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@transaction_bp.route('/user/<int:user_id>', methods=['GET'])
def get_user_transactions(user_id):
    """Get transactions for a specific user"""
    try:
        # Check if user is requesting their own transactions or is admin
        if 'user_id' not in session:
            return jsonify({'error': 'User not authenticated'}), 401
        
        current_user_id = session['user_id']
        if current_user_id != user_id:
            # TODO: Add admin check here if needed
            return jsonify({'error': 'Access denied'}), 403
        
        limit = request.args.get('limit', 50, type=int)
        if limit > 100:
            limit = 100
        
        transactions = ProfitTracker.get_user_transactions(user_id, limit)
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'transactions': transactions,
            'total_transactions': len(transactions)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@transaction_bp.route('/limits/<int:user_id>', methods=['GET'])
def get_user_limits(user_id):
    """Get user's current limits (portfolio size, daily transactions)"""
    try:
        # Check if user is requesting their own limits or is admin
        if 'user_id' not in session:
            return jsonify({'error': 'User not authenticated'}), 401
        
        current_user_id = session['user_id']
        if current_user_id != user_id:
            # TODO: Add admin check here if needed
            return jsonify({'error': 'Access denied'}), 403
        
        from config import config
        from backend.services.profit_tracker import ProfitTracker
        
        daily_count = ProfitTracker.get_daily_transaction_count(user_id)
        daily_limit = config['default'].DAILY_TRANSACTION_LIMIT
        portfolio_limit = config['default'].MAX_PORTFOLIO_SIZE
        
        return jsonify({
            'success': True,
            'limits': {
                'daily_transactions': {
                    'current': daily_count,
                    'limit': daily_limit,
                    'remaining': max(0, daily_limit - daily_count)
                },
                'portfolio': {
                    'limit': portfolio_limit
                }
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
