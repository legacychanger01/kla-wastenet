"""
KLA WasteNet Pro — Wait for DB management command
Used to wait for the database to be ready before starting the app
"""
import time
import logging
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Waits for the database to be available before starting the app'

    def add_arguments(self, parser):
        parser.add_argument('--max-retries', type=int, default=30)
        parser.add_argument('--delay', type=float, default=2.0)

    def handle(self, *args, **options):
        max_retries = options['max_retries']
        delay = options['delay']
        self.stdout.write('⏳ Waiting for database…')

        for attempt in range(1, max_retries + 1):
            try:
                connections['default'].ensure_connection()
                self.stdout.write(self.style.SUCCESS(
                    f'✅ Database ready after {attempt} attempt(s)'
                ))
                return
            except OperationalError:
                self.stdout.write(f'   Attempt {attempt}/{max_retries}: DB not ready, retrying in {delay}s…')
                time.sleep(delay)

        self.stderr.write(self.style.ERROR(
            f'❌ Database not available after {max_retries} attempts. Giving up.'
        ))
        raise SystemExit(1)
