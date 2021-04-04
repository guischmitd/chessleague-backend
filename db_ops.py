from models import Member, User, Event, Game, Fixture, db
from datetime import datetime
from elo import get_rating_deltas
import sys
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stdout))

def create_user(**kwargs):
    new_user = User(**kwargs)
    db.session.add(new_user)
    db.session.commit()
    return new_user.id


def get_user(unique_id):
    return User.query.get(unique_id)


def update_user_lichess_data(user_id, lichess_data):
    logger.debug('Updating user data')
    user = get_user(user_id)
    user.lichess_id = lichess_data['id']
    user.lichess_connected = True
    user.lichess_username = lichess_data['username']
    user.lichess_url = lichess_data['url']
    user.acl_username = lichess_data['username']
    user.lichess_rapid_elo = lichess_data['perfs']['rapid']['rating']
    user.lichess_blitz_elo = lichess_data['perfs']['blitz']['rating']

    db.session.commit()


def validate_game(fixture_id, lichess_gamedata):
    # Check if fixture has already been fulfilled
    fixture = Fixture.query.get(fixture_id)
    
    not_fulfilled = not bool(fixture.game_id)

    # Check if game is already uploaded
    new_game = not bool(Game.query.get(lichess_gamedata['id']))
    
    # Check if users are in current event
    valid_members = lichess_gamedata['players']['white']['user']['id'] == fixture.white \
                    and  lichess_gamedata['players']['black']['user']['id'] == fixture.black

    # Check if game is within deadline
    within_deadline = datetime.date(datetime.utcfromtimestamp(lichess_gamedata['createdAt'] * 1e-3)) <= fixture.deadline
    
    time_base, time_increment = lichess_gamedata['clock']['initial'], lichess_gamedata['clock']['increment']
    
    # Check if correct time format was used
    correct_time_format = fixture.time_base == time_base and fixture.time_increment == time_increment
    
    validation_data = {}
    for k, v in zip(['not_fulfilled', 'valid_members', 'new_game', 'within_deadline', 'correct_time_format'], 
                    [not_fulfilled, valid_members, new_game, within_deadline, correct_time_format]):
        validation_data[k] = v

    return validation_data


def add_game_to_db(fixture_id, lichess_gamedata):
    # Function will be called only after validation
    fixture = Fixture.query.get(fixture_id)

    # Parse lichess_gamedata and build Game row to add to the database
    date_played = datetime.utcfromtimestamp(lichess_gamedata['createdAt'] * 1e-3)
    outcome = lichess_gamedata['winner'] if 'winner' in lichess_gamedata else 'draw'
    white = lichess_gamedata['players']['white']['user']['id']
    black = lichess_gamedata['players']['black']['user']['id']
    winner = lichess_gamedata['players'][outcome]['user']['id'] if outcome != 'draw' else None

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
                event_id=fixture.event_id,
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

def get_ranking_data():
    logger.debug('Gathering ranking data...')
    ranking_data = []

    for member in Member.query.all():
        games_required = len(list(Fixture.query.filter_by(white=member.lichess_id)) + 
                             list(Fixture.query.filter_by(black=member.lichess_id)))

        games_as_white = list(Game.query.filter_by(white=member.lichess_id))
        games_as_black = list(Game.query.filter_by(black=member.lichess_id))
        games_played = games_as_white + games_as_black

        wins = len([g for g in games_as_white if g.outcome == 'white'] + 
                   [g for g in games_as_black if g.outcome == 'black'])
        
        draws = len([g for g in games_played if g.outcome == 'draw'])

        losses = len(games_played) - wins - draws

        logger.debug(f'{member.lichess_id} - {member.acl_elo} - {wins}W-{draws}D-{losses}L')
        player_data = {}
        player_data['id'] = member.lichess_id
        player_data['username'] = member.acl_username
        player_data['wins'] = wins
        player_data['losses'] = losses
        player_data['draws'] = draws
        player_data['aelo'] = member.acl_elo
        player_data['games_played'] = len(games_as_black + games_as_white)
        player_data['games_required'] = games_required
        ranking_data.append(player_data)
    
    return ranking_data

def get_fixtures():
    fixtures = []
    
    for f in Fixture.query.all():

        fixture = {'id': f.id, 'white': f.white, 'black': f.black, 
                   'game_id': f.game_id, 'outcome': f.outcome, 
                   'event_id': f.event_id, 'round_id': f.round_number,
                   'deadline': f.deadline, 
                   'time_base': f.time_base, 'time_increment': f.time_increment}
        
        
        fixture['winner_name'] = fixture[f.outcome] if f.outcome in ['white', 'black'] else f.outcome

        fixtures.append(fixture)
    
    return fixtures
