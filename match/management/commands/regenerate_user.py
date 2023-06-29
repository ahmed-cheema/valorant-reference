from django.core.management.base import BaseCommand
from match.models import Player, User

class Command(BaseCommand):
    help = 'Regenerate User model'

    def handle(self, *args, **kwargs):

        team_a_players = Player.objects.filter(Team='Team A').values('Username').distinct()

        # Create a new User for each unique username
        for player in team_a_players:
            username = player['Username']
            displayname, tag = username.split('#')

            User.objects.get_or_create(
                Username=username,
                defaults={
                    'DisplayName': displayname,
                    'UserTag': tag
                }
            )

        self.stdout.write(self.style.SUCCESS("Successfully regenerated User model"))