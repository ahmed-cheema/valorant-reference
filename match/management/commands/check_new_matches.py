from django.shortcuts import render, get_object_or_404
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone
from match.models import Match, Player
from match.scraper import GetNewMatches, ScrapeMatch
from match.views import match_detail

from django.core.cache import cache

class Command(BaseCommand):
    help = 'Scrape newest matches for player(s)'

    def add_arguments(self, parser):
        parser.add_argument('usernames', nargs='+', type=str)

    def handle(self, *args, **kwargs):
        usernames = kwargs['usernames']

        for username in usernames:
            new_match_ids = GetNewMatches(username)

            if len(new_match_ids) > 0:

                for match_id in new_match_ids:

                    try:
                        ScrapeMatch(match_id)
                        cache.clear()
                    except SystemExit as e:
                        print(e)
                        continue

                    # get the scraped match from the database
                    match = get_object_or_404(Match, MatchID=match_id)

                    # get the players for the scraped match
                    players = Player.objects.filter(Match=match)

                    self.stdout.write(self.style.SUCCESS(f'Successfully scraped data for match {match_id}!'))
            else:
                self.stdout.write("No new match IDs to scrape for {}".format(username))
                break