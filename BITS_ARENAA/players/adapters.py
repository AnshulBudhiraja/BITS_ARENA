from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse

class CustomAccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        if request.session.get('prompt_password_setup'):
            del request.session['prompt_password_setup']
            return reverse('players:optional_password')
        return super().get_login_redirect_url(request)

    def get_signup_redirect_url(self, request):
        if request.session.get('prompt_password_setup'):
            del request.session['prompt_password_setup']
            return reverse('players:optional_password')
        return super().get_signup_redirect_url(request)
