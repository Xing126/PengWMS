# finance_record/filter.py
import datetime as _dt
import calendar as _cal
import django_filters
from django.db.models import QuerySet
from finance_record.models import FinanceRecord


class FinanceRecordFilter(django_filters.FilterSet):
    """
    Mutually exclusive search:
      - Precise order number: ?asn_dn_code=DN2025-0001
      - Fuzzy time: ?ship_receive_time=2025
                  ?ship_receive_time=2025-10
                  ?ship_receive_time=2025-10-31
                  ?ship_receive_time=2025-10-31T14
                  ?ship_receive_time=2025-10-31T14:30

    Rules:
      1) If asn_dn_code is provided, only perform exact matching search by order number, ignore ship_receive_time.
      2) Otherwise, if ship_receive_time is provided, parse it as a fuzzy time into a range for search.
      3) If neither parameter is provided, return the original QuerySet (no filtering).
    """
    # Two available parameters at the form level (final filtering is handled uniformly in filter_queryset)
    asn_dn_code = django_filters.CharFilter()
    ship_receive_time = django_filters.CharFilter()

    class Meta:
        model = FinanceRecord
        fields = ["asn_dn_code", "ship_receive_time"]

    def filter_queryset(self, queryset: QuerySet) -> QuerySet:
        # Read cleaned parameters
        cd = getattr(self, "form", None)
        cd = cd.cleaned_data if cd and hasattr(cd, "cleaned_data") else {}

        code = (cd.get("asn_dn_code") or "").strip()
        time_expr = (cd.get("ship_receive_time") or "").strip()

        # Priority: Exact order number matching
        if code:
            return queryset.filter(asn_dn_code=code)

        # Next: Fuzzy time matching (parse "prefix-style time" into a range)
        if time_expr:
            start, end = self._fuzzy_bounds(time_expr)
            if start and end:
                # Half-open interval [start, end)
                return queryset.filter(
                    ship_receive_time__gte=start,
                    ship_receive_time__lt=end
                )

        # No filtering parameters, return original set
        return queryset

    # ---------- Utility methods ----------

    @staticmethod
    def _fuzzy_bounds(expr: str):
        """
        Parse 'YYYY' / 'YYYY-MM' / 'YYYY-MM-DD' / 'YYYY-MM-DDTHH(:MM)' etc. "prefix-style time"
        into a half-open interval [start, next_tick), ensuring precision does not exceed minutes.
        Return (None, None) on parsing failure.
        """
        # Uniformly replace 't' -> 'T' for splitting
        expr = expr.strip().replace("t", "T")

        # Year
        if _match(expr, r"^\d{4}$"):
            year = int(expr)
            start = _dt.datetime(year, 1, 1, 0, 0, 0)
            end = _dt.datetime(year + 1, 1, 1, 0, 0, 0)
            return start, end

        # Year-Month
        if _match(expr, r"^\d{4}-\d{2}$"):
            year, month = map(int, expr.split("-"))
            start = _dt.datetime(year, month, 1, 0, 0, 0)
            last_day = _cal.monthrange(year, month)[1]
            end = _dt.datetime(year, month, last_day, 23, 59, 59) + _dt.timedelta(seconds=1)
            return start, end

        # Year-Month-Day
        if _match(expr, r"^\d{4}-\d{2}-\d{2}$"):
            year, month, day = map(int, expr.split("-"))
            start = _dt.datetime(year, month, day, 0, 0, 0)
            end = start + _dt.timedelta(days=1)
            return start, end

        # Date + 'T' + Hour (precise to hour)
        if _match(expr, r"^\d{4}-\d{2}-\d{2}T\d{2}$"):
            dt = _dt.datetime.strptime(expr, "%Y-%m-%dT%H")
            start = dt.replace(minute=0, second=0)
            end = start + _dt.timedelta(hours=1)
            return start, end

        # Date + 'T' + Hour:Minute (precise to minute)
        if _match(expr, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$"):
            dt = _dt.datetime.strptime(expr, "%Y-%m-%dT%H:%M")
            start = dt.replace(second=0)
            end = start + _dt.timedelta(minutes=1)
            return start, end

        # Parsing failure (seconds are discarded to ensure not precise to seconds)
        return None, None


def _match(text: str, pattern: str) -> bool:
    """Simple regex matching (to avoid introducing re dependency into the global namespace)"""
    import re as _re
    return bool(_re.match(pattern, text))
