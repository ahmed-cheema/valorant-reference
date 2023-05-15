from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from match.models import Match, Player
import json

class Command(BaseCommand):
    help = 'Change a player\'s name in the database'

    def add_arguments(self, parser):
        parser.add_argument('old_name', nargs=1, type=str)
        parser.add_argument('new_name', nargs=1, type=str)

    def handle(self, *args, **kwargs):

        ### INITIALIZE VARIABLES

        old_name = kwargs['old_name'][0]
        new_name = kwargs['new_name'][0]

        old_display = old_name.split("#")[0]
        new_display = new_name.split("#")[0]

        ### FIX PLAYER OBJECT FIELDS
        
        for p in Player.objects.filter(Username = old_name):
            p.Username = new_name
            p.DisplayName = new_display
            p.save()

        ### FIX MATCH OBJECT FIELDS

        format1 = "{}, " 
        format2 = ", {}," 
        format3 = ", {}" 

        for m in Match.objects.filter(Players__contains = old_display):
            ## replace user in Players field
            players = m.Players
            if players.startswith(format1.format(old_display)):
                m.Players = players.replace(format1.format(old_display),
                                             format1.format(new_display))
            elif format2.format(old_display) in players:
                m.Players = players.replace(format2.format(old_display),
                                             format2.format(new_display))
            elif players.endswith(format3.format(old_display)):
                m.Players = players.replace(format3.format(old_display),
                                             format3.format(new_display))
            else:
                continue

            ## re-sort the Players field
            players_str = [s.strip() for s in m.Players.split(',')]
            sorted_players = ', '.join(sorted(players_str, key=str.lower))
            m.Players = sorted_players

            ## update individual player fields
            if m.MVP == old_display:
                m.MVP = new_display
            if m.TopKiller == old_display:
                m.TopKiller = new_display
            if m.TopKDR == old_display:
                m.TopKDR = new_display

            m.save()

        ### UPDATE LIST OF SQUAD TEAMMATES

        with open('match/squad.json', 'r') as f:
            usernames = json.load(f)

        try:
            index = usernames.index(old_name)
            usernames[index] = new_name
        except ValueError:
            self.stderr.write(f'{old_name} not found in squad.json')

        with open('match/squad.json', 'w') as f:
            json.dump(usernames, f)

        ### OUTPUT PRINT

        print("Username update was successful:")
        print("{} -> {}".format(old_name, new_name))

        for m in Match.objects.all():
