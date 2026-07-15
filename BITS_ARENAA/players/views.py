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
    """Player registration."""
    if request.user.is_authenticated:
        return redirect('arena:home')

    form = PlayerSignupForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        player = form.save()
        messages.success(request, f'Welcome to BITS ARENA, {player.username}!')
        return perform_login(
            request, 
            player, 
            email_verification='none', # Bypasses email checks
            redirect_url=resolve_url(request.GET.get('next', 'arena:home'))
        )

    return render(request, 'players/signup.html', {'form': form})


def login_view(request):
    """Player login."""
    if request.user.is_authenticated:
        return redirect('arena:home')

    form = PlayerLoginForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        player = form.get_player()
        return perform_login(
            request, 
            player, 
            email_verification='none', # Bypasses email checks
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


@login_required
def optional_password_view(request):
    """View to optionally set a password and modify auto-generated username after social signup."""
    from django.contrib.auth import update_session_auth_hash
    from .forms import SocialSignupCompletionForm

    if request.method == 'POST':
        if 'skip' in request.POST:
            return redirect('arena:home')
        
        form = SocialSignupCompletionForm(request.POST, user=request.user)
        if form.is_valid():
            # Update username
            request.user.username = form.cleaned_data['username']
            request.user.save()

            # Update password if provided
            pwd = form.cleaned_data.get('password')
            if pwd:
                request.user.set_password(pwd)
                request.user.save()
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Your profile has been updated and password set!')
            else:
                messages.success(request, 'Your username has been updated!')

            return redirect('arena:home')
    else:
        form = SocialSignupCompletionForm(user=request.user, initial={'username': request.user.username})

    return render(request, 'players/optional_password.html', {'form': form})


@login_required
def password_settings_view(request):
    """View to change password using either old password or OTP."""
    from django.contrib.auth import update_session_auth_hash
    from .forms import PasswordChangeOldPasswordForm, PasswordChangeOTPForm

    # Handle form submissions
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'old_password':
            old_pwd_form = PasswordChangeOldPasswordForm(request.POST, user=request.user)
            otp_form = PasswordChangeOTPForm(user=request.user)
            if old_pwd_form.is_valid():
                request.user.set_password(old_pwd_form.cleaned_data['new_password'])
                request.user.save()
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Your password has been changed successfully.')
                return redirect('players:profile')
        elif action == 'otp':
            old_pwd_form = PasswordChangeOldPasswordForm(user=request.user)
            otp_form = PasswordChangeOTPForm(request.POST, user=request.user)
            if otp_form.is_valid():
                request.user.set_password(otp_form.cleaned_data['new_password'])
                request.user.save()
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Your password has been changed successfully using OTP.')
                
                # Clear the OTP from cache to prevent reuse
                from django.core.cache import cache
                cache.delete(f'otp_pwd_{request.user.id}')
                
                return redirect('players:profile')
    else:
        old_pwd_form = PasswordChangeOldPasswordForm(user=request.user)
        otp_form = PasswordChangeOTPForm(user=request.user)

    context = {
        'old_pwd_form': old_pwd_form,
        'otp_form': otp_form,
        'has_usable_password': request.user.has_usable_password(),
    }
    return render(request, 'players/password_change.html', context)


@login_required
def send_otp_view(request):
    """AJAX endpoint to generate and send OTP for password change."""
    import random
    from django.core.cache import cache
    from django.core.mail import send_mail
    from django.http import JsonResponse
    
    if request.method == 'POST':
        otp = str(random.randint(100000, 999999))
        
        # Save OTP to cache (expires in 10 minutes = 600 seconds)
        cache.set(f'otp_pwd_{request.user.id}', otp, 600)
        
        # Send email
        subject = 'BITS ARENA - Password Change OTP'
        message = f'Your one-time password to change your BITS ARENA password is: {otp}\n\nThis code is valid for 10 minutes.'
        send_mail(
            subject,
            message,
            None, # Uses DEFAULT_FROM_EMAIL
            [request.user.email],
            fail_silently=False,
        )
        
        return JsonResponse({'status': 'success', 'message': 'OTP sent to your email.'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=400)
