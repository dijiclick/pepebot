"""
Main entry point for the PEPE Scalping Bot.
"""
import asyncio
import time
import csv
import os
from datetime import datetime
from dotenv import load_dotenv

from websocket import BinanceWebSocket
from layers import find_layers, find_nearest_layer, format_layer_for_prompt
from utils import calculate_atr, calculate_adx, is_ranging, calculate_position_size
from grok import GrokClient
from alerts import TelegramAlert

load_dotenv()

# === CONFIGURATION ===
SYMBOL = "1000PEPE/USDT:USDT"
TIMEFRAME = "1m"
LOOKBACK = 60
LEVERAGE = 10
MAX_RISK_PERCENT = 0.2
ACCOUNT_BALANCE = 1000  # Update with your actual balance

# API Call limits
COOLDOWN_SECONDS = 60
MAX_CALLS_PER_DAY = 500
MAX_X_SEARCHES_PER_DAY = 100

# Confidence thresholds
MIN_CONFIDENCE = 60
HIGH_CONFIDENCE = 80

# Layer detection
LAYER_THRESHOLD_PCT = 0.1  # Trigger when price is within 0.1% of layer


class PepeScalpingBot:
    """Main bot class."""

    def __init__(self):
        self.ws = BinanceWebSocket(SYMBOL, TIMEFRAME, LOOKBACK)
        self.grok = GrokClient()
        self.telegram = TelegramAlert()

        # Rate limiting
        self.last_api_call = 0
        self.daily_calls = 0
        self.daily_x_searches = 0
        self.last_reset_day = datetime.utcnow().day

        # Logging
        self.log_dir = "logs"
        os.makedirs(self.log_dir, exist_ok=True)

    def can_call_api(self) -> bool:
        """Check if we can make an API call (cooldown + daily limit)."""
        # Reset daily counters
        current_day = datetime.utcnow().day
        if current_day != self.last_reset_day:
            self.daily_calls = 0
            self.daily_x_searches = 0
            self.last_reset_day = current_day

        # Check daily limit
        if self.daily_calls >= MAX_CALLS_PER_DAY:
            return False

        # Check cooldown
        elapsed = time.time() - self.last_api_call
        return elapsed >= COOLDOWN_SECONDS

    def log_api_call(self, call_type: str, cost: float):
        """Log API call for cost tracking."""
        log_file = os.path.join(self.log_dir, "api_usage.csv")
        file_exists = os.path.exists(log_file)

        with open(log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['timestamp', 'type', 'cost', 'daily_calls', 'daily_x_searches'])
            writer.writerow([
                datetime.utcnow().isoformat(),
                call_type,
                cost,
                self.daily_calls,
                self.daily_x_searches
            ])

    def log_trade_signal(self, direction: str, entry: float, tp: float, sl: float, confidence: int, reason: str):
        """Log trade signals."""
        log_file = os.path.join(self.log_dir, "trades.csv")
        file_exists = os.path.exists(log_file)

        with open(log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['timestamp', 'direction', 'entry', 'tp', 'sl', 'confidence', 'reason'])
            writer.writerow([
                datetime.utcnow().isoformat(),
                direction,
                entry,
                tp,
                sl,
                confidence,
                reason
            ])

    async def on_candle(self, candles):
        """Callback for each candle update."""
        if len(candles) < 20:
            return
        
        # Periodic status (every 60 candle updates)
        if not hasattr(self, '_update_count'):
            self._update_count = 0
        self._update_count += 1
        if self._update_count % 60 == 0:
            price = candles[-1]['close']
            print(f"[Bot] ♻️ Active | Price: {price:.8f} | Candles: {len(candles)} | Calls today: {self.daily_calls}")

        # Get OHLCV data
        opens, highs, lows, closes, volumes = self.ws.get_ohlcv_lists()
        current_price = closes[-1]

        # Calculate indicators
        atr = calculate_atr(highs, lows, closes)
        adx = calculate_adx(highs, lows, closes)
        market_status = "RANGE" if is_ranging(adx) else "TREND"
        volume_ratio = volumes[-1] / (sum(volumes) / len(volumes)) if volumes else 1.0

        # Find layers
        resistance_layers, support_layers = find_layers(
            highs, lows, closes, volumes,
            cluster_threshold=0.1,
            max_layers=4
        )

        # Check if price is near any layer
        near_layer = find_nearest_layer(
            current_price,
            resistance_layers,
            support_layers,
            threshold_pct=LAYER_THRESHOLD_PCT
        )

        if not near_layer:
            return

        # Check cooldown
        if not self.can_call_api():
            return

        print(f"[Bot] Price {current_price:.8f} near {near_layer.layer_type} at {near_layer.price:.8f}")

        # === STEP 1: Technical Analysis ===
        self.last_api_call = time.time()
        self.daily_calls += 1
        self.log_api_call("technical", 0.00028)

        layer_info = format_layer_for_prompt(near_layer)
        ohlcv_summary = self.ws.get_candles_summary()

        result = self.grok.analyze_technical(
            price=current_price,
            layer_type=near_layer.layer_type,
            layer_price=near_layer.price,
            layer_distance=near_layer.distance_pct,
            layer_strength=f"{near_layer.strength}/3",
            layer_touches=near_layer.touches,
            ohlcv_summary=ohlcv_summary,
            atr_value=atr,
            adx_value=adx,
            market_status=market_status,
            volume_ratio=volume_ratio
        )

        direction = result['direction']
        confidence = result['confidence']
        tp = result['tp']
        sl = result['sl']
        reason = result['reason']

        print(f"[Bot] Analysis: {direction} | Confidence: {confidence}% | Reason: {reason}")

        # === DECISION LOGIC ===

        # Low confidence - SKIP
        if confidence < MIN_CONFIDENCE:
            print(f"[Bot] SKIP: Low confidence {confidence}%")
            return

        # Calculate position size
        position_size = calculate_position_size(
            ACCOUNT_BALANCE, MAX_RISK_PERCENT,
            current_price, sl, LEVERAGE
        )

        # High confidence (>=80%) - Send alert directly
        if confidence >= HIGH_CONFIDENCE:
            print(f"[Bot] HIGH CONFIDENCE: Sending alert")
            self.log_trade_signal(direction, current_price, tp, sl, confidence, reason)

            await self.telegram.send_high_confidence_alert(
                direction=direction,
                entry=current_price,
                tp=tp,
                sl=sl,
                size=position_size,
                layer_info=f"{near_layer.layer_type.title()} ({near_layer.strength}/3 • {near_layer.touches} touches)",
                market_status=market_status,
                adx=adx,
                confidence=confidence,
                reason=reason
            )
            return

        # === STEP 2: Borderline (60-79%) - Need X confirmation ===
        if self.daily_x_searches >= MAX_X_SEARCHES_PER_DAY:
            print(f"[Bot] X search limit reached, skipping borderline setup")
            return

        print(f"[Bot] BORDERLINE: Running X sentiment check")
        self.daily_x_searches += 1
        self.log_api_call("x_search", 0.005)

        x_result = self.grok.analyze_with_sentiment(
            direction=direction,
            confidence=confidence,
            price=current_price,
            tp=tp,
            sl=sl
        )

        print(f"[Bot] X Result: Take={x_result['take_trade']} | Sentiment={x_result['sentiment']}")

        if x_result['take_trade']:
            print(f"[Bot] X CONFIRMED: Sending alert")
            self.log_trade_signal(direction, current_price, tp, sl, confidence, f"{reason} | X: {x_result['reason']}")

            await self.telegram.send_borderline_alert(
                direction=direction,
                entry=current_price,
                tp=tp,
                sl=sl,
                size=position_size,
                layer_info=f"{near_layer.layer_type.title()} ({near_layer.strength}/3 • {near_layer.touches} touches)",
                market_status=market_status,
                adx=adx,
                technical_confidence=confidence,
                sentiment=x_result['sentiment'],
                buzz_score=x_result['buzz_score'],
                btc_status=x_result['btc_status'],
                whale_alert=x_result['whale_alert'],
                reason=x_result['reason']
            )
        else:
            print(f"[Bot] X REJECTED: {x_result['reason']}")

    async def run(self):
        """Main run loop."""
        print("=" * 60)
        print("PEPE Scalping Bot v3.1")
        print("=" * 60)
        print(f"Symbol: {SYMBOL}")
        print(f"Timeframe: {TIMEFRAME}")
        print(f"Leverage: {LEVERAGE}x")
        print(f"Max Risk: {MAX_RISK_PERCENT}%")
        print(f"Cooldown: {COOLDOWN_SECONDS}s")
        print("=" * 60)

        # Connect to WebSocket
        await self.ws.connect()

        # Send startup message
        try:
            await self.telegram.send_startup_message()
        except Exception as e:
            print(f"[Bot] Warning: Could not send startup message: {e}")

        # Set callback
        self.ws.set_callback(self.on_candle)

        # Start streaming
        try:
            await self.ws.stream_candles()
        except KeyboardInterrupt:
            print("\n[Bot] Shutting down...")
        except Exception as e:
            print(f"[Bot] Error: {e}")
            try:
                await self.telegram.send_error_message(str(e))
            except:
                pass
        finally:
            await self.ws.close()
            print("[Bot] Goodbye!")


async def main():
    """Entry point."""
    bot = PepeScalpingBot()
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
