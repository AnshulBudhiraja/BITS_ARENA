from django import forms
from django.contrib.auth import authenticate
from .models import Player


# ── Signup Form (ModelForm of Player) ────────────────────────────────────────

class PlayerSignupForm(forms.ModelForm):
    """
    ModelForm for Player registration.
    Collects bits_id, username (display name), email, and password.
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
        fields = ['bits_id', 'username', 'email']
        labels = {
            'bits_id':  'BITS ID',
            'username': 'Display Name',
            'email':    'Email Address',
        }
        widgets = {
            'bits_id': forms.TextInput(attrs={
                'id': 'id_bits_id',
                'placeholder': '2022A7PS0001P',
                'autocomplete': 'username',
            }),
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

    def clean_bits_id(self):
        bits_id = self.cleaned_data.get('bits_id', '').strip().upper()
        if Player.objects.filter(bits_id=bits_id).exists():
            raise forms.ValidationError('This BITS ID is already registered.')
        return bits_id

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
    Login using BITS ID + password.
    """
    bits_id = forms.CharField(
        label='BITS ID',
        max_length=20,
        widget=forms.TextInput(attrs={
            'id': 'id_login_bits_id',
            'placeholder': '2022A7PS0001P',
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
        bits_id  = cleaned.get('bits_id', '').strip().upper()
        password = cleaned.get('password')

        if bits_id and password:
            player = authenticate(bits_id=bits_id, password=password)
            if player is None:
                raise forms.ValidationError(
                    'Invalid BITS ID or password. Please try again.'
                )
            if not player.is_active:
                raise forms.ValidationError('This account is inactive.')
            self._player = player
        return cleaned

    def get_player(self):
        return self._player
