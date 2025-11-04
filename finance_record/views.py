# finance_record/views.py
from django.apps import apps
from django.http import StreamingHttpResponse
from rest_framework import viewsets
from rest_framework.settings import api_settings

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
    filterset_class = FinanceRecordFilter
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
    filterset_class = FinanceRecordFilter  # :contentReference[oaicite:11]{index=11}
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
        qs = list(self.filter_queryset(self.get_queryset()))

    # 2) 预构建 customer_name -> bank_account 映射（当前租户）
        Customer = apps.get_model('customer', 'ListModel')
        openid = getattr(getattr(self.request, "auth", None), "openid", None) \
            or getattr(getattr(self.request, "user", None), "openid", None)

        bank_map = {}
        if openid:
        # 一次查询拿全量映射
            for row in Customer.objects.filter(openid=openid, is_delete=False)\
                                   .values('customer_name', 'customer_bank_account'):
                name = row['customer_name'] or ''
                if name and name not in bank_map:
                    bank_map[name] = row['customer_bank_account'] or ''

    # 3) 若存在 DN 记录，预构建 dn_code -> customer_name 映射，减少二跳查询
        dn_codes = [obj.asn_dn_code for obj in qs if obj.source_type == 'DN']
        dn_customer_map = {}
        if dn_codes:
            DnListModel = apps.get_model('dn', 'DnListModel')
            for row in DnListModel.objects.filter(openid=openid, is_delete=False, dn_code__in=dn_codes)\
                                      .values('dn_code', 'customer'):
                dn_customer_map[row['dn_code']] = row['customer'] or ''

    # 4) 序列化时把映射放进 context，供序列化器直接查 dict 而非再 hit DB
        serializer = self.get_serializer(
            qs,
            many=True,
            context={
                **self.get_serializer_context(),
                'customer_bank_map': bank_map,
                'dn_customer_map': dn_customer_map
            }
        )

        renderer = self.get_lang(serializer.data)
        response = StreamingHttpResponse(renderer, content_type="text/csv")
        response['Content-Disposition'] = "attachment; filename='finance_{}.csv'".format(
            dt.strftime('%Y%m%d%H%M%S%f')
        )
        return response




