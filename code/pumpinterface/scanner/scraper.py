import asyncio
import websockets
import json
from channels.layers import get_channel_layer
from django.utils.dateparse import parse_datetime
from .models import Token, Trade
import django
import os
from datetime import datetime, timedelta, timezone

from asgiref.sync import sync_to_async
from django.db.models import Count, Max, Q

import pandas as pd

import pickle
from pathlib import Path

import sys
from pathlib import Path

# Add the ml directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'ml'))
from indicators import compute_features

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pumpinterface.settings')
django.setup()

model_path = Path(__file__).resolve().parent.parent.parent.parent / 'data' / 'model.pkl'
with open(model_path, 'rb') as f:
    model = pickle.load(f)


channel_layer = get_channel_layer()

async def stream():
    uri = "wss://unified-prod.nats.realtime.pump.fun"

    # Clean up the DB for a fresh run
    await sync_to_async(lambda: Token.objects.all().delete())()

    while True:
        try:
            async with websockets.connect(
                uri,
                additional_headers={"Origin": "https://pump.fun"},
                ping_interval=None,
                ping_timeout=None
            ) as ws:
                await ws.recv()
                await ws.send('CONNECT {"no_responders":true,"protocol":1,"verbose":false,"pedantic":false,"user":"subscriber","pass":"OX745xvUbNQMuFqV","lang":"nats.ws","version":"1.29.2","headers":true}\r\n')
                await ws.send("PING\r\n")
                await ws.recv()
                await ws.send("SUB unifiedTradeEvent.processed.* 2\r\n")

                async for msg in ws:
                    if isinstance(msg, bytes):
                        msg = msg.decode('utf-8')

                    for chunk in msg.split("MSG ")[1:]:
                        try:
                            _, rest = chunk.split("\n", 1)
                            raw = rest.strip()
                            outer = json.loads(raw)
                            payload = json.loads(outer) if isinstance(outer, str) else outer

                            if not payload.get('isBondingCurve') or not payload.get('coinMeta'):
                                continue

                            mint = payload['mintAddress']
                            symbol = payload['coinMeta']['symbol']

                            # Save to Django DB
                            token, _ = await sync_to_async(Token.objects.get_or_create)(
                                mint_address=mint,
                                defaults={'symbol': symbol}
                            )

                            await sync_to_async(Trade.objects.create)(
                                token=token,
                                timestamp=parse_datetime(payload['timestamp']),
                                trade_type=payload['type'],
                                market_cap=float(payload['marketCap']),
                                amount_usd=float(payload['amountUsd']),
                                price_usd=float(payload['priceUsd']),
                            )

                            count = await sync_to_async(lambda: Trade.objects.filter(token=token).count())()
                            confidence = token.confidence  # use cached value by default
                            if (confidence > 60 or count % 5 == 0) and count >= 15:
                                confidence = await sync_to_async(predict_confidence)(token)
                                _pk = token.pk
                                _conf = confidence
                                await sync_to_async(lambda: Token.objects.filter(pk=_pk).update(confidence=_conf))()

                            await channel_layer.group_send("feed", {
                                "type": "trade.update",
                                "data": {
                                    "mint": mint,
                                    "symbol": symbol,
                                    "type": payload['type'],
                                    "market_cap": float(payload['marketCap']),
                                    "amount_usd": float(payload['amountUsd']),
                                    "price_usd": float(payload['priceUsd']),
                                    "timestamp": payload['timestamp'],
                                    "confidence": confidence
                                }
                            })

                        except Exception as e:
                            print(f"Error: {e}")

                    if "PING" in msg:
                        await ws.send("PONG\r\n")

        except Exception as e:
            print(f"Connection dropped: {e}, reconnecting in 5s...")
            await asyncio.sleep(5)

async def cleanup():
    while True:
        await asyncio.sleep(60)
        print("Cleanup running...")
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=45)

        # Get dead mints before deleting
        dead_mints = await sync_to_async(db_get_dead_mints)(cutoff=cutoff)

        # Delete them
        await sync_to_async(lambda: Token.objects.filter(mint_address__in=dead_mints).delete())()


        # Notify frontend
        for mint in dead_mints:
            await channel_layer.group_send("feed", {
                "type": "trade.update",
                "data": {"mint": mint, "remove": True}
            })

        print(f"Cleanup ran — removed {len(dead_mints)} tokens")


def db_get_dead_mints(cutoff, window_multiplier=5, min_rate=1.0):
    window_start = cutoff - timedelta(seconds=30 * window_multiplier)  # last 150s
    
    candidates = Token.objects.annotate(
        last_trade=Max('trade__timestamp'),
        recent_trades=Count('trade', filter=Q(trade__timestamp__gte=window_start)),
    ).filter(
        last_trade__lt=cutoff
    ).values('mint_address', 'recent_trades')

    window_seconds = 30 * window_multiplier
    dead = []
    for tok in candidates:
        rate = tok['recent_trades'] / window_seconds
        if rate < min_rate:
            dead.append(tok['mint_address'])
    
    return dead


def predict_confidence(token):
    trades = list(Trade.objects.filter(token=token).order_by('-timestamp')[:50].values(
        'trade_type', 'amount_usd', 'market_cap', 'timestamp'
    ))
    if len(trades) < 5:
        return 0.0
    
    df = pd.DataFrame(trades)
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    features = compute_features(df)
    feature_vector = [list(features.values())]
    
    prob = model.predict_proba(feature_vector)[0][1]
    return round(prob * 100, 1)


async def main():
    await asyncio.gather(
        stream(),
        cleanup()
    )