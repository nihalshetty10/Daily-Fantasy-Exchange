#!/bin/bash

echo "🚀 PropTrader Website Setup"
echo "============================"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8+ first."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is not installed. Please install pip3 first."
    exit 1
fi

echo "✅ pip3 found: $(pip3 --version)"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "🔧 Creating virtual environment..."
    python3 -m venv .venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "🔧 Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "🔧 Installing Python dependencies..."
pip install -r requirements.txt

# Make scripts executable
echo "🔧 Making scripts executable..."
chmod +x generate_daily_props.py
chmod +x start_website.py
chmod +x setup_cron.py

# Generate initial props
echo "🔧 Generating initial MLB props..."
python3 generate_daily_props.py

# Set up cron job for daily updates
echo "🔧 Setting up daily cron job..."
python3 setup_cron.py

echo ""
echo "🎉 Setup Complete!"
echo "================"
echo "✅ Dependencies installed"
echo "✅ Virtual environment configured"
echo "✅ Initial props generated"
echo "✅ Daily cron job configured"
echo ""
echo "🚀 To start your website:"
echo "   python3 start_website.py"
echo ""
echo "🌐 Website will be available at: http://localhost:8000"
echo "📊 Props will update daily at 7:30 AM"
echo ""
echo "💡 Manual commands:"
echo "   - Generate props: python3 generate_daily_props.py"
echo "   - Start website: python3 app.py"
echo "   - Check status: python3 start_website.py" 