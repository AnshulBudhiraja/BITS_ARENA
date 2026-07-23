from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.cache import cache

from players.models import Player, PlayerRating
from arena.models import Match, Game


def home(request):
    """
    Root view. Unauthenticated users see the welcome/splash screen.
    Authenticated users see the home dashboard.
    """
    if not request.user.is_authenticated:
        return render(request, 'welcome.html')
        
    games = Game.objects.filter(is_active=True)
    user_stats = []
    
    for game in games:
        cache_key = f"game_{game.id}_top_10_leaderboard"
        top_10 = cache.get(cache_key)
        
        if top_10 is None:
            top_10 = list(PlayerRating.objects.filter(game=game).select_related('player').order_by('-rating')[:10])
            cache.set(cache_key, top_10, timeout=86400)  # cache for 24 hours
            
        
        # Find current user's rating and rank efficiently without loading the entire leaderboard
        rating_obj = PlayerRating.objects.filter(game=game, player=request.user).first()
        if rating_obj:
            rank = PlayerRating.objects.filter(game=game, rating__gt=rating_obj.rating).count() + 1
            user_stats.append({
                'game': game,
                'rating': rating_obj.rating,
                'rank': rank
            })
        
    context = {
        'games': games,
        'user_stats': user_stats,
    }
    return render(request, 'home.html', context)


@login_required
def match_hub(request):
    """Match Hub – displays all matches the logged-in player is involved in."""
    player = request.user  # Player IS the custom user model

    player_ct = ContentType.objects.get_for_model(Player)

    # Matches where the current player is the challenger
    as_challenger = Match.objects.filter(
        challenged_by_content_type=player_ct,
        challenged_by_object_id=player.pk,
    ).select_related('game')

    # Matches where the current player is the opponent
    as_opponent = Match.objects.filter(
        opponent_content_type=player_ct,
        opponent_object_id=player.pk,
    ).select_related('game')

    # Cancel expired pending matches created by this player
    expired_matches = Match.objects.filter(
        challenged_by_content_type=player_ct,
        challenged_by_object_id=player.pk,
        status=Match.Status.PENDING,
        played_at__lt=timezone.now(),
        opponent_object_id__isnull=True
    )
    for ext_match in expired_matches:
        ext_match.status = Match.Status.CANCELLED
        ext_match.save(update_fields=['status'])
        messages.warning(request, f"Your pending match for {ext_match.game.name} has expired and was cancelled.")

    matches = (as_challenger | as_opponent).exclude(status__in=[Match.Status.CANCELLED, Match.Status.COMPLETED, Match.Status.FINALIZED]).order_by('-created_at')

    # Check if user already has Ongoing/Confirmed matches
    busy_as_challenger = Match.objects.filter(
        challenged_by_content_type=player_ct,
        challenged_by_object_id=player.pk,
        status__in=[Match.Status.CONFIRMED, Match.Status.ONGOING]
    ).exists()

    busy_as_opponent = Match.objects.filter(
        opponent_content_type=player_ct,
        opponent_object_id=player.pk,
        status__in=[Match.Status.CONFIRMED, Match.Status.ONGOING]
    ).exists()

    can_join = not (busy_as_challenger or busy_as_opponent)

    # All pending open challenges in the future created by someone else
    potential_matches = Match.objects.filter(
        invite_type=Match.InviteType.OPEN_CHALLENGE,
        status=Match.Status.PENDING,
        played_at__gt=timezone.now()
    ).exclude(
        challenged_by_content_type=player_ct,
        challenged_by_object_id=player.pk
    ).select_related('game').order_by('played_at')

    # Match invites addressed to the current player
    match_invites = Match.objects.filter(
        invite_type=Match.InviteType.INVITE_ONLY,
        status=Match.Status.PENDING,
        invited_opponent=player
    ).select_related('game').order_by('created_at')

    context = {
        'matches': matches,
        'potential_matches': potential_matches,
        'match_invites': match_invites,
        'can_join': can_join,
        'now': timezone.now(),
    }

    return render(request, 'match_hub.html', context)

