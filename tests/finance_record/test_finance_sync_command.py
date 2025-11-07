import pytest
from django.core.management import call_command
from finance_record.models import FinanceRecord

@pytest.mark.django_db
def test_sync_finance_keys(stub_models):
    Asn, Dn, Customer = stub_models
    # 造源单据
    Asn.objects.create(asn_code='A-1', openid='o1', is_delete=False)
    Dn.objects.create(dn_code='D-1',  openid='o1', is_delete=False)

    # 初次同步
    call_command('sync_finance_keys')
    assert FinanceRecord.objects.filter(asn_dn_code='A-1', source_type='ASN', openid='o1').exists()
    assert FinanceRecord.objects.filter(asn_dn_code='D-1', source_type='DN',  openid='o1').exists()

    # 再次同步（幂等：不重复新增）
    count1 = FinanceRecord.objects.count()
    call_command('sync_finance_keys')
    count2 = FinanceRecord.objects.count()
    assert count1 == count2
