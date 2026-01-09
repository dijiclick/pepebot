"""
PEPE Scalping Bot - 3-Day Backtest with Grok Analysis
Simulates the bot's behavior over historical data and tracks trade outcomes.
"""
import asyncio
import time
import csv
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv

import ccxt.pro as ccxtpro

from src.layers import find_layers, find_nearest_layer
from src.utils import calculate_atr, calculate_adx, is_ranging, calculate_position_size
from src.grok import GrokClient

load_dotenv()

# === CONFIGURATION ===
SYMBOL = "1000PEPE/USDT:USDT"
TIMEFRAME = "1m"
LOOKBACK_DAYS = 3
LOOKBACK_CANDLES = 60  # For layer detection

# Trading parameters
ACCOUNT_BALANCE = 1000
MAX_RISK_PERCENT = 0.2
LEVERAGE = 10

# Bot parameters
LAYER_THRESHOLD_PCT = 0.1  # Trigger when price within 0.1% of layer
MIN_CONFIDENCE = 60
HIGH_CONFIDENCE = 80
COOLDOWN_CANDLES = 1  # No cooldown for backtest - max speed
MIN_LAYER_STRENGTH = 2  # Only analyze layers with strength >= 2
MAX_GROK_CALLS = 10  # Only 10 random setups for quick backtest

# Cost tracking
GROK_COST_PER_CALL = 0.00028


class BacktestTrade:
    """Represents a single backtest trade."""
    
    def __init__(self, entry_idx: int, entry_price: float, direction: str,
                 tp: float, sl: float, confidence: int, reason: str):
        self.entry_idx = entry_idx
        self.entry_price = entry_price
        self.direction = direction
        self.tp = tp
        self.sl = sl
        self.confidence = confidence
        self.reason = reason
        self.exit_idx: Optional[int] = None
        self.exit_price: Optional[float] = None
        self.result: Optional[str] = None  # 'WIN', 'LOSS', 'OPEN'
        self.pnl_percent: float = 0.0
        self.pnl_usd: float = 0.0


class Backtester:
    """Main backtesting engine."""
    
    def __init__(self):
        self.grok = GrokClient()
        self.trades: List[BacktestTrade] = []
        self.grok_calls = 0
        self.setups_found = 0
        self.total_cost = 0.0
        
    async def fetch_historical_data(self) -> List[List]:
        """Fetch historical OHLCV data from Binance."""
        print(f"\n[Backtest] Fetching {LOOKBACK_DAYS} days of historical data...")
        
        exchange = ccxtpro.binance({
            'timeout': 60000,
            'options': {'defaultType': 'swap'}
        })
        
        try:
            # Retry loading markets up to 5 times
            for attempt in range(5):
                try:
                    print(f"   Connecting to Binance (attempt {attempt + 1}/5)...")
                    await exchange.load_markets()
                    print(f"   Connected! ({len(exchange.markets)} markets)")
                    break
                except Exception as e:
                    print(f"   Connection failed: {e}")
                    if attempt < 4:
                        wait_time = (attempt + 1) * 10
                        print(f"   Retrying in {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                    else:
                        raise Exception("Failed to connect to Binance after 5 attempts")
            
            # Calculate start time (3 days ago)
            end_time = int(datetime.now().timestamp() * 1000)
            start_time = end_time - (LOOKBACK_DAYS * 24 * 60 * 60 * 1000)
            
            all_candles = []
            current_time = start_time
            
            # Fetch in chunks (Binance limit is 1500 per request)
            while current_time < end_time:
                candles = await exchange.fetch_ohlcv(
                    SYMBOL, TIMEFRAME,
                    since=current_time,
                    limit=1500
                )
                
                if not candles:
                    break
                    
                all_candles.extend(candles)
                current_time = candles[-1][0] + 60000  # Move to next minute
                
                print(f"   Fetched {len(all_candles)} candles...", end='\r')
                await asyncio.sleep(0.1)  # Rate limiting
            
            print(f"\n[Backtest] Total candles fetched: {len(all_candles)}")
            return all_candles
            
        finally:
            await exchange.close()
    
    def build_ohlcv_summary(self, candles: List[List], end_idx: int) -> str:
        """Build OHLCV summary string for Grok prompt."""
        summary_lines = []
        start_idx = max(0, end_idx - 10)
        
        for i in range(start_idx, end_idx):
            c = candles[i]
            change = ((c[4] - c[1]) / c[1]) * 100
            sign = '+' if change >= 0 else ''
            dt = datetime.fromtimestamp(c[0] / 1000).strftime('%H:%M')
            summary_lines.append(
                f"{dt}: O={c[1]:.8f} H={c[2]:.8f} L={c[3]:.8f} C={c[4]:.8f} ({sign}{change:.2f}%)"
            )
        
        return '\n'.join(summary_lines)
    
    def check_trade_outcome(self, trade: BacktestTrade, candles: List[List]) -> None:
        """Check if TP or SL was hit after trade entry."""
        for i in range(trade.entry_idx + 1, len(candles)):
            high = candles[i][2]
            low = candles[i][3]
            
            if trade.direction == 'LONG':
                # Check if TP hit (high reached TP)
                if high >= trade.tp:
                    trade.exit_idx = i
                    trade.exit_price = trade.tp
                    trade.result = 'WIN'
                    trade.pnl_percent = ((trade.tp - trade.entry_price) / trade.entry_price) * 100
                    break
                # Check if SL hit (low reached SL)
                elif low <= trade.sl:
                    trade.exit_idx = i
                    trade.exit_price = trade.sl
                    trade.result = 'LOSS'
                    trade.pnl_percent = ((trade.sl - trade.entry_price) / trade.entry_price) * 100
                    break
            else:  # SHORT
                # Check if TP hit (low reached TP)
                if low <= trade.tp:
                    trade.exit_idx = i
                    trade.exit_price = trade.tp
                    trade.result = 'WIN'
                    trade.pnl_percent = ((trade.entry_price - trade.tp) / trade.entry_price) * 100
                    break
                # Check if SL hit (high reached SL)
                elif high >= trade.sl:
                    trade.exit_idx = i
                    trade.exit_price = trade.sl
                    trade.result = 'LOSS'
                    trade.pnl_percent = ((trade.entry_price - trade.sl) / trade.entry_price) * 100
                    break
        
        if trade.result is None:
            trade.result = 'OPEN'
        
        # Calculate USD P&L based on position size
        if trade.result != 'OPEN':
            position_size = calculate_position_size(
                ACCOUNT_BALANCE, MAX_RISK_PERCENT,
                trade.entry_price, trade.sl, LEVERAGE
            )
            trade.pnl_usd = position_size * (trade.pnl_percent / 100) * LEVERAGE
    
    async def run_backtest(self) -> Dict:
        """Run the full backtest."""
        import random
        
        print("=" * 60)
        print("PEPE SCALPING BOT - 3-DAY BACKTEST (10 Random Setups)")
        print("=" * 60)
        
        # Fetch historical data
        candles = await self.fetch_historical_data()
        
        if len(candles) < LOOKBACK_CANDLES + 100:
            print("[Backtest] ERROR: Not enough candles fetched")
            return {}
        
        total_candles = len(candles)
        
        print(f"\n[Backtest] Phase 1: Scanning for setups...")
        print(f"   Total candles: {total_candles}")
        
        # Phase 1: Collect all potential setups (fast, no API calls)
        all_setups = []
        
        for i in range(LOOKBACK_CANDLES, total_candles):
            window = candles[i - LOOKBACK_CANDLES:i + 1]
            
            highs = [c[2] for c in window]
            lows = [c[3] for c in window]
            closes = [c[4] for c in window]
            volumes = [c[5] for c in window]
            
            current_price = closes[-1]
            
            atr = calculate_atr(highs, lows, closes)
            adx = calculate_adx(highs, lows, closes)
            market_status = "RANGE" if is_ranging(adx) else "TREND"
            volume_ratio = volumes[-1] / (sum(volumes) / len(volumes)) if volumes else 1.0
            
            resistance_layers, support_layers = find_layers(
                highs, lows, closes, volumes,
                cluster_threshold=0.1,
                max_layers=4
            )
            
            near_layer = find_nearest_layer(
                current_price,
                resistance_layers,
                support_layers,
                threshold_pct=LAYER_THRESHOLD_PCT
            )
            
            if not near_layer or near_layer.strength < MIN_LAYER_STRENGTH:
                continue
            
            # Store setup info
            all_setups.append({
                'idx': i,
                'price': current_price,
                'layer': near_layer,
                'atr': atr,
                'adx': adx,
                'market_status': market_status,
                'volume_ratio': volume_ratio
            })
            
            if len(all_setups) % 10 == 0:
                print(f"   Found {len(all_setups)} setups...", end='\r')
        
        self.setups_found = len(all_setups)
        print(f"\n   Total setups found: {self.setups_found}")
        
        # Phase 2: Randomly select 10 setups
        if len(all_setups) > MAX_GROK_CALLS:
            selected_setups = random.sample(all_setups, MAX_GROK_CALLS)
            selected_setups.sort(key=lambda x: x['idx'])  # Sort by time
        else:
            selected_setups = all_setups
        
        print(f"\n[Backtest] Phase 2: Analyzing {len(selected_setups)} random setups with Grok...")
        
        # Phase 3: Call Grok for selected setups
        for j, setup in enumerate(selected_setups):
            i = setup['idx']
            current_price = setup['price']
            near_layer = setup['layer']
            atr = setup['atr']
            adx = setup['adx']
            market_status = setup['market_status']
            volume_ratio = setup['volume_ratio']
            
            print(f"   Analyzing setup {j+1}/{len(selected_setups)}...", end='\r')
            
            self.grok_calls += 1
            self.total_cost += GROK_COST_PER_CALL
            
            ohlcv_summary = self.build_ohlcv_summary(candles, i)
            
            try:
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
                
                print(f"   Setup {j+1}: {direction} @ {confidence}% confidence")
                
                if direction != 'SKIP' and confidence >= MIN_CONFIDENCE:
                    tp = result['tp']
                    sl = result['sl']
                    
                    if tp == 0 or sl == 0:
                        if direction == 'LONG':
                            tp = current_price + atr
                            sl = current_price - atr
                        else:
                            tp = current_price - atr
                            sl = current_price + atr
                    
                    trade = BacktestTrade(
                        entry_idx=i,
                        entry_price=current_price,
                        direction=direction,
                        tp=tp,
                        sl=sl,
                        confidence=confidence,
                        reason=result['reason']
                    )
                    
                    self.trades.append(trade)
                    
            except Exception as e:
                print(f"\n   [Error] Setup {j+1}: {e}")
                continue
        
        print(f"\n\n[Backtest] Phase 3: Checking trade outcomes...")
        
        for trade in self.trades:
            self.check_trade_outcome(trade, candles)
        
        return self.generate_report(candles)
    
    def generate_report(self, candles: List[List]) -> Dict:
        """Generate backtest report."""
        # Calculate statistics
        wins = [t for t in self.trades if t.result == 'WIN']
        losses = [t for t in self.trades if t.result == 'LOSS']
        open_trades = [t for t in self.trades if t.result == 'OPEN']
        
        total_trades = len(wins) + len(losses)
        win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0
        
        total_pnl_usd = sum(t.pnl_usd for t in self.trades)
        total_pnl_percent = sum(t.pnl_percent for t in self.trades)
        
        # Calculate average R:R
        avg_win = sum(t.pnl_percent for t in wins) / len(wins) if wins else 0
        avg_loss = abs(sum(t.pnl_percent for t in losses) / len(losses)) if losses else 1
        avg_rr = avg_win / avg_loss if avg_loss > 0 else 0
        
        # Time range
        start_time = datetime.fromtimestamp(candles[0][0] / 1000)
        end_time = datetime.fromtimestamp(candles[-1][0] / 1000)
        
        # Print report
        print("\n" + "=" * 60)
        print("BACKTEST REPORT")
        print("=" * 60)
        print(f"Period: {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')}")
        print(f"Symbol: {SYMBOL}")
        print(f"Timeframe: {TIMEFRAME}")
        print("-" * 60)
        print(f"Candles Analyzed: {len(candles)}")
        print(f"Setups Found (price near layer): {self.setups_found}")
        print(f"Grok API Calls: {self.grok_calls}")
        print(f"API Cost: ${self.total_cost:.4f}")
        print("-" * 60)
        print(f"Trades Taken (confidence >= {MIN_CONFIDENCE}%): {len(self.trades)}")
        print(f"  - Wins: {len(wins)}")
        print(f"  - Losses: {len(losses)}")
        print(f"  - Still Open: {len(open_trades)}")
        print("-" * 60)
        if total_trades > 0:
            print(f"Win Rate: {win_rate:.1f}%")
            print(f"Average R:R: {avg_rr:.2f}:1")
            print(f"Avg Win: +{avg_win:.2f}%")
            print(f"Avg Loss: -{avg_loss:.2f}%")
            print("-" * 60)
            print(f"Total P&L: {'+' if total_pnl_percent >= 0 else ''}{total_pnl_percent:.2f}%")
            print(f"Total P&L (USD): {'+' if total_pnl_usd >= 0 else ''}${total_pnl_usd:.2f}")
            print(f"(Based on ${ACCOUNT_BALANCE} account, {MAX_RISK_PERCENT}% risk, {LEVERAGE}x leverage)")
        print("=" * 60)
        
        # Save detailed trade log
        self.save_trade_log(candles)
        
        return {
            'period_start': start_time.isoformat(),
            'period_end': end_time.isoformat(),
            'candles_analyzed': len(candles),
            'setups_found': self.setups_found,
            'grok_calls': self.grok_calls,
            'api_cost': self.total_cost,
            'total_trades': len(self.trades),
            'wins': len(wins),
            'losses': len(losses),
            'open': len(open_trades),
            'win_rate': win_rate,
            'avg_rr': avg_rr,
            'total_pnl_percent': total_pnl_percent,
            'total_pnl_usd': total_pnl_usd
        }
    
    def save_trade_log(self, candles: List[List]) -> None:
        """Save detailed trade log to CSV."""
        os.makedirs('logs', exist_ok=True)
        log_file = 'logs/backtest_results.csv'
        
        with open(log_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Entry Time', 'Exit Time', 'Direction', 'Entry Price', 'TP', 'SL',
                'Exit Price', 'Confidence', 'Result', 'P&L %', 'P&L USD', 'Reason'
            ])
            
            for trade in self.trades:
                entry_time = datetime.fromtimestamp(candles[trade.entry_idx][0] / 1000).strftime('%Y-%m-%d %H:%M')
                exit_time = datetime.fromtimestamp(candles[trade.exit_idx][0] / 1000).strftime('%Y-%m-%d %H:%M') if trade.exit_idx else 'N/A'
                
                writer.writerow([
                    entry_time,
                    exit_time,
                    trade.direction,
                    f"{trade.entry_price:.8f}",
                    f"{trade.tp:.8f}",
                    f"{trade.sl:.8f}",
                    f"{trade.exit_price:.8f}" if trade.exit_price else 'N/A',
                    trade.confidence,
                    trade.result,
                    f"{trade.pnl_percent:.2f}",
                    f"{trade.pnl_usd:.2f}",
                    trade.reason
                ])
        
        print(f"\n[Backtest] Trade log saved to: {log_file}")


async def main():
    """Run backtest."""
    backtester = Backtester()
    results = await backtester.run_backtest()
    return results


if __name__ == "__main__":
    asyncio.run(main())
