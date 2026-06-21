from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from players.models import PlayerRating
from arena.models import Game
from .serializers import PlayerRatingSerializer, GameSerializer, MatchSerializer, MatchCreateSerializer


class LeaderboardView(APIView):
    """
    API endpoint that provides leaderboards for games.
    
    Supports:
    - GET /api/leaderboard/ : returns leaderboards for all active games
    - GET /api/leaderboard/<game_id>/ : returns leaderboard for a specific game
    - GET /api/leaderboard/?game=<game_id> : returns leaderboard for a specific game
    """
    
    def get(self, request, game_id=None, *args, **kwargs):
        # Allow specifying the game via query parameter or URL path variable
        if not game_id:
            game_id = request.query_params.get('game')
            
        if game_id:
            # Leaderboard for a single game
            game = get_object_or_404(Game, id=game_id)
            ratings = PlayerRating.objects.filter(game=game).order_by('-rating')
            
            # Map rating IDs to 1-based ranks
            ranks = {rating.id: idx + 1 for idx, rating in enumerate(ratings)}
            
            serializer = PlayerRatingSerializer(ratings, many=True, context={'ranks': ranks})
            
            return Response({
                'game': GameSerializer(game).data,
                'leaderboard': serializer.data
            })
            
        # Leaderboards for all active games
        games = Game.objects.filter(is_active=True)
        response_data = []
        
        for game in games:
            ratings = PlayerRating.objects.filter(game=game).order_by('-rating')
            ranks = {rating.id: idx + 1 for idx, rating in enumerate(ratings)}
            
            serializer = PlayerRatingSerializer(ratings, many=True, context={'ranks': ranks})
            
            response_data.append({
                'game': GameSerializer(game).data,
                'leaderboard': serializer.data
            })
            
        return Response(response_data)


class MatchCreateView(APIView):
    """
    API endpoint to create a new match challenge.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = MatchCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            match = serializer.save()
            return Response(MatchSerializer(match, context={'request': request}).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
