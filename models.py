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
    
    playoffs_method = db.Column(JSON)
    tiebreak_method = db.Column(JSON)

    players = db.Column(JSON)
    
    current_phase = db.Column(db.String)
    

class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date_played = db.Column(db.Date)
    date_added = db.Column(db.Date)
    
    white = db.Column(db.String)
    black = db.Column(db.String)
    outcome = db.Column(db.String)
    winner = db.Column(db.String)
    
    time_base = db.Column(db.Integer)
    time_increment = db.Column(db.Integer)

    lichess_gamedata = db.Column(JSON)
    event = db.Column(db.Integer)

    
class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    acl_username = db.Column(db.String)
    lichess_username = db.Column(db.String)
    
    date_joined = db.Column(db.Date)
    
    acl_elo = db.Column(db.Numeric)