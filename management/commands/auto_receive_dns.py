# dn/management/commands/auto_receive_dns.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from django.conf import settings  # 读取 settings
from dn.models import DnListModel, DnDetailModel

DEFAULT_DAYS = 7  # 兜底默认值

class Command(BaseCommand):
    help = "Auto confirm in-transit DNs after timeout. Uses settings.DN_AUTO_RECEIVE_DAYS (default 7). "\
           "You can override with --days."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=None, help="Override timeout days")

    def handle(self, *args, **options):
        # 优先顺序：命令行 --days > settings.DN_AUTO_RECEIVE_DAYS > 默认 7
        days = options["days"] or getattr(settings, "DN_AUTO_RECEIVE_DAYS", DEFAULT_DAYS)

        threshold = timezone.now() - timedelta(days=days)
        count_dn = 0
        count_detail = 0
        self.stdout.write(f"⏳ Checking DNs older than {days} days ...")

        with transaction.atomic():
            dns = (DnListModel.objects
                   .select_for_update(skip_locked=True)
                   .filter(dn_status=DnListModel.STATUS_INTRANSIT,
                           update_time__lte=threshold,
                           is_delete=False))

            for dn in dns:
                details = list(DnDetailModel.objects.select_for_update().filter(
                    openid=dn.openid,
                    dn_code=dn.dn_code,
                    dn_status=DnListModel.STATUS_INTRANSIT,
                    is_delete=False
                ))
                if not details:
                    continue

                for d in details:
                    intransit = int(d.intransit_qty or 0)
                    d.delivery_actual_qty = intransit
                    d.delivery_damage_qty = 0
                    d.delivery_more_qty = 0
                    d.delivery_shortage_qty = 0
                    d.intransit_qty = 0
                    d.dn_status = DnListModel.STATUS_DELIVERED
                    d.save(update_fields=[
                        "delivery_actual_qty", "delivery_damage_qty",
                        "delivery_more_qty", "delivery_shortage_qty",
                        "intransit_qty", "dn_status"
                    ])
                    count_detail += 1

                dn.dn_status = DnListModel.STATUS_DELIVERED
                dn.signed_by = "system_auto"
                dn.sign_time = timezone.now()
                dn.save(update_fields=["dn_status", "signed_by", "sign_time"])
                count_dn += 1

        self.stdout.write(self.style.SUCCESS(
            f"✅ Auto receive done: DNs={count_dn}, details={count_detail} (days={days})"
        ))
