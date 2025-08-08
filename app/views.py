from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.utils import translation
from django.views.decorators.http import require_POST


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


