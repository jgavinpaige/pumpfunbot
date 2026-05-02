from pathlib import Path
import sqlite3
import pandas as pd
from indicators import compute_features

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, RandomizedSearchCV
from sklearn.metrics import classification_report

import pickle

base_dir = Path(__file__).resolve().parent.parent.parent

X = []
y = []

def main():
    global X, y
    print("Loading database...")
    conn = sqlite3.connect(base_dir / 'data' / 'trades.db')

    df_all = pd.read_sql("""
        SELECT mint_address, timestamp, market_cap, amount_usd, type 
        FROM trades 
        ORDER BY mint_address, timestamp ASC
    """, conn)

    df_all['timestamp'] = pd.to_datetime(df_all['timestamp'], utc=True)
    df_all = df_all.rename(columns={'type': 'trade_type'})

    groups = df_all.groupby('mint_address')
    print(f"Total tokens: {len(groups)}")

    skipped = 0
    processed = 0
    for i, (mint, df) in enumerate(groups, 1):
        lifespan = (df['timestamp'].max() - df['timestamp'].min()).total_seconds() / 60
        if lifespan < 15 or len(df) < 20:
            skipped += 1
            continue
        train(df)
        processed += 1
        if processed % 100 == 0:
            print(f"Processed {processed} tokens, {len(X)} windows so far...")

    print(f"Done — {processed} tokens processed, {skipped} skipped")

    X_arr = np.array(X)
    y_arr = np.array(y)

    print(f"Dataset: {len(X_arr)} examples, {y_arr.sum()} positive ({y_arr.mean()*100:.1f}%)")

    X_train, X_test, y_train, y_test = train_test_split(X_arr, y_arr, test_size=0.2, random_state=42)

    print("Training model...")
   
    param_grid = {
        'n_estimators': [100, 200, 300],
        'max_depth': [None, 10, 20, 30],
        'min_samples_split': [2, 5, 10],
        'min_samples_leaf': [1, 2, 4],
        'class_weight': ['balanced', {0: 1, 1: 2}, {0: 1, 1: 3}],
    }

    search = RandomizedSearchCV(
        RandomForestClassifier(random_state=42),
        param_distributions=param_grid,
        n_iter=50,           # try 50 random combinations
        cv=5,                # 5-fold cross validation
        scoring='f1',        # optimize for f1 on class 1
        n_jobs=-1,           # use all CPU cores
        random_state=42,
        verbose=2
    )

    search.fit(X_train, y_train)

    print(f"Best params: {search.best_params_}")
    model = search.best_estimator_
    print(classification_report(y_test, model.predict(X_test)))

    print("Training complete")

    # get feature names from a sample compute_features call
    sample_features = compute_features(df_all.iloc[:10].copy())
    feature_names = list(sample_features.keys())
    
    print("\nFeature importances:")
    for name, imp in sorted(zip(feature_names, model.feature_importances_), key=lambda x: -x[1])[:15]:
        print(f"  {name}: {imp:.3f}")

    print("\n" + classification_report(y_test, model.predict(X_test)))

    with open(base_dir / 'data' / 'model.pkl', 'wb') as f:
        pickle.dump(model, f)

    print("Model saved to model.pkl")

def train(df):
    window_size = pd.Timedelta(minutes=5)
    lookahead_size = pd.Timedelta(minutes=10)
    step = pd.Timedelta(minutes=5)

    start = df['timestamp'].iloc[0]
    end = df['timestamp'].iloc[-1]

    current = start
    while current + window_size + lookahead_size <= end:
        window = df[(df['timestamp'] >= current) & (df['timestamp'] < current + window_size)]
        lookahead = df[(df['timestamp'] >= current + window_size) & (df['timestamp'] < current + window_size + lookahead_size)]
        
        if len(window) >= 5 and len(lookahead) >= 2:
            features = compute_features(window)
            label = 1 if lookahead['market_cap'].max() >= window['market_cap'].iloc[-1] * 1.2 else 0
            X.append(list(features.values()))
            y.append(int(label))
        
        current += step

if __name__ == '__main__':
    main()