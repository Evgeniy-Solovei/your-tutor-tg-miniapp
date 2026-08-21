from django.urls import path

from learning.views import AIExplainView

app_name = 'learning'

urlpatterns = [
    path('ai-explain/<int:tg_id>/', AIExplainView.as_view(), name='ai-explain'),
]
