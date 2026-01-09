# PEPE SCALPING AI SYSTEM - SPEC v3.1

---

## Project Overview

| Field | Value |
|-------|-------|
| Project | AI-Powered Bounce Layer Scalping System |
| Trader | dekopa |
| Created | January 2026 |
| Version | 3.1 - Cost-Optimized with Smart API Usage |

---

## What Changed (v3.0 → v3.1)

| Area | v3.0 | v3.1 |
|------|------|------|
| Model | Grok (unspecified) | **Grok 4.1 Fast (Reasoning)** |
| API Frequency | Event-based (unlimited) | **60-second cooldown** |
| X Search | Every call | **Only for 60-80% confidence** |
| Initial Screen | Full analysis | **Technical-only first** |
| Est. Daily Cost | $0.50-2.00 | **$0.20-0.35** |

---

## Trading Parameters

| Parameter | Value |
|-----------|-------|
| Pair | 1000PEPEUSDT (Binance Futures) |
| Leverage | 10x Isolated |
| Timeframe | 1-minute chart |
| Lookback | 1 hour (60 candles) |
| Target Profit | 0.5% per trade OR 1x ATR (whichever smaller) |
| Stop Loss | 1x ATR (minimum 0.3%) |
| Max Risk | 0.2% account per trade |
| Strategy | Layer/FVG bounce scalping in ranging markets |
| Target Win Rate | 65-75% at 1.5:1 R:R |
| Min Confidence | 75% to trigger alert |

---

## AI Model Selection

### Grok 4.1 Fast (Reasoning) ✅

| Specification | Value |
|---------------|-------|
| Model ID | `grok-4-fast-reasoning` |
| Intelligence Score | 64/65 (nearly matches Grok 4) |
| Input Price | $0.20 per 1M tokens |
| Output Price | $0.50 per 1M tokens |
| X Search Price | $5.00 per 1,000 calls ($0.005/call) |
| Context Window | 2M tokens |
| Latency | Fast |

**Why Grok 4.1 Fast?**
- 64 intelligence score (nearly matches Grok 4's 65)
- **15x cheaper** than Grok 4
- Real-time X/Twitter integration available
- 2M context window (more than enough)
- Fast response for scalping

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   PART 1: TRADINGVIEW INDICATOR                                             │
│   • Visual display of bounce layers + FVGs                                  │
│   • Max 4 layers (green support / red resistance)                           │
│   • Market status (RANGE/TREND) + ATR value                                 │
│   • Under 150 lines Pine Script v5                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
                         Trader watches chart
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   PART 2: PYTHON BOT (Cost-Optimized)                                       │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                                                                      │  │
│   │  BINANCE WEBSOCKET                                                   │  │
│   │  Stream 1m candles → Detect price near layer                         │  │
│   │                                                                      │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                              ↓                                              │
│                    ┌─────────────────────┐                                  │
│                    │ 60-SECOND COOLDOWN  │                                  │
│                    │ Last call < 60s ago?│                                  │
│                    │ → SKIP              │                                  │
│                    └─────────────────────┘                                  │
│                              ↓ (cooldown passed)                            │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                                                                      │  │
│   │  STEP 1: TECHNICAL SCREEN (No X Search)                              │  │
│   │  • Send price data + candles to Grok 4.1 Fast                        │  │
│   │  • Cost: ~$0.00028 per call                                          │  │
│   │  • Get: Direction + Confidence (technical only)                      │  │
│   │                                                                      │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                              ↓                                              │
│              ┌───────────────┴───────────────┐                              │
│              ↓                               ↓                              │
│   ┌──────────────────┐            ┌──────────────────┐                      │
│   │ Confidence < 60% │            │ Confidence ≥ 80% │                      │
│   │      SKIP        │            │  SEND ALERT      │                      │
│   │  (log silently)  │            │  (no X needed)   │                      │
│   └──────────────────┘            └──────────────────┘                      │
│                                                                             │
│              ↓ (Confidence 60-79%)                                          │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                                                                      │  │
│   │  STEP 2: X SEARCH CONFIRMATION (Only if borderline)                  │  │
│   │  • Add X/Twitter sentiment check                                     │  │
│   │  • Cost: +$0.005 per call                                            │  │
│   │  • Get: Buzz score, whale mentions, news                             │  │
│   │                                                                      │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                              ↓                                              │
│              ┌───────────────┴───────────────┐                              │
│              ↓                               ↓                              │
│   ┌──────────────────┐            ┌──────────────────┐                      │
│   │ X confirms trade │            │ X rejects trade  │                      │
│   │   SEND ALERT     │            │      SKIP        │                      │
│   └──────────────────┘            └──────────────────┘                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## API Call Logic (Cost-Optimized)

### Cooldown System

```python
COOLDOWN_SECONDS = 60  # Minimum time between API calls

last_api_call = None

def can_call_api():
    if last_api_call is None:
        return True
    elapsed = time.time() - last_api_call
    return elapsed >= COOLDOWN_SECONDS
```

**Why 60-second cooldown?**
- Prevents spam during choppy markets
- Max 60 calls/hour = 1,440 calls/day (theoretical max)
- Realistic: 200-400 calls/day with filters
- Gives time for price action to develop

---

### Two-Step API Flow

#### Step 1: Technical Screen (Every Trigger)

```
Model: grok-4-fast-reasoning
X Search: DISABLED
Cost: ~$0.00028 per call

Purpose: Quick technical check without sentiment overhead
```

**Prompt (Technical Only):**
```
You are an expert PEPE futures scalper. Analyze 1000PEPEUSDT for bounce trade.
Use ONLY technical analysis (no sentiment/news needed yet).

═══════════════════════════════════════════════════════════════════
PRICE DATA
═══════════════════════════════════════════════════════════════════
Current Price: {price}
Near Layer: {support/resistance} at {level} ({distance}% away)
Layer Strength: {2/3 or 3/3} factors, {touch_count} touches

═══════════════════════════════════════════════════════════════════
TECHNICAL DATA (Last 60 1-min candles)
═══════════════════════════════════════════════════════════════════
OHLCV Summary: {ohlcv_summary}
ATR(14): {atr_value}
ADX: {adx_value}
Market Status: {RANGE/TREND}
Volume vs 20-bar avg: {volume_ratio}x

═══════════════════════════════════════════════════════════════════
TASK
═══════════════════════════════════════════════════════════════════
Decide if this is technically a good scalp setup.
Consider: layer strength, price action, volume, momentum.

═══════════════════════════════════════════════════════════════════
RESPOND EXACTLY
═══════════════════════════════════════════════════════════════════
DIRECTION: [LONG / SHORT / SKIP]
CONFIDENCE: [0-100]
TP: [price] (+[percent]% / [x]ATR)
SL: [price] (-[percent]% / [x]ATR)
REASON: [1 sentence]
```

---

#### Step 2: X Search Confirmation (Only if 60-79%)

```
Model: grok-4-fast-reasoning
X Search: ENABLED
Cost: ~$0.0053 per call

Purpose: Sentiment confirmation for borderline setups
```

**Prompt (With X Search):**
```
You are an expert PEPE futures scalper. 
I have a borderline technical setup. Need sentiment confirmation.

═══════════════════════════════════════════════════════════════════
SETUP SUMMARY
═══════════════════════════════════════════════════════════════════
Direction: {direction_from_step1}
Technical Confidence: {confidence_from_step1}%
Entry: {price}
TP: {tp} | SL: {sl}

═══════════════════════════════════════════════════════════════════
SENTIMENT CHECK (Use X Search)
═══════════════════════════════════════════════════════════════════
Please check:
• X/Twitter PEPE sentiment in last hour (buzz score 0-100)
• Any whale mentions or large transfer alerts
• BTC price movement (PEPE follows BTC)
• Breaking crypto news affecting meme coins

═══════════════════════════════════════════════════════════════════
TASK
═══════════════════════════════════════════════════════════════════
Should I take this trade based on current sentiment?

═══════════════════════════════════════════════════════════════════
RESPOND EXACTLY
═══════════════════════════════════════════════════════════════════
TAKE_TRADE: [YES / NO]
SENTIMENT: [BULLISH / BEARISH / NEUTRAL]
BUZZ_SCORE: [0-100]
BTC_STATUS: [UP / DOWN / FLAT] ([percent]%)
WHALE_ALERT: [YES / NO]
REASON: [1 sentence]
```

---

### Decision Matrix

| Step 1 Confidence | Action | X Search? | Cost |
|-------------------|--------|-----------|------|
| 0-59% | ❌ SKIP | No | $0.00028 |
| 60-79% | ⏳ Step 2 | **Yes** | $0.0053 |
| 80-100% | ✅ ALERT | No | $0.00028 |

---

## Cost Estimation (24 Hours)

### Assumptions

| Metric | Conservative | Normal | Aggressive |
|--------|--------------|--------|------------|
| Triggers hitting cooldown | 50% | 40% | 30% |
| Step 1 calls/day | 200 | 350 | 500 |
| Confidence 60-79% rate | 15% | 20% | 25% |
| Step 2 calls/day | 30 | 70 | 125 |

### Cost Breakdown

| Scenario | Step 1 Cost | Step 2 Cost | **Total/Day** |
|----------|-------------|-------------|---------------|
| Conservative | $0.056 | $0.159 | **$0.22** |
| Normal | $0.098 | $0.371 | **$0.47** |
| Aggressive | $0.140 | $0.663 | **$0.80** |

### Monthly Cost

| Scenario | Daily | **Monthly** |
|----------|-------|-------------|
| Conservative | $0.22 | **$6.60** |
| Normal | $0.47 | **$14.10** |
| Aggressive | $0.80 | **$24.00** |

---

## Rate Limiting

```python
# Hard limits to prevent runaway costs
MAX_CALLS_PER_HOUR = 60      # Matches cooldown
MAX_CALLS_PER_DAY = 500      # Safety cap
MAX_X_SEARCHES_PER_DAY = 100 # Limit expensive calls

# Daily cost cap
MAX_DAILY_COST = 1.00  # USD - stop if exceeded
```

---

## Confluence Factors (Unchanged)

> **REQUIRE MINIMUM 2 OF 3 FACTORS TO DRAW LAYER**

### Factor 1: Price Action Peaks/Valleys (Primary)

**Detection:**
- Swing high: `high > high[1] AND high > high[2] AND high > high[-1] AND high > high[-2]`
- Swing low: `low < low[1] AND low < low[2] AND low < low[-1] AND low < low[-2]`

**Clustering:**
- Group levels within 0.05% threshold
- Minimum 2 touches to form valid layer
- More touches = stronger layer (score 1-5)

**Recency Weighting:**
- Last 20 bars: 2x weight
- Bars 21-60: 1x weight

---

### Factor 2: Volume Profile (Approximated)

**Calculation:**
- Divide 60-bar price range into 10 zones
- Sum volume in each zone
- High Volume Nodes (HVN): top 30% volume zones
- Point of Control (POC): highest volume zone

**Layer Validation:**
- Layer must align with HVN (within 0.1%)
- POC = strongest layer (yellow highlight)

---

### Factor 3: Channels/Trendlines

**Calculation:**
- Linear regression on last 60 bars
- Standard deviation bands (1.5σ and 2σ)
- Upper band = resistance, Lower band = support

**Layer Validation:**
- Layer must be within 0.1% of channel boundary

---

## Part 1: TradingView Indicator

### Technical Requirements

- Pine Script v5
- Under 150 lines of code
- No external APIs
- Auto-updates on each new bar
- Maximum 4 active layers
- No alerts (visual only)

### Display Elements

**Layers:**
- Support: GREEN solid line
- Resistance: RED solid line
- POC: YELLOW dashed line

**Info Box (top right):**
```
┌────────────────────────┐
│ 🟢 RANGE (ADX: 18)     │
│ ATR: 0.00000015        │
│ Layers: 3 active       │
└────────────────────────┘
```

---

## Part 2: Python AI Bot

### Data Source

```python
# Binance WebSocket ONLY
import ccxt.pro as ccxtpro

exchange = ccxtpro.binance()
while True:
    candles = await exchange.watch_ohlcv('1000PEPE/USDT', '1m', limit=60)
```

---

### Grok API Integration

```python
from openai import OpenAI

# Grok uses OpenAI-compatible API
client = OpenAI(
    api_key="your-grok-api-key",
    base_url="https://api.x.ai/v1"
)

def call_grok_technical(prompt: str) -> dict:
    """Step 1: Technical analysis only"""
    response = client.chat.completions.create(
        model="grok-4-fast-reasoning",
        messages=[{"role": "user", "content": prompt}],
        # No tools = no X search
    )
    return parse_response(response)

def call_grok_with_x_search(prompt: str) -> dict:
    """Step 2: With X/Twitter sentiment"""
    response = client.chat.completions.create(
        model="grok-4-fast-reasoning",
        messages=[{"role": "user", "content": prompt}],
        tools=[{"type": "x_search"}],  # Enable X search
    )
    return parse_response(response)
```

---

### Main Loop

```python
import time

COOLDOWN = 60  # seconds
last_call = 0
daily_calls = 0
daily_x_searches = 0

async def main():
    global last_call, daily_calls, daily_x_searches
    
    while True:
        candles = await get_candles()
        price = candles[-1]['close']
        layers = calculate_layers(candles)
        
        # Check if price near any layer
        near_layer = find_nearest_layer(price, layers, threshold=0.001)
        
        if not near_layer:
            continue
            
        # Check cooldown
        if time.time() - last_call < COOLDOWN:
            continue
            
        # Check daily limits
        if daily_calls >= 500:
            log("Daily call limit reached")
            continue
        
        # STEP 1: Technical screen
        last_call = time.time()
        daily_calls += 1
        
        result = call_grok_technical(build_technical_prompt(price, near_layer, candles))
        
        if result['confidence'] < 60:
            log(f"SKIP: Low confidence {result['confidence']}%")
            continue
            
        if result['confidence'] >= 80:
            # High confidence - send alert directly
            send_telegram_alert(result, x_search=False)
            continue
        
        # STEP 2: Borderline (60-79%) - need X confirmation
        if daily_x_searches >= 100:
            log("X search limit reached, skipping borderline setup")
            continue
            
        daily_x_searches += 1
        
        x_result = call_grok_with_x_search(build_x_search_prompt(result))
        
        if x_result['take_trade']:
            send_telegram_alert(result, x_result)
        else:
            log(f"SKIP: X sentiment negative - {x_result['reason']}")
```

---

## Telegram Alert Format

### High Confidence (≥80%, No X Search)

```
🟢 LONG SIGNAL
1000PEPEUSDT | 10x Isolated

Entry:  0.0000082
TP:     0.00000824 (+0.5% / 0.8 ATR)
SL:     0.00000812 (-1.0% / 1.0 ATR)
Size:   $50 (0.2% risk)

Layer: Support S1 (3/3 • 4 touches)
Market: 🟢 RANGE (ADX: 18)

🤖 Grok 4.1 Fast
• Confidence: 85% (technical)
• Reason: Strong volume confluence at support

⏱ 2026-01-09 14:32:15 UTC
```

### Borderline Confirmed (60-79% + X Search)

```
🟢 LONG SIGNAL (X Confirmed)
1000PEPEUSDT | 10x Isolated

Entry:  0.0000082
TP:     0.00000824 (+0.5% / 0.8 ATR)
SL:     0.00000812 (-1.0% / 1.0 ATR)
Size:   $50 (0.2% risk)

Layer: Support S1 (2/3 • 3 touches)
Market: 🟢 RANGE (ADX: 22)

🤖 Grok 4.1 Fast
• Technical: 72%
• Sentiment: NEUTRAL (buzz: 28)
• BTC: +0.3% (supportive)
• Whale Alert: NO
• Reason: Low buzz + BTC stable = safe entry

⏱ 2026-01-09 15:45:30 UTC
```

---

## API Keys Required

| Key | Source | Required |
|-----|--------|----------|
| Grok API Key | console.x.ai | ✅ Yes |
| Telegram Bot Token | @BotFather | ✅ Yes |
| Telegram Chat ID | Your user ID | ✅ Yes |

---

## Tech Stack

```
Python 3.10+
├── ccxt          (Binance WebSocket)
├── openai        (Grok API - OpenAI compatible)
├── python-telegram-bot
├── pandas        (data handling)
└── (No Docker - runs directly on PC)
```

---

## Build Order

| Step | Task | Deliverable |
|------|------|-------------|
| 1 | TradingView Indicator | Pine Script v5 (<150 lines) |
| 2 | Python Bot - Core | WebSocket + Layer detection + Cooldown |
| 2.5 | Backtest | 100+ simulated trades, 65%+ win rate |
| 3 | Grok Integration | Two-step flow (technical → X search) |
| 4 | Telegram Alerts | Formatted signals |
| 4.5 | Paper Trading | 1 week live signals, no real trades |
| 5 | Local PC Deployment | Run script + auto-restart |

---

## Deployment: Local PC

### Requirements

- Windows 10/11, macOS, or Linux
- Python 3.10+ installed
- Stable internet connection
- PC must stay ON while trading (no sleep mode)

### Setup Steps

```bash
# 1. Clone/create project folder
mkdir pepe-scalper
cd pepe-scalper

# 2. Create virtual environment
python -m venv venv

# 3. Activate virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Create .env file with API keys
# (see .env.example)

# 6. Run the bot
python src/main.py
```

### Keep PC Awake (Important!)

**Windows:**
- Settings → System → Power → Screen and sleep → Never
- Or use `caffeinate` alternative for Windows

**macOS:**
```bash
caffeinate -i python src/main.py
```

**Linux:**
```bash
systemd-inhibit --what=idle python src/main.py
```

### Auto-Restart on Crash

**Windows (PowerShell script):**
```powershell
# run_bot.ps1
while ($true) {
    python src/main.py
    Write-Host "Bot crashed. Restarting in 5 seconds..."
    Start-Sleep -Seconds 5
}
```

**Mac/Linux (Bash script):**
```bash
#!/bin/bash
# run_bot.sh
while true; do
    python src/main.py
    echo "Bot crashed. Restarting in 5 seconds..."
    sleep 5
done
```

### Run on PC Startup (Optional)

**Windows:**
1. Create shortcut to `run_bot.ps1`
2. Press `Win + R`, type `shell:startup`
3. Move shortcut to startup folder

**macOS:**
- Use Automator to create app, add to Login Items

**Linux:**
- Add to systemd user service or crontab `@reboot`

---

## File Structure

```
pepe-scalper/
├── requirements.txt
├── .env                    # API keys (gitignored)
├── .env.example            # Template for .env
├── run_bot.ps1             # Windows auto-restart script
├── run_bot.sh              # Mac/Linux auto-restart script
├── src/
│   ├── __init__.py
│   ├── main.py             # Entry point + main loop
│   ├── websocket.py        # Binance WebSocket
│   ├── layers.py           # Layer detection
│   ├── grok.py             # Grok API (both steps)
│   ├── telegram.py         # Alerts
│   ├── rate_limiter.py     # Cooldown + daily limits
│   └── utils.py            # ATR, ADX, helpers
├── logs/
│   ├── trades.csv
│   └── api_usage.csv       # Track costs
└── tradingview/
    └── pepe_layers.pine
```

### requirements.txt

```
ccxt>=4.0.0
openai>=1.0.0
python-telegram-bot>=20.0
pandas>=2.0.0
python-dotenv>=1.0.0
```

### .env.example

```
# Grok API
GROK_API_KEY=your-grok-api-key-here

# Telegram
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_CHAT_ID=your-chat-id

# Optional: Binance (for future auto-trade)
# BINANCE_API_KEY=
# BINANCE_API_SECRET=
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Win Rate | 65-75% |
| R:R Ratio | 1.5:1 |
| Max Drawdown | 5% account |
| Monthly Return | 20-50% (ranging) |
| Daily API Cost | $0.20-0.50 |
| Monthly API Cost | $6-15 |

---

## Summary: v3.1 Optimizations

| Feature | Benefit |
|---------|---------|
| Grok 4.1 Fast | 15x cheaper than Grok 4, same intelligence |
| 60-second cooldown | Prevents spam, max 1,440 calls/day |
| Technical-first | Most calls are cheap ($0.00028) |
| X Search only 60-79% | Expensive calls only when needed |
| Daily limits | Hard cap prevents runaway costs |

**Result:** Professional-grade signals at $0.20-0.50/day

---

## Risk Disclaimer

> **⚠️ WARNING:** This system is for educational purposes only. Crypto futures trading with leverage carries extreme risk of loss. Start with paper trading, use only funds you can afford to lose completely, and never rely solely on automated signals. Past performance does not guarantee future results.

---

*End of Specification v3.1*
