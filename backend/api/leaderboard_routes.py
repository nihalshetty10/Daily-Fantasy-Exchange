from flask import Blueprint, jsonify, request
from backend.services.profit_tracker import ProfitTracker

leaderboard_bp = Blueprint('leaderboard', __name__, url_prefix='/api/leaderboard')

@leaderboard_bp.route('/top', methods=['GET'])
def get_leaderboard():
    """Get top 10 users by net profit"""
    try:
        limit = request.args.get('limit', 10, type=int)
        if limit > 50:  # Cap at 50 for performance
            limit = 50
            
        leaderboard = ProfitTracker.get_leaderboard(limit)
        
        return jsonify({
            'success': True,
            'leaderboard': leaderboard,
            'total_users': len(leaderboard)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@leaderboard_bp.route('/profit', methods=['GET'])
def get_net_profit():
    """Get platform net profit"""
    try:
        net_profit = ProfitTracker.get_net_profit()
        
        return jsonify({
            'success': True,
            'net_profit': net_profit
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@leaderboard_bp.route('/user/<int:user_id>', methods=['GET'])
def get_user_profit(user_id):
    """Get profit for a specific user"""
    try:
        user_profit = ProfitTracker.get_user_profit(user_id)
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'net_profit': user_profit
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@leaderboard_bp.route('/transactions/<int:user_id>', methods=['GET'])
def get_user_transactions(user_id):
    """Get recent transactions for a user"""
    try:
        limit = request.args.get('limit', 50, type=int)
        if limit > 100:  # Cap at 100 for performance
            limit = 100
            
        transactions = ProfitTracker.get_user_transactions(user_id, limit)
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'transactions': transactions,
            'total_transactions': len(transactions)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
