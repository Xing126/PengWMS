from django.db import models

class FinanceRecord(models.Model):
    # Primary key: unified field for both ASN (asn_code) and DN (dn_code)
    asn_dn_code = models.CharField(max_length=255, primary_key=True, verbose_name="ASN/DN Code")
    source_type = models.CharField(max_length=8, choices=(('ASN', 'ASN'), ('DN', 'DN')), verbose_name="Source Type (ASN/DN)")
    openid = models.CharField(max_length=255, verbose_name="OpenID")
    
    # Fees imported from Customer model
    customer_refrigeration_fee = models.BigIntegerField(default=0, verbose_name="Refrigeration Fee")
    customer_loading_fee = models.BigIntegerField(default=0, verbose_name="Loading Fee")
    customer_film_laminating_fee = models.BigIntegerField(default=0, verbose_name="Film-Laminating Fee")
    
    # Logical delete flag
    is_delete = models.BooleanField(default=False, verbose_name="Delete Label")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="Create Time")
    update_time = models.DateTimeField(auto_now=True, blank=True, null=True, verbose_name="Update Time")

    class Meta:
        db_table = 'finance_record'
        verbose_name = 'Finance Record'
        verbose_name_plural = 'Finance Record'
        ordering = ['-update_time']
