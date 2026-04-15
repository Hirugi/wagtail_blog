from django.conf import settings
from django.urls import path
from django.utils.safestring import mark_safe
from wagtail import hooks

from home import translation_views


@hooks.register('register_admin_urls')
def register_translation_urls():
    return [
        path('ai-translate/', translation_views.ai_translate_view, name='wagtail_ai_translate'),
    ]


@hooks.register('insert_global_admin_css')
def translation_tools_css():
    return mark_safe(
        f'<link rel="stylesheet" href="{settings.STATIC_URL}css/translation_tools.css">'
    )
