from django import template

register = template.Library()

@register.filter
def int_divide(value, arg):
    try:
        return value // arg
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def calculate_percentage(value, total):
    try:
        return (value / total) * 100
    except (ValueError, ZeroDivisionError):
        return 0
