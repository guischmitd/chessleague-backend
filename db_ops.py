from models import Member, Event, Game, Fixture, db
from datetime import datetime
from elo import get_rating_deltas

def validate_game(fixture_id, lichess_gamedata):
    # Check if fixture has already been fulfilled
    fixture = Fixture.query.get(fixture_id)
    
    not_fulfilled = not bool(fixture.game_id)

    # Check if game is already uploaded
    print('Game is', Game.query.get(lichess_gamedata['id']))
    new_game = not bool(Game.query.get(lichess_gamedata['id']))
    
    # Check if users are in current event
    valid_members = lichess_gamedata['players']['white']['user']['id'] == fixture.white \
                    and  lichess_gamedata['players']['black']['user']['id'] == fixture.black

    # Check if game is within deadline
    within_deadline = datetime.date(datetime.utcfromtimestamp(lichess_gamedata['createdAt'] * 1e-3)) <= fixture.deadline
    
    time_base, time_increment = lichess_gamedata['clock']['initial'], lichess_gamedata['clock']['increment']
    
    # Check if correct time format was used
    correct_time_format = fixture.time_base == time_base and fixture.time_increment == time_increment
    for k, v in zip(['not_fulfilled', 'valid_members', 'new_game', 'within_deadline', 'correct_time_format'], 
        [not_fulfilled, valid_members, new_game, within_deadline, correct_time_format]):
        print(k, '=', v)

    return not_fulfilled and valid_members and new_game and within_deadline and correct_time_format


def add_game_to_db(fixture_id, lichess_gamedata):
    # Function will be called only after validation
    fixture = Fixture.query.get(fixture_id)

    # Parse lichess_gamedata and build Game row to add to the database
    date_played = datetime.utcfromtimestamp(lichess_gamedata['createdAt'] * 1e-3)
    outcome = lichess_gamedata['winner'] if 'winner' in lichess_gamedata else 'draw'
    white = lichess_gamedata['players']['white']['user']['name']
    black = lichess_gamedata['players']['black']['user']['name']
    winner = lichess_gamedata['players'][outcome]['user']['name'] if outcome != 'draw' else None

    game = Game(id=lichess_gamedata['id'],
                lichess_gamedata=lichess_gamedata,
                date_played=date_played,
                date_added=datetime.now(),
                white=white,
                black=black,
                outcome=outcome,
                winner=winner,
                time_base=lichess_gamedata['clock']['initial'],
                time_increment=lichess_gamedata['clock']['increment'],
                event=fixture.event_id,
                )

    fixture.game_id = game.id
    fixture.outcome = outcome

    db.session.add(game)
    db.session.commit()


def update_acl_elo(fixture_id):
    fixture = Fixture.query.get(fixture_id)
    game = Game.query.get(fixture.game_id)

    white = Member.query.get(game.white)
    black = Member.query.get(game.black)
    white_delta, black_delta = get_rating_deltas(white.acl_elo, black.acl_elo, game.outcome)

    new_white_elo, new_black_elo = white.acl_elo + white_delta, black.acl_elo + black_delta
    white.acl_elo = new_white_elo
    black.acl_elo = new_black_elo

    db.session.commit()

