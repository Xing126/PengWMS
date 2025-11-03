# finance_record/views.py
# finance_record/views.py
from django.http import StreamingHttpResponse
from rest_framework import viewsets
from rest_framework.settings import api_settings
from rest_framework.response import Response

from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from finance_record.models import FinanceRecord
from finance_record.serializers import (
    FinanceGetSerializer,
    FinanceRecordRenderSerializer,
)
from utils.page import MyPageNumberPagination

# Use the new mutually-exclusive filter (asn_dn_code exact OR ship_receive_time fuzzy)
from .filter import FinanceRecordFilter  # :contentReference[oaicite:5]{index=5}

# CSV renderers (headers/labels defined in files.py)
from .files import FinancefileRenderCN, FinancefileRenderEN  # :contentReference[oaicite:6]{index=6}


class FinanceRecordViewSet(viewsets.ModelViewSet):
    """
    Read-only endpoints for front-end:
      - list/retrieve data
      - no create/update/delete
    """
    pagination_class = MyPageNumberPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    # expose useful ordering fields; ship_receive_time now first-class for querying
    ordering_fields = ['asn_dn_code', 'ship_receive_time', 'create_time', 'update_time', 'total_fee']
    filter_class = FinanceRecordFilter
    http_method_names = ['get', 'head', 'options']

    def get_project(self):
        try:
            return self.kwargs.get('pk')
        except Exception:
            return None

    def get_queryset(self):
        obj_key = self.get_project()
        openid = getattr(getattr(self.request, "auth", None), "openid", None) \
             or getattr(getattr(self.request, "user", None), "openid", None)
        if not openid:
            return FinanceRecord.objects.none()

        base = FinanceRecord.objects.filter(openid=openid, is_delete=False)
        if obj_key is None:
            return base.order_by('-ship_receive_time', '-update_time')
        else:
            return base.filter(asn_dn_code=obj_key).order_by('-ship_receive_time', '-update_time')

    def get_serializer_class(self):
        # list/retrieve remain read-only and use the "Get" serializer
        if self.action in ['list', 'retrieve']:
            return FinanceGetSerializer  # :contentReference[oaicite:9]{index=9}
        # disallow write operations
        return FinanceGetSerializer


class FinancefileDownloadView(viewsets.ModelViewSet):
    """
    CSV download view (read-only):
      - language-aware CSV renderer
      - uses export serializer (includes computed bank account)
    """
    renderer_classes = (FinancefileRenderCN,) + tuple(api_settings.DEFAULT_RENDERER_CLASSES)  # :contentReference[oaicite:10]{index=10}
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ['asn_dn_code', 'ship_receive_time', 'create_time', 'update_time', 'total_fee']
    filter_class = FinanceRecordFilter  # :contentReference[oaicite:11]{index=11}
    http_method_names = ['get', 'head', 'options']

    def get_project(self):
        try:
            return self.kwargs.get('pk')
        except Exception:
            return None

    def get_queryset(self):
        obj_key = self.get_project()
        openid = getattr(getattr(self.request, "auth", None), "openid", None) \
             or getattr(getattr(self.request, "user", None), "openid", None)
        if not openid:
            return FinanceRecord.objects.none()

        base = FinanceRecord.objects.filter(openid=openid, is_delete=False)
        if obj_key is None:
            return base.order_by('-ship_receive_time', '-update_time')
        else:
            return base.filter(asn_dn_code=obj_key).order_by('-ship_receive_time', '-update_time')

    def get_serializer_class(self):
        if self.action in ['list']:
            # export serializer contains "customer_bank_account" and all columns used by CSV
            return FinanceRecordRenderSerializer  # :contentReference[oaicite:14]{index=14}
        return FinanceRecordRenderSerializer

    def get_lang(self, data_iterable):
        # Choose renderer per "Language" header (default to EN)
        lang = self.request.META.get('HTTP_LANGUAGE')
        if lang == 'zh-hans':
            return FinancefileRenderCN().render(data_iterable)  # :contentReference[oaicite:15]{index=15}
        return FinancefileRenderEN().render(data_iterable)      # :contentReference[oaicite:16]{index=16}

    def list(self, request, *args, **kwargs):
        from datetime import datetime
        dt = datetime.now()
        # Serialize filtered queryset with export serializer
        data = (
            self.get_serializer(instance).data
            for instance in self.filter_queryset(self.get_queryset())
        )
        renderer = self.get_lang(data)
        response = StreamingHttpResponse(renderer, content_type="text/csv")
        response['Content-Disposition'] = "attachment; filename='finance_{}.csv'".format(
            dt.strftime('%Y%m%d%H%M%S%f')
        )
        return response




