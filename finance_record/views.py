# finance_record/views.py
from django.apps import apps
from django.http import StreamingHttpResponse
from rest_framework import viewsets, permissions  # ← 加上 permissions
from rest_framework.settings import api_settings

from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from finance_record.models import FinanceRecord
from finance_record.serializers import (
    FinanceGetSerializer,
    FinanceRecordRenderSerializer,
)
from utils.page import MyPageNumberPagination

from .filter import FinanceRecordFilter  # :contentReference[oaicite:5]{index=5}
from .files import FinancefileRenderCN, FinancefileRenderEN  # :contentReference[oaicite:6]{index=6}

# 仅允许安全方法（GET/HEAD/OPTIONS）
class SafeMethodsOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS


class FinanceRecordViewSet(viewsets.ModelViewSet):
    """
    Read-only endpoints for front-end:
      - list/retrieve data
      - no create/update/delete
    """
    permission_classes = [SafeMethodsOnly]  # ← 显式放宽到安全方法即可
    pagination_class = MyPageNumberPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
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
        if self.action in ['list', 'retrieve']:
            return FinanceGetSerializer  # :contentReference[oaicite:9]{index=9}
        return FinanceGetSerializer


class FinancefileDownloadView(viewsets.ModelViewSet):
    """
    CSV download view (read-only):
      - language-aware CSV renderer
      - uses export serializer (includes computed bank account)
    """
    permission_classes = [SafeMethodsOnly]  # ← 同样显式放宽
    renderer_classes = tuple(api_settings.DEFAULT_RENDERER_CLASSES)
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
            return FinanceRecordRenderSerializer  # :contentReference[oaicite:14]{index=14}
        return FinanceRecordRenderSerializer

    def _pick_csv_renderer(self, data_iterable):
        """
        选择中/英文 CSV 渲染器（默认英文）：
        - 优先 ?lang=zh|en
        - 其次 HTTP_LANGUAGE
        - 再次 Accept-Language（判断是否以 zh 开头）
        """
        req = self.request
        lang = (req.query_params.get('lang')
                or req.META.get('HTTP_LANGUAGE')
                or req.META.get('HTTP_ACCEPT_LANGUAGE', '')).lower()
        is_zh = str(lang).startswith('zh')
        return (FinancefileRenderCN() if is_zh else FinancefileRenderEN()).render(data_iterable)

    def list(self, request, *args, **kwargs):
        from datetime import datetime
        dt = datetime.now()

        qs = list(self.filter_queryset(self.get_queryset()))

        Customer = apps.get_model('customer', 'ListModel')
        openid = getattr(getattr(self.request, "auth", None), "openid", None) \
            or getattr(getattr(self.request, "user", None), "openid", None)

        bank_map = {}
        if openid:
            for row in Customer.objects.filter(openid=openid, is_delete=False).values('customer_name', 'customer_bank_account'):
                name = row['customer_name'] or ''
                if name and name not in bank_map:
                    bank_map[name] = row['customer_bank_account'] or ''

        dn_codes = [obj.asn_dn_code for obj in qs if obj.source_type == 'DN']
        dn_customer_map = {}
        if dn_codes:
            DnListModel = apps.get_model('dn', 'DnListModel')
            for row in DnListModel.objects.filter(openid=openid, is_delete=False, dn_code__in=dn_codes).values('dn_code', 'customer'):
                dn_customer_map[row['dn_code']] = row['customer'] or ''

        serializer = self.get_serializer(
            qs, many=True,
            context={**self.get_serializer_context(),
                     'customer_bank_map': bank_map,
                     'dn_customer_map': dn_customer_map}
        )

        renderer = self._pick_csv_renderer(serializer.data)
        response = StreamingHttpResponse(renderer, content_type="text/csv; charset=utf-8")
        response['Content-Disposition'] = "attachment; filename='finance_{}.csv'".format(dt.strftime('%Y%m%d%H%M%S%f'))
        return response






