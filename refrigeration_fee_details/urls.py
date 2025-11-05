# 只读路由注册：查询与导出
# refrigeration_fee_details/urls.py
from django.urls import path, re_path
from . import views

urlpatterns = [
    # 列表（只读）—— 查询所有 openid 的冷藏费用明细
    path('refrigeration-fee-details/', views.RefrigerationFeeViewSet.as_view({"get": "list"}), name="refrigerationfeerecord"),

    # 导出（CSV，只读）—— 导出冷藏费用明细
    path('refrigeration-fee-details-export/', views.RefrigerationFileDownloadView.as_view({"get": "list"}), name="refrigerationfeerecordexport"),

    # 详情（只读）—— 主键为 (openid, ship_receive_time)
    re_path(r'^refrigeration-fee-details/(?P<openid>[^/]+)/(?P<ship_receive_time>[^/]+)/$', views.RefrigerationFeeViewSet.as_view({"get": "retrieve"}), name="refrigerationfeerecord_1"),
]
