from django.contrib import messages
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext
from wagtail.models import Revision

from home.ai_translation import translate_text, TranslationError
from home.models import BlogPage, TranslationSettings


def ai_translate_view(request):
    if not request.user.is_authenticated or not request.user.has_perm('wagtailadmin.access_admin'):
        return HttpResponseForbidden()

    page_id = request.GET.get('page_id')
    field = request.GET.get('field')
    block_index_raw = request.GET.getlist('block_index')

    if not page_id or not field:
        return HttpResponseBadRequest("Missing parameters")

    page = get_object_or_404(BlogPage, pk=int(page_id))
    edit_url = reverse('wagtailadmin_pages:edit', args=[page.pk])

    ts = _get_translation_settings(request)
    if not ts:
        messages.error(request, gettext("Translation settings not configured. Go to Settings → Translation settings."))
        return redirect(edit_url)

    # Start from the latest draft of the TARGET page, so we preserve
    # any other edits and create a proper revision.
    target_draft = _get_latest_draft(page)

    # Disclaimer: no AI needed, just set the configured default
    if field == 'disclaimer':
        lang_config = ts.language_configs.filter(locale=page.locale).first()
        if lang_config and lang_config.default_disclaimer:
            target_draft.disclaimer = lang_config.default_disclaimer
            target_draft.save_revision(
                user=request.user, changed=True, log_action=True, clean=False,
            )
            messages.success(request, gettext("Disclaimer set from default."))
        else:
            messages.warning(request, gettext("No default disclaimer configured for this language."))
        return redirect(edit_url)

    # All other fields need AI → require an API key
    if not ts.api_key:
        messages.error(request, gettext("API key not configured in Translation settings."))
        return redirect(edit_url)

    # All other fields require the source page
    source_locale = ts.source_locale
    if not source_locale:
        messages.error(request, gettext("Source language not configured in Translation settings."))
        return redirect(edit_url)
    try:
        source_page_live = page.get_translation(source_locale)
        source_page = _get_latest_draft(source_page_live)
    except Exception:
        msg = gettext("Source page not found for locale")
        messages.error(request, f"{msg} {source_locale}")
        return redirect(edit_url)

    lang_config = ts.language_configs.filter(locale=page.locale).first()
    system_prompt = lang_config.system_prompt if lang_config else ''

    def _translate(text):
        return translate_text(text, system_prompt, ts.provider, ts.api_key, ts.model, ts.base_url)

    try:
        if field == 'title':
            target_draft.title = _translate(source_page.title)
            target_draft.save_revision(
                user=request.user, changed=True, log_action=True, clean=False,
            )
            messages.success(request, gettext("Title translated."))

        elif field == 'body':
            source_stream = [dict(b) for b in source_page.body.raw_data]
            stream_data = [dict(b) for b in target_draft.body.raw_data]

            # Decide which blocks to translate:
            #   - explicit indexes (from checkboxes / single button) → translate only those
            #   - empty list       (from "Translate all" link)      → translate every translatable block
            if block_index_raw:
                try:
                    target_indexes = sorted({int(x) for x in block_index_raw})
                except ValueError:
                    messages.error(request, gettext("Invalid block index."))
                    return redirect(edit_url)
            else:
                target_indexes = list(range(len(source_stream)))

            translated_count = 0
            skipped_count = 0
            for idx in target_indexes:
                if idx < 0 or idx >= len(source_stream):
                    skipped_count += 1
                    continue
                block = source_stream[idx]
                if block['type'] not in ('rich_text', 'html'):
                    skipped_count += 1
                    continue
                translated_value = _translate(block['value'])
                if idx < len(stream_data):
                    stream_data[idx] = {**stream_data[idx], 'value': translated_value}
                else:
                    stream_data.append({**block, 'value': translated_value})
                translated_count += 1

            if translated_count:
                target_draft.body = stream_data
                target_draft.save_revision(
                    user=request.user, changed=True, log_action=True, clean=False,
                )
                msg = gettext("Blocks translated")
                messages.success(request, f"{msg}: {translated_count}")
                if skipped_count:
                    skipped_msg = gettext("Blocks skipped (not translatable or out of range)")
                    messages.info(request, f"{skipped_msg}: {skipped_count}")
            else:
                messages.warning(request, gettext("No translatable blocks selected."))

        else:
            msg = gettext("Unknown field")
            messages.error(request, f"{msg}: {field}")

    except TranslationError as e:
        msg = gettext("Translation error")
        messages.error(request, f"{msg}: {e}")
    except Exception as e:
        msg = gettext("Unexpected error during translation")
        messages.error(request, f"{msg}: {e}")

    return redirect(edit_url)


def _get_translation_settings(request):
    try:
        ts = TranslationSettings.for_request(request)
        if ts:
            return ts
    except Exception:
        pass
    return TranslationSettings.objects.first()


def _get_latest_draft(page):
    """
    Return the latest revision of *page* as an editable model instance,
    bypassing Wagtail's ``get_latest_revision_as_object()`` which silently
    returns the live DB row when ``has_unpublished_changes`` is False.

    The returned object has ``_state`` fixed so that ``save_revision()``
    can update the page metadata afterward.
    """
    latest = (
        Revision.objects
        .filter(
            base_content_type=page.get_base_content_type(),
            object_id=str(page.pk),
        )
        .order_by('-created_at')
        .first()
    )
    if latest:
        obj = latest.as_object()
        # as_object() builds a *transient* instance via from_serializable_data,
        # so Django marks it _state.adding = True.  save_revision() internally
        # calls self.save(update_fields=...) which refuses to UPDATE a row for
        # an object that was "never saved".  Fix the state so the UPDATE works.
        obj._state.adding = False
        obj._state.db = page._state.db
        return obj
    return page.specific
