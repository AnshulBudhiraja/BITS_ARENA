from django.shortcuts import render, redirect, resolve_url
from django.contrib.auth import login, logout
from .forms import PlayerSignupForm, PlayerLoginForm
from django.contrib import messages
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType
from allauth.account.utils import perform_login
from arena.models import Match
from .models import Player, Team, PlayerRating


def signup_view(request):
    """Player registration using BITS ID."""
    if request.user.is_authenticated:
        return redirect('arena:home')

    form = PlayerSignupForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        player = form.save()
        messages.success(request, f'Welcome to BITS ARENA, {player.username}!')
        return perform_login(
            request, 
            player, 
            email_verification='none', # Bypasses email checks if using internal BITS ID
            redirect_url=resolve_url(request.GET.get('next', 'arena:home'))
        )

    return render(request, 'players/signup.html', {'form': form})


def login_view(request):
    """Player login using BITS ID + password."""
    if request.user.is_authenticated:
        return redirect('arena:home')

    form = PlayerLoginForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        player = form.get_player()
        return perform_login(
            request, 
            player, 
            email_verification='none', # Bypasses email checks if using internal BITS ID
            redirect_url=resolve_url(request.GET.get('next', 'arena:home'))
        )

    return render(request, 'players/login.html', {'form': form})


def logout_view(request):
    """Log out the current player — POST only for CSRF safety."""
    if request.method == 'POST':
        logout(request)
    return redirect('arena:home')   # home view will show welcome for unauthenticated


from django.contrib.auth.decorators import login_required

@login_required
def profile(request):
    """Player profile view showing stats, ratings, and match history (LEGACY)."""
    # Fetch all ratings for the current player, including game details
    ratings = request.user.ratings.select_related('game').all()
    
    # Attach global campus rankings to each rating
    for rating_obj in ratings:
        rating_obj.rank = PlayerRating.objects.filter(
            game=rating_obj.game, 
            rating__gt=rating_obj.rating
        ).count() + 1
    
    # --- Fetch Match History (LEGACY) ---
    player_ct = ContentType.objects.get_for_model(Player)
    team_ct = ContentType.objects.get_for_model(Team)
    user_team_ids = request.user.teams.values_list('id', flat=True)

    # Filter for matches where the user participated (as player or through a team)
    # only include finished/cancelled matches
    match_history = Match.objects.filter(
        (
            # Individual Participant
            Q(challenged_by_content_type=player_ct, challenged_by_object_id=request.user.id) |
            Q(opponent_content_type=player_ct, opponent_object_id=request.user.id)
        ) |
        (
            # Team Participant
            Q(challenged_by_content_type=team_ct, challenged_by_object_id__in=user_team_ids) |
            Q(opponent_content_type=team_ct, opponent_object_id__in=user_team_ids)
        )
    ).filter(
        status__in=[Match.Status.COMPLETED, Match.Status.FINALIZED, Match.Status.CANCELLED]
    ).select_related('game').order_by('-played_at', '-created_at')

    # Django templates don't support calling methods with arguments like get_outcome(player).
    # We pre-calculate these for the template.
    for m in match_history:
        m.outcome = m.get_outcome(request.user)
        m.opponent_display = m.get_opponent(request.user)
        m.display_score = m.get_display_score(request.user)

    context = {
        'player': request.user,
        'ratings': ratings,
        'matches': match_history,
    }
    return render(request, 'profile.html', context)

