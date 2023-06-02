from django import template
from django.template.loader import render_to_string

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.simple_tag(takes_context=True)
def active_streak_element(context, streak):
    return render_to_string('match/recordbook/active_streak_element.html', {'streak': streak})

@register.simple_tag(takes_context=True)
def streak_element(context, streak):
    return render_to_string('match/recordbook/streak_element.html', {'streak': streak})

@register.simple_tag
def game_element(game, FloatCount):
    return render_to_string('match/recordbook/game_element.html', {'game': game,
                                                                   'FloatCount': FloatCount})

@register.simple_tag(takes_context=True)
def match_element(context, game):
    return render_to_string('match/recordbook/match_element.html', {'game': game})

@register.simple_tag
def career_element(record, FloatCount, superlative, varName):
    return render_to_string('match/recordbook/career_element.html', {'record': record,
                                                                     'FloatCount': FloatCount,
                                                                     'superlative': superlative,
                                                                     'varName': varName})