# CSV 导出渲染器：固定列头，支持中英列名
# refrigeration_fee_details/files.py
from rest_framework_csv.renderers import CSVStreamingRenderer

def file_headers():
    return [
        'ship_receive_time',
        'total_pallet_qty',
        'refrigeration_fee',
        'creator',
        'create_time',
        'update_time',
    ]

def cn_headers():
    return dict([
        ('ship_receive_time', '发货/收货日期'),
        ('total_pallet_qty', '当日期末在库量'),
        ('refrigeration_fee', '冷藏费'),
        ('creator', '创建人'),
        ('create_time', '创建时间'),
        ('update_time', '更新时间'),
    ])

def en_headers():
    return dict([
        ('ship_receive_time', 'Ship/Receive Day'),
        ('total_pallet_qty', 'End-of-Day Stock'),
        ('refrigeration_fee', 'Refrigeration Fee'),
        ('creator', 'Creator'),
        ('create_time', 'Create Time'),
        ('update_time', 'Update Time'),
    ])

class RefrigerationFileRenderCN(CSVStreamingRenderer):
    header = file_headers()
    labels = cn_headers()

class RefrigerationFileRenderEN(CSVStreamingRenderer):
    header = file_headers()
    labels = en_headers()

def agg_file_headers():
    """
    聚合导出列顺序（固定）：
    - openid：明确作用域，便于多租户导出审计
    - period：周期（按 granularity 截断后的日期；例如月/季）
    - total_fee：该期费用合计（Sum of daily fee）
    - end_stock：该期期末在库量（取该期最后一天的库存）
    """
    return [
        'period',
        'total_fee',
        'end_stock',
    ]

def agg_cn_headers():
    """
    聚合中文列名
    """
    return dict([
        ('period', '周期'),
        ('total_fee', '期间费用合计'),
        ('end_stock', '期间期末在库量'),
    ])

def agg_en_headers():
    """
    聚合英文列名
    """
    return dict([
        ('period', 'Period'),
        ('total_fee', 'Total Fee'),
        ('end_stock', 'End-of-Period Stock'),
    ])

class RefrigerationAggFileRenderCN(CSVStreamingRenderer):
    header = agg_file_headers()
    labels = agg_cn_headers()

class RefrigerationAggFileRenderEN(CSVStreamingRenderer):
    header = agg_file_headers()
    labels = agg_en_headers()
