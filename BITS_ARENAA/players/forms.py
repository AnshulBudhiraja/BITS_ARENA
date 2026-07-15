from django import forms
from django.contrib.auth import authenticate
from .models import Player


# ── Signup Form (ModelForm of Player) ────────────────────────────────────────

class PlayerSignupForm(forms.ModelForm):
    """
    ModelForm for Player registration.
    Collects username (display name), email, and password.
    """
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'id': 'id_password',
            'placeholder': 'Create a password',
            'autocomplete': 'new-password',
        }),
        min_length=8,
        help_text='Minimum 8 characters.',
    )
    confirm_password = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'id': 'id_confirm_password',
            'placeholder': 'Repeat your password',
            'autocomplete': 'new-password',
        }),
    )

    class Meta:
        model  = Player
        fields = ['username', 'email']
        labels = {
            'username': 'Display Name',
            'email':    'Email Address',
        }
        widgets = {
            'username': forms.TextInput(attrs={
                'id': 'id_username',
                'placeholder': 'Your display name',
                'autocomplete': 'nickname',
            }),
            'email': forms.EmailInput(attrs={
                'id': 'id_email',
                'placeholder': 'you@bits.edu',
                'autocomplete': 'email',
            }),
        }

    # ── Validation ───────────────────────────────────────────────────────────

    def clean(self):
        cleaned = super().clean()
        pw  = cleaned.get('password')
        cpw = cleaned.get('confirm_password')
        if pw and cpw and pw != cpw:
            self.add_error('confirm_password', 'Passwords do not match.')
        return cleaned

    # ── Save ─────────────────────────────────────────────────────────────────

    def save(self, commit=True):
        player = super().save(commit=False)
        player.set_password(self.cleaned_data['password'])
        if commit:
            player.save()
            self._save_m2m()
        return player


# ── Login Form ───────────────────────────────────────────────────────────────

class PlayerLoginForm(forms.Form):
    """
    Login using Email, or Username + password.
    """
    login_id = forms.CharField(
        label='Username or Email',
        max_length=254,
        widget=forms.TextInput(attrs={
            'id': 'id_login_id',
            'placeholder': 'Your Username or Email',
            'autocomplete': 'username',
        }),
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'id': 'id_login_password',
            'placeholder': 'Your password',
            'autocomplete': 'current-password',
        }),
    )

    def __init__(self, *args, **kwargs):
        self._player = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned  = super().clean()
        login_id = cleaned.get('login_id', '').strip()
        password = cleaned.get('password')

        if login_id and password:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            player = None
            
            # 1. Try by email
            if '@' in login_id:
                try:
                    user_obj = User.objects.get(email=login_id)
                    player = authenticate(username=user_obj.username, password=password)
                except User.DoesNotExist:
                    pass
            
            # 2. Try by username (display name)
            if not player:
                player = authenticate(username=login_id, password=password)
                
            if player is None:
                raise forms.ValidationError(
                    'Invalid credentials. Please try again.'
                )
            if not player.is_active:
                raise forms.ValidationError('This account is inactive.')
            self._player = player
        return cleaned

    def get_player(self):
        return self._player


class SocialSignupCompletionForm(forms.Form):
    """
    Form to allow Google users to change their auto-generated username
    and optionally set a password.
    """
    username = forms.CharField(
        label='Username',
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'id': 'id_username',
            'placeholder': 'Your Username',
            'autocomplete': 'username',
        }),
    )
    password = forms.CharField(
        label='Optional Password',
        required=False,
        widget=forms.PasswordInput(attrs={
            'id': 'id_password',
            'placeholder': 'Leave blank to skip',
            'autocomplete': 'new-password',
        }),
    )
    password_confirm = forms.CharField(
        label='Confirm Optional Password',
        required=False,
        widget=forms.PasswordInput(attrs={
            'id': 'id_password_confirm',
            'placeholder': 'Confirm optional password',
            'autocomplete': 'new-password',
        }),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if Player.objects.filter(username=username).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def clean(self):
        cleaned_data = super().clean()
        pwd = cleaned_data.get('password')
        pwd_conf = cleaned_data.get('password_confirm')
        
        if pwd or pwd_conf:
            if pwd != pwd_conf:
                raise forms.ValidationError('Passwords do not match.')
        return cleaned_data


class PasswordChangeOldPasswordForm(forms.Form):
    old_password = forms.CharField(
        label='Current Password',
        widget=forms.PasswordInput(attrs={'placeholder': 'Enter your current password'})
    )
    new_password = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={'placeholder': 'Enter new password'})
    )
    confirm_new_password = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirm new password'})
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        old_password = self.cleaned_data.get('old_password')
        if not self.user.check_password(old_password):
            raise forms.ValidationError('Incorrect current password.')
        return old_password

    def clean(self):
        cleaned_data = super().clean()
        new_pwd = cleaned_data.get('new_password')
        conf_pwd = cleaned_data.get('confirm_new_password')
        if new_pwd and conf_pwd and new_pwd != conf_pwd:
            raise forms.ValidationError('New passwords do not match.')
        return cleaned_data


class PasswordChangeOTPForm(forms.Form):
    otp = forms.CharField(
        label='6-Digit OTP',
        max_length=6,
        widget=forms.TextInput(attrs={'placeholder': 'Enter the OTP sent to your email'})
    )
    new_password = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={'placeholder': 'Enter new password'})
    )
    confirm_new_password = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirm new password'})
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_otp(self):
        from django.core.cache import cache
        otp = self.cleaned_data.get('otp')
        cached_otp = cache.get(f'otp_pwd_{self.user.id}')
        
        if not cached_otp or str(cached_otp) != str(otp):
            raise forms.ValidationError('Invalid or expired OTP.')
        return otp

    def clean(self):
        cleaned_data = super().clean()
        new_pwd = cleaned_data.get('new_password')
        conf_pwd = cleaned_data.get('confirm_new_password')
        if new_pwd and conf_pwd and new_pwd != conf_pwd:
            raise forms.ValidationError('New passwords do not match.')
        return cleaned_data
