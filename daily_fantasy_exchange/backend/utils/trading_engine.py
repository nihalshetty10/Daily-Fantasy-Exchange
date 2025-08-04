import logging
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from ..models import User, Contract, Prop, Portfolio, Trade, TradeType
from config import Config

db = SQLAlchemy()

class TradingEngine:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.standard_payout = Config.STANDARD_PAYOUT
    
    def buy_contract(self, user_id, prop_id, quantity=1):
        """Buy contracts for a prop"""
        try:
            # Get user and prop
            user = User.query.get(user_id)
            prop = Prop.query.get(prop_id)
            
            if not user or not prop:
                return {'success': False, 'error': 'User or prop not found'}
            
            # Check if prop can be traded
            if not prop.can_trade():
                return {'success': False, 'error': 'Prop is not tradeable'}
            
            # Check if contracts can be bought
            if not prop.can_buy_contracts(quantity):
                return {'success': False, 'error': 'Not enough contracts available'}
            
            # Calculate total cost
            contract_price = prop.get_contract_price()
            total_cost = contract_price * quantity * 100  # $100 payout
            
            # Check if user has enough balance
            if user.balance < total_cost:
                return {'success': False, 'error': 'Insufficient balance'}
            
            # Buy contracts
            if prop.buy_contracts(quantity):
                # Create portfolio entry
                portfolio_entry = Portfolio.query.filter_by(
                    user_id=user_id, 
                    prop_id=prop_id
                ).first()
                
                if portfolio_entry:
                    # Update existing entry
                    portfolio_entry.quantity += quantity
                    portfolio_entry.average_price = (
                        (portfolio_entry.average_price * portfolio_entry.quantity + total_cost) /
                        (portfolio_entry.quantity + quantity)
                    )
                else:
                    # Create new entry
                    portfolio_entry = Portfolio(
                        user_id=user_id,
                        prop_id=prop_id,
                        quantity=quantity,
                        average_price=total_cost
                    )
                    db.session.add(portfolio_entry)
                
                # Update user balance
                user.balance -= total_cost
                
                # Create trade record
                trade = Trade(
                    user_id=user_id,
                    prop_id=prop_id,
                    trade_type=TradeType.BUY,
                    quantity=quantity,
                    price=contract_price,
                    total_value=total_cost
                )
                db.session.add(trade)
                
                # Update prop probability based on trading activity
                self._update_prop_probability(prop_id)
                
                db.session.commit()
                
                return {
                    'success': True,
                    'message': f'Bought {quantity} contract(s)',
                    'new_balance': user.balance,
                    'contract_price': contract_price
                }
            else:
                return {'success': False, 'error': 'Failed to buy contracts'}
                
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Trade failed: {str(e)}'}
    
    def sell_contract(self, user_id, prop_id, quantity=1):
        """Sell contracts for a prop"""
        try:
            # Get user and prop
            user = User.query.get(user_id)
            prop = Prop.query.get(prop_id)
            
            if not user or not prop:
                return {'success': False, 'error': 'User or prop not found'}
            
            # Check if prop can be traded
            if not prop.can_trade():
                return {'success': False, 'error': 'Prop is not tradeable'}
            
            # Check if user can sell contracts
            if not prop.can_sell_contracts(user_id, quantity):
                return {'success': False, 'error': 'Not enough contracts to sell'}
            
            # Calculate total value
            contract_price = prop.get_contract_price()
            total_value = contract_price * quantity * 100  # $100 payout
            
            # Sell contracts
            if prop.sell_contracts(quantity):
                # Update portfolio entry
                portfolio_entry = Portfolio.query.filter_by(
                    user_id=user_id, 
                    prop_id=prop_id
                ).first()
                
                if portfolio_entry:
                    portfolio_entry.quantity -= quantity
                    if portfolio_entry.quantity <= 0:
                        db.session.delete(portfolio_entry)
                
                # Update user balance
                user.balance += total_value
                
                # Create trade record
                trade = Trade(
                    user_id=user_id,
                    prop_id=prop_id,
                    trade_type=TradeType.SELL,
                    quantity=quantity,
                    price=contract_price,
                    total_value=total_value
                )
                db.session.add(trade)
                
                # Update prop probability based on trading activity
                self._update_prop_probability(prop_id)
                
                db.session.commit()
                
                return {
                    'success': True,
                    'message': f'Sold {quantity} contract(s)',
                    'new_balance': user.balance,
                    'contract_price': contract_price
                }
            else:
                return {'success': False, 'error': 'Failed to sell contracts'}
                
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Trade failed: {str(e)}'}
    
    def _update_prop_probability(self, prop_id):
        """Update prop probability based on recent trading activity"""
        try:
            prop = Prop.query.get(prop_id)
            if not prop:
                return
            
            # Get recent trades for this prop
            recent_trades = Trade.query.filter_by(prop_id=prop_id).order_by(Trade.timestamp.desc()).limit(10).all()
            
            if not recent_trades:
                return
            
            # Calculate average price from recent trades
            total_price = sum(trade.price for trade in recent_trades)
            avg_price = total_price / len(recent_trades)
            
            # Update implied probability (clamp between 0.01 and 0.99)
            new_probability = max(0.01, min(0.99, avg_price))
            
            if prop.game_status.value == 'LIVE':
                prop.live_implied_probability = new_probability
            else:
                prop.implied_probability = new_probability
            
            prop.updated_at = datetime.utcnow()
            
        except Exception as e:
            self.logger.error(f"Error updating prop probability: {e}")
    
    def get_market_data(self, prop_id):
        """Get market data for a specific prop"""
        try:
            prop = Prop.query.get(prop_id)
            if not prop:
                return None
            
            # Get recent trades
            recent_trades = Trade.query.filter_by(contract_id=prop_id).order_by(
                Trade.timestamp.desc()
            ).limit(50).all()
            
            # Calculate market metrics
            total_volume = sum(trade.total_amount for trade in recent_trades)
            buy_volume = sum(trade.total_amount for trade in recent_trades if trade.trade_type == TradeType.BUY)
            sell_volume = sum(trade.total_amount for trade in recent_trades if trade.trade_type == TradeType.SELL)
            
            # Price change
            if len(recent_trades) >= 2:
                price_change = recent_trades[0].price - recent_trades[-1].price
                price_change_pct = (price_change / recent_trades[-1].price) * 100
            else:
                price_change = 0
                price_change_pct = 0
            
            return {
                'prop_id': prop_id,
                'current_price': prop.get_contract_price(),
                'implied_probability': prop.implied_probability,
                'available_contracts': prop.get_available_contracts(),
                'total_volume': total_volume,
                'buy_volume': buy_volume,
                'sell_volume': sell_volume,
                'price_change': price_change,
                'price_change_pct': price_change_pct,
                'recent_trades': [trade.to_dict() for trade in recent_trades[:10]]
            }
            
        except Exception as e:
            self.logger.error(f"Error getting market data: {e}")
            return None
    
    def get_user_portfolio(self, user_id):
        """Get user's portfolio"""
        try:
            user = User.query.get(user_id)
            if not user:
                return None
            
            portfolios = Portfolio.query.filter_by(user_id=user_id, is_active=True).all()
            
            portfolio_data = []
            total_value = user.balance
            total_pnl = 0
            
            for portfolio in portfolios:
                contract = Contract.query.get(portfolio.contract_id)
                if contract and contract.is_active:
                    prop = Prop.query.get(contract.prop_id)
                    if prop:
                        position_value = portfolio.get_current_value()
                        position_pnl = portfolio.get_pnl()
                        
                        total_value += position_value
                        total_pnl += position_pnl
                        
                        portfolio_data.append({
                            'portfolio_id': portfolio.id,
                            'contract_id': portfolio.contract_id,
                            'prop_id': contract.prop_id,
                            'quantity': portfolio.quantity,
                            'average_purchase_price': portfolio.average_purchase_price,
                            'current_price': contract.current_price,
                            'position_value': position_value,
                            'position_pnl': position_pnl,
                            'position_pnl_pct': portfolio.get_pnl_percentage(),
                            'prop_type': prop.prop_type,
                            'line_value': prop.line_value,
                            'implied_probability': prop.implied_probability
                        })
            
            return {
                'user_id': user_id,
                'balance': user.balance,
                'total_portfolio_value': total_value,
                'total_pnl': total_pnl,
                'portfolio': portfolio_data
            }
            
        except Exception as e:
            self.logger.error(f"Error getting user portfolio: {e}")
            return None 