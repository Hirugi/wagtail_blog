from django.conf import settings
from django.dispatch import receiver
from django.urls import path
from django.utils.safestring import mark_safe
from wagtail import hooks
from wagtail.models import Revision
from wagtail.signals import copy_for_translation_done

from home import translation_views
from home.ai_translation import translate_text
from home.models import BlogPage, TranslationSettings


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

@receiver(copy_for_translation_done)
def auto_translate_on_copy(sender, source_obj, target_obj, **kwargs):
    """
    Auto-translate when Wagtail copies a page for translation.

    Only translates the title (single API call) and sets the
    default disclaimer — keeps the HTTP request well under the gunicorn
    worker timeout. Body blocks are translated on-demand via the manual
    Translation tools panel.
    """

    if not isinstance(target_obj, BlogPage):
        return

    ts = TranslationSettings.objects.first()
    if not ts or not ts.api_key:
        return

    if not ts.source_locale or target_obj.locale == ts.source_locale:
        return

    lang_config = ts.language_configs.filter(locale=target_obj.locale).first()
    if not lang_config or not lang_config.system_prompt:
        return

    # Use the truly latest revision bypassing has_unpublished_changes check
    latest = (
        Revision.objects
        .filter(
            base_content_type=source_obj.get_base_content_type(),
            object_id=str(source_obj.pk),
        )
        .order_by('-created_at')
        .first()
    )
    source = latest.as_object() if latest else source_obj.specific

    try:
        target_obj.title = translate_text(
            source.title, lang_config.system_prompt,
            ts.provider, ts.api_key, ts.model, ts.base_url,
        )

        if lang_config.default_disclaimer:
            target_obj.disclaimer = lang_config.default_disclaimer

        target_obj.save_revision(changed=True, clean=False)
    except Exception:
        pass  # never interrupt the copy process
