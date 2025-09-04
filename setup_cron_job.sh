#!/bin/bash

# Setup Cron Job for Daily MLB Prop Generation
# This script sets up a cron job to run daily at 1:30 AM Eastern

echo "🏈 Setting up daily MLB prop generation cron job..."

# Get the current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/daily_prop_generator.py"

# Check if the Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "❌ Error: daily_prop_generator.py not found at $PYTHON_SCRIPT"
    exit 1
fi

# Make the script executable
chmod +x "$PYTHON_SCRIPT"

# Create the cron job entry (1:30 AM Eastern = 6:30 AM UTC)
CRON_JOB="30 6 * * * cd $SCRIPT_DIR && /usr/bin/python3 $PYTHON_SCRIPT >> $SCRIPT_DIR/logs/cron.log 2>&1"

echo "📅 Cron job to be added:"
echo "$CRON_JOB"
echo ""

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "daily_prop_generator.py"; then
    echo "⚠️  Cron job already exists. Removing old entry..."
    crontab -l 2>/dev/null | grep -v "daily_prop_generator.py" | crontab -
fi

# Add the new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

if [ $? -eq 0 ]; then
    echo "✅ Cron job added successfully!"
    echo ""
    echo "📋 Current cron jobs:"
    crontab -l
    echo ""
    echo "🕐 The script will run daily at 1:30 AM Eastern (6:30 AM UTC)"
    echo "📁 Logs will be saved to: $SCRIPT_DIR/logs/"
    echo ""
    echo "To manually test the script, run:"
    echo "python3 $PYTHON_SCRIPT"
    echo ""
    echo "To remove the cron job, run:"
    echo "crontab -e"
    echo "Then delete the line with daily_prop_generator.py"
else
    echo "❌ Failed to add cron job"
    exit 1
fi 