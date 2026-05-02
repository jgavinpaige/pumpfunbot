from django.core.management.base import BaseCommand
import asyncio
import threading

class Command(BaseCommand):
    help = 'Run daphne and scraper together'

    def handle(self, *args, **kwargs):
        # Start scraper in background thread
        def run_scraper():
            asyncio.run(__import__('scanner.scraper', fromlist=['main']).main())

        thread = threading.Thread(target=run_scraper, daemon=True)
        thread.start()

        # Run daphne in main thread
        from daphne.cli import CommandLineInterface
        CommandLineInterface().run([
            '-b', '0.0.0.0',
            '-p', '8000',
            'pumpinterface.asgi:application'
        ])