from rest_framework import serializers
from .models import AsnListModel, AsnDetailModel
from utils import datasolve

class ASNListGetSerializer(serializers.ModelSerializer):
    asn_code = serializers.CharField(read_only=True, required=False)
    asn_status = serializers.IntegerField(read_only=True, required=False)
    customer = serializers.CharField(read_only=True, required=False)
    bar_code = serializers.CharField(read_only=True, required=False)
    creator = serializers.CharField(read_only=True, required=False)
    create_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    update_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    total_pallet_qty = serializers.IntegerField(read_only=True, default=0)
    wrapped_pallet_qty = serializers.IntegerField(read_only=True, default=0)
    recive_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')

    class Meta:
        model = AsnListModel
        #排除了废弃字段'total_weight', 'total_volume'
        exclude = ['openid', 'is_delete']
        read_only_fields = ['id', 'openid', ]

class ASNListPostSerializer(serializers.ModelSerializer):
    openid = serializers.CharField(read_only=False, required=False, validators=[datasolve.openid_validate])
    asn_code = serializers.CharField(read_only=False,  required=True, validators=[datasolve.asn_data_validate])
    customer  = serializers.CharField(read_only=False, required=False)
    bar_code = serializers.CharField(read_only=False, required=True)
    creator = serializers.CharField(read_only=False, required=True, validators=[datasolve.data_validate])
    asn_status = serializers.IntegerField(default=1)
    customer_other_fees = serializers.JSONField(read_only=False, required=False, default=dict)
    total_pallet_qty = serializers.IntegerField(read_only=False, required=False, default=0, min_value=0)
    wrapped_pallet_qty = serializers.IntegerField(read_only=False, required=False, default=0, min_value=0)
    recive_time = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        total = attrs.get('total_pallet_qty', 0)
        wrapped = attrs.get('wrapped_pallet_qty', 0)
        if wrapped > total:
            raise serializers.ValidationError("wrapped_pallet_qty cannot be greater than total_pallet_qty.")
        return attrs

    class Meta:
        model = AsnListModel
        #排除了废弃字段
        exclude = ['is_delete']
        read_only_fields = ['id', 'create_time', 'update_time', ]

class ASNListPartialUpdateSerializer(serializers.ModelSerializer):
    asn_code = serializers.CharField(read_only=True)
    total_pallet_qty = serializers.IntegerField(read_only=False, required=False, default=0)
    wrapped_pallet_qty = serializers.IntegerField(read_only=False, required=False, default=0)
    recive_time = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        # 两者都不传：直接通过（不涉及 pallet 字段变更）
        if 'total_pallet_qty' not in attrs and 'wrapped_pallet_qty' not in attrs:
            return attrs

        # 补齐缺省值再校验关系
        total = attrs.get('total_pallet_qty', getattr(instance, 'total_pallet_qty', 0))
        wrapped = attrs.get('wrapped_pallet_qty', getattr(instance, 'wrapped_pallet_qty', 0))

        if "total_pallet_qty" in attrs or "wrapped_pallet_qty" in attrs:
            if total is None or wrapped is None:
                raise serializers.ValidationError("total_pallet_qty 与 wrapped_pallet_qty 必须成对可解析。")
            if wrapped > total:
                raise serializers.ValidationError("wrapped_pallet_qty 不得大于 total_pallet_qty。")

        return attrs


    class Meta:
        model = AsnListModel
        # 排除了废弃字段
        exclude = ['is_delete' ]
        read_only_fields = ['id', 'create_time', 'update_time', ]

class ASNListUpdateSerializer(serializers.ModelSerializer):
    asn_code = serializers.CharField(read_only=True)
    total_pallet_qty = serializers.IntegerField(read_only=False, required=False, default=0, min_value=0)
    wrapped_pallet_qty = serializers.IntegerField(read_only=False, required=False, default=0, min_value=0)
    recive_time = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        # 若前端只传了一个字段，另一个从 instance 取，以便做 pair 关系校验
        instance = getattr(self, 'instance', None)
        total = attrs.get('total_pallet_qty', getattr(instance, 'total_pallet_qty', 0))
        wrapped = attrs.get('wrapped_pallet_qty', getattr(instance, 'wrapped_pallet_qty', 0))
        if wrapped > total:
            raise serializers.ValidationError("wrapped_pallet_qty cannot be greater than total_pallet_qty.")
        return attrs

    class Meta:
        model = AsnListModel
        exclude = ['is_delete']
        read_only_fields = ['id', 'create_time', 'update_time', ]

class ASNDetailGetSerializer(serializers.ModelSerializer):
    asn_code = serializers.CharField(read_only=True, required=False)
    customer  = serializers.CharField(read_only=True, required=False)
    goods_code = serializers.CharField(read_only=True, required=False)
    goods_desc = serializers.CharField(read_only=True, required=False)
    goods_qty = serializers.IntegerField(read_only=True, required=False)
    goods_actual_qty = serializers.IntegerField(read_only=True, required=False)
    sorted_qty = serializers.IntegerField(read_only=True, required=False)
    goods_shortage_qty = serializers.IntegerField(read_only=True, required=False)
    goods_more_qty = serializers.IntegerField(read_only=True, required=False)
    goods_damage_qty = serializers.IntegerField(read_only=True, required=False)
    #新增字段
    customer_other_fees = serializers.JSONField(read_only=True, required=False)
    creator = serializers.CharField(read_only=True, required=False)
    create_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    update_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    class Meta:
        model = AsnDetailModel
        exclude = ['openid', 'is_delete', ]
        read_only_fields = ['id', 'openid']

class ASNDetailPostSerializer(serializers.ModelSerializer):
    openid = serializers.CharField(read_only=False, required=False, validators=[datasolve.openid_validate])
    asn_code = serializers.CharField(read_only=False,  required=True, validators=[datasolve.data_validate])
    customer  = serializers.CharField(read_only=False,  required=True, validators=[datasolve.data_validate])
    goods_code = serializers.CharField(read_only=False, required=True, validators=[datasolve.data_validate])
    goods_desc = serializers.CharField(read_only=False, required=False)
    goods_qty = serializers.IntegerField(read_only=False, required=True, validators=[datasolve.qty_0_data_validate])
    #新增字段
    customer_other_fees = serializers.JSONField(read_only=False, required=True)
    creator = serializers.CharField(read_only=False, required=True, validators=[datasolve.data_validate])
    asn_status = serializers.IntegerField(default=1,required=False)  # 说明：默认状态=1（正常流程从 1 开始）；“跳过版”接口在视图层会显式把状态置为 3
    class Meta:
        model = AsnDetailModel
        exclude = ['is_delete', ]
        read_only_fields = ['id', 'create_time', 'update_time', ]

class ASNSortedPostSerializer(serializers.ModelSerializer):
    openid = serializers.CharField(read_only=False, required=False, validators=[datasolve.openid_validate])
    asn_code = serializers.CharField(read_only=False,  required=True, validators=[datasolve.data_validate])
    customer  = serializers.CharField(read_only=False,  required=True, validators=[datasolve.data_validate])
    goods_code = serializers.CharField(read_only=False, required=True, validators=[datasolve.data_validate])
    goods_desc = serializers.CharField(read_only=False, required=False)
    goods_qty = serializers.IntegerField(read_only=False, required=True, validators=[datasolve.qty_data_validate])
    #新增字段
    customer_other_fees = serializers.JSONField(read_only=False, required=False)
    creator = serializers.CharField(read_only=False, required=True, validators=[datasolve.data_validate])
    class Meta:
        model = AsnDetailModel
        exclude = ['is_delete', ]
        read_only_fields = ['id', 'create_time', 'update_time', ]

class ASNDetailUpdateSerializer(serializers.ModelSerializer):
    asn_code = serializers.CharField(read_only=False, required=True, validators=[datasolve.data_validate])
    customer  = serializers.CharField(read_only=False,  required=True, validators=[datasolve.data_validate])
    goods_code = serializers.CharField(read_only=False, required=True, validators=[datasolve.data_validate])
    goods_desc = serializers.CharField(read_only=False, required=False)
    goods_qty = serializers.IntegerField(read_only=False, required=True, validators=[datasolve.qty_0_data_validate])
    creator = serializers.CharField(read_only=False, required=True, validators=[datasolve.data_validate])
    # 新增字段
    customer_other_fees = serializers.JSONField(read_only=False, required=False)

    class Meta:
        model = AsnDetailModel
        exclude = ['openid', 'is_delete', ]
        read_only_fields = ['id', 'create_time', 'update_time', ]

class ASNDetailPartialUpdateSerializer(serializers.ModelSerializer):
    asn_code = serializers.CharField(read_only=False, required=False, validators=[datasolve.data_validate])
    customer  = serializers.CharField(read_only=False,  required=False, validators=[datasolve.data_validate])
    goods_code = serializers.CharField(read_only=False, required=False, validators=[datasolve.data_validate])
    goods_desc = serializers.CharField(read_only=False, required=False)
    goods_qty = serializers.IntegerField(read_only=False, required=False, validators=[datasolve.qty_0_data_validate])
    # 新增字段
    customer_other_fees = serializers.JSONField(read_only=False, required=False)
    creator = serializers.CharField(read_only=False, required=False, validators=[datasolve.data_validate])
    class Meta:
        model = AsnDetailModel
        exclude = ['openid', 'is_delete', ]
        read_only_fields = ['id', 'create_time', 'update_time', ]

class MoveToBinSerializer(serializers.ModelSerializer):
    bin_name = serializers.CharField(read_only=False, required=True, validators=[datasolve.data_validate])
    qty = serializers.IntegerField(read_only=False, required=True, validators=[datasolve.qty_0_data_validate])
    class Meta:
        model = AsnDetailModel
        ref_name = 'AsnMoveToBin'
        exclude = ['openid', 'is_delete', ]
        read_only_fields = ['id', 'create_time', 'update_time', ]

class FileListRenderSerializer(serializers.ModelSerializer):
    asn_code = serializers.CharField(read_only=False, required=False)
    asn_status = serializers.IntegerField(read_only=False, required=False)
    #total_weight = serializers.FloatField(read_only=False, required=False)
    #total_volume = serializers.FloatField(read_only=False, required=False)
    total_cost = serializers.FloatField(read_only=False, required=False)
    customer  = serializers.CharField(read_only=False, required=False)
    creator = serializers.CharField(read_only=False, required=False)
    transportation_fee = serializers.JSONField(read_only=False, required=False)
    create_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    update_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    total_pallet_qty = serializers.IntegerField(read_only=False, required=False)
    wrapped_pallet_qty = serializers.IntegerField(read_only=False, required=False)
    recive_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')

    class Meta:
        model = AsnListModel
        ref_name = 'ASNFileListRenderSerializer'
        exclude = ['openid', 'is_delete', ]

class FileDetailRenderSerializer(serializers.ModelSerializer):
    asn_code = serializers.CharField(read_only=False, required=False)
    asn_status = serializers.IntegerField(read_only=False, required=False)
    goods_code = serializers.CharField(read_only=False, required=False)
    goods_desc = serializers.CharField(read_only=False, required=False)
    goods_qty = serializers.IntegerField(read_only=False, required=False)
    goods_actual_qty = serializers.IntegerField(read_only=False, required=False)
    sorted_qty = serializers.IntegerField(read_only=False, required=False)
    goods_shortage_qty = serializers.IntegerField(read_only=False, required=False)
    goods_more_qty = serializers.IntegerField(read_only=False, required=False)
    goods_damage_qty = serializers.IntegerField(read_only=False, required=False)
    #废弃字段
    #goods_weight = serializers.FloatField(read_only=False, required=False)
    #goods_cost = serializers.FloatField(read_only=False, required=False)
    customer  = serializers.CharField(read_only=False, required=False)
    creator = serializers.CharField(read_only=False, required=False)
    create_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    update_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')

    class Meta:
        model = AsnDetailModel
        ref_name = 'ASNFileDetailRenderSerializer'
        exclude = ['openid', 'is_delete', ]
