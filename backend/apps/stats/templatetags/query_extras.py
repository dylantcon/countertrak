from django import template

register = template.Library()

@register.filter
def replace(value, arg):
    """
    Replace all occurrences of the first argument with the second argument.
    Usage: {{ value|replace:"_," " }}
    """
    if not arg or ',' not in arg:
        # Default to replacing underscores with spaces if no proper argument is provided
        return value.replace('_', ' ')
    
    what, to = arg.split(',', 1)
    return value.replace(what, to)
