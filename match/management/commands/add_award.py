from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from datetime import datetime

from match.models import User, Award

class Command(BaseCommand):
    help = 'Create an award and assign it to a user'

    def add_arguments(self, parser):
        parser.add_argument('Username', type=str)
        parser.add_argument('Name', type=str)
        parser.add_argument('StartDate', type=str)
        parser.add_argument('EndDate', type=str)

    def handle(self, *args, **kwargs):
        username = kwargs['Username']
        name = kwargs['Name']
        start_date = datetime.strptime(kwargs['StartDate'], "%m/%d/%Y")
        end_date = datetime.strptime(kwargs['EndDate'], "%m/%d/%Y")

        try:
            user = User.objects.get(Username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User '{username}' does not exist."))
            return

        award = Award.objects.create(Name=name, StartDate=start_date, EndDate=end_date)
        user.Awards.add(award)

        self.stdout.write(self.style.SUCCESS(f"Award '{name}' successfully added to user '{username}'."))
