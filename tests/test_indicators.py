# tests/test_indicators.py
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'code' / 'ml'))
from indicators import compute_features, ema, sma, rsi, macd

# Create fake trade data
df = pd.DataFrame({
    'timestamp': pd.date_range('2026-01-01', periods=50, freq='10s', tz='UTC'),
    'market_cap': [1000 + i*10 for i in range(50)],
    'amount_usd': [50.0] * 50,
    'trade_type': ['buy'] * 30 + ['sell'] * 20
})

features = compute_features(df)
assert len(features) == 52, f"Expected 52 features, got {len(features)}"
assert features['rsi'] >= 0 and features['rsi'] <= 100
assert features['trade_imbalance_30s'] >= -1 and features['trade_imbalance_30s'] <= 1
print(f"All tests passed — {len(features)} features computed")
print(f"RSI: {features['rsi']:.1f}")
print(f"EMA5: {features['ema_5']:.2f}")