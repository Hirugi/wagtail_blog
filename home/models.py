import hashlib
import re
from io import BytesIO

from PIL import Image, ImageOps
from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import models
from django.db.models import Count
from django.utils.translation import gettext_lazy as _
from modelcluster.contrib.taggit import ClusterTaggableManager
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from taggit.models import TaggedItemBase
from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel, PageChooserPanel
from wagtail.blocks import RichTextBlock, RawHTMLBlock, StructBlock, ListBlock
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail.fields import StreamField
from wagtail.images import get_image_model_string
from wagtail.images.blocks import ImageChooserBlock
from wagtail.images.models import AbstractImage, AbstractRendition, Image as WagtailImage
from wagtail.models import Page, TranslatableMixin
from wagtail.search import index
from wagtail.snippets.blocks import SnippetChooserBlock
from wagtail.snippets.models import register_snippet

from home.panels import TranslationToolsPanel


class ImageCarouselBlock(StructBlock):
    images = ListBlock(ImageChooserBlock(label=_("Image")), label=_("Images"))

    class Meta:
        icon = "image"
        label = _("Image carousel")
        template = "home/blocks/image_carousel.html"


class ResponsiveImageBlock(ImageChooserBlock):
    class Meta:
        icon = "image"
        label = _("Image")
        template = "home/blocks/responsive_image.html"


class CustomImage(AbstractImage):
    alt_text = models.CharField(max_length=255, blank=True, default="", verbose_name=_("Alternative text"))
    no_downscale = models.BooleanField(default=False, verbose_name=_("Don't downscale on upload"))

    admin_form_fields = WagtailImage.admin_form_fields + ("alt_text", "no_downscale",)

    def save(self, *args, **kwargs):
        # Downscale original image on first save if enabled
        if self.file and not self.no_downscale:
            try:
                self.file.seek(0)
                with Image.open(self.file) as im:
                    fmt = (im.format or "JPEG").upper()
                    # Skip animated GIFs
                    if fmt == "GIF" and getattr(im, "is_animated", False):
                        pass
                    else:
                        # Normalize orientation
                        im = ImageOps.exif_transpose(im)
                        max_dim = getattr(settings, "IMAGE_MAX_UPLOAD_DIMENSION", 2000)
                        w, h = im.size
                        if max(w, h) > max_dim:
                            scale = max_dim / float(max(w, h))
                            new_size = (int(w * scale), int(h * scale))
                            if im.mode in ("RGBA", "P"):  # ensure correct mode for JPEG
                                save_mode = "PNG" if fmt == "PNG" else fmt
                            else:
                                save_mode = fmt
                            resized = im.resize(new_size, Image.Resampling.LANCZOS)
                            buf = BytesIO()
                            save_kwargs = {}
                            if save_mode == "JPEG":
                                # JPEG must be RGB
                                if resized.mode not in ("RGB", "L"):
                                    resized = resized.convert("RGB")
                                save_kwargs.update({"quality": 95, "optimize": True})
                            if save_mode == "PNG":
                                save_kwargs.update({"optimize": True})
                            resized.save(buf, format=save_mode, **save_kwargs)
                            buf.seek(0)
                            # Keep original filename
                            file_name = self.file.name
                            self.file = ContentFile(buf.read(), name=file_name)
            except Exception:
                # If processing fails, proceed with the original
                pass
        super().save(*args, **kwargs)


class CustomRendition(AbstractRendition):
    image = models.ForeignKey(CustomImage, related_name='renditions', on_delete=models.CASCADE)

    class Meta:
        unique_together = (('image', 'filter_spec', 'focal_point_key'),)


@register_snippet
class NavLink(TranslatableMixin, models.Model):
    label = models.CharField(max_length=255, verbose_name=_("Label"))
    page = models.ForeignKey(
        'wagtailcore.Page',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='nav_links',
        verbose_name=_("Page"),
        help_text=_("Select a page to link to. Takes priority over the URL field."),
    )
    url = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("URL"),
        help_text=_("Used when no page is selected. Enter a full URL (e.g. https://blog.example.com) or a path starting with / for internal links."),
    )

    panels = [
        FieldPanel("label"),
        MultiFieldPanel([
            PageChooserPanel("page"),
            FieldPanel("url"),
        ], heading=_("Link target (page takes priority over URL)")),
    ]

    def get_url(self):
        if self.page:
            return self.page.full_url
        return self.url

    def __str__(self) -> str:
        return self.label

    class Meta:
        verbose_name = _("Navigation link")
        verbose_name_plural = _("Navigation links")
        constraints = [
            models.UniqueConstraint(fields=('translation_key', 'locale'),
                                    name='unique_translation_key_locale_home_navlink')
        ]


@register_snippet
class SocialLink(TranslatableMixin, models.Model):
    label = models.CharField(max_length=255)
    url = models.CharField(max_length=500)
    icon = models.ForeignKey(
        get_image_model_string(), null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name=_("Icon")
    )

    panels = [
        FieldPanel("label"),
        FieldPanel("url"),
        FieldPanel("icon"),
    ]

    def __str__(self) -> str:
        return self.label

    class Meta:
        verbose_name = _("Social link")
        verbose_name_plural = _("Social links")
        constraints = [
            models.UniqueConstraint(fields=('translation_key', 'locale'),
                                    name='unique_translation_key_locale_home_sociallink')
        ]


@register_setting
class HeaderSettings(BaseSiteSetting):
    header_links = StreamField([
        ("link", SnippetChooserBlock("home.NavLink")),
    ], blank=True, verbose_name=_("Header links"))
    show_search = models.BooleanField(default=True, verbose_name=_("Show search"))

    panels = [
        FieldPanel("header_links"),
        FieldPanel("show_search"),
    ]

    class Meta:
        verbose_name = _("Header settings")


@register_setting
class FooterSettings(BaseSiteSetting):
    footer_links = StreamField([
        ("link", SnippetChooserBlock("home.NavLink")),
    ], blank=True, verbose_name=_("Footer links"))
    social_links = StreamField([
        ("social", SnippetChooserBlock("home.SocialLink")),
    ], blank=True, verbose_name=_("Social links"))
    copyright = models.CharField(max_length=255, blank=True, default="", verbose_name=_("Copyright"))

    panels = [
        FieldPanel("footer_links"),
        FieldPanel("social_links"),
        FieldPanel("copyright"),
    ]

    class Meta:
        verbose_name = _("Footer settings")


class LanguageTranslationConfig(models.Model):
    translation_settings = ParentalKey(
        'TranslationSettings',
        on_delete=models.CASCADE,
        related_name='language_configs',
    )
    locale = models.ForeignKey(
        'wagtailcore.Locale',
        on_delete=models.CASCADE,
        verbose_name=_('Language'),
    )
    system_prompt = models.TextField(
        verbose_name=_('Translation prompt'),
        help_text=_('Instructions for the AI: target language, writing style, formatting rules, etc.'),
    )
    default_disclaimer = models.TextField(
        blank=True,
        verbose_name=_('Default disclaimer'),
        help_text=_('Auto-filled in the page disclaimer field when translating (e.g. "Translated with AI")'),
    )

    panels = [
        FieldPanel('locale'),
        FieldPanel('system_prompt'),
        FieldPanel('default_disclaimer'),
    ]

    def __str__(self):
        return str(self.locale)

    class Meta:
        verbose_name = _('Language translation config')
        verbose_name_plural = _('Language translation configs')
        constraints = [
            models.UniqueConstraint(
                fields=('translation_settings', 'locale'),
                name='unique_language_config_per_settings',
            )
        ]


@register_setting(icon='site')
class TranslationSettings(ClusterableModel, BaseSiteSetting):
    source_locale = models.ForeignKey(
        'wagtailcore.Locale',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('Source language'),
        help_text=_('The language your posts are originally written in'),
    )
    provider = models.CharField(
        max_length=50,
        choices=[
            ('anthropic', 'Anthropic (Claude)'),
            ('openai', 'OpenAI-compatible  (ChatGPT, DeepSeek, Mistral, Ollama, …)'),
        ],
        default='anthropic',
        verbose_name=_('AI provider'),
    )
    api_key = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('API key'),
    )
    model = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_('Model'),
        help_text=_('e.g. claude-sonnet-4-6, gpt-4o, mistral-large-latest'),
    )
    base_url = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Base URL'),
        help_text=_('OpenAI-compatible only. Leave blank for OpenAI. Example: https://api.deepseek.com/v1'),
    )

    panels = [
        MultiFieldPanel([
            FieldPanel('source_locale'),
            FieldPanel('provider'),
            FieldPanel('api_key'),
            FieldPanel('model'),
            FieldPanel('base_url'),
        ], heading=_('AI provider')),
        InlinePanel('language_configs', label=_('Language'), heading=_('Per-language settings')),
    ]

    class Meta:
        verbose_name = _('Translation settings')


class HomePage(Page):
    subpage_types = ['home.BlogPage', 'home.StandardPage']
    max_count = 1

    posts_per_page = models.PositiveIntegerField(default=5, verbose_name=_("Posts per page"))
    tags_max_display = models.PositiveIntegerField(default=16, verbose_name=_("Max tags in cloud"))

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request)
        tags_param = request.GET.get('tags', '') or ''
        selected_tags = [t.strip() for t in tags_param.split(',') if t.strip()] if tags_param else []

        lang_code = getattr(request, 'LANGUAGE_CODE', None)
        all_posts_qs = BlogPage.objects.live().public()
        if lang_code:
            all_posts_qs = all_posts_qs.filter(locale__language_code=lang_code)
        for t in selected_tags:
            all_posts_qs = all_posts_qs.filter(tags__name=t)

        # Trip date filtering
        trip_year = request.GET.get('trip_year')
        trip_month = request.GET.get('trip_month')
        if trip_year:
            all_posts_qs = all_posts_qs.filter(trip_date__year=trip_year)
        if trip_month:
            all_posts_qs = all_posts_qs.filter(trip_date__month=trip_month)
        # Sorting: first by trip_date desc, then by first_published_at desc
        all_posts_qs = all_posts_qs.order_by(models.F('trip_date').desc(nulls_last=True), '-first_published_at')

        paginator = Paginator(all_posts_qs, self.posts_per_page)
        page_number = request.GET.get('page')
        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)
        context['latest_posts'] = page_obj.object_list
        context['page_obj'] = page_obj
        context['paginator'] = paginator
        context['is_paginated'] = page_obj.has_other_pages()

        # Tag cloud by frequency
        tags_base = BlogPage.objects.live().public()
        if lang_code:
            tags_base = tags_base.filter(locale__language_code=lang_code)
        tag_rows = (
            tags_base.values('tags__name')
            .exclude(tags__name__isnull=True)
            .exclude(tags__name__exact='')
            .annotate(cnt=Count('id'))
            .order_by('-cnt', 'tags__name')
        )
        tag_names = [row['tags__name'] for row in tag_rows[: self.tags_max_display]]
        for t in selected_tags:
            if t not in tag_names:
                tag_names.append(t)

        context['tag_cloud'] = tag_names
        context['selected_tags'] = selected_tags
        context['selected_tags_csv'] = ','.join(selected_tags)

        # Trip date filter logic:
        #   - trip_years: all years present in posts with trip_date.
        #   - trip_months: if a year is selected, all unique months in that year present in posts;
        #                  otherwise, all unique months present across all posts (each month only once).
        #   - trip_months is always a list of unique months (integers), sorted ascending.

        trip_years = (
            BlogPage.objects.filter(trip_date__isnull=False)
            .dates('trip_date', 'year')
            .distinct()
        )
        if trip_year:
            months_qs = BlogPage.objects.filter(trip_date__year=trip_year, trip_date__isnull=False)
        else:
            months_qs = BlogPage.objects.filter(trip_date__isnull=False)
        months_set = sorted(
            {int(m) for m in months_qs.values_list('trip_date__month', flat=True) if m}
        )

        context['trip_years'] = trip_years
        context['trip_months'] = months_set
        context['trip_year_selected'] = trip_year
        context['trip_month_selected'] = trip_month
        return context

    content_panels = Page.content_panels + [
        FieldPanel('posts_per_page'),
        FieldPanel('tags_max_display'),
    ]


class BlogPageTag(TaggedItemBase):
    content_object = ParentalKey('BlogPage', related_name='tagged_items', on_delete=models.CASCADE)


class PageBase(Page):
    views = models.IntegerField(_('Views'), default=0)

    promote_panels = Page.promote_panels + [
        FieldPanel('views', read_only=True),
    ]

    def get_admin_display_title(self):
        base = super().get_admin_display_title()
        # Show views in the explorer listing for quick reference
        try:
            views_str = f" | {self.views} " + str(_('Views')).lower()
        except Exception:
            views_str = ""
        return f"{base}{views_str}"

    @staticmethod
    def _get_client_ip(request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            ip = xff.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip or ''

    _BOT_UA_RE = re.compile(
        r'bot|crawl|spider|slurp|baiduspider|yandexbot|sogou|exabot|facebookexternalhit'
        r'|facebot|ia_archiver|alexa|msnbot|duckduckbot|semrushbot|ahrefsbot'
        r'|dotbot|petalbot|bytespider|gptbot|claudebot|chatgpt|applebot'
        r'|linkedinbot|twitterbot|whatsapp|telegrambot|discordbot|pinterestbot',
        re.IGNORECASE,
    )

    def _record_unique_view(self, request, ttl_seconds: int = 24 * 60 * 60):
        """
        Increment page.views only once per unique viewer within the TTL window.
        Uniqueness is based on client IP + User-Agent hash.
        Staff/superusers and bots are excluded from view counting.
        """
        if getattr(request, 'is_preview', False) or request.method != 'GET':
            return

        user = getattr(request, 'user', None)
        if user and user.is_authenticated and (user.is_staff or user.is_superuser):
            return

        ua = (request.META.get('HTTP_USER_AGENT') or '').strip()
        if not ua or self._BOT_UA_RE.search(ua):
            return

        ip = self._get_client_ip(request)
        raw = f"{ip}|{ua}".encode('utf-8')
        viewer_hash = hashlib.sha256(raw).hexdigest()[:32]
        cache_key = f"pageview:{self.id}:{viewer_hash}"

        if cache.add(cache_key, True, timeout=ttl_seconds):
            self.__class__.objects.filter(id=self.id).update(views=models.F('views') + 1)
            try:
                self.views += 1
            except Exception:
                pass

    def serve(self, request, *args, **kwargs):
        response = super().serve(request, *args, **kwargs)
        self._record_unique_view(request)
        return response

    class Meta:
        abstract = True


class BlogPage(PageBase):
    trip_date = models.DateField(
        _('Trip date'),
        blank=True,
        null=True,
        help_text=_('Month and year of the trip')
    )
    body = StreamField(
        [
            ('rich_text', RichTextBlock()),
            ('html', RawHTMLBlock()),
            ('image', ResponsiveImageBlock()),
            ('carousel', ImageCarouselBlock()),
        ],
        blank=True,
        verbose_name=_('Content')
    )
    cover_image = models.ForeignKey(
        get_image_model_string(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='blogpage_cover_images',
        verbose_name=_('Cover image')
    )
    disclaimer = models.TextField(
        blank=True,
        verbose_name=_('Disclaimer'),
        help_text=_('Disclaimer text displayed at the top of the post (will not appear in post excerpts)')
    )
    tags = ClusterTaggableManager(through=BlogPageTag, blank=True)

    prev_part = models.ForeignKey(
        'home.BlogPage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='next_parts',
        verbose_name=_('Previous part'),
    )
    prev_part_text = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Previous part link text'),
        help_text=_('Text displayed on the link to the previous part'),
    )
    next_part = models.ForeignKey(
        'home.BlogPage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='prev_parts',
        verbose_name=_('Next part'),
    )
    next_part_text = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Next part link text'),
        help_text=_('Text displayed on the link to the next part'),
    )

    content_panels = Page.content_panels + [
        FieldPanel('cover_image'),
        FieldPanel('trip_date'),
        FieldPanel('disclaimer'),
        FieldPanel('body'),
        FieldPanel('tags'),
        MultiFieldPanel([
            PageChooserPanel('prev_part', 'home.BlogPage'),
            FieldPanel('prev_part_text'),
            PageChooserPanel('next_part', 'home.BlogPage'),
            FieldPanel('next_part_text'),
        ], heading=_('Series navigation')),
        TranslationToolsPanel(heading=_('Translation tools')),
    ]
    search_fields = Page.search_fields + [
        index.SearchField('title'),
        index.SearchField('body'),
    ]

    parent_page_types = ['home.HomePage']
    subpage_types = []


class StandardPage(PageBase):
    body = StreamField(
        [
            ('rich_text', RichTextBlock()),
            ('html', RawHTMLBlock()),
            ('image', ResponsiveImageBlock()),
            ('carousel', ImageCarouselBlock()),
        ],
        blank=True,
        verbose_name=_("Content")
    )
    content_panels = Page.content_panels + [
        FieldPanel('body'),
    ]

    search_fields = Page.search_fields + [
        index.SearchField('title'),
        index.SearchField('body'),
    ]

    parent_page_types = ['home.HomePage', 'home.StandardPage', 'wagtailcore.Page']
    subpage_types = ['home.StandardPage']

    class Meta:
        verbose_name = _("Standard page")
        verbose_name_plural = _("Standard pages")
