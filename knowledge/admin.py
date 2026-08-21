from django.contrib import admin
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
