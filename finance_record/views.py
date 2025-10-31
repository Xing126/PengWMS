# finance_record/views.py
from django.http import StreamingHttpResponse
from rest_framework import viewsets
from rest_framework.settings import api_settings
from rest_framework.response import Response

from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from finance_record.models import FinanceRecord
from finance_record import serializers
from utils.page import MyPageNumberPagination

# Filter: mirror the original file's pattern
from .filter import FinanceRecordFilter

# CSV renderers (implemented in finance_record/files.py)
from .files import FinancefileRenderCN, FinancefileRenderEN


class FinanceRecordViewSet(viewsets.ModelViewSet):
    """
        retrieve:
            Response a data list（get）

        list:
            Response a data list（all）

        create:
            (Not allowed) — Read-only business

        delete:
            (Not allowed) — Read-only business

        partial_update:
            (Not allowed) — Read-only business

        update:
            (Not allowed) — Read-only business
    """
    pagination_class = MyPageNumberPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ['id', "create_time", "update_time"]
    filter_class = FinanceRecordFilter
    http_method_names = ['get', 'head', 'options']

    def get_project(self):
        try:
            return self.kwargs.get('pk')
        except Exception:
            return None

    def get_queryset(self):
        obj_id = self.get_project()
        if self.request.user:
            if obj_id is None:
                return FinanceRecord.objects.filter(
                    openid=self.request.auth.openid, is_delete=False
                ).order_by('-update_time')
            else:
                return FinanceRecord.objects.filter(
                    openid=self.request.auth.openid, id=obj_id, is_delete=False
                ).order_by('-update_time')
        else:
            return FinanceRecord.objects.none()

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return serializers.FinanceRecordSerializer
        else:
            return self.http_method_not_allowed(request=self.request)


class FinancefileDownloadView(viewsets.ModelViewSet):
    """
    CSV download view:
    - Follows the original renderer pattern (language-aware)
    - Only 'list' is allowed; uses export serializer (includes bank account)
    """
    renderer_classes = (FinancefileRenderCN,) + tuple(api_settings.DEFAULT_RENDERER_CLASSES)
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ['id', "create_time", "update_time"]
    filter_class = FinanceRecordFilter
    http_method_names = ['get', 'head', 'options']

    def get_project(self):
        try:
            return self.kwargs.get('pk')
        except Exception:
            return None

    def get_queryset(self):
        obj_id = self.get_project()
        if self.request.user:
            if obj_id is None:
                return FinanceRecord.objects.filter(
                    openid=self.request.auth.openid, is_delete=False
                ).order_by('-update_time')
            else:
                return FinanceRecord.objects.filter(
                    openid=self.request.auth.openid, id=obj_id, is_delete=False
                ).order_by('-update_time')
        else:
            return FinanceRecord.objects.none()

    def get_serializer_class(self):
        if self.action in ['list']:
            return serializers.FinanceRecordExportSerializer
        else:
            return self.http_method_not_allowed(request=self.request)

    def get_lang(self, data_iterable):
        lang = self.request.META.get('HTTP_LANGUAGE')
        if lang:
            if lang == 'zh-hans':
                return FinancefileRenderCN().render(data_iterable)
            else:
                return FinancefileRenderEN().render(data_iterable)
        else:
            return FinancefileRenderEN().render(data_iterable)

    def list(self, request, *args, **kwargs):
        from datetime import datetime
        dt = datetime.now()
        data = (
            self.get_serializer(instance).data
            for instance in self.filter_queryset(self.get_queryset())
        )
        renderer = self.get_lang(data)
        response = StreamingHttpResponse(renderer, content_type="text/csv")
        response['Content-Disposition'] = "attachment; filename='finance_{}.csv'".format(
            str(dt.strftime('%Y%m%d%H%M%S%f'))
        )
        return response



