from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.utils import translation
from django.utils.translation import get_supported_language_variant
from django.utils.translation.trans_real import parse_accept_lang_header
from django.views.decorators.http import require_POST
from wagtail.models import Site


def _language_for_root(request):
    """
    Choose the language to send a visitor of the bare site root ("/") to.

    Precedence mirrors Django's ``get_language_from_request`` but with a
    configurable fallback (``settings.ROOT_DEFAULT_LANGUAGE``) instead of
    ``LANGUAGE_CODE``:

    1. A language the visitor previously chose, stored in the language cookie
       by :func:`switch_language`.
    2. The best supported match for the browser's ``Accept-Language`` header.
    3. ``settings.ROOT_DEFAULT_LANGUAGE`` when nothing above matches a
       supported locale.
    """
    cookie = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
    if cookie:
        try:
            return get_supported_language_variant(cookie)
        except LookupError:
            pass

    accept = request.META.get("HTTP_ACCEPT_LANGUAGE", "")
    for accept_lang, _ in parse_accept_lang_header(accept):
        if accept_lang == "*":
            break
        try:
            return get_supported_language_variant(accept_lang)
        except LookupError:
            continue

    return getattr(settings, "ROOT_DEFAULT_LANGUAGE", settings.LANGUAGE_CODE)


def root_redirect(request):
    """
    Redirect the bare site root ("/") to the language-prefixed home page,
    picking the language from the visitor's cookie / browser preference.

    Only the bare "/" reaches this view; any URL that already carries a
    language prefix is served by ``i18n_patterns`` and is left untouched.
    """
    target = f"/{_language_for_root(request)}/"
    query = request.META.get("QUERY_STRING", "")
    if query:
        target = f"{target}?{query}"
    return redirect(target)


@require_POST
def switch_language(request):
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"
    lang_code = request.POST.get("language")
    if not lang_code:
        return redirect(next_url)

    # Activate and store
    translation.activate(lang_code)
    if hasattr(request, "session"):
        # Явно используем ключ, который читает LocaleMiddleware
        request.session['django_language'] = lang_code

    # Rewrite URL prefix to selected lang
    parts = urlsplit(next_url)
    path = parts.path or "/"

    if path == "/":
        new_path = f"/{lang_code}/"
    else:
        segments = [seg for seg in path.split("/") if seg != ""]
        if segments and segments[0] in {"en", "ru", "ja"}:
            segments[0] = lang_code
            new_path = "/" + "/".join(segments) + ("/" if path.endswith("/") else "")
        else:
            new_path = f"/{lang_code}{path if path.startswith('/') else '/' + path}"

    new_url = urlunsplit((parts.scheme, parts.netloc, new_path, parts.query, parts.fragment))

    # Response + cookie
    if not parts.scheme and not parts.netloc:
        response = redirect(new_path + ("?" + parts.query if parts.query else ""))
    else:
        response = HttpResponseRedirect(new_url)

    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang_code)
    return response


def robots_txt(request):
    site = Site.find_for_request(request)
    base_url = site.root_url if site else settings.WAGTAILADMIN_BASE_URL

    lines = [
        "User-agent: *",
        "Allow: /",
        "",
        "# Admin and internal paths",
        "Disallow: /admin/",
        "Disallow: /django-admin/",
        "Disallow: /documents/",
        "Disallow: /search/",
        "",
        "# AI scrapers",
        "User-agent: GPTBot",
        "Disallow: /",
        "",
        "User-agent: ChatGPT-User",
        "Disallow: /",
        "",
        "User-agent: ClaudeBot",
        "Disallow: /",
        "",
        "User-agent: CCBot",
        "Disallow: /",
        "",
        "User-agent: ByteSpider",
        "Disallow: /",
        "",
        f"Sitemap: {base_url}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


