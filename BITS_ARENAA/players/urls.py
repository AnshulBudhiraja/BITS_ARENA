from django.urls import path
from . import views

app_name = 'players'

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
    path('login/',  views.login_view,  name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('optional-password/', views.optional_password_view, name='optional_password'),
    path('settings/password/', views.password_settings_view, name='password_settings'),
    path('settings/password/send-otp/', views.send_otp_view, name='send_otp'),
]
