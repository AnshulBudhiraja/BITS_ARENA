from django.contrib.auth.models import AbstractUser
from django.db import models


class Player(AbstractUser):
    """
    Custom user model extending Django's AbstractUser.
    BITS ID is the primary identifier used for login and signup.
    """

    # ── BITS ID as the login field ──────────────────────────────────────────
    bits_id = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='BITS ID',
        help_text='Your official BITS Pilani ID (e.g. 2022A7PS0001G)',
    )

    # AbstractUser already provides: username, first_name, last_name,
    # email, password, is_active, date_joined, etc.
    # We keep username as a required field but make bits_id the login key.

    USERNAME_FIELD  = 'bits_id'   # used by authenticate() / login()
    REQUIRED_FIELDS = ['username', 'email']   # asked by createsuperuser

    games = models.ManyToManyField(
        'arena.Game',
        blank=True,
        related_name='players',
        verbose_name='Games Participated In',
    )

    class Meta:
        verbose_name        = 'Player'
        verbose_name_plural = 'Players'

    def __str__(self):
        return f"{self.bits_id} ({self.username})"

    @property
    def get_avatar_url(self):
        """Returns a generated avatar URL based on username."""
        # Using DiceBear Bottts style for a cyber-athletic look
        return f"https://api.dicebear.com/7.x/bottts/svg?seed={self.username}&backgroundColor=020408,060c14&textColor=00f5ff"


class PlayerRating(models.Model):
    """
    Stores a numeric rating for a specific player in a specific game.
    """
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='ratings',
        verbose_name='Player',
    )
    game = models.ForeignKey(
        'arena.Game',
        on_delete=models.CASCADE,
        related_name='player_ratings',
        verbose_name='Game',
    )
    rating = models.FloatField(
        default=0.0,
        verbose_name='Rating',
    )
    has_crossed_elo_floor = models.BooleanField(
        default=False,
        verbose_name='Has Crossed ELO Floor',
    )

    class Meta:
        verbose_name        = 'Player Rating'
        verbose_name_plural = 'Player Ratings'
        unique_together     = ('player', 'game')

    def __str__(self):
        return f"{self.player.bits_id} — {self.game.name}: {self.rating}"


class Team(models.Model):
    """
    Represents a team of players for a specific game.
    """
    team_name = models.CharField(
        max_length=150,
        verbose_name='Team Name',
    )
    game = models.ForeignKey(
        'arena.Game',
        on_delete=models.CASCADE,
        related_name='teams',
        verbose_name='Game',
    )
    players = models.ManyToManyField(
        Player,
        blank=True,
        related_name='teams',
        verbose_name='Players',
    )

    class Meta:
        verbose_name        = 'Team'
        verbose_name_plural = 'Teams'

    def __str__(self):
        return f"{self.team_name} ({self.game.name})"
