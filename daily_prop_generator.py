#!/usr/bin/env python3
"""
Daily MLB Prop Generator - Cron Job Script
Generates props daily at 1:30 AM Eastern and updates the website
"""

import os
import sys
import logging
from datetime import datetime, timezone
import pytz

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/daily_prop_generator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def setup_directories():
    """Create necessary directories if they don't exist"""
    os.makedirs('logs', exist_ok=True)
    os.makedirs('data', exist_ok=True)

def generate_daily_props():
    """Generate daily MLB props"""
    try:
        logger.info("🚀 Starting daily prop generation...")
        
        # Import after path setup
        from prop_generation import RealisticPropGenerator
        
        # Initialize generator
        generator = RealisticPropGenerator()
        
        # Generate today's props
        logger.info("📊 Generating props for today's games...")
        generator.generate_todays_props()
        
        logger.info("✅ Daily prop generation completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error generating daily props: {e}")
        return False

def update_website():
    """Update the website with new props"""
    try:
        logger.info("🌐 Updating website with new props...")
        
        # The website automatically reads from mlb_props.json
        # Just need to ensure the file is updated
        if os.path.exists('mlb_props.json'):
            logger.info("✅ Website will automatically load updated props")
            return True
        else:
            logger.error("❌ mlb_props.json not found")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error updating website: {e}")
        return False

def main():
    """Main function for cron job"""
    try:
        # Setup directories
        setup_directories()
        
        # Get current time in Eastern
        eastern = pytz.timezone('US/Eastern')
        now = datetime.now(eastern)
        
        logger.info(f"🕐 Starting daily prop generation at {now.strftime('%Y-%m-%d %I:%M %p %Z')}")
        
        # Generate props
        if generate_daily_props():
            # Update website
            if update_website():
                logger.info("🎉 Daily prop generation and website update completed successfully")
                return 0
            else:
                logger.error("❌ Website update failed")
                return 1
        else:
            logger.error("❌ Prop generation failed")
            return 1
            
    except Exception as e:
        logger.error(f"❌ Unexpected error in daily prop generator: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 