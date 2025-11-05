# 管理命令：运维/人工重算指定 openid 集与时间范围
# refrigeration_fee_details/management/commands/recompute_refrigeration_fee.py
from django.core.management.base import BaseCommand
from datetime import datetime
from refrigeration_fee_details.utils.refrigeration_fee_service import compute_and_upsert

class Command(BaseCommand):
    help = "Recalculate refrigeration fees for the specified openid list and date range: e.g. --openids=oid1,oid2 --from=2025-11-01 --to=2025-11-30"

    def add_arguments(self, parser):
        parser.add_argument('--openids', type=str, required=True, help='Comma-separated list of openids')
        parser.add_argument('--from', dest='date_from', type=str, required=True, help='Start date YYYY-MM-DD')
        parser.add_argument('--to', dest='date_to', type=str, required=True, help='End date YYYY-MM-DD')
        parser.add_argument('--creator', type=str, default='admin', help='Creator tag for record writing')

    def handle(self, *args, **opts):
        openids = [x.strip() for x in opts['openids'].split(',') if x.strip()]
        d_from = datetime.strptime(opts['date_from'], '%Y-%m-%d').date()
        d_to = datetime.strptime(opts['date_to'], '%Y-%m-%d').date()
        creator = opts.get('creator') or 'admin'

        compute_and_upsert(openids, d_from, d_to, creator=creator)
        self.stdout.write(self.style.SUCCESS(f'done: {openids}  {d_from} ~ {d_to}'))
