#!/bin/bash

# Setup daily cron job for automatic prop generation at 1:30 AM Eastern
# This script should be run once to set up the cron job

# Get the current directory (this should be the project root)
PROJECT_DIR="$(pwd)"

# Get the correct Python path
PYTHON_PATH=$(which python3)

echo "Setting up cron job for project directory: $PROJECT_DIR"
echo "Using Python path: $PYTHON_PATH"

# Create the cron job entry with the correct Python path
CRON_JOB="30 1 * * * cd $PROJECT_DIR && $PYTHON_PATH $PROJECT_DIR/prop_generation.py >> $PROJECT_DIR/logs/cron_prop_generation.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "prop_generation.py"; then
    echo "Cron job for prop generation already exists. Updating..."
    # Remove existing cron job
    crontab -l 2>/dev/null | grep -v "prop_generation.py" | crontab -
fi

# Add the new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "✅ Daily cron job set up successfully!"
echo "📅 Props will be generated automatically at 1:30 AM Eastern every day"
echo "📁 Logs will be saved to: $PROJECT_DIR/logs/cron_prop_generation.log"

# Create logs directory if it doesn't exist
mkdir -p "$PROJECT_DIR/logs"

# Make the script executable
chmod +x "$PROJECT_DIR/prop_generation.py"

echo ""
echo "🔍 To verify the cron job was added:"
echo "   crontab -l"
echo ""
echo "🔄 To manually test prop generation:"
echo "   cd $PROJECT_DIR && $PYTHON_PATH prop_generation.py"
echo ""
echo "📊 To view cron logs:"
echo "   tail -f $PROJECT_DIR/logs/cron_prop_generation.log" 