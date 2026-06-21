from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from players.models import Player, PlayerRating
from arena.models import Game, Match


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

        # Test non-existent game ID returns 404
        url = f"{reverse('api:leaderboard-list')}?game=9999"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class MatchCreateAPITests(APITestCase):
    def setUp(self):
        # Create users
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

        # Create active games (one set-based, one non-set-based)
        self.game_non_set = Game.objects.create(
            name="Chess",
            is_team_based=False,
            is_active=True,
            scoring_unit="points"
        )
        self.game_set = Game.objects.create(
            name="Tennis",
            is_team_based=False,
            is_active=True,
            scoring_unit="points",
            duration_unit="sets",
            requires_duration=True
        )
        self.inactive_game = Game.objects.create(
            name="FIFA",
            is_team_based=False,
            is_active=False,
            scoring_unit="goals"
        )

        self.url = reverse('api:match-create')

    def test_anonymous_user_cannot_create_match(self):
        """Verify anonymous user gets 403 (or 401)."""
        response = self.client.post(self.url, data={})
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_create_open_challenge_success(self):
        """Verify authenticated player can create an open challenge match."""
        self.client.force_authenticate(user=self.player1)
        payload = {
            "game": self.game_non_set.id,
            "invite_type": "open_challenge",
            "location": "Gymg"
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify response structure
        data = response.data
        self.assertEqual(data['status'], 'pending')
        self.assertEqual(data['invite_type'], 'open_challenge')
        self.assertEqual(data['location'], 'Gymg')
        self.assertEqual(data['challenged_by']['username'], 'player1')
        self.assertIsNone(data['opponent'])
        self.assertIsNone(data['invited_opponent'])

        # Verify database record
        match_id = data['id']
        match_obj = Match.objects.get(id=match_id)
        self.assertEqual(match_obj.challenged_by, self.player1)
        self.assertIn(self.game_non_set, self.player1.games.all())

    def test_create_invite_only_success(self):
        """Verify authenticated player can create an invite-only match with another player."""
        self.client.force_authenticate(user=self.player1)
        payload = {
            "game": self.game_non_set.id,
            "invite_type": "invite_only",
            "opponent_bits_id": self.player2.bits_id,
            "location": "VK QT lawns"
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify response structure
        data = response.data
        self.assertEqual(data['status'], 'pending')
        self.assertEqual(data['invite_type'], 'invite_only')
        self.assertEqual(data['invited_opponent']['username'], 'player2')

        # Verify database record
        match_obj = Match.objects.get(id=data['id'])
        self.assertEqual(match_obj.invited_opponent, self.player2)

    def test_create_invite_only_self_failure(self):
        """Verify players cannot invite themselves to a match."""
        self.client.force_authenticate(user=self.player1)
        payload = {
            "game": self.game_non_set.id,
            "invite_type": "invite_only",
            "opponent_bits_id": self.player1.bits_id,
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('opponent_bits_id', response.data)
        self.assertEqual(response.data['opponent_bits_id'][0], "You cannot invite yourself to a match.")

    def test_create_invite_only_missing_opponent_id(self):
        """Verify invite-only match validation requires opponent BITS ID."""
        self.client.force_authenticate(user=self.player1)
        payload = {
            "game": self.game_non_set.id,
            "invite_type": "invite_only",
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('opponent_bits_id', response.data)

    def test_create_invite_only_invalid_opponent_id(self):
        """Verify invite-only match fails with non-existent opponent BITS ID."""
        self.client.force_authenticate(user=self.player1)
        payload = {
            "game": self.game_non_set.id,
            "invite_type": "invite_only",
            "opponent_bits_id": "999999999"
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('opponent_bits_id', response.data)

    def test_set_based_duration_unit_validation(self):
        """Verify that duration unit numbers (sets) must be an odd number."""
        self.client.force_authenticate(user=self.player1)
        
        # Even number of sets should fail validation
        payload = {
            "game": self.game_set.id,
            "invite_type": "open_challenge",
            "duration_unit_number": 4
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('duration_unit_number', response.data)
        self.assertTrue("must be an odd number" in response.data['duration_unit_number'][0])

        # Odd number of sets should succeed
        payload["duration_unit_number"] = 3
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_match_for_inactive_game_failure(self):
        """Verify match creation fails if game is not active."""
        self.client.force_authenticate(user=self.player1)
        payload = {
            "game": self.inactive_game.id,
            "invite_type": "open_challenge"
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('game', response.data)


from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, TestCase as DjangoTestCase
from api.serializers import MatchJoinSerializer

class MatchJoinSerializerTests(DjangoTestCase):
    def setUp(self):
        self.factory = RequestFactory()
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
        self.game = Game.objects.create(
            name="Chess",
            is_active=True,
            scoring_unit="points"
        )
        
        player_ct = ContentType.objects.get_for_model(Player)
        self.match = Match.objects.create(
            game=self.game,
            status=Match.Status.PENDING,
            invite_type=Match.InviteType.OPEN_CHALLENGE,
            challenged_by_content_type=player_ct,
            challenged_by_object_id=self.player1.pk
        )

    def test_join_open_challenge_success(self):
        request = self.factory.post('/dummy-url/')
        request.user = self.player2
        
        serializer = MatchJoinSerializer(
            instance=self.match, 
            data={}, 
            context={'request': request}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated_match = serializer.save()
        
        self.assertEqual(updated_match.opponent, self.player2)
        self.assertEqual(updated_match.status, Match.Status.CONFIRMED)
        self.assertIn(self.game, self.player2.games.all())

    def test_join_own_match_failure(self):
        request = self.factory.post('/dummy-url/')
        request.user = self.player1
        
        serializer = MatchJoinSerializer(
            instance=self.match, 
            data={}, 
            context={'request': request}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("You cannot join your own match.", serializer.errors['non_field_errors'])

    def test_join_invited_only_wrong_opponent_failure(self):
        player_ct = ContentType.objects.get_for_model(Player)
        invite_only_match = Match.objects.create(
            game=self.game,
            status=Match.Status.PENDING,
            invite_type=Match.InviteType.INVITE_ONLY,
            challenged_by_content_type=player_ct,
            challenged_by_object_id=self.player1.pk,
            invited_opponent=self.player3
        )
        
        request = self.factory.post('/dummy-url/')
        request.user = self.player2
        
        serializer = MatchJoinSerializer(
            instance=invite_only_match, 
            data={}, 
            context={'request': request}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("You are not invited to this match.", serializer.errors['non_field_errors'])

