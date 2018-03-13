import re
from django.conf import settings
from django.db import models

USE_GEODJANGO = ('django.contrib.gis' in settings.INSTALLED_APPS)
if USE_GEODJANGO:
    from django.contrib.gis.db import models

from boundaryservice.fields import ListField, JSONField
from boundaryservice.utils import get_site_url_root


class SluggedModel(models.Model):
    """
    Extend this class to get a slug field and slug generated from a model
    field. We call the 'get_slug_text', '__unicode__' or '__str__'
    methods (in that order) on save() to get text to slugify. The slug may
    have numbers appended to make sure the slug is unique.
    """
    slug = models.SlugField(max_length=256)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.unique_slug()
        if self.slug == '': raise ValueError("Slug may not be blank [%s]" % str(self))
        super(SluggedModel,self).save(*args, **kwargs)

    def unique_slug(self):
        """
        Customized unique_slug function
        """
        if not getattr(self, "slug"): # if it's already got a slug, do nothing.
            from django.template.defaultfilters import slugify
            if hasattr(self,'get_slug_text') and callable(self.get_slug_text):
                slug_txt = self.get_slug_text()
            elif hasattr(self,'__unicode__'):
                slug_txt = str(self)
            elif hasattr(self,'__str__'):
                slug_txt = str(self)
            else:
                return
            original_slug = slugify(slug_txt)
            queryset = self.__class__._default_manager.all()
            if not queryset.filter(slug=original_slug).count():
                setattr(self, "slug", original_slug)
            else:
                slug = ''
                next = 2
                while not slug or queryset.filter(slug=slug).count():
                    slug = original_slug
                    end = '-%s' % next
                    if len(slug) + len(end) > 256:
                        slug = slug[:200-len(end)]
                    slug = '%s%s' % (slug, end)
                    next += 1
                setattr(self, "slug", slug)

    def fully_qualified_url(self):
        return get_site_url_root() + self.get_absolute_url()


class BoundarySet(SluggedModel):
    """
    A set of related boundaries, such as all Wards or Neighborhoods.
    """
    name = models.CharField(max_length=64, unique=True,
        help_text='Category of boundaries, e.g. "Community Areas".')
    singular = models.CharField(max_length=64,
        help_text='Name of a single boundary, e.g. "Community Area".')
    kind_first = models.BooleanField(
        help_text='If true, boundary display names will be "kind name" (e.g. Austin Community Area), otherwise "name kind" (e.g. 43rd Precinct).')
    authority = models.CharField(max_length=256,
        help_text='The entity responsible for this data\'s accuracy, e.g. "City of Chicago".')
    domain = models.CharField(max_length=256,
        help_text='The area that this BoundarySet covers, e.g. "Chicago" or "Illinois".')
    last_updated = models.DateField(
        help_text='The last time this data was updated from its authority (but not necessarily the date it is current as of).')
    href = models.URLField(blank=True,
        help_text='The url this data was found at, if any.')
    notes = models.TextField(blank=True,
        help_text='Notes about loading this data, including any transformations that were applied to it.')
    count = models.IntegerField(
        help_text='Total number of features in this boundary set.')
    metadata_fields = ListField(separator='|', blank=True,
        help_text='What, if any, metadata fields were loaded from the original dataset.')

    class Meta:
        ordering = ('name',)

    def __unicode__(self):
        """
        Print plural names.
        """
        return str(self.name)


class Boundary(SluggedModel):
    """
    A boundary object, such as a Ward or Neighborhood.
    """
    set = models.ForeignKey(BoundarySet, related_name='boundaries',
        help_text='Category of boundaries that this boundary belongs, e.g. "Community Areas".')
    kind = models.CharField(max_length=64,
        help_text='A copy of BoundarySet\'s "singular" value for purposes of slugging and inspection.')
    external_id = models.CharField(max_length=64,
        help_text='The boundaries\' unique id in the source dataset, or a generated one.')
    name = models.CharField(max_length=192, db_index=True,
        help_text='The name of this boundary, e.g. "Austin".')
    display_name = models.CharField(max_length=256,
        help_text='The name and kind of the field to be used for display purposes.')
    metadata = JSONField(blank=True,
        help_text='The complete contents of the attribute table for this boundary from the source shapefile, structured as json.')

    if USE_GEODJANGO:
        shape = models.MultiPolygonField(srid=4269,
            help_text='The geometry of this boundary in EPSG:4269 projection.')
        simple_shape = models.MultiPolygonField(srid=4269,
            help_text='The geometry of this boundary in EPSG:4269 projection and simplified to 0.0001 tolerance.')
        centroid = models.PointField(srid=4269,
            null=True,
            help_text='The centroid (weighted center) of this boundary in EPSG:4269 projection.')
    else:
        shape = models.TextField(help_text='(GeoDjango is disabled)')
        simple_shape = models.TextField(help_text='(GeoDjango is disabled)')
        centroid = models.TextField(
            null=True,
            help_text='(GeoDjango is disabled)')

    if USE_GEODJANGO:
        objects = models.GeoManager()
    else:
        objects = models.Manager()

    class Meta:
        ordering = ('kind', 'display_name')
        verbose_name_plural = 'boundaries'

    def __unicode__(self):
        """
        Print names are formatted like "Austin Community Area"
        and will slug like "austin-community-area".
        """
        return str(self.display_name)
