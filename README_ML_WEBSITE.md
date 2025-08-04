# ML Prop Trader - Complete Web Application

A full-stack web application that combines machine learning prop generation with live sports trading. The application scrapes real MLB games from MLB.com/scores, uses ML to predict player props, and provides a live trading interface.

## 🚀 Features

### ML Prop Generation
- **Real-time scraping** from MLB.com/scores for today's games
- **Machine learning predictions** for player props using Random Forest models
- **Multiple prop types**: Hits, RBIs, Runs, Total Bases, Strikeouts, Earned Runs Allowed
- **Difficulty levels**: Easy (75% probability), Medium (45% probability), Hard (15% probability)
- **Historical data analysis** from Baseball-Reference

### Live Trading Platform
- **Real-time market** with live contract prices
- **Portfolio management** with balance tracking
- **Trade history** with detailed transaction logs
- **Live updates** every 30 seconds
- **Filtering** by sport, difficulty, and status

### Web Interface
- **Modern responsive design** with Bootstrap 5
- **Real-time updates** with WebSocket support
- **Admin controls** for ML prop generation
- **Trading modal** for buy/sell operations
- **Status indicators** for live games

## 🛠️ Installation

### Prerequisites
- Python 3.8+
- pip package manager

### Dependencies
```bash
pip install flask flask-sqlalchemy flask-socketio beautifulsoup4 requests pandas numpy scikit-learn
```

### Quick Start
1. **Clone or navigate to the project directory**
   ```bash
   cd daily_fantasy_exchange
   ```

2. **Run the application**
   ```bash
   python start_app.py
   ```

3. **Access the website**
   - Open your browser to: http://127.0.0.1:8002
   - Login with: admin / admin123

## 📊 How to Use

### 1. Generate Today's Props
1. Login to the dashboard
2. Click "Generate Today's Props" in the ML Controls section
3. Watch the generation log for real-time updates
4. Props will appear in the Live Market section

### 2. View and Trade Props
1. Browse generated props in the Live Market
2. Filter by sport (MLB), difficulty (Easy/Medium/Hard), or status
3. Click "OVER" or "UNDER" buttons to trade
4. Set quantity and confirm trade in the modal

### 3. Monitor Portfolio
- View your current balance and positions
- Track live prices and game status
- Review trade history

## 🏗️ Architecture

### Backend Components
- **Flask Application** (`app.py`): Main web server
- **ML Prop Generator** (`ml_prop_generator.py`): Scrapes MLB data and generates props
- **Database Models** (`backend/models/`): User, Player, Prop, Trade entities
- **API Routes** (`backend/api/routes.py`): RESTful API endpoints
- **Trading Engine** (`backend/utils/trading_engine.py`): Handles trade execution

### Frontend Components
- **Dashboard** (`frontend/templates/dashboard.html`): Main trading interface
- **ML Controls**: Prop generation and management
- **Live Market**: Real-time prop display and trading
- **Portfolio**: User positions and balance
- **Trade History**: Transaction logs

### Key Files
```
daily_fantasy_exchange/
├── app.py                          # Main Flask application
├── ml_prop_generator.py           # ML prop generation engine
├── start_app.py                   # Startup script
├── frontend/templates/
│   └── dashboard.html             # Main trading interface
├── backend/
│   ├── models/                    # Database models
│   ├── api/routes.py             # API endpoints
│   └── utils/trading_engine.py   # Trading logic
└── config.py                      # Configuration settings
```

## 🔧 Configuration

### Database
- SQLite database (default)
- Located at: `instance/proptrader.db`
- Auto-created on first run

### ML Settings
- **Scraping**: MLB.com/scores for real games
- **Historical Data**: Baseball-Reference for player stats
- **Model**: Random Forest Regressor
- **Features**: Player stats, team data, game context

### Trading Settings
- **Starting Balance**: $1000.00
- **Contract Types**: Over/Under on prop lines
- **Live Updates**: Every 30 seconds
- **Trading Hours**: Based on game times

## 📈 ML Prop Generation Process

1. **Scrape Today's Games**
   - Visit MLB.com/scores
   - Extract game information (teams, times, pitchers)
   - Parse lineup data

2. **Get Player Data**
   - Scrape player historical stats from Baseball-Reference
   - Extract 2 seasons of data + recent performance
   - Calculate player averages and trends

3. **Generate Predictions**
   - Train Random Forest models on historical data
   - Predict prop values based on player performance
   - Calculate implied probabilities

4. **Create Prop Lines**
   - Generate Easy/Medium/Hard difficulty levels
   - Set appropriate line values for target probabilities
   - Create tradeable contracts

## 🎯 Prop Types Supported

### Batter Props
- **Hits**: Total hits in the game
- **RBIs**: Runs batted in
- **Runs**: Runs scored
- **Total Bases**: Total bases reached

### Pitcher Props
- **Strikeouts**: Total strikeouts
- **Earned Runs Allowed**: Runs given up
- **Hits Allowed**: Hits surrendered

## 🔐 Security

- **JWT Authentication** for API access
- **Admin user** created automatically
- **Session management** for user state
- **Input validation** on all endpoints

## 🚨 Troubleshooting

### Common Issues

1. **"No props generated"**
   - Check if MLB.com/scores is accessible
   - Verify internet connection
   - Check generation logs for specific errors

2. **"Database errors"**
   - Delete `instance/proptrader.db` and restart
   - Check file permissions in instance directory

3. **"Import errors"**
   - Install missing dependencies: `pip install -r requirements.txt`
   - Check Python version (3.8+ required)

4. **"Port already in use"**
   - Change port in `app.py` line 180
   - Kill existing process on port 8002

### Debug Mode
```bash
# Enable debug logging
export FLASK_DEBUG=1
python start_app.py
```

## 🔄 API Endpoints

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/register` - User registration

### ML Generation
- `POST /api/generate-today-props` - Generate today's props
- `GET /api/ml-status` - Get ML system status
- `POST /api/clear-props` - Clear all props

### Market Data
- `GET /api/market/props` - Get all props
- `POST /api/market/trade` - Execute trade
- `GET /api/market/live-updates` - Get live updates

### Portfolio
- `GET /api/portfolio` - Get user portfolio
- `GET /api/portfolio/trades` - Get trade history

## 📝 License

This project is for educational and demonstration purposes. Please respect MLB.com and Baseball-Reference terms of service when scraping data.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Review the generation logs
3. Check browser console for JavaScript errors
4. Verify all dependencies are installed

---

**Happy Trading! 🎯📊** 