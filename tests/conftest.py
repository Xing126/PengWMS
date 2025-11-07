# tests/conftest.py
import pytest
from django.db import connection, models

def _table_exists(name: str) -> bool:
    with connection.cursor() as cursor:
        return name in connection.introspection.table_names(cursor)

@pytest.fixture(autouse=True, scope='session')
def ensure_refrigeration_fee_detail_table(django_db_setup, django_db_blocker):
    """
    兼容你之前的冷藏费测试：确保 refrigeration_fee_details 的模型表存在。
    如果此处创建，则在会话结束时清理；如果原本就有，则不动。
    """
    from refrigeration_fee_details.models import RefrigerationFeeDetail

    table_name = RefrigerationFeeDetail._meta.db_table  # 默认 'refrigeration_fee_details'
    created = False

    with django_db_blocker.unblock():
        if not _table_exists(table_name):
            with connection.schema_editor() as se:
                se.create_model(RefrigerationFeeDetail)
            created = True

    try:
        yield
    finally:
        if created:
            with django_db_blocker.unblock():
                with connection.schema_editor() as se:
                    se.delete_model(RefrigerationFeeDetail)


def make_model(name, fields, app_label, db_table):
    """
    生成测试用模型类（不与正式 app/表冲突）：
    - 独立 app_label（tests_*）
    - 独立测试表名（test_*）
    - managed=True
    """
    Meta = type("Meta", (), {
        "app_label": app_label,
        "db_table": db_table,
        "managed": True,
    })
    attrs = {"__module__": __name__, "Meta": Meta}
    attrs.update(fields)
    return type(name, (models.Model,), attrs)


@pytest.fixture(scope='session')
def stub_models(django_db_setup, django_db_blocker):
    """
    提供 3 个测试模型类，既能满足冷藏费，也能满足 finance_record：
      - ASN 测试表：包含 asn_code、两类数量（围膜/总）、receive_time、openid/is_delete
      - DN  测试表：包含 dn_code、customer、两类数量、ship_time、openid/is_delete
      - Customer 测试表：包含客户名、银行账号、围膜/装卸单价、冷藏单价，以及 openid/is_delete

    冷藏费测试会用到：
      - ASN: receive_time / asn_total_pallet_qty
      - DN : ship_time  / dn_total_pallet_qty
      - Customer: customer_refrigeration_fee

    finance_record 会用到：
      - ASN: asn_code + (stretch_wrapped_pallet_qty, total_pallet_qty)
      - DN : dn_code, customer + (stretch_wrapped_pallet_qty, total_pallet_qty)
      - Customer: customer_name, customer_bank_account,
                  customer_film_laminating_fee, customer_loading_fee
    """
    ASN_TABLE = 'test_asn_list'
    DN_TABLE = 'test_dn_list'
    CUSTOMER_TABLE = 'test_customer_list'

    TestAsnListModel = make_model(
        'TestAsnListModel',
        dict(
            # 通用标识
            openid=models.CharField(max_length=255, db_index=True),
            is_delete=models.BooleanField(default=False),

            # 冷藏费用：接收时间
            receive_time=models.DateTimeField(null=True, blank=True),

            # finance_record：单号 + 两类数量
            asn_code=models.CharField(max_length=255, db_index=True, default=''),
            asn_stretch_wrapped_pallet_qty=models.IntegerField(default=0),
            asn_total_pallet_qty=models.IntegerField(default=0),
            stretch_wrapped_pallet_qty=models.IntegerField(default=0),
            total_pallet_qty=models.IntegerField(default=0),
        ),
        app_label='tests_asn',
        db_table=ASN_TABLE,
    )

    TestDnListModel = make_model(
        'TestDnListModel',
        dict(
            # 通用标识
            openid=models.CharField(max_length=255, db_index=True),
            is_delete=models.BooleanField(default=False),

            # 冷藏费用：发货时间
            ship_time=models.DateTimeField(null=True, blank=True),

            # finance_record：单号 + 客户 + 两类数量
            dn_code=models.CharField(max_length=255, db_index=True, default=''),
            customer=models.CharField(max_length=255, default=''),
            dn_stretch_wrapped_pallet_qty=models.IntegerField(default=0),
            dn_total_pallet_qty=models.IntegerField(default=0),
            stretch_wrapped_pallet_qty=models.IntegerField(default=0),
            total_pallet_qty=models.IntegerField(default=0),

        ),
        app_label='tests_dn',
        db_table=DN_TABLE,
    )

    TestCustomerModel = make_model(
        'TestCustomerModel',
        dict(
            # 通用标识
            openid=models.CharField(max_length=255, db_index=True),
            is_delete=models.BooleanField(default=False),

            # 冷藏费用：冷藏单价
            customer_refrigeration_fee=models.DecimalField(max_digits=12, decimal_places=2, default=0),

            # finance_record：客户名 / 银行账号 / 两项单价
            customer_name=models.CharField(max_length=255, db_index=True, default=''),
            customer_bank_account=models.CharField(max_length=255, default=''),
            customer_film_laminating_fee=models.DecimalField(max_digits=12, decimal_places=2, default=0),
            customer_loading_fee=models.DecimalField(max_digits=12, decimal_places=2, default=0),
        ),
        app_label='tests_customer',
        db_table=CUSTOMER_TABLE,
    )

    created = {ASN_TABLE: False, DN_TABLE: False, CUSTOMER_TABLE: False}
    with django_db_blocker.unblock():
        with connection.schema_editor() as se:
            if not _table_exists(ASN_TABLE):
                se.create_model(TestAsnListModel)
                created[ASN_TABLE] = True
            if not _table_exists(DN_TABLE):
                se.create_model(TestDnListModel)
                created[DN_TABLE] = True
            if not _table_exists(CUSTOMER_TABLE):
                se.create_model(TestCustomerModel)
                created[CUSTOMER_TABLE] = True

    try:
        yield TestAsnListModel, TestDnListModel, TestCustomerModel
    finally:
        with django_db_blocker.unblock():
            with connection.schema_editor() as se:
                if created[ASN_TABLE]:
                    se.delete_model(TestAsnListModel)
                if created[DN_TABLE]:
                    se.delete_model(TestDnListModel)
                if created[CUSTOMER_TABLE]:
                    se.delete_model(TestCustomerModel)


@pytest.fixture(autouse=True)
def _patch_models_everywhere(monkeypatch, stub_models):
    """
    继续沿用你的“全局打补丁”策略：
    1) 给冷藏费服务模块（refrigeration_fee_service）直接替换模块内引用；
    2) 覆盖 django.apps.apps.get_model，使任何 ('asn','AsnListModel') / ('dn','DnListModel')
       / ('customer','ListModel') 的动态获取都落到我们的测试表上。
    这样既能跑冷藏费，也能跑 finance_record 的 models/save、views/export、command 等逻辑。
    """
    Asn, Dn, Customer = stub_models

    # 1) 替换冷藏费服务里的直接引用（如果存在）
    try:
        import refrigeration_fee_details.utils.refrigeration_fee_service as svc
        monkeypatch.setattr(svc, 'AsnListModel', Asn, raising=False)
        monkeypatch.setattr(svc, 'DnListModel', Dn, raising=False)
        # 尽量覆盖“客户模型”的不同命名
        monkeypatch.setattr(svc, 'Customer', Customer, raising=False)
        monkeypatch.setattr(svc, 'CustomerModel', Customer, raising=False)
        monkeypatch.setattr(svc, 'ListModel', Customer, raising=False)
    except Exception:
        # 如果该模块不存在或路径不同，忽略即可
        pass

    # 2) 覆盖 apps.get_model，确保任何动态获取都返回测试模型（finance_record 依赖这一点）
    from django.apps import apps as _apps
    orig_get_model = _apps.get_model

    def _patched_get_model(app_label, model_name, require_ready=True):
        key = (app_label.lower(), model_name.lower())
        if key == ('asn', 'asnlistmodel'):
            return Asn
        if key == ('dn', 'dnlistmodel'):
            return Dn
        if key in {('customer', 'listmodel'), ('customer', 'customermodel')}:
            return Customer
        return orig_get_model(app_label, model_name, require_ready=require_ready)

    monkeypatch.setattr(_apps, 'get_model', _patched_get_model, raising=True)



