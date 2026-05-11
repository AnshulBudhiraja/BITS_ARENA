from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.utils.crypto import get_random_string

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        email = data.get('email', '')
        
        if email:
            prefix = email.split('@')[0].upper()
            from players.models import Player
            if not Player.objects.filter(bits_id=prefix).exists():
                user.bits_id = prefix
            else:
                user.bits_id = f"{prefix}_{get_random_string(4)}"
        else:
            user.bits_id = f"GOOGLE_{get_random_string(8)}"
            
        return user
