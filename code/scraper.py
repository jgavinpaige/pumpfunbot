import websockets
import json
import sqlite3
import asyncio

from pathlib import Path
base_dir = Path(__file__).resolve().parent.parent

count = 0

conn = sqlite3.connect(base_dir / "data" / "live_session.db")
conn.execute("""
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        mint_address TEXT,
        symbol TEXT,
        type TEXT,
        market_cap REAL,
        amount_usd REAL,
        price_usd REAL
    )
""")
conn.commit()


async def stream():
    uri = "wss://unified-prod.nats.realtime.pump.fun"
    
    async with websockets.connect(
        uri,
        additional_headers={"Origin": "https://pump.fun"}
    ) as ws:
        await ws.recv()  # INFO frame
        
        await ws.send('CONNECT {"no_responders":true,"protocol":1,"verbose":false,"pedantic":false,"user":"subscriber","pass":"OX745xvUbNQMuFqV","lang":"nats.ws","version":"1.29.2","headers":true}\r\n')
        await ws.send("PING\r\n")
        await ws.recv()  # PONG
        
        await ws.send("SUB unifiedTradeEvent.processed.* 2\r\n")
        
        async for msg in ws:
            if isinstance(msg, bytes):
                msg = msg.decode('utf-8')
            if msg.startswith("MSG"):
                parts = msg.split("\n", 1)
                if len(parts) > 1:
                    try:
                        payload = json.loads(parts[1].strip().strip('"').replace('\\"', '"'))
                        
                        # Determine is coin is traded on pump.fun or not
                        isBondingCurve = payload['isBondingCurve'] if 'isBondingCurve' in payload else False
                        if isBondingCurve:
                            timestamp = payload['timestamp']
                            mint = payload['mintAddress']
                            symbol = payload['coinMeta']['symbol']
                            transation_type = payload['type']
                            market_cap = payload['marketCap']
                            amount = payload['amountUsd']
                            price = payload['priceUsd']

                            conn.execute("INSERT INTO trades " \
                            "(timestamp, mint_address, symbol, type, market_cap, amount_usd, price_usd) " \
                            "VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (timestamp, mint, symbol, transation_type, float(market_cap), float(amount), float(price)))
                            conn.commit()

                            count += 1
                            if(count % 500 == 0):
                                print(f"{count} trades collected")
                    except:
                        pass
            elif msg.startswith("PING"):
                await ws.send("PONG\r\n")

def run():
    asyncio.run(stream())

if __name__ == '__main__':
    run()