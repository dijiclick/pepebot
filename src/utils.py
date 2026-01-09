"""
Utility functions for technical analysis: ATR, ADX, etc.
"""
import pandas as pd
import numpy as np
from typing import List, Tuple


def calculate_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
    """Calculate Average True Range (ATR)."""
    if len(highs) < period + 1:
        return 0.0

    df = pd.DataFrame({'high': highs, 'low': lows, 'close': closes})

    # True Range
    df['tr1'] = df['high'] - df['low']
    df['tr2'] = abs(df['high'] - df['close'].shift(1))
    df['tr3'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)

    # ATR (RMA/Wilder's smoothing)
    atr = df['tr'].ewm(alpha=1/period, min_periods=period).mean().iloc[-1]
    return float(atr)


def calculate_adx(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
    """Calculate Average Directional Index (ADX)."""
    if len(highs) < period * 2:
        return 0.0

    df = pd.DataFrame({'high': highs, 'low': lows, 'close': closes})

    # +DM and -DM
    df['up_move'] = df['high'].diff()
    df['down_move'] = -df['low'].diff()

    df['+dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
    df['-dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)

    # True Range
    df['tr1'] = df['high'] - df['low']
    df['tr2'] = abs(df['high'] - df['close'].shift(1))
    df['tr3'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)

    # Smoothed values (Wilder's smoothing)
    alpha = 1 / period
    df['atr'] = df['tr'].ewm(alpha=alpha, min_periods=period).mean()
    df['+di'] = 100 * df['+dm'].ewm(alpha=alpha, min_periods=period).mean() / df['atr']
    df['-di'] = 100 * df['-dm'].ewm(alpha=alpha, min_periods=period).mean() / df['atr']

    # DX and ADX
    df['dx'] = 100 * abs(df['+di'] - df['-di']) / (df['+di'] + df['-di']).replace(0, 1)
    df['adx'] = df['dx'].ewm(alpha=alpha, min_periods=period).mean()

    return float(df['adx'].iloc[-1])


def is_ranging(adx_value: float, threshold: float = 25.0) -> bool:
    """Check if market is ranging (ADX below threshold)."""
    return adx_value < threshold


def calculate_position_size(account_balance: float, risk_percent: float, entry: float, stop_loss: float, leverage: int = 10) -> float:
    """
    Calculate position size based on risk management.

    Args:
        account_balance: Total account balance in USDT
        risk_percent: Risk per trade (e.g., 0.2 for 0.2%)
        entry: Entry price
        stop_loss: Stop loss price
        leverage: Leverage used

    Returns:
        Position size in USDT
    """
    risk_amount = account_balance * (risk_percent / 100)
    price_diff_percent = abs(entry - stop_loss) / entry * 100

    if price_diff_percent == 0:
        return 0.0

    # Position size = Risk Amount / (Price Diff % / 100) / Leverage
    position_size = risk_amount / (price_diff_percent / 100)

    return round(position_size, 2)


def format_price(price: float, decimals: int = 8) -> str:
    """Format price with appropriate decimal places."""
    return f"{price:.{decimals}f}"
