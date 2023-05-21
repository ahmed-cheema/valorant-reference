# In your app's templatetags folder, create a new Python file, e.g., custom_filters.py
from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def remove_slash(value):
    return value.replace('/', '')