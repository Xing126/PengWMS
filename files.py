from rest_framework_csv.renderers import CSVStreamingRenderer


# ---------------- 头表导出 ----------------
def list_file_headers():
    return [
        'dn_code',
        'dn_status',
        'other_fees',       # ✅ 新增其他费用字段
        'customer',
        'creater',
        'create_time',
        'update_time'
    ]


def list_cn_data_header():
    return dict([
        ('dn_code', u'发货单单号'),
        ('dn_status', u'发货单状态'),
        ('other_fees', u'其他费用'),
        ('customer', u'客户'),
        ('creater', u'创建人'),
        ('create_time', u'创建时间'),
        ('update_time', u'更新时间')
    ])


def list_en_data_header():
    return dict([
        ('dn_code', u'DN Code'),
        ('dn_status', u'DN Status'),
        ('other_fees', u'Other Fees'),
        ('customer', u'Customer'),
        ('creater', u'Creator'),
        ('create_time', u'Create Time'),
        ('update_time', u'Update Time')
    ])


# ---------------- 明细导出 ----------------
def detail_file_headers():
    return [
        'dn_code',
        'dn_status',
        'goods_code',
        'goods_desc',
        'goods_qty',
        'pick_qty',
        'picked_qty',
        'intransit_qty',
        'delivery_actual_qty',
        'delivery_shortage_qty',
        'delivery_more_qty',
        'delivery_damage_qty',
        'customer',
        'creater',
        'create_time',
        'update_time'
    ]


def detail_cn_data_header():
    return dict([
        ('dn_code', u'发货单单号'),
        ('dn_status', u'发货单状态'),
        ('goods_code', u'货品编号'),
        ('goods_desc', u'货品描述'),
        ('goods_qty', u'订单数量'),
        ('pick_qty', u'计划拣货数量'),
        ('picked_qty', u'已拣货数量'),
        ('intransit_qty', u'在途数量'),
        ('delivery_actual_qty', u'实际到货数量'),
        ('delivery_shortage_qty', u'短少数量'),
        ('delivery_more_qty', u'多到数量'),
        ('delivery_damage_qty', u'破损数量'),
        ('customer', u'客户'),
        ('creater', u'创建人'),
        ('create_time', u'创建时间'),
        ('update_time', u'更新时间')
    ])


def detail_en_data_header():
    return dict([
        ('dn_code', u'DN Code'),
        ('dn_status', u'DN Status'),
        ('goods_code', u'Goods Code'),
        ('goods_desc', u'Goods Description'),
        ('goods_qty', u'Goods Qty'),
        ('pick_qty', u'Pick Qty'),
        ('picked_qty', u'Picked Qty'),
        ('intransit_qty', u'Intransit Qty'),
        ('delivery_actual_qty', u'Delivery Actual Qty'),
        ('delivery_shortage_qty', u'Delivery Shortage Qty'),
        ('delivery_more_qty', u'Delivery More Qty'),
        ('delivery_damage_qty', u'Delivery Damage Qty'),
        ('customer', u'Customer'),
        ('creater', u'Creator'),
        ('create_time', u'Create Time'),
        ('update_time', u'Update Time')
    ])


# ---------------- 渲染器类 ----------------
class FileListRenderCN(CSVStreamingRenderer):
    header = list_file_headers()
    labels = list_cn_data_header()


class FileListRenderEN(CSVStreamingRenderer):
    header = list_file_headers()
    labels = list_en_data_header()


class FileDetailRenderCN(CSVStreamingRenderer):
    header = detail_file_headers()
    labels = detail_cn_data_header()


class FileDetailRenderEN(CSVStreamingRenderer):
    header = detail_file_headers()
    labels = detail_en_data_header()
