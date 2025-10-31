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
        'customer_bank_account',
        'customer_refrigeration_fee',
        'customer_film_laminating_fee',
        'customer_loading_fee',
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
        ('customer_bank_account', u'客户银行账号'),
        ('customer_refrigeration_fee', u'冷藏费'),
        ('customer_film_laminating_fee', u'围膜费'),
        ('customer_loading_fee', u'装卸费'),
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
        ('customer_bank_account', u'Customer Bank Account'),
        ('customer_refrigeration_fee', u'Refrigeration Fee'),
        ('customer_film_laminating_fee', u'Film-Laminating Fee'),
        ('customer_loading_fee', u'Loading Fee'),
        ('create_time', u'Create Time'),
        ('update_time', u'Update Time'),
    ])

class FinancefileRenderCN(CSVStreamingRenderer):
    header = file_headers()
    labels = cn_data_header()

class FinancefileRenderEN(CSVStreamingRenderer):
    header = file_headers()
    labels = en_data_header()
