from django.urls import path, re_path
from . import views

urlpatterns = [
path(r'list/', views.AsnListViewSet.as_view({"get": "list", "post": "create"}), name="asnlist"),
re_path(r'^list/(?P<pk>\d+)/$', views.AsnListViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
}), name="asnlist_1"),
path(r'detail/', views.AsnDetailViewSet.as_view({"get": "list", "post": "create", 'put': 'update'}), name="asndetail"),
re_path(r'^detail/(?P<pk>\d+)/$', views.AsnDetailViewSet.as_view({
    'get': 'retrieve',
}), name="asndetail_1"),
re_path(r'^viewprint/(?P<pk>\d+)/$', views.AsnViewPrintViewSet.as_view({
    'get': 'retrieve',
}), name="asnviewprint_1"),
re_path(r'^preload/(?P<pk>\d+)/$', views.AsnPreLoadViewSet.as_view({
    'post': 'create',
}), name="preload_1"),
re_path(r'^presort/(?P<pk>\d+)/$', views.AsnPreSortViewSet.as_view({
    'post': 'create',
}), name="presort_1"),
path(r'sorted/', views.AsnSortedViewSet.as_view({"put": "update"}), name="sorted"),
re_path(r'^sorted/(?P<pk>\d+)/$', views.AsnSortedViewSet.as_view({
    'post': 'create'
}), name="sorted_1"),
path(r'movetobin/', views.MoveToBinViewSet.as_view({'put': 'update'}), name="movetobin"),
re_path(r'^movetobin/(?P<pk>\d+)/$', views.MoveToBinViewSet.as_view({
    'post': 'create',
}), name="movetobin_1"),
path(r'filelist/', views.FileListDownloadView.as_view({"get": "list"}), name="asnfilelistdownload"),
path(r'filedetail/', views.FileDetailDownloadView.as_view({"get": "list"}), name="asnfiledetaildownload"),

# ======== 新增：跳过版接口（与新增 ViewSet 对应） =======
    # 1) 直接创建 ASN 到状态=3（跳过待到货/待卸货）
path(
        r'list/skip_create/',
        views.SkipAsnListCreateViewSet.as_view({'post': 'create'}),
        name='asn_skip_create'
    ),

    # 2) 直接创建 ASN 明细到状态=3（库存直接入 pre_sort_stock）
path(
        r'detail/skip_create/',
        views.SkipAsnDetailCreateViewSet.as_view({'post': 'create'}),
        name='asndetail_skip_create'
    ),

    # 3) 直接用状态=3的口径重建/更新 ASN 明细（库存维持 pre_sort_stock）
path(
        r'detail/skip_update/',
        views.SkipAsnDetailUpdateViewSet.as_view({'put': 'update'}),
        name='asndetail_skip_update'
    ),
]
