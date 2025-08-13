#!/bin/bash
# PropTrader Persistent Service Starter
# This script keeps your PropTrader app running at all times

APP_DIR="/Users/nihal/Desktop/daily_fantasy_exchange"
APP_NAME="proptrader"
LOG_FILE="$APP_DIR/service.log"
PID_FILE="$APP_DIR/service.pid"

# Function to start the app
start_app() {
    echo "$(date): Starting PropTrader app..." >> "$LOG_FILE"
    
    cd "$APP_DIR"
    source .venv/bin/activate
    
    # Start the app in background
    nohup python app.py >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    
    echo "$(date): PropTrader app started with PID $(cat $PID_FILE)" >> "$LOG_FILE"
    echo "✅ PropTrader app started! PID: $(cat $PID_FILE)"
}

# Function to stop the app
stop_app() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        echo "$(date): Stopping PropTrader app (PID: $PID)..." >> "$LOG_FILE"
        
        kill "$PID" 2>/dev/null
        sleep 2
        
        # Force kill if still running
        if kill -0 "$PID" 2>/dev/null; then
            kill -9 "$PID" 2>/dev/null
            echo "$(date): Force killed PropTrader app" >> "$LOG_FILE"
        fi
        
        rm -f "$PID_FILE"
        echo "$(date): PropTrader app stopped" >> "$LOG_FILE"
        echo "⏹️ PropTrader app stopped"
    else
        echo "❌ No PID file found. App may not be running."
    fi
}

# Function to check if app is running
check_status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "✅ PropTrader app is running (PID: $PID)"
            echo "🌐 Website: http://127.0.0.1:8002/i"
            echo "📊 Live Tracker: Running in background"
        else
            echo "❌ PropTrader app is not running (stale PID file)"
            rm -f "$PID_FILE"
        fi
    else
        echo "❌ PropTrader app is not running"
    fi
}

# Function to restart the app
restart_app() {
    echo "🔄 Restarting PropTrader app..."
    stop_app
    sleep 2
    start_app
}

# Function to monitor and auto-restart
monitor_app() {
    echo "👀 Starting PropTrader monitor service..."
    echo "$(date): Monitor service started" >> "$LOG_FILE"
    
    while true; do
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if ! kill -0 "$PID" 2>/dev/null; then
                echo "$(date): App crashed, restarting..." >> "$LOG_FILE"
                echo "⚠️ App crashed, restarting..."
                start_app
            fi
        else
            echo "$(date): No PID file, starting app..." >> "$LOG_FILE"
            echo "⚠️ No PID file, starting app..."
            start_app
        fi
        
        sleep 30  # Check every 30 seconds
    done
}

# Main script logic
case "$1" in
    start)
        start_app
        ;;
    stop)
        stop_app
        ;;
    restart)
        restart_app
        ;;
    status)
        check_status
        ;;
    monitor)
        monitor_app
        ;;
    *)
        echo "PropTrader Service Manager"
        echo "Usage: $0 {start|stop|restart|status|monitor}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the PropTrader app"
        echo "  stop    - Stop the PropTrader app"
        echo "  restart - Restart the PropTrader app"
        echo "  status  - Check if app is running"
        echo "  monitor - Start monitoring service (auto-restart on crash)"
        echo ""
        echo "To keep app running at all times:"
        echo "  $0 start && $0 monitor"
        ;;
esac 