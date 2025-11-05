from django.contrib import admin
from .models import RefrigerationFeeDetail

@admin.register(RefrigerationFeeDetail)
class RefrigerationFeeDetailAdmin(admin.ModelAdmin):
    list_display = ('openid', 'ship_receive_time', 'total_pallet_qty', 'refrigeration_fee', 'update_time')
    list_filter  = ('openid',)
    search_fields = ('openid',)
    ordering = ('-ship_receive_time',)

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):    return False
    def has_delete_permission(self, request, obj=None): return False
    def has_change_permission(self, request, obj=None):
        return request.method in ('GET',)
