from django.contrib import admin
from unfold.admin import ModelAdmin

from core.models import AppSettings, City, School


@admin.register(AppSettings)
class AppSettingsAdmin(ModelAdmin):
    list_display = [
        'free_mode_enabled',
        'free_daily_tasks_limit',
        'free_ai_explanations_enabled',
        'daily_session_tasks_count',
        'max_daily_xp',
        'web_app_url',
        'updated_at',
    ]
    fields = [
        'web_app_url',
        'welcome_message',
        'free_mode_enabled',
        'free_daily_tasks_limit',
        'free_ai_explanations_enabled',
        'pro_ai_explanations_enabled',
        'daily_session_tasks_count',
        'weak_topic_task_ratio',
        'xp_per_correct_answer',
        'streak_bonus_xp',
        'max_daily_xp',
    ]

    def has_add_permission(self, request):
        return not AppSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(City)
class CityAdmin(ModelAdmin):
    list_display = ['name', 'region', 'is_active']
    list_filter = ['is_active', 'region']
    search_fields = ['name']


@admin.register(School)
class SchoolAdmin(ModelAdmin):
    list_display = ['name', 'city', 'is_active']
    list_filter = ['is_active', 'city']
    search_fields = ['name', 'city__name']
    autocomplete_fields = ['city']
