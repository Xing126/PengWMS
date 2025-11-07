# refrigeration_fee_details/utils/refrigeration_fee_service.py
from collections import defaultdict
from datetime import date, datetime, timedelta, time
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Iterable, List, Tuple

from django.apps import apps
from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from refrigeration_fee_details.models import RefrigerationFeeDetail

MAX_WINDOW_DAYS = 180
LOOKBACK_DAYS   = 7

def _clamp(d_from: date, d_to: date) -> Tuple[date, date]:
    span = (d_to - d_from).days + 1
    if span > MAX_WINDOW_DAYS:
        d_from = d_to - timedelta(days=MAX_WINDOW_DAYS - 1)
    return d_from, d_to

def _days(d_from: date, d_to: date) -> List[date]:
    return [d_from + timedelta(days=i) for i in range((d_to - d_from).days + 1)]

def _day_end_ts(d: date):
    tz = timezone.get_current_timezone()
    naive = datetime.combine(d, time(23, 59, 59))
    return timezone.make_aware(naive, tz)

def fetch_daily_net_flow_bulk(openids: Iterable[str], d_from: date, d_to: date) -> Dict[Tuple[str, date], int]:
    Asn = apps.get_model('asn', 'AsnListModel')
    Dn  = apps.get_model('dn',  'DnListModel')

    in_rows = (Asn.objects
               .filter(openid__in=openids, is_delete=False,
                       receive_time__date__gte=d_from,
                       receive_time__date__lte=d_to)
               .annotate(day=TruncDate('receive_time'))
               .values('openid', 'day')
               .annotate(qty=Sum('asn_total_pallet_qty')))

    out_rows = (Dn.objects
               .filter(openid__in=openids, is_delete=False,
                       ship_time__date__gte=d_from,
                       ship_time__date__lte=d_to)
               .annotate(day=TruncDate('ship_time'))
               .values('openid', 'day')
               .annotate(qty=Sum('dn_total_pallet_qty')))

    net: Dict[Tuple[str, date], int] = defaultdict(int)
    for r in in_rows:
        net[(r['openid'], r['day'])] += int(r['qty'] or 0)
    for r in out_rows:
        net[(r['openid'], r['day'])] -= int(r['qty'] or 0)
    return net

def opening_stock_for(openid: str, anchor_day: date) -> int:
    prev = (RefrigerationFeeDetail.objects
            .filter(openid=openid, ship_receive_time__date__lt=anchor_day)
            .order_by('-ship_receive_time')
            .values('total_pallet_qty')
            .first())
    if prev:
        return int(prev['total_pallet_qty'] or 0)

    start = anchor_day - timedelta(days=LOOKBACK_DAYS)
    hist = fetch_daily_net_flow_bulk([openid], start, anchor_day - timedelta(days=1))
    s = 0
    for (_oid, d), v in sorted(hist.items(), key=lambda x: x[0][1]):
        s += v
    return s

def fetch_unit_prices(openids: Iterable[str]) -> Dict[str, Decimal]:
    Customer = apps.get_model('customer', 'ListModel')
    rows = (Customer.objects
            .filter(openid__in=openids, is_delete=False)
            .values('openid', 'customer_refrigeration_fee'))
    price = {}
    for r in rows:
        price[r['openid']] = Decimal(str(r.get('customer_refrigeration_fee') or '0'))
    return price

def compute_and_upsert(openids: Iterable[str], d_from: date, d_to: date, creator='system'):
    """
    幂等 Upsert：自动识别唯一键
      - 若模型存在 `day` 字段，则按 (openid, day) 去重并写入 day
      - 否则按 (openid, ship_receive_time) 去重
    """
    d_from, d_to = _clamp(d_from, d_to)
    days = _days(d_from, d_to)

    net = fetch_daily_net_flow_bulk(openids, d_from, d_to)
    price_map = fetch_unit_prices(openids)

    # —— 动态识别是否有 day 字段 —— #
    model_fields = {f.name for f in RefrigerationFeeDetail._meta.get_fields()}
    has_day_field = 'day' in model_fields

    # 目标记录缓存：键根据唯一键选择 (openid, day) 或 (openid, ts)
    target_rows: Dict[Tuple[str, object], RefrigerationFeeDetail] = {}

    for oid in openids:
        stock_prev = opening_stock_for(oid, d_from)
        unit_price = price_map.get(oid, Decimal('0'))

        for d in days:
            net_today = int(net.get((oid, d), 0))
            end_stock = stock_prev + net_today
            fee = (Decimal(end_stock) * unit_price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            ts = _day_end_ts(d)

            kwargs = dict(
                openid=oid,
                ship_receive_time=ts,
                total_pallet_qty=end_stock,
                refrigeration_fee=fee,
                creator=creator,
            )
            if has_day_field:
                kwargs['day'] = d  # 与唯一索引保持一致

            obj = RefrigerationFeeDetail(**kwargs)
            key = (oid, d) if has_day_field else (oid, ts)
            target_rows[key] = obj
            stock_prev = end_stock

    if not target_rows:
        return

    # —— 事务内：先删后插，避免任何唯一冲突 —— #
    with transaction.atomic():
        # 删除本次窗口内、指定 openids 的旧数据
        RefrigerationFeeDetail.objects.filter(
            openid__in=list(openids),
            ship_receive_time__date__gte=d_from,
            ship_receive_time__date__lte=d_to,
        ).delete()

        # 统一设置 update_time（如果模型没有 auto_now）
        now = timezone.now()
        objs = list(target_rows.values())
        for obj in objs:
            obj.update_time = now

        # 整批重建
        RefrigerationFeeDetail.objects.bulk_create(objs, batch_size=1000)


