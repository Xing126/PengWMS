# refrigeration_fee_details/utils/refrigeration_fee_service.py
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Iterable, List, Tuple

from django.apps import apps
from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from refrigeration_fee_details.models import RefrigerationFeeDetail

MAX_WINDOW_DAYS = 180   # 防止无界窗口
LOOKBACK_DAYS   = 7     # 无历史时短回溯窗口

def _clamp(d_from: date, d_to: date) -> Tuple[date, date]:
    span = (d_to - d_from).days + 1
    if span > MAX_WINDOW_DAYS:
        d_from = d_to - timedelta(days=MAX_WINDOW_DAYS - 1)
    return d_from, d_to

def _days(d_from: date, d_to: date) -> List[date]:
    return [d_from + timedelta(days=i) for i in range((d_to - d_from).days + 1)]

def _day_end_ts(d: date):
    tz = timezone.get_current_timezone()
    return datetime.combine(d, datetime.max.time()).replace(microsecond=0, tzinfo=tz)

def fetch_daily_net_flow_bulk(openids: Iterable[str], d_from: date, d_to: date) -> Dict[Tuple[str, date], int]:
    """
    聚合同一天净流量：
      inbound = sum(AsnListModel.asn_total_pallet_qty) grouped by TruncDate(receive_time)
      outbound = sum(DnListModel.dn_total_pallet_qty) grouped by TruncDate(ship_time)
      net = inbound - outbound
    """
    Asn = apps.get_model('asn', 'AsnListModel')
    Dn  = apps.get_model('dn',  'DnListModel')

    # 入库：按 receive_time 的日期聚合 asn_total_pallet_qty
    in_rows = (Asn.objects
               .filter(openid__in=openids, is_delete=False,
                       receive_time__date__gte=d_from,
                       receive_time__date__lte=d_to)
               .annotate(day=TruncDate('receive_time'))
               .values('openid', 'day')
               .annotate(qty=Sum('asn_total_pallet_qty')))

    # 出库：按 ship_time 的日期聚合 dn_total_pallet_qty
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
    """
    上一日结存：
      1) 先从结果表找 anchor_day 之前最近一条记录的 total_pallet_qty；
      2) 若无历史，则回溯 LOOKBACK_DAYS 叠加净流量得到起点。
    """
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
    """
    读取每个 openid 的冷藏费单价：
      customer.ListModel.customer_refrigeration_fee
    """
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
    Django 4.1.2 兼容的幂等批量落库：
      - 批量聚合净流量
      - 逐日 O(D) 前缀和得到当日期末在库量
      - 计算冷藏费 = 单价 × 期末在库量
      - 一次查询现存记录 → bulk_update / bulk_create（事务内）
    """
    d_from, d_to = _clamp(d_from, d_to)
    days = _days(d_from, d_to)

    net = fetch_daily_net_flow_bulk(openids, d_from, d_to)   # {(openid, day): net}
    price_map = fetch_unit_prices(openids)                   # {openid: unit_price}

    # 目标行（内存构建）
    target_rows: Dict[Tuple[str, datetime], RefrigerationFeeDetail] = {}

    for oid in openids:
        stock_prev = opening_stock_for(oid, d_from)
        unit_price = price_map.get(oid, Decimal('0'))

        for d in days:
            net_today = int(net.get((oid, d), 0))
            end_stock = stock_prev + net_today
            fee = (Decimal(end_stock) * unit_price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            ts = _day_end_ts(d)
            target_rows[(oid, ts)] = RefrigerationFeeDetail(
                openid=oid,
                ship_receive_time=ts,
                total_pallet_qty=end_stock,
                refrigeration_fee=fee,
                creator=creator,
            )
            stock_prev = end_stock

    if not target_rows:
        return

    # 查询已存在记录（按 openid 与 ship_receive_time 集合过滤）
    openid_set = {k[0] for k in target_rows.keys()}
    ts_set     = {k[1] for k in target_rows.keys()}

    existing_qs = (RefrigerationFeeDetail.objects
                   .filter(openid__in=list(openid_set),
                           ship_receive_time__in=list(ts_set))
                   .only('openid', 'ship_receive_time', 'total_pallet_qty', 'refrigeration_fee', 'creator'))

    existing_map: Dict[Tuple[str, datetime], RefrigerationFeeDetail] = {}
    for obj in existing_qs:
        existing_map[(obj.openid, obj.ship_receive_time)] = obj

    to_create: List[RefrigerationFeeDetail] = []
    to_update: List[RefrigerationFeeDetail] = []

    for key, target in target_rows.items():
        if key in existing_map:
            obj = existing_map[key]
            obj.total_pallet_qty = target.total_pallet_qty
            obj.refrigeration_fee = target.refrigeration_fee
            obj.creator = target.creator
            to_update.append(obj)
        else:
            to_create.append(target)

    # 事务内批量持久化
    with transaction.atomic():
        if to_create:
            RefrigerationFeeDetail.objects.bulk_create(to_create, batch_size=1000)
        if to_update:
            now = timezone.now()
            for obj in to_update:
                obj.update_time = now  # 手动刷新更新时间
            RefrigerationFeeDetail.objects.bulk_update(
                to_update,
                fields=['total_pallet_qty', 'refrigeration_fee', 'creator', 'update_time'],
                batch_size=1000
            )
