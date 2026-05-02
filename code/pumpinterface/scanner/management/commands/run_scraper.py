from django.core.management.base import BaseCommand
import asyncio
from scanner.scraper import main

class Command(BaseCommand):
    help = 'Run the pump.fun scraper'

    def handle(self, *args, **kwargs):
        asyncio.run(main())