"""
Grok API integration for AI-powered trade analysis.
Uses OpenAI-compatible API.
"""
import os
import re
from typing import Dict, Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class GrokClient:
    """Client for Grok API (OpenAI-compatible)."""

    def __init__(self):
        """Initialize the Grok client."""
        self.api_key = os.getenv("GROK_API_KEY")
        if not self.api_key:
            raise ValueError("GROK_API_KEY not found in environment variables")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.x.ai/v1"
        )
        self.model = "grok-4"  # Grok 4 model

    def analyze_technical(
            self,
            price: float,
            layer_type: str,
            layer_price: float,
            layer_distance: float,
            layer_strength: str,
            layer_touches: int,
            ohlcv_summary: str,
            atr_value: float,
            adx_value: float,
            market_status: str,
            volume_ratio: float
    ) -> Dict:
        """
        Step 1: Technical-only analysis (no X search).

        Returns: Dict with direction, confidence, tp, sl, reason
        """
        prompt = f"""You are an expert PEPE futures scalper. Analyze 1000PEPEUSDT for bounce trade.
Use ONLY technical analysis (no sentiment/news needed yet).

===============================================================
PRICE DATA
===============================================================
Current Price: {price:.8f}
Near Layer: {layer_type} at {layer_price:.8f} ({layer_distance:.3f}% away)
Layer Strength: {layer_strength}, {layer_touches} touches

===============================================================
TECHNICAL DATA (Last 60 1-min candles)
===============================================================
OHLCV Summary (last 10 candles):
{ohlcv_summary}

ATR(14): {atr_value:.8f}
ADX: {adx_value:.1f}
Market Status: {market_status}
Volume vs 20-bar avg: {volume_ratio:.2f}x

===============================================================
TASK
===============================================================
Decide if this is technically a good scalp setup.
Consider: layer strength, price action, volume, momentum.

===============================================================
RESPOND EXACTLY IN THIS FORMAT
===============================================================
DIRECTION: [LONG / SHORT / SKIP]
CONFIDENCE: [0-100]
TP: [price]
SL: [price]
REASON: [1 sentence]"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3
            )

            return self._parse_technical_response(response.choices[0].message.content, price, atr_value)

        except Exception as e:
            print(f"[Grok] Technical analysis error: {e}")
            return {
                'direction': 'SKIP',
                'confidence': 0,
                'tp': 0,
                'sl': 0,
                'reason': f'API error: {str(e)}'
            }

    def analyze_with_sentiment(
            self,
            direction: str,
            confidence: int,
            price: float,
            tp: float,
            sl: float
    ) -> Dict:
        """
        Step 2: Sentiment confirmation with X search (only for 60-79% confidence).

        Returns: Dict with take_trade, sentiment, buzz_score, btc_status, whale_alert, reason
        """
        prompt = f"""You are an expert PEPE futures scalper.
I have a borderline technical setup. Need sentiment confirmation.

===============================================================
SETUP SUMMARY
===============================================================
Direction: {direction}
Technical Confidence: {confidence}%
Entry: {price:.8f}
TP: {tp:.8f} | SL: {sl:.8f}

===============================================================
SENTIMENT CHECK (Use X Search)
===============================================================
Please check:
- X/Twitter PEPE sentiment in last hour (buzz score 0-100)
- Any whale mentions or large transfer alerts
- BTC price movement (PEPE follows BTC)
- Breaking crypto news affecting meme coins

===============================================================
TASK
===============================================================
Should I take this trade based on current sentiment?

===============================================================
RESPOND EXACTLY IN THIS FORMAT
===============================================================
TAKE_TRADE: [YES / NO]
SENTIMENT: [BULLISH / BEARISH / NEUTRAL]
BUZZ_SCORE: [0-100]
BTC_STATUS: [UP / DOWN / FLAT]
WHALE_ALERT: [YES / NO]
REASON: [1 sentence]"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                tools=[{"type": "x_search"}],  # Enable X search
                max_tokens=200,
                temperature=0.3
            )

            return self._parse_sentiment_response(response.choices[0].message.content)

        except Exception as e:
            print(f"[Grok] Sentiment analysis error: {e}")
            return {
                'take_trade': False,
                'sentiment': 'NEUTRAL',
                'buzz_score': 0,
                'btc_status': 'FLAT',
                'whale_alert': False,
                'reason': f'API error: {str(e)}'
            }

    def _parse_technical_response(self, response: str, price: float, atr: float) -> Dict:
        """Parse the technical analysis response."""
        result = {
            'direction': 'SKIP',
            'confidence': 0,
            'tp': 0,
            'sl': 0,
            'reason': 'Failed to parse response'
        }

        try:
            lines = response.strip().split('\n')
            for line in lines:
                line = line.strip()

                if line.startswith('DIRECTION:'):
                    direction = line.split(':')[1].strip().upper()
                    if direction in ['LONG', 'SHORT', 'SKIP']:
                        result['direction'] = direction

                elif line.startswith('CONFIDENCE:'):
                    conf_str = line.split(':')[1].strip()
                    conf_match = re.search(r'\d+', conf_str)
                    if conf_match:
                        result['confidence'] = int(conf_match.group())

                elif line.startswith('TP:'):
                    tp_str = line.split(':')[1].strip()
                    tp_match = re.search(r'[\d.]+', tp_str)
                    if tp_match:
                        result['tp'] = float(tp_match.group())

                elif line.startswith('SL:'):
                    sl_str = line.split(':')[1].strip()
                    sl_match = re.search(r'[\d.]+', sl_str)
                    if sl_match:
                        result['sl'] = float(sl_match.group())

                elif line.startswith('REASON:'):
                    result['reason'] = line.split(':', 1)[1].strip()

            # Set default TP/SL based on ATR if not parsed
            if result['tp'] == 0 and result['direction'] != 'SKIP':
                if result['direction'] == 'LONG':
                    result['tp'] = price + atr
                    result['sl'] = price - atr
                else:  # SHORT
                    result['tp'] = price - atr
                    result['sl'] = price + atr

        except Exception as e:
            print(f"[Grok] Parse error: {e}")

        return result

    def _parse_sentiment_response(self, response: str) -> Dict:
        """Parse the sentiment analysis response."""
        result = {
            'take_trade': False,
            'sentiment': 'NEUTRAL',
            'buzz_score': 0,
            'btc_status': 'FLAT',
            'whale_alert': False,
            'reason': 'Failed to parse response'
        }

        try:
            lines = response.strip().split('\n')
            for line in lines:
                line = line.strip()

                if line.startswith('TAKE_TRADE:'):
                    result['take_trade'] = 'YES' in line.upper()

                elif line.startswith('SENTIMENT:'):
                    sentiment = line.split(':')[1].strip().upper()
                    if sentiment in ['BULLISH', 'BEARISH', 'NEUTRAL']:
                        result['sentiment'] = sentiment

                elif line.startswith('BUZZ_SCORE:'):
                    buzz_match = re.search(r'\d+', line)
                    if buzz_match:
                        result['buzz_score'] = int(buzz_match.group())

                elif line.startswith('BTC_STATUS:'):
                    btc = line.split(':')[1].strip().upper()
                    if any(s in btc for s in ['UP', 'DOWN', 'FLAT']):
                        result['btc_status'] = btc.split()[0]

                elif line.startswith('WHALE_ALERT:'):
                    result['whale_alert'] = 'YES' in line.upper()

                elif line.startswith('REASON:'):
                    result['reason'] = line.split(':', 1)[1].strip()

        except Exception as e:
            print(f"[Grok] Sentiment parse error: {e}")

        return result
