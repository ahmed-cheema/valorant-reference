from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from match.models import Match, Player

class Command(BaseCommand):
    help = 'Remove match and player data from the database'

    def add_arguments(self, parser):
        parser.add_argument('match_ids', nargs='+', type=str)

    def handle(self, *args, **kwargs):
        match_ids = kwargs['match_ids']
        for match_id in match_ids:
            try:
                match = Match.objects.get(MatchID=match_id)
                players = Player.objects.filter(Match=match)
                players.delete()
                match.delete()
                self.stdout.write(self.style.SUCCESS(f'Successfully removed match {match_id} and related data!'))
            except ObjectDoesNotExist:
                self.stdout.write(self.style.ERROR(f'Match with ID {match_id} does not exist!'))