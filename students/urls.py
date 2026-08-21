from django.urls import path

from learning.views import (
    AIExplainView,
    ExamStartView,
    ExamSubmitView,
    IzlozheniyaCatalogView,
    IzlozheniyaStartView,
    SubmitAnswerView,
)
from students.geo_views import (
    CitySearchView,
    ProfileUpdateView,
    PublicConfigView,
    RegisterView,
    SchoolSearchView,
    WebAppUrlSettingsView,
)
from students.parent_views import (
    FamilyHubView,
    ParentInviteIssueView,
    ParentLinkChildView,
    ParentSendReportView,
    ParentUnlinkChildView,
)
from students.views import (
    BePaidCheckoutView,
    BePaidWebhookView,
    DailySessionView,
    DashboardView,
    DevUsersView,
    LeaderboardView,
    MeView,
    PingSessionView,
    ScoreHistoryView,
    StreakDetailView,
    StudentProfileView,
    StudentStatsView,
    TariffsView,
)

app_name = 'students'

urlpatterns = [
    path('dev/users/', DevUsersView.as_view(), name='dev-users'),
    path('me/', MeView.as_view(), name='me'),
    path('ping-session/', PingSessionView.as_view(), name='ping-session'),
    path('me/register/', RegisterView.as_view(), name='register'),
    path('me/profile/', ProfileUpdateView.as_view(), name='profile-update'),
    path('dashboard/<int:tg_id>/', DashboardView.as_view(), name='dashboard'),
    path('payments/bepaid/checkout/', BePaidCheckoutView.as_view(), name='bepaid-checkout'),
    path('payments/bepaid/webhook/', BePaidWebhookView.as_view(), name='bepaid-webhook'),
    path('config/', PublicConfigView.as_view(), name='public-config'),
    path('config/web-app-url/', WebAppUrlSettingsView.as_view(), name='web-app-url'),
    path('cities/', CitySearchView.as_view(), name='cities'),
    path('cities/<int:city_id>/schools/', SchoolSearchView.as_view(), name='schools'),
    path('profile/<int:tg_id>/', StudentProfileView.as_view(), name='profile'),
    path('stats/<int:tg_id>/', StudentStatsView.as_view(), name='stats'),
    path('scores/<int:tg_id>/', ScoreHistoryView.as_view(), name='scores'),
    path('streak/<int:tg_id>/', StreakDetailView.as_view(), name='streak'),
    path('tariffs/', TariffsView.as_view(), name='tariffs'),
    path('daily-session/<int:tg_id>/', DailySessionView.as_view(), name='daily-session'),
    path('leaderboard/', LeaderboardView.as_view(), name='leaderboard'),
    path('submit-answer/<int:tg_id>/', SubmitAnswerView.as_view(), name='submit-answer'),
    path('izlozheniya/<int:tg_id>/', IzlozheniyaCatalogView.as_view(), name='izlozheniya'),
    path('izlozheniya/<int:tg_id>/start/', IzlozheniyaStartView.as_view(), name='izlozheniya-start'),
    path('exam/<int:tg_id>/start/', ExamStartView.as_view(), name='exam-start'),
    path('exam/<int:tg_id>/submit/', ExamSubmitView.as_view(), name='exam-submit'),
    path('family/', FamilyHubView.as_view(), name='family-hub'),
    path('family/invite/<int:tg_id>/', ParentInviteIssueView.as_view(), name='family-invite'),
    path('family/link/', ParentLinkChildView.as_view(), name='family-link'),
    path('family/report/', ParentSendReportView.as_view(), name='family-report'),
    path('family/unlink/', ParentUnlinkChildView.as_view(), name='family-unlink'),
]
