# test_finance_views_and_csv.py
import datetime as dt, csv, io, pytest
from decimal import Decimal
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate
from finance_record.models import FinanceRecord
from finance_record.views import FinanceRecordViewSet, FinancefileDownloadView
from types import SimpleNamespace

class DummyUser:
    def __init__(self, openid): self.openid = openid
    is_authenticated = True

@pytest.mark.django_db
def test_list_readonly_and_export_with_bank(stub_models):
    Asn, Dn, Customer = stub_models
    rf = APIRequestFactory()
    tz = timezone.get_current_timezone()
    oid = 'tenantX'

    # Customer：单价 + 银行账号
    Customer.objects.create(openid=oid, is_delete=False, customer_name='ACME',
                            customer_film_laminating_fee=Decimal('2.00'),
                            customer_loading_fee=Decimal('1.00'),
                            customer_bank_account='6214-ACME-123')

    # DN 源单据，且指向 customer='ACME'，用于导出时二跳银行账号解析
    Dn.objects.create(dn_code='DN888', openid=oid, is_delete=False,
                      stretch_wrapped_pallet_qty=1, total_pallet_qty=2, customer='ACME')

    # 建 FinanceRecord 并保存（触发费用计算）
    obj = FinanceRecord(
        asn_dn_code='DN888', source_type='DN', openid=oid, customer_name='ACME',
        ship_receive_time=timezone.make_aware(dt.datetime(2025,11,3,12,0), tz), creator='u'
    )
    obj.save()

    # ---- 列表视图：不包含银行账号（GetSerializer） ----
    list_view = FinanceRecordViewSet.as_view({'get': 'list'})
    req = rf.get('/api/finance-record/?ship_receive_time=2025-11-03')
    req.user = DummyUser(oid)
    resp = list_view(req)
    assert resp.status_code == 200
    payload = resp.data
    if isinstance(payload, dict):
        items = (
            payload.get('results')
            or payload.get('data')
            or payload.get('list')
            or payload.get('rows')
        )
        if items is None:
            items = list(payload) if not isinstance(payload, list) else payload
    else:
        items = payload

    row = items[0]

    assert 'customer_bank_account' not in row  # 只读列表不应暴露银行账号

    # ---- 导出视图：CSV 包含银行账号（RenderSerializer + files.py 头） ----
    export_view = FinancefileDownloadView.as_view({'get': 'list'})

    # 中文表头
    req2 = rf.get('/api/finance-record/export/?asn_dn_code=DN888', HTTP_LANGUAGE='zh-hans')
    force_authenticate(req2, user=DummyUser(oid), token=SimpleNamespace(openid=oid, appid='test-app'))
    resp2 = export_view(req2) 

    # 兼容 StreamingHttpResponse 或 DRF Response
    if hasattr(resp2, 'streaming_content'):
        raw_cn = b''.join(resp2.streaming_content)
    else:
        resp2.render()          # 让 DRF Response 完成渲染
        raw_cn = resp2.content  # 读取字节

    content_cn = raw_cn.decode('utf-8')
    headers_cn = next(csv.reader(io.StringIO(content_cn)))
    assert headers_cn[0:5] == ['单据编号（ASN/DN）','来源类型','客户名称','客户银行账号','围膜库板数']

    # 英文表头（显式指定为英文，避免环境默认或上一次请求影响）
    req3 = rf.get('/api/finance-record/export/?asn_dn_code=DN888', HTTP_LANGUAGE='en')
    force_authenticate(req3, user=DummyUser(oid), token=SimpleNamespace(openid=oid, appid='test-app'))
    resp3 = export_view(req3)

    # 兼容 StreamingHttpResponse / DRF Response 的读取方式（你已加）
    if hasattr(resp3, 'streaming_content'):
       raw_en = b''.join(resp3.streaming_content)
    else:
       resp3.render()
       raw_en = resp3.content

    content_en = raw_en.decode('utf-8')
    reader = csv.reader(io.StringIO(content_en))
    headers_en = next(reader)
    row_en = next(reader)
    assert headers_en[0:5] == [
       'ASN/DN Code','Source Type','Customer Name','Customer Bank Account','Stretch Wrapped Pallet Qty'
    ]
    assert row_en[3] == '6214-ACME-123'


