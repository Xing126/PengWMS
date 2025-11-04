# finance_record/filter.py
import datetime as _dt
import django_filters
from django.db.models import QuerySet
from finance_record.models import FinanceRecord


class FinanceRecordFilter(django_filters.FilterSet):
    
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
        date_expr = (cd.get("ship_receive_time") or "").strip()

        # Priority: Exact order number matching
        if code:
            return queryset.filter(asn_dn_code=code)

        # Next: Fuzzy time matching (parse "prefix-style time" into a range)
        if date_expr:
            try:
                date_obj = _dt.datetime.strptime(date_expr, "%Y-%m-%d").date()
            except ValueError:
                return queryset.none()
            return queryset.filter(ship_receive_time__date=date_obj)

        # No filtering parameters, return original set
        return queryset
    