import datetime
from typing import Dict, List, Optional
from backend.db import get_db_session
from backend.models.transaction import Transaction
from backend.models.user import User
from sqlalchemy import text, func

class ProfitTracker:
    """Service to track net profits and manage transactions"""
    
    @staticmethod
    def record_transaction(user_id: int, transaction_type: str, amount: float, 
                          prop_id: str = None, player_name: str = None, 
                          sport: str = None, description: str = None) -> bool:
        """Record a new transaction"""
        try:
            from sqlalchemy import text
            
            with next(get_db_session()) as db:
                db.execute(
                    text("""
                        INSERT INTO transactions (user_id, transaction_type, amount, prop_id, player_name, sport, description, created_at)
                        VALUES (:user_id, :transaction_type, :amount, :prop_id, :player_name, :sport, :description, :created_at)
                    """),
                    {
                        'user_id': user_id,
                        'transaction_type': transaction_type,
                        'amount': amount,
                        'prop_id': prop_id,
                        'player_name': player_name,
                        'sport': sport,
                        'description': description,
                        'created_at': datetime.datetime.utcnow()
                    }
                )
                db.commit()
                return True
        except Exception as e:
            print(f"Error recording transaction: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    @staticmethod
    def get_net_profit() -> float:
        """Calculate total net profit for the platform"""
        try:
            from sqlalchemy import text
            
            with next(get_db_session()) as db:
                result = db.execute(
                    text("SELECT COALESCE(SUM(amount), 0) as net_profit FROM transactions")
                ).fetchone()
                
                return float(result.net_profit) if result else 0.0
        except Exception as e:
            print(f"Error calculating net profit: {e}")
            return 0.0
    
    @staticmethod
    def get_user_profit(user_id: int) -> float:
        """Calculate net profit for a specific user"""
        try:
            from sqlalchemy import text
            
            with next(get_db_session()) as db:
                result = db.execute(
                    text("SELECT COALESCE(SUM(amount), 0) as user_profit FROM transactions WHERE user_id = :user_id"),
                    {'user_id': user_id}
                ).fetchone()
                
                return float(result.user_profit) if result else 0.0
        except Exception as e:
            print(f"Error calculating user profit: {e}")
            return 0.0
    
    @staticmethod
    def get_leaderboard(limit: int = 10) -> List[Dict]:
        """Get top users by net profit"""
        try:
            from sqlalchemy import text
            
            with next(get_db_session()) as db:
                result = db.execute(
                    text("""
                        SELECT 
                            u.id,
                            u.username,
                            u.first_name,
                            u.last_name,
                            COALESCE(SUM(t.amount), 0) as net_profit,
                            u.balance
                        FROM users u
                        LEFT JOIN transactions t ON u.id = t.user_id
                        WHERE u.is_active = 1
                        GROUP BY u.id, u.username, u.first_name, u.last_name, u.balance
                        ORDER BY net_profit DESC
                        LIMIT :limit
                    """),
                    {'limit': limit}
                ).fetchall()
                
                leaderboard = []
                current_position = 1
                previous_profit = None
                
                for i, row in enumerate(result):
                    net_profit = float(row.net_profit)
                    
                    # If this user's profit is different from the previous user, update position
                    if previous_profit is not None and net_profit != previous_profit:
                        current_position = i + 1
                    
                    full_name = f"{row.first_name} {row.last_name}" if row.first_name and row.last_name else row.username
                    leaderboard.append({
                        'position': current_position,
                        'user_id': row.id,
                        'username': row.username,
                        'full_name': full_name,
                        'net_profit': net_profit,
                        'balance': float(row.balance)
                    })
                    
                    previous_profit = net_profit
                
                return leaderboard
        except Exception as e:
            print(f"Error getting leaderboard: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    @staticmethod
    def get_user_transactions(user_id: int, limit: int = 50) -> List[Dict]:
        """Get recent transactions for a user"""
        try:
            from sqlalchemy import text
            
            with next(get_db_session()) as db:
                result = db.execute(
                    text("""
                        SELECT * FROM transactions 
                        WHERE user_id = :user_id 
                        ORDER BY created_at DESC 
                        LIMIT :limit
                    """),
                    {'user_id': user_id, 'limit': limit}
                ).fetchall()
                
                transactions = []
                for row in result:
                    transactions.append({
                        'id': row.id,
                        'transaction_type': row.transaction_type,
                        'amount': float(row.amount),
                        'prop_id': row.prop_id,
                        'player_name': row.player_name,
                        'sport': row.sport,
                        'description': row.description,
                        'created_at': row.created_at.isoformat() if row.created_at else None
                    })
                
                return transactions
        except Exception as e:
            print(f"Error getting user transactions: {e}")
            return []
    
    @staticmethod
    def record_prop_bet(user_id: int, prop_id: str, player_name: str, sport: str, bet_amount: float) -> bool:
        """Record a prop bet transaction"""
        return ProfitTracker.record_transaction(
            user_id=user_id,
            transaction_type='bet',
            amount=-bet_amount,  # Negative because it's money going out
            prop_id=prop_id,
            player_name=player_name,
            sport=sport,
            description=f"Bet on {player_name} {sport} prop"
        )
    
    @staticmethod
    def record_prop_win(user_id: int, prop_id: str, player_name: str, sport: str, win_amount: float) -> bool:
        """Record a prop win transaction"""
        return ProfitTracker.record_transaction(
            user_id=user_id,
            transaction_type='win',
            amount=win_amount,  # Positive because it's money coming in
            prop_id=prop_id,
            player_name=player_name,
            sport=sport,
            description=f"Won bet on {player_name} {sport} prop"
        )
    
    @staticmethod
    def record_prop_loss(user_id: int, prop_id: str, player_name: str, sport: str, loss_amount: float) -> bool:
        """Record a prop loss transaction (platform gains)"""
        return ProfitTracker.record_transaction(
            user_id=user_id,
            transaction_type='loss',
            amount=loss_amount,  # Positive for platform (user lost, we gained)
            prop_id=prop_id,
            player_name=player_name,
            sport=sport,
            description=f"User lost bet on {player_name} {sport} prop"
        )
    
    @staticmethod
    def record_cashout(user_id: int, amount: float, description: str = "Cashout") -> bool:
        """Record a cashout transaction"""
        return ProfitTracker.record_transaction(
            user_id=user_id,
            transaction_type='cashout',
            amount=-amount,  # Negative because it's money going out
            description=description
        )
