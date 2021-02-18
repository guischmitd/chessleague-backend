from models import Member, Event, Game, Fixture
from itertools import combinations
from datetime import datetime
import requests

import logging
logger = logging.getLogger(__name__)

def initialize_mock_db(db, app):
    # Drop all tables and recreate them
    db.drop_all()
    db.create_all()

    # Initialize members table
    logger.info('Initializing members table...')
    league_members = ['joaopf', 'dodo900', 'gspenny', 'hiperlicious', 'mrunseen', 'eduardodsp', 'guischmitd']
    lichess_members_data = requests.post('https://lichess.org/api/users', data=','.join(league_members)).json()

    for member in league_members:
        lichess_member_data = [data for data in lichess_members_data if data['id'] == member.lower()][0]
        if not Member.query.get(lichess_member_data['id']):
            m = Member(lichess_id=member,
                    lichess_username=lichess_member_data['username'],
                    lichess_rapid_elo=lichess_member_data['perfs']['rapid']['rating'],
                    lichess_blitz_elo=lichess_member_data['perfs']['blitz']['rating'],
                    acl_username=lichess_member_data['username'],
                    acl_elo=1000,
                    date_joined=datetime.now())

            db.session.add(m)
    db.session.commit()

    members = Member.query.all()

    # Initialize an event
    logger.info('Initializing Event...')
    event = Event(
        start_date = datetime.now(),
        start_timestamp = datetime.now(),
        active = True,
        n_rounds = 2,
        rounds_deadline = datetime(2021, 2, 8),
        playoffs_method = {'top': 2},
        tiebreak_method = {'base': 300, 'increment': 3},
        rounds_time_format = {'base': 600, 'increment': 0},
        players = league_members,
        current_phase = 'playoffs'
    )

    db.session.add(event)
    db.session.commit()

    # TODO Initialize rounds
    
    # initialize all fixtures
    for r in range(1, event.n_rounds + 1):
        logger.info(f'Creating fixtures for round {r}...')
        for m_a, m_b in set(combinations(league_members, 2)):
            fixture1 = Fixture(
                round_id=r,
                event_id=event.id,
                white=m_a,
                black=m_b,
                deadline=event.rounds_deadline,
                time_base=event.rounds_time_format['base'],
                time_increment=event.rounds_time_format['increment'],
            )
            
            fixture2 = Fixture(
                round_id=r,
                event_id=event.id,
                white=m_b,
                black=m_a,
                deadline=event.rounds_deadline,
                time_base=event.rounds_time_format['base'],
                time_increment=event.rounds_time_format['increment'],
            )
            
            db.session.add(fixture1)
            db.session.add(fixture2)
    
    logger.info('Done initializing mock database.')

    db.session.commit()
    