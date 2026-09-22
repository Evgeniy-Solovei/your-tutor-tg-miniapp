from django.urls import path

from knowledge.views import (
    CatalogView,
    ExamTrackListView,
    GradeCurriculumView,
    GradeExtraTasksSummaryView,
    SubjectListView,
    TopicExtraTasksView,
    TopicExtraTaskSubmitView,
)

app_name = 'knowledge'

urlpatterns = [
    path('subjects/', SubjectListView.as_view(), name='subjects'),
    path('subjects/<int:subject_id>/tracks/', ExamTrackListView.as_view(), name='tracks'),
    path('catalog/', CatalogView.as_view(), name='catalog'),
    path('grade/<int:grade>/', GradeCurriculumView.as_view(), name='grade_curriculum'),
    path('extra-tasks/summary/', GradeExtraTasksSummaryView.as_view(), name='extra_tasks_summary'),
    path('topics/<int:topic_id>/extra-tasks/', TopicExtraTasksView.as_view(), name='topic_extra_tasks'),
    path('extra-tasks/<int:task_id>/answer/', TopicExtraTaskSubmitView.as_view(), name='extra_task_answer'),
]

