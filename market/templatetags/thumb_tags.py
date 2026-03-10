from django import template
from sorl.thumbnail import get_thumbnail

register = template.Library()


@register.simple_tag
def thumb(image, geometry='320x240'):
    if not image:
        return ''
    try:
        t = get_thumbnail(image, geometry, crop='center', quality=85)
        return t.url
    except Exception:
        return image.url
