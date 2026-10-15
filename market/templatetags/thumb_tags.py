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


def _slugify(raw):
    slug = []
    prev_dash = False
    for ch in (raw or "").lower():
        if ch.isalnum():
            slug.append(ch)
            prev_dash = False
        elif not prev_dash:
            slug.append("-")
            prev_dash = True
    return "".join(slug).strip("-")


def _photo_slug(make, model_name):
    return _slugify(f"{make or ''}-{model_name or ''}")


def _catalog_url(*candidates):
    for relative in candidates:
        if relative and finders.find(relative):
            return static(relative)
    return static("img/listings/honda-beat.jpg")


@register.simple_tag
def listing_photo(motorcycle):
    """Uploaded listing photo, otherwise the catalog photo for that model."""
    image = getattr(motorcycle, "image", None)
    if image:
        url = thumb(image, "800x600")
        if url:
            return url

    make = getattr(motorcycle, "make", "") or ""
    model_name = getattr(motorcycle, "model_name", "") or ""
    title = getattr(motorcycle, "title", "") or ""

    candidates = [
        f"img/listings/{_photo_slug(make, model_name)}.jpg",
        f"img/listings/{_slugify(title)}.jpg",
    ]
    # Strip leading year from titles like "2021 Kawasaki Ninja 250"
    parts = title.split(None, 1)
    if parts and parts[0].isdigit() and len(parts) > 1:
        candidates.append(f"img/listings/{_slugify(parts[1])}.jpg")

    return _catalog_url(*candidates)
