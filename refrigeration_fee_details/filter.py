
# 过滤器：支持按“日 / 月 / 季度”三种查询口径
# - granularity=day  时，ship_receive_time=YYYY-MM-DD
# - granularity=month时，ship_receive_time=YYYY-MM
# - granularity=quarter时，ship_receive_time=YYYY-Q   （Q ∈ {1,2,3,4}）
#
# 说明：
# 1) 继续沿用同一个查询参数 ship_receive_time，但根据 granularity 不同采用不同的解析与过滤逻辑；
# 2) views 的 get_queryset() 先得到“按口径裁剪后的日粒度数据”，再由视图决定是否做聚合；
# 3) 输入非法时返回空集合（避免抛异常影响接口）。

import datetime as _dt
import django_filters
from django.db.models import QuerySet
from .models import RefrigerationFeeDetail
import logging
logger = logging.getLogger(__name__)


class RefrigerationFeeFilter(django_filters.FilterSet):
    # 字符串参数接收，便于按口径自定义解析
    ship_receive_time = django_filters.CharFilter()

    class Meta:
        model = RefrigerationFeeDetail
        fields = ["ship_receive_time"]

    def filter_queryset(self, queryset: QuerySet) -> QuerySet:
        # 从 request.GET 读取 granularity（默认 day）
        req = getattr(self, "request", None)
        granularity = (getattr(req, "GET", {}) or {}).get("granularity", "day")
        granularity = (granularity or "").strip().lower()

        cd = getattr(self, "form", None)
        cd = cd.cleaned_data if cd and hasattr(cd, "cleaned_data") else {}
        expr = (cd.get("ship_receive_time") or "").strip()

        logger.info("[RefrigFeeFilter] in: granularity=%s expr=%s before=%s",
                    granularity, expr, queryset.count())

        # 未提供 ship_receive_time，直接返回（不限定时间）
        if not expr:
            logger.info("[RefrigFeeFilter] skip(no expr) after=%s", queryset.count())
            return queryset

        try:
            if granularity == "day":
                d = _dt.datetime.strptime(expr, "%Y-%m-%d").date()
                qs = queryset.filter(ship_receive_time__date=d)
            elif granularity == "month":
                d = _dt.datetime.strptime(expr, "%Y-%m")
                qs = queryset.filter(ship_receive_time__year=d.year,
                                     ship_receive_time__month=d.month)
            elif granularity == "quarter":
                raw = expr.upper().replace("Q", "")
                parts = raw.split("-") if "-" in raw else [raw[:4], raw[4:]] if len(raw) >= 5 else []
                if len(parts) != 2:
                    logger.warning("[RefrigFeeFilter] bad quarter expr: %s", expr)
                    return queryset.none()
                year = int(parts[0]); q = int(parts[1])
                if q not in (1,2,3,4):
                    logger.warning("[RefrigFeeFilter] bad quarter num: %s", q)
                    return queryset.none()
                q_months = {1:(1,2,3),2:(4,5,6),3:(7,8,9),4:(10,11,12)}[q]
                qs = queryset.filter(ship_receive_time__year=year,
                                     ship_receive_time__month__in=q_months)
            else:
                logger.warning("[RefrigFeeFilter] unknown granularity: %s", granularity)
                return queryset.none()
        except Exception as e:
            logger.exception("[RefrigFeeFilter] exception while filtering: %s", e)
            return queryset.none()

        logger.info("[RefrigFeeFilter] out:  after=%s", qs.count())
        return qs
