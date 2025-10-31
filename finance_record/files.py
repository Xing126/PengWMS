# finance_record/files.py
from rest_framework_csv.renderers import CSVStreamingRenderer

def file_headers():
    """
    Define the exact CSV column order for export.
    """
    return [
        'asn_dn_code',
        'source_type',
        'openid', 
        'customer_name',
        'customer_bank_account',
        'stretch_wrapped_pallet_qty',
        'total_pallet_qty',
        'customer_refrigeration_fee',
        'customer_film_laminating_fee',
        'customer_loading_fee',
        'customer_other_fee',
        'total_fee',
        'ship_receive_time',
        'creator',
        'create_time',
        'update_time',
    ]

def cn_data_header():
    """
    Chinese column display names.
    """
    return dict([
        ('asn_dn_code', u'单据编号（ASN/DN）'),
        ('source_type', u'来源类型'),
        ('openid', u'OpenID'),
        ('customer_name', u'客户名称'),
        ('customer_bank_account', u'客户银行账号'),
        ('stretch_wrapped_pallet_qty', u'围膜库板数'),
        ('total_pallet_qty', u'总库板数'),
        ('customer_refrigeration_fee', u'冷藏费'),
        ('customer_film_laminating_fee', u'围膜费'),
        ('customer_loading_fee', u'装卸费'),
        ('customer_other_fee', u'其他费用'),
        ('total_fee', u'总计费用'),
        ('ship_receive_time', u'发货/收货时间'),
        ('creator', u'创建人'),
        ('create_time', u'创建时间'),
        ('update_time', u'更新时间'),
    ])

def en_data_header():
    """
    English column display names.
    """
    return dict([
        ('asn_dn_code', u'ASN/DN Code'),
        ('source_type', u'Source Type'),
        ('openid', u'OpenID'),
        ('customer_name', u'Customer Name'),
        ('customer_bank_account', u'Customer Bank Account'),
        ('stretch_wrapped_pallet_qty', u'Stretch Wrapped Pallet Qty'),
        ('total_pallet_qty', u'Total Pallet Qty'),
        ('customer_refrigeration_fee', u'Refrigeration Fee'),
        ('customer_film_laminating_fee', u'Film-Laminating Fee'),
        ('customer_loading_fee', u'Loading Fee'),
        ('customer_other_fee', u'Other Fee'),
        ('total_fee', u'Total Fee'),
        ('ship_receive_time', u'Ship/Receive Time'),
        ('creator', u'Creator'),
        ('create_time', u'Create Time'),
        ('update_time', u'Update Time'),
    ])

class FinancefileRenderCN(CSVStreamingRenderer):
    header = file_headers()
    labels = cn_data_header()

class FinancefileRenderEN(CSVStreamingRenderer):
    header = file_headers()
    labels = en_data_header()
