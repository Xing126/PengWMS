from django.test import TestCase
from rest_framework.test import APIRequestFactory, APIClient
from django.contrib.auth.models import User
from goods.views import APIViewSet
from customer.models import ListModel as Customer
from goods.models import ListModel as Goods
from userprofile.models import Users


class DummyAuth:
    def __init__(self, openid: str):
        self.openid = openid


class GoodsApiTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.client = APIClient()
        self.view = APIViewSet.as_view({'post': 'create', 'put': 'update', 'patch': 'partial_update'})
        self.user = User.objects.create(username='tester')
        self.openid = 'test_openid'
        Users.objects.create(user_id=1, name='tester', vip=1, openid=self.openid, appid='app', is_delete=False,
                             developer=True, t_code='t', ip='127.0.0.1', link_to=False, link_to_id=0)
        Customer.objects.create(customer_name='客户A', customer_city='x', customer_address='x',
                                customer_contact='x', customer_manager='x', customer_level=1,
                                creater='tester', openid=self.openid, is_delete=False)

    def _auth_request(self, request):
        request.user = self.user
        request.auth = DummyAuth(self.openid)

    # 注意：直接调用视图会绕过渲染管线，使用 APIClient 验证端到端

    def test_api_client_create(self):
        payload = {
            'goods_code': 'G011',
            'goods_desc': '测试商品11',
            'goods_supplier': '客户A',
            'creater': 'tester'
        }
        resp = self.client.post('/goods/', payload, format='json', **{'HTTP_TOKEN': self.openid})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Goods.objects.filter(goods_code='G011').exists())

    def test_serializer_create_minimal(self):
        from goods.serializers import GoodsPostSerializer
        data = {
            'openid': self.openid,
            'goods_code': 'G010',
            'goods_desc': '测试商品10',
            'goods_supplier': '客户A',
            'goods_weight': 0,
            'goods_w': 0,
            'goods_d': 0,
            'goods_h': 0,
            'unit_volume': 0,
            'goods_unit': '',
            'goods_class': '',
            'goods_brand': '',
            'goods_color': '',
            'goods_shape': '',
            'goods_specs': '',
            'goods_origin': '',
            'goods_cost': 0,
            'goods_price': 0,
            'creater': 'tester',
            'bar_code': 'bar_G010'
        }
        ser = GoodsPostSerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)
        obj = ser.save()
        self.assertEqual(obj.goods_code, 'G010')

    def test_update_minimal_fields(self):
        g = Goods.objects.create(
            goods_code='G002', goods_desc='初始商品', goods_supplier='客户A', goods_weight=0,
            goods_w=0, goods_d=0, goods_h=0, unit_volume=0,
            goods_unit='', goods_class='', goods_brand='', goods_color='', goods_shape='', goods_specs='', goods_origin='',
            goods_cost=0, goods_price=0, creater='tester', bar_code='bar_G002', openid=self.openid, is_delete=False
        )
        payload = {
            'goods_code': 'G002',
            'goods_desc': '更新商品',
            'goods_supplier': '客户A',
            'creater': 'tester'
        }
        request = self.factory.put(f'/goods/{g.id}/', payload, format='json')
        self._auth_request(request)
        response = self.view(request, pk=g.id)
        self.assertEqual(response.status_code, 200)

    def test_partial_update_optional_fields(self):
        g = Goods.objects.create(
            goods_code='G003', goods_desc='初始商品', goods_supplier='客户A', goods_weight=1,
            goods_w=1, goods_d=1, goods_h=1, unit_volume=0.000000001,
            goods_unit='U', goods_class='C', goods_brand='B', goods_color='COL', goods_shape='S', goods_specs='SP', goods_origin='O',
            goods_cost=1, goods_price=1, creater='tester', bar_code='bar_G003', openid=self.openid, is_delete=False
        )
        payload = {
            'goods_desc': '局部更新',
        }
        request = self.factory.patch(f'/goods/{g.id}/', payload, format='json')
        self._auth_request(request)
        response = self.view(request, pk=g.id)
        self.assertEqual(response.status_code, 200)
