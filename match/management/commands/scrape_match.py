from django.shortcuts import render, get_object_or_404
from django.core.management.base import BaseCommand
from django.utils import timezone
from match.models import Match, Player
from match.scraper import ScrapeMatch
from match.views import match_detail

class Command(BaseCommand):
    help = 'Scrape match data and add it to the database'

    def add_arguments(self, parser):
        parser.add_argument('match_ids', nargs='+', type=str)

    def handle(self, *args, **kwargs):
        match_ids = kwargs['match_ids']

        for match_id in match_ids:
            try:
                ScrapeMatch(match_id)
            except SystemExit as e:
                print(e)
                continue

            # get the scraped match from the database
            match = get_object_or_404(Match, MatchID=match_id)

            # get the players for the scraped match
            #players = Player.objects.filter(Match=match)

            self.stdout.write(self.style.SUCCESS(f'Successfully scraped data for match {match_id}!'))