from rest_framework import serializers
from .models import DnListModel, DnDetailModel, PickingListModel
from utils import datasolve


# ====== Scanner明细（只读） ======
class SannerDnDetailGetSerializer(serializers.ModelSerializer):
    dn_code = serializers.CharField(read_only=True, required=False)
    dn_status = serializers.IntegerField(read_only=True, required=False)
    customer = serializers.CharField(read_only=True, required=False)
    goods_code = serializers.CharField(read_only=True, required=False)
    goods_qty = serializers.IntegerField(read_only=True, required=False)
    pick_qty = serializers.IntegerField(read_only=True, required=False)
    picked_qty = serializers.IntegerField(read_only=True, required=False)
    intransit_qty = serializers.IntegerField(read_only=True, required=False)
    delivery_actual_qty = serializers.IntegerField(read_only=True, required=False)
    delivery_shortage_qty = serializers.IntegerField(read_only=True, required=False)
    delivery_more_qty = serializers.IntegerField(read_only=True, required=False)
    delivery_damage_qty = serializers.IntegerField(read_only=True, required=False)
    creater = serializers.CharField(read_only=True, required=False)
    create_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    update_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')

    class Meta:
        model = DnDetailModel
        exclude = ['openid', 'is_delete', ]
        read_only_fields = ['id', 'openid']


# ====== 头表（GET） ======
class DNListGetSerializer(serializers.ModelSerializer):
    dn_code = serializers.CharField(read_only=True, required=False)
    dn_status = serializers.IntegerField(read_only=True, required=False)
    customer = serializers.CharField(read_only=True, required=False)
    creater = serializers.CharField(read_only=True, required=False)
    bar_code = serializers.CharField(read_only=True, required=False)
    # ⬇️ 新/改 字段
    other_fees = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, read_only=True)
    pallet_qty = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, read_only=True)
    created_by = serializers.CharField(read_only=True, required=False)
    signed_by = serializers.CharField(read_only=True, required=False)
    sign_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')

    create_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    update_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')

    class Meta:
        model = DnListModel
        exclude = ['openid', 'is_delete', ]
        read_only_fields = ['id', ]


# ====== 头表（POST） ======
class DNListPostSerializer(serializers.ModelSerializer):
    openid = serializers.CharField(read_only=False, required=False, validators=[datasolve.openid_validate])
    dn_code = serializers.CharField(read_only=False,  required=True, validators=[datasolve.dn_data_validate])
    customer = serializers.CharField(read_only=False, required=False)
    bar_code = serializers.CharField(read_only=False, required=True)
    creater = serializers.CharField(read_only=False, required=True, validators=[datasolve.data_validate])
    # ⬇️ 新/改 字段（非负约束交给模型 + 这里的 min_value 双保险）
    other_fees = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, min_value=0)
    pallet_qty = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, min_value=0)

    # created_by 由视图根据用户角色写入，这里不开放给前端覆盖
    created_by = serializers.CharField(read_only=True)

    class Meta:
        model = DnListModel
        exclude = ['is_delete', ]
        read_only_fields = ['id', 'create_time', 'update_time', 'created_by']


# ====== 头表（PATCH 部分更新） ======
class DNListPartialUpdateSerializer(serializers.ModelSerializer):
    dn_code = serializers.CharField(read_only=False,  required=True, validators=[datasolve.dn_data_validate])
    other_fees = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, min_value=0)
    pallet_qty = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, min_value=0)

    class Meta:
        model = DnListModel
        exclude = ['is_delete', ]
        read_only_fields = ['id', 'create_time', 'update_time', 'created_by', 'signed_by', 'sign_time']


# ====== 头表（PUT 全量更新） ======
class DNListUpdateSerializer(serializers.ModelSerializer):
    dn_code = serializers.CharField(read_only=False,  required=True, validators=[datasolve.dn_data_validate])
    other_fees = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, min_value=0)
    pallet_qty = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, min_value=0)

    class Meta:
        model = DnListModel
        exclude = ['is_delete', ]
        read_only_fields = ['id', 'create_time', 'update_time', 'created_by', 'signed_by', 'sign_time']


# ====== 明细（GET） ======
class DNDetailGetSerializer(serializers.ModelSerializer):
    dn_code = serializers.CharField(read_only=True, required=False)
    dn_status = serializers.IntegerField(read_only=True, required=False)
    customer = serializers.CharField(read_only=True, required=False)
    goods_code = serializers.CharField(read_only=True, required=False)
    goods_desc = serializers.CharField(read_only=True, required=False)
    goods_qty = serializers.IntegerField(read_only=True, required=False)
    pick_qty = serializers.IntegerField(read_only=True, required=False)
    picked_qty = serializers.IntegerField(read_only=True, required=False)
    intransit_qty = serializers.IntegerField(read_only=True, required=False)
    delivery_actual_qty = serializers.IntegerField(read_only=True, required=False)
    delivery_shortage_qty = serializers.IntegerField(read_only=True, required=False)
    delivery_more_qty = serializers.IntegerField(read_only=True, required=False)
    delivery_damage_qty = serializers.IntegerField(read_only=True, required=False)
    creater = serializers.CharField(read_only=True, required=False)
    create_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    update_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')

    class Meta:
        model = DnDetailModel
        exclude = ['openid', 'is_delete', ]
        read_only_fields = ['id', 'openid']


# ====== 明细（POST） ======
class DNDetailPostSerializer(serializers.ModelSerializer):
    openid = serializers.CharField(read_only=False, required=False, validators=[datasolve.openid_validate])
    dn_code = serializers.CharField(read_only=False,  required=True, validators=[datasolve.data_validate])
    customer = serializers.CharField(read_only=False,  required=True, validators=[datasolve.data_validate])
    goods_code = serializers.CharField(read_only=False, required=True, validators=[datasolve.data_validate])
    goods_desc = serializers.CharField(read_only=False, required=False)
    goods_qty = serializers.IntegerField(read_only=False, required=True, validators=[datasolve.qty_0_data_validate])
    creater = serializers.CharField(read_only=False, required=True, validators=[datasolve.data_validate])

    class Meta:
        model = DnDetailModel
        exclude = ['is_delete', ]
        read_only_fields = ['id', 'create_time', 'update_time', ]


# ====== 明细（PUT 全量更新） ======
class DNDetailUpdateSerializer(serializers.ModelSerializer):
    dn_code = serializers.CharField(read_only=False, required=True, validators=[datasolve.data_validate])
    customer = serializers.CharField(read_only=False,  required=True, validators=[datasolve.data_validate])
    goods_code = serializers.CharField(read_only=False, required=True, validators=[datasolve.data_validate])
    goods_desc = serializers.CharField(read_only=False, required=False)
    goods_qty = serializers.IntegerField(read_only=False, required=True, validators=[datasolve.qty_0_data_validate])
    creater = serializers.CharField(read_only=False, required=True, validators=[datasolve.data_validate])

    class Meta:
        model = DnDetailModel
        exclude = ['openid', 'is_delete', ]
        read_only_fields = ['id', 'create_time', 'update_time', ]


# ====== 明细（PATCH 部分更新） ======
class DNDetailPartialUpdateSerializer(serializers.ModelSerializer):
    dn_code = serializers.CharField(read_only=False, required=False, validators=[datasolve.data_validate])
    customer = serializers.CharField(read_only=False,  required=False, validators=[datasolve.data_validate])
    goods_code = serializers.CharField(read_only=False, required=False, validators=[datasolve.data_validate])
    goods_desc = serializers.CharField(read_only=False, required=False)
    goods_qty = serializers.IntegerField(read_only=False, required=False, validators=[datasolve.qty_0_data_validate])
    creater = serializers.CharField(read_only=False, required=False, validators=[datasolve.data_validate])

    class Meta:
        model = DnDetailModel
        exclude = ['openid', 'is_delete', ]
        read_only_fields = ['id', 'create_time', 'update_time', ]


# ====== PickingList（只读显示/审核） ======
class DNPickingListGetSerializer(serializers.ModelSerializer):
    dn_code = serializers.CharField(read_only=True, required=False)
    bin_name = serializers.CharField(read_only=True, required=False)
    goods_code = serializers.CharField(read_only=True, required=False)
    picking_status = serializers.IntegerField(read_only=True, required=False)
    pick_qty = serializers.IntegerField(read_only=True, required=False)
    picked_qty = serializers.IntegerField(read_only=True, required=False)
    creater = serializers.CharField(read_only=True, required=False)
    t_code = serializers.CharField(read_only=True, required=False)
    create_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    update_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')

    class Meta:
        model = PickingListModel
        exclude = ['openid', ]
        read_only_fields = ['id', ]


class DNPickingCheckGetSerializer(serializers.ModelSerializer):
    dn_code = serializers.CharField(read_only=True, required=False)
    bin_name = serializers.CharField(read_only=True, required=False)
    goods_code = serializers.CharField(read_only=True, required=False)
    picking_status = serializers.IntegerField(read_only=False, required=False)
    pick_qty = serializers.IntegerField(read_only=True, required=False)
    picked_qty = serializers.IntegerField(read_only=True, required=False)
    creater = serializers.CharField(read_only=True, required=False)
    create_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    update_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')

    class Meta:
        model = PickingListModel
        exclude = ['openid', ]
        read_only_fields = ['id', ]


# ====== 文件导出（头表） ======
class FileListRenderSerializer(serializers.ModelSerializer):
    dn_code = serializers.CharField(read_only=False, required=False)
    dn_status = serializers.IntegerField(read_only=False, required=False)
    customer = serializers.CharField(read_only=False, required=False)
    creater = serializers.CharField(read_only=False, required=False)
    
    # ⬇️ 新/改 字段（导出）
    other_fees = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    pallet_qty = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    created_by = serializers.CharField(read_only=False, required=False)
    signed_by = serializers.CharField(read_only=False, required=False)
    sign_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    
    create_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    update_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')

    class Meta:
        model = DnListModel
        ref_name = 'DNFileListRenderSerializer'
        exclude = ['openid', 'is_delete', ]


# ====== 文件导出（明细） ======
class FileDetailRenderSerializer(serializers.ModelSerializer):
    dn_code = serializers.CharField(read_only=False, required=False)
    dn_status = serializers.IntegerField(read_only=False, required=False)
    customer = serializers.CharField(read_only=False, required=False)
    goods_code = serializers.CharField(read_only=False, required=False)
    goods_desc = serializers.CharField(read_only=False, required=False)
    goods_qty = serializers.IntegerField(read_only=False, required=False)
    pick_qty = serializers.IntegerField(read_only=False, required=False)
    picked_qty = serializers.IntegerField(read_only=False, required=False)
    intransit_qty = serializers.IntegerField(read_only=False, required=False)
    delivery_actual_qty = serializers.IntegerField(read_only=False, required=False)
    delivery_shortage_qty = serializers.IntegerField(read_only=False, required=False)
    delivery_more_qty = serializers.IntegerField(read_only=False, required=False)
    delivery_damage_qty = serializers.IntegerField(read_only=False, required=False)
    creater = serializers.CharField(read_only=False, required=False)
    create_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    update_time = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')

    class Meta:
        model = DnDetailModel
        ref_name = 'DNFileDetailRenderSerializer'
        exclude = ['openid', 'is_delete', ]
