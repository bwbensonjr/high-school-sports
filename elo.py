import math

class Elo:
    def __init__(
            self,
            teams=None,
            k=20,
            home_field=50,
            rating_mean=1505,
    ):
        self.ratings = {}
        self.k = k
        self.home_field = home_field
        self.rating_mean = rating_mean
        if teams:
            for team_name in teams:
                self.add_team(team_name)

    def add_team(self, team_name, initial_rating=1500):
        self.ratings[team_name] = initial_rating

    def team_rating(self, team_name):
        rating = self.ratings[team_name]
        return rating

    def set_rating(self, team_name, new_rating):
        self.ratings[team_name] = new_rating

    def elo_difference(self, home_team, away_team):
        home_elo = self.team_rating(home_team)
        away_elo = self.team_rating(away_team)
        elo_diff = away_elo - (home_elo + self.home_field)
        return elo_diff

    def home_win_prob(self, home_team, away_team):
        elo_diff = self.elo_difference(home_team, away_team)
        expected_home = 1 / (1 + 10 ** (elo_diff/400))
        return expected_home
    
    def point_spread(self, home_team, away_team):
        elo_diff = self.elo_difference(home_team, away_team)
        spread = -(elo_diff / 25)
        return spread
    
    def update_ratings(self, home_team, home_score, away_team, away_score):
        if home_score > away_score:
            result_home = 1
        elif away_score > home_score:
            result_home = 0
        else:
            result_home = 0.5
            
        expected_home = self.home_win_prob(home_team, away_team)
        forecast_delta = result_home - expected_home

        score_diff = abs(home_score - away_score)
        score_multiplier = math.log(score_diff + 1)

        elo_change = self.k * score_multiplier * forecast_delta
        new_home_elo = self.team_rating(home_team) + elo_change
        new_away_elo = self.team_rating(away_team) - elo_change
        self.set_rating(home_team, new_home_elo)
        self.set_rating(away_team, new_away_elo)

        return new_home_elo, new_away_elo

    def regress_towards_mean(self, regress_mult=0.33):
        """Regress all of the ratings towards a historic mean."""
        for team in self.ratings:
            old_rating = self.team_rating(team)
            rating_adjustment = (
                (self.rating_mean - old_rating) * regress_mult
            )
            new_rating = old_rating + rating_adjustment
            self.set_rating(team, new_rating)
