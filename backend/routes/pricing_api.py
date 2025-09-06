"""
Pricing API endpoints for dynamic prop pricing
"""

from flask import Blueprint, request, jsonify
from backend.services.pricing_engine import get_pricing_engine
import logging

logger = logging.getLogger(__name__)

pricing_bp = Blueprint('pricing', __name__)

@pricing_bp.route('/api/contracts', methods=['GET'])
def get_all_contracts():
    """Get all available prop contracts with current prices"""
    try:
        engine = get_pricing_engine()
        contracts = engine.get_all_contracts()
        
        return jsonify({
            'success': True,
            'contracts': contracts,
            'total': len(contracts)
        })
    except Exception as e:
        logger.error(f"Error getting contracts: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@pricing_bp.route('/api/contracts/<prop_id>', methods=['GET'])
def get_contract(prop_id):
    """Get specific contract information"""
    try:
        engine = get_pricing_engine()
        contract = engine.get_contract_info(prop_id)
        
        if not contract:
            return jsonify({
                'success': False,
                'error': 'Contract not found'
            }), 404
        
        return jsonify({
            'success': True,
            'contract': contract
        })
    except Exception as e:
        logger.error(f"Error getting contract {prop_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@pricing_bp.route('/api/contracts/<prop_id>/price', methods=['GET'])
def get_contract_price(prop_id):
    """Get current price for a contract"""
    try:
        engine = get_pricing_engine()
        price = engine.get_contract_price(prop_id)
        
        if price is None:
            return jsonify({
                'success': False,
                'error': 'Contract not found'
            }), 404
        
        return jsonify({
            'success': True,
            'price': price
        })
    except Exception as e:
        logger.error(f"Error getting price for {prop_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@pricing_bp.route('/api/orders', methods=['POST'])
def place_order():
    """Place a buy or sell order for a contract"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['user_id', 'prop_id', 'side', 'price', 'quantity']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Validate side
        if data['side'] not in ['buy', 'sell']:
            return jsonify({
                'success': False,
                'error': 'Side must be "buy" or "sell"'
            }), 400
        
        # Validate quantity
        if not isinstance(data['quantity'], int) or data['quantity'] <= 0:
            return jsonify({
                'success': False,
                'error': 'Quantity must be a positive integer'
            }), 400
        
        # Validate price
        if not isinstance(data['price'], (int, float)) or data['price'] <= 0:
            return jsonify({
                'success': False,
                'error': 'Price must be a positive number'
            }), 400
        
        engine = get_pricing_engine()
        order_id = engine.place_order(
            user_id=data['user_id'],
            prop_id=data['prop_id'],
            side=data['side'],
            price=float(data['price']),
            quantity=int(data['quantity'])
        )
        
        return jsonify({
            'success': True,
            'order_id': order_id,
            'message': 'Order placed successfully'
        })
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error placing order: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@pricing_bp.route('/api/orders/<order_id>/cancel', methods=['POST'])
def cancel_order(order_id):
    """Cancel an active order"""
    try:
        engine = get_pricing_engine()
        success = engine.cancel_order(order_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Order cancelled successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Order not found or already cancelled'
            }), 404
            
    except Exception as e:
        logger.error(f"Error cancelling order {order_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@pricing_bp.route('/api/orders/user/<user_id>', methods=['GET'])
def get_user_orders(user_id):
    """Get all orders for a specific user"""
    try:
        engine = get_pricing_engine()
        orders = engine.get_user_orders(user_id)
        
        return jsonify({
            'success': True,
            'orders': orders,
            'total': len(orders)
        })
    except Exception as e:
        logger.error(f"Error getting orders for user {user_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@pricing_bp.route('/api/contracts/<prop_id>/orderbook', methods=['GET'])
def get_order_book(prop_id):
    """Get order book for a specific contract (for advanced users)"""
    try:
        engine = get_pricing_engine()
        order_book = engine.get_order_book(prop_id)
        
        return jsonify({
            'success': True,
            'order_book': order_book
        })
    except Exception as e:
        logger.error(f"Error getting order book for {prop_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@pricing_bp.route('/api/contracts/search', methods=['GET'])
def search_contracts():
    """Search contracts by player name, prop type, or difficulty"""
    try:
        query = request.args.get('q', '').lower()
        sport = request.args.get('sport', '').lower()
        difficulty = request.args.get('difficulty', '').lower()
        
        engine = get_pricing_engine()
        all_contracts = engine.get_all_contracts()
        
        filtered_contracts = []
        for contract in all_contracts:
            # Filter by search query
            if query and query not in contract['player_name'].lower() and query not in contract['prop_type'].lower():
                continue
            
            # Filter by sport
            if sport and sport not in contract['prop_id'].lower():
                continue
            
            # Filter by difficulty
            if difficulty and difficulty != contract['difficulty'].lower():
                continue
            
            filtered_contracts.append(contract)
        
        return jsonify({
            'success': True,
            'contracts': filtered_contracts,
            'total': len(filtered_contracts)
        })
    except Exception as e:
        logger.error(f"Error searching contracts: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@pricing_bp.route('/api/games/<game_id>/expire', methods=['POST'])
def expire_game_contracts(game_id):
    """Expire all contracts for a game when it starts"""
    try:
        engine = get_pricing_engine()
        expired_contracts = engine.expire_contracts_at_game_start(game_id)
        
        return jsonify({
            'success': True,
            'expired_contracts': expired_contracts,
            'message': f'Expired {len(expired_contracts)} contracts for game {game_id}'
        })
    except Exception as e:
        logger.error(f"Error expiring contracts for game {game_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@pricing_bp.route('/refund/check', methods=['POST'])
def check_exact_hit_refund():
    """Check if a prop hit the exact line value for refund"""
    try:
        data = request.get_json()
        prop_id = data.get('prop_id')
        actual_value = data.get('actual_value')
        user_id = data.get('user_id')
        
        if not prop_id or actual_value is None:
            return jsonify({'error': 'prop_id and actual_value are required'}), 400
        
        refund_info = pricing_engine.check_exact_hit_refund(prop_id, actual_value, user_id)
        return jsonify(refund_info), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

