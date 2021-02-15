from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSON, TIMESTAMP

db = SQLAlchemy()

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.Date)
    start_timestamp = db.Column(TIMESTAMP)
    active = db.Column(db.Boolean)
    
    n_rounds = db.Column(db.Integer)
    rounds_deadline = db.Column(db.Date)
    rounds_time_format = db.Column(JSON)
    
    playoffs_method = db.Column(JSON)
    tiebreak_method = db.Column(JSON)

    players = db.Column(JSON)
    
    current_phase = db.Column(db.String)
    

class Game(db.Model):
    id = db.Column(db.String, primary_key=True)
    date_played = db.Column(db.Date)
    date_added = db.Column(db.Date)
    
    white = db.Column(db.String)
    black = db.Column(db.String)
    outcome = db.Column(db.String)
    winner = db.Column(db.String)
    
    time_base = db.Column(db.Integer)  # in seconds
    time_increment = db.Column(db.Integer)  # in seconds

    lichess_gamedata = db.Column(JSON)

    event = db.Column(db.Integer)

    
class Member(db.Model):
    lichess_id = db.Column(db.String, primary_key=True)
    acl_username = db.Column(db.String)
    acl_elo = db.Column(db.Integer)

    lichess_username = db.Column(db.String)
    lichess_rapid_elo = db.Column(db.Integer)
    lichess_blitz_elo = db.Column(db.Integer)
    
    date_joined = db.Column(db.Date)


class Fixture(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    deadline = db.Column(db.Date)
    event_id = db.Column(db.Integer)
    round_id = db.Column(db.Integer)

    white = db.Column(db.String)
    black = db.Column(db.String)
    game_id = db.Column(db.String)
    outcome = db.Column(db.String)

    time_base = db.Column(db.Integer)  # in seconds
    time_increment = db.Column(db.Integer)  # in seconds

    def __repr__(self):
        return f'<Fixture({self.white} (w) vs. {self.black} (b). {self.time_base//60}+{self.time_increment})>'