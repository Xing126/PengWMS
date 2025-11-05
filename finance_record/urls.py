# finance_record/urls.py
from django.urls import path, re_path
from . import views

urlpatterns = [
    # 列表（只读）
    path( r'finance/', views.FinanceRecordViewSet.as_view({"get": "list"}), name="financerecord"),
    # 导出（CSV，只读）
    path( r'financefile/', views.FinancefileDownloadView.as_view({"get": "list"}), name="financefiledownload"),
    # 详情（只读）—— 主键为 asn_dn_code（字符型），用“非斜杠”通配
    re_path( r'^finance/(?P<pk>[^/]+)/$', views.FinanceRecordViewSet.as_view({"get": "retrieve"}), name="financerecord_1"),
]
