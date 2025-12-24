from datetime import date

from django import template
from django.utils.formats import date_format
from django.utils.html import strip_tags
from wagtail.models import Locale

register = template.Library()


@register.filter
def localized_snippet(obj, language_code: str):
    """Return translated snippet for the given language if it exists; otherwise the original.

    Works with Wagtail TranslatableMixin-based snippets (e.g., NavLink, SocialLink).
    """
    if obj is None or not language_code:
        return obj
    try:
        locale = Locale.objects.get(language_code=language_code)
    except Locale.DoesNotExist:
        return obj

    # Prefer get_translation_or_none if available
    try:
        translated = obj.get_translation_or_none(locale)
        return translated or obj
    except Exception:
        # Fallback to get_translation API if present
        try:
            return obj.get_translation(locale)
        except Exception:
            return obj


@register.filter
def page_model(obj):
    """Return model class name of a Wagtail Page in templates (safe, without __ access)."""
    try:
        specific_class = getattr(obj, "specific_class", None)
        return specific_class.__name__ if specific_class else ""
    except Exception:
        return ""


@register.filter
def translation_codes(page):
    """Return list of language codes available for the page translations (including current) without duplicates."""
    try:
        codes = [t.locale.language_code for t in page.get_translations().live()]
        current = getattr(getattr(page, "locale", None), "language_code", None)
        if current:
            codes.append(current)
        # uniq preserving order
        seen = set()
        uniq_codes = []
        for c in codes:
            if c and c not in seen:
                seen.add(c)
                uniq_codes.append(c)
        return uniq_codes
    except Exception:
        return []


@register.filter
def uniq(seq):
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


@register.filter
def lang_label(code: str) -> str:
    mapping = {
        'ru': 'Русский',
        'en': 'English',
        'ja': '日本語',
    }
    return mapping.get(code, (code or '').upper())


@register.filter
def post_excerpt(page, max_chars=200):
    """Get excerpt for BlogPage: first use search_description; else first rich_text block plain text.
    Usage: {{ page|post_excerpt:220 }}
    """
    try:
        # Prefer explicit search_description if present
        search_desc = getattr(page, 'search_description', '') or ''
        if search_desc:
            text = strip_tags(str(search_desc))
        else:
            body = getattr(page, 'body', None)
            text = ''
            if body:
                for child in body:
                    if getattr(child, 'block_type', '') == 'rich_text' and child.value:
                        text = strip_tags(str(child.value))
                        if text:
                            break
        text = (text or '').strip()
        if not text:
            return ''
        max_len = int(max_chars) if max_chars else 200
        if len(text) <= max_len:
            return text
        return text[:max_len].rstrip() + '…'
    except Exception:
        return ''


@register.filter
def exclude(seq, item):
    try:
        return [x for x in seq if x != item]
    except Exception:
        return seq


@register.filter
def month_name(month_number):
    """Return readable month name (e.g. January) for given month number, language aware."""
    try:
        month_number = int(month_number)
        d = date(2000, month_number, 1)
        return date_format(d, "F")
    except Exception:
        return ""
