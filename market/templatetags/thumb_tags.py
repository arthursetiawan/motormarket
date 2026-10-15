from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static
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


def _photo_slug(make, model_name):
    raw = f"{make or ''}-{model_name or ''}".lower()
    slug = []
    prev_dash = False
    for ch in raw:
        if ch.isalnum():
            slug.append(ch)
            prev_dash = False
        elif not prev_dash:
            slug.append("-")
            prev_dash = True
    return "".join(slug).strip("-")


@register.simple_tag
def listing_photo(motorcycle):
    """Uploaded listing photo, otherwise the catalog photo for that model."""
    image = getattr(motorcycle, "image", None)
    if image:
        url = thumb(image, "800x600")
        if url:
            return url
    slug = _photo_slug(getattr(motorcycle, "make", ""), getattr(motorcycle, "model_name", ""))
    relative = f"img/listings/{slug}.jpg"
    if not finders.find(relative):
        relative = "img/listings/honda-beat.jpg"
    return static(relative)
