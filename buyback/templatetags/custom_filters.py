from django import template
  
register = template.Library()
  
@register.filter()
def low(value):
    return value.lower()

@register.filter(name='add_commas')
def add_commas(value):
    try:
        value = int(value)
        return '{:,}'.format(value)
    except (ValueError, TypeError):
        return value