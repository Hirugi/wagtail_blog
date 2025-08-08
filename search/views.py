from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.template.response import TemplateResponse

from wagtail.models import Page, Locale

# To enable logging of search queries for use with the "Promoted search results" module
# <https://docs.wagtail.org/en/stable/reference/contrib/searchpromotions.html>
# uncomment the following line and the lines indicated in the search function
# (after adding wagtail.contrib.search_promotions to INSTALLED_APPS):

# from wagtail.contrib.search_promotions.models import Query


def search(request):
    search_query = request.GET.get("query", None)
    page = request.GET.get("page", 1)

    lang_code = getattr(request, "LANGUAGE_CODE", "en")
    locale = None
    try:
        locale = Locale.objects.get(language_code=lang_code)
    except Locale.DoesNotExist:
        pass

    # Base queryset limited by locale at DB level
    base_qs = Page.objects.live()
    if locale:
        base_qs = base_qs.filter(locale_id=locale.id)

    # Search
    if search_query:
        search_results = base_qs.search(search_query)
        # query = Query.get(search_query); query.add_hit()
    else:
        search_results = Page.objects.none()

    # Pagination
    paginator = Paginator(search_results, 10)
    try:
        search_results = paginator.page(page)
    except PageNotAnInteger:
        search_results = paginator.page(1)
    except EmptyPage:
        search_results = paginator.page(paginator.num_pages)

    return TemplateResponse(
        request,
        "search/search.html",
        {
            "search_query": search_query,
            "search_results": search_results,
        },
    )
