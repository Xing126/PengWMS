# Celery 定时任务：每日/每小时自动计算
# refrigeration_fee_details/tasks.py
from celery import shared_task
from datetime import date, timedelta
from django.apps import apps
from refrigeration_fee_details.utils.refrigeration_fee_service import compute_and_upsert

@shared_task
def recompute_yesterday_for_all_openids():
    """
    对所有 openid 计算“昨天”的冷藏费用（收/发货两表并集）
    """
    Asn = apps.get_model('asn', 'AsnListModel')
    Dn  = apps.get_model('dn',  'DnListModel')

    asn_oids = set(Asn.objects.values_list('openid', flat=True).distinct())
    dn_oids  = set(Dn.objects.values_list('openid', flat=True).distinct())
    all_oids = list(asn_oids | dn_oids)

    if not all_oids:
        return
    y = date.today() - timedelta(days=1)
    compute_and_upsert(all_oids, y, y, creator='scheduler')

