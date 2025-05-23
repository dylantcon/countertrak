from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary using key.
    Usage: {{ dict|get_item:key }}
    """
    return dictionary.get(key, 0)