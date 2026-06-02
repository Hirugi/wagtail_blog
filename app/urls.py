from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.contrib.sitemaps.views import sitemap
from wagtail.documents import urls as wagtaildocs_urls

from search import views as search_views
from . import views as app_views

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("set-language/", app_views.switch_language, name="set_language"),
    path("robots.txt", app_views.robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap, name="sitemap"),
    # At the root, select the locale based on the browser language (with a fallback to ROOT_DEFAULT_LANGUAGE).
    # URLs with a language prefix are not included here - they are served by i18n_patterns below.
    path("", app_views.root_redirect, name="root"),
]

urlpatterns += i18n_patterns(
    path("admin/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("search/", search_views.search, name="search"),
    path("", include(wagtail_urls)),
)

if settings.DEBUG:
    from django.conf.urls.static import static
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    # Serve static and media files from development server
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
