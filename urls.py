from django.urls import path, re_path
from . import views

urlpatterns = [
    # 头表
    path('list/', views.DnListViewSet.as_view({"get": "list", "post": "create"}), name="dnlist"),
    re_path(r'^list/(?P<pk>\d+)/$', views.DnListViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name="dnlist_1"),

    # 明细
    path('detail/', views.DnDetailViewSet.as_view({"get": "list", "post": "create", 'put': 'update'}), name="dndetail"),
    re_path(r'^detail/(?P<pk>\d+)/$', views.DnDetailViewSet.as_view({
        'get': 'retrieve',
        'delete': 'destroy'
    }), name="dndetail_1"),

    # 打印视图
    re_path(r'^viewprint/(?P<pk>\d+)/$', views.DnViewPrintViewSet.as_view({
        'get': 'retrieve',
    }), name="dnviewprint_1"),

    # 发货单创建：客户/仓管创建
    path('dn/create/', views.DnCreateViewSet.as_view({'post': 'create'}), name="dncreate"),

    # 签收回单：客户确认 / 仓管代理确认（根据 proxy_confirm 字段判断）
    re_path(r'^pod/(?P<pk>\d+)/$', views.DnPODViewSet.as_view({'post': 'create'}), name="pod_1"),


    # ⛔ 已删除：
    # re_path(r'^neworder/(?P<pk>\d+)/$', views.DnNewOrderViewSet.as_view({'post': 'create'}), name="preloadid_1"),
    # path('orderrelease/', views.DnOrderReleaseViewSet.as_view({"post": "create"}), name="orderrelease"),
    # re_path(r'^orderrelease/(?P<pk>\d+)/$', views.DnOrderReleaseViewSet.as_view({'put': 'update'}), name="orderrelease_1"),

    # ⛔ 拣货单相关也下线（没有“待拣货/匹配”流程就无需这些）
    # path('pickinglistfilter/', views.DnPickingListFilterViewSet.as_view({"get": "list"}), name="pickinglistfilter"),
    # re_path(r'^pickinglist/(?P<pk>\d+)/$', views.DnPickingListViewSet.as_view({'get': 'retrieve'}), name="pickinglist_1"),

    # 拣货确认（1→4）、发运（4→5）、签收（5→6）
    path('picked/', views.DnPickedViewSet.as_view({'put': 'update'}), name="picked"),
    re_path(r'^picked/(?P<pk>\d+)/$', views.DnPickedViewSet.as_view({'post': 'create', 'put': 'update'}), name="picked_1"),
    re_path(r'^dispatch/(?P<pk>\d+)/$', views.DnDispatchViewSet.as_view({'post': 'create'}), name="dispatch_1"),
    re_path(r'^pod/(?P<pk>\d+)/$', views.DnPODViewSet.as_view({'post': 'create'}), name="pod_1"),

    # 文件导出
    path('filelist/', views.FileListDownloadView.as_view({"get": "list"}), name="dnfilelistdownload"),
    path('filedetail/', views.FileDetailDownloadView.as_view({"get": "list"}), name="dnfiledetaildownload"),
]
