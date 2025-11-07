# tests/test_service.py
import datetime as dt
from decimal import Decimal
import pytest
from django.utils import timezone
from refrigeration_fee_details.models import RefrigerationFeeDetail
from refrigeration_fee_details.utils.refrigeration_fee_service import compute_and_upsert

@pytest.mark.django_db
def test_compute_and_upsert_basic(stub_models):
    Asn, Dn, Customer = stub_models
    tz  = timezone.get_current_timezone()
    oid = 'tenantA'

    # 单价
    Customer.objects.create(openid=oid, is_delete=False, customer_refrigeration_fee=Decimal('0.50'))

    # 11/01 入 10；11/02 出 3；11/03 入 5
    Asn.objects.create(openid=oid, is_delete=False,
                       receive_time=timezone.make_aware(dt.datetime(2025,11,1,10,0,0), tz),
                       asn_total_pallet_qty=10)
    Dn.objects.create(openid=oid, is_delete=False,
                      ship_time=timezone.make_aware(dt.datetime(2025,11,2,15,0,0), tz),
                      dn_total_pallet_qty=3)
    Asn.objects.create(openid=oid, is_delete=False,
                       receive_time=timezone.make_aware(dt.datetime(2025,11,3,9,30,0), tz),
                       asn_total_pallet_qty=5)

    compute_and_upsert([oid], dt.date(2025,11,1), dt.date(2025,11,3), creator='test')

    rows = RefrigerationFeeDetail.objects.filter(openid=oid).order_by('ship_receive_time')
    assert rows.count() == 3
    assert rows[0].total_pallet_qty == 10 and rows[0].refrigeration_fee == Decimal('5.00')
    assert rows[1].total_pallet_qty == 7  and rows[1].refrigeration_fee == Decimal('3.50')
    assert rows[2].total_pallet_qty == 12 and rows[2].refrigeration_fee == Decimal('6.00')

    # 幂等：重复执行不新增
    compute_and_upsert([oid], dt.date(2025,11,1), dt.date(2025,11,3), creator='again')
    assert RefrigerationFeeDetail.objects.filter(openid=oid).count() == 3
