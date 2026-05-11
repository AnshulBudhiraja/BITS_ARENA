from django.urls import path
from . import views
from Bits_Arena.views import home, match_hub
from players.views import profile

app_name = 'arena'

urlpatterns = [
    path('',                  home,                    name='home'),
    path('matches/',          match_hub,               name='match_hub'),
    path('matches/create/',   views.create_match_view, name='create_match'),
    path('matches/join/<int:match_id>/', views.join_match,   name='join_match'),
    path('matches/cancel/<int:match_id>/', views.cancel_match, name='cancel_match'),
    path('matches/accept-cancellation/<int:match_id>/', views.accept_cancellation, name='accept_cancellation'),
    path('matches/start/<int:match_id>/', views.start_match, name='start_match'),
    path('matches/live/<int:match_id>/', views.live_match_view, name='live_match'),
    path('matches/end/<int:match_id>/', views.end_match_view, name='end_match'),
    path('profile/',          profile,                 name='profile'),
]
