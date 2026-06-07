from rest_framework import serializers
from players.models import Player, PlayerRating
from arena.models import Game


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