from dateutil.relativedelta import relativedelta
from rest_framework import viewsets
from .models import DnListModel, DnDetailModel, PickingListModel
from . import serializers
from .page import MyPageNumberPaginationDNList
from utils.page import MyPageNumberPagination
from utils.datasolve import sumOfList, transportation_calculate
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from .filter import DnListFilter, DnDetailFilter, DnPickingListFilter
from rest_framework.exceptions import APIException
from customer.models import ListModel as customer
from warehouse.models import ListModel as warehouse
from binset.models import ListModel as binset
from goods.models import ListModel as goods
from payment.models import TransportationFeeListModel as transportation
from stock.models import StockListModel as stocklist
from stock.models import StockBinModel as stockbin
from driver.models import ListModel as driverlist
from driver.models import DispatchListModel as driverdispatch
from scanner.models import ListModel as scanner
from cyclecount.models import QTYRecorder as qtychangerecorder
from cyclecount.models import CyclecountModeDayModel as cyclecount
from django.db.models import Q
from django.db.models import Sum
from utils.md5 import Md5
import re
from .serializers import FileListRenderSerializer, FileDetailRenderSerializer
from django.http import StreamingHttpResponse
from django.utils import timezone
from .files import FileListRenderCN, FileListRenderEN, FileDetailRenderCN, FileDetailRenderEN
from rest_framework.settings import api_settings
from staff.models import ListModel as staff
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import APIException
from .models import DnListModel, DnDetailModel, PickingListModel
from . import serializers

# ========== 通用工具 ==========
def _openid(request):
    auth = getattr(request, "auth", None)
    return getattr(auth, "openid", None)

class DnCreateViewSet(viewsets.ModelViewSet):
    """
    创建发货单：
    - 客户可直接创建；
    - 仓管也可代客户创建；
    - 支持输入 other_fees / pallet_qty；
    """
    pagination_class = None

    def get_queryset(self):
        return DnListModel.objects.none()

    def get_serializer_class(self):
        return serializers.DNListPostSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        user = request.user
        openid = request.auth.openid
        data = request.data

        # 区分角色
        if user.groups.filter(name='客户').exists():
            created_by = 'customer'
        elif user.groups.filter(name='仓管').exists():
            created_by = 'warehouse'
        else:
            raise APIException({'detail': '无创建权限'})

        dn_code = data.get('dn_code') or timezone.now().strftime("DN%Y%m%d%H%M%S%f")
        customer = data.get('customer')
        if not customer:
            raise APIException({'detail': '客户字段不能为空'})

        dn = DnListModel.objects.create(
            openid=openid,
            dn_code=dn_code,
            customer=customer,
            bar_code=data.get('bar_code', ''),
            creater=user.username,
            created_by=created_by,
            other_fees=data.get('other_fees', 0) or 0,
            pallet_qty=data.get('pallet_qty', 0) or 0,
            dn_status=DnListModel.STATUS_DRAFT,
        )
        return Response({'detail': '创建成功', 'dn_code': dn.dn_code}, status=201)


class DnListViewSet(viewsets.ModelViewSet):
    """
        retrieve:
            Response a data list（get）

        list:
            Response a data list（all）

        create:
            Create a data line（post）

        delete:
            Delete a data line（delete)
    """
    permission_classes = [IsAuthenticated]
    pagination_class = MyPageNumberPaginationDNList
    filter_backends = [DjangoFilterBackend, OrderingFilter, ]
    ordering_fields = ['id', "create_time", "update_time", ]

    # 原写法（django-filter 旧属性）
    # filter_class = DnListFilter
    # —— 改为新属性，避免弃用警告/失效 —— 
    filterset_class = DnListFilter  # NEW

    def get_project(self):
        try:
            id = self.kwargs.get('pk')
            return id
        except:
            return None

    def get_queryset(self):
        id = self.get_project()
        if self.request.user:
            # === 旧实现：逐条循环删除（效率低，存在竞态） ===
            # empty_qs = DnListModel.objects.filter(
            #     Q(openid=self.request.auth.openid, dn_status=1, is_delete=False) & Q(customer=''))
            # cur_date = timezone.now()
            # date_check = relativedelta(day=1)
            # if len(empty_qs) > 0:
            #     for i in range(len(empty_qs)):
            #         if empty_qs[i].create_time <= cur_date - date_check:
            #             empty_qs[i].delete()

            # === 新实现：一次性批量删除，更高效且更安全 ===
            cur_date = timezone.now()
            date_check = relativedelta(day=1)
            month_cutoff = cur_date - date_check
            (DnListModel.objects
                .filter(
                    openid=self.request.auth.openid,
                    dn_status=1,
                    is_delete=False,
                    customer=''
                )
                .filter(create_time__lte=month_cutoff)
                .delete())  # NEW: 批量删除

            if id is None:
                return DnListModel.objects.filter(
                    Q(openid=self.request.auth.openid, is_delete=False) & ~Q(customer=''))
            else:
                return DnListModel.objects.filter(
                    Q(openid=self.request.auth.openid, id=id, is_delete=False) & ~Q(customer=''))
        else:
            return DnListModel.objects.none()

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve', 'destroy']:
            return serializers.DNListGetSerializer
        elif self.action in ['create']:
            return serializers.DNListPostSerializer
        elif self.action in ['update']:
            return serializers.DNListUpdateSerializer
        elif self.action in ['partial_update']:
            return serializers.DNListPartialUpdateSerializer
        else:
            return self.http_method_not_allowed(request=self.request)

    # === 旧实现：未加事务/并发可能重复单号 ===
    # def create(self, request, *args, **kwargs):
    #     data = self.request.data
    #     data['openid'] = self.request.auth.openid
    #     custom_dn = self.request.GET.get('custom_dn', '')
    #     if custom_dn:
    #         data['dn_code'] = custom_dn
    #     else:
    #         qs_set = DnListModel.objects.filter(openid=self.request.auth.openid)
    #         order_day = str(timezone.now().strftime('%Y%m%d'))
    #         if len(qs_set) > 0:
    #             dn_last_code = qs_set.order_by('-id').first().dn_code
    #             if dn_last_code[2:10] == order_day:
    #                 order_create_no = str(int(dn_last_code[10:]) + 1)
    #                 data['dn_code'] = 'DN' + order_day + order_create_no
    #             else:
    #                 data['dn_code'] = 'DN' + order_day + '1'
    #         else:
    #             data['dn_code'] = 'DN' + order_day + '1'
    #     data['bar_code'] = Md5.md5(str(data['dn_code']))
    #     serializer = self.get_serializer(data=data)
    #     serializer.is_valid(raise_exception=True)
    #     serializer.save()
    #     scanner.objects.create(openid=self.request.auth.openid, mode="DN", code=data['dn_code'],
    #                            bar_code=data['bar_code'])
    #     headers = self.get_success_headers(serializer.data)
    #     return Response(serializer.data, status=200, headers=headers)

    # === 新实现：加事务 + 锁定读取，避免并发重复单号 ===
    @transaction.atomic  # NEW
    def create(self, request, *args, **kwargs):
        data = self.request.data.copy()  # NEW：copy 以免修改 request.data
        data['openid'] = self.request.auth.openid
        custom_dn = self.request.GET.get('custom_dn', '').strip()

        if custom_dn:
            data['dn_code'] = custom_dn
        else:
            # NEW: 锁住本 openid 下的最后一条，确保并发安全
            last = (DnListModel.objects
                    .select_for_update()  # NEW
                    .filter(openid=self.request.auth.openid)
                    .order_by('-id')
                    .first())
            order_day = timezone.now().strftime('%Y%m%d')
            if last and last.dn_code.startswith('DN') and last.dn_code[2:10] == order_day:
                seq = int(last.dn_code[10:] or '0') + 1
            else:
                seq = 1
            data['dn_code'] = f'DN{order_day}{seq}'  # NEW

        data['bar_code'] = Md5.md5(str(data['dn_code']))
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()

        # 仍然保留 scanner 的副作用，但不让它失败影响主流程
        try:
            scanner.objects.create(
                openid=self.request.auth.openid, mode="DN",
                code=data['dn_code'], bar_code=data['bar_code']
            )
        except Exception:
            pass  # NEW: 忽略 scanner 失败

        # 状态码也更合适：创建成功 201
        return Response(serializer.data, status=201, headers=self.get_success_headers(serializer.data))

    # === 旧实现：删除草稿并回滚 dn_stock（已不再适用新流程） ===
    # def destroy(self, request, pk):
    #     qs = self.get_object()
    #     if qs.openid != self.request.auth.openid:
    #         raise APIException({"detail": "Cannot delete data which not yours"})
    #     else:
    #         if qs.dn_status == 1:
    #             qs.is_delete = True
    #             dn_detail_list = DnDetailModel.objects.filter(openid=self.request.auth.openid, dn_code=qs.dn_code,
    #                                           dn_status=1, is_delete=False)
    #             for i in range(len(dn_detail_list)):
    #                 goods_qty_change = stocklist.objects.filter(openid=self.request.auth.openid,
    #                                                             goods_code=str(dn_detail_list[i].goods_code)).first()
    #                 goods_qty_change.dn_stock = goods_qty_change.dn_stock - int(dn_detail_list[i].goods_qty)
    #                 goods_qty_change.save()
    #             dn_detail_list.update(is_delete=True)
    #             qs.save()
    #             return Response({"detail": "success"}, status=200)
    #         else:
    #             raise APIException({"detail": "This order has Confirmed or Deliveried"})

    # === 新实现：仅草稿可删；不做库存回滚，统一软删头表+明细 ===
    @transaction.atomic  # NEW
    def destroy(self, request, pk):
        qs = self.get_object()
        if qs.openid != self.request.auth.openid:
            raise APIException({"detail": "Cannot delete data which not yours"})

        if qs.dn_status != 1:  # 只允许草稿删除
            raise APIException({"detail": "This DN has been picked or delivered"})

        qs.is_delete = True
        qs.save(update_fields=['is_delete'])  # NEW

        # NEW：统一软删对应明细（不回滚任何库存）
        DnDetailModel.objects.filter(
            openid=self.request.auth.openid,
            dn_code=qs.dn_code,
            is_delete=False
        ).update(is_delete=True)

        return Response({"detail": "success"}, status=200)


class DnDetailViewSet(viewsets.ModelViewSet):
    """
        retrieve:
            Response a data list（get）

        list:
            Response a data list（all）

        create:
            Create a data line（post）

        update:
            Update a data（put：update）
    """
    pagination_class = MyPageNumberPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter, ]
    ordering_fields = ['id', "create_time", "update_time", ]

    # 原写法（django-filter 旧属性）
    # filter_class = DnDetailFilter
    # NEW: 统一使用 django-filter 2.x 的属性，避免弃用
    filterset_class = DnDetailFilter  # NEW

    def get_project(self):
        try:
            id = self.kwargs.get('pk')
            return id
        except:
            return None

    def get_queryset(self):
        id = self.get_project()
        if self.request.user:
            if id is None:
                return DnDetailModel.objects.filter(openid=self.request.auth.openid, is_delete=False)
            else:
                return DnDetailModel.objects.filter(openid=self.request.auth.openid, id=id, is_delete=False)
        else:
            return DnDetailModel.objects.none()

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve', 'destroy']:
            return serializers.DNDetailGetSerializer
        elif self.action in ['create']:
            return serializers.DNDetailPostSerializer
        elif self.action in ['update']:
            return serializers.DNDetailUpdateSerializer
        # 原写法：未覆盖 partial_update，会 405
        # else:
        #     return self.http_method_not_allowed(request=self.request)
        # NEW: 回落到 GET 序列化器，避免 405；如需 partial_update 可单独加
        return serializers.DNDetailGetSerializer  # NEW

    # ========= create =========
    # 原实现（包含重量/体积/成本计算、运输费、预约库存、合并重复时汇总重量体积成本等——全部保留为注释）
    # def create(self, request, *args, **kwargs):
    #     data = self.request.data
    #     if DnListModel.objects.filter(openid=self.request.auth.openid, dn_code=str(data['dn_code']), is_delete=False).exists():
    #         if customer.objects.filter(openid=self.request.auth.openid, customer_name=str(data['customer']), is_delete=False).exists():
    #             staff_name = staff.objects.filter(openid=self.request.auth.openid,
    #                                               id=self.request.META.get('HTTP_OPERATOR')).first().staff_name
    #             for i in range(len(data['goods_code'])):
    #                 if goods.objects.filter(openid=self.request.auth.openid,
    #                                         goods_code=str(data['goods_code'][i]),
    #                                         is_delete=False).exists():
    #                     check_data = {
    #                         'openid': self.request.auth.openid,
    #                         'dn_code': str(data['dn_code']),
    #                         'customer': str(data['customer']),
    #                         'goods_code': str(data['goods_code'][i]),
    #                         'goods_qty': int(data['goods_qty'][i]),
    #                         'creater': str(staff_name)
    #                     }
    #                     serializer = self.get_serializer(data=check_data)
    #                     serializer.is_valid(raise_exception=True)
    #                 else:
    #                     raise APIException({"detail": str(data['goods_code'][i]) + " does not exists"})
    #             post_data_list = []
    #             weight_list = []
    #             volume_list = []
    #             cost_list = []
    #             for j in range(len(data['goods_code'])):
    #                 goods_detail = goods.objects.filter(openid=self.request.auth.openid,
    #                                                     goods_code=str(data['goods_code'][j]),
    #                                                     is_delete=False).first()
    #                 goods_weight = round(goods_detail.goods_weight * int(data['goods_qty'][j]) / 1000, 4)
    #                 goods_volume = round(goods_detail.unit_volume * int(data['goods_qty'][j]), 4)
    #                 goods_cost = round(goods_detail.goods_price * int(data['goods_qty'][j]), 2)
    #                 if stocklist.objects.filter(openid=self.request.auth.openid, goods_code=str(data['goods_code'][j]),
    #                                             can_order_stock__gte=0).exists():
    #                     goods_qty_change = stocklist.objects.filter(openid=self.request.auth.openid,
    #                                                                 goods_code=str(data['goods_code'][j])).first()
    #                     goods_qty_change.dn_stock = goods_qty_change.dn_stock + int(data['goods_qty'][j])
    #                     goods_qty_change.save()
    #                 else:
    #                     stocklist.objects.create(openid=self.request.auth.openid,
    #                                              goods_code=str(data['goods_code'][j]),
    #                                              goods_desc=goods_detail.goods_desc,
    #                                              dn_stock=int(data['goods_qty'][j]))
    #                 post_data = DnDetailModel(openid=self.request.auth.openid,
    #                                           dn_code=str(data['dn_code']),
    #                                           customer=str(data['customer']),
    #                                           goods_code=str(data['goods_code'][j]),
    #                                           goods_desc=str(goods_detail.goods_desc),
    #                                           goods_qty=int(data['goods_qty'][j]),
    #                                           goods_weight=goods_weight,
    #                                           goods_volume=goods_volume,
    #                                           goods_cost=goods_cost,
    #                                           creater=str(staff_name))
    #                 weight_list.append(goods_weight)
    #                 volume_list.append(goods_volume)
    #                 cost_list.append(goods_cost)
    #                 post_data_list.append(post_data)
    #             total_weight = sumOfList(weight_list, len(weight_list))
    #             total_volume = sumOfList(volume_list, len(volume_list))
    #             other_fees = sumOfList(cost_list, len(cost_list))
    #             customer_city = customer.objects.filter(...).first().customer_city
    #             warehouse_city = warehouse.objects.filter(openid=self.request.auth.openid).first().warehouse_city
    #             transportation_fee = transportation.objects.filter(...)
    #             transportation_res = {"detail": []}
    #             if len(transportation_fee) >= 1:
    #                 ...
    #             DnDetailModel.objects.bulk_create(post_data_list, batch_size=100)
    #             check_data = DnDetailModel.objects.filter(openid=self.request.auth.openid, dn_code=data['dn_code'], is_delete=False)
    #             for k in range(len(check_data)):
    #                 res_check_data = check_data.filter(goods_code=check_data[k].goods_code)
    #                 if res_check_data.count() > 1:
    #                     combine_qty = []; conbine_weight = []; conbine_volume = []; conbine_cost = []
    #                     for z in range(len(res_check_data)):
    #                         combine_qty.append(res_check_data[z].goods_qty)
    #                         conbine_weight.append(res_check_data[z].goods_weight)
    #                         conbine_volume.append(res_check_data[z].goods_volume)
    #                         conbine_cost.append(res_check_data[z].goods_cost)
    #                         res_check_data[z].delete()
    #                     DnDetailModel.objects.create(..., goods_qty=sumOfList(...), goods_weight=sumOfList(...),
    #                                                  goods_volume=sumOfList(...), goods_cost=sumOfList(...), ...)
    #             DnListModel.objects.filter(openid=self.request.auth.openid, dn_code=str(data['dn_code'])).update(
    #                 customer=str(data['customer']), total_weight=total_weight, total_volume=total_volume,
    #                 other_fees=other_fees, transportation_fee=transportation_res)
    #             return Response({"detail": "success"}, status=200)
    #         else:
    #             raise APIException({"detail": "customer does not exists"})
    #     else:
    #         raise APIException({"detail": "DN Code does not exists"})

    @transaction.atomic  # NEW：保证并发安全
    def create(self, request, *args, **kwargs):
        data = self.request.data
        # 只校验 DN 存在（不删除、状态不限；由拣货环节控制流程）
        if not DnListModel.objects.filter(openid=self.request.auth.openid, dn_code=str(data['dn_code']), is_delete=False).exists():  # NEW
            raise APIException({"detail": "DN Code does not exist"})  # NEW
        if not customer.objects.filter(openid=self.request.auth.openid, customer_name=str(data['customer']), is_delete=False).exists():  # NEW
            raise APIException({"detail": "customer does not exist"})  # NEW

        staff_name = staff.objects.filter(openid=self.request.auth.openid,
                                          id=self.request.META.get('HTTP_OPERATOR')).first().staff_name  # NEW

        # 先校验每一项
        for i in range(len(data['goods_code'])):  # NEW
            if not goods.objects.filter(openid=self.request.auth.openid,
                                        goods_code=str(data['goods_code'][i]),
                                        is_delete=False).exists():
                raise APIException({"detail": str(data['goods_code'][i]) + " does not exist"})  # NEW
            check_data = {  # NEW
                'openid': self.request.auth.openid,
                'dn_code': str(data['dn_code']),
                'customer': str(data['customer']),
                'goods_code': str(data['goods_code'][i]),
                'goods_qty': int(data['goods_qty'][i]),
                'creater': str(staff_name)
            }
            serializer = self.get_serializer(data=check_data)  # NEW
            serializer.is_valid(raise_exception=True)  # NEW

        # 构造明细对象（不再写 weights/volume/cost，也不预约库存）  # NEW
        post_data_list = []  # NEW
        for j in range(len(data['goods_code'])):  # NEW
            goods_detail = goods.objects.filter(openid=self.request.auth.openid,
                                                goods_code=str(data['goods_code'][j]),
                                                is_delete=False).first()
            post_data = DnDetailModel(  # NEW
                openid=self.request.auth.openid,
                dn_code=str(data['dn_code']),
                customer=str(data['customer']),
                goods_code=str(data['goods_code'][j]),
                goods_desc=str(goods_detail.goods_desc),
                goods_qty=int(data['goods_qty'][j]),
                creater=str(staff_name)
            )
            post_data_list.append(post_data)  # NEW

        DnDetailModel.objects.bulk_create(post_data_list, batch_size=100)  # NEW

        # 合并重复 goods_code：只合并数量（不再汇总重量/体积/成本）  # NEW
        check_data_qs = DnDetailModel.objects.filter(openid=self.request.auth.openid, dn_code=data['dn_code'], is_delete=False)  # NEW
        seen = {}  # NEW
        for row in list(check_data_qs):  # NEW
            key = row.goods_code
            if key not in seen:
                seen[key] = row
            else:
                seen[key].goods_qty += row.goods_qty
                row.delete()
        # 把累加后的 qty 保存（避免多次 save）  # NEW
        for row in seen.values():  # NEW
            row.save(update_fields=['goods_qty'])

        # 头表仅更新 customer；不再写 total_weight/total_volume/transportation_fee/other_fees（总价由前端直接传入头表）  # NEW
        DnListModel.objects.filter(openid=self.request.auth.openid, dn_code=str(data['dn_code'])).update(
            customer=str(data['customer'])
        )  # NEW
        return Response({"detail": "success"}, status=200)  # NEW

    # ========= update =========
    # 原实现（会回滚 dn_stock、重新计算重量/体积/成本与运输费、并更新头表 total_* 与 transportation_fee）
    # def update(self, request, *args, **kwargs):
    #     data = self.request.data
    #     if DnListModel.objects.filter(openid=self.request.auth.openid, dn_code=str(data['dn_code']),
    #                                    dn_status=1, is_delete=False).exists():
    #         if customer.objects.filter(...).exists():
    #             staff_name = ...
    #             ...（回滚 stocklist.dn_stock）
    #             ...（重新累计 goods_weight/volume/cost）
    #             ...（重算运输费 transportation_fee）
    #             ...（bulk_create + 合并重复时再汇总 weight/volume/cost）
    #             DnListModel.objects.filter(...).update(
    #                 customer=..., total_weight=..., total_volume=...,
    #                 other_fees=..., transportation_fee=...
    #             )
    #             return Response({"detail": "success"}, status=200)
    #         else:
    #             raise APIException({"detail": "Customer does not exists"})
    #     else:
    #         raise APIException({"detail": "DN Code has been Confirmed or does not exists"})

    @transaction.atomic  # NEW
    def update(self, request, *args, **kwargs):
        data = self.request.data  # NEW
        # 只允许草稿单修改明细  # NEW
        if not DnListModel.objects.filter(openid=self.request.auth.openid, dn_code=str(data['dn_code']),
                                          dn_status=DnListModel.STATUS_DRAFT, is_delete=False).exists():  # NEW
            raise APIException({"detail": "DN Code is not draft or does not exist"})  # NEW
        if not customer.objects.filter(openid=self.request.auth.openid, customer_name=str(data['customer']),
                                       is_delete=False).exists():  # NEW
            raise APIException({"detail": "Customer does not exist"})  # NEW

        staff_name = staff.objects.filter(openid=self.request.auth.openid,
                                          id=self.request.META.get('HTTP_OPERATOR')).first().staff_name  # NEW

        # 软删旧明细（不回滚任何库存预约；你已删除匹配/欠货流程）  # NEW
        DnDetailModel.objects.filter(openid=self.request.auth.openid,
                                     dn_code=str(data['dn_code']), is_delete=False).update(is_delete=True)  # NEW

        # 校验并重建新明细  # NEW
        post_data_list = []  # NEW
        for i in range(len(data['goods_code'])):  # NEW
            if not goods.objects.filter(openid=self.request.auth.openid,
                                        goods_code=str(data['goods_code'][i]),
                                        is_delete=False).exists():
                raise APIException({"detail": str(data['goods_code'][i]) + " does not exist"})  # NEW
            goods_detail = goods.objects.filter(openid=self.request.auth.openid,
                                                goods_code=str(data['goods_code'][i]),
                                                is_delete=False).first()  # NEW
            check_data = {  # NEW
                'openid': self.request.auth.openid,
                'dn_code': str(data['dn_code']),
                'customer': str(data['customer']),
                'goods_code': str(data['goods_code'][i]),
                'goods_qty': int(data['goods_qty'][i]),
                'creater': str(staff_name)
            }
            serializer = self.get_serializer(data=check_data)  # NEW
            serializer.is_valid(raise_exception=True)  # NEW
            post_data_list.append(DnDetailModel(  # NEW
                openid=self.request.auth.openid,
                dn_code=str(data['dn_code']),
                customer=str(data['customer']),
                goods_code=str(data['goods_code'][i]),
                goods_desc=str(goods_detail.goods_desc),
                goods_qty=int(data['goods_qty'][i]),
                creater=str(staff_name)
            ))
        DnDetailModel.objects.bulk_create(post_data_list, batch_size=100)  # NEW

        # 合并重复 goods_code：仅合并数量  # NEW
        check_data_qs = DnDetailModel.objects.filter(openid=self.request.auth.openid, dn_code=data['dn_code'], is_delete=False)  # NEW
        seen = {}  # NEW
        for row in list(check_data_qs):  # NEW
            key = row.goods_code
            if key not in seen:
                seen[key] = row
            else:
                seen[key].goods_qty += row.goods_qty
                row.delete()
        for row in seen.values():  # NEW
            row.save(update_fields=['goods_qty'])

        # 头表只更新 customer（总价由头表接口维护）  # NEW
        DnListModel.objects.filter(openid=self.request.auth.openid, dn_code=str(data['dn_code'])).update(
            customer=str(data['customer'])
        )  # NEW
        return Response({"detail": "success"}, status=200)  # NEW

    # ========= destroy =========
    # 原实现：依赖状态2 + back_order_label + 回滚 ordered/back_order_stock（已废弃流程）
    # def destroy(self, request, pk):
    #     qs = self.get_object()
    #     if qs.openid != self.request.auth.openid:
    #         raise APIException({"detail": "Cannot delete data which not yours"})
    #     else:
    #         if qs.dn_status == 2 and qs.back_order_label:
    #             qs.is_delete = True
    #             goods_qty_change = stocklist.objects.filter(...).first()
    #             goods_qty_change.back_order_stock = goods_qty_change.back_order_stock - int(qs.goods_qty)
    #             goods_qty_change.ordered_stock = goods_qty_change.ordered_stock - int(qs.goods_qty)
    #             goods_qty_change.save()
    #             qs.save()
    #             ...
    #             return Response({"detail": "success"}, status=200)
    #         else:
    #             raise APIException({"detail": "This order has Confirmed or Deliveried"})

    @transaction.atomic  # NEW
    def destroy(self, request, pk):
        qs = self.get_object()
        if qs.openid != self.request.auth.openid:
            raise APIException({"detail": "Cannot delete data which not yours"})

        # 仅允许“头表为草稿(1)”时删除某行明细；不做任何库存回滚  # NEW
        header = DnListModel.objects.filter(openid=self.request.auth.openid,
                                            dn_code=qs.dn_code,
                                            dn_status=DnListModel.STATUS_DRAFT,
                                            is_delete=False).first()  # NEW
        if not header:
            raise APIException({"detail": "Header is not draft or does not exist"})  # NEW

        qs.is_delete = True  # NEW
        qs.save(update_fields=['is_delete'])  # NEW

        # 若该 DN 下已无任何有效明细，可按需软删头表（可选，默认不删）  # NEW（可按需要解开）
        # if not DnDetailModel.objects.filter(openid=self.request.auth.openid, dn_code=qs.dn_code, is_delete=False).exists():
        #     header.is_delete = True
        #     header.save(update_fields=['is_delete'])

        return Response({"detail": "success"}, status=200)  # NEW


class DnViewPrintViewSet(viewsets.ModelViewSet):
    """
        retrieve:
            Response a data list（get）
    """
    serializer_class = serializers.DNListGetSerializer
    pagination_class = MyPageNumberPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter, ]
    ordering_fields = ['id', "create_time", "update_time", ]

    # 原写法（django-filter 旧属性）
    # filter_class = DnListFilter
    # NEW: 统一使用 django-filter 2.x 的属性
    filterset_class = DnListFilter  # NEW

    def get_project(self):
        try:
            id = self.kwargs.get('pk')
            return id
        except:
            return None

    def get_queryset(self):
        id = self.get_project()
        if self.request.user:
            if id is None:
                return DnListModel.objects.filter(openid=self.request.auth.openid, is_delete=False)
            else:
                return DnListModel.objects.filter(openid=self.request.auth.openid, id=id, is_delete=False)
        else:
            return DnListModel.objects.none()

    def get_serializer_class(self):
        if self.action in ['retrieve']:
            return serializers.DNDetailGetSerializer
        else:
            return self.http_method_not_allowed(request=self.request)

    def retrieve(self, request, pk):
        qs = self.get_object()
        if qs.openid != self.request.auth.openid:
            raise APIException({"detail": "Cannot update data which not yours"})
        else:
            context = {}

            # ===== 原实现：只返回明细、客户、仓库；未返回头信息 =====
            # dn_detail_list = DnDetailModel.objects.filter(openid=self.request.auth.openid,
            #                                               dn_code=qs.dn_code,
            #                                               is_delete=False)
            # dn_detail = serializers.DNDetailGetSerializer(dn_detail_list, many=True)
            # customer_detail = customer.objects.filter(openid=self.request.auth.openid,
            #                                                 customer_name=qs.customer).first()
            # warehouse_detail = warehouse.objects.filter(openid=self.request.auth.openid).first()
            # context['dn_detail'] = dn_detail.data
            # context['customer_detail'] = {
            #     "customer_name": customer_detail.customer_name,
            #     "customer_city": customer_detail.customer_city,
            #     "customer_address": customer_detail.customer_address,
            #     "customer_contact": customer_detail.customer_contact
            # }
            # context['warehouse_detail'] = {
            #     "warehouse_name": warehouse_detail.warehouse_name,
            #     "warehouse_city": warehouse_detail.warehouse_city,
            #     "warehouse_address": warehouse_detail.warehouse_address,
            #     "warehouse_contact": warehouse_detail.warehouse_contact
            # }

            # ===== NEW：补充 dn_header；仅保留总价 other_fees（删除重量/体积/运费/欠货等字段）=====
            context['dn_header'] = {  # NEW
                "dn_code": qs.dn_code,
                "dn_status": qs.dn_status,
                "customer": qs.customer,
                "create_time": qs.create_time,
                "update_time": qs.update_time,
                "other_fees": qs.other_fees,  # NEW：与你 models.py 对齐（DecimalField）
            }

            # 明细
            dn_detail_list = DnDetailModel.objects.filter(  # NEW（与原相同）
                openid=self.request.auth.openid,
                dn_code=qs.dn_code,
                is_delete=False
            )
            dn_detail = serializers.DNDetailGetSerializer(dn_detail_list, many=True)  # NEW
            context['dn_detail'] = dn_detail.data  # NEW

            # 客户信息
            customer_detail = customer.objects.filter(  # NEW（与原相同）
                openid=self.request.auth.openid,
                customer_name=qs.customer
            ).first()
            context['customer_detail'] = {  # NEW
                "customer_name": customer_detail.customer_name if customer_detail else "",
                "customer_city": customer_detail.customer_city if customer_detail else "",
                "customer_address": customer_detail.customer_address if customer_detail else "",
                "customer_contact": customer_detail.customer_contact if customer_detail else ""
            }

            # 仓库信息
            warehouse_detail = warehouse.objects.filter(  # NEW（与原相同）
                openid=self.request.auth.openid
            ).first()
            context['warehouse_detail'] = {  # NEW
                "warehouse_name": warehouse_detail.warehouse_name if warehouse_detail else "",
                "warehouse_city": warehouse_detail.warehouse_city if warehouse_detail else "",
                "warehouse_address": warehouse_detail.warehouse_address if warehouse_detail else "",
                "warehouse_contact": warehouse_detail.warehouse_contact if warehouse_detail else ""
            }

        return Response(context, status=200)



class DnNewOrderViewSet(viewsets.ModelViewSet):
    """
        retrieve:
            Response a data list（get）
    """
    pagination_class = MyPageNumberPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter, ]
    ordering_fields = ['id', "create_time", "update_time", ]
    filter_class = DnListFilter

    def get_project(self):
        try:
            id = self.kwargs.get('pk')
            return id
        except:
            return None

    def get_queryset(self):
        id = self.get_project()
        if self.request.user:
            if id is None:
                return DnListModel.objects.filter(openid=self.request.auth.openid, is_delete=False)
            else:
                return DnListModel.objects.filter(openid=self.request.auth.openid, id=id, is_delete=False)
        else:
            return DnListModel.objects.none()

    def get_serializer_class(self):
        if self.action in ['create']:
            return serializers.DNListPartialUpdateSerializer
        else:
            return self.http_method_not_allowed(request=self.request)

    def create(self, request, pk):
        qs = self.get_object()
        if qs.openid != self.request.auth.openid:
            raise APIException({"detail": "Cannot delete data which not yours"})
        else:
            if qs.dn_status == 1:
                dn_detail_list = DnDetailModel.objects.filter(openid=self.request.auth.openid, dn_code=qs.dn_code,
                                                              dn_status=1, is_delete=False)
                if dn_detail_list.exists():
                    qs.dn_status = 2
                    for i in range(len(dn_detail_list)):
                        if stocklist.objects.filter(openid=self.request.auth.openid,
                                                    goods_code=str(dn_detail_list[i].goods_code)).exists():
                            pass
                        else:
                            goods_detail = goods.objects.filter(openid=self.request.auth.openid, goods_code=str(dn_detail_list[i].goods_code)).first()
                            stocklist.objects.create(openid=self.request.auth.openid,
                                                     goods_code=str(dn_detail_list[i].goods_code),
                                                     goods_desc=goods_detail.goods_desc,
                                                     supplier=goods_detail.goods_supplier)
                        goods_qty_change = stocklist.objects.filter(openid=self.request.auth.openid,
                                                                    goods_code=str(
                                                                        dn_detail_list[i].goods_code)).first()
                        goods_qty_change.can_order_stock = goods_qty_change.can_order_stock - dn_detail_list[i].goods_qty
                        goods_qty_change.ordered_stock = goods_qty_change.ordered_stock + dn_detail_list[i].goods_qty
                        goods_qty_change.dn_stock = goods_qty_change.dn_stock - dn_detail_list[i].goods_qty
                        if goods_qty_change.can_order_stock < 0:
                            goods_qty_change.can_order_stock = 0
                        goods_qty_change.save()
                    dn_detail_list.update(dn_status=2)
                    qs.save()
                    serializer = self.get_serializer(qs, many=False)
                    headers = self.get_success_headers(serializer.data)
                    return Response(serializer.data, status=200, headers=headers)
                else:
                    raise APIException({"detail": "Please Enter The DN Detail"})
            else:
                raise APIException({"detail": "This DN Status Is Not Pre Order"})

class DnOrderReleaseViewSet(viewsets.ModelViewSet):
    """
        retrieve:
            Response a data list（get）
    """
    pagination_class = MyPageNumberPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter, ]
    ordering_fields = ['id', "create_time", "update_time", ]
    filter_class = DnListFilter

    def get_project(self):
        try:
            id = self.kwargs.get('pk')
            return id
        except:
            return None

    def get_queryset(self):
        id = self.get_project()
        if self.request.user:
            if id is None:
                return DnListModel.objects.filter(openid=self.request.auth.openid, dn_status=2, is_delete=False).order_by('create_time')
            else:
                return DnListModel.objects.filter(openid=self.request.auth.openid, dn_status=2, id=id, is_delete=False)
        else:
            return DnListModel.objects.none()

    def get_serializer_class(self):
        if self.action in ['create', 'update']:
            return serializers.DNListUpdateSerializer
        else:
            return self.http_method_not_allowed(request=self.request)

    def create(self, request, *args, **kwargs):
        qs = self.get_queryset()
        staff_name = staff.objects.filter(openid=self.request.auth.openid,
                                          id=self.request.META.get('HTTP_OPERATOR')).first().staff_name
        for v in range(len(qs)):
            dn_detail_list = DnDetailModel.objects.filter(openid=self.request.auth.openid, dn_code=qs[v].dn_code,
                                                          dn_status=2, is_delete=False)
            picking_list = []
            picking_list_label = 0
            back_order_list = []
            back_order_list_label = 0
            back_order_goods_weight_list = []
            back_order_goods_volume_list = []
            back_order_goods_cost_list = []
            back_order_base_code = DnListModel.objects.filter(openid=self.request.auth.openid,
                                                              is_delete=False).order_by('-id').first().dn_code
            dn_last_code = re.findall(r'\d+', str(back_order_base_code), re.IGNORECASE)
            back_order_dn_code = 'DN' + str(int(dn_last_code[0]) + 1).zfill(8)
            bar_code = Md5.md5(back_order_dn_code)
            total_weight = qs[v].total_weight
            total_volume = qs[v].total_volume
            other_fees = qs[v].other_fees
            for i in range(len(dn_detail_list)):
                goods_detail = goods.objects.filter(openid=self.request.auth.openid,
                                                    goods_code=str(dn_detail_list[i].goods_code),
                                                    is_delete=False).first()
                if stocklist.objects.filter(openid=self.request.auth.openid,
                                            goods_code=str(dn_detail_list[i].goods_code)).exists() is False:
                    stocklist.objects.create(openid=self.request.auth.openid,
                                             goods_code=str(goods_detail.goods_code),
                                             goods_desc=goods_detail.goods_desc,
                                             dn_stock=int(dn_detail_list[i].goods_qty))
                goods_qty_change = stocklist.objects.filter(openid=self.request.auth.openid,
                                                            goods_code=str(
                                                                dn_detail_list[i].goods_code)).first()
                goods_bin_stock_list = stockbin.objects.filter(openid=self.request.auth.openid,
                                                               goods_code=str(dn_detail_list[i].goods_code),
                                                               bin_property="Normal", goods_qty__gt=0).order_by('id')
                can_pick_qty = goods_qty_change.onhand_stock - \
                               goods_qty_change.inspect_stock - \
                               goods_qty_change.hold_stock - \
                               goods_qty_change.damage_stock - \
                               goods_qty_change.pick_stock
                if can_pick_qty > 0:
                    if dn_detail_list[i].goods_qty > can_pick_qty:
                        if qs[v].back_order_label is False:
                            dn_pick_qty = dn_detail_list[i].pick_qty
                            for j in range(len(goods_bin_stock_list)):
                                bin_can_pick_qty = goods_bin_stock_list[j].goods_qty - \
                                                   goods_bin_stock_list[j].pick_qty
                                if bin_can_pick_qty > 0:
                                    goods_bin_stock_list[j].pick_qty = goods_bin_stock_list[
                                                                           j].pick_qty + bin_can_pick_qty
                                    goods_qty_change.ordered_stock = goods_qty_change.ordered_stock - bin_can_pick_qty
                                    goods_qty_change.pick_stock = goods_qty_change.pick_stock + bin_can_pick_qty
                                    picking_list.append(PickingListModel(openid=self.request.auth.openid,
                                                                         dn_code=dn_detail_list[i].dn_code,
                                                                         bin_name=goods_bin_stock_list[j].bin_name,
                                                                         goods_code=goods_bin_stock_list[
                                                                             j].goods_code,
                                                                         pick_qty=bin_can_pick_qty,
                                                                         creater=str(staff_name),
                                                                         t_code=goods_bin_stock_list[j].t_code))
                                    picking_list_label = 1
                                    dn_pick_qty = dn_pick_qty + bin_can_pick_qty
                                    goods_qty_change.save()
                                    goods_bin_stock_list[j].save()
                                elif bin_can_pick_qty == 0:
                                    continue
                                else:
                                    continue
                            dn_detail_list[i].pick_qty = dn_pick_qty
                            dn_back_order_qty = dn_detail_list[i].goods_qty - \
                                                dn_detail_list[i].pick_qty
                            goods_qty_change.back_order_stock = dn_detail_list[i].goods_qty - can_pick_qty
                            dn_detail_list[i].goods_qty = dn_pick_qty
                            dn_detail_list[i].dn_status = 3
                            back_order_goods_volume = round(goods_detail.unit_volume * dn_back_order_qty, 4)
                            back_order_goods_weight = round(
                                (goods_detail.goods_weight * dn_back_order_qty) / 1000, 4)
                            back_order_goods_cost = round(goods_detail.goods_price * dn_back_order_qty, 2)
                            back_order_list.append(DnDetailModel(dn_code=back_order_dn_code,
                                                                 dn_status=2,
                                                                 customer=qs[v].customer,
                                                                 goods_code=dn_detail_list[i].goods_code,
                                                                 goods_desc=dn_detail_list[i].goods_desc,
                                                                 goods_qty=dn_back_order_qty,
                                                                 goods_weight=back_order_goods_weight,
                                                                 goods_volume=back_order_goods_volume,
                                                                 goods_cost=back_order_goods_cost,
                                                                 creater=str(staff_name),
                                                                 back_order_label=True,
                                                                 openid=self.request.auth.openid,
                                                                 create_time=dn_detail_list[i].create_time))
                            back_order_list_label = 1
                            total_weight = total_weight - back_order_goods_weight
                            total_volume = total_volume - back_order_goods_volume
                            other_fees = other_fees - back_order_goods_cost
                            dn_detail_list[i].goods_weight = dn_detail_list[i].goods_weight - \
                                                             back_order_goods_weight
                            dn_detail_list[i].goods_volume = dn_detail_list[i].goods_volume - \
                                                             back_order_goods_volume
                            dn_detail_list[i].goods_cost = dn_detail_list[i].goods_cost - \
                                                           back_order_goods_cost
                            back_order_goods_weight_list.append(back_order_goods_weight)
                            back_order_goods_volume_list.append(back_order_goods_volume)
                            back_order_goods_cost_list.append(back_order_goods_cost)
                            goods_qty_change.save()
                            dn_detail_list[i].save()
                        else:
                            dn_pick_qty = dn_detail_list[i].pick_qty
                            for j in range(len(goods_bin_stock_list)):
                                bin_can_pick_qty = goods_bin_stock_list[j].goods_qty - \
                                                   goods_bin_stock_list[j].pick_qty
                                if bin_can_pick_qty > 0:
                                    goods_bin_stock_list[j].pick_qty = goods_bin_stock_list[
                                                                           j].pick_qty + bin_can_pick_qty
                                    goods_qty_change.ordered_stock = goods_qty_change.ordered_stock - bin_can_pick_qty
                                    goods_qty_change.can_order_stock = goods_qty_change.can_order_stock - bin_can_pick_qty
                                    goods_qty_change.back_order_stock = goods_qty_change.back_order_stock - bin_can_pick_qty
                                    goods_qty_change.pick_stock = goods_qty_change.pick_stock + bin_can_pick_qty
                                    picking_list.append(PickingListModel(openid=self.request.auth.openid,
                                                                         dn_code=dn_detail_list[i].dn_code,
                                                                         bin_name=goods_bin_stock_list[j].bin_name,
                                                                         goods_code=goods_bin_stock_list[
                                                                             j].goods_code,
                                                                         pick_qty=bin_can_pick_qty,
                                                                         creater=str(staff_name),
                                                                         t_code=goods_bin_stock_list[j].t_code))
                                    picking_list_label = 1
                                    dn_pick_qty = dn_pick_qty + bin_can_pick_qty
                                    goods_qty_change.save()
                                    goods_bin_stock_list[j].save()
                                elif bin_can_pick_qty == 0:
                                    continue
                                else:
                                    continue
                            dn_detail_list[i].pick_qty = dn_pick_qty
                            dn_back_order_qty = dn_detail_list[i].goods_qty - \
                                                dn_detail_list[i].pick_qty
                            dn_detail_list[i].goods_qty = dn_pick_qty
                            dn_detail_list[i].dn_status = 3
                            back_order_goods_volume = round(goods_detail.unit_volume * dn_back_order_qty, 4)
                            back_order_goods_weight = round(
                                (goods_detail.goods_weight * dn_back_order_qty) / 1000, 4)
                            back_order_goods_cost = round(goods_detail.goods_price * dn_back_order_qty, 2)
                            back_order_list.append(DnDetailModel(dn_code=back_order_dn_code,
                                                                 dn_status=2,
                                                                 customer=qs[v].customer,
                                                                 goods_code=dn_detail_list[i].goods_code,
                                                                 goods_desc=dn_detail_list[i].goods_desc,
                                                                 goods_qty=dn_back_order_qty,
                                                                 goods_weight=back_order_goods_weight,
                                                                 goods_volume=back_order_goods_volume,
                                                                 goods_cost=back_order_goods_cost,
                                                                 creater=str(staff_name),
                                                                 back_order_label=True,
                                                                 openid=self.request.auth.openid,
                                                                 create_time=dn_detail_list[i].create_time))
                            back_order_list_label = 1
                            total_weight = total_weight - back_order_goods_weight
                            total_volume = total_volume - back_order_goods_volume
                            other_fees = other_fees - back_order_goods_cost
                            dn_detail_list[i].goods_weight = dn_detail_list[i].goods_weight - \
                                                             back_order_goods_weight
                            dn_detail_list[i].goods_volume = dn_detail_list[i].goods_volume - \
                                                             back_order_goods_volume
                            dn_detail_list[i].goods_cost = dn_detail_list[i].goods_cost - \
                                                           back_order_goods_cost
                            back_order_goods_weight_list.append(back_order_goods_weight)
                            back_order_goods_volume_list.append(back_order_goods_volume)
                            back_order_goods_cost_list.append(back_order_goods_cost)
                            dn_detail_list[i].save()
                    elif dn_detail_list[i].goods_qty == can_pick_qty:
                        for j in range(len(goods_bin_stock_list)):
                            bin_can_pick_qty = goods_bin_stock_list[j].goods_qty - goods_bin_stock_list[j].pick_qty
                            if bin_can_pick_qty > 0:
                                dn_need_pick_qty = dn_detail_list[i].goods_qty - dn_detail_list[i].pick_qty
                                if dn_need_pick_qty > bin_can_pick_qty:
                                    goods_bin_stock_list[j].pick_qty = goods_bin_stock_list[
                                                                           j].pick_qty + bin_can_pick_qty
                                    if qs[v].back_order_label is True:
                                        goods_qty_change.can_order_stock = goods_qty_change.can_order_stock - bin_can_pick_qty
                                        goods_qty_change.back_order_stock = goods_qty_change.back_order_stock - bin_can_pick_qty
                                    goods_qty_change.ordered_stock = goods_qty_change.ordered_stock - bin_can_pick_qty
                                    goods_qty_change.pick_stock = goods_qty_change.pick_stock + bin_can_pick_qty
                                    picking_list.append(PickingListModel(openid=self.request.auth.openid,
                                                                         dn_code=dn_detail_list[i].dn_code,
                                                                         bin_name=goods_bin_stock_list[j].bin_name,
                                                                         goods_code=goods_bin_stock_list[j].goods_code,
                                                                         pick_qty=bin_can_pick_qty,
                                                                         creater=str(staff_name),
                                                                         t_code=goods_bin_stock_list[j].t_code))
                                    picking_list_label = 1
                                    dn_detail_list[i].pick_qty = dn_detail_list[i].pick_qty + bin_can_pick_qty
                                    goods_bin_stock_list[j].save()
                                    goods_qty_change.save()
                                elif dn_need_pick_qty == bin_can_pick_qty:
                                    goods_bin_stock_list[j].pick_qty = goods_bin_stock_list[
                                                                           j].pick_qty + bin_can_pick_qty
                                    if qs[v].back_order_label is True:
                                        goods_qty_change.can_order_stock = goods_qty_change.can_order_stock - bin_can_pick_qty
                                        goods_qty_change.back_order_stock = goods_qty_change.back_order_stock - bin_can_pick_qty
                                    goods_qty_change.ordered_stock = goods_qty_change.ordered_stock - bin_can_pick_qty
                                    goods_qty_change.pick_stock = goods_qty_change.pick_stock + bin_can_pick_qty
                                    picking_list.append(PickingListModel(openid=self.request.auth.openid,
                                                                         dn_code=dn_detail_list[i].dn_code,
                                                                         bin_name=goods_bin_stock_list[j].bin_name,
                                                                         goods_code=goods_bin_stock_list[j].goods_code,
                                                                         pick_qty=bin_can_pick_qty,
                                                                         creater=str(staff_name),
                                                                         t_code=goods_bin_stock_list[j].t_code))
                                    picking_list_label = 1
                                    dn_detail_list[i].pick_qty = dn_detail_list[i].pick_qty + bin_can_pick_qty
                                    dn_detail_list[i].dn_status = 3
                                    dn_detail_list[i].save()
                                    goods_bin_stock_list[j].save()
                                    goods_qty_change.save()
                                    break
                                else:
                                    break
                            elif bin_can_pick_qty == 0:
                                continue
                            else:
                                continue
                    elif dn_detail_list[i].goods_qty < can_pick_qty:
                        for j in range(len(goods_bin_stock_list)):
                            bin_can_pick_qty = goods_bin_stock_list[j].goods_qty - \
                                               goods_bin_stock_list[j].pick_qty
                            if bin_can_pick_qty > 0:
                                dn_need_pick_qty = dn_detail_list[i].goods_qty - \
                                                   dn_detail_list[i].pick_qty
                                if dn_need_pick_qty > bin_can_pick_qty:
                                    goods_bin_stock_list[j].pick_qty = goods_bin_stock_list[j].pick_qty + \
                                                                       bin_can_pick_qty
                                    if qs[v].back_order_label is True:
                                        goods_qty_change.can_order_stock = goods_qty_change.can_order_stock - bin_can_pick_qty
                                        goods_qty_change.back_order_stock = goods_qty_change.back_order_stock - bin_can_pick_qty
                                    goods_qty_change.ordered_stock = goods_qty_change.ordered_stock - \
                                                                     bin_can_pick_qty
                                    goods_qty_change.pick_stock = goods_qty_change.pick_stock + \
                                                                  bin_can_pick_qty
                                    picking_list.append(PickingListModel(openid=self.request.auth.openid,
                                                                         dn_code=dn_detail_list[i].dn_code,
                                                                         bin_name=goods_bin_stock_list[j].bin_name,
                                                                         goods_code=goods_bin_stock_list[j].goods_code,
                                                                         pick_qty=bin_can_pick_qty,
                                                                         creater=str(staff_name),
                                                                         t_code=goods_bin_stock_list[j].t_code))
                                    picking_list_label = 1
                                    dn_detail_list[i].pick_qty = dn_detail_list[i].pick_qty + \
                                                                 bin_can_pick_qty
                                    dn_detail_list[i].save()
                                    goods_bin_stock_list[j].save()
                                    goods_qty_change.save()
                                elif dn_need_pick_qty == bin_can_pick_qty:
                                    goods_bin_stock_list[j].pick_qty = goods_bin_stock_list[
                                                                           j].pick_qty + bin_can_pick_qty
                                    if qs[v].back_order_label is True:
                                        goods_qty_change.can_order_stock = goods_qty_change.can_order_stock - bin_can_pick_qty
                                        goods_qty_change.back_order_stock = goods_qty_change.back_order_stock - bin_can_pick_qty
                                    goods_qty_change.ordered_stock = goods_qty_change.ordered_stock - bin_can_pick_qty
                                    goods_qty_change.pick_stock = goods_qty_change.pick_stock + bin_can_pick_qty
                                    picking_list.append(PickingListModel(openid=self.request.auth.openid,
                                                                         dn_code=dn_detail_list[i].dn_code,
                                                                         bin_name=goods_bin_stock_list[j].bin_name,
                                                                         goods_code=goods_bin_stock_list[j].goods_code,
                                                                         pick_qty=bin_can_pick_qty,
                                                                         creater=str(staff_name),
                                                                         t_code=goods_bin_stock_list[j].t_code))
                                    picking_list_label = 1
                                    dn_detail_list[i].pick_qty = dn_detail_list[i].pick_qty + bin_can_pick_qty
                                    dn_detail_list[i].dn_status = 3
                                    dn_detail_list[i].save()
                                    goods_bin_stock_list[j].save()
                                    goods_qty_change.save()
                                    break
                                elif dn_need_pick_qty < bin_can_pick_qty:
                                    goods_bin_stock_list[j].pick_qty = goods_bin_stock_list[j].pick_qty + \
                                                                       dn_need_pick_qty
                                    if qs[v].back_order_label is True:
                                        goods_qty_change.can_order_stock = goods_qty_change.can_order_stock - dn_need_pick_qty
                                        goods_qty_change.back_order_stock = goods_qty_change.back_order_stock - dn_need_pick_qty
                                    goods_qty_change.ordered_stock = goods_qty_change.ordered_stock - \
                                                                     dn_need_pick_qty
                                    goods_qty_change.pick_stock = goods_qty_change.pick_stock + \
                                                                  dn_need_pick_qty
                                    picking_list.append(PickingListModel(openid=self.request.auth.openid,
                                                                         dn_code=dn_detail_list[i].dn_code,
                                                                         bin_name=goods_bin_stock_list[j].bin_name,
                                                                         goods_code=goods_bin_stock_list[j].goods_code,
                                                                         pick_qty=dn_need_pick_qty,
                                                                         creater=str(staff_name),
                                                                         t_code=goods_bin_stock_list[j].t_code))
                                    picking_list_label = 1
                                    dn_detail_list[i].pick_qty = dn_detail_list[i].pick_qty + dn_need_pick_qty
                                    dn_detail_list[i].dn_status = 3
                                    dn_detail_list[i].save()
                                    goods_bin_stock_list[j].save()
                                    goods_qty_change.save()
                                    break
                                else:
                                    break
                            elif bin_can_pick_qty == 0:
                                continue
                            else:
                                continue
                elif can_pick_qty == 0:
                    if qs[v].back_order_label is False:
                        goods_qty_change.back_order_stock = goods_qty_change.back_order_stock + dn_detail_list[
                            i].goods_qty
                        back_order_goods_volume = round(goods_detail.unit_volume * dn_detail_list[i].goods_qty, 4)
                        back_order_goods_weight = round(
                            (goods_detail.goods_weight * dn_detail_list[i].goods_qty) / 1000, 4)
                        back_order_goods_cost = round(goods_detail.goods_price * dn_detail_list[i].goods_qty, 2)
                        back_order_list.append(DnDetailModel(dn_code=back_order_dn_code,
                                                             dn_status=2,
                                                             customer=qs[v].customer,
                                                             goods_code=dn_detail_list[i].goods_code,
                                                             goods_desc=dn_detail_list[i].goods_desc,
                                                             goods_qty=dn_detail_list[i].goods_qty,
                                                             goods_weight=back_order_goods_weight,
                                                             goods_volume=back_order_goods_volume,
                                                             goods_cost=back_order_goods_cost,
                                                             creater=str(staff_name),
                                                             back_order_label=True,
                                                             openid=self.request.auth.openid,
                                                             create_time=dn_detail_list[i].create_time))
                        back_order_list_label = 1
                        total_weight = total_weight - back_order_goods_weight
                        total_volume = total_volume - back_order_goods_volume
                        other_fees = other_fees - back_order_goods_cost
                        back_order_goods_weight_list.append(back_order_goods_weight)
                        back_order_goods_volume_list.append(back_order_goods_volume)
                        back_order_goods_cost_list.append(back_order_goods_cost)
                        dn_detail_list[i].is_delete = True
                        dn_detail_list[i].save()
                        goods_qty_change.save()
                    else:
                        continue
                else:
                    continue
            if picking_list_label == 1:
                if back_order_list_label == 1:
                    back_order_total_volume = sumOfList(back_order_goods_volume_list,
                                                        len(back_order_goods_volume_list))
                    back_order_total_weight = sumOfList(back_order_goods_weight_list,
                                                        len(back_order_goods_weight_list))
                    back_order_other_fees = sumOfList(back_order_goods_cost_list,
                                                      len(back_order_goods_cost_list))
                    customer_city = customer.objects.filter(openid=self.request.auth.openid,
                                                            customer_name=str(qs[v].customer),
                                                            is_delete=False).first().customer_city
                    warehouse_city = warehouse.objects.filter(
                        openid=self.request.auth.openid).first().warehouse_city
                    transportation_fee = transportation.objects.filter(
                        Q(openid=self.request.auth.openid, send_city__icontains=warehouse_city,
                          receiver_city__icontains=customer_city,
                          is_delete=False) | Q(openid='init_data', send_city__icontains=warehouse_city,
                                               receiver_city__icontains=customer_city,
                                               is_delete=False))
                    transportation_res = {
                        "detail": []
                    }
                    transportation_back_order_res = {
                        "detail": []
                    }
                    if len(transportation_fee) >= 1:
                        transportation_list = []
                        transportation_back_order_list = []
                        for k in range(len(transportation_fee)):
                            transportation_cost = transportation_calculate(total_weight,
                                                                           total_volume,
                                                                           transportation_fee[k].weight_fee,
                                                                           transportation_fee[k].volume_fee,
                                                                           transportation_fee[k].min_payment)
                            transportation_back_order_cost = transportation_calculate(back_order_total_weight,
                                                                                      back_order_total_volume,
                                                                                      transportation_fee[k].weight_fee,
                                                                                      transportation_fee[k].volume_fee,
                                                                                      transportation_fee[k].min_payment)
                            transportation_detail = {
                                "transportation_supplier": transportation_fee[k].transportation_supplier,
                                "transportation_cost": transportation_cost
                            }
                            transportation_back_order_detail = {
                                "transportation_supplier": transportation_fee[k].transportation_supplier,
                                "transportation_cost": transportation_back_order_cost
                            }
                            transportation_list.append(transportation_detail)
                            transportation_back_order_list.append(transportation_back_order_detail)
                        transportation_res['detail'] = transportation_list
                        transportation_back_order_res['detail'] = transportation_back_order_list
                    DnListModel.objects.create(openid=self.request.auth.openid,
                                               dn_code=back_order_dn_code,
                                               dn_status=2,
                                               total_weight=back_order_total_weight,
                                               total_volume=back_order_total_volume,
                                               other_fees=back_order_other_fees,
                                               customer=qs[v].customer,
                                               creater=str(staff_name),
                                               bar_code=bar_code,
                                               back_order_label=True,
                                               transportation_fee=transportation_back_order_res,
                                               create_time=qs[v].create_time)
                    scanner.objects.create(openid=self.request.auth.openid, mode="DN", code=back_order_dn_code,
                                           bar_code=bar_code)
                    PickingListModel.objects.bulk_create(picking_list, batch_size=100)
                    DnDetailModel.objects.bulk_create(back_order_list, batch_size=100)
                    qs[v].total_weight = total_weight
                    qs[v].total_volume = total_volume
                    qs[v].other_fees = other_fees
                    qs[v].transportation_fee = transportation_res
                    qs[v].dn_status = 3
                    qs[v].save()
                elif back_order_list_label == 0:
                    PickingListModel.objects.bulk_create(picking_list, batch_size=100)
                    qs[v].dn_status = 3
                    qs[v].save()
            elif picking_list_label == 0:
                if back_order_list_label == 1:
                    DnDetailModel.objects.bulk_create(back_order_list, batch_size=100)
                    DnListModel.objects.create(openid=self.request.auth.openid,
                                               dn_code=back_order_dn_code,
                                               dn_status=2,
                                               total_weight=qs[v].total_weight,
                                               total_volume=qs[v].total_volume,
                                               other_fees=qs[v].other_fees,
                                               customer=qs[v].customer,
                                               creater=str(staff_name),
                                               bar_code=bar_code,
                                               back_order_label=True,
                                               transportation_fee=qs[v].transportation_fee,
                                               create_time=qs[v].create_time)
                    scanner.objects.create(openid=self.request.auth.openid, mode="DN", code=back_order_dn_code,
                                           bar_code=bar_code)
                    qs[v].is_delete = True
                    qs[v].dn_status = 3
                    qs[v].save()
            else:
                continue
        return Response({"detail": "success"}, status=200)

    def update(self, request, pk):
        qs = self.get_object()
        if qs.openid != self.request.auth.openid:
            raise APIException({"detail": "Cannot Release Order Data Which Not Yours"})
        else:
            if qs.dn_status == 2:
                staff_name = staff.objects.filter(openid=self.request.auth.openid,
                                                  id=self.request.META.get('HTTP_OPERATOR')).first().staff_name
                dn_detail_list = DnDetailModel.objects.filter(openid=self.request.auth.openid,
                                                              dn_code=qs.dn_code,
                                                              dn_status=2, is_delete=False)
                picking_list = []
                picking_list_label = 0
                back_order_list = []
                back_order_list_label = 0
                back_order_goods_weight_list = []
                back_order_goods_volume_list = []
                back_order_goods_cost_list = []
                back_order_base_code = DnListModel.objects.filter(openid=self.request.auth.openid, is_delete=False).order_by('-id').first().dn_code
                dn_last_code = re.findall(r'\d+', str(back_order_base_code), re.IGNORECASE)
                back_order_dn_code = 'DN' + str(int(dn_last_code[0]) + 1).zfill(8)
                bar_code = Md5.md5(back_order_dn_code)
                total_weight = qs.total_weight
                total_volume = qs.total_volume
                other_fees = qs.other_fees
                for i in range(len(dn_detail_list)):
                    goods_detail = goods.objects.filter(openid=self.request.auth.openid,
                                                        goods_code=str(dn_detail_list[i].goods_code),
                                                        is_delete=False).first()
                    if stocklist.objects.filter(openid=self.request.auth.openid,
                                                goods_code=str(dn_detail_list[i].goods_code)).exists():
                        pass
                    else:
                        stocklist.objects.create(openid=self.request.auth.openid,
                                                 goods_code=str(goods_detail.goods_code),
                                                 goods_desc=goods_detail.goods_desc,
                                                 dn_stock=int(dn_detail_list[i].goods_qty))
                    goods_qty_change = stocklist.objects.filter(openid=self.request.auth.openid,
                                                                goods_code=str(
                                                                    dn_detail_list[i].goods_code)).first()
                    goods_bin_stock_list = stockbin.objects.filter(openid=self.request.auth.openid,
                                                                   goods_code=str(dn_detail_list[i].goods_code),
                                                                   bin_property="Normal", goods_qty__gt=0).order_by('id')
                    can_pick_qty = goods_qty_change.onhand_stock - \
                                   goods_qty_change.inspect_stock - \
                                   goods_qty_change.hold_stock - \
                                   goods_qty_change.damage_stock - \
                                   goods_qty_change.pick_stock
                    if can_pick_qty > 0:
                        if dn_detail_list[i].goods_qty > can_pick_qty:
                            if qs.back_order_label is False:
                                dn_pick_qty = dn_detail_list[i].pick_qty
                                for j in range(len(goods_bin_stock_list)):
                                    bin_can_pick_qty = goods_bin_stock_list[j].goods_qty - \
                                                       goods_bin_stock_list[j].pick_qty
                                    if bin_can_pick_qty > 0:
                                        goods_bin_stock_list[j].pick_qty = goods_bin_stock_list[
                                                                               j].pick_qty + bin_can_pick_qty
                                        goods_qty_change.ordered_stock = goods_qty_change.ordered_stock - bin_can_pick_qty
                                        goods_qty_change.pick_stock = goods_qty_change.pick_stock + bin_can_pick_qty
                                        picking_list.append(PickingListModel(openid=self.request.auth.openid,
                                                                             dn_code=dn_detail_list[i].dn_code,
                                                                             bin_name=goods_bin_stock_list[j].bin_name,
                                                                             goods_code=goods_bin_stock_list[
                                                                                 j].goods_code,
                                                                             pick_qty=bin_can_pick_qty,
                                                                             creater=str(staff_name),
                                                                             t_code=goods_bin_stock_list[j].t_code))
                                        picking_list_label = 1
                                        dn_pick_qty = dn_pick_qty + bin_can_pick_qty
                                        goods_qty_change.save()
                                        goods_bin_stock_list[j].save()
                                    elif bin_can_pick_qty == 0:
                                        continue
                                    else:
                                        continue
                                dn_detail_list[i].pick_qty = dn_pick_qty
                                dn_back_order_qty = dn_detail_list[i].goods_qty - \
                                                   dn_detail_list[i].pick_qty
                                goods_qty_change.back_order_stock = dn_detail_list[i].goods_qty - can_pick_qty
                                dn_detail_list[i].goods_qty = dn_pick_qty
                                dn_detail_list[i].dn_status = 3
                                back_order_goods_volume = round(goods_detail.unit_volume * dn_back_order_qty, 4)
                                back_order_goods_weight = round(
                                    (goods_detail.goods_weight * dn_back_order_qty) / 1000, 4)
                                back_order_goods_cost = round(goods_detail.goods_price * dn_back_order_qty, 2)
                                back_order_list.append(DnDetailModel(dn_code=back_order_dn_code,
                                                                     dn_status=2,
                                                                     customer=qs.customer,
                                                                     goods_code=dn_detail_list[i].goods_code,
                                                                     goods_desc=dn_detail_list[i].goods_desc,
                                                                     goods_qty=dn_back_order_qty,
                                                                     goods_weight=back_order_goods_weight,
                                                                     goods_volume=back_order_goods_volume,
                                                                     goods_cost=back_order_goods_cost,
                                                                     creater=str(staff_name),
                                                                     back_order_label=True,
                                                                     openid=self.request.auth.openid,
                                                                     create_time=dn_detail_list[i].create_time))
                                back_order_list_label = 1
                                total_weight = total_weight - back_order_goods_weight
                                total_volume = total_volume - back_order_goods_volume
                                other_fees = other_fees - back_order_goods_cost
                                dn_detail_list[i].goods_weight = dn_detail_list[i].goods_weight - \
                                                                 back_order_goods_weight
                                dn_detail_list[i].goods_volume = dn_detail_list[i].goods_volume - \
                                                                 back_order_goods_volume
                                dn_detail_list[i].goods_cost = dn_detail_list[i].goods_cost - \
                                                                 back_order_goods_cost
                                back_order_goods_weight_list.append(back_order_goods_weight)
                                back_order_goods_volume_list.append(back_order_goods_volume)
                                back_order_goods_cost_list.append(back_order_goods_cost)
                                goods_qty_change.save()
                                dn_detail_list[i].save()
                            else:
                                dn_pick_qty = dn_detail_list[i].pick_qty
                                for j in range(len(goods_bin_stock_list)):
                                    bin_can_pick_qty = goods_bin_stock_list[j].goods_qty - \
                                                       goods_bin_stock_list[j].pick_qty
                                    if bin_can_pick_qty > 0:
                                        goods_bin_stock_list[j].pick_qty = goods_bin_stock_list[
                                                                               j].pick_qty + bin_can_pick_qty
                                        goods_qty_change.ordered_stock = goods_qty_change.ordered_stock - bin_can_pick_qty
                                        goods_qty_change.can_order_stock = goods_qty_change.can_order_stock - bin_can_pick_qty
                                        goods_qty_change.back_order_stock = goods_qty_change.back_order_stock - bin_can_pick_qty
                                        goods_qty_change.pick_stock = goods_qty_change.pick_stock + bin_can_pick_qty
                                        picking_list.append(PickingListModel(openid=self.request.auth.openid,
                                                                             dn_code=dn_detail_list[i].dn_code,
                                                                             bin_name=goods_bin_stock_list[j].bin_name,
                                                                             goods_code=goods_bin_stock_list[
                                                                                 j].goods_code,
                                                                             pick_qty=bin_can_pick_qty,
                                                                             creater=str(staff_name),
                                                                             t_code=goods_bin_stock_list[j].t_code))
                                        picking_list_label = 1
                                        dn_pick_qty = dn_pick_qty + bin_can_pick_qty
                                        goods_qty_change.save()
                                        goods_bin_stock_list[j].save()
                                    elif bin_can_pick_qty == 0:
                                        continue
                                    else:
                                        continue
                                dn_detail_list[i].pick_qty = dn_pick_qty
                                dn_back_order_qty = dn_detail_list[i].goods_qty - \
                                                    dn_detail_list[i].pick_qty
                                dn_detail_list[i].goods_qty = dn_pick_qty
                                dn_detail_list[i].dn_status = 3
                                back_order_goods_volume = round(goods_detail.unit_volume * dn_back_order_qty, 4)
                                back_order_goods_weight = round(
                                    (goods_detail.goods_weight * dn_back_order_qty) / 1000, 4)
                                back_order_goods_cost = round(goods_detail.goods_price * dn_back_order_qty, 2)
                                back_order_list.append(DnDetailModel(dn_code=back_order_dn_code,
                                                                     dn_status=2,
                                                                     customer=qs.customer,
                                                                     goods_code=dn_detail_list[i].goods_code,
                                                                     goods_desc=dn_detail_list[i].goods_desc,
                                                                     goods_qty=dn_back_order_qty,
                                                                     goods_weight=back_order_goods_weight,
                                                                     goods_volume=back_order_goods_volume,
                                                                     goods_cost=back_order_goods_cost,
                                                                     creater=str(staff_name),
                                                                     back_order_label=True,
                                                                     openid=self.request.auth.openid,
                                                                     create_time=dn_detail_list[i].create_time))
                                back_order_list_label = 1
                                total_weight = total_weight - back_order_goods_weight
                                total_volume = total_volume - back_order_goods_volume
                                other_fees = other_fees - back_order_goods_cost
                                dn_detail_list[i].goods_weight = dn_detail_list[i].goods_weight - \
                                                                 back_order_goods_weight
                                dn_detail_list[i].goods_volume = dn_detail_list[i].goods_volume - \
                                                                 back_order_goods_volume
                                dn_detail_list[i].goods_cost = dn_detail_list[i].goods_cost - \
                                                                 back_order_goods_cost
                                back_order_goods_weight_list.append(back_order_goods_weight)
                                back_order_goods_volume_list.append(back_order_goods_volume)
                                back_order_goods_cost_list.append(back_order_goods_cost)
                                dn_detail_list[i].save()
                        elif dn_detail_list[i].goods_qty == can_pick_qty:
                            for j in range(len(goods_bin_stock_list)):
                                bin_can_pick_qty = goods_bin_stock_list[j].goods_qty - goods_bin_stock_list[j].pick_qty
                                if bin_can_pick_qty > 0:
                                    dn_need_pick_qty = dn_detail_list[i].goods_qty - dn_detail_list[i].pick_qty
                                    if dn_need_pick_qty > bin_can_pick_qty:
                                        goods_bin_stock_list[j].pick_qty = goods_bin_stock_list[
                                                                               j].pick_qty + bin_can_pick_qty
                                        if qs.back_order_label is True:
                                            goods_qty_change.can_order_stock = goods_qty_change.can_order_stock - bin_can_pick_qty
                                            goods_qty_change.back_order_stock = goods_qty_change.back_order_stock - bin_can_pick_qty
                                        goods_qty_change.ordered_stock = goods_qty_change.ordered_stock - bin_can_pick_qty
                                        goods_qty_change.pick_stock = goods_qty_change.pick_stock + bin_can_pick_qty
                                        picking_list.append(PickingListModel(openid=self.request.auth.openid,
                                                                             dn_code=dn_detail_list[i].dn_code,
                                                                             bin_name=goods_bin_stock_list[j].bin_name,
                                                                             goods_code=goods_bin_stock_list[j].goods_code,
                                                                             pick_qty=bin_can_pick_qty,
                                                                             creater=str(staff_name),
                                                                             t_code=goods_bin_stock_list[j].t_code))
                                        picking_list_label = 1
                                        dn_detail_list[i].pick_qty = dn_detail_list[i].pick_qty + bin_can_pick_qty
                                        goods_bin_stock_list[j].save()
                                        goods_qty_change.save()
                                    elif dn_need_pick_qty == bin_can_pick_qty:
                                        goods_bin_stock_list[j].pick_qty = goods_bin_stock_list[
                                                                               j].pick_qty + bin_can_pick_qty
                                        if qs.back_order_label is True:
                                            goods_qty_change.can_order_stock = goods_qty_change.can_order_stock - bin_can_pick_qty
                                            goods_qty_change.back_order_stock = goods_qty_change.back_order_stock - bin_can_pick_qty
                                        goods_qty_change.ordered_stock = goods_qty_change.ordered_stock - bin_can_pick_qty
                                        goods_qty_change.pick_stock = goods_qty_change.pick_stock + bin_can_pick_qty
                                        picking_list.append(PickingListModel(openid=self.request.auth.openid,
                                                                             dn_code=dn_detail_list[i].dn_code,
                                                                             bin_name=goods_bin_stock_list[j].bin_name,
                                                                             goods_code=goods_bin_stock_list[j].goods_code,
                                                                             pick_qty=bin_can_pick_qty,
                                                                             creater=str(staff_name),
                                                                             t_code=goods_bin_stock_list[j].t_code))
                                        picking_list_label = 1
                                        dn_detail_list[i].pick_qty = dn_detail_list[i].pick_qty + bin_can_pick_qty
                                        dn_detail_list[i].dn_status = 3
                                        dn_detail_list[i].save()
                                        goods_bin_stock_list[j].save()
                                        goods_qty_change.save()
                                        break
                                    else:
                                        break
                                elif bin_can_pick_qty == 0:
                                    continue
                                else:
                                    continue
                        elif dn_detail_list[i].goods_qty < can_pick_qty:
                            for j in range(len(goods_bin_stock_list)):
                                bin_can_pick_qty = goods_bin_stock_list[j].goods_qty - \
                                                   goods_bin_stock_list[j].pick_qty
                                if bin_can_pick_qty > 0:
                                    dn_need_pick_qty = dn_detail_list[i].goods_qty - \
                                                       dn_detail_list[i].pick_qty
                                    if dn_need_pick_qty > bin_can_pick_qty:
                                        goods_bin_stock_list[j].pick_qty = goods_bin_stock_list[j].pick_qty + \
                                                                           bin_can_pick_qty
                                        if qs.back_order_label is True:
                                            goods_qty_change.can_order_stock = goods_qty_change.can_order_stock - bin_can_pick_qty
                                            goods_qty_change.back_order_stock = goods_qty_change.back_order_stock - bin_can_pick_qty
                                        goods_qty_change.ordered_stock = goods_qty_change.ordered_stock - \
                                                                         bin_can_pick_qty
                                        goods_qty_change.pick_stock = goods_qty_change.pick_stock + \
                                                                      bin_can_pick_qty
                                        picking_list.append(PickingListModel(openid=self.request.auth.openid,
                                                                             dn_code=dn_detail_list[i].dn_code,
                                                                             bin_name=goods_bin_stock_list[j].bin_name,
                                                                             goods_code=goods_bin_stock_list[j].goods_code,
                                                                             pick_qty=bin_can_pick_qty,
                                                                             creater=str(staff_name),
                                                                             t_code=goods_bin_stock_list[j].t_code))
                                        picking_list_label = 1
                                        dn_detail_list[i].pick_qty = dn_detail_list[i].pick_qty + \
                                                                     bin_can_pick_qty
                                        dn_detail_list[i].save()
                                        goods_bin_stock_list[j].save()
                                        goods_qty_change.save()
                                    elif dn_need_pick_qty == bin_can_pick_qty:
                                        goods_bin_stock_list[j].pick_qty = goods_bin_stock_list[
                                                                               j].pick_qty + bin_can_pick_qty
                                        if qs.back_order_label is True:
                                            goods_qty_change.can_order_stock = goods_qty_change.can_order_stock - bin_can_pick_qty
                                            goods_qty_change.back_order_stock = goods_qty_change.back_order_stock - bin_can_pick_qty
                                        goods_qty_change.ordered_stock = goods_qty_change.ordered_stock - bin_can_pick_qty
                                        goods_qty_change.pick_stock = goods_qty_change.pick_stock + bin_can_pick_qty
                                        picking_list.append(PickingListModel(openid=self.request.auth.openid,
                                                                             dn_code=dn_detail_list[i].dn_code,
                                                                             bin_name=goods_bin_stock_list[j].bin_name,
                                                                             goods_code=goods_bin_stock_list[j].goods_code,
                                                                             pick_qty=bin_can_pick_qty,
                                                                             creater=str(staff_name),
                                                                             t_code=goods_bin_stock_list[j].t_code))
                                        picking_list_label = 1
                                        dn_detail_list[i].pick_qty = dn_detail_list[i].pick_qty + bin_can_pick_qty
                                        dn_detail_list[i].dn_status = 3
                                        dn_detail_list[i].save()
                                        goods_bin_stock_list[j].save()
                                        goods_qty_change.save()
                                        break
                                    elif dn_need_pick_qty < bin_can_pick_qty:
                                        goods_bin_stock_list[j].pick_qty = goods_bin_stock_list[j].pick_qty + \
                                                                           dn_need_pick_qty
                                        if qs.back_order_label is True:
                                            goods_qty_change.can_order_stock = goods_qty_change.can_order_stock - dn_need_pick_qty
                                            goods_qty_change.back_order_stock = goods_qty_change.back_order_stock - dn_need_pick_qty
                                        goods_qty_change.ordered_stock = goods_qty_change.ordered_stock - \
                                                                         dn_need_pick_qty
                                        goods_qty_change.pick_stock = goods_qty_change.pick_stock + \
                                                                      dn_need_pick_qty
                                        picking_list.append(PickingListModel(openid=self.request.auth.openid,
                                                                             dn_code=dn_detail_list[i].dn_code,
                                                                             bin_name=goods_bin_stock_list[j].bin_name,
                                                                             goods_code=goods_bin_stock_list[j].goods_code,
                                                                             pick_qty=dn_need_pick_qty,
                                                                             creater=str(staff_name),
                                                                             t_code=goods_bin_stock_list[j].t_code))
                                        picking_list_label = 1
                                        dn_detail_list[i].pick_qty = dn_detail_list[i].pick_qty + dn_need_pick_qty
                                        dn_detail_list[i].dn_status = 3
                                        dn_detail_list[i].save()
                                        goods_bin_stock_list[j].save()
                                        goods_qty_change.save()
                                        break
                                    else:
                                        break
                                elif bin_can_pick_qty == 0:
                                    continue
                                else:
                                    continue
                    elif can_pick_qty == 0:
                        if qs.back_order_label is False:
                            goods_qty_change.back_order_stock = goods_qty_change.back_order_stock + dn_detail_list[i].goods_qty
                            back_order_goods_volume = round(goods_detail.unit_volume * dn_detail_list[i].goods_qty, 4)
                            back_order_goods_weight = round((goods_detail.goods_weight * dn_detail_list[i].goods_qty) / 1000, 4)
                            back_order_goods_cost = round(goods_detail.goods_price * dn_detail_list[i].goods_qty, 2)
                            back_order_list.append(DnDetailModel(dn_code=back_order_dn_code,
                                                                 dn_status=2,
                                                                 customer=qs.customer,
                                                                 goods_code=dn_detail_list[i].goods_code,
                                                                 goods_desc=dn_detail_list[i].goods_desc,
                                                                 goods_qty=dn_detail_list[i].goods_qty,
                                                                 goods_weight=back_order_goods_weight,
                                                                 goods_volume=back_order_goods_volume,
                                                                 goods_cost=back_order_goods_cost,
                                                                 creater=str(staff_name),
                                                                 back_order_label=True,
                                                                 openid=self.request.auth.openid,
                                                                 create_time=dn_detail_list[i].create_time))
                            back_order_list_label = 1
                            total_weight = total_weight - back_order_goods_weight
                            total_volume = total_volume - back_order_goods_volume
                            other_fees = other_fees - back_order_goods_cost
                            back_order_goods_weight_list.append(back_order_goods_weight)
                            back_order_goods_volume_list.append(back_order_goods_volume)
                            back_order_goods_cost_list.append(back_order_goods_cost)
                            dn_detail_list[i].is_delete = True
                            dn_detail_list[i].save()
                            goods_qty_change.save()
                        else:
                            continue
                    else:
                        continue
                if picking_list_label == 1:
                    if back_order_list_label == 1:
                        back_order_total_volume = sumOfList(back_order_goods_volume_list,
                                                            len(back_order_goods_volume_list))
                        back_order_total_weight = sumOfList(back_order_goods_weight_list,
                                                            len(back_order_goods_weight_list))
                        back_order_other_fees = sumOfList(back_order_goods_cost_list,
                                                            len(back_order_goods_cost_list))
                        customer_city = customer.objects.filter(openid=self.request.auth.openid,
                                                                customer_name=str(qs.customer),
                                                                is_delete=False).first().customer_city
                        warehouse_city = warehouse.objects.filter(
                            openid=self.request.auth.openid).first().warehouse_city
                        transportation_fee = transportation.objects.filter(
                            Q(openid=self.request.auth.openid, send_city__icontains=warehouse_city,
                              receiver_city__icontains=customer_city,
                              is_delete=False) | Q(openid='init_data', send_city__icontains=warehouse_city,
                                                   receiver_city__icontains=customer_city,
                                                   is_delete=False))
                        transportation_res = {
                            "detail": []
                        }
                        transportation_back_order_res = {
                            "detail": []
                        }
                        if len(transportation_fee) >= 1:
                            transportation_list = []
                            transportation_back_order_list = []
                            for k in range(len(transportation_fee)):
                                transportation_cost = transportation_calculate(total_weight,
                                                                               total_volume,
                                                                               transportation_fee[k].weight_fee,
                                                                               transportation_fee[k].volume_fee,
                                                                               transportation_fee[k].min_payment)
                                transportation_back_order_cost = transportation_calculate(back_order_total_weight,
                                                                               back_order_total_volume,
                                                                               transportation_fee[k].weight_fee,
                                                                               transportation_fee[k].volume_fee,
                                                                               transportation_fee[k].min_payment)
                                transportation_detail = {
                                    "transportation_supplier": transportation_fee[k].transportation_supplier,
                                    "transportation_cost": transportation_cost
                                }
                                transportation_back_order_detail = {
                                    "transportation_supplier": transportation_fee[k].transportation_supplier,
                                    "transportation_cost": transportation_back_order_cost
                                }
                                transportation_list.append(transportation_detail)
                                transportation_back_order_list.append(transportation_back_order_detail)
                            transportation_res['detail'] = transportation_list
                            transportation_back_order_res['detail'] = transportation_back_order_list
                        DnListModel.objects.create(openid=self.request.auth.openid,
                                                   dn_code=back_order_dn_code,
                                                   dn_status=2,
                                                   total_weight=back_order_total_weight,
                                                   total_volume=back_order_total_volume,
                                                   other_fees=back_order_other_fees,
                                                   customer=qs.customer,
                                                   creater=str(staff_name),
                                                   bar_code=bar_code,
                                                   back_order_label=True,
                                                   transportation_fee=transportation_back_order_res,
                                                   create_time=qs.create_time)
                        scanner.objects.create(openid=self.request.auth.openid, mode="DN", code=back_order_dn_code,
                                               bar_code=bar_code)
                        PickingListModel.objects.bulk_create(picking_list, batch_size=100)
                        DnDetailModel.objects.bulk_create(back_order_list, batch_size=100)
                        qs.total_weight = total_weight
                        qs.total_volume = total_volume
                        qs.other_fees = other_fees
                        qs.transportation_fee = transportation_res
                        qs.dn_status = 3
                        qs.save()
                    elif back_order_list_label == 0:
                        PickingListModel.objects.bulk_create(picking_list, batch_size=100)
                        qs.dn_status = 3
                        qs.save()
                elif picking_list_label == 0:
                    if back_order_list_label == 1:
                        DnDetailModel.objects.bulk_create(back_order_list, batch_size=100)
                        DnListModel.objects.create(openid=self.request.auth.openid,
                                                   dn_code=back_order_dn_code,
                                                   dn_status=2,
                                                   total_weight=qs.total_weight,
                                                   total_volume=qs.total_volume,
                                                   other_fees=qs.other_fees,
                                                   customer=qs.customer,
                                                   creater=str(staff_name),
                                                   bar_code=bar_code,
                                                   back_order_label=True,
                                                   transportation_fee=qs.transportation_fee,
                                                   create_time=qs.create_time)
                        scanner.objects.create(openid=self.request.auth.openid, mode="DN", code=back_order_dn_code,
                                               bar_code=bar_code)
                        qs.is_delete = True
                        qs.dn_status = 3
                        qs.save()
                return Response({"detail": "success"}, status=200)
            else:
                raise APIException({"detail": "This Order Does Not in Release Status"})

class DnPickingListViewSet(viewsets.ModelViewSet):
    """
        retrieve:
            Picklist for pk
    """
    pagination_class = MyPageNumberPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter, ]
    ordering_fields = ['id', "create_time", "update_time", ]
    filter_class = DnListFilter

    def get_project(self):
        try:
            id = self.kwargs.get('pk')
            return id
        except:
            return None

    def get_queryset(self):
        id = self.get_project()
        if self.request.user:
            return DnListModel.objects.filter(openid=self.request.auth.openid, id=id)
        else:
            return DnListModel.objects.none()

    def get_serializer_class(self):
        if self.action in ['retrieve']:
            return serializers.DNListGetSerializer
        else:
            return self.http_method_not_allowed(request=self.request)

    def retrieve(self, request, pk):
        qs = self.get_object()
        if qs.dn_status < 3:
            raise APIException({"detail": "No Picking List Been Created"})
        else:
            picking_qs = PickingListModel.objects.filter(openid=self.request.auth.openid, dn_code=qs.dn_code)
            serializer = serializers.DNPickingListGetSerializer(picking_qs, many=True)
            return Response(serializer.data, status=200)

class DnPickingListFilterViewSet(viewsets.ModelViewSet):
    """
        list:
            Picklist for Filter
    """
    pagination_class = MyPageNumberPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter, ]
    ordering_fields = ['id', "create_time", "update_time", ]
    filter_class = DnPickingListFilter

    def get_queryset(self):
        if self.request.user:
            return PickingListModel.objects.filter(openid=self.request.auth.openid)
        else:
            return PickingListModel.objects.none()

    def get_serializer_class(self):
        if self.action in ['list']:
            return serializers.DNPickingCheckGetSerializer
        else:
            return self.http_method_not_allowed(request=self.request)

class DnPickedViewSet(viewsets.ModelViewSet):
    """
        create:
            Finish Picked
    """
    # 原写法：带分页
    # pagination_class = MyPageNumberPagination
    # NEW：拣货提交通常不分页，减少不必要的开销
    pagination_class = None  # NEW

    filter_backends = [DjangoFilterBackend, OrderingFilter, ]
    ordering_fields = ['id', "create_time", "update_time", ]

    # 原写法（django-filter 旧属性）
    # filter_class = DnListFilter
    # NEW：统一使用 django-filter 2.x 的属性
    filterset_class = DnListFilter  # NEW

    def get_project(self):
        try:
            id = self.kwargs.get('pk')
            return id
        except:
            return None

    def get_queryset(self):
        id = self.get_project()
        if self.request.user:
            if id is None:
                return DnListModel.objects.filter(openid=self.request.auth.openid, is_delete=False)
            else:
                return DnListModel.objects.filter(openid=self.request.auth.openid, id=id, is_delete=False)
        else:
            return DnListModel.objects.none()

    def get_serializer_class(self):
        if self.action in ['create', 'update']:
            return serializers.DNListUpdateSerializer
        else:
            return self.http_method_not_allowed(request=self.request)

    # ========= 原 create（依赖状态3/拣货单/库存与货位的多处联动） =========
    # def create(self, request, pk):
    #     delete_data = stockbin.objects.filter(openid=self.request.auth.openid,
    #                                                goods_qty=0,
    #                                                pick_qty=0,
    #                                                picked_qty=0)
    #     if delete_data.exists():
    #         for i in delete_data:
    #             i.delete()
    #     qs = self.get_object()
    #     if qs.dn_status != 3:
    #         raise APIException({"detail": "This dn Status Not Pre Pick"})
    #     else:
    #         data = self.request.data
    #         for i in range(len(data['goodsData'])):
    #             pick_qty_change = PickingListModel.objects.filter(openid=self.request.auth.openid,
    #                                                               dn_code=str(data['dn_code']),
    #                                                               picking_status=0,
    #                                                               t_code=str(data['goodsData'][i].get('t_code'))).first()
    #             if int(data['goodsData'][i].get('pick_qty')) < 0:
    #                 raise APIException({"detail": str(data['goodsData'][i].get('goods_code')) + " Picked Qty Must >= 0"})
    #             else:
    #                 if int(data['goodsData'][i].get('pick_qty')) > pick_qty_change.pick_qty:
    #                     raise APIException({"detail": str(data['goodsData'][i].get('goods_code')) + " Picked Qty Must Less Than Pick Qty"})
    #                 else:
    #                     continue
    #         qs.dn_status = 4
    #         staff_name = staff.objects.filter(openid=self.request.auth.openid,
    #                                           id=self.request.META.get('HTTP_OPERATOR')).first().staff_name
    #         for j in range(len(data['goodsData'])):
    #             goods_qty_change = stocklist.objects.filter(openid=self.request.auth.openid,
    #                                                         goods_code=str(data['goodsData'][j].get('goods_code'))).first()
    #             dn_detail = DnDetailModel.objects.filter(openid=self.request.auth.openid,
    #                                                      dn_code=str(data['dn_code']),
    #                                                      customer=str(data['customer']),
    #                                                      goods_code=str(data['goodsData'][j].get('goods_code'))).first()
    #             bin_qty_change = stockbin.objects.filter(openid=self.request.auth.openid,
    #                                                      t_code=str(data['goodsData'][j].get('t_code'))).first()
    #             pick_qty_change = PickingListModel.objects.filter(openid=self.request.auth.openid,
    #                                                               dn_code=str(data['dn_code']),
    #                                                               picking_status=0,
    #                                                               t_code=str(data['goodsData'][j].get('t_code'))).first()
    #             qtychangerecorder.objects.create(...)
    #             ...
    #             if int(data['goodsData'][j].get('pick_qty')) == pick_qty_change.pick_qty:
    #                 goods_qty_change.onhand_stock = ...
    #                 ...
    #             elif int(data['goodsData'][j].get('pick_qty')) < pick_qty_change.pick_qty:
    #                 goods_qty_change.onhand_stock = ...
    #                 ...
    #             dn_detail.picked_qty = dn_detail.picked_qty + int(data['goodsData'][j].get('pick_qty'))
    #             if dn_detail.dn_status == 3:
    #                 dn_detail.dn_status = 4
    #             if dn_detail.pick_qty > 0:
    #                 dn_detail.pick_qty = 0
    #             dn_detail.save()
    #         if DnDetailModel.objects.filter(openid=self.request.auth.openid, dn_code=str(data['dn_code']), dn_status=3).exists() is False:
    #             qs.save()
    #         return Response({"Detail": "success"}, status=200)

    # ========= NEW create：去掉“待拣货/匹配”，允许 1/4 → 4，直接累计 picked_qty =========
    @transaction.atomic  # NEW
    def create(self, request, pk):
        openid = self.request.auth.openid  # NEW

        # 加锁读取头表，保证并发安全
        dn = (DnListModel.objects
              .select_for_update()
              .filter(openid=openid, id=pk, is_delete=False)
              .first())  # NEW
        if not dn:  # NEW
            raise APIException({"detail": "DN not found"})  # NEW

        # 允许从草稿(1)或已拣货(4)进入拣货完成(4)；不再依赖状态3
        if dn.dn_status not in (DnListModel.STATUS_DRAFT, DnListModel.STATUS_PICKED):  # NEW
            raise APIException({"detail": "This DN status cannot be picked"})  # NEW

        data = self.request.data or {}  # NEW
        dn_code = str(data.get('dn_code', '')).strip()  # NEW
        if dn_code != dn.dn_code:  # NEW
            raise APIException({"detail": "dn_code mismatch"})  # NEW

        items = data.get('goodsData', []) or []  # NEW
        if not isinstance(items, list) or not items:  # NEW
            raise APIException({"detail": "goodsData must be a non-empty list"})  # NEW

        # 锁定所有相关明细
        detail_map = {  # NEW
            d.goods_code: d for d in DnDetailModel.objects.select_for_update().filter(
                openid=openid, dn_code=dn_code, is_delete=False
            )
        }

        # 简化：只校验非负并累加 picked_qty；如需要，你可在此处补充库存联动
        for it in items:  # NEW
            gcode = str(it.get('goods_code', '')).strip()
            try:
                picked = int(it.get('pick_qty', 0))
            except Exception:
                raise APIException({"detail": f"Invalid pick_qty for {gcode}"})
            if picked < 0:
                raise APIException({"detail": "pick_qty must be >= 0"})

            d = detail_map.get(gcode)
            if not d:
                raise APIException({"detail": f"Detail not found for {gcode}"})

            # —— 若需要与库存联动：在这里做 onhand ↓ / picked_stock ↑ ——（此处省略）  # NEW
            d.picked_qty = (d.picked_qty or 0) + picked  # NEW
            d.dn_status = DnListModel.STATUS_PICKED       # NEW
            if d.pick_qty and d.pick_qty > 0:            # NEW：把旧的计划拣货清 0（可选）
                d.pick_qty = 0
            d.save(update_fields=['picked_qty', 'dn_status', 'pick_qty'])  # NEW

        # 头表置为 4（已拣货）
        dn.dn_status = DnListModel.STATUS_PICKED  # NEW
        dn.save(update_fields=['dn_status'])      # NEW

        return Response({"detail": "success"}, status=200)  # NEW

    # ========= 原 update（同样依赖状态3/拣货单/库存联动） =========
    # def update(self, request, *args, **kwargs):
    #     delete_data = stockbin.objects.filter(openid=self.request.auth.openid,
    #                                           goods_qty=0,
    #                                           pick_qty=0,
    #                                           picked_qty=0)
    #     if delete_data.exists():
    #         for i in delete_data:
    #             i.delete()
    #     data = self.request.data
    #     qs = self.get_queryset().filter(dn_code=data['dn_code']).first()
    #     if qs.dn_status != 3:
    #         raise APIException({"detail": "This dn Status Not Pre Pick"})
    #     else:
    #         ...（大量 PickingList/stockbin/stocklist 相关逻辑）
    #         return Response({"Detail": "success"}, status=200)

    # NEW：PUT 与 POST 复用同一拣货完成逻辑（允许重复追加拣货）
    update = create  # NEW


class DnDispatchViewSet(viewsets.ModelViewSet):
    """
        create:
            Confirm Dispatch
    """
    # 原写法
    # pagination_class = MyPageNumberPagination
    # NEW：发运动作不需要分页
    pagination_class = None  # NEW

    filter_backends = [DjangoFilterBackend, OrderingFilter, ]
    ordering_fields = ['id', "create_time", "update_time", ]

    # 原写法（django-filter 旧属性）
    # filter_class = DnListFilter
    # NEW：统一为 django-filter 2.x 的属性
    filterset_class = DnListFilter  # NEW

    def get_project(self):
        try:
            id = self.kwargs.get('pk')
            return id
        except:
            return None

    def get_queryset(self):
        id = self.get_project()
        if self.request.user:
            return DnListModel.objects.filter(openid=self.request.auth.openid, id=id, is_delete=False)
        else:
            return DnListModel.objects.none()

    def get_serializer_class(self):
        if self.action in ['create']:
            return serializers.DNListUpdateSerializer
        else:
            return self.http_method_not_allowed(request=self.request)

    # ========= 原 create：对 stocklist / stockbin / PickingListModel 做了多处扣减与删除 =========
    # def create(self, request, pk):
    #     qs = self.get_object()
    #     if qs.dn_status != 4:
    #         raise APIException({"detail": "This DN Status Not Picked"})
    #     else:
    #         qs.dn_status = 5
    #         data = self.request.data
    #         staff_name = staff.objects.filter(openid=self.request.auth.openid,
    #                                           id=self.request.META.get('HTTP_OPERATOR')).first().staff_name
    #         if driverlist.objects.filter(openid=self.request.auth.openid,
    #                                      driver_name=str(data['driver']),
    #                                      is_delete=False).exists():
    #             driver = driverlist.objects.filter(openid=self.request.auth.openid,
    #                                                driver_name=str(data['driver']),
    #                                                is_delete=False).first()
    #             dn_detail = DnDetailModel.objects.filter(openid=self.request.auth.openid,
    #                                                      dn_code=str(data['dn_code']),
    #                                                      dn_status=4, customer=qs.customer,)
    #             pick_qty_change = PickingListModel.objects.filter(openid=self.request.auth.openid,
    #                                                               dn_code=str(data['dn_code']))
    #             for i in range(len(dn_detail)):
    #                 goods_qty_change = stocklist.objects.filter(...).first()
    #                 goods_qty_change.goods_qty = goods_qty_change.goods_qty - dn_detail[i].picked_qty
    #                 goods_qty_change.picked_stock = goods_qty_change.picked_stock - dn_detail[i].picked_qty
    #                 dn_detail[i].dn_status = 5
    #                 dn_detail[i].intransit_qty = dn_detail[i].picked_qty
    #                 dn_detail[i].save()
    #                 goods_qty_change.save()
    #                 if goods_qty_change.goods_qty == 0 and goods_qty_change.back_order_stock == 0:
    #                     goods_qty_change.delete()
    #             for j in range(len(pick_qty_change)):
    #                 bin_qty_change = stockbin.objects.filter(...).first()
    #                 bin_qty_change.picked_qty = bin_qty_change.picked_qty - pick_qty_change[j].picked_qty
    #                 bin_qty_change.save()
    #                 bin_stock_check = stockbin.objects.filter(...).first()
    #                 if bin_stock_check.goods_qty == 0 and bin_stock_check.pick_qty == 0 and bin_stock_check.picked_qty == 0:
    #                     bin_stock_check.delete()
    #                     if stockbin.objects.filter(...).exists() is False:
    #                         binset.objects.filter(...).update(empty_label=True)
    #             driverdispatch.objects.create(...)
    #             qs.save()
    #             return Response({"detail": "success"}, status=200)
    #         else:
    #             raise APIException({"detail": "Driver Does Not Exists"})

    # ========= NEW create：仅做 picked_qty→intransit_qty，头表 4→5；保留司机校验与派单记录 =========
    @transaction.atomic  # NEW
    def create(self, request, pk):
        openid = self.request.auth.openid  # NEW

        # 加锁读取头表
        dn = (DnListModel.objects
              .select_for_update()
              .filter(openid=openid, id=pk, is_delete=False)
              .first())  # NEW
        if not dn:  # NEW
            raise APIException({"detail": "DN not found"})  # NEW
        if dn.dn_status != DnListModel.STATUS_PICKED:  # 只允许 4 -> 5
            raise APIException({"detail": "This DN Status is not Picked"})  # NEW

        data = self.request.data or {}  # NEW
        # 防呆：dn_code 必须匹配
        if str(data.get('dn_code', '')).strip() != dn.dn_code:  # NEW
            raise APIException({"detail": "dn_code mismatch"})  # NEW

        # （可选）司机校验，保留你的业务逻辑
        staff_name = staff.objects.filter(
            openid=openid, id=self.request.META.get('HTTP_OPERATOR')
        ).first().staff_name  # NEW

        if not driverlist.objects.filter(
            openid=openid, driver_name=str(data.get('driver')), is_delete=False
        ).exists():  # NEW
            raise APIException({"detail": "Driver Does Not Exists"})  # NEW

        driver = driverlist.objects.filter(
            openid=openid, driver_name=str(data.get('driver')), is_delete=False
        ).first()  # NEW

        # 锁定明细：从 4（已拣货）转为 5（在途）
        details = list(DnDetailModel.objects.select_for_update().filter(
            openid=openid, dn_code=dn.dn_code, dn_status=DnListModel.STATUS_PICKED, is_delete=False
        ))  # NEW

        for d in details:  # NEW
            qty = int(d.picked_qty or 0)
            if qty <= 0:
                continue
            # ✅ 仅做 picked → intransit；不再扣 onhand/不再操作 stockbin/PickingList
            d.intransit_qty = (d.intransit_qty or 0) + qty  # NEW
            d.dn_status = DnListModel.STATUS_INTRANSIT          # NEW
            d.save(update_fields=['intransit_qty', 'dn_status'])  # NEW

        # 头表置 5
        dn.dn_status = DnListModel.STATUS_INTRANSIT  # NEW
        dn.save(update_fields=['dn_status'])  # NEW

        # 保留你的派单记录
        driverdispatch.objects.create(  # NEW
            openid=openid,
            driver_name=driver.driver_name,
            dn_code=dn.dn_code,
            contact=driver.contact,
            creater=str(staff_name)
        )

        return Response({"detail": "success"}, status=200)  # NEW


class DnPODViewSet(viewsets.ModelViewSet):
    """
        create:
            Confirm Dispatch
    """
    # 原写法
    # pagination_class = MyPageNumberPagination
    # NEW：签收动作不需要分页
    pagination_class = None  # NEW

    filter_backends = [DjangoFilterBackend, OrderingFilter, ]
    ordering_fields = ['id', "create_time", "update_time", ]

    # 原写法（django-filter 旧属性）
    # filter_class = DnListFilter
    # NEW：统一为 django-filter 2.x 的属性
    filterset_class = DnListFilter  # NEW

    def get_project(self):
        try:
            id = self.kwargs.get('pk')
            return id
        except:
            return None

    def get_queryset(self):
        id = self.get_project()
        if self.request.user:
            return DnListModel.objects.filter(openid=self.request.auth.openid, id=id, is_delete=False)
        else:
            return DnListModel.objects.none()

    def get_serializer_class(self):
        if self.action in ['create']:
            return serializers.DNListUpdateSerializer
        else:
            return self.http_method_not_allowed(request=self.request)

    # ========= 原 create：基本逻辑正确，但缺少并发锁与dn_code核对；头表直接置6 =========
    # def create(self, request, pk):
    #     qs = self.get_object()
    #     if qs.dn_status != 5:
    #         raise APIException({"detail": "This DN Status Not Intran-Sit"})
    #     else:
    #         qs.dn_status = 6
    #         data = self.request.data
    #         for i in range(len(data['goodsData'])):
    #             delivery_damage_qty = data['goodsData'][i].get('delivery_damage_qty')
    #             delivery_actual_qty = data['goodsData'][i].get('intransit_qty')
    #             ...
    #         dn_detail = DnDetailModel.objects.filter(openid=self.request.auth.openid,
    #                                                  dn_code=str(data['dn_code']),
    #                                                  dn_status=5, customer=qs.customer,)
    #         for j in range(len(data['goodsData'])):
    #             ...
    #             goods_detail.save()
    #         qs.save()
    #         return Response({"detail": "success"}, status=200)

    # ========= NEW create：加事务 + 行锁；校验 dn_code；只操作在途明细；剩余在途则不置头表6 =========
    @transaction.atomic  # NEW
    def create(self, request, pk):
        openid = self.request.auth.openid  # NEW

        # 加锁读取头表
        dn = (DnListModel.objects
              .select_for_update()
              .filter(openid=openid, id=pk, is_delete=False)
              .first())  # NEW
        if not dn:  # NEW
            raise APIException({"detail": "DN not found"})  # NEW
        if dn.dn_status != DnListModel.STATUS_INTRANSIT:  # NEW
            raise APIException({"detail": "This DN Status Not In-Transit"})  # NEW

        data = self.request.data or {}  # NEW
        # 防呆：dn_code 必须匹配
        if str(data.get('dn_code', '')).strip() != dn.dn_code:  # NEW
            raise APIException({"detail": "dn_code mismatch"})  # NEW

        # 先做基础校验（非负）
        for item in data.get('goodsData', []):  # NEW
            delivery_damage_qty = item.get('delivery_damage_qty', 0)
            delivery_actual_qty = item.get('intransit_qty', 0)
            if delivery_actual_qty < 0:
                raise APIException({"detail": "Delivery Actual QTY Must >= 0"})  # NEW
            if delivery_damage_qty < 0:
                raise APIException({"detail": "Delivery Damage QTY Must >= 0"})  # NEW

        # 只锁定“在途”的明细
        detail_map = {  # NEW
            d.goods_code: d for d in DnDetailModel.objects.select_for_update().filter(
                openid=openid,
                dn_code=dn.dn_code,
                dn_status=DnListModel.STATUS_INTRANSIT,
                customer=dn.customer,
                is_delete=False
            )
        }

        # 根据上报写入到货数据，并清零 intransit
        for item in data.get('goodsData', []):  # NEW
            goods_code = str(item.get('goods_code', '')).strip()
            delivery_damage_qty = int(item.get('delivery_damage_qty', 0))
            delivery_actual_qty = int(item.get('intransit_qty', 0))

            d = detail_map.get(goods_code)
            if not d:
                # 不在“在途”的行忽略/报错二选一；这里选择报错更安全
                raise APIException({"detail": f"Detail not found or not in-transit for {goods_code}"})  # NEW

            intransit = int(d.intransit_qty or 0)  # NEW
            d.delivery_actual_qty = delivery_actual_qty  # NEW
            if delivery_actual_qty > intransit:  # NEW
                d.delivery_more_qty = delivery_actual_qty - intransit
                d.delivery_shortage_qty = 0
            elif delivery_actual_qty < intransit:  # NEW
                d.delivery_shortage_qty = intransit - delivery_actual_qty
                d.delivery_more_qty = 0
            else:  # NEW
                d.delivery_more_qty = 0
                d.delivery_shortage_qty = 0
            d.delivery_damage_qty = delivery_damage_qty  # NEW
            d.intransit_qty = 0  # NEW
            d.dn_status = DnListModel.STATUS_DELIVERED  # NEW
            d.save(update_fields=[
                'delivery_actual_qty', 'delivery_more_qty', 'delivery_shortage_qty',
                'delivery_damage_qty', 'intransit_qty', 'dn_status'
            ])  # NEW

        # 若无剩余“在途”明细，则头表置 6（已签收）；否则保留 5（在途）
        still_intransit = DnDetailModel.objects.filter(
            openid=openid, dn_code=dn.dn_code,
            dn_status=DnListModel.STATUS_INTRANSIT, is_delete=False
        ).exists()  # NEW
        if not still_intransit:  # NEW
            dn.dn_status = DnListModel.STATUS_DELIVERED  # NEW
            dn.save(update_fields=['dn_status'])  # NEW

        return Response({"detail": "success"}, status=200)  # NEW


class FileListDownloadView(viewsets.ModelViewSet):
    # 原写法
    # renderer_classes = (FileListRenderCN, ) + tuple(api_settings.DEFAULT_RENDERER_CLASSES)
    # NEW：渲染器我们在 list() 内部手动选择，不强制类级 renderer
    renderer_classes = tuple(api_settings.DEFAULT_RENDERER_CLASSES)  # NEW

    # 原写法（缺鉴权）
    # filter_backends = [DjangoFilterBackend, OrderingFilter, ]
    permission_classes = [IsAuthenticated]  # NEW
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ['id', "create_time", "update_time", ]

    # 原写法（django-filter 旧属性）
    # filter_class = DnListFilter
    # NEW
    filterset_class = DnListFilter  # NEW

    # 原写法：未显式声明分页
    # NEW：导出一般不分页
    pagination_class = None  # NEW

    def get_project(self):
        try:
            id = self.kwargs.get('pk')
            return id
        except:
            return None

    def get_queryset(self):
        id = self.get_project()
        if self.request.user:
            # === 原实现：逐条循环删除（效率低） ===
            # empty_qs = DnListModel.objects.filter(
            #     Q(openid=self.request.auth.openid, dn_status=1, is_delete=False) & Q(customer=''))
            # cur_date = timezone.now()
            # date_check = relativedelta(day=1)
            # if len(empty_qs) > 0:
            #     for i in range(len(empty_qs)):
            #         if empty_qs[i].create_time <= cur_date - date_check:
            #             empty_qs[i].delete()

            # === NEW：一次性批量删除“空客户草稿单”且创建时间 <= 当月第1天 ===
            cur_date = timezone.now()  # NEW
            month_cut = cur_date - relativedelta(day=1)  # NEW
            (DnListModel.objects
                .filter(
                    openid=self.request.auth.openid,
                    dn_status=1,
                    is_delete=False,
                    customer=''
                )
                .filter(create_time__lte=month_cut)
                .delete())  # NEW

            if id is None:
                return DnListModel.objects.filter(
                    Q(openid=self.request.auth.openid, is_delete=False) & ~Q(customer=''))
            else:
                return DnListModel.objects.filter(
                    Q(openid=self.request.auth.openid, id=id, is_delete=False) & ~Q(customer=''))
        else:
            return DnListModel.objects.none()

    def get_serializer_class(self):
        if self.action in ['list']:
            # 原写法
            # return serializers.FileListRenderSerializer
            # NEW：显式从 serializers 命名空间取
            return serializers.FileListRenderSerializer  # NEW
        else:
            return self.http_method_not_allowed(request=self.request)

    # 原 get_lang（我们会在 list() 里直接选择 renderer）
    # def get_lang(self, data):
    #     lang = self.request.META.get('HTTP_LANGUAGE')
    #     if lang:
    #         if lang == 'zh-hans':
    #             return FileListRenderCN().render(data)
    #         else:
    #             return FileListRenderEN().render(data)
    #     else:
    #         return FileListRenderEN().render(data)

    def list(self, request, *args, **kwargs):
        # from datetime import datetime
        # dt = datetime.now()
        # data = (
        #     FileListRenderSerializer(instance).data
        #     for instance in self.filter_queryset(self.get_queryset())
        # )
        # renderer = self.get_lang(data)
        # response = StreamingHttpResponse(
        #     renderer,
        #     content_type="text/csv"
        # )
        # response['Content-Disposition'] = "attachment; filename='dnlist_{}.csv'".format(str(dt.strftime('%Y%m%d%H%M%S%f')))
        # return response

        # === NEW：按 files.py 的 Renderer 流式导出，含 other_fees 字段 ===
        from django.http import StreamingHttpResponse  # NEW
        from django.utils import timezone  # NEW
        from .files import FileListRenderCN, FileListRenderEN  # NEW

        rows = (
            serializers.FileListRenderSerializer(obj).data
            for obj in self.filter_queryset(self.get_queryset())
        )  # NEW

        lang = (request.META.get('HTTP_LANGUAGE') or '').lower()  # NEW
        renderer = FileListRenderCN() if lang == 'zh-hans' else FileListRenderEN()  # NEW

        ts = timezone.now().strftime('%Y%m%d%H%M%S%f')  # NEW
        resp = StreamingHttpResponse(
            renderer.render(rows),
            content_type="text/csv; charset=utf-8"
        )  # NEW
        resp['Content-Disposition'] = f"attachment; filename*=UTF-8''dnlist_{ts}.csv"  # NEW
        return resp  # NEW


class FileDetailDownloadView(viewsets.ModelViewSet):
    # 原写法
    # renderer_classes = (FileDetailRenderCN, ) + tuple(api_settings.DEFAULT_RENDERER_CLASSES)
    # NEW：与上面一致，类级不强制 CSV renderer
    renderer_classes = tuple(api_settings.DEFAULT_RENDERER_CLASSES)  # NEW

    # 原写法（缺鉴权）
    # filter_backends = [DjangoFilterBackend, OrderingFilter, ]
    permission_classes = [IsAuthenticated]  # NEW
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ['id', "create_time", "update_time", ]

    # 原写法（django-filter 旧属性）
    # filter_class = DnDetailFilter
    # NEW
    filterset_class = DnDetailFilter  # NEW

    # 原写法：未显式声明分页
    # NEW：导出一般不分页
    pagination_class = None  # NEW

    def get_project(self):
        try:
            id = self.kwargs.get('pk')
            return id
        except:
            return None

    def get_queryset(self):
        id = self.get_project()
        if self.request.user:
            if id is None:
                return DnDetailModel.objects.filter(openid=self.request.auth.openid, is_delete=False)
            else:
                return DnDetailModel.objects.filter(openid=self.request.auth.openid, id=id, is_delete=False)
        else:
            return DnDetailModel.objects.none()

    def get_serializer_class(self):
        if self.action in ['list']:
            # 原写法
            # return serializers.FileDetailRenderSerializer
            # NEW：显式从 serializers 命名空间取
            return serializers.FileDetailRenderSerializer  # NEW
        else:
            return self.http_method_not_allowed(request=self.request)

    # 原 get_lang（不再需要）
    # def get_lang(self, data):
    #     lang = self.request.META.get('HTTP_LANGUAGE')
    #     if lang:
    #         if lang == 'zh-hans':
    #             return FileDetailRenderCN().render(data)
    #         else:
    #             return FileDetailRenderEN().render(data)
    #     else:
    #         return FileDetailRenderEN().render(data)

    def list(self, request, *args, **kwargs):
        # from datetime import datetime
        # dt = datetime.now()
        # data = (
        #     FileDetailRenderSerializer(instance).data
        #     for instance in self.filter_queryset(self.get_queryset())
        # )
        # renderer = self.get_lang(data)
        # response = StreamingHttpResponse(
        #     renderer,
        #     content_type="text/csv"
        # )
        # response['Content-Disposition'] = "attachment; filename='dndetail_{}.csv'".format(str(dt.strftime('%Y%m%d%H%M%S%f')))
        # return response

        # === NEW：与 files.py 的 Renderer 配合；明细不包含重量/体积/欠货标识 ===
        from django.http import StreamingHttpResponse  # NEW
        from django.utils import timezone  # NEW
        from .files import FileDetailRenderCN, FileDetailRenderEN  # NEW

        rows = (
            serializers.FileDetailRenderSerializer(obj).data
            for obj in self.filter_queryset(self.get_queryset())
        )  # NEW

        lang = (request.META.get('HTTP_LANGUAGE') or '').lower()  # NEW
        renderer = FileDetailRenderCN() if lang == 'zh-hans' else FileDetailRenderEN()  # NEW

        ts = timezone.now().strftime('%Y%m%d%H%M%S%f')  # NEW
        resp = StreamingHttpResponse(
            renderer.render(rows),
            content_type="text/csv; charset=utf-8"
        )  # NEW
        resp['Content-Disposition'] = f"attachment; filename*=UTF-8''dndetail_{ts}.csv"  # NEW
        return resp  # NEW
