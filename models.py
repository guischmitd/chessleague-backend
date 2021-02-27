from flask_login.mixins import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSON, TIMESTAMP

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__='users'
    id = db.Column(db.String, primary_key=True)  # User Google ID
    
    acl_username = db.Column(db.String)
    acl_elo = db.Column(db.Integer)

    lichess_id = db.Column(db.String)
    lichess_connected = db.Column(db.Boolean)
    lichess_username = db.Column(db.String)
    lichess_url = db.Column(db.String)
    lichess_rapid_elo = db.Column(db.Integer)
    lichess_blitz_elo = db.Column(db.Integer)
    
    date_joined = db.Column(db.Date)
    email = db.Column(db.String)
    profile_picture = db.Column(db.String)
    google_name = db.Column(db.String)

    # @property
    # def is_active(self):
    #     # override UserMixin property which always returns true
    #     # return the value of the active column instead
    #     return self.active

    def __repr__(self):
        return f'<User {self.acl_username}(AELO {self.acl_elo} / Member since {self.date_joined} / Lichess {"Not connected!" if not self.lichess_connected else self.lichess_username})>'    

class Event(db.Model):
    __tablename__='events'
    id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.Date)
    start_timestamp = db.Column(TIMESTAMP)
    active = db.Column(db.Boolean)
    
    n_rounds = db.Column(db.Integer)
    rounds_duration = db.Column(JSON)  # List of length n_rounds. Number of days before round deadline
    rounds_time_format = db.Column(JSON)  # List of length n_rounds containing a dict with keys 'base' and 'increment' for each round
    
    playoffs_method = db.Column(JSON)  # Unused for now
    tiebreak_method = db.Column(JSON)  # Unused for now

    players = db.Column(JSON)

    def __repr__(self):
        return f'<Event {self.id}({self.n_rounds} rounds starting {self.start_date})>'


class Game(db.Model):
    __tablename__='games'
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

    event_id = db.Column(db.Integer, db.ForeignKey('events.id'))

    def __repr__(self):
        return f'<Game(Played on {self.date_played} - {self.white} (W) vs. {self.black} (B) - {self.time_base//60}+{self.time_increment}{" - Event " + str(self.event) if self.event else ""})>'


class Member(db.Model):
    __tablename__='members'
    lichess_id = db.Column(db.String, primary_key=True)
    acl_username = db.Column(db.String)
    acl_elo = db.Column(db.Integer)

    lichess_username = db.Column(db.String)
    lichess_rapid_elo = db.Column(db.Integer)
    lichess_blitz_elo = db.Column(db.Integer)
    
    date_joined = db.Column(db.Date)


class Fixture(db.Model):
    __tablename__='fixtures'
    id = db.Column(db.Integer, primary_key=True)
    deadline = db.Column(db.Date)
    round_number = db.Column(db.Integer)
    
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    event = db.relationship('Event', backref=db.backref('fixtures', lazy=False))

    white = db.Column(db.String)
    black = db.Column(db.String)
    game_id = db.Column(db.String)
    outcome = db.Column(db.String)

    time_base = db.Column(db.Integer)  # in seconds
    time_increment = db.Column(db.Integer)  # in seconds

    def __repr__(self):
        return f'<Fixture({self.white} (w) vs. {self.black} (b). {self.time_base//60}+{self.time_increment})>'