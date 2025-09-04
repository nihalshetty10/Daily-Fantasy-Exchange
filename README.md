# Daily Fantasy Exchange 🏈⚾🏀

A real-time sports betting platform for daily fantasy sports with machine learning-powered prop generation and live trading capabilities.

## 🚀 Features

- **MLB Prop Generation**: AI-powered player prop creation using historical data
- **Live Trading Platform**: Real-time contract buying/selling with order book
- **Game Status Tracking**: Automatic updates for upcoming, live, and final games
- **Portfolio Management**: Track your contracts and manage risk
- **Responsive Web Interface**: Modern, mobile-friendly trading dashboard

## 🏗️ Architecture

- **Frontend**: HTML/CSS/JavaScript with Bootstrap
- **Backend**: Flask (Python) with SQLAlchemy ORM
- **Database**: SQLite with real-time updates
- **ML Engine**: Custom algorithms for prop generation
- **Live Tracker**: Background service for game status updates

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/Daily-Fantasy-Exchange.git
   cd Daily-Fantasy-Exchange
   ```

2. **Set up virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Generate fresh props (optional)**
   ```bash
   python prop_generation.py
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

5. **Access the website**
   - Main Dashboard: http://127.0.0.1:8002/i
   - Login Page: http://127.0.0.1:8002/i8

## 📊 How It Works

### Prop Generation
- Scrapes MLB game data and player statistics
- Uses machine learning models to predict player performance
- Generates easy, medium, and hard difficulty props
- Calculates implied probabilities and pricing

### Trading System
- Users can buy/sell contracts on player props
- Real-time order book with bid/ask spreads
- Portfolio constraints (max 10 contracts)
- Automatic execution for favorable limit orders

### Game Status Logic
- **UPCOMING**: Full trading available
- **LIVE**: Can only buy previously sold contracts, sell owned contracts
- **FINAL**: Cash out winning contracts




- [ ] Real-time notifications
- [ ] Advanced analytics dashboard

---

**Built with ❤️ for the sports betting community** 
