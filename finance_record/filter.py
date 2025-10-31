from django_filters import FilterSet
from .models import FinanceRecord

class FinanceRecordFilter(FilterSet):
    """
    Only expose filters for:
    - asn_dn_code (primary key string for ASN/DN) : exact / iexact / contains / icontains
    - create_time / update_time : gt/gte/lt/lte/range (+ year/month/day/week_day for convenience)
    Style mirrors the original system's TransportationFeeListFilter.
    """
    class Meta:
        model = FinanceRecord
        fields = {
            "asn_dn_code": ['exact', 'iexact', 'contains', 'icontains'],
            "create_time": ['year', 'month', 'day', 'week_day', 'gt', 'gte', 'lt', 'lte', 'range'],
            "update_time": ['year', 'month', 'day', 'week_day', 'gt', 'gte', 'lt', 'lte', 'range'],
        }
