from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline

from .models import Game, Match


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_team_based', 'is_active', 'scoring_unit', 'requires_duration')
    list_filter = ('is_team_based', 'is_active', 'requires_duration')
    search_fields = ('name',)
    list_editable = ('is_active',)


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('game', 'status', 'location', 'played_at', 'winner', 'created_at')
    list_filter = ('game', 'status', 'location')
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Match Info', {
            'fields': ('game', 'status', 'location', 'played_at', 'created_at'),
        }),
        ('Challenger', {
            'fields': (
                'challenged_by_content_type',
                'challenged_by_object_id',
            ),
        }),
        ('Opponent', {
            'fields': (
                'opponent_content_type',
                'opponent_object_id',
            ),
        }),
        ('Result', {
            'fields': (
                'score',
                'winner_content_type',
                'winner_object_id',
            ),
        }),
    )
