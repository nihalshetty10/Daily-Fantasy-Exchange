#!/usr/bin/env python3
"""
Startup script for ML Prop Trader
"""

import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app import main
    
    if __name__ == '__main__':
        print("🚀 Starting ML Prop Trader...")
        print("📊 This will start the web application with ML prop generation capabilities")
        print("🔧 Default admin login: admin / admin123")
        print("🌐 Access at: http://127.0.0.1:8003")
        print("=" * 50)
        
        main()
        
except ImportError as e:
    print(f"❌ Error importing modules: {e}")
    print("💡 Make sure all dependencies are installed:")
    print("   pip install flask flask-sqlalchemy flask-socketio beautifulsoup4 requests pandas numpy scikit-learn")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error starting application: {e}")
    sys.exit(1) 