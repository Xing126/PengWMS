# 过滤器：支持按“日 / 月 / 季度”三种查询口径
# - granularity=day  时，ship_receive_time=YYYY-MM-DD
# - granularity=month时，ship_receive_time=YYYY-MM
# - granularity=quarter时，ship_receive_time=YYYY-Q   （Q ∈ {1,2,3,4}）
#
# 说明：
# 1) 我们继续沿用同一个查询参数 ship_receive_time，但根据 granularity 不同采用不同的解析与过滤逻辑；
# 2) 这样 views 的 get_queryset() 先得到“按口径裁剪后的日粒度数据”，再由视图决定是否做聚合；
# 3) 输入非法时返回空集合（避免抛异常影响接口）。

import datetime as _dt
import django_filters
from django.db.models import QuerySet
from .models import RefrigerationFeeDetail

class RefrigerationFeeFilter(django_filters.FilterSet):
    # 仍旧使用字符串参数接收
    ship_receive_time = django_filters.CharFilter()

    class Meta:
        model = RefrigerationFeeDetail
        fields = ["ship_receive_time"]

    def filter_queryset(self, queryset: QuerySet) -> QuerySet:
        # granularity 默认为 day；从 request.GET 读取
        req = getattr(self, "request", None)
        granularity = (getattr(req, "GET", {}) or {}).get("granularity", "day").strip().lower()

        cd = getattr(self, "form", None)
        cd = cd.cleaned_data if cd and hasattr(cd, "cleaned_data") else {}
        expr = (cd.get("ship_receive_time") or "").strip()

        # 未提供 ship_receive_time，直接返回（不限定时间）
        if not expr:
            return queryset

        # —— granularity=day：YYYY-MM-DD —— #
        if granularity == "day":
            try:
                d = _dt.datetime.strptime(expr, "%Y-%m-%d").date()
            except ValueError:
                return queryset.none()
            return queryset.filter(ship_receive_time__date=d)

        # —— granularity=month：YYYY-MM —— #
        if granularity == "month":
            try:
                d = _dt.datetime.strptime(expr, "%Y-%m")
            except ValueError:
                return queryset.none()
            return queryset.filter(
                ship_receive_time__year=d.year,
                ship_receive_time__month=d.month
            )

        # —— granularity=quarter：YYYY-Q（Q ∈ {1,2,3,4}） —— #
        if granularity == "quarter":
            # 允许 "2025-1" 或 "2025-Q1" 两种写法
            raw = expr.upper().replace("Q", "")
            parts = raw.split("-")
            if len(parts) != 2:
                return queryset.none()
            try:
                year = int(parts[0])
                q = int(parts[1])
                if q not in (1, 2, 3, 4):
                    return queryset.none()
            except Exception:
                return queryset.none()

            # 季度 → 月份集合
            q_months = {
                1: (1, 2, 3),
                2: (4, 5, 6),
                3: (7, 8, 9),
                4: (10, 11, 12),
            }[q]
            return queryset.filter(
                ship_receive_time__year=year,
                ship_receive_time__month__in=q_months
            )

        # 未知 granularity，返回空
        return queryset.none()

