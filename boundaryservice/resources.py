import re

from django.conf import settings
from django.contrib.gis.measure import D
from tastypie import fields
from tastypie.serializers import Serializer
from tastypie.constants import ALL, ALL_WITH_RELATIONS
from django.contrib.gis.geos import Polygon

from boundaryservice.authentication import NoOpApiKeyAuthentication
from boundaryservice.models import BoundarySet, Boundary
from boundaryservice.tastyhacks import SluggedResource
from boundaryservice.throttle import AnonymousThrottle

try:
    from cannonball.core.utils.cache.boundarycache import CannonballCache
except ImportError:
    from tastypie.cache import SimpleCache as CannonballCache


class BoundarySetResource(SluggedResource):
    boundaries = fields.ToManyField(
        'boundaryservice.resources.BoundaryResource', 'boundaries')

    class Meta:
        queryset = BoundarySet.objects.all()
        serializer = Serializer(
            formats=['json', 'jsonp'],
            content_types={
                'json': 'application/json',
                'jsonp': 'text/javascript'})
        resource_name = 'boundary-set'
        excludes = ['id', 'singular', 'kind_first']
        allowed_methods = ['get']
        authentication = NoOpApiKeyAuthentication()
        throttle = AnonymousThrottle(throttle_at=100)
        cache = CannonballCache()


class BoundaryResource(SluggedResource):
    set = fields.ForeignKey(BoundarySetResource, 'set', on_delete=models.CASCADE)

    class Meta:
        queryset = Boundary.objects.all()
        serializer = Serializer(
            formats=['json', 'jsonp'],
            content_types={
                'json': 'application/json',
                'jsonp': 'text/javascript'})
        resource_name = 'boundary'
        excludes = ['id', 'display_name']
        allowed_methods = ['get']
        authentication = NoOpApiKeyAuthentication()
        throttle = AnonymousThrottle(throttle_at=100)
        cache = CannonballCache()
        filtering = {
            'external_id': ['exact', 'startswith'],
        }


    def alter_list_data_to_serialize(self, request, data):
        """
        Allow the selection of simple, full or no shapes
        using a query parameter.
        """
        shape_type = request.GET.get('shape_type', 'simple')

        for obj in data['objects']:
            if shape_type != 'simple':
                del obj.data['simple_shape']

            if shape_type != 'full':
                del obj.data['shape']

        excludes = request.GET.get('excludes', "").strip().split(',')
        if excludes:
            for exclude in excludes:
                for obj in data['objects']:
                    try:
                        del obj.data[exclude]
                    except:
                        pass

        return data

    def alter_detail_data_to_serialize(self, request, bundle):
        """
        Allow the selection of simple, full or no shapes
        using a query parameter.
        """
        shape_type = request.GET.get('shape_type', 'simple')

        if shape_type != 'simple':
            del bundle.data['simple_shape']

        if shape_type != 'full':
            del bundle.data['shape']

        return bundle

    def build_filters(self, filters=None):
        """
        Override build_filters to support geoqueries.
        """
        if filters is None:
            filters = {}

        orm_filters = super(BoundaryResource, self).build_filters(filters)

        if 'sets' in filters:
            sets = filters['sets'].split(',')

            orm_filters.update({'set__slug__in': sets})

        if 'contains' in filters:
            lat, lon = filters['contains'].split(',')
            wkt_pt = 'POINT(%s %s)' % (lon, lat)

            orm_filters.update({'shape__contains': wkt_pt})

        if 'near' in filters:
            lat, lon, range = filters['near'].split(',')
            wkt_pt = 'POINT(%s %s)' % (lon, lat)
            numeral = re.match('([0-9]+)', range).group(1)
            unit = range[len(numeral):]
            numeral = int(numeral)
            kwargs = {unit: numeral}

            orm_filters.update({'shape__distance_lte': (wkt_pt, D(**kwargs))})

        if 'intersects' in filters:
            slug = filters['intersects']
            bounds = Boundary.objects.get(slug=slug)

            orm_filters.update({'shape__intersects': bounds.shape})

        return orm_filters
