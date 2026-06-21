from django.urls import path
from .views import LeaderboardView, MatchCreateView

app_name = 'api'

urlpatterns = [
    path('leaderboard/', LeaderboardView.as_view(), name='leaderboard-list'),
    path('leaderboard/<int:game_id>/', LeaderboardView.as_view(), name='leaderboard-detail'),
    path('matches/', MatchCreateView.as_view(), name='match-create'),
]
