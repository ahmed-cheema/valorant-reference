from django.core.management.base import BaseCommand
from django.core.cache import cache

class Command(BaseCommand):
    help = 'Clears the cache'

    def handle(self, *args, **options):
        cache.set('test_key', 'test_value')
        print(cache.get('test_key'))  # Should print 'test_value'
        cache.clear()
        print(cache.get('test_key'))  # Should print None