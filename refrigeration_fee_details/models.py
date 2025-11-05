from django.db import models

class RefrigerationFeeDetail(models.Model):
    openid = models.CharField(max_length=255, db_index=True, verbose_name="OpenID")
    ship_receive_time = models.DateTimeField(verbose_name="Ship/Receive Day Timestamp")
    total_pallet_qty = models.IntegerField(verbose_name="End-of-Day Stock")
    refrigeration_fee = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Refrigeration Fee")
    creator = models.CharField(max_length=255, verbose_name="Creator")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="Create Time")
    update_time = models.DateTimeField(auto_now=True, verbose_name="Update Time")

    class Meta:
        db_table = "refrigeration_fee_details"
        verbose_name = "Refrigeration Fee Detail"
        verbose_name_plural = "Refrigeration Fee Details"
        constraints = [
            models.UniqueConstraint(
                fields=["openid", "ship_receive_time"],
                name="uniq_openid_day"
            )
        ]
        indexes = [
            models.Index(fields=["openid", "ship_receive_time"]),
        ]

    def __str__(self):
        return f"{self.openid} @ {self.ship_receive_time} -> stock={self.total_pallet_qty}, fee={self.refrigeration_fee}"
