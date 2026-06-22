from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from players.models import Player, PlayerRating, Team
from arena.models import Game, Match


class PlayerUserSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Player
        fields = ['id', 'username', 'bits_id', 'avatar_url']

    def get_avatar_url(self, obj):
        return obj.get_avatar_url


class GameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Game
        fields = ['id', 'name', 'is_team_based', 'is_active', 'scoring_unit']


class PlayerRatingSerializer(serializers.ModelSerializer):
    player = PlayerUserSerializer(read_only=True)
    game = GameSerializer(read_only=True)
    rank = serializers.SerializerMethodField()

    class Meta:
        model = PlayerRating
        fields = ['id', 'player', 'game', 'rating', 'has_crossed_elo_floor', 'rank']

    def get_rank(self, obj):
        # Ranks can be injected via serializer context to avoid database-level N+1 issues
        return self.context.get('ranks', {}).get(obj.id, None)


# Keep the original PlayerSerializer name pointing to PlayerRatingSerializer for compatibility
class PlayerSerializer(PlayerRatingSerializer):
    pass


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ['id', 'team_name']


class MatchSerializer(serializers.ModelSerializer):
    game = GameSerializer(read_only=True)
    challenged_by = serializers.SerializerMethodField()
    opponent = serializers.SerializerMethodField()
    invited_opponent = PlayerUserSerializer(read_only=True)

    class Meta:
        model = Match
        fields = [
            'id', 'game', 'created_at', 'played_at', 'location',
            'status', 'invite_type', 'scoring_unit_number', 'duration_unit_number',
            'challenged_by', 'opponent', 'invited_opponent', 'score'
        ]

    def get_challenged_by(self, obj):
        if not obj.challenged_by:
            return None
        if isinstance(obj.challenged_by, Player):
            return PlayerUserSerializer(obj.challenged_by, context=self.context).data
        elif isinstance(obj.challenged_by, Team):
            return TeamSerializer(obj.challenged_by, context=self.context).data
        return str(obj.challenged_by)

    def get_opponent(self, obj):
        if not obj.opponent:
            return None
        if isinstance(obj.opponent, Player):
            return PlayerUserSerializer(obj.opponent, context=self.context).data
        elif isinstance(obj.opponent, Team):
            return TeamSerializer(obj.opponent, context=self.context).data
        return str(obj.opponent)


class MatchCreateSerializer(serializers.ModelSerializer):
    opponent_bits_id = serializers.CharField(required=False, write_only=True, allow_blank=True)

    class Meta:
        model = Match
        fields = [
            'id', 'game', 'played_at', 'location', 
            'duration_unit_number', 'scoring_unit_number', 
            'invite_type', 'opponent_bits_id'
        ]
        read_only_fields = ['id']

    def validate(self, attrs):
        game = attrs.get('game')
        duration_num = attrs.get('duration_unit_number')
        invite_type = attrs.get('invite_type')
        opponent_bits_id = attrs.get('opponent_bits_id')

        # 1. Check if the game is active
        if game and not game.is_active:
            raise serializers.ValidationError({
                'game': "Matches cannot be created for inactive games."
            })

        # 2. Validation for duration unit number (sets must be odd)
        if game and duration_num is not None:
            unit = (game.duration_unit or "").lower()
            if unit in ['set', 'sets']:
                if duration_num % 2 == 0:
                    raise serializers.ValidationError({
                        'duration_unit_number': f"For {game.name}, the number of sets must be an odd number (e.g. 1, 3, 5) to ensure a clear winner."
                    })

        # 3. Validation for invite only match
        if invite_type == Match.InviteType.INVITE_ONLY:
            if not opponent_bits_id or not opponent_bits_id.strip():
                raise serializers.ValidationError({
                    'opponent_bits_id': "Opponent's BITS ID is required for invite-only matches."
                })
            try:
                opponent = Player.objects.get(bits_id=opponent_bits_id.strip())
                request = self.context.get('request')
                if request and request.user == opponent:
                    raise serializers.ValidationError({
                        'opponent_bits_id': "You cannot invite yourself to a match."
                    })
                attrs['resolved_opponent'] = opponent
            except Player.DoesNotExist:
                raise serializers.ValidationError({
                    'opponent_bits_id': "No player found with that BITS ID."
                })

        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        if not request or not request.user or request.user.is_anonymous:
            raise serializers.ValidationError("Authentication credentials are required.")
        user = request.user
        if not isinstance(user, Player):
            raise serializers.ValidationError("Invalid user type.")

        resolved_opponent = validated_data.pop('resolved_opponent', None)
        validated_data.pop('opponent_bits_id', None)

        game = validated_data.get('game')
        
        # Create match instance
        match = Match(**validated_data)
        
        # Set challenger (GenericForeignKey pointing to Player)
        player_ct = ContentType.objects.get_for_model(Player)
        match.challenged_by_content_type = player_ct
        match.challenged_by_object_id = user.pk
        
        # Default status is PENDING
        match.status = Match.Status.PENDING

        # Set invited opponent if invite_only
        if validated_data.get('invite_type') == Match.InviteType.INVITE_ONLY:
            match.invited_opponent = resolved_opponent

        match.save()

        # Add game to player's played games
        user.games.add(game)

        return match


class MatchJoinSerializer(serializers.ModelSerializer):
    class Meta:
        model = Match
        fields = []

    def validate(self, attrs):
        request = self.context.get('request')
        if not request or not request.user or request.user.is_anonymous:
            raise serializers.ValidationError("Authentication credentials were not provided.")

        player = request.user
        if not isinstance(player, Player):
            raise serializers.ValidationError("Invalid user type.")
        player_ct = ContentType.objects.get_for_model(Player)

        match = self.instance
        if not match:
            raise serializers.ValidationError("Match instance not provided.")

        # Prevent joining own match
        if match.challenged_by_content_type == player_ct and match.challenged_by_object_id == player.pk:
            raise serializers.ValidationError("You cannot join your own match.")

        # Check if user already has Ongoing/Confirmed/Pending matches, excluding the current match
        busy_as_challenger = Match.objects.filter(
            challenged_by_content_type=player_ct,
            challenged_by_object_id=player.pk,
            status__in=[Match.Status.CONFIRMED, Match.Status.ONGOING, Match.Status.PENDING]
        ).exclude(pk=match.pk).exists()

        busy_as_opponent = Match.objects.filter(
            opponent_content_type=player_ct,
            opponent_object_id=player.pk,
            status__in=[Match.Status.CONFIRMED, Match.Status.ONGOING]
        ).exclude(pk=match.pk).exists()

        if busy_as_challenger or busy_as_opponent:
            raise serializers.ValidationError(
                "You cannot join a new match while having one in Pending, Confirmed or Ongoing status."
            )

        if match.status != Match.Status.PENDING:
            raise serializers.ValidationError("This match is not available for joining.")

        if match.invite_type == Match.InviteType.INVITE_ONLY and match.invited_opponent != player:
            raise serializers.ValidationError("You are not invited to this match.")

        if match.invite_type == Match.InviteType.OPEN_CHALLENGE and match.invited_opponent is not None:
            raise serializers.ValidationError("This match is not available.")

        return attrs

    def update(self, instance, validated_data):
        request = self.context.get('request')
        if not request or not request.user or request.user.is_anonymous:
            raise serializers.ValidationError("Authentication credentials are required.")
        player = request.user
        if not isinstance(player, Player):
            raise serializers.ValidationError("Invalid user type.")

        # Set opponent to the joining player and update status
        instance.opponent = player
        instance.status = Match.Status.CONFIRMED
        instance.save()

        # Add game to player's played games
        player.games.add(instance.game)

        return instance