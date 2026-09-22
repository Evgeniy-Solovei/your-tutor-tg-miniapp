from django.contrib import admin
from django.utils.html import escape
from django.utils.safestring import mark_safe
from import_export.admin import ImportExportModelAdmin
from unfold.admin import ModelAdmin, TabularInline

from knowledge.models import (
    ContentVersion,
    ExamCollection,
    ExamTrack,
    ExamVariant,
    ScoreScale,
    ScoreScaleRow,
    Section,
    Subject,
    Task,
    TaskOption,
    TaskSolution,
    TaskType,
    Textbook,
    TextbookChapter,
    TextbookFragment,
    Topic,
    TopicExtraTask,
    TopicSummary,
    VariantTask,
)


class TaskOptionInline(TabularInline):
    model = TaskOption
    extra = 4
    fields = ['text', 'image', 'is_correct', 'order']


class TaskSolutionInline(TabularInline):
    model = TaskSolution
    extra = 0
    max_num = 1


@admin.register(Subject)
class SubjectAdmin(ModelAdmin):
    list_display = ['name', 'slug', 'is_active', 'order']
    list_filter = ['is_active']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(ExamTrack)
class ExamTrackAdmin(ModelAdmin):
    list_display = ['name', 'subject', 'track_type', 'grade_from', 'grade_to', 'is_active']
    list_filter = ['subject', 'track_type', 'is_active']
    search_fields = ['name']


@admin.register(ContentVersion)
class ContentVersionAdmin(ModelAdmin):
    list_display = ['title', 'subject', 'year', 'is_current']
    list_filter = ['subject', 'year', 'is_current']
    search_fields = ['title']


class TopicInline(TabularInline):
    model = Topic
    extra = 0
    fields = ['name', 'grade_level', 'exam_weight', 'order', 'is_active']


@admin.register(Section)
class SectionAdmin(ModelAdmin):
    list_display = ['name', 'exam_track', 'content_version', 'order']
    list_filter = ['exam_track', 'content_version']
    search_fields = ['name']
    inlines = [TopicInline]


@admin.register(Topic)
class TopicAdmin(ModelAdmin):
    list_display = ['name', 'section', 'grade_level', 'exam_weight', 'is_active']
    list_filter = ['section__exam_track', 'is_active', 'grade_level']
    search_fields = ['name']


@admin.register(TopicSummary)
class TopicSummaryAdmin(ModelAdmin):
    list_display = ['title', 'topic', 'updated_at']
    search_fields = ['title', 'topic__name']
    autocomplete_fields = ['topic']


class TextbookChapterInline(TabularInline):
    model = TextbookChapter
    extra = 0


@admin.register(Textbook)
class TextbookAdmin(ModelAdmin):
    list_display = ['title', 'subject', 'grade_level', 'publisher', 'is_active']
    list_filter = ['subject', 'grade_level', 'is_active', 'is_official']
    search_fields = ['title', 'authors']
    inlines = [TextbookChapterInline]


class TextbookFragmentInline(TabularInline):
    model = TextbookFragment
    extra = 0


@admin.register(TextbookChapter)
class TextbookChapterAdmin(ModelAdmin):
    list_display = ['title', 'textbook', 'chapter_number', 'order']
    list_filter = ['textbook__subject']
    inlines = [TextbookFragmentInline]


@admin.register(TextbookFragment)
class TextbookFragmentAdmin(ModelAdmin):
    list_display = ['title', 'chapter', 'topic', 'order']
    list_filter = ['chapter__textbook__subject']
    search_fields = ['title', 'content']
    autocomplete_fields = ['topic']


@admin.register(TaskType)
class TaskTypeAdmin(ModelAdmin):
    list_display = ['code', 'name', 'exam_track', 'max_score', 'order']
    list_filter = ['exam_track']
    search_fields = ['code', 'name']


@admin.register(Task)
class TaskAdmin(ImportExportModelAdmin, ModelAdmin):
    list_display = [
        'question_short',
        'grade_level',
        'topic',
        'answer_format',
        'has_image',
        'source',
        'is_active',
    ]
    list_filter = [
        'topic__grade_level',
        'answer_format',
        'difficulty',
        'is_active',
        'topic__section__exam_track',
        'source',
    ]
    search_fields = ['question', 'source']
    inlines = [TaskOptionInline, TaskSolutionInline]
    autocomplete_fields = ['topic', 'task_type']
    readonly_fields = ['created_at']
    list_select_related = ['topic', 'topic__section']
    fields = [
        'topic',
        'task_type',
        'question',
        'image',
        'answer_format',
        'scoring_scheme',
        'difficulty',
        'source',
        'is_active',
        'created_at',
    ]

    @admin.display(description='Задание')
    def question_short(self, obj):
        return obj.question[:80]

    @admin.display(description='Класс', ordering='topic__grade_level')
    def grade_level(self, obj):
        return obj.topic.grade_level if obj.topic_id else '—'

    @admin.display(description='🖼', boolean=True)
    def has_image(self, obj):
        return bool(obj.image)


class ScoreScaleRowInline(TabularInline):
    model = ScoreScaleRow
    extra = 0


@admin.register(ScoreScale)
class ScoreScaleAdmin(ModelAdmin):
    list_display = ['title', 'year', 'exam_track', 'max_primary', 'is_current']
    list_filter = ['year', 'is_current', 'exam_track']
    search_fields = ['title']
    inlines = [ScoreScaleRowInline]

@admin.register(TaskSolution)
class TaskSolutionAdmin(ModelAdmin):
    list_display = ['task', 'correct_answer']
    search_fields = ['task__question', 'correct_answer']
    autocomplete_fields = ['task']


class VariantTaskInline(TabularInline):
    model = VariantTask
    extra = 0
    autocomplete_fields = ['task']


class ExamVariantInline(TabularInline):
    model = ExamVariant
    extra = 0
    fields = ['number', 'title', 'year', 'is_active']


@admin.register(ExamCollection)
class ExamCollectionAdmin(ModelAdmin):
    list_display = ['title', 'subject', 'publisher', 'year', 'is_active']
    list_filter = ['subject', 'year', 'is_active']
    search_fields = ['title', 'isbn', 'publisher']
    inlines = [ExamVariantInline]


@admin.register(ExamVariant)
class ExamVariantAdmin(ModelAdmin):
    list_display = ['collection', 'number', 'title', 'year', 'is_active']
    list_filter = ['collection', 'year', 'is_active']
    search_fields = ['title', 'collection__title']
    inlines = [VariantTaskInline]


@admin.register(VariantTask)
class VariantTaskAdmin(ModelAdmin):
    list_display = ['variant', 'order', 'task']
    list_filter = ['variant__collection']
    autocomplete_fields = ['variant', 'task']


@admin.register(TopicExtraTask)
class TopicExtraTaskAdmin(ModelAdmin):
    list_display = [
        'image_thumbnail',
        'topic',
        'grade_display',
        'difficulty',
        'question_preview',
        'correct_answer',
        'is_active',
    ]
    list_filter = ['topic__grade_level', 'difficulty', 'is_active', 'topic']
    search_fields = ['question', 'correct_answer', 'topic__name', 'explanation']
    autocomplete_fields = ['topic']
    readonly_fields = ['image_preview_large', 'formatted_options', 'created_at']
    fieldsets = [
        ('Основное', {
            'fields': ['topic', 'difficulty', 'is_active', 'order', 'source']
        }),
        ('Иллюстрация', {
            'fields': ['image_preview_large', 'image', 'image_url']
        }),
        ('Задание и ответы', {
            'fields': ['question', 'reading_text', 'formatted_options', 'options', 'correct_answer', 'explanation']
        }),
        ('Даты', {
            'fields': ['created_at'],
            'classes': ['collapse']
        }),
    ]

    def grade_display(self, obj):
        return f'{obj.topic.grade_level} класс' if obj.topic else '—'
    grade_display.short_description = 'Класс'
    grade_display.admin_order_field = 'topic__grade_level'

    def image_thumbnail(self, obj):
        url = obj.get_image_url
        if url:
            return mark_safe(f'<img src="{url}" style="height:36px; width:64px; object-fit:cover; border-radius:6px; border:1px solid #cbd5e1;" />')
        return '—'
    image_thumbnail.short_description = 'Карточка'

    def image_preview_large(self, obj):
        url = obj.get_image_url
        if url:
            return mark_safe(
                f'<div style="background:#f8fafc; padding:12px; border-radius:12px; display:inline-block; border:1px solid #e2e8f0;">'
                f'<img src="{url}" style="max-width:420px; max-height:240px; border-radius:8px; display:block; box-shadow:0 2px 8px rgba(0,0,0,0.08);" />'
                f'<div style="margin-top:6px; font-size:12px; color:#64748b;">Путь: <code>{url}</code></div>'
                f'</div>'
            )
        return 'Изображение не прикреплено'
    image_preview_large.short_description = 'Превью карточки'

    def formatted_options(self, obj):
        opts = obj.options or []
        if not opts:
            return '—'
        items = []
        for o in opts:
            escaped_opt = escape(str(o))
            is_c = str(o).strip().lower() == str(obj.correct_answer).strip().lower()
            if is_c:
                items.append(f'<li style="color:#16a34a; font-weight:600;">✓ {escaped_opt} <i>(верный ответ)</i></li>')
            else:
                items.append(f'<li style="color:#475569;">• {escaped_opt}</li>')
        return mark_safe(f'<ul style="margin:0; padding-left:18px; line-height:1.6;">{"".join(items)}</ul>')
    formatted_options.short_description = 'Варианты ответов'

    def question_preview(self, obj):
        q = obj.question or ''
        preview = (q[:60] + '…') if len(q) > 60 else q
        return escape(preview)
    question_preview.short_description = 'Вопрос'

