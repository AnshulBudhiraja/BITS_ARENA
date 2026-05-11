from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Player, PlayerRating, Team


@admin.register(Player)
class PlayerAdmin(UserAdmin):
    """Admin for the custom Player user model."""
    fieldsets = UserAdmin.fieldsets + (
        ('Games', {'fields': ('games',)}),
    )
    filter_horizontal = UserAdmin.filter_horizontal + ('games',)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')


@admin.register(PlayerRating)
class PlayerRatingAdmin(admin.ModelAdmin):
    list_display = ('player', 'game', 'rating', 'has_crossed_elo_floor')
    list_filter = ('game', 'has_crossed_elo_floor')
    search_fields = ('player__username',)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('team_name', 'game')
    list_filter = ('game',)
    search_fields = ('team_name',)
    filter_horizontal = ('players',)
