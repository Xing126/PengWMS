# 只读序列化器：对外仅查询/导出
# refrigeration_fee_details/serializers.py
from rest_framework import serializers
from .models import RefrigerationFeeDetail

class RefrigerationFeeGetSerializer(serializers.ModelSerializer):
    openid = serializers.CharField(read_only=True)
    ship_receive_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    total_pallet_qty = serializers.IntegerField(read_only=True)
    refrigeration_fee = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    creator = serializers.CharField(read_only=True)
    create_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    update_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')

    class Meta:
        model = RefrigerationFeeDetail
        fields = (
            'openid',
            'ship_receive_time',
            'total_pallet_qty',
            'refrigeration_fee',
            'creator',
            'create_time',
            'update_time',
        )
        read_only_fields = fields
