from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from players.models import Player, PlayerRating
from arena.models import Game


class LeaderboardAPITests(APITestCase):
    def setUp(self):
        # Create test users/players
        self.player1 = Player.objects.create_user(
            username="player1",
            email="p1@pilani.bits-pilani.ac.in",
            password="testpassword123",
            bits_id="2022A7PS0001G"
        )
        self.player2 = Player.objects.create_user(
            username="player2",
            email="p2@pilani.bits-pilani.ac.in",
            password="testpassword123",
            bits_id="2022A7PS0002G"
        )
        self.player3 = Player.objects.create_user(
            username="player3",
            email="p3@pilani.bits-pilani.ac.in",
            password="testpassword123",
            bits_id="2022A7PS0003G"
        )

        # Create test games
        self.game1 = Game.objects.create(
            name="Chess",
            is_team_based=False,
            is_active=True,
            scoring_unit="points"
        )
        self.game2 = Game.objects.create(
            name="Valorant",
            is_team_based=True,
            is_active=True,
            scoring_unit="rounds"
        )
        self.inactive_game = Game.objects.create(
            name="FIFA",
            is_team_based=False,
            is_active=False,
            scoring_unit="goals"
        )

        # Create ratings (Leaderboards)
        # For Chess: player1: 1500, player2: 1200, player3: 1600
        # Expected ranks: player3 (#1), player1 (#2), player2 (#3)
        self.rating1 = PlayerRating.objects.create(player=self.player1, game=self.game1, rating=1500.0)
        self.rating2 = PlayerRating.objects.create(player=self.player2, game=self.game1, rating=1200.0)
        self.rating3 = PlayerRating.objects.create(player=self.player3, game=self.game1, rating=1600.0)

        # For Valorant: player2: 2000, player3: 1800
        # Expected ranks: player2 (#1), player3 (#2)
        self.rating4 = PlayerRating.objects.create(player=self.player2, game=self.game2, rating=2000.0)
        self.rating5 = PlayerRating.objects.create(player=self.player3, game=self.game2, rating=1800.0)

    def test_get_all_leaderboards(self):
        """Test retrieving all active game leaderboards."""
        url = reverse('api:leaderboard-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should return a list of active games only (Chess and Valorant)
        data = response.data
        self.assertEqual(len(data), 2)
        
        # Verify first game (Chess) details and leaderboard sorting
        chess_data = next(item for item in data if item['game']['name'] == 'Chess')
        self.assertEqual(len(chess_data['leaderboard']), 3)
        # Check sorting and rank calculation
        self.assertEqual(chess_data['leaderboard'][0]['player']['username'], 'player3')
        self.assertEqual(chess_data['leaderboard'][0]['rank'], 1)
        self.assertEqual(chess_data['leaderboard'][1]['player']['username'], 'player1')
        self.assertEqual(chess_data['leaderboard'][1]['rank'], 2)
        self.assertEqual(chess_data['leaderboard'][2]['player']['username'], 'player2')
        self.assertEqual(chess_data['leaderboard'][2]['rank'], 3)

        # Verify second game (Valorant) details
        val_data = next(item for item in data if item['game']['name'] == 'Valorant')
        self.assertEqual(len(val_data['leaderboard']), 2)
        self.assertEqual(val_data['leaderboard'][0]['player']['username'], 'player2')
        self.assertEqual(val_data['leaderboard'][0]['rank'], 1)
        self.assertEqual(val_data['leaderboard'][1]['player']['username'], 'player3')
        self.assertEqual(val_data['leaderboard'][1]['rank'], 2)

    def test_get_leaderboard_by_path_param(self):
        """Test retrieving specific game leaderboard via URL path parameter."""
        url = reverse('api:leaderboard-detail', kwargs={'game_id': self.game1.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertEqual(data['game']['name'], 'Chess')
        self.assertEqual(len(data['leaderboard']), 3)
        self.assertEqual(data['leaderboard'][0]['player']['username'], 'player3')
        self.assertEqual(data['leaderboard'][0]['rank'], 1)

    def test_get_leaderboard_by_query_param(self):
        """Test retrieving specific game leaderboard via query parameter."""
        url = f"{reverse('api:leaderboard-list')}?game={self.game2.id}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertEqual(data['game']['name'], 'Valorant')
        self.assertEqual(len(data['leaderboard']), 2)
        self.assertEqual(data['leaderboard'][0]['player']['username'], 'player2')
        self.assertEqual(data['leaderboard'][0]['rank'], 1)

    def test_get_leaderboard_not_found(self):
        """Test retrieving a non-existent game's leaderboard returns 404."""
        url = reverse('api:leaderboard-detail', kwargs={'game_id': 9999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
