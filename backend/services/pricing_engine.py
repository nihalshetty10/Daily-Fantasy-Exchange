"""
Dynamic Pricing Engine for Player Props
Implements Volume-Weighted Average Price (VWAP) for DFS-compliant pricing
"""

import json
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import threading
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Order:
    """Represents a buy or sell order for a prop contract"""
    order_id: str
    prop_id: str
    user_id: str
    side: str  # 'buy' or 'sell'
    price: float
    quantity: int
    timestamp: float
    status: str = 'active'  # 'active', 'filled', 'cancelled'

@dataclass
class PropContract:
    """Represents a player prop contract with pricing data"""
    prop_id: str
    player_name: str
    prop_type: str
    line: float
    difficulty: str
    game_id: str
    initial_probability: float
    fixed_payout: float = 100.0  # Default $100 payout
    current_price: float = 0.0
    total_volume: int = 0
    last_updated: float = 0.0

class PricingEngine:
    """
    Dynamic pricing engine using Volume-Weighted Average Price (VWAP)
    """
    
    def __init__(self):
        self.contracts: Dict[str, PropContract] = {}
        self.orders: Dict[str, Order] = {}
        self.order_book: Dict[str, Dict[str, List[Order]]] = defaultdict(lambda: {'bids': [], 'asks': []})
        self.lock = threading.Lock()
        
        # Load existing props and initialize contracts
        self._load_props()
    
    def _load_props(self):
        """Load props from JSON files and create initial contracts"""
        try:
            # Load NFL props
            with open('nfl_props.json', 'r') as f:
                nfl_data = json.load(f)
                self._create_contracts_from_props(nfl_data.get('props', []), 'NFL')
            
            # Load MLB props
            with open('mlb_props.json', 'r') as f:
                mlb_data = json.load(f)
                props_dict = mlb_data.get('props', {})
                for player_key, player_data in props_dict.items():
                    props = player_data.get('props', [])
                    self._create_contracts_from_props(props, 'MLB')
            
            logger.info(f"Loaded {len(self.contracts)} contracts")
            
        except Exception as e:
            logger.error(f"Error loading props: {e}")
    
    def _create_contracts_from_props(self, props: List[Dict], sport: str):
        """Create PropContract objects from prop data"""
        for prop in props:
            # Generate unique prop ID
            prop_id = f"{sport}_{prop.get('player_name', 'Unknown')}_{prop.get('prop_type', 'unknown')}_{prop.get('line', 0)}_{prop.get('difficulty', 'medium')}"
            
            # Calculate initial price from implied probability
            implied_prob = prop.get('implied_probability', 0.5)
            initial_price = self._calculate_initial_price(implied_prob)
            
            contract = PropContract(
                prop_id=prop_id,
                player_name=prop.get('player_name', 'Unknown'),
                prop_type=prop.get('prop_type', 'unknown'),
                line=prop.get('line', 0),
                difficulty=prop.get('difficulty', 'medium'),
                game_id=prop.get('game_id', ''),
                initial_probability=implied_prob,
                current_price=initial_price,
                last_updated=time.time()
            )
            
            self.contracts[prop_id] = contract
    
    def _calculate_initial_price(self, implied_probability: float) -> float:
        """
        Calculate initial entry price based on implied probability
        Price = Fixed Payout × Implied Probability
        """
        fixed_payout = 100.0  # $100 fixed payout
        price = fixed_payout * implied_probability
        
        # Round to nearest cent
        return round(price, 2)
    
    def place_order(self, user_id: str, prop_id: str, side: str, price: float, quantity: int) -> str:
        """
        Place a buy or sell order for a prop contract
        
        Args:
            user_id: ID of the user placing the order
            prop_id: ID of the prop contract
            side: 'buy' or 'sell'
            price: Price per contract
            quantity: Number of contracts
            
        Returns:
            Order ID
        """
        if prop_id not in self.contracts:
            raise ValueError(f"Prop contract {prop_id} not found")
        
        if side not in ['buy', 'sell']:
            raise ValueError("Side must be 'buy' or 'sell'")
        
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        
        with self.lock:
            # Generate order ID
            order_id = f"{user_id}_{prop_id}_{int(time.time() * 1000)}"
            
            # Create order
            order = Order(
                order_id=order_id,
                prop_id=prop_id,
                user_id=user_id,
                side=side,
                price=price,
                quantity=quantity,
                timestamp=time.time()
            )
            
            # Add to order book
            self.orders[order_id] = order
            
            # Ensure order book structure exists
            if prop_id not in self.order_book:
                self.order_book[prop_id] = {'bids': [], 'asks': []}
            
            # Map side to order book key
            order_book_key = 'bids' if side == 'buy' else 'asks'
            self.order_book[prop_id][order_book_key].append(order)
            
            # Sort order book by price (bids: highest first, asks: lowest first)
            if order_book_key == 'bids':
                self.order_book[prop_id]['bids'].sort(key=lambda x: x.price, reverse=True)
            else:
                self.order_book[prop_id]['asks'].sort(key=lambda x: x.price)
            
            # Update contract price using VWAP
            self._update_contract_price(prop_id)
            
            logger.info(f"Order placed: {order_id} - {side} {quantity} contracts at ${price}")
            
            return order_id
    
    def _update_contract_price(self, prop_id: str):
        """
        Update contract price using Volume-Weighted Average Price (VWAP)
        and execute matching orders with price improvement
        """
        if prop_id not in self.contracts:
            return
        
        contract = self.contracts[prop_id]
        bids = self.order_book[prop_id]['bids']
        asks = self.order_book[prop_id]['asks']
        
        # Calculate VWAP
        total_bid_value = sum(order.price * order.quantity for order in bids if order.status == 'active')
        total_ask_value = sum(order.price * order.quantity for order in asks if order.status == 'active')
        total_quantity = sum(order.quantity for order in bids + asks if order.status == 'active')
        
        if total_quantity > 0:
            vwap_price = (total_bid_value + total_ask_value) / total_quantity
            contract.current_price = round(vwap_price, 2)
        else:
            # No orders, use initial price
            contract.current_price = self._calculate_initial_price(contract.initial_probability)
        
        contract.total_volume = total_quantity
        contract.last_updated = time.time()
        
        # Execute matching orders with price improvement
        self._execute_matching_orders(prop_id)
        
        logger.debug(f"Updated price for {prop_id}: ${contract.current_price} (VWAP)")
    
    def _execute_matching_orders(self, prop_id: str):
        """
        Execute matching orders when bids cross asks, ensuring price improvement
        """
        if prop_id not in self.order_book:
            return
        
        bids = [order for order in self.order_book[prop_id]['bids'] if order.status == 'active']
        asks = [order for order in self.order_book[prop_id]['asks'] if order.status == 'active']
        
        # Sort orders by price (bids: highest first, asks: lowest first)
        bids.sort(key=lambda x: x.price, reverse=True)
        asks.sort(key=lambda x: x.price)
        
        # Execute matching orders
        while bids and asks and bids[0].price >= asks[0].price:
            best_bid = bids[0]
            best_ask = asks[0]
            
            # Determine execution price (price improvement)
            # Use the better price for both parties
            execution_price = min(best_bid.price, best_ask.price)
            
            # Determine quantity to execute
            execution_quantity = min(best_bid.quantity, best_ask.quantity)
            
            # Execute the trade
            self._execute_trade(best_bid, best_ask, execution_price, execution_quantity)
            
            # Update quantities
            best_bid.quantity -= execution_quantity
            best_ask.quantity -= execution_quantity
            
            # Remove filled orders
            if best_bid.quantity <= 0:
                best_bid.status = 'filled'
                bids.pop(0)
            
            if best_ask.quantity <= 0:
                best_ask.status = 'filled'
                asks.pop(0)
    
    def _execute_trade(self, bid_order: Order, ask_order: Order, execution_price: float, quantity: int):
        """
        Execute a trade between a bid and ask order
        Platform acts as middleman for DFS compliance
        """
        # Update order status
        bid_order.status = 'filled' if bid_order.quantity <= quantity else 'partial'
        ask_order.status = 'filled' if ask_order.quantity <= quantity else 'partial'
        
        # Calculate platform profit (spread)
        platform_profit = (bid_order.price - execution_price) * quantity
        
        # Log the trade with DFS-compliant structure
        logger.info(f"Trade executed: {quantity} contracts")
        logger.info(f"  DFS Structure:")
        logger.info(f"    Bidder {bid_order.user_id} pays platform: ${bid_order.price * quantity:.2f}")
        logger.info(f"    Platform pays asker {ask_order.user_id}: ${execution_price * quantity:.2f}")
        logger.info(f"    Platform profit: ${platform_profit:.2f}")
        logger.info(f"    Contract transferred: {ask_order.user_id} → Platform → {bid_order.user_id}")
        
        # In a real system, you would:
        # 1. Update user portfolios (bidder gets contract, asker gets cash)
        # 2. Record transaction in database with platform as middleman
        # 3. Send notifications to users
        # 4. Update contract ownership (platform holds temporarily)
        # 5. Track platform revenue from spreads
    
    def get_contract_price(self, prop_id: str) -> Optional[float]:
        """Get current price for a prop contract"""
        if prop_id in self.contracts:
            return self.contracts[prop_id].current_price
        return None
    
    def get_market_price(self, prop_id: str) -> Dict[str, Optional[float]]:
        """
        Get current market price (best bid and ask)
        Returns: {'bid': best_bid_price, 'ask': best_ask_price, 'spread': spread}
        """
        if prop_id not in self.order_book:
            return {'bid': None, 'ask': None, 'spread': None}
        
        bids = [order for order in self.order_book[prop_id]['bids'] if order.status == 'active']
        asks = [order for order in self.order_book[prop_id]['asks'] if order.status == 'active']
        
        best_bid = max(bids, key=lambda x: x.price).price if bids else None
        best_ask = min(asks, key=lambda x: x.price).price if asks else None
        
        spread = best_ask - best_bid if best_bid and best_ask else None
        
        return {
            'bid': best_bid,
            'ask': best_ask,
            'spread': spread
        }
    
    def get_contract_info(self, prop_id: str) -> Optional[Dict]:
        """Get full contract information (without revealing probabilities)"""
        if prop_id not in self.contracts:
            return None
        
        contract = self.contracts[prop_id]
        
        return {
            'prop_id': contract.prop_id,
            'player_name': contract.player_name,
            'prop_type': contract.prop_type,
            'line': contract.line,
            'difficulty': contract.difficulty,
            'game_id': contract.game_id,
            'current_price': contract.current_price,
            'total_volume': contract.total_volume,
            'last_updated': contract.last_updated
        }
    
    def get_all_contracts(self) -> List[Dict]:
        """Get all contract information for display"""
        contracts = []
        for contract in self.contracts.values():
            contracts.append(self.get_contract_info(contract.prop_id))
        return contracts
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an active order"""
        if order_id not in self.orders:
            return False
        
        with self.lock:
            order = self.orders[order_id]
            if order.status == 'active':
                order.status = 'cancelled'
                
                # Remove from order book
                order_book_key = 'bids' if order.side == 'buy' else 'asks'
                self.order_book[order.prop_id][order_book_key] = [
                    o for o in self.order_book[order.prop_id][order_book_key] 
                    if o.order_id != order_id
                ]
                
                # Update contract price
                self._update_contract_price(order.prop_id)
                
                logger.info(f"Order cancelled: {order_id}")
                return True
        
        return False
    
    def get_order_book(self, prop_id: str) -> Dict:
        """Get order book for a specific prop (for advanced users)"""
        if prop_id not in self.order_book:
            return {'bids': [], 'asks': []}
        
        bids = [
            {
                'price': order.price,
                'quantity': order.quantity,
                'timestamp': order.timestamp
            }
            for order in self.order_book[prop_id]['bids']
            if order.status == 'active'
        ]
        
        asks = [
            {
                'price': order.price,
                'quantity': order.quantity,
                'timestamp': order.timestamp
            }
            for order in self.order_book[prop_id]['asks']
            if order.status == 'active'
        ]
        
        return {'bids': bids, 'asks': asks}
    
    def get_user_orders(self, user_id: str) -> List[Dict]:
        """Get all orders for a specific user"""
        user_orders = []
        for order in self.orders.values():
            if order.user_id == user_id:
                user_orders.append({
                    'order_id': order.order_id,
                    'prop_id': order.prop_id,
                    'side': order.side,
                    'price': order.price,
                    'quantity': order.quantity,
                    'status': order.status,
                    'timestamp': order.timestamp
                })
        return user_orders
    
    def expire_contracts_at_game_start(self, game_id: str):
        """
        Expire all unsold contracts when a game starts
        This ensures DFS compliance
        """
        with self.lock:
            expired_contracts = []
            for prop_id, contract in self.contracts.items():
                if contract.game_id == game_id:
                    # Cancel all active orders for this contract
                    for order in self.orders.values():
                        if order.prop_id == prop_id and order.status == 'active':
                            order.status = 'expired'
                    
                    expired_contracts.append(prop_id)
            
            logger.info(f"Expired {len(expired_contracts)} contracts for game {game_id}")
            return expired_contracts
    
    def check_exact_hit_refund(self, prop_id: str, actual_value: float, user_id: str = None) -> Dict:
        """
        Check if a prop hit the exact line value and process refund
        Returns refund information for the user
        """
        if prop_id not in self.contracts:
            return {'refund': False, 'amount': 0.0, 'reason': 'Contract not found'}
        
        contract = self.contracts[prop_id]
        line = contract.line
        
        # Check if actual value exactly matches the line
        if actual_value == line:
            # Calculate refund amount (what user actually paid, not fixed payout)
            # For now, use the current contract price as the refund amount
            # In a real system, this would look up the user's actual transaction amount
            refund_amount = contract.current_price if contract.current_price > 0 else contract.fixed_payout
            
            logger.info(f"Exact hit detected for {contract.player_name} {contract.prop_type}: {actual_value} = {line}")
            logger.info(f"Refund amount: ${refund_amount} (amount user paid)")
            
            return {
                'refund': True,
                'amount': refund_amount,
                'reason': f'Exact hit: {actual_value} = {line}',
                'player_name': contract.player_name,
                'prop_type': contract.prop_type,
                'user_id': user_id
            }
        
        return {'refund': False, 'amount': 0.0, 'reason': f'No exact hit: {actual_value} ≠ {line}'}

# Global pricing engine instance
pricing_engine = PricingEngine()

def get_pricing_engine() -> PricingEngine:
    """Get the global pricing engine instance"""
    return pricing_engine
