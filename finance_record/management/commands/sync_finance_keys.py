from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import transaction
from finance_record.models import FinanceRecord

class Command(BaseCommand):
    """
    Batch synchronize ASN and DN order numbers into FinanceRecord.asn_dn_code.
    This script is safe to run multiple times (idempotent).
    """
    help = "Synchronize ASN/DN codes into FinanceRecord.asn_dn_code (read-only table key initialization)"

    def handle(self, *args, **options):
        # Load ASN and DN models dynamically to avoid circular imports
        AsnListModel = apps.get_model('asn', 'AsnListModel')
        DnListModel = apps.get_model('dn', 'DnListModel')

        created_asn = 0
        created_dn = 0

        self.stdout.write(self.style.WARNING("Starting synchronization of ASN and DN codes..."))

        with transaction.atomic():
            # --- Synchronize ASN (Inbound Orders) ---
            for asn in AsnListModel.objects.all().only('asn_code', 'openid'):
                code = getattr(asn, 'asn_code', None)
                if not code:
                    continue
                openid = getattr(asn, 'openid', '') or ''
                obj, created = FinanceRecord.objects.update_or_create(
                    asn_dn_code=code,
                    defaults={
                        'source_type': 'ASN',
                        'openid': openid,
                        'is_delete': False,
                    }
                )
                if created:
                    created_asn += 1

            # --- Synchronize DN (Outbound Orders) ---
            for dn in DnListModel.objects.all().only('dn_code', 'openid'):
                code = getattr(dn, 'dn_code', None)
                if not code:
                    continue
                openid = getattr(dn, 'openid', '') or ''
                obj, created = FinanceRecord.objects.update_or_create(
                    asn_dn_code=code,
                    defaults={
                        'source_type': 'DN',
                        'openid': openid,
                        'is_delete': False,
                    }
                )
                if created:
                    created_dn += 1

        self.stdout.write(self.style.SUCCESS(
            f"Synchronization completed successfully: {created_asn} ASN records added, {created_dn} DN records added."
        ))