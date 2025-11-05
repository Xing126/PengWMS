# 只读接口：列表/详情/CSV 导出
# 在原基础上支持 granularity=day|month|quarter，并根据输入格式规范化 period 输出：
# - day：输入 YYYY-MM-DD；返回日快照（原有逻辑）
# - month：输入 YYYY-MM；   period 输出 YYYY-MM
# - quarter：输入 YYYY-Q；  period 输出 YYYY-Q
from django.http import StreamingHttpResponse
from rest_framework import viewsets, permissions
from rest_framework.settings import api_settings
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from django.db.models import Sum, OuterRef, Subquery, Max
from django.db.models.functions import TruncDate, TruncMonth, TruncQuarter

from .models import RefrigerationFeeDetail
from .serializers import RefrigerationFeeGetSerializer
from .filter import RefrigerationFeeFilter
from .files import (
    RefrigerationFileRenderCN,
    RefrigerationFileRenderEN,
    RefrigerationAggFileRenderCN,
    RefrigerationAggFileRenderEN,
)
from utils.page import MyPageNumberPagination


class SafeMethodsOnly(permissions.BasePermission):
    """仅允许安全方法（GET/HEAD/OPTIONS）"""
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS


class RefrigerationFeeViewSet(viewsets.ModelViewSet):
    """
    只读视图：列表/详情
    - granularity=day|month|quarter（默认 day）
    - day：返回日快照（分页 + 序列化器）
    - month/quarter：数据库侧聚合后返回（不分页）
    """
    permission_classes = [SafeMethodsOnly]
    http_method_names = ['get', 'head', 'options']

    pagination_class = MyPageNumberPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = RefrigerationFeeFilter
    ordering_fields = [
        'openid', 'ship_receive_time', 'create_time', 'update_time',
        'total_pallet_qty', 'refrigeration_fee'
    ]

    def get_queryset(self):
        openid = getattr(getattr(self.request, "auth", None), "openid", None) \
              or getattr(getattr(self.request, "user", None), "openid", None)
        if not openid:
            return RefrigerationFeeDetail.objects.none()
        return RefrigerationFeeDetail.objects.filter(openid=openid).order_by('-ship_receive_time', '-update_time')

    def get_serializer_class(self):
        return RefrigerationFeeGetSerializer

    # —— 按期聚合 —— #
    def _aggregate_by_period(self, base_qs, granularity: str):
        trunc_map = {
            'day': TruncDate('ship_receive_time'),
            'month': TruncMonth('ship_receive_time'),
            'quarter': TruncQuarter('ship_receive_time'),
        }
        trunc_fn = trunc_map.get(granularity, TruncDate('ship_receive_time'))

        qs = base_qs.annotate(period=trunc_fn).values('period')
        qs = qs.annotate(total_fee=Sum('refrigeration_fee'))

        period_max_dt = base_qs.annotate(period=trunc_fn).values('period') \
            .annotate(last_dt=Max('ship_receive_time')) \
            .filter(period=OuterRef('period')) \
            .values('last_dt')[:1]

        period_end_stock = base_qs.filter(ship_receive_time=Subquery(period_max_dt)) \
            .values('total_pallet_qty')[:1]

        qs = qs.annotate(end_stock=Subquery(period_end_stock))

        return qs.order_by('period')

    # —— 工具：把 period 规范化为字符串 —— #
    def _format_period(self, period_obj, granularity: str):
        """
        输出规则：
        - day:     YYYY-MM-DD
        - month:   YYYY-MM
        - quarter: YYYY-Q
        """
        if not hasattr(period_obj, 'strftime'):
            # 容错：如果数据库返回不是日期/时间对象，直接 str
            return str(period_obj)

        if granularity == 'day':
            return period_obj.strftime('%Y-%m-%d')
        if granularity == 'month':
            return period_obj.strftime('%Y-%m')  # 月口径只保留到月
        if granularity == 'quarter':
            # 计算该日期的季度号（1..4）
            m = period_obj.month
            q = (m - 1) // 3 + 1
            return f"{period_obj.year}-{q}"
        return period_obj.strftime('%Y-%m-%d')

    # —— list：支持 granularity —— #
    def list(self, request, *args, **kwargs):
        granularity = request.query_params.get('granularity', 'day').lower()
        if granularity == 'day':
            # 原日快照（分页）
            return super().list(request, *args, **kwargs)

        # month / quarter 聚合
        base = self.filter_queryset(self.get_queryset())
        data = list(self._aggregate_by_period(base, granularity))

        result = []
        for row in data:
            period_str = self._format_period(row['period'], granularity)
            result.append({
                'period': period_str,
                'total_fee': str(row.get('total_fee') or '0'),
                'end_stock': row.get('end_stock'),
            })

        from rest_framework.response import Response
        return Response(result)


class RefrigerationFileDownloadView(viewsets.ModelViewSet):
    """
    CSV 导出（只读）
    - granularity=day：导出日快照
    - granularity=month/quarter：导出聚合结果
    """
    permission_classes = [SafeMethodsOnly]
    http_method_names = ['get', 'head', 'options']

    renderer_classes = (RefrigerationFileRenderCN,) + tuple(api_settings.DEFAULT_RENDERER_CLASSES)
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = RefrigerationFeeFilter
    ordering_fields = [
        'openid', 'ship_receive_time', 'create_time', 'update_time',
        'total_pallet_qty', 'refrigeration_fee'
    ]

    def get_queryset(self):
        openid = getattr(getattr(self.request, "auth", None), "openid", None) \
              or getattr(getattr(self.request, "user", None), "openid", None)
        if not openid:
            return RefrigerationFeeDetail.objects.none()
        return RefrigerationFeeDetail.objects.filter(openid=openid).order_by('-ship_receive_time', '-update_time')

    def get_serializer_class(self):
        return RefrigerationFeeGetSerializer

    def _pick_renderer(self, data_iterable, is_agg: bool):
        lang = self.request.META.get('HTTP_LANGUAGE')
        if is_agg:
            if lang == 'zh-hans':
                return RefrigerationAggFileRenderCN().render(data_iterable)
            return RefrigerationAggFileRenderEN().render(data_iterable)
        else:
            if lang == 'zh-hans':
                return RefrigerationFileRenderCN().render(data_iterable)
            return RefrigerationFileRenderEN().render(data_iterable)

    def list(self, request, *args, **kwargs):
        from datetime import datetime
        dt = datetime.now()
        granularity = request.query_params.get('granularity', 'day').lower()
        base_qs = self.filter_queryset(self.get_queryset())

        # —— 日快照导出 —— #
        if granularity == 'day':
            qs = base_qs.iterator(chunk_size=2000)

            def row_iter_day():
                for obj in qs:
                    yield {
                        'ship_receive_time': obj.ship_receive_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'total_pallet_qty': obj.total_pallet_qty,
                        'refrigeration_fee': str(obj.refrigeration_fee),
                        'creator': obj.creator,
                        'create_time': obj.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'update_time': obj.update_time.strftime('%Y-%m-%d %H:%M:%S'),
                    }

            renderer = self._pick_renderer(row_iter_day(), is_agg=False)
            resp = StreamingHttpResponse(renderer, content_type="text/csv")
            resp['Content-Disposition'] = "attachment; filename='refrigeration_fee_day_{}.csv'".format(
                dt.strftime('%Y%m%d%H%M%S%f')
            )
            return resp

        # —— 月/季聚合导出 —— #
        data = self._aggregate_by_period(base_qs, granularity)

        def row_iter_agg():
            openid = getattr(getattr(self.request, "auth", None), "openid", None) \
                  or getattr(getattr(self.request, "user", None), "openid", None)
            for row in data.iterator(chunk_size=2000):
                period_str = self._format_period(row['period'], granularity)
                yield {
                    'period': period_str,              # YYYY-MM 或 YYYY-Q
                    'total_fee': str(row.get('total_fee') or '0'),
                    'end_stock': row.get('end_stock'),
                }

        renderer = self._pick_renderer(row_iter_agg(), is_agg=True)
        resp = StreamingHttpResponse(renderer, content_type="text/csv")
        resp['Content-Disposition'] = "attachment; filename='refrigeration_fee_{}_{}.csv'".format(
            granularity, dt.strftime('%Y%m%d%H%M%S%f')
        )
        return resp





