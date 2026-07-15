from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from players.models import Player

from .forms import MatchCreateForm
from .models import Match
from .utils import updated_ratings


@login_required
def create_match_view(request):
    """
    Renders and handles the Create Match form.
    - Sets challenged_by = request.user (the Player instance).
    - Sets status = 'pending'.
    - If invite_type == 'invite_only', looks up the opponent by bits_id.
    - Redirects to match_hub on success.
    """
    form = MatchCreateForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        match = form.save(commit=False)

        # ── Set challenger ─────────────────────────────────────────────────
        player = request.user  # Player extends AbstractUser; IS the user
        player_ct = ContentType.objects.get_for_model(Player)
        match.challenged_by_content_type = player_ct
        match.challenged_by_object_id = player.pk

        # ── Force status to pending ────────────────────────────────────────
        match.status = Match.Status.PENDING

        # ── Resolve opponent for invite-only matches ───────────────────────
        opponent_username = form.cleaned_data.get('opponent_username', '').strip()
        if match.invite_type == Match.InviteType.INVITE_ONLY and opponent_username:
            try:
                opponent = Player.objects.get(username=opponent_username)
                match.invited_opponent = opponent
            except Player.DoesNotExist:
                form.add_error('opponent_username', 'No player found with that Username.')
                
                # Fetch games data for re-render
                from .models import Game
                import json
                games = Game.objects.all()
                games_data = {g.id: {'requires_duration': g.requires_duration, 'duration_unit': g.duration_unit, 'scoring_unit': g.scoring_unit, 'has_standard_scoring': g.has_standard_scoring} for g in games}
                return render(request, 'create_match.html', {'form': form, 'games_data': json.dumps(games_data)})

        match.save()
        
        # Add game to player's played games
        player.games.add(match.game)
        
        return redirect('arena:match_hub')

    from .models import Game
    import json
    games = Game.objects.all()
    games_data = {g.id: {'requires_duration': g.requires_duration, 'duration_unit': g.duration_unit, 'scoring_unit': g.scoring_unit, 'has_standard_scoring': g.has_standard_scoring} for g in games}

    return render(request, 'create_match.html', {
        'form': form,
        'games_data': json.dumps(games_data)
    })

@login_required
@require_POST
def join_match(request, match_id):
    """Allows a player to join an existing open challenge."""
    player = request.user
    player_ct = ContentType.objects.get_for_model(Player)

    # Check if user already has Ongoing/Confirmed matches
    busy_as_challenger = Match.objects.filter(
        challenged_by_content_type=player_ct,
        challenged_by_object_id=player.pk,
        status__in=[Match.Status.CONFIRMED, Match.Status.ONGOING, Match.Status.PENDING]
    ).exists()

    busy_as_opponent = Match.objects.filter(
        opponent_content_type=player_ct,
        opponent_object_id=player.pk,
        status__in=[Match.Status.CONFIRMED, Match.Status.ONGOING]
    ).exists()

    if busy_as_challenger or busy_as_opponent:
        messages.error(request, "You cannot join a new match while having one in Pending,Confirmed or Ongoing status.")
        return redirect('arena:match_hub')

    # Retrieve pending match
    match = get_object_or_404(
        Match, 
        pk=match_id, 
        status=Match.Status.PENDING
    )

    if match.invite_type == Match.InviteType.INVITE_ONLY and match.invited_opponent != player:
        messages.error(request, "You are not invited to this match.")
        return redirect('arena:match_hub')
    
    if match.invite_type == Match.InviteType.OPEN_CHALLENGE and match.invited_opponent is not None:
        messages.error(request, "This match is not available.")
        return redirect('arena:match_hub')

    # Prevent joining own match
    if match.challenged_by_content_type == player_ct and match.challenged_by_object_id == player.pk:
        messages.error(request, "You cannot join your own match.")
        return redirect('arena:match_hub')

    # Set opponent to the joining player and update status
    match.opponent = player
    match.status = Match.Status.CONFIRMED
    match.save()

    # Add game to player's played games
    player.games.add(match.game)

    messages.success(request, f"You successfully joined the {match.game.name} match!")
    return redirect('arena:match_hub')


@login_required
@require_POST
def cancel_match(request, match_id):
    """
    Cancels a Match directly if PENDING, or sets cancellation_requested_by if CONFIRMED.
    """
    match = get_object_or_404(Match, pk=match_id)
    player = request.user
    player_ct = ContentType.objects.get_for_model(Player)

    # Check if the player is involved in this match
    is_challenger = (match.challenged_by_content_type == player_ct and match.challenged_by_object_id == player.pk)
    is_opponent = (match.opponent_content_type == player_ct and match.opponent_object_id == player.pk)
    is_invited = (match.invite_type == Match.InviteType.INVITE_ONLY and match.invited_opponent == player)

    if not (is_challenger or is_opponent or is_invited):
        messages.error(request, "You are not involved in this match.")
        return redirect('arena:match_hub')

    if match.status == Match.Status.PENDING:
        match.status = Match.Status.CANCELLED
        match.save()
        messages.success(request, f"Match for {match.game.name} has been cancelled.")
    elif match.status == Match.Status.CONFIRMED:
        # Request Cancellation
        match.cancellation_requested_by = player
        match.save()
        messages.success(request, f"Cancellation request sent for the {match.game.name} match.")
    else:
        messages.error(request, "Match cannot be cancelled at this stage.")

    return redirect('arena:match_hub')


@login_required
@require_POST
def accept_cancellation(request, match_id):
    """
    Accepts a cancellation request from the other player.
    """
    match = get_object_or_404(Match, pk=match_id)
    player = request.user
    player_ct = ContentType.objects.get_for_model(Player)

    # Check if the player is involved in this match
    is_challenger = (match.challenged_by_content_type == player_ct and match.challenged_by_object_id == player.pk)
    is_opponent = (match.opponent_content_type == player_ct and match.opponent_object_id == player.pk)

    if not (is_challenger or is_opponent):
        messages.error(request, "You are not involved in this match.")
        return redirect('arena:match_hub')

    if match.status != Match.Status.CONFIRMED or not match.cancellation_requested_by:
        messages.error(request, "There is no pending cancellation request for this match.")
        return redirect('arena:match_hub')

    if match.cancellation_requested_by == player:
        messages.error(request, "You cannot accept your own cancellation request.")
        return redirect('arena:match_hub')

    # Status becomes cancelled without clearing requested_by 
    match.status = Match.Status.CANCELLED
    match.save()
    messages.success(request, f"Cancellation accepted. The match for {match.game.name} is cancelled.")

    return redirect('arena:match_hub')


@login_required
@require_POST
def start_match(request, match_id):
    """
    Initiates match start. First player to click sets `start_requested_by`.
    Second player to click transitions status to ONGOING and clears `start_requested_by`.
    """
    match = get_object_or_404(Match, pk=match_id)
    player = request.user
    player_ct = ContentType.objects.get_for_model(Player)

    # Check if the player is involved in this match
    is_challenger = (match.challenged_by_content_type == player_ct and match.challenged_by_object_id == player.pk)
    is_opponent = (match.opponent_content_type == player_ct and match.opponent_object_id == player.pk)

    if not (is_challenger or is_opponent):
        messages.error(request, "You are not involved in this match.")
        return redirect('arena:match_hub')

    if match.status != Match.Status.CONFIRMED:
        messages.error(request, "This match is not confirmed.")
        return redirect('arena:match_hub')

    from django.utils import timezone
    if match.played_at and match.played_at > timezone.now():
        messages.error(request, "You cannot start the match before its scheduled time.")
        return redirect('arena:match_hub')

    if match.start_requested_by is None:
        # First request
        match.start_requested_by = player
        match.save()
        messages.success(request, f"Start match request sent for the {match.game.name} match.")
    elif match.start_requested_by == player:
        messages.error(request, "You have already requested to start the match. Awaiting opponent.")
    else:
        # Second request
        match.start_requested_by = None
        match.status = Match.Status.ONGOING
        match.save()
        messages.success(request, f"The {match.game.name} match has started!")
        return redirect('arena:live_match', match_id=match.id)

    return redirect('arena:match_hub')


@login_required
def live_match_view(request, match_id):
    """
    Displays the live match dashboard for ONGOING matches.
    Handles mutual score submission logic per set.
    """
    match = get_object_or_404(Match, pk=match_id)
    player = request.user
    player_ct = ContentType.objects.get_for_model(Player)

    is_challenger = (match.challenged_by_content_type == player_ct and match.challenged_by_object_id == player.pk)
    is_opponent = (match.opponent_content_type == player_ct and match.opponent_object_id == player.pk)

    if not (is_challenger or is_opponent):
        messages.error(request, "You are not involved in this match.")
        return redirect('arena:match_hub')

    if match.status not in [Match.Status.ONGOING, Match.Status.COMPLETED]:
        messages.error(request, "This match is not active.")
        return redirect('arena:match_hub')

    from .forms import SetScoreForm

    game_has_sets = bool(match.game.requires_duration and match.game.duration_unit and match.game.duration_unit.lower() in ['set', 'sets'])
    num_sets = match.duration_unit_number if game_has_sets and match.duration_unit_number else 1

    if request.method == 'POST' and match.status == Match.Status.ONGOING:
        form = SetScoreForm(request.POST, target_score=match.scoring_unit_number)
        if form.is_valid():
            set_num = str(form.cleaned_data.get('set_number')) if game_has_sets else "1"
            c_score = form.cleaned_data.get('challenger_score')
            o_score = form.cleaned_data.get('opponent_score')
            
            c_claim = match.challenger_score_claim or {}
            o_claim = match.opponent_score_claim or {}

            if is_challenger:
                c_claim[set_num] = {"challenger": c_score, "opponent": o_score}
                match.challenger_score_claim = c_claim
            else:
                o_claim[set_num] = {"challenger": c_score, "opponent": o_score}
                match.opponent_score_claim = o_claim
                
            match.save()
            
            if set_num in (match.challenger_score_claim or {}) and set_num in (match.opponent_score_claim or {}):
                if match.challenger_score_claim[set_num] == match.opponent_score_claim[set_num]:
                    if match.score is None:
                        match.score = {}
                    
                    if 'sets' not in match.score and game_has_sets:
                        match.score['sets'] = {}
                        
                    if game_has_sets:
                        match.score['sets'][set_num] = match.challenger_score_claim[set_num]
                    else:
                        match.score = match.challenger_score_claim[set_num]
                        
                    match.save()
                    messages.success(request, f"Set {set_num} verified!" if game_has_sets else "Score verified!")
                    
                    if game_has_sets:
                        sets = match.score.get('sets', {})
                        c_wins = sum(1 for s in sets.values() if s['challenger'] > s['opponent'])
                        o_wins = sum(1 for s in sets.values() if s['opponent'] > s['challenger'])
                        
                        majority = (num_sets // 2) + 1
                        if c_wins >= majority or o_wins >= majority or len(sets) >= num_sets:
                            match.status = Match.Status.COMPLETED
                            match.save()
                            msg = "Match finished by majority win!" if (c_wins >= majority or o_wins >= majority) else "All required sets verified."
                            messages.success(request, msg)
                    else:
                        match.status = Match.Status.COMPLETED
                        match.save()
                        messages.success(request, "Score verified! Match is officially completed!")

                else: 
                    messages.error(request, f"Mismatch in scores for Set {set_num}! Claims reset. Discuss and resubmit.")
                    c_claim = match.challenger_score_claim
                    o_claim = match.opponent_score_claim
                    if set_num in c_claim: del c_claim[set_num]
                    if set_num in o_claim: del o_claim[set_num]
                    # Assigning back to trigger JSONField change detection
                    match.challenger_score_claim = c_claim
                    match.opponent_score_claim = o_claim
                    match.save()
            else:
                messages.success(request, f"Set {set_num} locked. Waiting on opponent." if game_has_sets else "Score locked. Waiting on opponent.")
            
            return redirect('arena:live_match', match_id=match.id)

    sets_ui_data = []
    c_claim = match.challenger_score_claim or {}
    o_claim = match.opponent_score_claim or {}
    
    # Safely extract verified scores
    verified_scores = {}
    if match.score:
        if game_has_sets:
            verified_scores = match.score.get('sets', {})
        elif isinstance(match.score, dict) and 'challenger' in match.score:
            verified_scores = {"1": match.score}

    # Calculate current standing to check for majority
    c_wins = sum(1 for s in verified_scores.values() if s['challenger'] > s['opponent'])
    o_wins = sum(1 for s in verified_scores.values() if s['opponent'] > s['challenger'])
    majority = (num_sets // 2) + 1
    match_decided = (c_wins >= majority or o_wins >= majority)

    for i in range(1, num_sets + 1):
        set_key = str(i)
        is_verified = set_key in verified_scores
        
        # If match decided, don't show further sets that haven't been recorded
        if match_decided and not is_verified:
            continue
            
        my_claim = c_claim.get(set_key) if is_challenger else o_claim.get(set_key)
        their_claim = o_claim.get(set_key) if is_challenger else c_claim.get(set_key)
        
        waiting_on_me = my_claim is None and not is_verified
        waiting_on_opponent = my_claim is not None and their_claim is None and not is_verified
        
        form_instance = None
        if waiting_on_me:
            form_instance = SetScoreForm(
                initial={'set_number': i} if game_has_sets else {},
                target_score=match.scoring_unit_number
            )
            
        sets_ui_data.append({
            'set_number': i,
            'is_verified': is_verified,
            'waiting_on_me': waiting_on_me,
            'waiting_on_opponent': waiting_on_opponent,
            'verified_score': verified_scores.get(set_key),
            'form': form_instance
        })

    return render(request, 'live_match.html', {
        'match': match,
        'game_has_sets': game_has_sets,
        'is_challenger': is_challenger,
        'sets_ui_data': sets_ui_data,
    })


@login_required
@require_POST
def end_match_view(request, match_id):
    """
    Finalizes the match, updates player ratings, and sets the match status to FINALIZED.
    """
    match = get_object_or_404(Match, pk=match_id)

    if match.status != Match.Status.COMPLETED:
        messages.error(request, "Match is not ready to be finalized.")
        return redirect('arena:live_match', match_id=match.id)

    # ── Determine Winner and Scores ────────────────────────────────────────
    game_has_sets = bool(match.game.requires_duration and match.game.duration_unit and match.game.duration_unit.lower() in ['set', 'sets'])
    
    winner = None
    loser = None
    winner_score = 0
    loser_score = 0

    if game_has_sets:
        sets = match.score.get('sets', {})
        challenger_sets = 0
        opponent_sets = 0
        for s_num, s_data in sets.items():
            c_p = s_data.get('challenger', 0)
            o_p = s_data.get('opponent', 0)
            if c_p > o_p:
                challenger_sets += 1
            elif o_p > c_p:
                opponent_sets += 1
        
        if challenger_sets >= opponent_sets:
            winner, loser = match.challenged_by, match.opponent
            winner_score, loser_score = challenger_sets, opponent_sets
        else:
            winner, loser = match.opponent, match.challenged_by
            winner_score, loser_score = opponent_sets, challenger_sets
    else:
        c_score = match.score.get('challenger', 0)
        o_score = match.score.get('opponent', 0)
        if c_score >= o_score:
            winner, loser = match.challenged_by, match.opponent
            winner_score, loser_score = c_score, o_score
        else:
            winner, loser = match.opponent, match.challenged_by
            winner_score, loser_score = o_score, c_score

    # ── Update Ratings ─────────────────────────────────────────────────────
    from players.models import PlayerRating
    
    # Calculate new ratings
    # For non-set games, we treat set wins as 1 for winner and 0 for loser
    if game_has_sets:
        sw_winner = winner_score
        sw_loser = loser_score
    else:
        sw_winner = 1
        sw_loser = 0

    new_winner_rating, new_loser_rating = updated_ratings(
        match.id, winner, loser, 32, sw_winner, sw_loser
    )

    # Apply new ratings to PlayerRating objects
    # (Note: updated_ratings already fetches the objects and might save the loser's floor flag)
    winner_rating_obj = PlayerRating.objects.get(player=winner, game=match.game)
    loser_rating_obj = PlayerRating.objects.get(player=loser, game=match.game)

    change_in_winner_rating = new_winner_rating - winner_rating_obj.rating
    change_in_loser_rating = new_loser_rating - loser_rating_obj.rating
    
    winner_rating_obj.rating = new_winner_rating
    loser_rating_obj.rating = new_loser_rating
    
    winner_rating_obj.save()
    loser_rating_obj.save()

    # ── Finalize Match ─────────────────────────────────────────────────────
    match.status = Match.Status.FINALIZED
    match.winner = winner
    match.save()

    messages.success(request, f"Match finalized! Ratings updated for {winner} and {loser}.")
    context = {
        'match': match,
        'change_in_winner_rating': change_in_winner_rating,
        'change_in_loser_rating': change_in_loser_rating,
        'new_winner_rating': new_winner_rating,
        'new_loser_rating': new_loser_rating,
        # Minimal flags for template integrity
        'is_challenger': (match.challenged_by_object_id == request.user.id),
        'game_has_sets': bool(match.game.requires_duration and match.game.duration_unit and match.game.duration_unit.lower() in ['set', 'sets']),
    }
    return render(request, 'live_match.html', context)

