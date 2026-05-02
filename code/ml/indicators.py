import pandas as pd
import numpy as np


EPSILON = 1e-8


def ema(series: pd.Series, period: int) -> float:
    """Exponential moving average of a price series."""
    series = pd.to_numeric(series, errors="coerce").dropna()

    if series.empty:
        return 0.0

    if len(series) < period:
        return float(series.mean())

    return float(series.ewm(span=period, adjust=False).mean().iloc[-1])


def sma(series: pd.Series, period: int) -> float:
    """Simple moving average of a price series."""
    series = pd.to_numeric(series, errors="coerce").dropna()

    if series.empty:
        return 0.0

    if len(series) < period:
        return float(series.mean())

    return float(series.rolling(window=period).mean().iloc[-1])


def macd(series: pd.Series, fast=12, slow=26, signal=9) -> dict:
    """
    MACD line = EMA(fast) - EMA(slow)
    Signal line = EMA(MACD, signal)
    Histogram = MACD - Signal
    """
    series = pd.to_numeric(series, errors="coerce").dropna()

    if len(series) < slow:
        return {
            "macd_line": 0.0,
            "macd_signal": 0.0,
            "macd_histogram": 0.0,
        }

    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()

    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    return {
        "macd_line": float(macd_line.iloc[-1]),
        "macd_signal": float(signal_line.iloc[-1]),
        "macd_histogram": float(histogram.iloc[-1]),
    }


def rsi(series: pd.Series, period=14) -> float:
    """
    Relative Strength Index.
    Range: 0-100.
    >70 overbought, <30 oversold.
    """
    series = pd.to_numeric(series, errors="coerce").dropna()

    if len(series) < period + 1:
        return 50.0

    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(span=period, adjust=False).mean().iloc[-1]
    avg_loss = loss.ewm(span=period, adjust=False).mean().iloc[-1]

    if pd.isna(avg_gain) or pd.isna(avg_loss):
        return 50.0

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return float(100 - (100 / (1 + rs)))


def trade_imbalance(df: pd.DataFrame, windows=(1, 3, 5, 10, 30)) -> dict:
    """
    (number_of_buys - number_of_sells) / total_trades

    Range: -1 to +1.
    """
    result = {}
    now = df["timestamp"].iloc[-1]

    for w in windows:
        cutoff = now - pd.Timedelta(seconds=w)
        subset = df[df["timestamp"] >= cutoff]

        buys = (subset["trade_type"] == "buy").sum()
        sells = (subset["trade_type"] == "sell").sum()
        total = buys + sells

        result[f"trade_imbalance_{w}s"] = float((buys - sells) / total) if total > 0 else 0.0

    return result


def volume_velocity(df: pd.DataFrame, windows=(3, 5, 10, 30)) -> dict:
    """
    Stable volume expansion signal.

    Instead of:
        recent_volume / previous_volume

    this uses:
        log1p(recent_volume) - log1p(previous_volume)

    This avoids insane spikes when previous volume is near zero.
    """
    result = {}
    now = df["timestamp"].iloc[-1]

    for w in windows:
        recent_cutoff = now - pd.Timedelta(seconds=w)
        prev_cutoff = now - pd.Timedelta(seconds=w * 2)

        recent = df[df["timestamp"] >= recent_cutoff]["amount_usd"].sum()

        previous = df[
            (df["timestamp"] >= prev_cutoff)
            & (df["timestamp"] < recent_cutoff)
        ]["amount_usd"].sum()

        result[f"volume_velocity_{w}s"] = float(np.log1p(recent) - np.log1p(previous))

    return result


def price_velocity(df: pd.DataFrame, windows=(1, 3, 5, 10, 15, 30, 60, 120, 240)) -> dict:
    """
    Price movement over recent windows.

    This measures:
        (current_price - earliest_price_inside_window) / earliest_price_inside_window

    It does not guarantee exact price from exactly N seconds ago.
    """
    result = {}
    now = df["timestamp"].iloc[-1]
    current_price = float(df["market_cap"].iloc[-1])

    for w in windows:
        cutoff = now - pd.Timedelta(seconds=w)
        subset = df[df["timestamp"] >= cutoff]

        if len(subset) < 2:
            result[f"price_velocity_{w}s"] = 0.0
            continue

        past_price = float(subset["market_cap"].iloc[0])

        if past_price <= 0:
            result[f"price_velocity_{w}s"] = 0.0
            continue

        result[f"price_velocity_{w}s"] = float(
            (current_price - past_price) / (past_price + EPSILON)
        )

    return result


def price_acceleration(df: pd.DataFrame, windows=(3, 5, 10, 30)) -> dict:
    """
    Short-window momentum compared against longer-window momentum.

    This is technically more of a momentum shift than true acceleration,
    but keeping the function name avoids breaking your existing code.
    """
    pv = price_velocity(df, windows)
    result = {}

    window_list = sorted(windows)

    for i in range(1, len(window_list)):
        short = window_list[i - 1]
        long = window_list[i]

        short_vel = pv[f"price_velocity_{short}s"]
        long_vel = pv[f"price_velocity_{long}s"]

        result[f"price_acceleration_{short}s_{long}s"] = float(short_vel - long_vel)

    return result


def buy_sell_ratio(df: pd.DataFrame, windows=(1, 3, 5, 10, 30)) -> dict:
    """
    Stable buy/sell volume ratio.

    Instead of raw:
        buy_volume / sell_volume

    this uses:
        log1p(buy_volume) - log1p(sell_volume)

    Positive means buy-heavy.
    Negative means sell-heavy.
    Zero means neutral.
    """
    result = {}
    now = df["timestamp"].iloc[-1]

    for w in windows:
        cutoff = now - pd.Timedelta(seconds=w)
        subset = df[df["timestamp"] >= cutoff]

        buy_vol = subset[subset["trade_type"] == "buy"]["amount_usd"].sum()
        sell_vol = subset[subset["trade_type"] == "sell"]["amount_usd"].sum()

        result[f"buy_sell_ratio_{w}s"] = float(np.log1p(buy_vol) - np.log1p(sell_vol))

    return result


def net_buy_pressure(df: pd.DataFrame, windows=(1, 3, 5, 10, 30)) -> dict:
    """
    (buy_volume - sell_volume) / total_volume

    Range: -1 to +1.
    """
    result = {}
    now = df["timestamp"].iloc[-1]

    for w in windows:
        cutoff = now - pd.Timedelta(seconds=w)
        subset = df[df["timestamp"] >= cutoff]

        buy_vol = subset[subset["trade_type"] == "buy"]["amount_usd"].sum()
        sell_vol = subset[subset["trade_type"] == "sell"]["amount_usd"].sum()
        total_vol = buy_vol + sell_vol

        result[f"net_buy_pressure_{w}s"] = float(
            (buy_vol - sell_vol) / (total_vol + EPSILON)
        ) if total_vol > 0 else 0.0

    return result


def volatility(df: pd.DataFrame, windows=(5, 10, 30, 60)) -> dict:
    """
    Standard deviation of returns over recent time windows.
    """
    result = {}
    now = df["timestamp"].iloc[-1]

    for w in windows:
        cutoff = now - pd.Timedelta(seconds=w)
        subset = df[df["timestamp"] >= cutoff]

        if len(subset) < 2:
            result[f"volatility_{w}s"] = 0.0
            continue

        returns = subset["market_cap"].pct_change().replace([np.inf, -np.inf], np.nan).dropna()

        result[f"volatility_{w}s"] = float(returns.std()) if len(returns) > 0 else 0.0

    return result


def tpm(df: pd.DataFrame, windows=(1, 3, 5, 10, 30)) -> dict:
    """
    Trades per second over rolling windows.

    Keeping the function name as tpm because that is what you already had,
    but the actual feature names are tps.
    """
    result = {}
    now = df["timestamp"].iloc[-1]

    for w in windows:
        cutoff = now - pd.Timedelta(seconds=w)
        subset = df[df["timestamp"] >= cutoff]

        result[f"tps_{w}s"] = float(len(subset) / w) if w > 0 else 0.0

    return result


def drawdown_from_high(df: pd.DataFrame, windows=(5, 10, 30, 60)) -> dict:
    """
    (current_price - recent_high) / recent_high

    Usually <= 0.
    """
    result = {}
    now = df["timestamp"].iloc[-1]
    current_price = float(df["market_cap"].iloc[-1])

    for w in windows:
        cutoff = now - pd.Timedelta(seconds=w)
        subset = df[df["timestamp"] >= cutoff]

        if subset.empty:
            result[f"drawdown_{w}s"] = 0.0
            continue

        high = float(subset["market_cap"].max())

        if high <= 0:
            result[f"drawdown_{w}s"] = 0.0
            continue

        result[f"drawdown_{w}s"] = float((current_price - high) / (high + EPSILON))

    return result


def default_features() -> dict:
    """
    Return the same feature columns even when there is no usable data.

    This is important for ML because your model expects a consistent input shape.
    """
    features = {}

    features["ema_5"] = 0.0
    features["ema_10"] = 0.0
    features["sma_5"] = 0.0
    features["sma_10"] = 0.0

    features.update({
        "macd_line": 0.0,
        "macd_signal": 0.0,
        "macd_histogram": 0.0,
    })

    features["rsi"] = 50.0

    for w in (1, 3, 5, 10, 30):
        features[f"trade_imbalance_{w}s"] = 0.0

    for w in (3, 5, 10, 30):
        features[f"volume_velocity_{w}s"] = 0.0

    for w in (1, 3, 5, 10, 15, 30, 60, 120, 240):
        features[f"price_velocity_{w}s"] = 0.0

    for short, long in ((3, 5), (5, 10), (10, 30)):
        features[f"price_acceleration_{short}s_{long}s"] = 0.0

    for w in (1, 3, 5, 10, 30):
        features[f"buy_sell_ratio_{w}s"] = 0.0

    for w in (1, 3, 5, 10, 30):
        features[f"net_buy_pressure_{w}s"] = 0.0

    for w in (5, 10, 30, 60):
        features[f"volatility_{w}s"] = 0.0

    for w in (1, 3, 5, 10, 30):
        features[f"tps_{w}s"] = 0.0

    for w in (5, 10, 30, 60):
        features[f"drawdown_{w}s"] = 0.0

    return features


def clean_input_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize input data before computing features.
    """
    required_columns = {
        "timestamp",
        "market_cap",
        "amount_usd",
        "trade_type",
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df = df.copy()

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["market_cap"] = pd.to_numeric(df["market_cap"], errors="coerce")
    df["amount_usd"] = pd.to_numeric(df["amount_usd"], errors="coerce")

    df["trade_type"] = df["trade_type"].astype(str).str.lower().str.strip()

    df = df.dropna(subset=["timestamp", "market_cap", "amount_usd"])
    df = df[df["market_cap"] > 0]
    df = df[df["amount_usd"] >= 0]

    df = df.sort_values("timestamp").reset_index(drop=True)

    return df


def compute_features(df: pd.DataFrame) -> dict:
    """
    Compute all features for a trade-window DataFrame.

    Returns a flat dict:
        feature_name -> value

    Use this identically in both train.py and predict_confidence().
    """
    base = default_features()

    if df is None or df.empty:
        return base

    df = clean_input_df(df)

    if df.empty:
        return base

    prices = df["market_cap"]

    features = {}

    # Traditional price indicators
    features["ema_5"] = ema(prices, 5)
    features["ema_10"] = ema(prices, 10)
    features["sma_5"] = sma(prices, 5)
    features["sma_10"] = sma(prices, 10)
    features.update(macd(prices))
    features["rsi"] = rsi(prices)

    # Trade-flow and window-based indicators
    features.update(trade_imbalance(df))
    features.update(volume_velocity(df))
    features.update(price_velocity(df))
    features.update(price_acceleration(df))
    features.update(buy_sell_ratio(df))
    features.update(net_buy_pressure(df))
    features.update(volatility(df))
    features.update(tpm(df))
    features.update(drawdown_from_high(df))

    # Guarantee the same keys every time.
    base.update(features)

    # Final safety cleanup.
    for key, value in base.items():
        if value is None or pd.isna(value) or np.isinf(value):
            base[key] = 0.0
        else:
            base[key] = float(value)

    return base