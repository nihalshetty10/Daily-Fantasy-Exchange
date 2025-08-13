#!/usr/bin/env python3
"""
PropTrader Website Startup Script
Ensures everything is running with fresh props
"""

import os
import sys
import subprocess
import time
import json
from datetime import datetime
from pathlib import Path

def check_props_file():
    """Check if props file exists and is recent"""
    props_file = 'mlb_props.json'
    
    if not os.path.exists(props_file):
        print("❌ No props file found!")
        return False
    
    # Check file size
    file_size = os.path.getsize(props_file)
    if file_size < 1000:  # Less than 1KB
        print("❌ Props file is too small, may be empty")
        return False
    
    # Check last modified time
    mtime = os.path.getmtime(props_file)
    file_age = time.time() - mtime
    file_age_hours = file_age / 3600
    
    print(f"📁 Props file: {props_file}")
    print(f"📊 File size: {file_size:,} bytes")
    print(f"🕒 Last updated: {datetime.fromtimestamp(mtime)} ({file_age_hours:.1f} hours ago)")
    
    if file_age_hours > 24:
        print("⚠️ Props file is over 24 hours old!")
        return False
    
    return True

def generate_fresh_props():
    """Generate fresh props if needed"""
    print("\n🔄 Generating fresh props...")
    
    try:
        result = subprocess.run([
            sys.executable, "generate_daily_props.py"
        ], capture_output=True, text=True, timeout=300)  # 5 minute timeout
        
        if result.returncode == 0:
            print("✅ Props generated successfully!")
            print("📊 Output preview:")
            lines = result.stdout.strip().split('\n')
            for line in lines[-5:]:  # Show last 5 lines
                print(f"   {line}")
            return True
        else:
            print("❌ Props generation failed!")
            print("📊 Error output:")
            print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("⏰ Props generation timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"❌ Error running props generation: {e}")
        return False

def start_website():
    """Start the Flask website"""
    print("\n🌐 Starting PropTrader website...")
    
    try:
        # Check if website is already running
        result = subprocess.run([
            "lsof", "-ti", ":8000"
        ], capture_output=True, text=True)
        
        if result.stdout.strip():
            print("✅ Website is already running on port 8000")
            print(f"🌐 Access at: http://localhost:8000")
            return True
        
        # Start the website
        print("🚀 Starting website...")
        subprocess.Popen([
            sys.executable, "app.py"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait a moment for startup
        time.sleep(3)
        
        # Check if it's running
        result = subprocess.run([
            "lsof", "-ti", ":8000"
        ], capture_output=True, text=True)
        
        if result.stdout.strip():
            print("✅ Website started successfully!")
            print(f"🌐 Access at: http://localhost:8000")
            return True
        else:
            print("❌ Website failed to start")
            return False
            
    except Exception as e:
        print(f"❌ Error starting website: {e}")
        return False

def check_website_health():
    """Check if website is responding"""
    print("\n🏥 Checking website health...")
    
    try:
        import requests
        
        response = requests.get("http://localhost:8000", timeout=10)
        if response.status_code == 200:
            print("✅ Website is responding correctly")
            return True
        else:
            print(f"⚠️ Website responded with status: {response.status_code}")
            return False
            
    except ImportError:
        print("⚠️ Requests library not available, skipping health check")
        return True
    except Exception as e:
        print(f"❌ Website health check failed: {e}")
        return False

def main():
    """Main startup function"""
    print("🚀 PropTrader Website Startup")
    print("=" * 40)
    
    # Step 1: Check props file
    print("📊 Checking props file...")
    if not check_props_file():
        print("\n🔄 Props file needs updating...")
        if not generate_fresh_props():
            print("❌ Failed to generate props!")
            print("💡 You can manually run: python3 generate_daily_props.py")
            return False
    else:
        print("✅ Props file is up to date!")
    
    # Step 2: Start website
    if not start_website():
        print("❌ Failed to start website!")
        return False
    
    # Step 3: Health check
    if not check_website_health():
        print("⚠️ Website may not be fully ready")
    
    # Step 4: Final status
    print("\n🎉 PropTrader is ready!")
    print("=" * 40)
    print("🌐 Website: http://localhost:8000")
    print("📊 Props: mlb_props.json")
    print("📅 Props updated: Daily at 7:30 AM")
    print("💡 Manual props update: python3 generate_daily_props.py")
    print("🔄 Auto-restart: python3 start_website.py")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1) 