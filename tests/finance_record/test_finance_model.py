import datetime as dt
from decimal import Decimal
import pytest
from django.utils import timezone
from finance_record.models import FinanceRecord

@pytest.mark.django_db
def test_save_compute_fees_from_asn(stub_models):
    Asn, Dn, Customer = stub_models
    tz = timezone.get_current_timezone()
    oid = 'tenantA'

    # 单价
    Customer.objects.create(
        openid=oid, is_delete=False, customer_name='Acme',
        customer_film_laminating_fee=Decimal('2.50'),
        customer_loading_fee=Decimal('1.00'),
        customer_bank_account='6222-XXX'
    )

    # ASN 源数量：围膜=3，总=10
    Asn.objects.create(
        asn_code='ASN001', openid=oid, is_delete=False,
        stretch_wrapped_pallet_qty=3, total_pallet_qty=10
    )

    # 新建 FinanceRecord（source_type=ASN）
    rec = FinanceRecord(
        asn_dn_code='ASN001',
        source_type='ASN',
        openid=oid,
        customer_name='Acme',
        customer_other_fee=Decimal('5.00'),
        ship_receive_time=timezone.make_aware(dt.datetime(2025,11,1,10,0,0), tz),
        creator='tester'
    )
    rec.save()  # 触发数量解析 + 单价提取 + 费用计算

    assert rec.film_laminating_fee == Decimal('7.50')   # 3 * 2.50
    assert rec.loading_fee == Decimal('10.00')          # 10 * 1.00
    assert rec.total_fee == Decimal('22.50')            # 7.50 + 10.00 + 5.00

@pytest.mark.django_db
def test_save_compute_fees_from_dn(stub_models):
    Asn, Dn, Customer = stub_models
    tz = timezone.get_current_timezone()
    oid = 'tenantB'

    Customer.objects.create(
        openid=oid, is_delete=False, customer_name='Beta',
        customer_film_laminating_fee=Decimal('1.20'),
        customer_loading_fee=Decimal('0.80'),
        customer_bank_account='9555-YYY'
    )
    # DN 源数量：围膜=2，总=4
    Dn.objects.create(
        dn_code='DN001', openid=oid, is_delete=False,
        stretch_wrapped_pallet_qty=2, total_pallet_qty=4, customer='Beta'
    )

    rec = FinanceRecord(
        asn_dn_code='DN001', source_type='DN',
        openid=oid, customer_name='Beta',
        customer_other_fee=Decimal('0.10'),
        ship_receive_time=timezone.make_aware(dt.datetime(2025,11,2,9,0,0), tz),
        creator='tester'
    )
    rec.save()

    assert rec.film_laminating_fee == Decimal('2.40')   # 2 * 1.20
    assert rec.loading_fee == Decimal('3.20')           # 4 * 0.80
    assert rec.total_fee == Decimal('5.70')             # 2.40 + 3.20 + 0.10
