"""
Backtesting module for PEPE Scalping Bot.
Fetches historical data from Binance and runs analysis with async batch Grok requests.

Usage:
    python -m src.backtest                  # Full backtest with Grok analysis
    python -m src.backtest --scan-only      # Only scan for setups, no Grok API calls
    python -m src.backtest --days 5         # Backtest last 5 days
"""
import asyncio
import ccxt
import os
import csv
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

from src.layers import find_layers, find_nearest_layer, format_layer_for_prompt
from src.utils import calculate_atr, calculate_adx, is_ranging

load_dotenv()

# === CONFIGURATION ===
SYMBOL = "1000PEPE/USDT:USDT"
TIMEFRAME = "1m"
LOOKBACK_CANDLES = 60  # Candles needed for indicator calculation

# Setup filtering (tuned to reduce noise)
LAYER_THRESHOLD_PCT = 0.4  # Increased from 0.1% to 0.4% - meaningful approaches only
MIN_LAYER_TOUCHES = 2      # Minimum touches for layer validity
MIN_LAYER_STRENGTH = 2     # Minimum strength (2/3 or 3/3)
MIN_VOLUME_RATIO = 1.2     # Above average volume required
MIN_ADX = 20               # Filter pure ranging noise

# Batch settings
MAX_CONCURRENT_REQUESTS = 10  # Max parallel Grok API calls


@dataclass
class BacktestSetup:
    """Represents a potential trade setup found during backtesting."""
    timestamp: str
    price: float
    layer_type: str
    layer_price: float
    layer_distance: float
    layer_strength: int
    layer_touches: int
    atr: float
    adx: float
    market_status: str
    volume_ratio: float
    ohlcv_summary: str
    # Grok analysis results (filled after API call)
    direction: str = ""
    confidence: int = 0
    tp: float = 0.0
    sl: float = 0.0
    reason: str = ""


class Backtester:
    """Backtesting engine with async Grok analysis."""

    def __init__(self, scan_only: bool = False):
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'swap'}
        })
        self.scan_only = scan_only
        self.grok = None
        if not scan_only:
            from src.grok import GrokClient
            self.grok = GrokClient()
        self.setups: List[BacktestSetup] = []
        self.results_dir = "backtest_results"
        os.makedirs(self.results_dir, exist_ok=True)

    def fetch_historical_data(self, days: int = 3) -> List[Dict]:
        """
        Fetch historical 1m candles from Binance.

        Args:
            days: Number of days to fetch

        Returns:
            List of candle dicts
        """
        print(f"[Backtest] Fetching {days} days of historical data...")

        # Calculate timestamps
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)

        all_candles = []
        since = int(start_time.timestamp() * 1000)
        end_ts = int(end_time.timestamp() * 1000)

        # Binance limits to 1500 candles per request
        while True:
            print(f"[Backtest] Fetching from {datetime.fromtimestamp(since/1000).isoformat()}...")

            ohlcv = self.exchange.fetch_ohlcv(
                SYMBOL,
                TIMEFRAME,
                since=since,
                limit=1500
            )

            if not ohlcv:
                break

            for candle in ohlcv:
                all_candles.append({
                    'timestamp': candle[0],
                    'datetime': datetime.fromtimestamp(candle[0] / 1000).isoformat(),
                    'open': candle[1],
                    'high': candle[2],
                    'low': candle[3],
                    'close': candle[4],
                    'volume': candle[5]
                })

            # Move to next batch
            since = ohlcv[-1][0] + 60000  # +1 minute

            # Check if we've reached current time
            if since >= end_ts:
                break

            # Small delay to respect rate limits (sync sleep)
            import time
            time.sleep(0.1)

        print(f"[Backtest] Fetched {len(all_candles)} candles")
        return all_candles

    def get_ohlcv_lists(self, candles: List[Dict]) -> Tuple[List, List, List, List, List]:
        """Extract OHLCV as separate lists."""
        opens = [c['open'] for c in candles]
        highs = [c['high'] for c in candles]
        lows = [c['low'] for c in candles]
        closes = [c['close'] for c in candles]
        volumes = [c['volume'] for c in candles]
        return opens, highs, lows, closes, volumes

    def get_candles_summary(self, candles: List[Dict]) -> str:
        """Get summary of last 10 candles for AI prompt."""
        recent = candles[-10:]
        summary_lines = []

        for c in recent:
            change = ((c['close'] - c['open']) / c['open']) * 100
            direction = "+" if change >= 0 else ""
            summary_lines.append(
                f"{c['datetime'][-8:]}: O={c['open']:.8f} H={c['high']:.8f} L={c['low']:.8f} C={c['close']:.8f} ({direction}{change:.2f}%)"
            )

        return "\n".join(summary_lines)

    def find_setups(self, candles: List[Dict]) -> List[BacktestSetup]:
        """
        Scan historical data and find all potential trade setups.
        Applies filtering to reduce noise and focus on high-probability setups.

        Args:
            candles: List of historical candles

        Returns:
            List of BacktestSetup objects
        """
        print(f"[Backtest] Scanning for setups...")
        print(f"[Backtest] Filters: distance<={LAYER_THRESHOLD_PCT}%, touches>={MIN_LAYER_TOUCHES}, strength>={MIN_LAYER_STRENGTH}, volume>={MIN_VOLUME_RATIO}x, ADX>={MIN_ADX}")
        setups = []
        filtered_stats = {'adx': 0, 'volume': 0, 'touches': 0, 'strength': 0}

        # We need at least LOOKBACK_CANDLES for indicators
        for i in range(LOOKBACK_CANDLES, len(candles)):
            # Get window of candles
            window = candles[i - LOOKBACK_CANDLES:i + 1]
            opens, highs, lows, closes, volumes = self.get_ohlcv_lists(window)

            current_price = closes[-1]
            current_candle = candles[i]

            # Calculate indicators
            atr = calculate_atr(highs, lows, closes)
            adx = calculate_adx(highs, lows, closes)
            market_status = "RANGE" if is_ranging(adx) else "TREND"
            volume_ratio = volumes[-1] / (sum(volumes) / len(volumes)) if volumes else 1.0

            # Filter 1: ADX threshold (skip pure noise)
            if adx < MIN_ADX:
                filtered_stats['adx'] += 1
                continue

            # Filter 2: Volume ratio (need above average volume)
            if volume_ratio < MIN_VOLUME_RATIO:
                filtered_stats['volume'] += 1
                continue

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

            if near_layer:
                # Filter 3: Minimum layer touches
                if near_layer.touches < MIN_LAYER_TOUCHES:
                    filtered_stats['touches'] += 1
                    continue

                # Filter 4: Minimum layer strength
                if near_layer.strength < MIN_LAYER_STRENGTH:
                    filtered_stats['strength'] += 1
                    continue

                setup = BacktestSetup(
                    timestamp=current_candle['datetime'],
                    price=current_price,
                    layer_type=near_layer.layer_type,
                    layer_price=near_layer.price,
                    layer_distance=near_layer.distance_pct,
                    layer_strength=near_layer.strength,
                    layer_touches=near_layer.touches,
                    atr=atr,
                    adx=adx,
                    market_status=market_status,
                    volume_ratio=volume_ratio,
                    ohlcv_summary=self.get_candles_summary(window)
                )
                setups.append(setup)

        print(f"[Backtest] Found {len(setups)} potential setups")
        print(f"[Backtest] Filtered out: ADX={filtered_stats['adx']}, Volume={filtered_stats['volume']}, Touches={filtered_stats['touches']}, Strength={filtered_stats['strength']}")
        return setups

    async def analyze_setup_async(self, setup: BacktestSetup, semaphore: asyncio.Semaphore) -> BacktestSetup:
        """
        Analyze a single setup with Grok API (async with semaphore for concurrency control).
        """
        async with semaphore:
            try:
                # Run synchronous Grok call in executor to not block
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self.grok.analyze_technical(
                        price=setup.price,
                        layer_type=setup.layer_type,
                        layer_price=setup.layer_price,
                        layer_distance=setup.layer_distance,
                        layer_strength=f"{setup.layer_strength}/3",
                        layer_touches=setup.layer_touches,
                        ohlcv_summary=setup.ohlcv_summary,
                        atr_value=setup.atr,
                        adx_value=setup.adx,
                        market_status=setup.market_status,
                        volume_ratio=setup.volume_ratio
                    )
                )

                setup.direction = result['direction']
                setup.confidence = result['confidence']
                setup.tp = result['tp']
                setup.sl = result['sl']
                setup.reason = result['reason']

                print(f"[Backtest] {setup.timestamp}: {setup.direction} ({setup.confidence}%)")

            except Exception as e:
                print(f"[Backtest] Error analyzing {setup.timestamp}: {e}")
                setup.direction = "ERROR"
                setup.reason = str(e)

            return setup

    async def analyze_all_setups_async(self, setups: List[BacktestSetup]) -> List[BacktestSetup]:
        """
        Analyze all setups with concurrent async Grok API calls.
        No cooldown - maximum throughput.
        """
        print(f"[Backtest] Analyzing {len(setups)} setups with {MAX_CONCURRENT_REQUESTS} concurrent requests...")

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

        tasks = [
            self.analyze_setup_async(setup, semaphore)
            for setup in setups
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        analyzed = []
        for r in results:
            if isinstance(r, BacktestSetup):
                analyzed.append(r)
            else:
                print(f"[Backtest] Task exception: {r}")

        return analyzed

    def save_setups_pre_grok(self, setups: List[BacktestSetup], filename: str = None):
        """Save setups BEFORE Grok analysis (scan-only mode)."""
        if not filename:
            filename = f"setups_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        filepath = os.path.join(self.results_dir, filename)

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'timestamp', 'price', 'layer_type', 'layer_price', 'layer_distance',
                'layer_strength', 'layer_touches', 'atr', 'adx', 'market_status',
                'volume_ratio'
            ])
            writer.writeheader()

            for setup in setups:
                row = {
                    'timestamp': setup.timestamp,
                    'price': setup.price,
                    'layer_type': setup.layer_type,
                    'layer_price': setup.layer_price,
                    'layer_distance': setup.layer_distance,
                    'layer_strength': setup.layer_strength,
                    'layer_touches': setup.layer_touches,
                    'atr': setup.atr,
                    'adx': setup.adx,
                    'market_status': setup.market_status,
                    'volume_ratio': setup.volume_ratio
                }
                writer.writerow(row)

        print(f"[Backtest] Setups saved to {filepath}")
        return filepath

    def save_results(self, setups: List[BacktestSetup], filename: str = None):
        """Save backtest results to CSV (after Grok analysis)."""
        if not filename:
            filename = f"backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        filepath = os.path.join(self.results_dir, filename)

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'timestamp', 'price', 'layer_type', 'layer_price', 'layer_distance',
                'layer_strength', 'layer_touches', 'atr', 'adx', 'market_status',
                'volume_ratio', 'direction', 'confidence', 'tp', 'sl', 'reason'
            ])
            writer.writeheader()

            for setup in setups:
                row = asdict(setup)
                del row['ohlcv_summary']  # Don't save the large summary
                writer.writerow(row)

        print(f"[Backtest] Results saved to {filepath}")
        return filepath

    def print_scan_summary(self, setups: List[BacktestSetup]):
        """Print summary for scan-only mode (before Grok analysis)."""
        total = len(setups)
        if total == 0:
            print("[Backtest] No setups found.")
            return

        support_setups = [s for s in setups if s.layer_type == 'support']
        resistance_setups = [s for s in setups if s.layer_type == 'resistance']

        trending = [s for s in setups if s.market_status == 'TREND']
        ranging = [s for s in setups if s.market_status == 'RANGE']

        high_strength = [s for s in setups if s.layer_strength == 3]
        medium_strength = [s for s in setups if s.layer_strength == 2]
        low_strength = [s for s in setups if s.layer_strength == 1]

        print("\n" + "=" * 60)
        print("SCAN SUMMARY (Pre-Grok)")
        print("=" * 60)
        print(f"Total Setups Found: {total}")
        print()
        print(f"By Layer Type:")
        print(f"  - Near SUPPORT:    {len(support_setups)} ({len(support_setups)/total*100:.1f}%)")
        print(f"  - Near RESISTANCE: {len(resistance_setups)} ({len(resistance_setups)/total*100:.1f}%)")
        print()
        print(f"By Market Status:")
        print(f"  - TRENDING: {len(trending)} ({len(trending)/total*100:.1f}%)")
        print(f"  - RANGING:  {len(ranging)} ({len(ranging)/total*100:.1f}%)")
        print()
        print(f"By Layer Strength:")
        print(f"  - Strong (3/3): {len(high_strength)} setups")
        print(f"  - Medium (2/3): {len(medium_strength)} setups")
        print(f"  - Weak (1/3):   {len(low_strength)} setups")
        print()

        # Show sample setups
        print("Sample Setups (first 10):")
        print("-" * 60)
        for s in setups[:10]:
            print(f"  {s.timestamp} | {s.layer_type:10} | Price: {s.price:.8f} | Strength: {s.layer_strength}/3 | ADX: {s.adx:.1f}")

        if total > 10:
            print(f"  ... and {total - 10} more")

        print("=" * 60)
        print(f"\nTo run Grok analysis on these {total} setups:")
        print(f"  python -m src.backtest --days 3")
        print("=" * 60)

    def print_summary(self, setups: List[BacktestSetup]):
        """Print backtest summary statistics (after Grok analysis)."""
        total = len(setups)
        if total == 0:
            print("[Backtest] No setups found.")
            return

        longs = [s for s in setups if s.direction == 'LONG']
        shorts = [s for s in setups if s.direction == 'SHORT']
        skips = [s for s in setups if s.direction == 'SKIP']
        errors = [s for s in setups if s.direction == 'ERROR']

        high_conf = [s for s in setups if s.confidence >= 80]
        medium_conf = [s for s in setups if 60 <= s.confidence < 80]
        low_conf = [s for s in setups if s.confidence < 60 and s.direction not in ['SKIP', 'ERROR']]

        print("\n" + "=" * 60)
        print("BACKTEST SUMMARY")
        print("=" * 60)
        print(f"Total Setups Analyzed: {total}")
        print(f"  - LONG signals:  {len(longs)} ({len(longs)/total*100:.1f}%)")
        print(f"  - SHORT signals: {len(shorts)} ({len(shorts)/total*100:.1f}%)")
        print(f"  - SKIP signals:  {len(skips)} ({len(skips)/total*100:.1f}%)")
        print(f"  - ERRORS:        {len(errors)} ({len(errors)/total*100:.1f}%)")
        print()
        print(f"Confidence Distribution:")
        print(f"  - High (>=80%):    {len(high_conf)} signals")
        print(f"  - Medium (60-79%): {len(medium_conf)} signals")
        print(f"  - Low (<60%):      {len(low_conf)} signals")
        print()

        if longs:
            avg_conf_long = sum(s.confidence for s in longs) / len(longs)
            print(f"Avg LONG confidence: {avg_conf_long:.1f}%")
        if shorts:
            avg_conf_short = sum(s.confidence for s in shorts) / len(shorts)
            print(f"Avg SHORT confidence: {avg_conf_short:.1f}%")

        # Show top 5 highest confidence setups
        actionable = [s for s in setups if s.direction in ['LONG', 'SHORT']]
        actionable.sort(key=lambda x: x.confidence, reverse=True)

        if actionable:
            print()
            print("Top 5 Highest Confidence Setups:")
            print("-" * 60)
            for s in actionable[:5]:
                print(f"  {s.timestamp} | {s.direction:5} | {s.confidence}% | {s.layer_type} @ {s.price:.8f}")
                print(f"    TP: {s.tp:.8f} | SL: {s.sl:.8f} | {s.reason[:50]}")

        print("=" * 60)

    async def run(self, days: int = 3):
        """
        Run the full backtest.

        Args:
            days: Number of days to backtest
        """
        mode = "SCAN ONLY" if self.scan_only else "Full Backtest"
        print("=" * 60)
        print(f"PEPE Scalping Bot - {mode} ({days} days)")
        print("=" * 60)

        # Step 1: Fetch historical data
        candles = self.fetch_historical_data(days)

        if len(candles) < LOOKBACK_CANDLES + 10:
            print("[Backtest] Not enough data for backtesting")
            return

        # Step 2: Find all potential setups
        setups = self.find_setups(candles)

        if not setups:
            print("[Backtest] No setups found near layers")
            return

        # Step 3: Save setups (always save pre-Grok data)
        self.save_setups_pre_grok(setups)

        # Step 4: Print scan summary
        self.print_scan_summary(setups)

        # If scan-only mode, stop here
        if self.scan_only:
            return setups

        # Step 5: Analyze setups with Grok (async batch, no cooldown)
        print("\n[Backtest] Starting Grok analysis...")
        analyzed_setups = await self.analyze_all_setups_async(setups)

        # Step 6: Save results with Grok analysis
        self.save_results(analyzed_setups)

        # Step 7: Print full summary
        self.print_summary(analyzed_setups)

        return analyzed_setups


async def main():
    """Entry point for backtesting."""
    # Parse command line arguments
    scan_only = "--scan-only" in sys.argv

    days = 3  # default
    for i, arg in enumerate(sys.argv):
        if arg == "--days" and i + 1 < len(sys.argv):
            try:
                days = int(sys.argv[i + 1])
            except ValueError:
                print(f"Invalid days value: {sys.argv[i + 1]}")
                sys.exit(1)

    backtester = Backtester(scan_only=scan_only)
    await backtester.run(days=days)


if __name__ == "__main__":
    asyncio.run(main())
