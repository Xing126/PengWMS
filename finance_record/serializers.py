# finance_record/serializers.py
from django.apps import apps
from rest_framework import serializers
from finance_record.models import FinanceRecord


class FinanceGetSerializer(serializers.ModelSerializer):
    asn_dn_code = serializers.CharField(read_only=True, required=False)
    source_type = serializers.CharField(read_only=True, required=False)
    openid = serializers.CharField(read_only=True, required=False)

    customer_refrigeration_fee = serializers.IntegerField(read_only=True, required=False)
    customer_loading_fee = serializers.IntegerField(read_only=True, required=False)
    customer_film_laminating_fee = serializers.IntegerField(read_only=True, required=False)

    is_delete = serializers.BooleanField(read_only=True, required=False)
    create_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    update_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')

    class Meta:
        model = FinanceRecord
        # Keep bank account out of UI responses on purpose.
        fields = (
            'asn_dn_code',
            'source_type',
            'openid',
            'customer_refrigeration_fee',
            'customer_film_laminating_fee',
            'customer_loading_fee',
            'is_delete',
            'create_time',
            'update_time',
            # If your model also has a 'customer' field, you may add it here for display:
            # 'customer',
        )
        read_only_fields = fields


class FinanceRecordRenderSerializer(serializers.ModelSerializer):
    customer_bank_account = serializers.SerializerMethodField()

    asn_dn_code = serializers.CharField(read_only=True, required=False)
    source_type = serializers.CharField(read_only=True, required=False)
    openid = serializers.CharField(read_only=True, required=False)

    customer_refrigeration_fee = serializers.IntegerField(read_only=True, required=False)
    customer_loading_fee = serializers.IntegerField(read_only=True, required=False)
    customer_film_laminating_fee = serializers.IntegerField(read_only=True, required=False)

    create_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    update_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')

    class Meta:
        model = FinanceRecord
        fields = (
            'asn_dn_code',
            'source_type',
            'openid',
            'customer_bank_account',               # included in export only
            'customer_refrigeration_fee',
            'customer_film_laminating_fee',
            'customer_loading_fee',
            'create_time',
            'update_time',
            # If available on FinanceRecord, you can include 'customer' as well:
            # 'customer',
        )
        read_only_fields = fields

    def get_customer_bank_account(self, obj):
        """
        Resolve bank account from Customer.ListModel at export time.

        Priority:
        1) If FinanceRecord has a 'customer' field, use (openid + customer_name).
        2) Else if this is a DN record, resolve customer by dn_code -> DnListModel,
           then query Customer by (openid + customer_name).
        3) Otherwise return empty string.
        """
        # Customer model (your uploaded Customer models.py defines the bank account field)
        Customer = apps.get_model('customer', 'ListModel')

        # Case 1: direct match if FinanceRecord contains a 'customer' field
        customer_name = getattr(obj, 'customer', None)
        if customer_name:
            bank = Customer.objects.filter(
                openid=obj.openid,
                customer_name=customer_name
            ).values_list('customer_bank_account', flat=True).first()
            return bank or ''

        # Case 2: infer from DN document when source_type == 'DN'
        if obj.source_type == 'DN':
            DnListModel = apps.get_model('dn', 'DnListModel')
            dn = DnListModel.objects.filter(dn_code=obj.asn_dn_code).values('customer', 'openid').first()
            if dn:
                bank = Customer.objects.filter(
                    openid=dn.get('openid') or obj.openid,
                    customer_name=dn.get('customer') or ''
                ).values_list('customer_bank_account', flat=True).first()
                return bank or ''

        # Fallback: nothing found
        return ''
