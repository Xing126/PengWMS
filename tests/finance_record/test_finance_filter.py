import datetime as dt
import pytest
from django.utils import timezone
from django.test import RequestFactory
from finance_record.models import FinanceRecord
from finance_record.filter import FinanceRecordFilter

@pytest.mark.django_db
def test_filter_exact_code_then_date():
    rf = RequestFactory()
    oid = 'tenantF'
    tz = timezone.get_current_timezone()

    FinanceRecord.objects.create(
        asn_dn_code='ASN100', source_type='ASN', openid=oid,
        customer_name='Foo', ship_receive_time=timezone.make_aware(dt.datetime(2025,11,1,8,0), tz),
        creator='t'
    )
    FinanceRecord.objects.create(
        asn_dn_code='DN200', source_type='DN', openid=oid,
        customer_name='Bar', ship_receive_time=timezone.make_aware(dt.datetime(2025,11,1,9,0), tz),
        creator='t'
    )

    # 1) 按单号精确
    data = {'asn_dn_code': 'ASN100', 'ship_receive_time': '2025-11-01'}
    f = FinanceRecordFilter(data=data, queryset=FinanceRecord.objects.all())
    qs = f.qs
    assert qs.count() == 1 and qs.first().asn_dn_code == 'ASN100'

    # 2) 无单号 -> 按日期
    data = {'ship_receive_time': '2025-11-01'}
    f = FinanceRecordFilter(data=data, queryset=FinanceRecord.objects.all())
    assert f.qs.count() == 2

    # 3) 非法日期 -> 空
    data = {'ship_receive_time': '2025-13-99'}
    f = FinanceRecordFilter(data=data, queryset=FinanceRecord.objects.all())
    assert f.qs.count() == 0
