#!/usr/bin/env python3
"""
Initialize database with Transaction table and sample data
"""

import datetime
from backend.db import Base, engine
from backend.services.profit_tracker import ProfitTracker

def main():
    print("🗄️ Initializing Transaction database...")
    
    # Create all tables
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully")
    except Exception as e:
        print(f"❌ Error creating database tables: {e}")
        return
    
    # Add some sample transactions for demo purposes
    print("📊 Adding sample transactions...")
    
    sample_transactions = [
        # User 1 (demo) transactions
        (1, 'bet', -50.0, 'prop_1', 'Dak Prescott', 'NFL', 'Bet on Dak Prescott passing yards'),
        (1, 'win', 100.0, 'prop_1', 'Dak Prescott', 'NFL', 'Won bet on Dak Prescott passing yards'),
        (1, 'bet', -25.0, 'prop_2', 'Aaron Judge', 'MLB', 'Bet on Aaron Judge home runs'),
        (1, 'loss', 25.0, 'prop_2', 'Aaron Judge', 'MLB', 'Lost bet on Aaron Judge home runs'),
        
        # User 2 (admin) transactions
        (2, 'bet', -100.0, 'prop_3', 'Josh Allen', 'NFL', 'Bet on Josh Allen passing yards'),
        (2, 'win', 200.0, 'prop_3', 'Josh Allen', 'NFL', 'Won bet on Josh Allen passing yards'),
        (2, 'bet', -75.0, 'prop_4', 'Mookie Betts', 'MLB', 'Bet on Mookie Betts hits'),
        (2, 'win', 150.0, 'prop_4', 'Mookie Betts', 'MLB', 'Won bet on Mookie Betts hits'),
        
        # User 3 (testuser) transactions
        (3, 'bet', -30.0, 'prop_5', 'Travis Kelce', 'NFL', 'Bet on Travis Kelce receiving yards'),
        (3, 'loss', 30.0, 'prop_5', 'Travis Kelce', 'NFL', 'Lost bet on Travis Kelce receiving yards'),
        (3, 'bet', -40.0, 'prop_6', 'Ronald Acuña Jr.', 'MLB', 'Bet on Ronald Acuña Jr. total bases'),
        (3, 'win', 80.0, 'prop_6', 'Ronald Acuña Jr.', 'MLB', 'Won bet on Ronald Acuña Jr. total bases'),
    ]
    
    for user_id, transaction_type, amount, prop_id, player_name, sport, description in sample_transactions:
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
            print(f"✅ Added transaction: {transaction_type} ${amount} for {player_name}")
        else:
            print(f"❌ Failed to add transaction for {player_name}")
    
    # Display current leaderboard
    print("\n🏆 Current Leaderboard:")
    leaderboard = ProfitTracker.get_leaderboard(10)
    for user in leaderboard:
        print(f"{user['position']}. {user['full_name']} (@{user['username']}) - ${user['net_profit']:.2f}")
    
    # Display platform net profit
    net_profit = ProfitTracker.get_net_profit()
    print(f"\n💰 Platform Net Profit: ${net_profit:.2f}")
    
    print("\n✅ Transaction database initialization complete!")

if __name__ == "__main__":
    main()
