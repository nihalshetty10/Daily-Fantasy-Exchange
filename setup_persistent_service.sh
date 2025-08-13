#!/bin/bash
# Setup script for PropTrader Persistent Service

echo "🚀 Setting up PropTrader Persistent Service..."
echo "This will keep your app running at all times!"

# Get the current directory
CURRENT_DIR=$(pwd)
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$LAUNCH_AGENTS_DIR/com.proptrader.plist"

# Create LaunchAgents directory if it doesn't exist
mkdir -p "$LAUNCH_AGENTS_DIR"

# Copy the plist file to LaunchAgents
echo "📁 Installing Launch Agent..."
cp "$CURRENT_DIR/com.proptrader.plist" "$PLIST_FILE"

# Update the plist file with the correct path
sed -i '' "s|/Users/nihal/Desktop/daily_fantasy_exchange|$CURRENT_DIR|g" "$PLIST_FILE"

# Load the launch agent
echo "🔧 Loading Launch Agent..."
launchctl load "$PLIST_FILE"

# Start the service
echo "🚀 Starting PropTrader service..."
"$CURRENT_DIR/start_persistent_service.sh" start

echo ""
echo "✅ PropTrader Persistent Service Setup Complete!"
echo ""
echo "🎯 What this gives you:"
echo "  • App starts automatically when you log in"
echo "  • App keeps running even if it crashes"
echo "  • App restarts automatically if needed"
echo "  • No more manual starting required!"
echo ""
echo "📱 Commands you can use:"
echo "  • Check status: $CURRENT_DIR/start_persistent_service.sh status"
echo "  • Stop service: $CURRENT_DIR/start_persistent_service.sh stop"
echo "  • Restart service: $CURRENT_DIR/start_persistent_service.sh restart"
echo ""
echo "🌐 Your app is now running at: http://127.0.0.1:8002/i"
echo "📊 Live Tracker is running in the background"
echo ""
echo "🎉 PropTrader will now run at all times!" 