import hashlib
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
from taggit.models import TaggedItemBase
from wagtail.admin.panels import FieldPanel
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
    label = models.CharField(max_length=255)
    url = models.CharField(max_length=500)

    panels = [
        FieldPanel("label"),
        FieldPanel("url"),
    ]

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
    ], use_json_field=True, blank=True, verbose_name=_("Header links"))

    panels = [
        FieldPanel("header_links"),
    ]

    class Meta:
        verbose_name = _("Header settings")


@register_setting
class FooterSettings(BaseSiteSetting):
    footer_links = StreamField([
        ("link", SnippetChooserBlock("home.NavLink")),
    ], use_json_field=True, blank=True, verbose_name=_("Footer links"))
    social_links = StreamField([
        ("social", SnippetChooserBlock("home.SocialLink")),
    ], use_json_field=True, blank=True, verbose_name=_("Social links"))
    copyright = models.CharField(max_length=255, blank=True, default="", verbose_name=_("Copyright"))

    panels = [
        FieldPanel("footer_links"),
        FieldPanel("social_links"),
        FieldPanel("copyright"),
    ]

    class Meta:
        verbose_name = _("Footer settings")


class HomePage(Page):
    subpage_types = ['home.BlogPage', 'home.StandardPage']
    max_count = 1

    posts_per_page = models.PositiveIntegerField(default=5, verbose_name=_("Posts per page"))
    tags_max_display = models.PositiveIntegerField(default=16, verbose_name=_("Max tags in cloud"))

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request)
        # Parse selected tags from query (?tags=tag1,tag2)
        tags_param = request.GET.get('tags', '') or ''
        selected_tags = [t.strip() for t in tags_param.split(',') if t.strip()] if tags_param else []

        lang_code = getattr(request, 'LANGUAGE_CODE', None)
        all_posts_qs = BlogPage.objects.live().public().order_by('-first_published_at')
        if lang_code:
            all_posts_qs = all_posts_qs.filter(locale__language_code=lang_code)
        # Filter by ALL selected tags (intersection)
        for t in selected_tags:
            all_posts_qs = all_posts_qs.filter(tags__name=t)

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
        # Ensure selected tags are visible in cloud
        for t in selected_tags:
            if t not in tag_names:
                tag_names.append(t)

        context['tag_cloud'] = tag_names
        context['selected_tags'] = selected_tags
        context['selected_tags_csv'] = ','.join(selected_tags)
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

    def _record_unique_view(self, request, ttl_seconds: int = 24 * 60 * 60):
        """
        Increment page.views only once per unique viewer within the TTL window.
        Uniqueness is based on client IP + User-Agent hash.
        """
        if getattr(request, 'is_preview', False) or request.method != 'GET':
            return

        ua = (request.META.get('HTTP_USER_AGENT') or '').strip()
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
    body = StreamField(
        [
            ('rich_text', RichTextBlock()),
            ('html', RawHTMLBlock()),
            ('image', ResponsiveImageBlock()),
            ('carousel', ImageCarouselBlock()),
        ],
        use_json_field=True,
        blank=True,
        verbose_name=_("Content")
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

    content_panels = Page.content_panels + [
        FieldPanel('cover_image'),
        FieldPanel('disclaimer'),
        FieldPanel('body'),
        FieldPanel('tags'),
    ]

    search_fields = Page.search_fields + [
        index.SearchField('title', partial_match=True),
        index.SearchField('body', partial_match=True),
    ]


class StandardPage(PageBase):
    body = StreamField(
        [
            ('rich_text', RichTextBlock()),
            ('html', RawHTMLBlock()),
            ('image', ResponsiveImageBlock()),
            ('carousel', ImageCarouselBlock()),
        ],
        use_json_field=True,
        blank=True,
        verbose_name=_("Content")
    )
    content_panels = Page.content_panels + [
        FieldPanel('body'),
    ]

    search_fields = Page.search_fields + [
        index.SearchField('title', partial_match=True),
        index.SearchField('body', partial_match=True),
    ]

    parent_page_types = ['home.HomePage', 'home.StandardPage']
    subpage_types = ['home.StandardPage']

    class Meta:
        verbose_name = _("Standard page")
        verbose_name_plural = _("Standard pages")
