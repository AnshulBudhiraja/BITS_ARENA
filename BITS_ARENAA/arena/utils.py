import math
from players.models import PlayerRating
from .models import Match

def updated_ratings(match_id, winner, loser, k_factor, sets_won_by_winner, sets_won_by_loser):
    """
    Revised ELO algorithm with set-based resistance and per-set MoV weighting.
    """
    ELO_FLOOR = 600
    MAX_WIN = 50
    MAX_LOSS = 35

    # Fetch fresh match and game data
    match = Match.objects.get(pk=match_id)
    game = match.game
    
    # Get PlayerRating objects
    winner_rating_obj = PlayerRating.objects.get_or_create(player=winner, game=game)[0]
    loser_rating_obj = PlayerRating.objects.get_or_create(player=loser, game=game)[0]

    winner_match_rating = winner_rating_obj.rating
    loser_match_rating = loser_rating_obj.rating

    # 1. Resistance Calculation (BWP/BLP)
    max_possible_loser_sets = sets_won_by_winner - 1
    
    if max_possible_loser_sets == 0:
        bwp = 25
        blp = -20
    else:
        loser_resistance_ratio = sets_won_by_loser / max_possible_loser_sets
        bwp = 25 - (10 * loser_resistance_ratio)
        blp = -20 + (10 * loser_resistance_ratio)

    # 2. Expectation Calculation
    expected_winner = 1 / (1 + 10 ** ((loser_match_rating - winner_match_rating) / 400))

    scaled_BWP = bwp * (2 * (1 - expected_winner))
    scaled_BLP = blp * (2 * (1 - expected_winner))

    # 3. Per-Set Rating Calculation
    total_sets_played = sets_won_by_winner + sets_won_by_loser
    winner_set_sum = 0
    loser_set_sum = 0
    
    # We iterate over verified sets in the match score
    sets = match.score.get('sets', {})
    
    if not sets:
        # Standard match (no sets recorded in 'sets' key)
        # We treat the final match score as a single set
        c_score = match.score.get('challenger', 0)
        o_score = match.score.get('opponent', 0)
        
        # Calculate MoV for the overall match
        mov = max(1, abs(c_score - o_score))
        mov_multiplier = 1.0 if mov == 1 else 1 + (math.log(mov) / 2)
        
        # In a single set match, total_sets_played should be 1
        rating_per_set = (k_factor * (1 - expected_winner)) * mov_multiplier
        
        # Since 'winner' is passed as the overall winner, they won this "set"
        winner_set_sum = rating_per_set
        loser_set_sum = -rating_per_set
    else:
        # Complex set-based match
        for s_data in sets.values():
            c_p = s_data.get('challenger', 0)
            o_p = s_data.get('opponent', 0)
            
            # Determine who won this specific set
            set_winner_is_match_winner = False
            # If overall winner is challenger
            if match.challenged_by == winner:
                if c_p > o_p: set_winner_is_match_winner = True
            else:
                if o_p > c_p: set_winner_is_match_winner = True
            
            # Calculate MoV for this set
            mov = max(1, abs(c_p - o_p))
            mov_multiplier = 1.0 if mov == 1 else 1 + (math.log(mov) / 2)
            
            # Rating calculation for this set (using match expectations)
            # Divided by total sets played as requested
            rating_per_set = ((k_factor * (1 - expected_winner)) * mov_multiplier) / total_sets_played
            
            if set_winner_is_match_winner:
                winner_set_sum += rating_per_set
                loser_set_sum -= rating_per_set
            else:
                winner_set_sum -= rating_per_set
                loser_set_sum += rating_per_set

    # 4. Final Change Calculation
    raw_winner_change = round(scaled_BWP + winner_set_sum)
    raw_loser_change = round(scaled_BLP + loser_set_sum)

    # 5. Apply Caps
    winner_change = min(MAX_WIN, raw_winner_change)
    loser_change = max(-MAX_LOSS, raw_loser_change)

    # 6. Glass Floor Logic
    intended_loser_rating = loser_match_rating + loser_change
    
    if not loser_rating_obj.has_crossed_elo_floor:
        updated_loser_rating = loser_match_rating
        if intended_loser_rating >= ELO_FLOOR:
            loser_rating_obj.has_crossed_elo_floor = True
            loser_rating_obj.save()
    else:
        updated_loser_rating = intended_loser_rating

    updated_winner_rating = winner_match_rating + winner_change

    return updated_winner_rating, updated_loser_rating
