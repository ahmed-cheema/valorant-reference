from django import template
from django.template.loader import render_to_string

register = template.Library()

@register.simple_tag
def match_box(Match, Name):
    return render_to_string('match/match_box.html', {'Match': Match, 'Name': Name})