from django.db import models

class Token(models.Model):
    mint_address = models.CharField(max_length=100, unique=True)
    symbol = models.CharField(max_length=50)
    first_seen = models.DateTimeField(auto_now_add=True)
    confidence = models.FloatField(default=0)
    buy_signal = models.FloatField(default=0)
    sell_signal = models.FloatField(default=0)

class Trade(models.Model):
    token = models.ForeignKey(Token, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    trade_type = models.CharField(max_length=10)
    market_cap = models.FloatField()
    amount_usd = models.FloatField()
    price_usd = models.FloatField()
