"""
Binance WebSocket module for streaming 1-minute candles.
"""
import asyncio
import ccxt.pro as ccxtpro
from typing import Callable, Optional, List, Dict
from datetime import datetime


class BinanceWebSocket:
    """Handles WebSocket connection to Binance for real-time OHLCV data."""

    def __init__(self, symbol: str = "1000PEPE/USDT:USDT", timeframe: str = "1m", limit: int = 60):
        """
        Initialize the WebSocket handler.

        Args:
            symbol: Trading pair (default: 1000PEPE/USDT perpetual)
            timeframe: Candle timeframe (default: 1m)
            limit: Number of candles to keep (default: 60)
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.limit = limit
        self.exchange: Optional[ccxtpro.binance] = None
        self.candles: List[Dict] = []
        self.running = False
        self.on_candle_callback: Optional[Callable] = None

    async def connect(self):
        """Initialize the exchange connection with retry logic."""
        self.exchange = ccxtpro.binance({
            'enableRateLimit': True,
            'timeout': 30000,  # 30 seconds timeout
            'options': {
                'defaultType': 'swap',  # USD-M perpetual futures
            }
        })
        
        # Retry loading markets up to 5 times
        for attempt in range(5):
            try:
                print(f"[WebSocket] Loading Binance Futures markets (attempt {attempt + 1}/5)...")
                await self.exchange.load_markets()
                print(f"[WebSocket] Connected to Binance Futures ({len(self.exchange.markets)} markets)")
                return
            except Exception as e:
                print(f"[WebSocket] Connection failed: {e}")
                if attempt < 4:
                    wait_time = (attempt + 1) * 10
                    print(f"[WebSocket] Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    raise Exception("Failed to connect to Binance after 5 attempts")

    async def close(self):
        """Close the exchange connection."""
        if self.exchange:
            await self.exchange.close()
            print("[WebSocket] Connection closed")

    def set_callback(self, callback: Callable):
        """Set callback function to be called on each new candle."""
        self.on_candle_callback = callback

    async def stream_candles(self):
        """Stream OHLCV candles continuously."""
        self.running = True
        print(f"[WebSocket] Starting stream for {self.symbol} {self.timeframe}")

        while self.running:
            try:
                # Fetch OHLCV data via WebSocket
                ohlcv = await self.exchange.watch_ohlcv(self.symbol, self.timeframe, limit=self.limit)

                # Convert to list of dicts
                self.candles = []
                for candle in ohlcv:
                    self.candles.append({
                        'timestamp': candle[0],
                        'datetime': datetime.fromtimestamp(candle[0] / 1000).isoformat(),
                        'open': candle[1],
                        'high': candle[2],
                        'low': candle[3],
                        'close': candle[4],
                        'volume': candle[5]
                    })

                # Call callback if set
                if self.on_candle_callback and self.candles:
                    await self.on_candle_callback(self.candles)

            except Exception as e:
                print(f"[WebSocket] Error: {e}")
                await asyncio.sleep(5)  # Wait before retry

    def stop(self):
        """Stop the WebSocket stream."""
        self.running = False

    def get_current_price(self) -> float:
        """Get the current (latest close) price."""
        if self.candles:
            return self.candles[-1]['close']
        return 0.0

    def get_ohlcv_lists(self) -> tuple:
        """Get OHLCV data as separate lists for calculations."""
        if not self.candles:
            return [], [], [], [], []

        opens = [c['open'] for c in self.candles]
        highs = [c['high'] for c in self.candles]
        lows = [c['low'] for c in self.candles]
        closes = [c['close'] for c in self.candles]
        volumes = [c['volume'] for c in self.candles]

        return opens, highs, lows, closes, volumes

    def get_candles_summary(self) -> str:
        """Get a summary of recent candles for the AI prompt."""
        if not self.candles:
            return "No data"

        recent = self.candles[-10:]  # Last 10 candles
        summary_lines = []

        for c in recent:
            change = ((c['close'] - c['open']) / c['open']) * 100
            direction = "+" if change >= 0 else ""
            summary_lines.append(
                f"{c['datetime'][-8:]}: O={c['open']:.8f} H={c['high']:.8f} L={c['low']:.8f} C={c['close']:.8f} ({direction}{change:.2f}%)"
            )

        return "\n".join(summary_lines)


async def test_websocket():
    """Test the WebSocket connection."""
    ws = BinanceWebSocket()
    await ws.connect()

    async def on_candle(candles):
        print(f"[Test] Received {len(candles)} candles")
        print(f"[Test] Current price: {ws.get_current_price():.8f}")
        ws.stop()  # Stop after first update for testing

    ws.set_callback(on_candle)
    await ws.stream_candles()
    await ws.close()


if __name__ == "__main__":
    asyncio.run(test_websocket())
