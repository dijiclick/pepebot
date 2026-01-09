"""
Layer detection module for identifying support/resistance levels.
"""
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class Layer:
    """Represents a support or resistance layer."""
    price: float
    layer_type: str  # 'support' or 'resistance'
    touches: int
    strength: int  # 1-3 (factors matched)
    distance_pct: float  # Distance from current price in %


def detect_swing_highs(highs: List[float], lookback: int = 2) -> List[Tuple[int, float]]:
    """
    Detect swing high points.

    Returns: List of (index, price) tuples
    """
    swings = []
    for i in range(lookback, len(highs) - lookback):
        is_swing = True
        for j in range(1, lookback + 1):
            if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                is_swing = False
                break
        if is_swing:
            swings.append((i, highs[i]))
    return swings


def detect_swing_lows(lows: List[float], lookback: int = 2) -> List[Tuple[int, float]]:
    """
    Detect swing low points.

    Returns: List of (index, price) tuples
    """
    swings = []
    for i in range(lookback, len(lows) - lookback):
        is_swing = True
        for j in range(1, lookback + 1):
            if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                is_swing = False
                break
        if is_swing:
            swings.append((i, lows[i]))
    return swings


def cluster_levels(levels: List[Tuple[int, float]], threshold_pct: float = 0.1) -> List[Dict]:
    """
    Cluster nearby price levels together.

    Args:
        levels: List of (index, price) tuples
        threshold_pct: Percentage threshold for clustering (default 0.1%)

    Returns: List of dicts with 'price', 'touches', 'indices'
    """
    if not levels:
        return []

    clusters = []

    for idx, price in levels:
        found = False
        for cluster in clusters:
            # Check if price is within threshold of existing cluster
            if abs(cluster['price'] - price) / price * 100 < threshold_pct:
                # Update cluster with weighted average
                total_touches = cluster['touches'] + 1
                cluster['price'] = (cluster['price'] * cluster['touches'] + price) / total_touches
                cluster['touches'] = total_touches
                cluster['indices'].append(idx)
                found = True
                break

        if not found:
            clusters.append({
                'price': price,
                'touches': 1,
                'indices': [idx]
            })

    return clusters


def calculate_layer_strength(cluster: Dict, total_bars: int, volumes: List[float] = None) -> int:
    """
    Calculate layer strength (1-3) based on factors.

    Factors:
    1. Touch count (2+ touches)
    2. Recency (any touch in last 20 bars)
    3. Volume (high volume at touch points) - optional

    Returns: Strength score 1-3
    """
    strength = 0

    # Factor 1: Multiple touches
    if cluster['touches'] >= 2:
        strength += 1

    # Factor 2: Recency (touch in last 20 bars)
    recent_threshold = total_bars - 20
    has_recent = any(idx >= recent_threshold for idx in cluster['indices'])
    if has_recent:
        strength += 1

    # Factor 3: Volume confirmation (if volume data provided)
    if volumes and cluster['indices']:
        avg_volume = sum(volumes) / len(volumes) if volumes else 0
        touch_volumes = [volumes[i] for i in cluster['indices'] if i < len(volumes)]
        if touch_volumes:
            avg_touch_volume = sum(touch_volumes) / len(touch_volumes)
            if avg_touch_volume > avg_volume * 1.2:
                strength += 1

    return max(1, min(3, strength))  # Ensure 1-3 range


def find_layers(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float] = None,
        cluster_threshold: float = 0.1,
        max_layers: int = 4
) -> Tuple[List[Layer], List[Layer]]:
    """
    Find support and resistance layers.

    Args:
        highs: List of high prices
        lows: List of low prices
        closes: List of close prices
        volumes: List of volumes (optional)
        cluster_threshold: Clustering threshold in %
        max_layers: Maximum layers per side

    Returns: (resistance_layers, support_layers)
    """
    if len(highs) < 10:
        return [], []

    current_price = closes[-1]
    total_bars = len(closes)

    # Detect swings
    swing_highs = detect_swing_highs(highs)
    swing_lows = detect_swing_lows(lows)

    # Cluster levels
    resistance_clusters = cluster_levels(swing_highs, cluster_threshold)
    support_clusters = cluster_levels(swing_lows, cluster_threshold)

    # Convert to Layer objects and filter by position relative to current price
    resistance_layers = []
    for cluster in resistance_clusters:
        if cluster['price'] > current_price:  # Must be above current price
            strength = calculate_layer_strength(cluster, total_bars, volumes)
            distance = (cluster['price'] - current_price) / current_price * 100
            resistance_layers.append(Layer(
                price=cluster['price'],
                layer_type='resistance',
                touches=cluster['touches'],
                strength=strength,
                distance_pct=distance
            ))

    support_layers = []
    for cluster in support_clusters:
        if cluster['price'] < current_price:  # Must be below current price
            strength = calculate_layer_strength(cluster, total_bars, volumes)
            distance = (current_price - cluster['price']) / current_price * 100
            support_layers.append(Layer(
                price=cluster['price'],
                layer_type='support',
                touches=cluster['touches'],
                strength=strength,
                distance_pct=distance
            ))

    # Sort by touches (descending) and limit
    resistance_layers.sort(key=lambda x: (-x.touches, x.distance_pct))
    support_layers.sort(key=lambda x: (-x.touches, x.distance_pct))

    half_max = max_layers // 2
    return resistance_layers[:half_max], support_layers[:half_max]


def find_nearest_layer(
        current_price: float,
        resistance_layers: List[Layer],
        support_layers: List[Layer],
        threshold_pct: float = 0.1
) -> Optional[Layer]:
    """
    Find the nearest layer within threshold distance.

    Args:
        current_price: Current price
        resistance_layers: List of resistance layers
        support_layers: List of support layers
        threshold_pct: Distance threshold in % (default 0.1%)

    Returns: Nearest layer if within threshold, else None
    """
    nearest = None
    min_distance = float('inf')

    all_layers = resistance_layers + support_layers

    for layer in all_layers:
        if layer.distance_pct < min_distance and layer.distance_pct <= threshold_pct:
            min_distance = layer.distance_pct
            nearest = layer

    return nearest


def format_layer_for_prompt(layer: Layer) -> str:
    """Format a layer for inclusion in AI prompt."""
    return (
        f"{layer.layer_type.upper()} at {layer.price:.8f} "
        f"({layer.distance_pct:.3f}% away, {layer.touches} touches, {layer.strength}/3 strength)"
    )
