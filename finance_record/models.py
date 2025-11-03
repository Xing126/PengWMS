from django.db import models
from django.apps import apps

class FinanceRecord(models.Model):
    # Primary key: unified field for both ASN (asn_code) and DN (dn_code)
    asn_dn_code = models.CharField(max_length=255, primary_key=True, verbose_name="ASN/DN Code")
    source_type = models.CharField(max_length=8, choices=(('ASN', 'ASN'), ('DN', 'DN')), verbose_name="Source Type (ASN/DN)")
    openid = models.CharField(max_length=255, verbose_name="OpenID")
    customer_name = models.CharField(max_length=255, verbose_name="Customer Name")
    stretch_wrapped_pallet_qty = models.IntegerField(default=0, verbose_name="Stretch Wrapped Pallet Qty")
    total_pallet_qty = models.IntegerField(default=0, verbose_name="Total Pallet Qty")
    loading_fee = models.BigIntegerField(default=0, verbose_name="Loading Fee")
    film_laminating_fee = models.BigIntegerField(default=0, verbose_name="Film-Laminating Fee")
    customer_other_fee = models.BigIntegerField(default=0, verbose_name="Other Fee")
    total_fee = models.BigIntegerField(default=0, verbose_name="Total Fee(no refrigeration fees included)")
    ship_receive_time = models.DateTimeField(verbose_name="Ship/Receive Time")
    creator = models.CharField(max_length=255, verbose_name="Creator")
    
    # Logical delete flag
    is_delete = models.BooleanField(default=False, verbose_name="Delete Label")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="Create Time")
    update_time = models.DateTimeField(auto_now=True, blank=True, null=True, verbose_name="Update Time")

    class Meta:
        db_table = 'finance_record'
        verbose_name = 'Finance Record'
        verbose_name_plural = 'Finance Record'
        ordering = ['-update_time']

    def _resolve_source_quantities(self):

        qty_sw = int(self.stretch_wrapped_pallet_qty or 0)
        qty_total = int(self.total_pallet_qty or 0)

        try:
            if self.source_type == 'ASN':
            # 来自收货单：asn.AsnListModel + asn_code
                AsnListModel = apps.get_model('asn', 'AsnListModel')
                src = (
                    AsnListModel.objects
                    .filter(openid=self.openid, asn_code=self.asn_dn_code, is_delete=False)
                    .values('stretch_wrapped_pallet_qty', 'total_pallet_qty')
                    .first()
                )
                if src:
                # 若来源表未建这两个字段，get 会返回 None -> 回退到本地 qty
                    qty_sw = int(src.get('stretch_wrapped_pallet_qty') or qty_sw)
                    qty_total = int(src.get('total_pallet_qty') or qty_total)

            elif self.source_type == 'DN':
            # 来自发货单：dn.DnListModel + dn_code
                DnListModel = apps.get_model('dn', 'DnListModel')
                src = (
                    DnListModel.objects
                    .filter(openid=self.openid, dn_code=self.asn_dn_code, is_delete=False)
                    .values('stretch_wrapped_pallet_qty', 'total_pallet_qty')
                    .first()
                 )
                if src:
                    qty_sw = int(src.get('stretch_wrapped_pallet_qty') or qty_sw)
                    qty_total = int(src.get('total_pallet_qty') or qty_total)

        except Exception:
        # 模型不存在/字段不存在/查询异常时，静默回退为本地数量
            pass

        return qty_sw, qty_total


    def _fetch_unit_prices(self):
        """
        从 customer.ListModel 获取两项单价：
          - customer_film_laminating_fee  围膜单价
          - customer_loading_fee          装卸单价

        匹配键：
          - openid 与当前记录一致
          - customer_name（若你有更权威的客户外键字段，可替换为该字段）
        找不到记录时回退为 0。
        """
        film_price = 0
        loading_price = 0

        try:
            Customer = apps.get_model('customer', 'ListModel')
            lookup_name = getattr(self, 'customer', None) or self.customer_name

            row = (
                Customer.objects
                .filter(openid=self.openid, customer_name=lookup_name, is_delete=False)
                .values('customer_film_laminating_fee', 'customer_loading_fee')
                .first()
            )
            if row:
                # 字段来自用户管理表单模型定义
                film_price = int(row.get('customer_film_laminating_fee') or 0)
                loading_price = int(row.get('customer_loading_fee') or 0)
        except Exception:
            # 模型未加载/字段不存在/查询异常时，使用 0 作为兜底
            pass

        return film_price, loading_price
    
    def _compute_component_fees(self, qty_sw: int, qty_total: int):
        """
        使用“来源数量 + 用户管理单价”计算两项费用：
          - 围膜费 = 围膜库板数 * 围膜单价
          - 装卸费 = 总库板数   * 装卸单价
        """
        unit_price_film, unit_price_loading = self._fetch_unit_prices()
        film_fee = qty_sw * unit_price_film
        load_fee = qty_total * unit_price_loading
        return film_fee, load_fee

    def _compute_total_fee(self):
        """
        计算总费用（不含冷藏费）：
          total_fee = film_laminating_fee + loading_fee + customer_other_fee
        """
        return int(self.film_laminating_fee or 0) + int(self.loading_fee or 0) + int(self.customer_other_fee or 0)

    def save(self, *args, **kwargs):
        """
        保存前的统一流程：
          1) 基于 source_type 与 asn_dn_code，从 ASN/DN 表获取“围膜库板数/总库板数”
          2) 调用 _compute_component_fees() 使用“用户管理单价”计算费用
          3) 重新汇总 total_fee，最后保存
        """
        qty_sw, qty_total = self._resolve_source_quantities()
        film_fee, load_fee = self._compute_component_fees(qty_sw, qty_total)

        self.film_laminating_fee = film_fee
        self.loading_fee = load_fee
        self.total_fee = self._compute_total_fee()

        super().save(*args, **kwargs)