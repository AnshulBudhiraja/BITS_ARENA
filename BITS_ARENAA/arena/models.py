from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Game(models.Model):
    """
    Represents a sport or game type on the platform.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Game Name',
    )
    is_team_based = models.BooleanField(
        default=False,
        verbose_name='Team Based',
        help_text='If True, matches involve teams instead of individual players.',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Active',
    )
    scoring_unit = models.CharField(
        max_length=50,
        verbose_name='Scoring Unit',
        help_text='e.g. "points", "goals", "runs"',
    )
    duration_unit = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Duration Unit',
        help_text='e.g. "minutes", "sets", "overs"',
    )
    requires_duration = models.BooleanField(
        default=False,
        verbose_name='Requires Duration',
        help_text='Whether a match of this game must record duration.',
    )
    has_standard_scoring = models.BooleanField(
        default=True,
        verbose_name='Has Standard Scoring',
        help_text='If False, users will be prompted to specify the target scoring amount (e.g. 21 points).',
    )

    class Meta:
        verbose_name = 'Game'
        verbose_name_plural = 'Games'
        ordering = ['name']

    def __str__(self):
        return self.name


class Match(models.Model):
    """
    Represents a match between two participants (players or teams).
    `challenged_by` and `opponent` use GenericForeignKey so they can
    point to either a Player or a Team depending on game.is_team_based.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        ONGOING = 'ongoing', 'Ongoing'
        COMPLETED = 'completed', 'Completed'
        FINALIZED = 'finalized', 'Finalized'
        CANCELLED = 'cancelled', 'Cancelled'

    class InviteType(models.TextChoices):
        INVITE_ONLY     = 'invite_only',    'Invite Only'
        OPEN_CHALLENGE  = 'open_challenge',  'Open Challenge'

    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name='matches',
        verbose_name='Game',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Created At',
    )
    played_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Played At',
    )
    location = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Location',
        help_text='e.g. Gymg, VK QT lawns, etc.'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Status',
    )
    invite_type = models.CharField(
        max_length=20,
        choices=InviteType.choices,
        default=InviteType.OPEN_CHALLENGE,
        verbose_name='Invite Type',
    )

    scoring_unit_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Scoring Unit Number',
    )
    
    duration_unit_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Duration Unit Number',
    )

    # --- challenged_by (Player OR Team) ---
    challenged_by_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='challenger_matches',
        verbose_name='Challenger Type',
    )
    challenged_by_object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Challenger ID',
    )
    challenged_by = GenericForeignKey(
        'challenged_by_content_type',
        'challenged_by_object_id',
    )

    # --- opponent (Player OR Team) ---
    opponent_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='opponent_matches',
        verbose_name='Opponent Type',
    )
    opponent_object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Opponent ID',
    )
    opponent = GenericForeignKey(
        'opponent_content_type',
        'opponent_object_id',
    )

    # --- invited_opponent (Specific Player invited to match) ---
    invited_opponent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='match_invitations',
        verbose_name='Invited Opponent',
    )
    
    # --- cancellation_requested_by (User who requested to cancel the match) ---
    cancellation_requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cancellation_requests',
        verbose_name='Cancellation Requested By',
    )

    # --- start_requested_by (User who initially clicked Start Match) ---
    start_requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='start_requests',
        verbose_name='Start Requested By',
    )

    score = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Score',
        help_text='e.g. {"challenger": 3, "opponent": 1}',
    )
    
    challenger_score_claim = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Challenger Score Claim',
    )
    
    opponent_score_claim = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Opponent Score Claim',
    )

    # --- winner (Player OR Team, nullable until match is complete) ---
    winner_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='won_matches',
        verbose_name='Winner Type',
    )
    winner_object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Winner ID',
    )
    winner = GenericForeignKey(
        'winner_content_type',
        'winner_object_id',
    )

    class Meta:
        verbose_name = 'Match'
        verbose_name_plural = 'Matches'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.game.name} match — {self.status} ({self.created_at.date()})"

    def get_opponent(self, player):
        """Returns the participant that is NOT the given player/team."""
        if self.challenged_by == player:
            return self.opponent
        # If player is in a team, check if challenged_by is that team
        if hasattr(player, 'teams') and self.challenged_by in player.teams.all():
            return self.opponent
        return self.challenged_by

    def get_outcome(self, player):
        """Returns 'WIN', 'LOSS', 'DRAW', or 'CANCELLED' relative to the given player."""
        if self.status == self.Status.CANCELLED:
            return 'CANCELLED'
        
        if not self.winner:
            return 'DRAW'
            
        # Check if winner is the player or a team the player is in
        winner = self.winner
        if winner == player:
            return 'WIN'
        if hasattr(player, 'teams') and winner in player.teams.all():
            return 'WIN'
            
        return 'LOSS'

    def get_legacy_time(self):
        """Returns played_at for completed matches, or created_at for cancelled ones."""
        if self.status in [self.Status.COMPLETED, self.Status.FINALIZED]:
            return self.played_at or self.created_at
        return self.created_at

    def get_display_score(self, player):
        """Returns a string relative to the player, handling both sets and standard scores."""
        if not self.score:
            return "N/A"
        
        # Determine if player (or their team) is challenger or opponent
        is_challenger = (self.challenged_by == player)
        if not is_challenger and hasattr(player, 'teams'):
            is_challenger = (self.challenged_by in player.teams.all())
            
        # ── Case A: Set-based Score ───────────────────────────────────────────
        if 'sets' in self.score:
            sets_dict = self.score.get('sets', {})
            # Sort by set number (keys are strings "1", "2", ...)
            sorted_set_keys = sorted(sets_dict.keys(), key=lambda k: int(k))
            
            my_sets_won = 0
            their_sets_won = 0
            set_details = []
            
            for key in sorted_set_keys:
                s_data = sets_dict[key]
                c_p = s_data.get('challenger', 0)
                o_p = s_data.get('opponent', 0)
                
                # Update tally
                if c_p > o_p:
                    if is_challenger: my_sets_won += 1
                    else: their_sets_won += 1
                elif o_p > c_p:
                    if is_challenger: their_sets_won += 1
                    else: my_sets_won += 1
                
                # Build detail string
                if is_challenger:
                    set_details.append(f"{c_p}-{o_p}")
                else:
                    set_details.append(f"{o_p}-{c_p}")
            
            return f"{my_sets_won} — {their_sets_won}"

        # ── Case B: Standard Points Score ─────────────────────────────────────
        c_score = self.score.get('challenger', 0)
        o_score = self.score.get('opponent', 0)
        
        if is_challenger:
            return f"{c_score} — {o_score}"
        return f"{o_score} — {c_score}"
