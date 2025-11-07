# 只读接口：列表/详情/CSV 导出
# 在原基础上支持 granularity=day|month|quarter，并根据输入格式规范化 period 输出：
# - day：输入 YYYY-MM-DD；返回日快照（原有逻辑）
# - month：输入 YYYY-MM；   period 输出 YYYY-MM
# - quarter：输入 YYYY-Q；  period 输出 YYYY-Q
from django.http import StreamingHttpResponse
from rest_framework import viewsets, permissions
from rest_framework.settings import api_settings
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from django.db.models import Sum, OuterRef, Subquery, Max, F
from django.db.models.functions import TruncDate, TruncMonth, TruncQuarter, ExtractYear, ExtractMonth, ExtractDay, ExtractQuarter

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


# ===== 公共工具：供两个视图复用 =====

def _aggregate_by_period(base_qs, granularity: str):
    """
    对 base_qs 按日/月/季做聚合：
      - period: 分组键（日期/月/季度）
      - total_fee: Sum(refrigeration_fee)
      - end_stock: 该 period 最后一条日快照的 total_pallet_qty
    """
    from django.db.models import Sum, OuterRef, Subquery, Max, F
    from django.db.models.functions import (
        TruncDate, TruncMonth, TruncQuarter,
        ExtractYear, ExtractMonth, ExtractDay, ExtractQuarter
    )

    trunc_map = {
        'day': TruncDate('ship_receive_time'),
        'month': TruncMonth('ship_receive_time'),
        'quarter': TruncQuarter('ship_receive_time'),
    }
    trunc_fn = trunc_map.get(granularity, TruncDate('ship_receive_time'))

    # 外层：生成 period_dt + 数值键
    if granularity == 'day':
        outer = base_qs.annotate(
            y=ExtractYear('ship_receive_time'),
            m=ExtractMonth('ship_receive_time'),
            d=ExtractDay('ship_receive_time'),
            period_dt=trunc_fn,
        )
        group_keys = ['y', 'm', 'd']
    elif granularity == 'month':
        outer = base_qs.annotate(
            y=ExtractYear('ship_receive_time'),
            m=ExtractMonth('ship_receive_time'),
            period_dt=trunc_fn,
        )
        group_keys = ['y', 'm']
    elif granularity == 'quarter':
        outer = base_qs.annotate(
            y=ExtractYear('ship_receive_time'),
            q=ExtractQuarter('ship_receive_time'),
            period_dt=trunc_fn,
        )
        group_keys = ['y', 'q']
    else:
        outer = base_qs.annotate(
            y=ExtractYear('ship_receive_time'),
            m=ExtractMonth('ship_receive_time'),
            d=ExtractDay('ship_receive_time'),
            period_dt=TruncDate('ship_receive_time'),
        )
        group_keys = ['y', 'm', 'd']

    # 主聚合
    qs = (
        outer.values(*group_keys, 'period_dt')
        .annotate(total_fee=Sum('refrigeration_fee'))
    )

    #  修复的关键逻辑：子查询按真实字段过滤，不再用注解名
    inner_max_base = base_qs
    max_filters = {"ship_receive_time__year": OuterRef("y")}
    if 'm' in group_keys:
        max_filters["ship_receive_time__month"] = OuterRef("m")
    if 'd' in group_keys:
        max_filters["ship_receive_time__day"] = OuterRef("d")
    if 'q' in group_keys:
        inner_max_base = inner_max_base.annotate(_q=ExtractQuarter('ship_receive_time'))
        max_filters["_q"] = OuterRef("q")
    print("DEBUG max_filters keys:", list(max_filters.keys()))

    #  不再使用 values(*group_keys)
    #  用一层相关子查询直接拿 end_stock，避免 OuterRef 解析到 base_qs
    end_stock_subq_base = base_qs.annotate(
        y2=ExtractYear('ship_receive_time'),
        m2=ExtractMonth('ship_receive_time'),
        d2=ExtractDay('ship_receive_time'),
        q2=ExtractQuarter('ship_receive_time'),
    )

    end_stock_filters = {'y2': OuterRef('y')}
    if 'm' in group_keys:
        end_stock_filters['m2'] = OuterRef('m')
    if 'd' in group_keys:
        end_stock_filters['d2'] = OuterRef('d')
    if 'q' in group_keys:
        end_stock_filters['q2'] = OuterRef('q')

    end_stock_subq = (
        end_stock_subq_base
        .filter(**end_stock_filters)
        .order_by('-ship_receive_time')
        .values_list('total_pallet_qty', flat=True)[:1]
    )

    qs = (
        qs.annotate(end_stock=Subquery(end_stock_subq))
        .annotate(period=F('period_dt'))
        .values('period', 'total_fee', 'end_stock')
        .order_by('period')
    )
    return qs



def _format_period(period_obj, granularity: str) -> str:
    """
    输出 period 字符串：
      - day:     YYYY-MM-DD
      - month:   YYYY-MM
      - quarter: YYYY-Q
    """
    if not hasattr(period_obj, 'strftime'):
        return str(period_obj)

    if granularity == 'day':
        return period_obj.strftime('%Y-%m-%d')
    if granularity == 'month':
        return period_obj.strftime('%Y-%m')
    if granularity == 'quarter':
        m = period_obj.month
        q = (m - 1) // 3 + 1
        return f"{period_obj.year}-Q{q}"
    return period_obj.strftime('%Y-%m-%d')


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
        return RefrigerationFeeDetail.objects.filter(openid=openid).order_by(
            '-ship_receive_time', '-update_time'
        )

    def get_serializer_class(self):
        return RefrigerationFeeGetSerializer

    # views.py（节选：仅 list 方法的 month/quarter 分支增强诊断）
    def list(self, request, *args, **kwargs):
        granularity = request.query_params.get('granularity', 'day').lower()
        if granularity == 'day':
            return super().list(request, *args, **kwargs)

        diag = request.query_params.get('__diag') == '1'

        # —— 分段捕获：get_queryset —— #
        try:
            base_raw = self.get_queryset()
        except Exception as e:
            if diag:
                import traceback
                return Response({"diag": {
                    "stage": "get_queryset",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                }}, status=500)
            raise

        # —— 分段捕获：filter_queryset —— #
        try:
            base = self.filter_queryset(base_raw)
        except Exception as e:
            if diag:
                import traceback
                return Response({"diag": {
                    "stage": "filter_queryset",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "filter_backends": [getattr(b, "__name__", str(b)) for b in getattr(self, "filter_backends", [])],
                    "filterset_class": getattr(getattr(self, "filterset_class", None), "__name__", None),
                    "query_params": dict(request.query_params),
                }}, status=500)
            raise

        # —— 分段捕获：_aggregate_by_period —— #
        try:
            agg_qs = _aggregate_by_period(base, granularity)
            data = list(agg_qs)
        except Exception as e:
            if diag:
                import traceback
                agg_sql = None
                try:
                    agg_sql = str(agg_qs.query)  # noqa
                except Exception:
                    pass
                return Response({"diag": {
                    "stage": "aggregate",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "agg_sql": agg_sql,
                    "filtered_count": base.count(),
                }}, status=500)
            raise

        if diag:
            diag_payload = {
                "stage": "ok",
                "granularity": granularity,
                "filter_backends": [getattr(b, "__name__", str(b)) for b in getattr(self, "filter_backends", [])],
                "filterset_class": getattr(getattr(self, "filterset_class", None), "__name__", None),
                "base_count": base_raw.count(),
                "filtered_count": base.count(),
                "agg_sql": str(agg_qs.query),
                "sample_filtered": list(base.values("ship_receive_time","total_pallet_qty")[:3]),
                "sample_result": data[:2],
            }
            result = [{
                "period": _format_period(row["period"], granularity),
                "total_fee": str(row.get("total_fee") or "0"),
                "end_stock": row.get("end_stock"),
            } for row in data]
            return Response({"diag": diag_payload, "data": result})

        result = [{
            "period": _format_period(row["period"], granularity),
            "total_fee": str(row.get("total_fee") or "0"),
            "end_stock": row.get("end_stock"),
        } for row in data]
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
        return RefrigerationFeeDetail.objects.filter(openid=openid).order_by(
            '-ship_receive_time', '-update_time'
        )

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
        data = _aggregate_by_period(base_qs, granularity)

        def row_iter_agg():
            for row in data.iterator(chunk_size=2000):
                period_str = _format_period(row['period'], granularity)
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







