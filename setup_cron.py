#!/usr/bin/env python3
"""
Setup cron job for daily prop generation at 7:30 AM
"""

import os
import subprocess
from pathlib import Path

def setup_cron():
    """Set up cron job to run daily prop generation at 7:30 AM"""
    
    # Get the absolute path to the script
    script_path = Path(__file__).parent / "generate_daily_props.py"
    script_path = script_path.resolve()
    
    # Get the Python executable path
    python_path = sys.executable
    
    # Create the cron command
    cron_command = f"30 7 * * * cd {script_path.parent} && {python_path} {script_path} >> /tmp/proptrader_daily.log 2>&1"
    
    print("🔄 Setting up daily prop generation cron job...")
    print(f"📁 Script path: {script_path}")
    print(f"🐍 Python path: {python_path}")
    print(f"⏰ Cron schedule: 7:30 AM daily")
    
    try:
        # Create a temporary file with the cron job
        temp_cron_file = "/tmp/proptrader_cron"
        with open(temp_cron_file, "w") as f:
            f.write(cron_command + "\n")
        
        # Install the cron job
        result = subprocess.run([
            "crontab", "-l"
        ], capture_output=True, text=True)
        
        current_crons = result.stdout
        
        # Check if our cron job already exists
        if "generate_daily_props.py" not in current_crons:
            # Add our cron job to existing crons
            with open(temp_cron_file, "a") as f:
                f.write(current_crons)
            
            # Install the updated crontab
            subprocess.run(["crontab", temp_cron_file], check=True)
            print("✅ Cron job installed successfully!")
            print(f"📝 Cron job: {cron_command}")
        else:
            print("ℹ️ Cron job already exists")
        
        # Clean up
        os.remove(temp_cron_file)
        
        # Show current crontab
        print("\n📋 Current crontab:")
        subprocess.run(["crontab", "-l"])
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error setting up cron job: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

def test_daily_generation():
    """Test the daily prop generation script"""
    print("\n🧪 Testing daily prop generation...")
    
    try:
        result = subprocess.run([
            sys.executable, "generate_daily_props.py"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Daily prop generation test successful!")
            print("📊 Output:")
            print(result.stdout)
        else:
            print("❌ Daily prop generation test failed!")
            print("📊 Error output:")
            print(result.stderr)
            
    except Exception as e:
        print(f"❌ Error testing daily prop generation: {e}")

if __name__ == "__main__":
    import sys
    
    print("🚀 PropTrader Daily Prop Generator Setup")
    print("=" * 50)
    
    # Set up cron job
    if setup_cron():
        print("\n✅ Cron job setup completed!")
        
        # Test the script
        test_daily_generation()
        
        print("\n📅 Your props will now be generated automatically every day at 7:30 AM")
        print("📊 Check /tmp/proptrader_daily.log for generation logs")
    else:
        print("\n❌ Cron job setup failed!")
        print("💡 You can manually run: python3 generate_daily_props.py") 