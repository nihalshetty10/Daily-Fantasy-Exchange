#!/bin/bash

# Setup daily cron job for PropTrader prop generation
# This script sets up a cron job to run the daily prop generator every morning at 6 AM

# Get the current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create the cron job command
CRON_JOB="0 6 * * * cd $SCRIPT_DIR && python daily_prop_generator.py >> /var/log/proptrader_daily.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "daily_prop_generator.py"; then
    echo "Cron job already exists. Removing old one..."
    crontab -l 2>/dev/null | grep -v "daily_prop_generator.py" | crontab -
fi

# Add the new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "Daily prop generation cron job set up successfully!"
echo "The script will run every day at 6:00 AM"
echo "Logs will be written to /var/log/proptrader_daily.log"
echo ""
echo "To view the cron jobs: crontab -l"
echo "To remove the cron job: crontab -e" 