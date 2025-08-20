#!/bin/bash

# Script to check cron job status and recent prop generation

echo "🔍 Checking PropTrader Cron Job Status"
echo "======================================"

# Check if cron job exists
echo "📅 Current Cron Jobs:"
crontab -l 2>/dev/null | grep -E "(prop_generation|daily_fantasy)" || echo "❌ No prop generation cron jobs found"

echo ""
echo "📊 Recent Prop Generation Logs:"
if [ -f "logs/cron_prop_generation.log" ]; then
    echo "✅ Log file exists"
    echo "📝 Last 10 lines of log:"
    tail -10 logs/cron_prop_generation.log
else
    echo "❌ No log file found at logs/cron_prop_generation.log"
fi

echo ""
echo "📈 Prop Generation Status:"
if [ -f "mlb_props.json" ]; then
    # Get last modification time
    LAST_MOD=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" mlb_props.json)
    echo "✅ mlb_props.json exists (last modified: $LAST_MOD)"
    
    # Count players
    PLAYER_COUNT=$(python3 -c "import json; data=json.load(open('mlb_props.json')); print(len(data.get('props', {})))" 2>/dev/null || echo "Error reading file")
    echo "👥 Players with props: $PLAYER_COUNT"
    
    # Count games
    GAME_COUNT=$(python3 -c "import json; data=json.load(open('mlb_props.json')); print(len(data.get('games', [])))" 2>/dev/null || echo "Error reading file")
    echo "🎮 Games included: $GAME_COUNT"
else
    echo "❌ mlb_props.json not found"
fi

echo ""
echo "🕐 Next Scheduled Run:"
echo "   The cron job runs at 1:30 AM Eastern every day"
echo "   Next run: Tomorrow at 1:30 AM Eastern"

echo ""
echo "🔄 To manually test prop generation:"
echo "   python3 prop_generation.py"

echo ""
echo "📊 To monitor logs in real-time:"
echo "   tail -f logs/cron_prop_generation.log" 