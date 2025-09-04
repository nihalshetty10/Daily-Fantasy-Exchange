#!/usr/bin/env python3
"""
Start Live System
Starts both the WebSocket server and live game monitor
"""

import subprocess
import sys
import os
import time
import signal
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/live_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class LiveSystemManager:
    def __init__(self):
        self.processes = []
        self.logs_dir = 'logs'
        
        # Ensure logs directory exists
        os.makedirs(self.logs_dir, exist_ok=True)
        
    def start_websocket_server(self):
        """Start the WebSocket server"""
        try:
            logger.info("🚀 Starting WebSocket server...")
            
            # Start WebSocket server in background
            websocket_process = subprocess.Popen([
                sys.executable, 'websocket_server.py'
            ], stdout=open(f'{self.logs_dir}/websocket_server.log', 'w'),
               stderr=subprocess.STDOUT)
            
            self.processes.append(('WebSocket Server', websocket_process))
            logger.info(f"✅ WebSocket server started with PID: {websocket_process.pid}")
            
            # Wait a moment for server to start
            time.sleep(2)
            
            return websocket_process
            
        except Exception as e:
            logger.error(f"❌ Failed to start WebSocket server: {e}")
            return None
            
    def start_live_monitor(self):
        """Start the live game monitor"""
        try:
            logger.info("🚀 Starting live game monitor...")
            
            # Start live monitor in background
            monitor_process = subprocess.Popen([
                sys.executable, 'live_game_monitor.py'
            ], stdout=open(f'{self.logs_dir}/live_monitor.log', 'w'),
               stderr=subprocess.STDOUT)
            
            self.processes.append(('Live Game Monitor', monitor_process))
            logger.info(f"✅ Live game monitor started with PID: {monitor_process.pid}")
            
            return monitor_process
            
        except Exception as e:
            logger.error(f"❌ Failed to start live game monitor: {e}")
            return None
            
    def start_flask_app(self):
        """Start the Flask app"""
        try:
            logger.info("🚀 Starting Flask app...")
            
            # Start Flask app in background
            flask_process = subprocess.Popen([
                sys.executable, 'app.py'
            ], stdout=open(f'{self.logs_dir}/flask_app.log', 'w'),
               stderr=subprocess.STDOUT)
            
            self.processes.append(('Flask App', flask_process))
            logger.info(f"✅ Flask app started with PID: {flask_process.pid}")
            
            return flask_process
            
        except Exception as e:
            logger.error(f"❌ Failed to start Flask app: {e}")
            return None
            
    def check_processes(self):
        """Check if all processes are running"""
        for name, process in self.processes:
            if process.poll() is None:
                logger.info(f"✅ {name} is running (PID: {process.pid})")
            else:
                logger.error(f"❌ {name} has stopped (exit code: {process.returncode})")
                
    def stop_all_processes(self):
        """Stop all running processes"""
        logger.info("🛑 Stopping all processes...")
        
        for name, process in self.processes:
            try:
                if process.poll() is None:
                    logger.info(f"🛑 Stopping {name}...")
                    process.terminate()
                    
                    # Wait for graceful shutdown
                    try:
                        process.wait(timeout=5)
                        logger.info(f"✅ {name} stopped gracefully")
                    except subprocess.TimeoutExpired:
                        logger.warning(f"⚠️ {name} didn't stop gracefully, forcing...")
                        process.kill()
                        process.wait()
                        logger.info(f"✅ {name} force stopped")
                        
            except Exception as e:
                logger.error(f"❌ Error stopping {name}: {e}")
                
        self.processes.clear()
        logger.info("✅ All processes stopped")
        
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"📡 Received signal {signum}, shutting down...")
        self.stop_all_processes()
        sys.exit(0)
        
    def run(self):
        """Run the complete live system"""
        try:
            logger.info("🚀 Starting PropTrader Live System...")
            
            # Register signal handlers
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
            
            # Start WebSocket server first
            websocket_process = self.start_websocket_server()
            if not websocket_process:
                logger.error("❌ Failed to start WebSocket server, exiting")
                return
                
            # Start live game monitor
            monitor_process = self.start_live_monitor()
            if not monitor_process:
                logger.error("❌ Failed to start live game monitor, exiting")
                self.stop_all_processes()
                return
                
            # Start Flask app
            flask_process = self.start_flask_app()
            if not flask_process:
                logger.error("❌ Failed to start Flask app, exiting")
                self.stop_all_processes()
                return
                
            logger.info("🎉 All services started successfully!")
            logger.info("🌐 Website: http://localhost:5000")
            logger.info("🔌 WebSocket: ws://localhost:8765")
            logger.info("📊 Check logs in the 'logs' directory")
            logger.info("🛑 Press Ctrl+C to stop all services")
            
            # Monitor processes
            try:
                while True:
                    time.sleep(10)
                    self.check_processes()
                    
            except KeyboardInterrupt:
                logger.info("🛑 Received keyboard interrupt")
                
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
        finally:
            self.stop_all_processes()

if __name__ == "__main__":
    manager = LiveSystemManager()
    manager.run() 