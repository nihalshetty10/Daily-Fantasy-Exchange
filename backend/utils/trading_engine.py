import logging
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from ..models import User, Contract, Prop, Portfolio, Trade, TradeType, Order, OrderSide, OrderStatus
from config import Config
from sqlalchemy import asc, desc

db = SQLAlchemy()

class TradingEngine:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.standard_payout = Config.STANDARD_PAYOUT
    
    def buy_contract(self, user_id, prop_id, quantity=1):
        """Buy contracts for a prop - Limited to 1 per player"""
        try:
            # Force quantity to 1 (1 contract limit per player)
            quantity = 1
            
            # Get user and prop
            user = User.query.get(user_id)
            prop = Prop.query.get(prop_id)
            
            if not user or not prop:
                return {'success': False, 'error': 'User or prop not found'}
            
            # Check if prop can be traded
            if not prop.can_trade():
                return {'success': False, 'error': 'Prop is not tradeable'}
            
            # Get trading availability based on game status
            trading_availability = prop.get_trading_availability()
            
            if not trading_availability['can_buy']:
                return {'success': False, 'error': trading_availability['message']}
            
            # Check if contracts can be bought
            if not prop.can_buy_contracts(quantity):
                if prop.game_status.value == 'LIVE':
                    return {'success': False, 'error': 'No contracts available for purchase during live games. Only previously sold contracts can be bought.'}
                else:
                    return {'success': False, 'error': 'Not enough contracts available'}
            
            # Check if user already owns this contract (1 contract limit)
            existing_position = Portfolio.query.filter_by(
                user_id=user_id, 
                prop_id=prop_id
            ).first()
            
            if existing_position:
                return {'success': False, 'error': 'Maximum 1 contract per player allowed'}
            
            # Calculate total cost
            contract_price = prop.get_contract_price()
            total_cost = contract_price * 100  # $100 payout (quantity is always 1)
            
            # Check if user has enough balance
            if user.balance < total_cost:
                return {'success': False, 'error': 'Insufficient balance'}
            
            # Buy contracts
            if prop.buy_contracts(quantity):
                # Create portfolio entry (only 1 contract)
                portfolio_entry = Portfolio(
                    user_id=user_id,
                    prop_id=prop_id,
                    quantity=1,
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
                    quantity=1,
                    price=contract_price,
                    total_value=total_cost
                )
                db.session.add(trade)
                
                # Update prop probability based on trading activity
                self._update_prop_probability(prop_id)
                
                db.session.commit()
                
                return {
                    'success': True,
                    'message': 'Bought 1 contract (1 contract limit per player)',
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
            
            # Get trading availability based on game status
            trading_availability = prop.get_trading_availability()
            
            if not trading_availability['can_sell']:
                return {'success': False, 'error': trading_availability['message']}
            
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
    
    def cash_out_contract(self, user_id, prop_id):
        """Cash out contracts when game is final"""
        try:
            # Get user and prop
            user = User.query.get(user_id)
            prop = Prop.query.get(prop_id)
            
            if not user or not prop:
                return {'success': False, 'error': 'User or prop not found'}
            
            # Check if game is final
            if prop.game_status.value != 'FINAL':
                return {'success': False, 'error': 'Can only cash out contracts when game is final'}
            
            # Check if user has contracts to cash out
            portfolio_entry = Portfolio.query.filter_by(
                user_id=user_id, 
                prop_id=prop_id
            ).first()
            
            if not portfolio_entry or portfolio_entry.quantity <= 0:
                return {'success': False, 'error': 'No contracts to cash out'}
            
            # Calculate payout based on whether the prop hit
            # This is a simplified version - you can enhance this based on actual game results
            payout = 100  # $100 if prop hits, $0 if it doesn't
            
            # For now, we'll assume the prop hits (you can implement actual result checking)
            # In a real system, you'd check the actual game results here
            
            # Remove from portfolio
            db.session.delete(portfolio_entry)
            
            # Add payout to user balance
            user.balance += payout
            
            # Create trade record for cash out
            trade = Trade(
                user_id=user_id,
                prop_id=prop_id,
                trade_type=TradeType.CASH_OUT,
                quantity=portfolio_entry.quantity,
                price=payout,
                total_value=payout
            )
            db.session.add(trade)
            
            db.session.commit()
            
            return {
                'success': True,
                'message': f'Cashed out {portfolio_entry.quantity} contract(s) for ${payout}',
                'new_balance': user.balance,
                'payout': payout
            }
                
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Cash out failed: {str(e)}'}
    
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

    def get_initial_price(self, prop: Prop) -> float:
        # default initial price from implied prob if no orders yet
        base_prob = prop.live_implied_probability or prop.implied_probability or 0.5
        return round(base_prob * 100, 2)

    def get_order_book(self, prop_id: int, depth: int = 10):
        bids = Order.query.filter_by(prop_id=prop_id, side=OrderSide.BID, status=OrderStatus.OPEN)\
            .order_by(desc(Order.price), asc(Order.created_at)).limit(depth).all()
        asks = Order.query.filter_by(prop_id=prop_id, side=OrderSide.ASK, status=OrderStatus.OPEN)\
            .order_by(asc(Order.price), asc(Order.created_at)).limit(depth).all()
        return {
            'bids': [o.to_dict() for o in bids],
            'asks': [o.to_dict() for o in asks]
        }

    def _best_bid(self, prop_id: int):
        return Order.query.filter_by(prop_id=prop_id, side=OrderSide.BID, status=OrderStatus.OPEN)\
            .order_by(desc(Order.price), asc(Order.created_at)).first()

    def _best_ask(self, prop_id: int):
        return Order.query.filter_by(prop_id=prop_id, side=OrderSide.ASK, status=OrderStatus.OPEN)\
            .order_by(asc(Order.price), asc(Order.created_at)).first()

    def get_mid_price(self, prop_id: int) -> float:
        prop = Prop.query.get(prop_id)
        bb = self._best_bid(prop_id)
        ba = self._best_ask(prop_id)
        if bb and ba:
            return round((bb.price + ba.price) / 2.0, 2)
        return self.get_initial_price(prop) if prop else 50.0

    def place_order(self, user_id: str, prop_id: int, side: str, price: float, quantity: int = 1):
        # Force quantity to 1 (1 contract limit per player)
        quantity = 1
        
        # Check if user already has an order for this prop (1 contract limit)
        existing_order = Order.query.filter_by(
            user_id=user_id, 
            prop_id=prop_id
        ).first()
        
        if existing_order:
            return {'success': False, 'error': 'Maximum 1 contract per player allowed'}
        
        side_enum = OrderSide.BID if side.lower() == 'bid' else OrderSide.ASK
        order = Order(prop_id=prop_id, user_id=user_id, side=side_enum, price=price, quantity=quantity, remaining=quantity)
        db.session.add(order)
        db.session.flush()
        # After adding, try match and update price
        self._match_orders(prop_id)
        self._update_mid_price(prop_id)
        db.session.commit()
        return {'success': True, 'order': order.to_dict(), 'mid_price': self.get_mid_price(prop_id)}

    def _update_mid_price(self, prop_id: int):
        prop = Prop.query.get(prop_id)
        if not prop:
            return
        mid = self.get_mid_price(prop_id)
        # update implied probabilities to align with price
        prob = max(0.01, min(0.99, mid / 100.0))
        if prop.game_status.value == 'LIVE':
            prop.live_implied_probability = prob
        else:
            prop.implied_probability = prob
        # Optionally update all contracts' displayed price to the same mid
        contracts = Contract.query.filter_by(prop_id=prop_id).all()
        for c in contracts:
            c.current_price = mid
        prop.updated_at = datetime.utcnow()

    def _record_trade(self, buyer_id: str, seller_id: str, prop_id: int, price: float, quantity: int):
        # Create/update a synthetic contract position value for both sides (simplified for MVP)
        # Debit buyer
        # Here we only write Trade rows as record; portfolio updates can be extended later
        bt = Trade(user_id=buyer_id, contract_id=str(prop_id), trade_type=TradeType.BUY, quantity=quantity, price=price)
        st = Trade(user_id=seller_id, contract_id=str(prop_id), trade_type=TradeType.SELL, quantity=quantity, price=price)
        db.session.add(bt)
        db.session.add(st)

    def _match_orders(self, prop_id: int):
        # Simple continuous matching: while crossed market, execute at ask price
        while True:
            bb = self._best_bid(prop_id)
            ba = self._best_ask(prop_id)
            if not bb or not ba:
                break
            if bb.price < ba.price:
                break
            # crossed
            trade_qty = min(bb.remaining, ba.remaining)
            trade_price = ba.price
            # reduce remaining
            bb.remaining -= trade_qty
            ba.remaining -= trade_qty
            # statuses
            if bb.remaining == 0:
                bb.status = OrderStatus.FILLED
            else:
                bb.status = OrderStatus.PARTIAL
            if ba.remaining == 0:
                ba.status = OrderStatus.FILLED
            else:
                ba.status = OrderStatus.PARTIAL
            # record
            self._record_trade(buyer_id=bb.user_id, seller_id=ba.user_id, prop_id=prop_id, price=trade_price, quantity=trade_qty)

        # Clean up fully filled orders optional
        return True 