from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from learning.models import (
    AIExplanationLog,
    DailySession,
    LeagueEntry,
    SessionTask,
    StudentVariantProgress,
    TaskAttempt,
    TopicMastery,
    WeeklyLeague,
)


class SessionTaskInline(TabularInline):
    model = SessionTask
    extra = 0
    readonly_fields = ['task', 'purpose', 'order', 'is_answered']


@admin.register(DailySession)
class DailySessionAdmin(ModelAdmin):
    list_select_related = ['student']
    list_display = [
        'student',
        'session_date',
        'kind',
        'status',
        'tasks_completed',
        'tasks_total',
        'primary_score',
        'max_primary',
        'test_score',
        'xp_earned',
    ]
    list_filter = ['kind', 'status', 'session_date']
    search_fields = ['student__display_name', 'student__tg_id']
    inlines = [SessionTaskInline]


@admin.register(StudentVariantProgress)
class StudentVariantProgressAdmin(ModelAdmin):
    list_select_related = ['student', 'variant', 'variant__collection']
    list_display = [
        'student',
        'variant',
        'status',
        'score_percent',
        'correct_count',
        'wrong_count',
        'completed_at',
    ]
    list_filter = ['status', 'variant__collection']
    search_fields = ['student__display_name', 'variant__title']



@admin.register(TaskAttempt)
class TaskAttemptAdmin(ModelAdmin):
    list_select_related = ['student', 'task']
    list_display = [
        'student',
        'task',
        'is_correct',
        'points_earned',
        'max_points',
        'created_at',
    ]
    list_filter = ['is_correct', 'created_at']
    search_fields = ['student__display_name', 'task__question']


@admin.register(TopicMastery)
class TopicMasteryAdmin(ModelAdmin):
    list_select_related = ['student', 'topic']
    list_display = ['student', 'topic', 'mastery_score', 'correct_count', 'wrong_count', 'last_attempt_at']
    list_filter = ['topic__section__exam_track']
    search_fields = ['student__display_name', 'topic__name']


@admin.register(AIExplanationLog)
class AIExplanationLogAdmin(ModelAdmin):
    list_display = ['attempt', 'model_name', 'created_at']
    list_filter = ['model_name', 'created_at']
    readonly_fields = ['attempt', 'prompt_context', 'ai_response', 'model_name', 'created_at']


class LeagueEntryInline(TabularInline):
    model = LeagueEntry
    extra = 0
    readonly_fields = ['student', 'test_score', 'primary_score', 'weekly_xp', 'rank']
    fields = ['student', 'test_score', 'primary_score', 'weekly_xp', 'rank']
    ordering = ['-test_score', '-primary_score', '-weekly_xp']


@admin.register(WeeklyLeague)
class WeeklyLeagueAdmin(ModelAdmin):
    list_display = ['title', 'period_type', 'week_start', 'week_end', 'is_active', 'prize_first_place']
    list_filter = ['period_type', 'is_active']
    search_fields = ['title', 'prize_first_place', 'prizes_text']
    fieldsets = (
        (None, {
            'fields': ('title', 'period_type', 'week_start', 'week_end', 'is_active')
        }),
        ('🏆 Призы и подарки для учеников (Оставьте пустыми, если призов нет)', {
            'fields': ('prize_first_place', 'prize_second_place', 'prize_third_place', 'prizes_text'),
            'description': 'Если заполнить призы, они автоматически покажутся вверху таблицы лидеров.'
        }),
    )
    inlines = [LeagueEntryInline]


@admin.register(LeagueEntry)
class LeagueEntryAdmin(ModelAdmin):
    list_select_related = ['student', 'league']
    list_display = ['student', 'league', 'test_score', 'primary_score', 'weekly_xp', 'rank']
    list_filter = ['league__period_type', 'league']
    search_fields = ['student__display_name', 'student__tg_id', 'league__title']
