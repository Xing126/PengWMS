# finance_record/serializers.py
from django.apps import apps
from rest_framework import serializers
from finance_record.models import FinanceRecord


class FinanceGetSerializer(serializers.ModelSerializer):
    asn_dn_code = serializers.CharField(read_only=True, required=False)
    source_type = serializers.CharField(read_only=True, required=False)
    openid = serializers.CharField(read_only=True, required=False)
    customer_name = serializers.CharField(read_only=True, required=False)
    stretch_wrapped_pallet_qty = serializers.IntegerField(read_only=True, required=False)
    total_pallet_qty = serializers.IntegerField(read_only=True, required=False)
    film_laminating_fee = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, required=False)
    loading_fee = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, required=False)
    customer_other_fee = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, required=False)
    total_fee = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, required=False)
    ship_receive_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    creator = serializers.CharField(read_only=True, required=False)

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
            'customer_name',
            'stretch_wrapped_pallet_qty',
            'total_pallet_qty',
            'film_laminating_fee',
            'loading_fee',
            'customer_other_fee',
            'total_fee',
            'ship_receive_time',
            'creator',
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
    customer_name = serializers.CharField(read_only=True, required=False)
    stretch_wrapped_pallet_qty = serializers.IntegerField(read_only=True, required=False)
    total_pallet_qty = serializers.IntegerField(read_only=True, required=False)
    film_laminating_fee = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, required=False)
    loading_fee = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, required=False)
    customer_other_fee = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, required=False)
    total_fee = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, required=False)
    ship_receive_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    creator = serializers.CharField(read_only=True, required=False)
    create_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    update_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    
    def __init__(self, *args, **kwargs):
        """
        取出导出视图传入的映射，避免在 get_customer_bank_account 中重复访问数据库
        """
        super().__init__(*args, **kwargs)
        ctx = self.context or {}
        self._bank_map = ctx.get('customer_bank_map', {}) or {}
        self._dn_customer_map = ctx.get('dn_customer_map', {}) or {}


    def get_customer_bank_account(self, obj):
        """
        Resolve bank account from Customer.ListModel at export time.

        Priority:
        1) If FinanceRecord has a 'customer' field, use (openid + customer_name).
        2) Else if this is a DN record, resolve customer by dn_code -> DnListModel,
           then query Customer by (openid + customer_name).
        3) Otherwise return empty string.
        """
        direct_name = getattr(obj, 'customer', None) or getattr(obj, 'customer_name', None)
        if direct_name:
            if direct_name in self._bank_map:
                return self._bank_map[direct_name]

        # 2) DN 路径：dn_code -> customer_name -> bank
        if obj.source_type == 'DN':
            dn_code = obj.asn_dn_code
            if dn_code in self._dn_customer_map:
                name = self._dn_customer_map[dn_code]
                return self._bank_map.get(name, '')

        # 3) 数据库兜底：当 context 缺失或映射未命中时
        Customer = apps.get_model('customer', 'ListModel')

        # 3a) 用 direct_name 直接查
        if direct_name:
            bank = Customer.objects.filter(
                openid=obj.openid,
                customer_name=direct_name
            ).values_list('customer_bank_account', flat=True).first()
            return bank or ''

        # 3b) DN 记录：dn -> customer -> bank
        if obj.source_type == 'DN':
            DnListModel = apps.get_model('dn', 'DnListModel')
            dn = DnListModel.objects.filter(openid=obj.openid, dn_code=obj.asn_dn_code).values('customer', 'openid').first()
            if dn:
                bank = Customer.objects.filter(
                    openid=dn.get('openid') or obj.openid,
                    customer_name=dn.get('customer') or ''
                ).values_list('customer_bank_account', flat=True).first()
                return bank or ''

        return ''

    class Meta:
        model = FinanceRecord
        fields = (
            'asn_dn_code',
            'source_type',
            'openid',
            'customer_name',
            'customer_bank_account',
            'stretch_wrapped_pallet_qty',
            'total_pallet_qty',
            'film_laminating_fee',
            'loading_fee',
            'customer_other_fee',
            'total_fee',
            'ship_receive_time',
            'creator',
            'create_time',
            'update_time',
        )
        read_only_fields = fields