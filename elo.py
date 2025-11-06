import math

class Elo:
    """
    Elo rating system for calculating team rankings and win probabilities.

    The Elo rating system assigns numerical ratings to teams and updates them based on
    game results. Higher-rated teams are expected to win more often, and ratings change
    based on whether outcomes match expectations.

    Attributes:
        ratings (dict): Dictionary mapping team names to their current Elo ratings.
        k (float): K-factor determining the maximum rating change per game.
        home_field (float): Home field advantage in Elo rating points.
        spread_factor (float): Divisor for converting Elo differences to point spreads.
        rating_mean (float): Historical mean rating for regression purposes.
    """

    def __init__(
            self,
            teams=None,
            k=30,
            home_field=50,
            spread_factor=25,
            rating_mean=1505,
    ):
        """
        Initialize the Elo rating system.

        Args:
            teams (list, optional): List of team names to initialize with default ratings.
                If None, teams can be added later using add_team().
            k (float, optional): K-factor controlling rating volatility. Higher values mean
                larger rating changes per game. Default is 20.
            home_field (float, optional): Home field advantage in Elo rating points. Added to
                the home team's rating when calculating win probabilities. Default of 50 points
                translates to approximately 57% win probability for equally-rated teams.
            spread_factor (float, optional): Divisor for converting Elo rating differences to
                predicted point/goal spreads. Should be adjusted based on sport scoring levels:
                - Lower values (e.g., 15-20) for high-scoring sports like football/basketball
                - Higher values (e.g., 35-40) for low-scoring sports like soccer/field hockey
                Default is 25.
            rating_mean (float, optional): Historical mean rating used for regression between
                seasons. Default is 1505.
        """
        self.ratings = {}
        self.k = k
        self.home_field = home_field
        self.spread_factor = spread_factor
        self.rating_mean = rating_mean
        if teams:
            for team_name in teams:
                self.add_team(team_name)

    def add_team(self, team_name, initial_rating=1500):
        """
        Add a new team to the rating system.

        Args:
            team_name (str): Name of the team to add.
            initial_rating (float, optional): Starting Elo rating for the team. Default is 1500.
        """
        self.ratings[team_name] = initial_rating

    def team_rating(self, team_name):
        """
        Get the current Elo rating for a team.

        Args:
            team_name (str): Name of the team.

        Returns:
            float: Current Elo rating of the team.
        """
        rating = self.ratings[team_name]
        return rating

    def set_rating(self, team_name, new_rating):
        """
        Set a team's Elo rating to a specific value.

        Args:
            team_name (str): Name of the team.
            new_rating (float): New Elo rating to assign.
        """
        self.ratings[team_name] = new_rating

    def elo_difference(self, home_team, away_team):
        """
        Calculate the Elo rating difference between away and home teams.

        The home team receives a bonus equal to home_field advantage before comparison.

        Args:
            home_team (str): Name of the home team.
            away_team (str): Name of the away team.

        Returns:
            float: Elo difference (away_elo - (home_elo + home_field)). Positive values
                favor the away team, negative values favor the home team.
        """
        home_elo = self.team_rating(home_team)
        away_elo = self.team_rating(away_team)
        elo_diff = away_elo - (home_elo + self.home_field)
        return elo_diff

    def home_win_prob(self, home_team, away_team):
        """
        Calculate the probability that the home team wins.

        Uses the standard Elo formula: 1 / (1 + 10^(elo_diff/400))

        Args:
            home_team (str): Name of the home team.
            away_team (str): Name of the away team.

        Returns:
            float: Probability of home team victory (0.0 to 1.0).
        """
        elo_diff = self.elo_difference(home_team, away_team)
        expected_home = 1 / (1 + 10 ** (elo_diff/400))
        return expected_home

    def point_spread(self, home_team, away_team):
        """
        Calculate the predicted point/goal spread for a matchup.

        Converts Elo rating difference to an estimated score differential. Positive values
        indicate the home team is favored to win by that margin.

        Args:
            home_team (str): Name of the home team.
            away_team (str): Name of the away team.

        Returns:
            float: Predicted point/goal spread. Positive means home team favored,
                negative means away team favored.
        """
        elo_diff = self.elo_difference(home_team, away_team)
        spread = -(elo_diff / self.spread_factor)
        return spread
    
    def update_ratings(self, home_team, home_score, away_team, away_score):
        """
        Update team ratings based on a completed game result.

        Calculates rating changes using the Elo formula with margin of victory adjustment.
        The magnitude of rating change depends on:
        - The difference between actual and expected outcome
        - The margin of victory (logarithmic scaling)
        - The K-factor

        Args:
            home_team (str): Name of the home team.
            home_score (float): Home team's score.
            away_team (str): Name of the away team.
            away_score (float): Away team's score.

        Returns:
            tuple: (new_home_elo, new_away_elo) - Updated ratings for both teams.
        """
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
        """
        Regress all team ratings towards the historical mean.

        Used between seasons to account for roster changes, coaching changes, and
        other factors that cause ratings to drift from their true values over time.

        Args:
            regress_mult (float, optional): Fraction of the difference between current
                rating and mean to regress (0.0 to 1.0). Default is 0.33, meaning each
                team moves 33% of the way toward the mean.
        """
        for team in self.ratings:
            old_rating = self.team_rating(team)
            rating_adjustment = (
                (self.rating_mean - old_rating) * regress_mult
            )
            new_rating = old_rating + rating_adjustment
            self.set_rating(team, new_rating)

    @staticmethod
    def calculate_mae(predicted, actual):
        """
        Calculate Mean Absolute Error between predicted and actual values.

        Args:
            predicted (array-like): Predicted values
            actual (array-like): Actual values

        Returns:
            float: Mean absolute error
        """
        errors = [abs(p - a) for p, a in zip(predicted, actual)]
        return sum(errors) / len(errors) if errors else 0.0

    @staticmethod
    def calculate_rmse(predicted, actual):
        """
        Calculate Root Mean Squared Error between predicted and actual values.

        Args:
            predicted (array-like): Predicted values
            actual (array-like): Actual values

        Returns:
            float: Root mean squared error
        """
        squared_errors = [(p - a) ** 2 for p, a in zip(predicted, actual)]
        mse = sum(squared_errors) / len(squared_errors) if squared_errors else 0.0
        return math.sqrt(mse)

    def evaluate_predictions(self, games_df):
        """
        Evaluate prediction accuracy for completed games.

        Calculates error metrics comparing predicted point spreads to actual
        outcomes. Only evaluates games with valid prediction and outcome data.

        Args:
            games_df (DataFrame): DataFrame with columns "pred_point_spread" and
                "actual_point_spread"

        Returns:
            dict: Dictionary with error metrics:
                - "mae": Mean Absolute Error
                - "rmse": Root Mean Squared Error
                - "count": Number of games evaluated
        """
        # Filter for games with valid predictions and outcomes
        valid_games = games_df[
            games_df["pred_point_spread"].notna() &
            games_df["actual_point_spread"].notna()
        ]

        if len(valid_games) == 0:
            return {"mae": 0.0, "rmse": 0.0, "count": 0}

        predicted = valid_games["pred_point_spread"].tolist()
        actual = valid_games["actual_point_spread"].tolist()

        return {
            "mae": self.calculate_mae(predicted, actual),
            "rmse": self.calculate_rmse(predicted, actual),
            "count": len(valid_games)
        }
