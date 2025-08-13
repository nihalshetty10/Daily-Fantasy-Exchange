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

## 🔧 Configuration

Key settings in `config.py`:
- `MAX_CONTRACTS_PER_PROP`: 10 contracts per prop
- `STANDARD_PAYOUT`: $100 for winning contracts
- `MAX_PORTFOLIO_SIZE`: 10 total contracts per user

## 🚀 Deployment

### Local Development
```bash
python app.py
```

### AWS Deployment
```bash
python deploy_aws.py
eb create proptrader-prod
eb open
```

## 📁 Project Structure

```
daily_fantasy_exchange/
├── app.py                 # Main Flask application
├── prop_generation.py     # MLB prop scraper and generator
├── backend/               # Backend models and services
│   ├── models/           # Database models
│   ├── services/         # Business logic
│   └── utils/            # Utility functions
├── frontend/             # HTML templates and static files
├── ml/                   # Machine learning models
├── config.py             # Configuration settings
└── requirements.txt      # Python dependencies
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For support and questions:
- Create an issue in the GitHub repository
- Check the documentation in the code comments

## 🔮 Roadmap

- [ ] NBA and NFL prop generation
- [ ] Advanced ML models (LSTM, Random Forest)
- [ ] Social trading features
- [ ] Mobile app
- [ ] Real-time notifications
- [ ] Advanced analytics dashboard

---

**Built with ❤️ for the sports betting community** 