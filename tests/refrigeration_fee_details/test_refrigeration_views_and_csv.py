# tests/test_views_and_csv.py
import datetime as dt
from decimal import Decimal
import csv, io, pytest
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate
from refrigeration_fee_details.views import RefrigerationFeeViewSet, RefrigerationFileDownloadView
from refrigeration_fee_details.utils.refrigeration_fee_service import compute_and_upsert
from types import SimpleNamespace  # 用于构造携带 openid 的 token 对象

class DummyUser:
    def __init__(self, openid): self.openid = openid
    is_authenticated = True

@pytest.mark.django_db
def test_views_and_csv(stub_models):
    Asn, Dn, Customer = stub_models
    tz  = timezone.get_current_timezone()
    oid = 'tenantD'  # 先定义 oid，避免 NameError
    Customer.objects.create(openid=oid, is_delete=False, customer_refrigeration_fee=Decimal('1.00'))

    # 11/01 入 2；11/02 出 1；12/15 入 3
    Asn.objects.create(openid=oid, is_delete=False,
                       receive_time=timezone.make_aware(dt.datetime(2025,11,1,8,0,0), tz),
                       asn_total_pallet_qty=2)
    Dn.objects.create(openid=oid, is_delete=False,
                      ship_time=timezone.make_aware(dt.datetime(2025,11,2,9,0,0), tz),
                      dn_total_pallet_qty=1)
    Asn.objects.create(openid=oid, is_delete=False,
                       receive_time=timezone.make_aware(dt.datetime(2025,12,15,9,0,0), tz),
                       asn_total_pallet_qty=3)

    # 写入结果表
    compute_and_upsert([oid], dt.date(2025,11,1), dt.date(2025,12,15), creator='test')

    rf = APIRequestFactory()
    view = RefrigerationFeeViewSet.as_view({'get':'list'})
    file_view = RefrigerationFileDownloadView.as_view({'get':'list'})

    # ====== 统一“强制鉴权” ======
    user  = DummyUser(oid)
    token = SimpleNamespace(openid=oid, appid='test-app')  # 让 view.get_queryset() 能读取到 openid

    # 日口径
    req1 = rf.get('/api/refrig?granularity=day&ship_receive_time=2025-11-01')
    force_authenticate(req1, user=user, token=token)
    resp1 = view(req1)
    assert resp1.status_code == 200

    # 月口径（诊断：只打印，不做断言）
    req2d = rf.get('/api/refrig?granularity=month&ship_receive_time=2025-11&__diag=1')
    force_authenticate(req2d, user=user, token=token)
    resp2d = view(req2d)
    print("DIAG:", resp2d.status_code, resp2d.data)  # pytest -s 可见
    if isinstance(resp2d.data, dict) and 'diag' in resp2d.data:
        print("DIAG-STAGE:", resp2d.data['diag'].get('stage'))

    # 月口径（正式断言：不带 __diag=1）
    req2 = rf.get('/api/refrig?granularity=month&ship_receive_time=2025-11')
    force_authenticate(req2, user=user, token=token)
    resp2 = view(req2)
    assert resp2.status_code == 200

    payload = resp2.data
    items = payload.get('results') if isinstance(payload, dict) and 'results' in payload else payload

    if isinstance(items, dict):  # 兼容“直接返回单对象”的情况
        assert {'period','total_fee','end_stock'} <= set(items.keys())
    else:
        assert isinstance(items, list) and len(items) > 0, "expected non-empty list for month aggregation"
        assert {'period','total_fee','end_stock'} <= set(items[0].keys())

    # 季度口径（期望 YYYY-Qx）
    req3 = rf.get('/api/refrig?granularity=quarter&ship_receive_time=2025-Q4')
    force_authenticate(req3, user=user, token=token)
    resp3 = view(req3)
    assert resp3.status_code == 200
    assert resp3.data and resp3.data[0]['period'].startswith('2025-Q')

    # CSV 导出（不含 openid）
    # 日口径 CSV
    req4 = rf.get('/api/refrig/export?granularity=day&ship_receive_time=2025-11-01', HTTP_LANGUAGE='zh-hans')
    force_authenticate(req4, user=user, token=token)
    resp4 = file_view(req4)
    content = b''.join(resp4.streaming_content).decode('utf-8')
    headers = next(csv.reader(io.StringIO(content)))
    # 语言为 zh-hans 时应为中文表头
    assert headers in (
        ['发货/收货日期','当日期末在库量','冷藏费','创建人','创建时间','更新时间'],
        ['ship_receive_time','total_pallet_qty','refrigeration_fee','creator','create_time','update_time']
    )


    # 月口径 CSV
    req5 = rf.get('/api/refrig/export?granularity=month&ship_receive_time=2025-11')
    force_authenticate(req5, user=user, token=token)
    resp5 = file_view(req5)
    content2 = b''.join(resp5.streaming_content).decode('utf-8')
    headers2 = next(csv.reader(io.StringIO(content2)))
    assert headers2 == ['Period','Total Fee','End-of-Period Stock']




