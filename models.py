from django.db import models
from django.core.validators import MinValueValidator

class DnListModel(models.Model):
    # 仅保留 1→4→5→6 四个状态
    STATUS_DRAFT = 1         # 草稿
    STATUS_PICKED = 4        # 已拣货
    STATUS_INTRANSIT = 5     # 在途
    STATUS_DELIVERED = 6     # 已签收

    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_PICKED, 'Picked'),
        (STATUS_INTRANSIT, 'In-Transit'),
        (STATUS_DELIVERED, 'Delivered'),
    )

    dn_code = models.CharField(max_length=255, verbose_name="DN Code")
    dn_status = models.BigIntegerField(default=1, verbose_name="DN Status")
    # total_weight = models.FloatField(default=0, verbose_name="Total Weight")
    # total_volume = models.FloatField(default=0, verbose_name="Total Volume")
    # other_fees = models.FloatField(default=0, verbose_name="Total Cost")
    customer = models.CharField(max_length=255, verbose_name="DN Customer")
    creater = models.CharField(max_length=255, verbose_name="Who Created")
    bar_code = models.CharField(max_length=255, verbose_name="Bar Code")
    # back_order_label = models.BooleanField(default=False, verbose_name='Back Order Label')
    openid = models.CharField(max_length=255, verbose_name="Openid")
    # transportation_fee = models.JSONField(default=dict, verbose_name="Transportation Fee")
    is_delete = models.BooleanField(default=False, verbose_name='Delete Label')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="Create Time")
    update_time = models.DateTimeField(auto_now=True, blank=True, null=True, verbose_name="Update Time")
    # ✅ 新字段：其他费用（改用 Decimal 存钱）
    other_fees = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Other Fees",
        validators=[MinValueValidator(0)]
    )
    # ✅ 库板数（直接输入，非负，建议用 Decimal）
    pallet_qty = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Pallet Qty",
        validators=[MinValueValidator(0)]
    )

    # ✅ 记录由谁创建：客户 / 仓管
    created_by = models.CharField(
        max_length=20, blank=True, null=True, verbose_name="Created By"  # 'customer' / 'warehouse'
    )

    # ✅ 签收人 & 签收时间（客户签/仓管代签/系统自动签）
    signed_by = models.CharField(max_length=50, blank=True, null=True, verbose_name="Signed By")
    sign_time = models.DateTimeField(blank=True, null=True, verbose_name="Sign Time")

    class Meta:
        db_table = 'dnlist'
        verbose_name = 'DN List'
        verbose_name_plural = "DN List"
        ordering = ['-id']

        constraints = [
            # ✅ 限制状态只能是 1/4/5/6，杜绝 2/3
            models.CheckConstraint(
                check=models.Q(dn_status__in=[1, 4, 5, 6]),
                name='dnlist_status_1456_only'
            ),
            # 常用唯一/查询索引（可选但强烈建议）
            models.UniqueConstraint(fields=['openid', 'dn_code'], name='uniq_openid_dncode'),
            # 非负约束（保险起见，模型层+DB双保险）
            models.CheckConstraint(
                check=models.Q(other_fees__gte=0),
                name='dnlist_other_fees_nonneg'
            ),
            models.CheckConstraint(
                check=models.Q(pallet_qty__gte=0),
                name='dnlist_pallet_qty_nonneg'
            ),

        ]

class DnDetailModel(models.Model):
    dn_code = models.CharField(max_length=255, verbose_name="DN Code")
    dn_status = models.BigIntegerField(default=1, verbose_name="DN Status")
    customer = models.CharField(max_length=255, verbose_name="DN Customer")
    goods_code = models.CharField(max_length=255, verbose_name="Goods Code")
    goods_desc = models.CharField(max_length=255, verbose_name="Goods Description")
    goods_qty = models.BigIntegerField(default=0, verbose_name="Goods QTY")
    pick_qty = models.BigIntegerField(default=0, verbose_name="Goods Pre Pick QTY")
    picked_qty = models.BigIntegerField(default=0, verbose_name="Goods Picked QTY")
    intransit_qty = models.BigIntegerField(default=0, verbose_name="Intransit QTY")
    delivery_actual_qty = models.BigIntegerField(default=0, verbose_name="Delivery Actual QTY")
    delivery_shortage_qty = models.BigIntegerField(default=0, verbose_name="Delivery Shortage QTY")
    delivery_more_qty = models.BigIntegerField(default=0, verbose_name="Delivery More QTY")
    delivery_damage_qty = models.BigIntegerField(default=0, verbose_name="Delivery Damage QTY")
    # goods_weight = models.FloatField(default=0, verbose_name="Goods Weight")
    # goods_volume = models.FloatField(default=0, verbose_name="Goods Volume")
    # goods_cost = models.FloatField(default=0, verbose_name="Goods Cost")
    creater = models.CharField(max_length=255, verbose_name="Who Created")
    # back_order_label = models.BooleanField(default=False, verbose_name='Back Order Label')
    openid = models.CharField(max_length=255, verbose_name="Openid")
    is_delete = models.BooleanField(default=False, verbose_name='Delete Label')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="Create Time")
    update_time = models.DateTimeField(auto_now=True, blank=True, null=True, verbose_name="Update Time")

    class Meta:
        db_table = 'dndetail'
        verbose_name = 'DN Detail'
        verbose_name_plural = "DN Detail"
        ordering = ['-id']

        indexes = [
            models.Index(fields=['openid', 'dn_code']),
            models.Index(fields=['openid', 'goods_code']),
        ]

class PickingListModel(models.Model):
    dn_code = models.CharField(max_length=255, verbose_name="DN Code")
    bin_name = models.CharField(max_length=255, verbose_name="Bin Name")
    goods_code = models.CharField(max_length=255, verbose_name="Goods Code")
    picking_status = models.SmallIntegerField(default=0, verbose_name="Picking Status")
    pick_qty = models.BigIntegerField(default=0, verbose_name="Goods Pre Pick QTY")
    picked_qty = models.BigIntegerField(default=0, verbose_name="Picked QTY")
    creater = models.CharField(max_length=255, verbose_name="Who Created")
    t_code = models.CharField(max_length=255, verbose_name="Transaction Code")
    openid = models.CharField(max_length=255, verbose_name="Openid")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="Create Time")
    update_time = models.DateTimeField(auto_now=True, blank=True, null=True, verbose_name="Update Time")

    class Meta:
        db_table = 'pickinglist'
        verbose_name = 'Picking List'
        verbose_name_plural = "Picking List"
        ordering = ['-id']

        indexes = [
            models.Index(fields=['openid', 'dn_code']),
            models.Index(fields=['openid', 'goods_code']),
        ]