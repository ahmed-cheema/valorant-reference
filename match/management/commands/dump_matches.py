from django.core.management.base import BaseCommand
from match.models import Match

class Command(BaseCommand):
    help = 'Dump list of match IDs to aid mass refresh'

    def handle(self, *args, **kwargs):

        match_ids = [m["MatchID"] for m in Match.objects.all().values("MatchID")]
        print(' '.join(['"{}"'.format(s) for s in match_ids]))

        print("\n{} total matches dumped".format(len(match_ids)))