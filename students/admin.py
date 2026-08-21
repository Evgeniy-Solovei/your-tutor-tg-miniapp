from django.contrib import admin
from import_export.admin import ExportActionMixin
from unfold.admin import ModelAdmin

from students.models import Parent, ParentChildLink, ParentInvite, PaymentOrder, Student


@admin.register(Student)
class StudentAdmin(ExportActionMixin, ModelAdmin):
    list_display = [
        'display_name',
        'tg_id',
        'grade',
        'subject',
        'exam_track',
        'city',
        'is_pro',
        'xp',
        'streak_days',
        'registration_completed',
    ]
    list_filter = [
        'is_pro',
        'registration_completed',
        'grade',
        'goal',
        'subject',
        'city',
    ]
    search_fields = ['display_name', 'tg_id', 'username']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Parent)
class ParentAdmin(ModelAdmin):
    list_display = ['display_name', 'tg_id', 'username', 'created_at']
    search_fields = ['display_name', 'tg_id', 'username']


@admin.register(ParentInvite)
class ParentInviteAdmin(ModelAdmin):
    list_display = ['code', 'student', 'is_active', 'expires_at', 'created_at']
    list_filter = ['is_active']
    search_fields = ['code', 'student__display_name']


@admin.register(ParentChildLink)
class ParentChildLinkAdmin(ModelAdmin):
    list_display = ['parent', 'student', 'notify_weekly', 'linked_at']
    list_filter = ['notify_weekly']
    search_fields = ['parent__tg_id', 'student__display_name']


@admin.register(PaymentOrder)
class PaymentOrderAdmin(ModelAdmin):
    list_display = ['order_id', 'student', 'plan_code', 'amount_byn', 'days', 'status', 'created_at', 'paid_at']
    list_filter = ['status', 'plan_code', 'created_at']
    search_fields = ['order_id', 'student__display_name', 'student__tg_id', 'bepaid_token']
    readonly_fields = ['order_id', 'created_at', 'paid_at', 'bepaid_token', 'bepaid_checkout_url']
