from django.dispatch import receiver
from allauth.account.signals import user_signed_up

@receiver(user_signed_up)
def on_user_signed_up(request, user, **kwargs):
    # If the user signed up via a social account (like Google), they won't have a usable password.
    if not user.has_usable_password():
        # Set a session flag to prompt for an optional password setup
        request.session['prompt_password_setup'] = True
