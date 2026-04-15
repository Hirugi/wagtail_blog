import re

from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.safestring import mark_safe
from wagtail.admin.panels import Panel

_FALLBACK_SOURCE_LANG = 'ru'


class TranslationToolsPanel(Panel):
    """
    Admin panel that shows per-field and per-block AI translation buttons.
    Only visible when editing a non-source-language page.
    """

    class BoundPanel(Panel.BoundPanel):

        @staticmethod
        def _source_language():
            try:
                from home.models import TranslationSettings
                ts = TranslationSettings.objects.select_related('source_locale').first()
                if ts and ts.source_locale:
                    return ts.source_locale.language_code
            except Exception:
                pass
            return _FALLBACK_SOURCE_LANG

        def _can_translate(self):
            if not self.instance or not self.instance.pk:
                return False
            locale = getattr(self.instance, 'locale', None)
            if not locale:
                return False
            return locale.language_code != self._source_language()

        def render_html(self, *_, **__):
            if not self._can_translate():
                return mark_safe('')

            base_url = reverse('wagtail_ai_translate')
            page = self.instance

            field_items = [
                {
                    'label': 'Title',
                    'url': f'{base_url}?page_id={page.pk}&field=title',
                    'ai': True,
                },
                {
                    'label': 'Disclaimer',
                    'url': f'{base_url}?page_id={page.pk}&field=disclaimer',
                    'ai': False,
                    'note': 'sets default from settings',
                },
            ]

            blocks = []
            if hasattr(page, 'body'):
                for i, block_data in enumerate(page.body.raw_data):
                    if block_data['type'] not in ('rich_text', 'html'):
                        continue
                    raw = str(block_data.get('value', ''))
                    preview = re.sub(r'<[^>]+>', '', raw)[:120].strip() or '—'
                    blocks.append({
                        'num': i + 1,
                        'type': block_data['type'],
                        'preview': preview,
                        'url': f'{base_url}?page_id={page.pk}&field=body&block_index={i}',
                    })

            context = {
                'field_items': field_items,
                'blocks': blocks,
                'translate_all_url': f'{base_url}?page_id={page.pk}&field=body',
            }

            return mark_safe(render_to_string(
                'home/panels/translation_tools.html',
                context,
                request=self.request,
            ))
