# pump.scanner

A real-time machine learning trading dashboard for pump.fun tokens on the Solana blockchain.

## Project Overview

pump.scanner is a live token analysis tool that connects directly to pump.fun's WebSocket feed, collects trade data in real time, and uses a trained Random Forest classifier to score each token's potential. The dashboard displays active tokens as cards with live sparkline charts, ML confidence scores, and buy/sell signal indicators.

The system has three main components:
- A WebSocket scraper that reverse-engineered pump.fun's undocumented NATS protocol to stream live trade events
- A machine learning pipeline that trains on historical trade data and generates confidence scores for live tokens
- A Django + Django Channels web dashboard that pushes live updates to the browser via WebSocket

## Video

*[Video link to be added]*

## Installation and Setup

**Requirements:** Python 3.12+, pip

1. Clone the repository:
```bash
git clone https://gitlab.com/yourusername/pumpfunbot.git
cd pumpfunbot
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Navigate to the Django project:
```bash
cd code/pumpinterface
```

5. Run database migrations:
```bash
python manage.py migrate
```

6. Train the ML model (requires `data/trades.db`):
```bash
cd ../ml
python train.py
cd ../pumpinterface
```

## Running the Program

Start the full application with a single command:

```bash
python manage.py runall
```

This starts both the Daphne ASGI server and the pump.fun WebSocket scraper simultaneously. Open your browser to:

```
http://localhost:8000
```

The dashboard will begin populating with live token cards within a few seconds as trade data streams in. Cards are automatically cleaned up when tokens go inactive. The ML model scores each token every 5 trades and updates the confidence badge in real time.

To retrain the model on fresh data:
```bash
cd code/ml
python train.py
```

Then restart the application to load the new model.

## How It Works

1. The scraper connects to `wss://unified-prod.nats.realtime.pump.fun` using the NATS pub/sub protocol, discovered by intercepting pump.fun's browser traffic with mitmproxy
2. Every buy/sell event on a bonding curve token is captured and saved to a SQLite database
3. Every 5 trades, technical indicators are computed for that token's recent history and fed into the ML model
4. The confidence score (0-100) is pushed to all connected browsers via Django Channels WebSocket
5. The frontend renders live cards with sparkline charts, sorted by confidence score

## Technologies and Libraries

**Backend**
- Django 6 — web framework and ORM
- Django Channels — WebSocket support for real-time browser updates
- Daphne — ASGI server
- websockets — pump.fun NATS WebSocket connection
- scikit-learn — Random Forest classifier
- pandas / numpy — data processing and feature engineering

**ML Pipeline**
- Random Forest Classifier with hyperparameter tuning via RandomizedSearchCV
- 52 technical indicators including EMA, SMA, MACD, RSI, price velocity, volume velocity, trade imbalance, buy/sell ratio, volatility, and drawdown
- Trained on sliding 5-minute windows with 10-minute lookahead labels from 24+ hours of real pump.fun trade data
- ~8,500 labeled training examples across 1,500+ tokens

**Frontend**
- Vanilla JavaScript with WebSocket client
- SVG sparkline charts rendered client-side
- leo-profanity for content filtering
- Space Mono + Syne fonts (Google Fonts)

**Reverse Engineering**
- mitmproxy — intercepted pump.fun's HTTPS/WebSocket traffic to discover the undocumented NATS API
- Identified hardcoded subscriber credentials and NATS subject patterns from frontend JavaScript

## Author

**Joshua Paige (joshuap00)**

All components designed and implemented independently, including protocol reverse engineering, data pipeline architecture, ML feature engineering, and full-stack Django implementation. Claude (Anthropic) was used as a coding assistant to accelerate implementation of more complex components such as the technical indicator library and Django Channels configuration, with all architectural decisions, debugging, and system design made by the author.