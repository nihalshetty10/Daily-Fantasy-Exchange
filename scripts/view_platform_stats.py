#!/usr/bin/env python3
"""
Platform Stats Viewer - For creators only
Shows recent platform statistics from the log file
"""

import os
import sys
import json
import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.services.platform_monitor import platform_monitor

def view_platform_stats(hours=24):
    """View recent platform statistics"""
    print("📊 Platform Stats Viewer (Creators Only)")
    print("=" * 50)
    
    stats = platform_monitor.get_recent_stats(hours)
    
    if not stats:
        print("No platform stats found in the last 24 hours.")
        print("Make sure the app is running to generate stats.")
        return
    
    print(f"📈 Recent Platform Statistics (Last {hours} hours)")
    print(f"📅 Total Entries: {len(stats)}")
    print()
    
    # Show latest stats
    if stats:
        latest = stats[-1]
        print("🔥 Latest Stats:")
        print(f"   Timestamp: {latest['timestamp']}")
        print(f"   Net Profit: ${latest['platform_net_profit']:.2f}")
        print(f"   Total Users: {latest['total_users']}")
        print(f"   Active Today: {latest['active_users_today']}")
        print(f"   Transactions Today: {latest['transactions_today']}")
        print(f"   Volume Today: ${latest['volume_today']:.2f}")
        print()
    
    # Show hourly summary
    print("📊 Hourly Summary:")
    hourly_data = {}
    for stat in stats:
        hour = stat['timestamp'][:13]  # Get YYYY-MM-DDTHH
        if hour not in hourly_data:
            hourly_data[hour] = {
                'net_profit': stat['platform_net_profit'],
                'users': stat['total_users'],
                'active': stat['active_users_today'],
                'transactions': stat['transactions_today'],
                'volume': stat['volume_today']
            }
    
    for hour in sorted(hourly_data.keys())[-12:]:  # Last 12 hours
        data = hourly_data[hour]
        print(f"   {hour}: Profit=${data['net_profit']:.2f}, Users={data['users']}, Active={data['active']}, Txns={data['transactions']}, Vol=${data['volume']:.2f}")
    
    print()
    print("💡 To view more detailed logs, check: platform_stats.log")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='View platform statistics')
    parser.add_argument('--hours', type=int, default=24, help='Hours of data to show (default: 24)')
    
    args = parser.parse_args()
    
    view_platform_stats(args.hours)
