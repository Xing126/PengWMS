from django.db import models
from django.utils import timezone

class AsnListModel(models.Model):
    asn_code = models.CharField(max_length=255, verbose_name="ASN Code")
    asn_status = models.BigIntegerField(default=1, verbose_name="ASN Status")
    #废弃字段：总重量
    #total_weight = models.FloatField(default=0, verbose_name="Total Weight")
    total_cost = models.FloatField(default=0, verbose_name="Total Cost")
    customer = models.CharField(max_length=255, verbose_name="ASN Customer")
    creator = models.CharField(max_length=255, verbose_name="Who Created")
    bar_code = models.CharField(max_length=255, verbose_name="Bar Code")
    openid = models.CharField(max_length=255, verbose_name="Openid")
    transportation_fee = models.JSONField(default=dict, verbose_name="Transportation Fee")
    is_delete = models.BooleanField(default=False, verbose_name='Delete Label')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="Create Time")
    update_time = models.DateTimeField(auto_now=True, blank=True, null=True, verbose_name="Update Time")
    customer_other_fees = models.JSONField(default=dict, verbose_name="Customer Other Fees")
    total_pallet_qty = models.IntegerField(default=0, verbose_name="Total Pallet QTY")
    wrapped_pallet_qty = models.IntegerField(default=0, verbose_name="Wrapped Pallet QTY")
    recive_time = models.DateTimeField(default=timezone.now, verbose_name="Receive Time")

    def save(self, *args, **kwargs):
        if not self.pk and not self.recive_time:
            # 首次创建且未显式传入时，用当前时间；与 auto_now_add 行为一致
            self.recive_time = timezone.now()
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'asnlist'
        verbose_name = 'ASN List'
        verbose_name_plural = "ASN List"
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(fields=['openid', 'asn_code'], name='uniq_openid_asncode')
        ]
        indexes = [
            models.Index(fields=['openid', 'asn_status'], name='idx_openid_status'),
            models.Index(fields=['asn_code', 'asn_status'], name='idx_asncode_status'),
            models.Index(fields=['create_time'], name='idx_asnlist_ctime'),
        ]

class AsnDetailModel(models.Model):
    asn_code = models.CharField(max_length=255, verbose_name="ASN Code")
    asn_status = models.BigIntegerField(default=1, verbose_name="ASN Status")
    customer = models.CharField(max_length=255, verbose_name="ASN Customer")
    goods_code = models.CharField(max_length=255, verbose_name="Goods Code")
    goods_desc = models.CharField(max_length=255, verbose_name="Goods Description")
    goods_qty = models.BigIntegerField(default=0, verbose_name="Goods QTY")
    goods_actual_qty = models.BigIntegerField(default=0, verbose_name="Goods Actual QTY")
    sorted_qty = models.BigIntegerField(default=0, verbose_name="Sorted QTY")
    goods_shortage_qty = models.BigIntegerField(default=0, verbose_name="Goods Shortage QTY")
    goods_more_qty = models.BigIntegerField(default=0, verbose_name="Goods More QTY")
    goods_damage_qty = models.BigIntegerField(default=0, verbose_name="Goods damage QTY")
    #goods_weight = models.FloatField(default=0, verbose_name="Goods Weight")
    #goods_volume = models.FloatField(default=0, verbose_name="Goods Volume")
    goods_cost = models.FloatField(default=0, verbose_name="Goods Cost")
    creator = models.CharField(max_length=255, verbose_name="Who Created")
    openid = models.CharField(max_length=255, verbose_name="Openid")
    is_delete = models.BooleanField(default=False, verbose_name='Delete Label')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="Create Time")
    update_time = models.DateTimeField(auto_now=True, blank=True, null=True, verbose_name="Update Time")
    #新增字段
    customer_other_fees = models.JSONField(default=dict, verbose_name="Customer Other Fees")

    class Meta:
        db_table = 'asndetail'
        verbose_name = 'ASN Detail'
        verbose_name_plural = "ASN Detail"
        ordering = ['-id']
        # 常用联查：openid + asn_code；常用统计：asn_status=3
        indexes = [
            models.Index(fields=['openid', 'asn_code'], name='idx_openid_asncode_detail'),
            models.Index(fields=['asn_status', 'goods_code'], name='idx_status_goodscode'),
            models.Index(fields=['create_time'], name='idx_asndetail_ctime'),
        ]


