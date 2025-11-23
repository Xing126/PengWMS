from rest_framework import viewsets
from .models import AsnListModel, AsnDetailModel
from . import serializers
from .page import MyPageNumberPaginationASNList
from utils.page import MyPageNumberPagination
from utils.datasolve import sumOfList, transportation_calculate
from utils.fbmsg import FBMsg
from utils.md5 import Md5
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from .filter import AsnListFilter, AsnDetailFilter
from rest_framework.exceptions import APIException
from customer.models import ListModel as customer
from warehouse.models import ListModel as warehouse
from goods.models import ListModel as goods
from payment.models import TransportationFeeListModel as transportation
from stock.models import StockListModel as stocklist
from stock.models import StockBinModel as stockbin
from binset.models import ListModel as binset
from scanner.models import ListModel as scanner
from cyclecount.models import QTYRecorder as qtychangerecorder
from cyclecount.models import CyclecountModeDayModel as cyclecount
from django.db.models import Q
from django.db.models import Sum
from .serializers import FileListRenderSerializer, FileDetailRenderSerializer
from django.http import StreamingHttpResponse
from django.utils import timezone
from .files import FileListRenderCN, FileListRenderEN, FileDetailRenderCN, FileDetailRenderEN
from rest_framework.settings import api_settings
from dateutil.relativedelta import relativedelta
from staff.models import ListModel as staff
from django.db import transaction
from decimal import Decimal, InvalidOperation
from rest_framework import status
from django.utils.dateparse import parse_datetime


class AsnListViewSet(viewsets.ModelViewSet):
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
    pagination_class = MyPageNumberPaginationASNList
    filter_backends = [DjangoFilterBackend, OrderingFilter, ]
    ordering_fields = ['id', "create_time", "update_time", ]
    filter_class = AsnListFilter

    def get_project(self):
        try:
            id = self.kwargs.get('pk')
            return id
        except:
            return None

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()  # 由 pk=8 定位
        data = request.data.copy()
        # 用实例上的 asn_code 回填，避免“必填”报错
        data.setdefault("asn_code", getattr(instance, "asn_code", None))

        serializer = self.get_serializer(instance, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def get_queryset(self):
        id = self.get_project()
        if self.request.user:
            empty_qs = AsnListModel.objects.filter(Q(openid=self.request.auth.openid, asn_status=1, is_delete=False) & Q(customer=''))
            cur_date = timezone.now()
            date_check = relativedelta(day=1)
            if len(empty_qs) > 0:
                for i in range(len(empty_qs)):
                    if empty_qs[i].create_time <= cur_date - date_check:
                        empty_qs[i].delete()
            if id is None:
                return AsnListModel.objects.filter(Q(openid=self.request.auth.openid, is_delete=False) & ~Q(customer=''))
            else:
                return AsnListModel.objects.filter(Q(openid=self.request.auth.openid, id=id, is_delete=False) & ~Q(customer=''))
        else:
            return AsnListModel.objects.none()

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve', 'destroy']:
            return serializers.ASNListGetSerializer
        elif self.action in ['create']:
            return serializers.ASNListPostSerializer
        elif self.action in ['update']:
            return serializers.ASNListUpdateSerializer
        elif self.action in ['partial_update']:
            return serializers.ASNListPartialUpdateSerializer
        else:
            return self.http_method_not_allowed(request=self.request)

    def notice_lang(self):
        return FBMsg(self.request.META.get('HTTP_LANGUAGE'))

    def create(self, request, *args, **kwargs):
        data = self.request.data
        data['openid'] = self.request.auth.openid
        total_pallet_qty, wrapped_pallet_qty = self._parse_and_validate_pallet_fields(data)
        data['total_pallet_qty'] = total_pallet_qty
        data['wrapped_pallet_qty'] = wrapped_pallet_qty
        if 'recive_time' not in data or not data['recive_time']:
            data['recive_time'] = timezone.now()
        if total_pallet_qty < 0 or wrapped_pallet_qty < 0:
            raise APIException({"detail": "Total pallet quantity and wrapped pallet quantity must be non-negative."})
        custom_asn = self.request.GET.get('custom_asn', '')
        if custom_asn:
            data['asn_code'] = custom_asn
        else:
            qs_set = AsnListModel.objects.filter(openid=self.request.auth.openid)
            order_day =str(timezone.now().strftime('%Y%m%d'))
            if len(qs_set) > 0:
                asn_last_code = qs_set.order_by('-id').first().asn_code
                if str(asn_last_code[3:11]) == order_day:
                    order_create_no = str(int(asn_last_code[11:]) + 1)
                    data['asn_code'] = 'ASN' + order_day + order_create_no
                else:
                    data['asn_code'] = 'ASN' + order_day + '1'
            else:
                data['asn_code'] = 'ASN' + order_day + '1'
        data['bar_code'] = Md5.md5(data['asn_code'])
        data['total_pallet_qty'] = total_pallet_qty
        data['wrapped_pallet_qty'] = wrapped_pallet_qty
        # 包含 customer_other_fees 字段
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        scanner.objects.create(openid=self.request.auth.openid, mode="ASN", code=data['asn_code'], bar_code=data['bar_code'])
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=200, headers=headers)

    def destroy(self, request, pk):
        qs = self.get_object()
        if qs.openid != self.request.auth.openid:
            raise APIException({"detail": "Cannot delete data which not yours"})
        else:
            if qs.asn_status == 1:
                qs.is_delete = True
                asn_detail_list = AsnDetailModel.objects.filter(openid=self.request.auth.openid, asn_code=qs.asn_code,
                                              asn_status=1, is_delete=False)
                for i in range(len(asn_detail_list)):
                    goods_qty_change = stocklist.objects.filter(openid=self.request.auth.openid,
                                                                goods_code=str(asn_detail_list[i].goods_code)).first()
                    goods_qty_change.goods_qty = goods_qty_change.goods_qty - int(asn_detail_list[i].goods_qty)
                    goods_qty_change.asn_stock = goods_qty_change.asn_stock - int(asn_detail_list[i].goods_qty)
                    goods_qty_change.save()
                asn_detail_list.update(is_delete=True)
                qs.save()
                serializer = self.get_serializer(qs, many=False)
                headers = self.get_success_headers(serializer.data)
                return Response(serializer.data, status=200, headers=headers)
            else:
                raise APIException({"detail": "This ASN Status Is Not '1'"})

    def update(self, request, *args, **kwargs):
        data = self.request.data
        asn_code = data.get('asn_code')
        if not asn_code:
            raise APIException({"detail": "asn_code is required."})

        qs = AsnListModel.objects.filter(
            openid=self.request.auth.openid, asn_code=asn_code, is_delete=False
        )
        if not qs.exists():
            raise APIException({"detail": "ASN Code does not exist."})

        total_pallet_qty, wrapped_pallet_qty = self._parse_and_validate_pallet_fields(data)

        instance = qs.first()
        instance.total_pallet_qty = total_pallet_qty
        instance.wrapped_pallet_qty = wrapped_pallet_qty
        if 'recive_time' in data:
            instance.recive_time = data['recive_time']
        instance.save(update_fields=["total_pallet_qty", "wrapped_pallet_qty"])

        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=200)

    def _parse_and_validate_pallet_fields(self, data):
        """解析并严格校验 total_pallet_qty / wrapped_pallet_qty，返回 (total, wrapped) 两个 int。
        约束：整数、非负、wrapped ≤ total
        """

        def to_int(name):
            raw = data.get(name, 0)
            try:
                # 允许前端传字符串/数字，均转为 int
                val = int(raw)
            except (ValueError, TypeError):
                raise APIException({"detail": f"{name} must be an integer."})
            if val < 0:
                raise APIException({"detail": f"{name} must be non-negative."})
            return val

        total = to_int("total_pallet_qty")
        wrapped = to_int("wrapped_pallet_qty")

        if wrapped > total:
            raise APIException({"detail": "wrapped_pallet_qty cannot be greater than total_pallet_qty."})

        return total, wrapped


class AsnDetailViewSet(viewsets.ModelViewSet):
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
    filter_class = AsnDetailFilter


    def get_project(self):
        try:
            id = self.kwargs.get('pk')
            return id
        except:
            return None

    def _sum_customer_other_fees(self, fees):
        """
        参数 fees：期望为 dict(JSON)。对其 value 求和，支持 int/float/decimal/数字字符串。
        返回：Decimal 总和。
        """
        if fees in (None, ''):
            return Decimal('0')
        if not isinstance(fees, dict):
            raise APIException({"detail": "customer_other_fees must be a JSON object."})

        total = Decimal('0')
        for k, v in fees.items():
            if v in (None, ''):
                continue
            try:
                # 统一转 Decimal，避免二进制浮点误差
                total += Decimal(str(v))
            except (InvalidOperation, ValueError, TypeError):
                raise APIException({"detail": f"customer_other_fees['{k}'] must be a number."})
        return total

    def get_queryset(self):
        id = self.get_project()
        if self.request.user:
            if id is None:
                return AsnDetailModel.objects.filter(openid=self.request.auth.openid, is_delete=False)
            else:
                return AsnDetailModel.objects.filter(openid=self.request.auth.openid, id=id, is_delete=False)
        else:
            return AsnDetailModel.objects.none()

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return serializers.ASNDetailGetSerializer
        elif self.action in ['create']:
            return serializers.ASNDetailPostSerializer
        elif self.action in ['update']:
            return serializers.ASNDetailUpdateSerializer
        else:
            return self.http_method_not_allowed(request=self.request)

    def create(self, request, *args, **kwargs):
        data = self.request.data
        customer_other_fees = data.get('customer_other_fees', {})
        fees_sum = self._sum_customer_other_fees(customer_other_fees)
        if AsnListModel.objects.filter(openid=self.request.auth.openid, asn_code=str(data['asn_code']), is_delete=False).exists():
            if customer.objects.filter(openid=self.request.auth.openid, customer_name=str(data['customer']), is_delete=False).exists():
                staff_name = staff.objects.filter(openid=self.request.auth.openid, id=self.request.META.get('HTTP_OPERATOR')).first().staff_name
                for i in range(len(data['goods_code'])):
                    check_data = {
                        'openid': self.request.auth.openid,
                        'asn_code': str(data['asn_code']),
                        'customer': str(data['customer']),
                        'goods_code': str(data['goods_code'][i]),
                        'goods_qty': int(data['goods_qty'][i]),
                        'creator': str(staff_name),
                        'customer_other_fees': customer_other_fees,

                    }
                    fees_sum = self._sum_customer_other_fees(customer_other_fees)  # Decimal
                    serializer = self.get_serializer(data=check_data)
                    serializer.is_valid(raise_exception=True)
                post_data_list = []
#去掉重量体积初始化
                #weight_list = []
                #volume_list = []
                cost_list = []
                for j in range(len(data['goods_code'])):
                    goods_detail = goods.objects.filter(openid=self.request.auth.openid,
                                                        goods_code=str(data['goods_code'][j]),
                                                        is_delete=False).first()
                    #goods_weight = round(goods_detail.goods_weight * int(data['goods_qty'][j]) / 1000, 4)
                    #goods_volume = round(goods_detail.unit_volume * int(data['goods_qty'][j]), 4)
                    goods_cost = round(goods_detail.goods_cost * int(data['goods_qty'][j]), 2)
                    if stocklist.objects.filter(openid=self.request.auth.openid, goods_code=str(data['goods_code'][j])).exists():
                        goods_qty_change = stocklist.objects.filter(openid=self.request.auth.openid,
                                                 goods_code=str(data['goods_code'][j])).first()
                        goods_qty_change.goods_qty = goods_qty_change.goods_qty + int(data['goods_qty'][j])
                        goods_qty_change.asn_stock = goods_qty_change.asn_stock + int(data['goods_qty'][j])
                        goods_qty_change.save()
                    else:
                        stocklist.objects.create(openid=self.request.auth.openid,
                                                 goods_code=str(data['goods_code'][j]),
                                                 goods_desc=goods_detail.goods_desc,
                                                 goods_qty=int(data['goods_qty'][j]),
                                                 asn_stock=int(data['goods_qty'][j]))
                    post_data = AsnDetailModel(openid=self.request.auth.openid,
                                               asn_code=str(data['asn_code']),
                                               customer=str(data['customer']),
                                               goods_code=str(data['goods_code'][j]),
                                               goods_desc=str(goods_detail.goods_desc),
                                               goods_qty=int(data['goods_qty'][j]),
                                               #goods_weight=goods_weight,
                                               #goods_volume=goods_volume,
                                               goods_cost=goods_cost,
                                               creator=str(staff_name),
                                               customer_other_fees=customer_other_fees,

                                               )

                    post_data_list.append(post_data)
                    #weight_list.append(goods_weight)
                    #volume_list.append(goods_volume)
                    cost_list.append(goods_cost)
                #total_weight = sumOfList(weight_list, len(weight_list))
                #total_volume = sumOfList(volume_list, len(volume_list))
                total_cost = Decimal(str(sumOfList(cost_list, len(cost_list)))) + fees_sum

                customer_city = customer.objects.filter(openid=self.request.auth.openid,
                                                        customer_name=str(data['customer']),
                                                        is_delete=False).first().customer_city
                warehouse_city = warehouse.objects.filter(openid=self.request.auth.openid).first().warehouse_city
                transportation_fee = transportation.objects.filter(
                    Q(openid=self.request.auth.openid, send_city__icontains=customer_city, receiver_city__icontains=warehouse_city,
                      is_delete=False) | Q(openid='init_data', send_city__icontains=customer_city, receiver_city__icontains=warehouse_city,
                                           is_delete=False))
                transportation_res = {
                    "detail": []
                }
                if len(transportation_fee) >= 1:
                    transportation_list = []
                    for k in range(len(transportation_fee)):
                        transportation_cost = transportation_calculate(#total_weight,
                                                                       #total_volume,
                                                                       transportation_fee[k].weight_fee,
                                                                       transportation_fee[k].volume_fee,
                                                                       transportation_fee[k].min_payment)
                        transportation_detail = {
                            "transportation_customer": transportation_fee[k].transportation_customer,
                            "transportation_cost": transportation_cost
                        }
                        transportation_list.append(transportation_detail)
                    transportation_res['detail'] = transportation_list
                AsnDetailModel.objects.bulk_create(post_data_list, batch_size=100)
                check_data = AsnDetailModel.objects.filter(openid=self.request.auth.openid, asn_code=data['asn_code'], is_delete=False)
                for k in range(len(check_data)):
                    res_check_data = check_data.filter(goods_code=check_data[k].goods_code)
                    if res_check_data.count() > 1:
                        combine_qty = []
                        #conbine_weight = []
                        #conbine_volume = []
                        conbine_cost = []
                        for z in range(len(res_check_data)):
                            combine_qty.append(res_check_data[z].goods_qty)
                            #conbine_weight.append(res_check_data[z].goods_weight)
                            #conbine_volume.append(res_check_data[z].goods_volume)
                            conbine_cost.append(res_check_data[z].goods_cost)
                            res_check_data[z].delete()
                        AsnDetailModel.objects.create(openid=self.request.auth.openid,
                                                      asn_code=str(data['asn_code']),
                                                      customer=str(data['customer']),
                                                      goods_code=str(check_data[k].goods_code),
                                                      goods_desc=str(check_data[k].goods_desc),
                                                      goods_qty=sumOfList(combine_qty, len(combine_qty)),
                                                      #goods_weight=sumOfList(conbine_weight, len(conbine_weight)),
                                                      #goods_volume=sumOfList(conbine_volume, len(conbine_volume)),
                                                      goods_cost=sumOfList(conbine_cost, len(conbine_cost)),
                                                      creator=str(staff_name))
                AsnListModel.objects.filter(openid=self.request.auth.openid, asn_code=str(data['asn_code'])).update(
                    customer=str(data['customer']), #total_weight=total_weight, total_volume=total_volume,
                    total_cost=total_cost, transportation_fee=transportation_res,customer_other_fees=customer_other_fees)
                return Response({"detail": "success"}, status=200)
            else:
                raise APIException({"detail": "Customer does not exists"})
        else:
            raise APIException({"detail": "ASN Code does not exists"})

    def update(self, request, *args, **kwargs):
        data = self.request.data
        customer_other_fees = data.get('customer_other_fees', {})
        fees_sum = self._sum_customer_other_fees(customer_other_fees)

        if AsnListModel.objects.filter(openid=self.request.auth.openid, asn_code=str(data['asn_code']),
                                       asn_status=1, is_delete=False).exists():
            if customer.objects.filter(openid=self.request.auth.openid, customer_name=str(data['customer']),
                                       is_delete=False).exists():
                staff_name = staff.objects.filter(openid=self.request.auth.openid,
                                                  id=self.request.META.get('HTTP_OPERATOR')).first().staff_name
                for i in range(len(data['goods_code'])):
                    check_data = {
                        'openid': self.request.auth.openid,
                        'asn_code': str(data['asn_code']),
                        'customer': str(data['customer']),
                        'goods_code': str(data['goods_code'][i]),
                        'goods_qty': int(data['goods_qty'][i]),
                        'creator': str(staff_name),

                    }
                    serializer = self.get_serializer(data=check_data)
                    serializer.is_valid(raise_exception=True)
                asn_detail_list = AsnDetailModel.objects.filter(openid=self.request.auth.openid,
                                                                asn_code=str(data['asn_code']), is_delete=False)
                for v in range(len(asn_detail_list)):
                    goods_qty_change = stocklist.objects.filter(openid=self.request.auth.openid,
                                                                goods_code=str(asn_detail_list[v].goods_code)).first()
                    goods_qty_change.goods_qty = goods_qty_change.goods_qty - asn_detail_list[v].goods_qty
                    if goods_qty_change.goods_qty < 0:
                        goods_qty_change.goods_qty = 0
                    goods_qty_change.asn_stock = goods_qty_change.asn_stock - asn_detail_list[v].goods_qty
                    if goods_qty_change.asn_stock < 0:
                        goods_qty_change.asn_stock = 0
                    goods_qty_change.save()
                    asn_detail_list[v].is_delete = True
                    asn_detail_list[v].save()
                post_data_list = []
                #weight_list = []
                #volume_list = []
                for j in range(len(data['goods_code'])):
                    goods_detail = goods.objects.filter(openid=self.request.auth.openid,
                                                        goods_code=str(data['goods_code'][j]),
                                                        is_delete=False).first()
                    #goods_weight = round(goods_detail.goods_weight * int(data['goods_qty'][j]) / 1000, 4)
                    #goods_volume = round(goods_detail.unit_volume * int(data['goods_qty'][j]), 4)
                    goods_cost = round(goods_detail.goods_cost * int(data['goods_qty'][j]), 2)
                    if stocklist.objects.filter(openid=self.request.auth.openid, goods_code=str(data['goods_code'][j])).exists():
                        goods_qty_change = stocklist.objects.filter(openid=self.request.auth.openid,
                                                 goods_code=str(data['goods_code'][j])).first()
                        goods_qty_change.goods_qty = goods_qty_change.goods_qty + int(data['goods_qty'][j])
                        goods_qty_change.asn_stock = goods_qty_change.asn_stock + int(data['goods_qty'][j])
                        goods_qty_change.save()
                    else:
                        stocklist.objects.create(openid=self.request.auth.openid,
                                                 goods_code=str(data['goods_code'][j]),
                                                 goods_desc=goods_detail.goods_desc,
                                                 goods_qty=int(data['goods_qty'][j]),
                                                 asn_stock=int(data['goods_qty'][j]))
                    post_data = AsnDetailModel(openid=self.request.auth.openid,
                                               asn_code=str(data['asn_code']),
                                               customer=str(data['customer']),
                                               goods_code=str(data['goods_code'][j]),
                                               goods_desc=str(goods_detail.goods_desc),
                                               goods_qty=int(data['goods_qty'][j]),
                                               #goods_weight=goods_weight,
                                               #goods_volume=goods_volume,
                                               creator=str(staff_name),
                                               customer_other_fees=customer_other_fees,
                                               goods_cost=goods_cost,

                                               )

                    post_data_list.append(post_data)
                    #weight_list.append(goods_weight)
                    #volume_list.append(goods_volume)
                #total_weight = sumOfList(weight_list, len(weight_list))
                #total_volume = sumOfList(volume_list, len(volume_list))
                total_cost = Decimal(str(sum([item.goods_cost for item in post_data_list]))) + fees_sum
                customer_city = customer.objects.filter(openid=self.request.auth.openid,
                                                        customer_name=str(data['customer']),
                                                        is_delete=False).first().customer_city
                warehouse_city = warehouse.objects.filter(openid=self.request.auth.openid).first().warehouse_city
                transportation_fee = transportation.objects.filter(
                    Q(openid=self.request.auth.openid, send_city__icontains=customer_city,
                      receiver_city__icontains=warehouse_city,
                      is_delete=False) | Q(openid='init_data', send_city__icontains=customer_city,
                                           receiver_city__icontains=warehouse_city,
                                           is_delete=False))
                transportation_res = {
                    "detail": []
                }
                if len(transportation_fee) >= 1:
                    transportation_list = []
                    for k in range(len(transportation_fee)):
                        transportation_cost = transportation_calculate(#total_weight,
                                                                       #total_volume,
                                                                       transportation_fee[k].weight_fee,
                                                                       transportation_fee[k].volume_fee,
                                                                       transportation_fee[k].min_payment)
                        transportation_detail = {
                            "transportation_customer": transportation_fee[k].transportation_customer,
                            "transportation_cost": transportation_cost
                        }
                        transportation_list.append(transportation_detail)
                    transportation_res['detail'] = transportation_list
                AsnDetailModel.objects.bulk_create(post_data_list, batch_size=100)
                check_data = AsnDetailModel.objects.filter(openid=self.request.auth.openid, asn_code=data['asn_code'], is_delete=False)
                for k in range(len(check_data)):
                    res_check_data = check_data.filter(goods_code=check_data[k].goods_code)
                    if res_check_data.count() > 1:
                        combine_qty = []
                        #conbine_weight = []
                        #conbine_volume = []
                        conbine_cost = []
                        for z in range(len(res_check_data)):
                            combine_qty.append(res_check_data[z].goods_qty)
                            #conbine_weight.append(res_check_data[z].goods_weight)
                            #conbine_volume.append(res_check_data[z].goods_volume)
                            conbine_cost.append(res_check_data[z].goods_cost)
                            res_check_data[z].delete()
                        AsnDetailModel.objects.create(openid=self.request.auth.openid,
                                                      asn_code=str(data['asn_code']),
                                                      customer=str(data['customer']),
                                                      goods_code=str(check_data[k].goods_code),
                                                      goods_desc=str(check_data[k].goods_desc),
                                                      goods_qty=sumOfList(combine_qty, len(combine_qty)),
                                                      #goods_weight=sumOfList(conbine_weight, len(conbine_weight)),
                                                      #goods_volume=sumOfList(conbine_volume, len(conbine_volume)),
                                                      goods_cost=sumOfList(conbine_cost, len(conbine_cost)),
                                                      creator=str(staff_name))
                AsnListModel.objects.filter(openid=self.request.auth.openid, asn_code=str(data['asn_code'])).update(
                    customer=str(data['customer']),# total_weight=total_weight, total_volume=total_volume,
                    transportation_fee=transportation_res,customer_other_fees=customer_other_fees,total_cost=total_cost)
                return Response({"detail": "success"}, status=200)
            else:
                raise APIException({"detail": "Customer does not exists"})
        else:
            raise APIException({"detail": "This ASN Status Is Not 1"})

class AsnViewPrintViewSet(viewsets.ModelViewSet):
    """
        retrieve:
            Response a data list（get）
    """
    pagination_class = MyPageNumberPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter, ]
    ordering_fields = ['id', "create_time", "update_time", ]
    filter_class = AsnListFilter

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
                return AsnListModel.objects.filter(openid=self.request.auth.openid, is_delete=False)
            else:
                return AsnListModel.objects.filter(openid=self.request.auth.openid, id=id, is_delete=False)
        else:
            return AsnListModel.objects.none()

    def get_serializer_class(self):
        if self.action in ['retrieve']:
            return serializers.ASNDetailGetSerializer
        else:
            return self.http_method_not_allowed(request=self.request)

    def retrieve(self, request, pk):
        qs = self.get_object()
        if qs.openid != self.request.auth.openid:
            raise APIException({"detail": "Cannot update data which not yours"})
        else:
            context = {}
            asn_detail_list = AsnDetailModel.objects.filter(openid=self.request.auth.openid,
                                                            asn_code=qs.asn_code,
                                                            is_delete=False)
            asn_detail = serializers.ASNDetailGetSerializer(asn_detail_list, many=True)
            customer_detail = customer.objects.filter(openid=self.request.auth.openid,
                                                            customer_name=qs.customer).first()
            warehouse_detail = warehouse.objects.filter(openid=self.request.auth.openid,).first()
            context['asn_detail'] = asn_detail.data
            context['customer_detail'] = {
                "customer_name": customer_detail.customer_name,
                "customer_city": customer_detail.customer_city,
                "customer_address": customer_detail.customer_address,
                "customer_contact": customer_detail.customer_contact
            }
            context['warehouse_detail'] = {
                "warehouse_name": warehouse_detail.warehouse_name,
                "warehouse_city": warehouse_detail.warehouse_city,
                "warehouse_address": warehouse_detail.warehouse_address,
                "warehouse_contact": warehouse_detail.warehouse_contact
            }
        return Response(context, status=200)

class AsnPreLoadViewSet(viewsets.ModelViewSet):
    """
        retrieve:
            Response a data list（get）
    """
    pagination_class = MyPageNumberPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter, ]
    ordering_fields = ['id', "create_time", "update_time", ]
    filter_class = AsnListFilter

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
                return AsnListModel.objects.filter(openid=self.request.auth.openid, is_delete=False)
            else:
                return AsnListModel.objects.filter(openid=self.request.auth.openid, id=id, is_delete=False)
        else:
            return AsnListModel.objects.none()

    def get_serializer_class(self):
        if self.action in ['create']:
            return serializers.ASNListPartialUpdateSerializer
        else:
            return self.http_method_not_allowed(request=self.request)

    def create(self, request, pk):
        qs = self.get_object()
        if qs.openid != self.request.auth.openid:
            raise APIException({"detail": "Cannot delete data which not yours"})
        else:
            if qs.asn_status == 1:
                if AsnDetailModel.objects.filter(openid=self.request.auth.openid, asn_code=qs.asn_code,
                                                                asn_status=1, is_delete=False).exists():
                    qs.asn_status = 2
                    asn_detail_list = AsnDetailModel.objects.filter(openid=self.request.auth.openid, asn_code=qs.asn_code,
                                                                    asn_status=1, is_delete=False)
                    for i in range(len(asn_detail_list)):
                        goods_qty_change = stocklist.objects.filter(openid=self.request.auth.openid,
                                                                    goods_code=str(asn_detail_list[i].goods_code)).first()
                        goods_qty_change.asn_stock = goods_qty_change.asn_stock - asn_detail_list[i].goods_qty
                        if goods_qty_change.asn_stock < 0:
                            goods_qty_change.asn_stock = 0
                        goods_qty_change.pre_load_stock = goods_qty_change.pre_load_stock + asn_detail_list[i].goods_qty
                        goods_qty_change.save()
                    asn_detail_list.update(asn_status=2)
                    qs.save()
                    serializer = self.get_serializer(qs, many=False)
                    headers = self.get_success_headers(serializer.data)
                    return Response(serializer.data, status=200, headers=headers)
                else:
                    raise APIException({"detail": "Please Enter The ASN Detail"})
            else:
                raise APIException({"detail": "This ASN Status Is Not 1"})

class AsnPreSortViewSet(viewsets.ModelViewSet):
    """
        retrieve:
            Response a data list（get）
    """
    pagination_class = MyPageNumberPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter, ]
    ordering_fields = ['id', "create_time", "update_time", ]
    filter_class = AsnListFilter

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
                return AsnListModel.objects.filter(openid=self.request.auth.openid, is_delete=False)
            else:
                return AsnListModel.objects.filter(openid=self.request.auth.openid, id=id, is_delete=False)
        else:
            return AsnListModel.objects.none()

    def get_serializer_class(self):
        if self.action in ['create']:
            return serializers.ASNListUpdateSerializer
        else:
            return self.http_method_not_allowed(request=self.request)

    def create(self, request, pk):
        qs = self.get_object()
        if qs.openid != self.request.auth.openid:
            raise APIException({"detail": "Cannot delete data which not yours"})
        else:
            if qs.asn_status == 2:
                qs.asn_status = 3
                asn_detail_list = AsnDetailModel.objects.filter(openid=self.request.auth.openid, asn_code=qs.asn_code,
                                                                asn_status=2, is_delete=False)
                for i in range(len(asn_detail_list)):
                    goods_qty_change = stocklist.objects.filter(openid=self.request.auth.openid,
                                                                goods_code=str(asn_detail_list[i].goods_code)).first()
                    goods_qty_change.pre_load_stock = goods_qty_change.pre_load_stock - asn_detail_list[i].goods_qty
                    if goods_qty_change.pre_load_stock < 0:
                        goods_qty_change.pre_load_stock = 0
                    goods_qty_change.pre_sort_stock = goods_qty_change.pre_sort_stock + asn_detail_list[i].goods_qty
                    goods_qty_change.save()
                asn_detail_list.update(asn_status=3)
                qs.save()
                serializer = self.get_serializer(qs, many=False)
                headers = self.get_success_headers(serializer.data)
                return Response(serializer.data, status=200, headers=headers)
            else:
                raise APIException({"detail": "This ASN Status Is Not 2"})

class AsnSortedViewSet(viewsets.ModelViewSet):
    """
        create:
            Finish Sorted

        update:
            All Sorted
    """
    pagination_class = MyPageNumberPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter, ]
    ordering_fields = ['id', "create_time", "update_time", ]
    filter_class = AsnListFilter

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
                return AsnListModel.objects.filter(openid=self.request.auth.openid, is_delete=False)
            else:
                return AsnListModel.objects.filter(openid=self.request.auth.openid, id=id, is_delete=False)
        else:
            return AsnListModel.objects.none()

    def get_serializer_class(self):
        if self.action in ['create', 'update']:
            return serializers.ASNSortedPostSerializer
        else:
            return self.http_method_not_allowed(request=self.request)

    def create(self, request, pk):
        qs = self.get_object()
        if qs.asn_status != 3:
            raise APIException({"detail": "This ASN Status Is Not 3"})
        else:
            data = self.request.data
            for j in range(len(data['goodsData'])):
                goods_qty_change = stocklist.objects.filter(openid=self.request.auth.openid,
                                                            goods_code=str(
                                                                data['goodsData'][j].get('goods_code'))).first()
                asn_detail = AsnDetailModel.objects.filter(openid=self.request.auth.openid,
                                                           asn_code=str(data['asn_code']),
                                                           asn_status=3, customer=str(data['customer']),
                                                           goods_code=str(
                                                               data['goodsData'][j].get('goods_code'))).first()
                goods_detail = goods.objects.filter(openid=self.request.auth.openid,
                                                    goods_code=str(data['goodsData'][j].get('goods_code')),
                                                    is_delete=False).first()
                if int(data['goodsData'][j].get('goods_actual_qty')) == 0:
                    asn_detail.goods_actual_qty = int(data['goodsData'][j].get('goods_actual_qty'))
                    asn_detail.goods_shortage_qty = asn_detail.goods_qty
                    asn_detail.goods_cost = 0
                    qs.total_cost = qs.total_cost - (asn_detail.goods_shortage_qty * goods_detail.goods_cost)
                    goods_qty_change.goods_qty = goods_qty_change.goods_qty - asn_detail.goods_qty
                    goods_qty_change.pre_sort_stock = goods_qty_change.pre_sort_stock - asn_detail.goods_qty
                    asn_detail.asn_status = 5
                    asn_detail.save()
                    goods_qty_change.save()
                    if goods_qty_change.goods_qty == 0 and goods_qty_change.back_order_stock == 0:
                        goods_qty_change.delete()
                else:
                    asn_detail.goods_actual_qty = int(data['goodsData'][j].get('goods_actual_qty'))
                    goods_qty_check = asn_detail.goods_qty - int(data['goodsData'][j].get('goods_actual_qty'))
                    if goods_qty_check > 0:
                        asn_detail.goods_shortage_qty = goods_qty_check
                        asn_detail.goods_more_qty = 0
                        asn_detail.goods_cost = asn_detail.goods_cost - (asn_detail.goods_shortage_qty * goods_detail.goods_cost)
                        qs.total_cost = qs.total_cost - (asn_detail.goods_shortage_qty * goods_detail.goods_cost)
                        goods_qty_change.goods_qty = goods_qty_change.goods_qty - goods_qty_check
                        goods_qty_change.pre_sort_stock = goods_qty_change.pre_sort_stock - asn_detail.goods_qty
                        goods_qty_change.sorted_stock = goods_qty_change.sorted_stock + int(data['goodsData'][j].get('goods_actual_qty'))
                    elif goods_qty_check == 0:
                        asn_detail.goods_shortage_qty = 0
                        asn_detail.goods_more_qty = 0
                        goods_qty_change.pre_sort_stock = goods_qty_change.pre_sort_stock - int(data['goodsData'][j].get('goods_actual_qty'))
                        goods_qty_change.sorted_stock = goods_qty_change.sorted_stock + int(data['goodsData'][j].get('goods_actual_qty'))
                    elif goods_qty_check < 0:
                        asn_detail.goods_shortage_qty = 0
                        asn_detail.goods_more_qty = abs(goods_qty_check)
                        asn_detail.goods_cost = asn_detail.goods_cost + (asn_detail.goods_more_qty * goods_detail.goods_cost)
                        qs.total_cost = qs.total_cost + (asn_detail.goods_more_qty * goods_detail.goods_cost)
                        goods_qty_change.goods_qty = goods_qty_change.goods_qty + abs(goods_qty_check)
                        goods_qty_change.pre_sort_stock = goods_qty_change.pre_sort_stock - asn_detail.goods_qty
                        goods_qty_change.sorted_stock = goods_qty_change.sorted_stock + int(data['goodsData'][j].get('goods_actual_qty'))
                    asn_detail.asn_status = 4
                    asn_detail.save()
                    goods_qty_change.save()
                    if goods_qty_change.goods_qty == 0 and goods_qty_change.back_order_stock == 0:
                        goods_qty_change.delete()
            if AsnDetailModel.objects.filter(openid=self.request.auth.openid, asn_code=str(data['asn_code']),
                                                      asn_status=4, customer=str(data['customer'])).exists():
                qs.asn_status = 4
            else:
                qs.asn_status = 5
            qs.save()
            return Response({"detail": "success"}, status=200)

    def update(self, request, *args, **kwargs):
        data = self.request.data
        qs = self.get_queryset().filter(asn_code=data['asn_code']).first()
        if qs.asn_status != 3:
            raise APIException({"detail": "This ASN Status Is Not 3"})
        else:
            for j in range(len(data['goodsData'])):
                goods_qty_change = stocklist.objects.filter(openid=self.request.auth.openid,
                                                            goods_code=str(
                                                                data['goodsData'][j].get('goods_code'))).first()
                asn_detail = AsnDetailModel.objects.filter(openid=self.request.auth.openid,
                                                           asn_code=str(data['asn_code']),
                                                           goods_code=str(
                                                               data['goodsData'][j].get('goods_code'))).first()
                goods_detail = goods.objects.filter(openid=self.request.auth.openid,
                                                    goods_code=str(data['goodsData'][j].get('goods_code')),
                                                    is_delete=False).first()
                if int(data['goodsData'][j].get('goods_actual_qty')) == 0:
                    asn_detail.goods_actual_qty = int(data['goodsData'][j].get('goods_actual_qty'))
                    asn_detail.goods_shortage_qty = asn_detail.goods_qty
                    asn_detail.goods_cost = 0
                    qs.total_cost = qs.total_cost - (asn_detail.goods_shortage_qty * goods_detail.goods_cost)
                    goods_qty_change.goods_qty = goods_qty_change.goods_qty - asn_detail.goods_qty
                    goods_qty_change.pre_sort_stock = goods_qty_change.pre_sort_stock - asn_detail.goods_qty
                    asn_detail.asn_status = 5
                    asn_detail.save()
                    goods_qty_change.save()
                    if goods_qty_change.goods_qty == 0 and goods_qty_change.back_order_stock == 0:
                        goods_qty_change.delete()
                else:
                    asn_detail.goods_actual_qty = int(data['goodsData'][j].get('goods_actual_qty'))
                    goods_qty_check = asn_detail.goods_qty - int(data['goodsData'][j].get('goods_actual_qty'))
                    if goods_qty_check > 0:
                        asn_detail.goods_shortage_qty = goods_qty_check
                        asn_detail.goods_more_qty = 0
                        asn_detail.goods_cost = asn_detail.goods_cost - (asn_detail.goods_shortage_qty * goods_detail.goods_cost)
                        qs.total_cost = qs.total_cost - (asn_detail.goods_shortage_qty * goods_detail.goods_cost)
                        goods_qty_change.goods_qty = goods_qty_change.goods_qty - goods_qty_check
                        goods_qty_change.pre_sort_stock = goods_qty_change.pre_sort_stock - asn_detail.goods_qty
                        goods_qty_change.sorted_stock = goods_qty_change.sorted_stock + int(data['goodsData'][j].get('goods_actual_qty'))
                    elif goods_qty_check == 0:
                        asn_detail.goods_shortage_qty = 0
                        asn_detail.goods_more_qty = 0
                        goods_qty_change.pre_sort_stock = goods_qty_change.pre_sort_stock - int(data['goodsData'][j].get('goods_actual_qty'))
                        goods_qty_change.sorted_stock = goods_qty_change.sorted_stock + int(data['goodsData'][j].get('goods_actual_qty'))
                    elif goods_qty_check < 0:
                        asn_detail.goods_shortage_qty = 0
                        asn_detail.goods_more_qty = abs(goods_qty_check)
                        asn_detail.goods_cost = asn_detail.goods_cost + (asn_detail.goods_more_qty * goods_detail.goods_cost)
                        qs.total_cost = qs.total_cost + (asn_detail.goods_more_qty * goods_detail.goods_cost)
                        goods_qty_change.goods_qty = goods_qty_change.goods_qty + abs(goods_qty_check)
                        goods_qty_change.pre_sort_stock = goods_qty_change.pre_sort_stock - asn_detail.goods_qty
                        goods_qty_change.sorted_stock = goods_qty_change.sorted_stock + int(data['goodsData'][j].get('goods_actual_qty'))
                    asn_detail.asn_status = 4
                    asn_detail.save()
                    goods_qty_change.save()
                    if goods_qty_change.goods_qty == 0 and goods_qty_change.back_order_stock == 0:
                        goods_qty_change.delete()
            if AsnDetailModel.objects.filter(openid=self.request.auth.openid, asn_code=str(data['asn_code']),
                                                      asn_status=4).exists():
                qs.asn_status = 4
            else:
                qs.asn_status = 5
            qs.save()
            return Response({"detail": "success"}, status=200)

class MoveToBinViewSet(viewsets.ModelViewSet):
    """
        create:
            Create a data line（post）
    """
    pagination_class = MyPageNumberPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter, ]
    ordering_fields = ['id', "create_time", "update_time", ]
    filter_class = AsnDetailFilter

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
                return AsnDetailModel.objects.filter(openid=self.request.auth.openid, is_delete=False)
            else:
                return AsnDetailModel.objects.filter(openid=self.request.auth.openid, id=id, is_delete=False)
        else:
            return AsnDetailModel.objects.none()

    def get_serializer_class(self):
        if self.action in ['retrieve']:
            return serializers.ASNDetailGetSerializer
        elif self.action in ['create', 'update']:
            return serializers.MoveToBinSerializer
        else:
            return self.http_method_not_allowed(request=self.request)

    def create(self, request, pk):
        qs = self.get_object()
        if qs.openid != self.request.auth.openid:
            raise APIException({"detail": "Cannot delete data which not yours"})
        else:
            if qs.asn_status != 4:
                raise APIException({"detail": "This ASN Status Is Not 4"})
            else:
                data = self.request.data
                if 'bin_name' not in data:
                    raise APIException({"detail": "Please Enter the Bin Name"})
                else:
                    bin_detail = binset.objects.filter(openid=self.request.auth.openid,
                                                       bin_name=str(data['bin_name']),
                                                       is_delete=False).first()
                    asn_detail = AsnListModel.objects.filter(openid=self.request.auth.openid,
                                                             asn_code=str(data['asn_code'])).first()
                    goods_qty_change = stocklist.objects.filter(openid=self.request.auth.openid,
                                                                goods_code=str(data['goods_code'])).first()
                    if int(data['qty']) <= 0:
                        raise APIException({"detail": "Move QTY Must > 0"})
                    else:
                        staff_name = staff.objects.filter(openid=self.request.auth.openid,
                                                          id=self.request.META.get('HTTP_OPERATOR')).first().staff_name
                        move_qty = qs.goods_actual_qty - qs.sorted_qty - int(data['qty'])
                        if move_qty > 0:
                            qs.sorted_qty = qs.sorted_qty + int(data['qty'])
                            goods_qty_change.sorted_stock = goods_qty_change.sorted_stock - int(data['qty'])
                            goods_qty_change.onhand_stock = goods_qty_change.onhand_stock + int(data['qty'])
                            if bin_detail.bin_property == 'Damage':
                                goods_qty_change.damage_stock = goods_qty_change.damage_stock + int(data['qty'])
                                qs.goods_damage_qty = qs.goods_damage_qty + int(data['qty'])
                            elif bin_detail.bin_property == 'Inspection':
                                goods_qty_change.inspect_stock = goods_qty_change.inspect_stock + int(data['qty'])
                            elif bin_detail.bin_property == 'Holding':
                                goods_qty_change.hold_stock = goods_qty_change.hold_stock + int(data['qty'])
                            else:
                                goods_qty_change.can_order_stock = goods_qty_change.can_order_stock + int(data['qty'])
                            qs.save()
                            goods_qty_change.save()
                            store_code = Md5.md5(str(data['goods_code']))
                            stockbin.objects.create(openid=self.request.auth.openid,
                                                    bin_name=str(data['bin_name']),
                                                    goods_code=str(data['goods_code']),
                                                    goods_desc=goods_qty_change.goods_desc,
                                                    goods_qty=int(data['qty']),
                                                    bin_size=bin_detail.bin_size,
                                                    bin_property=bin_detail.bin_property,
                                                    t_code=store_code,
                                                    create_time=qs.create_time
                                                    )
                            qtychangerecorder.objects.create(openid=self.request.auth.openid,
                                                             mode_code=qs.asn_code,
                                                             bin_name=str(data['bin_name']),
                                                             goods_code=str(data['goods_code']),
                                                             goods_desc=goods_qty_change.goods_desc,
                                                             goods_qty=int(data['qty']),
                                                             store_code=store_code,
                                                             creator=str(staff_name)
                                                             )
                            cur_date = timezone.now().date()
                            line_data = cyclecount.objects.filter(openid=self.request.auth.openid,
                                                                  bin_name=str(data['bin_name']),
                                                                  goods_code=str(data['goods_code']),
                                                                  create_time__gte=cur_date)
                            bin_check = stockbin.objects.filter(openid=self.request.auth.openid,
                                                                bin_name=str(data['bin_name']),
                                                                goods_code=str(data['goods_code']),
                                                                )
                            if bin_check.exists():
                                bin_stock = bin_check.aggregate(sum=Sum('goods_qty'))["sum"]
                            else:
                                bin_stock = 0
                            if line_data.exists():
                                line_data.goods_qty = bin_stock + int(data['qty'])
                                line_data.update(goods_qty=line_data.goods_qty)
                            else:
                                cyclecount.objects.create(openid=self.request.auth.openid,
                                                          bin_name=str(data['bin_name']),
                                                          goods_code=str(data['goods_code']),
                                                          goods_qty=int(data['qty']),
                                                          creator=str(staff_name)
                                                          )
                            if bin_detail.empty_label is True:
                                bin_detail.empty_label = False
                                bin_detail.save()
                        elif move_qty == 0:
                            qs.sorted_qty = qs.sorted_qty + int(data['qty'])
                            qs.asn_status = 5
                            goods_qty_change.sorted_stock = goods_qty_change.sorted_stock - int(data['qty'])
                            goods_qty_change.onhand_stock = goods_qty_change.onhand_stock + int(data['qty'])
                            if bin_detail.bin_property == 'Damage':
                                goods_qty_change.damage_stock = goods_qty_change.damage_stock + int(data['qty'])
                                qs.goods_damage_qty = qs.goods_damage_qty + int(data['qty'])
                            elif bin_detail.bin_property == 'Inspection':
                                goods_qty_change.inspect_stock = goods_qty_change.inspect_stock + int(data['qty'])
                            elif bin_detail.bin_property == 'Holding':
                                goods_qty_change.hold_stock = goods_qty_change.hold_stock + int(data['qty'])
                            else:
                                goods_qty_change.can_order_stock = goods_qty_change.can_order_stock + int(data['qty'])
                            cur_date = timezone.now().date()
                            line_data = cyclecount.objects.filter(openid=self.request.auth.openid,
                                                                  bin_name=str(data['bin_name']),
                                                                  goods_code=str(data['goods_code']),
                                                                  create_time__gte=cur_date)
                            bin_check = stockbin.objects.filter(openid=self.request.auth.openid,
                                                                bin_name=str(data['bin_name']),
                                                                goods_code=str(data['goods_code']),
                                                                )
                            if bin_check.exists():
                                bin_stock = bin_check.aggregate(sum=Sum('goods_qty'))["sum"]
                            else:
                                bin_stock = 0
                            if line_data.exists():
                                line_data.goods_qty = bin_stock + int(data['qty'])
                                line_data.update(goods_qty=line_data.goods_qty)
                            else:
                                cyclecount.objects.create(openid=self.request.auth.openid,
                                                          bin_name=str(data['bin_name']),
                                                          goods_code=str(data['goods_code']),
                                                          goods_qty=int(data['qty']),
                                                          creator=str(staff_name),
                                                          t_code=Md5.md5(str(data['bin_name']))
                                                          )
                            qs.save()
                            goods_qty_change.save()
                            if AsnDetailModel.objects.filter(openid=self.request.auth.openid,
                                                             asn_code=str(data['asn_code']),
                                                             asn_status=4
                                                             ).exists():
                                pass
                            else:
                                asn_detail.asn_status = 5
                                asn_detail.save()
                            store_code = Md5.md5(str(data['goods_code']))
                            stockbin.objects.create(openid=self.request.auth.openid,
                                                    bin_name=str(data['bin_name']),
                                                    goods_code=str(data['goods_code']),
                                                    goods_desc=goods_qty_change.goods_desc,
                                                    goods_qty=int(data['qty']),
                                                    bin_size=bin_detail.bin_size,
                                                    bin_property=bin_detail.bin_property,
                                                    t_code=store_code,
                                                    create_time=qs.create_time)
                            qtychangerecorder.objects.create(openid=self.request.auth.openid,
                                                             mode_code=qs.asn_code,
                                                             bin_name=str(data['bin_name']),
                                                             goods_code=str(data['goods_code']),
                                                             goods_desc=goods_qty_change.goods_desc,
                                                             goods_qty=int(data['qty']),
                                                             store_code=store_code,
                                                             creator=str(staff_name)
                                                             )
                            if bin_detail.empty_label is True:
                                bin_detail.empty_label = False
                                bin_detail.save()
                        elif move_qty < 0:
                            raise APIException({"detail": "Move Qty must < Actual Arrive Qty"})
                        return Response({"detail": "success"}, status=200)

    def update(self, request, *args, **kwargs):
        data = self.request.data
        qs_list = self.get_queryset().filter(asn_code=data['asn_code'])
        if qs_list[0].openid != self.request.auth.openid:
            raise APIException({"detail": "Cannot delete data which not yours"})
        else:
            if 'bin_name' not in data:
                raise APIException({"detail": "Please Enter the Bin Name"})
            else:
                bin_detail = binset.objects.filter(openid=self.request.auth.openid,
                                                   bin_name=str(data['bin_name']),
                                                   is_delete=False).first()
                asn_detail = AsnListModel.objects.filter(openid=self.request.auth.openid,
                                                         asn_code=str(data['asn_code'])
                                                         ).first()
                staff_name = staff.objects.filter(openid=self.request.auth.openid,
                                                  id=self.request.META.get('HTTP_OPERATOR')).first().staff_name
                for i in range(len(data['res_data'])):
                    goods_qty_change = stocklist.objects.filter(openid=self.request.auth.openid,
                                                                goods_code=str(data['res_data'][i]['goods_code'])).first()
                    if int(data['res_data'][i]['qty']) <= 0:
                        continue
                    else:
                        qs = qs_list.filter(goods_code=str(data['res_data'][i]['goods_code'])).first()
                        move_qty = qs.goods_actual_qty - qs.sorted_qty - int(data['res_data'][i]['qty'])
                        if move_qty > 0:
                            qs.sorted_qty = qs.sorted_qty + int(data['res_data'][i]['qty'])
                            goods_qty_change.sorted_stock = goods_qty_change.sorted_stock - int(data['res_data'][i]['qty'])
                            goods_qty_change.onhand_stock = goods_qty_change.onhand_stock + int(data['res_data'][i]['qty'])
                            if bin_detail.bin_property == 'Damage':
                                goods_qty_change.damage_stock = goods_qty_change.damage_stock + int(data['res_data'][i]['qty'])
                                qs.goods_damage_qty = qs.goods_damage_qty + int(data['res_data'][i]['qty'])
                            elif bin_detail.bin_property == 'Inspection':
                                goods_qty_change.inspect_stock = goods_qty_change.inspect_stock + int(data['res_data'][i]['qty'])
                            elif bin_detail.bin_property == 'Holding':
                                goods_qty_change.hold_stock = goods_qty_change.hold_stock + int(data['res_data'][i]['qty'])
                            else:
                                goods_qty_change.can_order_stock = goods_qty_change.can_order_stock + int(data['res_data'][i]['qty'])
                            qs.save()
                            goods_qty_change.save()
                            store_code = Md5.md5(str(data['res_data'][i]['goods_code']))
                            stockbin.objects.create(openid=self.request.auth.openid,
                                                    bin_name=str(data['bin_name']),
                                                    goods_code=str(data['res_data'][i]['goods_code']),
                                                    goods_desc=goods_qty_change.goods_desc,
                                                    goods_qty=int(data['res_data'][i]['qty']),
                                                    bin_size=bin_detail.bin_size,
                                                    bin_property=bin_detail.bin_property,
                                                    t_code=store_code,
                                                    create_time=qs.create_time
                                                    )
                            qtychangerecorder.objects.create(openid=self.request.auth.openid,
                                                             mode_code=qs.asn_code,
                                                             bin_name=str(data['bin_name']),
                                                             goods_code=str(data['res_data'][i]['goods_code']),
                                                             goods_desc=goods_qty_change.goods_desc,
                                                             goods_qty=int(data['res_data'][i]['qty']),
                                                             store_code=store_code,
                                                             creator=str(staff_name)
                                                             )
                            cur_date = timezone.now().date()
                            line_data = cyclecount.objects.filter(openid=self.request.auth.openid,
                                                                  bin_name=str(data['bin_name']),
                                                                  goods_code=str(data['res_data'][i]['goods_code']),
                                                                  create_time__gte=cur_date)
                            bin_check = stockbin.objects.filter(openid=self.request.auth.openid,
                                                                bin_name=str(data['bin_name']),
                                                                goods_code=str(data['res_data'][i]['goods_code']),
                                                                )
                            if bin_check.exists():
                                bin_stock = bin_check.aggregate(sum=Sum('goods_qty'))["sum"]
                            else:
                                bin_stock = 0
                            if line_data.exists():
                                line_data.goods_qty = bin_stock + int(data['res_data'][i]['qty'])
                                line_data.update(goods_qty=line_data.goods_qty)
                            else:
                                cyclecount.objects.create(openid=self.request.auth.openid,
                                                          bin_name=str(data['bin_name']),
                                                          goods_code=str(data['res_data'][i]['goods_code']),
                                                          goods_qty=int(data['res_data'][i]['qty']),
                                                          creator=str(staff_name)
                                                          )
                            if bin_detail.empty_label == True:
                                bin_detail.empty_label = False
                                bin_detail.save()
                        elif move_qty == 0:
                            qs.sorted_qty = qs.sorted_qty + int(data['res_data'][i]['qty'])
                            qs.asn_status = 5
                            goods_qty_change.sorted_stock = goods_qty_change.sorted_stock - int(data['res_data'][i]['qty'])
                            goods_qty_change.onhand_stock = goods_qty_change.onhand_stock + int(data['res_data'][i]['qty'])
                            if bin_detail.bin_property == 'Damage':
                                goods_qty_change.damage_stock = goods_qty_change.damage_stock + int(data['res_data'][i]['qty'])
                                qs.goods_damage_qty = qs.goods_damage_qty + int(data['res_data'][i]['qty'])
                            elif bin_detail.bin_property == 'Inspection':
                                goods_qty_change.inspect_stock = goods_qty_change.inspect_stock + int(data['res_data'][i]['qty'])
                            elif bin_detail.bin_property == 'Holding':
                                goods_qty_change.hold_stock = goods_qty_change.hold_stock + int(data['res_data'][i]['qty'])
                            else:
                                goods_qty_change.can_order_stock = goods_qty_change.can_order_stock + int(data['res_data'][i]['qty'])
                            cur_date = timezone.now().date()
                            line_data = cyclecount.objects.filter(openid=self.request.auth.openid,
                                                                  bin_name=str(data['bin_name']),
                                                                  goods_code=str(data['res_data'][i]['goods_code']),
                                                                  create_time__gte=cur_date)
                            bin_check = stockbin.objects.filter(openid=self.request.auth.openid,
                                                                bin_name=str(data['bin_name']),
                                                                goods_code=str(data['res_data'][i]['goods_code']),
                                                                )
                            if bin_check.exists():
                                bin_stock = bin_check.aggregate(sum=Sum('goods_qty'))["sum"]
                            else:
                                bin_stock = 0
                            if line_data.exists():
                                line_data.goods_qty = bin_stock + int(data['res_data'][i]['qty'])
                                line_data.update(goods_qty=line_data.goods_qty)
                            else:
                                cyclecount.objects.create(openid=self.request.auth.openid,
                                                          bin_name=str(data['bin_name']),
                                                          goods_code=str(data['res_data'][i]['goods_code']),
                                                          goods_qty=int(data['res_data'][i]['qty']),
                                                          creator=str(staff_name),
                                                          t_code=Md5.md5(str(data['bin_name']))
                                                          )
                            qs.save()
                            goods_qty_change.save()
                            if AsnDetailModel.objects.filter(openid=self.request.auth.openid,
                                                             asn_code=str(data['asn_code']),
                                                             asn_status=4
                                                             ).exists():
                                pass
                            else:
                                asn_detail.asn_status = 5
                                asn_detail.save()
                            store_code = Md5.md5(str(data['res_data'][i]['goods_code']))
                            stockbin.objects.create(openid=self.request.auth.openid,
                                                    bin_name=str(data['bin_name']),
                                                    goods_code=str(data['res_data'][i]['goods_code']),
                                                    goods_desc=goods_qty_change.goods_desc,
                                                    goods_qty=int(data['res_data'][i]['qty']),
                                                    bin_size=bin_detail.bin_size,
                                                    bin_property=bin_detail.bin_property,
                                                    t_code=store_code,
                                                    create_time=qs.create_time)
                            qtychangerecorder.objects.create(openid=self.request.auth.openid,
                                                             mode_code=qs.asn_code,
                                                             bin_name=str(data['bin_name']),
                                                             goods_code=str(data['res_data'][i]['goods_code']),
                                                             goods_desc=goods_qty_change.goods_desc,
                                                             goods_qty=int(data['res_data'][i]['qty']),
                                                             store_code=store_code,
                                                             creator=str(staff_name)
                                                             )
                            if bin_detail.empty_label == True:
                                bin_detail.empty_label = False
                                bin_detail.save()
                return Response({"detail": "success"}, status=200)

class FileListDownloadView(viewsets.ModelViewSet):
    renderer_classes = (FileListRenderCN, ) + tuple(api_settings.DEFAULT_RENDERER_CLASSES)
    filter_backends = [DjangoFilterBackend, OrderingFilter, ]
    ordering_fields = ['id', "create_time", "update_time", ]
    filter_class = AsnListFilter

    def get_project(self):
        try:
            id = self.kwargs.get('pk')
            return id
        except:
            return None

    def get_queryset(self):
        id = self.get_project()
        if self.request.user:
            empty_qs = AsnListModel.objects.filter(
                Q(openid=self.request.auth.openid, asn_status=1, is_delete=False) & Q(customer=''))
            cur_date = timezone.now()
            date_check = relativedelta(day=1)
            if len(empty_qs) > 0:
                for i in range(len(empty_qs)):
                    if empty_qs[i].create_time <= cur_date - date_check:
                        empty_qs[i].delete()
            if id is None:
                return AsnListModel.objects.filter(
                    Q(openid=self.request.auth.openid, is_delete=False) & ~Q(customer=''))
            else:
                return AsnListModel.objects.filter(
                    Q(openid=self.request.auth.openid, id=id, is_delete=False) & ~Q(customer=''))
        else:
            return AsnListModel.objects.none()

    def get_serializer_class(self):
        if self.action in ['list']:
            return serializers.FileListRenderSerializer
        else:
            return self.http_method_not_allowed(request=self.request)

    def get_lang(self, data):
        lang = self.request.META.get('HTTP_LANGUAGE')
        if lang:
            if lang == 'zh-hans':
                return FileListRenderCN().render(data)
            else:
                return FileListRenderEN().render(data)
        else:
            return FileListRenderEN().render(data)

    def list(self, request, *args, **kwargs):
        from datetime import datetime
        dt = datetime.now()
        data = (
            FileListRenderSerializer(instance).data
            for instance in self.filter_queryset(self.get_queryset())
        )
        renderer = self.get_lang(data)
        response = StreamingHttpResponse(
            renderer,
            content_type="text/csv"
        )
        response['Content-Disposition'] = "attachment; filename='asnlist_{}.csv'".format(str(dt.strftime('%Y%m%d%H%M%S%f')))
        return response

class FileDetailDownloadView(viewsets.ModelViewSet):
    serializer_class = serializers.FileDetailRenderSerializer
    renderer_classes = (FileDetailRenderCN, ) + tuple(api_settings.DEFAULT_RENDERER_CLASSES)
    filter_backends = [DjangoFilterBackend, OrderingFilter, ]
    ordering_fields = ['id', "create_time", "update_time", ]
    filter_class = AsnDetailFilter

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
                return AsnDetailModel.objects.filter(openid=self.request.auth.openid, is_delete=False)
            else:
                return AsnDetailModel.objects.filter(openid=self.request.auth.openid, id=id, is_delete=False)
        else:
            return AsnDetailModel.objects.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return serializers.FileDetailRenderSerializer
        else:
            return self.http_method_not_allowed(request=self.request)

    def get_lang(self, data):
        lang = self.request.META.get('HTTP_LANGUAGE')
        if lang:
            if lang == 'zh-hans':
                return FileDetailRenderCN().render(data)
            else:
                return FileDetailRenderEN().render(data)
        else:
            return FileDetailRenderEN().render(data)

    def list(self, request, *args, **kwargs):
        from datetime import datetime
        dt = datetime.now()
        data = (
            FileDetailRenderSerializer(instance).data
            for instance in self.filter_queryset(self.get_queryset())
        )
        renderer = self.get_lang(data)
        response = StreamingHttpResponse(
            renderer,
            content_type="text/csv"
        )
        response['Content-Disposition'] = "attachment; filename='asndetail_{}.csv'".format(str(dt.strftime('%Y%m%d%H%M%S%f')))
        return response



# =========================
# 跳过版：直接创建 ASN（状态=3）
# =========================
class SkipAsnListCreateViewSet(AsnListViewSet):
    """
    POST /asn/skip_create/
    作用：创建 ASN，并直接将 asn_status 设为 3（跳过待到货/待卸货）
    """
    def create(self, request, *args, **kwargs):
        data = self.request.data.copy()
        data['openid'] = self.request.auth.openid
        custom_asn = self.request.GET.get('custom_asn', '')

        # 生成 asn_code 的逻辑与原实现一致，保持可追溯性
        if custom_asn:
            data['asn_code'] = custom_asn
        else:
            qs_set = AsnListModel.objects.filter(openid=self.request.auth.openid)
            order_day = str(timezone.now().strftime('%Y%m%d'))
            if qs_set.exists():
                asn_last_code = qs_set.order_by('-id').first().asn_code
                if str(asn_last_code[3:11]) == order_day:
                    order_create_no = str(int(asn_last_code[11:]) + 1)
                    data['asn_code'] = 'ASN' + order_day + order_create_no
                else:
                    data['asn_code'] = 'ASN' + order_day + '1'
            else:
                data['asn_code'] = 'ASN' + order_day + '1'   # 与原逻辑完全一致
            if 'recive_time' not in data or not data['recive_time']:
                data['recive_time'] = timezone.now()

        # 关键差异：直接进入状态 3
        data['asn_status'] = 3

        # 仍按原逻辑生成条码并写入 scanner
        data['bar_code'] = Md5.md5(data['asn_code'])
        serializer = serializers.ASNListPostSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        scanner.objects.create(
            openid=self.request.auth.openid,
            mode="ASN",
            code=data['asn_code'],
            bar_code=data['bar_code']
        )
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=200, headers=headers)


# ==========================================
# 跳过版：创建 ASN 明细（状态=3，库存进 pre_sort）
# ==========================================
class SkipAsnDetailCreateViewSet(AsnDetailViewSet):
    """
    POST /asn_detail/skip_create/
    作用：创建 ASN 明细并直接使明细处于 asn_status=3，
          同时库存直接累加到 pre_sort_stock（跳过 asn_stock / pre_load_stock）
    """
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        data = self.request.data
        customer_other_fees = data.get('customer_other_fees', {})
        fees_sum = self._sum_customer_other_fees(customer_other_fees)  # 复用同名方法；若不在同一类，可复制该小函数

        # 校验 ASN 与客户存在（沿用你现有校验口径）
        if not AsnListModel.objects.filter(
            openid=self.request.auth.openid, asn_code=str(data['asn_code']), is_delete=False
        ).exists():
            raise APIException({"detail": "ASN Code does not exists"})
        if not customer.objects.filter(
            openid=self.request.auth.openid, customer_name=str(data['customer']), is_delete=False
        ).exists():
            raise APIException({"detail": "Customer does not exists"})

        operator = self.request.META.get('HTTP_OPERATOR')
        staff_name = staff.objects.filter(
            openid=self.request.auth.openid, id=operator
        ).first().staff_name

        # 逐条校验入参（与原 create 一致，保证 serializer 约束）
        for i in range(len(data['goods_code'])):
            check_data = {
                'openid': self.request.auth.openid,
                'asn_code': str(data['asn_code']),
                'customer': str(data['customer']),
                'goods_code': str(data['goods_code'][i]),
                'goods_qty': int(data['goods_qty'][i]),
                'creator': str(staff_name),

            }
            serializer = serializers.ASNDetailPostSerializer(data=check_data)
            serializer.is_valid(raise_exception=True)

        post_data_list = []
        cost_list = []

        # 与原逻辑一致：按 goods 成本计算总成本；不同点是库存去向改为 pre_sort_stock
        for j in range(len(data['goods_code'])):
            gcode = str(data['goods_code'][j])
            gqty = int(data['goods_qty'][j])

            goods_detail = goods.objects.filter(
                openid=self.request.auth.openid, goods_code=gcode, is_delete=False
            ).first()
            goods_cost = round(goods_detail.goods_cost * gqty, 2)

            # 关键差异：直接进 pre_sort_stock（不走 asn_stock）
            if stocklist.objects.filter(openid=self.request.auth.openid, goods_code=gcode).exists():
                goods_qty_change = stocklist.objects.filter(
                    openid=self.request.auth.openid, goods_code=gcode
                ).first()
                goods_qty_change.goods_qty = goods_qty_change.goods_qty + gqty
                goods_qty_change.pre_sort_stock = goods_qty_change.pre_sort_stock + gqty
                goods_qty_change.save()
            else:
                stocklist.objects.create(
                    openid=self.request.auth.openid,
                    goods_code=gcode,
                    goods_desc=goods_detail.goods_desc,
                    goods_qty=gqty,
                    pre_sort_stock=gqty
                )

            post_data = AsnDetailModel(
                openid=self.request.auth.openid,
                asn_code=str(data['asn_code']),
                customer=str(data['customer']),
                goods_code=gcode,
                goods_desc=str(goods_detail.goods_desc),
                goods_qty=gqty,
                goods_cost=goods_cost,
                asn_status=3,              # 明细直接到 3
                creator=str(staff_name),

            )
            post_data_list.append(post_data)
            cost_list.append(goods_cost)

        # 插入明细
        AsnDetailModel.objects.bulk_create(post_data_list, batch_size=100)

        # 合并相同 goods_code（完全沿用你原先去重合并的思路）
        check_data_qs = AsnDetailModel.objects.filter(
            openid=self.request.auth.openid, asn_code=data['asn_code'], is_delete=False
        )
        for k in range(len(check_data_qs)):
            res_check_data = check_data_qs.filter(goods_code=check_data_qs[k].goods_code)
            if res_check_data.count() > 1:
                combine_qty = []
                conbine_cost = []
                for z in range(len(res_check_data)):
                    combine_qty.append(res_check_data[z].goods_qty)
                    conbine_cost.append(res_check_data[z].goods_cost)
                    res_check_data[z].delete()
                AsnDetailModel.objects.create(
                    openid=self.request.auth.openid,
                    asn_code=str(data['asn_code']),
                    customer=str(data['customer']),
                    goods_code=str(check_data_qs[k].goods_code),
                    goods_desc=str(check_data_qs[k].goods_desc),
                    goods_qty=sumOfList(combine_qty, len(combine_qty)),
                    goods_cost=sumOfList(conbine_cost, len(conbine_cost)),
                    asn_status=3,
                    creator=str(staff_name)
                )

        # 更新 ASN 汇总成本（与原实现一致）
        total_cost = Decimal(str(sumOfList(cost_list, len(cost_list)))) + fees_sum

        AsnListModel.objects.filter(
            openid=self.request.auth.openid, asn_code=str(data['asn_code'])
        ).update(
            customer=str(data['customer']),
            total_cost=total_cost
        )
        # 主表状态强制为 3，确保与明细/库存一致（跳过到预分拣）
        AsnListModel.objects.filter(
            openid=self.request.auth.openid,
            asn_code=str(data['asn_code'])
        ).update(asn_status=3,
                 customer=str(data['customer']),
                 total_cost=float(total_cost),
                 customer_other_fees=customer_other_fees
                 )
        return Response({"detail": "success"}, status=200)


# ==================================================
# 跳过版：更新 ASN 明细（保持状态=3，库存维持在 pre_sort）
# ==================================================
class SkipAsnDetailUpdateViewSet(AsnDetailViewSet):
    """
    PUT /asn_detail/skip_update/
    作用：重建 ASN 明细到状态 3：
         1）先把该 asn_code 现有未删明细删除，并回滚其对 pre_sort_stock / goods_qty 的影响；
         2）再按请求数据重建明细，并将库存重新计入 pre_sort_stock；
         3）不要求 ASN 处于状态 1（与原 update 的限制不同）。
    """
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        data = self.request.data
        customer_other_fees = data.get('customer_other_fees', {})
        fees_sum = self._sum_customer_other_fees(customer_other_fees)  # 复用父类里的工具函数

        # 仍做基本校验
        if not AsnListModel.objects.filter(
            openid=self.request.auth.openid, asn_code=str(data['asn_code']), is_delete=False
        ).exists():
            raise APIException({"detail": "ASN Code does not exists"})
        if not customer.objects.filter(
            openid=self.request.auth.openid, customer_name=str(data['customer']), is_delete=False
        ).exists():
            raise APIException({"detail": "Customer does not exists"})

        operator = self.request.META.get('HTTP_OPERATOR')
        staff_name = staff.objects.filter(
            openid=self.request.auth.openid, id=operator
        ).first().staff_name

        # 【改动点-A】加事务：保证“回滚库存/删旧 → 写新 → 合并覆盖 → 回写主表”原子性
        with transaction.atomic():
            # ---- 1) 回滚并“软删”旧明细（你原有逻辑保留）----
            old_details = AsnDetailModel.objects.filter(
                openid=self.request.auth.openid, asn_code=str(data['asn_code']), is_delete=False
            )
            for item in old_details:
                stock_item = stocklist.objects.filter(
                    openid=self.request.auth.openid, goods_code=str(item.goods_code)
                ).first()
                if stock_item:
                    stock_item.goods_qty = max(0, stock_item.goods_qty - item.goods_qty)
                    stock_item.pre_sort_stock = max(0, stock_item.pre_sort_stock - item.goods_qty)
                    stock_item.save()
            old_details.update(is_delete=True)


        # 逐条校验新数据（与原 update 一致的校验逻辑）
        for i in range(len(data['goods_code'])):
            check_data = {
                'openid': self.request.auth.openid,
                'asn_code': str(data['asn_code']),
                'customer': str(data['customer']),
                'goods_code': str(data['goods_code'][i]),
                'goods_qty': int(data['goods_qty'][i]),
                'creator': str(staff_name),

            }
            serializer = serializers.ASNDetailUpdateSerializer(data=check_data)
            serializer.is_valid(raise_exception=True)

        post_data_list = []
        cost_list = []

        # 重新累加到 pre_sort_stock
        for j in range(len(data['goods_code'])):
            gcode = str(data['goods_code'][j])
            gqty = int(data['goods_qty'][j])

            goods_detail = goods.objects.filter(
                openid=self.request.auth.openid, goods_code=gcode, is_delete=False
            ).first()
            goods_cost = round(goods_detail.goods_cost * gqty, 2)

            if stocklist.objects.filter(openid=self.request.auth.openid, goods_code=gcode).exists():
                goods_qty_change = stocklist.objects.filter(
                    openid=self.request.auth.openid, goods_code=gcode
                ).first()
                goods_qty_change.goods_qty = goods_qty_change.goods_qty + gqty
                goods_qty_change.pre_sort_stock = goods_qty_change.pre_sort_stock + gqty
                goods_qty_change.save()
            else:
                stocklist.objects.create(
                    openid=self.request.auth.openid,
                    goods_code=gcode,
                    goods_desc=goods_detail.goods_desc,
                    goods_qty=gqty,
                    pre_sort_stock=gqty
                )

            post_data = AsnDetailModel(
                openid=self.request.auth.openid,
                asn_code=str(data['asn_code']),
                customer=str(data['customer']),
                goods_code=gcode,
                goods_desc=str(goods_detail.goods_desc),
                goods_qty=gqty,
                goods_cost=goods_cost,
                asn_status=3,
                creator=str(staff_name),
                customer_other_fees=customer_other_fees

            )
            post_data_list.append(post_data)
            cost_list.append(goods_cost)

        AsnDetailModel.objects.bulk_create(post_data_list, batch_size=100)

        # 合并相同 goods_code（与原先一致）
        current_rows = list(AsnDetailModel.objects.filter(
            openid=self.request.auth.openid, asn_code=str(data['asn_code']), is_delete=False
        ))
        # 用字典聚合，累加 qty / cost
        merged = {}
        for row in current_rows:
            key = row.goods_code
            if key not in merged:
                merged[key] = {
                    "goods_desc": row.goods_desc,
                    "qty_sum": 0,
                    "cost_sum": Decimal('0'),
                }
            merged[key]["qty_sum"] += int(row.goods_qty)
            merged[key]["cost_sum"] += Decimal(str(row.goods_cost))

        # “覆盖”语义：先删当前 asn 的有效明细，再以合并结果重建一条/货品
        AsnDetailModel.objects.filter(
            openid=self.request.auth.openid, asn_code=str(data['asn_code']), is_delete=False
        ).delete()

        merged_rows = []
        for gcode, agg in merged.items():
            merged_rows.append(AsnDetailModel(
                openid=self.request.auth.openid,
                asn_code=str(data['asn_code']),
                customer=str(data['customer']),
                goods_code=str(gcode),
                goods_desc=str(agg["goods_desc"]),
                goods_qty=int(agg["qty_sum"]),
                goods_cost=float(agg["cost_sum"]),
                asn_status=3,
                creator=str(staff_name),
                customer_other_fees=customer_other_fees
            ))
        if merged_rows:
            AsnDetailModel.objects.bulk_create(merged_rows, batch_size=100)

        # ---- 5) 统一计算并回写主表 total_cost（只执行一次）----
        # 【改动点-C】把 total_cost 的计算与回写从“去重循环内部”移到“循环之后”，避免漏更新/多次更新
        total_cost = Decimal(str(sumOfList(cost_list, len(cost_list)))) + fees_sum

        AsnListModel.objects.filter(
            openid=self.request.auth.openid,
            asn_code=str(data['asn_code'])
        ).update(
            asn_status=3,
            customer=str(data['customer']),
            customer_other_fees=customer_other_fees,  # 回写 JSON 以便前端/报表直接读取
            total_cost=total_cost
        )

        # ---- 6) 返回：你要求把 total_cost 返回给前端 ----
        # 【改动点-D】响应体中附带 total_cost

        return Response({"detail": "success", "total_cost": str(total_cost)}, status=status.HTTP_200_OK)