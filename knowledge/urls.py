from django.urls import path

from knowledge.views import CatalogView, ExamTrackListView, GradeCurriculumView, SubjectListView

app_name = 'knowledge'

urlpatterns = [
    path('subjects/', SubjectListView.as_view(), name='subjects'),
    path('subjects/<int:subject_id>/tracks/', ExamTrackListView.as_view(), name='tracks'),
    path('catalog/', CatalogView.as_view(), name='catalog'),
    path('grade/<int:grade>/', GradeCurriculumView.as_view(), name='grade_curriculum'),
]

