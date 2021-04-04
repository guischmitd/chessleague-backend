from models import Member, Event, Game, Fixture, User
from itertools import combinations
from datetime import datetime, timedelta
import requests

import logging
logger = logging.getLogger(__name__)

def initialize_mock_db(db, app):
    # Drop all tables and recreate them
    db.drop_all()
    db.create_all()

    # Initialize members table
    logger.info('Initializing Members table...')
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

    # Initialize an event
    logger.info('Initializing Event...')
    event = Event(
        start_date = datetime.now(),
        start_timestamp = datetime.now(),
        active = True,
        n_rounds = 2,
        rounds_duration = [15, 30],  # in days
        playoffs_method = {'top': 2},  # Unused for now
        tiebreak_method = {'base': 300, 'increment': 3}, # Unused for now
        rounds_time_format = [{'base': 600, 'increment': 0}, {'base': 300, 'increment': 3}],
        players = league_members,
    )

    # Create the fixtures for each
    for r in range(1, event.n_rounds + 1):
        logger.info(f'\tCreating round {r}...')
        
        round_deadline = event.start_date + timedelta(event.rounds_duration[r-1])
        round_time_base = event.rounds_time_format[r-1]['base']
        round_time_increment = event.rounds_time_format[r-1]['increment']
        
        for m_a, m_b in set(combinations(league_members, 2)):
            fixture_wb = Fixture(
                round_number=r,
                event_id=event.id,
                white=m_a,
                black=m_b,
                deadline=round_deadline,
                time_base=round_time_base,
                time_increment=round_time_increment,
            )

            fixture_bw = Fixture(
                round_number=r,
                event_id=event.id,
                white=m_b,
                black=m_a,
                deadline=round_deadline,
                time_base=round_time_base,
                time_increment=round_time_increment,
            )
            
            event.fixtures.append(fixture_wb)
            event.fixtures.append(fixture_bw)
            
    logger.info('Done initializing mock database.')

    db.session.add(event)
    db.session.commit()
    