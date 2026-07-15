from django import forms
from .models import Match


class MatchCreateForm(forms.ModelForm):
    """
    ModelForm for creating a new match.
    Includes an optional opponent_username field shown only when
    invite_type == 'invite_only'.
    """
    opponent_username = forms.CharField(
        required=False,
        max_length=150,
        label="Opponent's Username",
        widget=forms.TextInput(attrs={
            'id': 'opponent-username',
            'placeholder': 'Search Username',
            'autocomplete': 'off',
            'class': 'form-input bits-search-input',
        }),
    )

    class Meta:
        model = Match
        fields = ['game', 'played_at', 'location', 'duration_unit_number', 'scoring_unit_number', 'invite_type']
        widgets = {
            'game': forms.Select(attrs={
                'id': 'id-game',
                'class': 'form-input form-select',
            }),
            'played_at': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={
                    'type': 'datetime-local',
                    'id': 'id-played-at',
                    'class': 'form-input',
                }
            ),
            'location': forms.TextInput(attrs={
                'id': 'id-location',
                'class': 'form-input',
                'placeholder': 'Enter location',
            }),
            'duration_unit_number': forms.NumberInput(attrs={
                'id': 'id-duration',
                'class': 'form-input',
                'placeholder': 'Duration Unit',
                'min': '1',
            }),
            'scoring_unit_number': forms.NumberInput(attrs={
                'id': 'id-scoring',
                'class': 'form-input',
                'placeholder': 'Scoring Unit',
                'min': '1',
            }),
            'invite_type': forms.Select(attrs={
                'id': 'id-invite-type',
                'class': 'form-input form-select',
            }),
        }
        labels = {
            'game': 'Game',
            'played_at': 'Scheduled Date & Time',
            'invite_type': 'Match Type',
            'duration_unit_number': 'Duration Unit Number',
            'scoring_unit_number': 'Scoring Unit Number',
            'location': 'Location',
        }
        help_texts = {
            'location': 'Gymg, VK QT lawns, etc.',
        }

    def clean(self):
        cleaned_data = super().clean()
        game = cleaned_data.get('game')
        duration_num = cleaned_data.get('duration_unit_number')

        if game and duration_num is not None:
            # Check if duration_unit is 'set' or 'sets' (case-insensitive)
            unit = (game.duration_unit or "").lower()
            if unit in ['set', 'sets']:
                if duration_num % 2 == 0:
                    self.add_error(
                        'duration_unit_number', 
                        f"For {game.name}, the number of sets must be an odd number (e.g. 1, 3, 5) to ensure a clear winner."
                    )
        
        return cleaned_data


class SetScoreForm(forms.Form):
    """
    Handles score inputs for a single set (or single match if sets are not used).
    """
    def __init__(self, *args, **kwargs):
        self.target_score = kwargs.pop('target_score', None)
        super().__init__(*args, **kwargs)

    set_number = forms.IntegerField(required=False, widget=forms.HiddenInput())
    
    challenger_score = forms.IntegerField(
        label='Challenger',
        min_value=0,
        required=True,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '0', 'style': 'font-size: 1.1rem; padding: 0.5rem; border-radius: 0.5rem;'})
    )
    
    opponent_score = forms.IntegerField(
        label='Opponent',
        min_value=0,
        required=True,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '0', 'style': 'font-size: 1.1rem; padding: 0.5rem; border-radius: 0.5rem;'})
    )

    def clean(self):
        cleaned_data = super().clean()
        c_score = cleaned_data.get('challenger_score')
        o_score = cleaned_data.get('opponent_score')

        if self.target_score is not None and c_score is not None and o_score is not None:
            # Check if at least one player reached the target score
            if c_score != self.target_score and o_score != self.target_score:
                raise forms.ValidationError(f"At least one player must have a score of {self.target_score}.")
            
            # Check if any player exceeded the target score
            if c_score > self.target_score or o_score > self.target_score:
                raise forms.ValidationError(f"Scores cannot exceed the target score of {self.target_score}.")
            
            # Additional rule: they cannot both be equal if it's a win-by-X game, 
            # but user didn't ask for that. "one must be equal, other is <= target"
            # If both are equal, it's a tie at the target, which fits the rule.
        
        return cleaned_data
