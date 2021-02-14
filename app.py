from datetime import datetime
import random

import os
from pathlib import Path
from dotenv.main import resolve_nested_variables

from flask import Flask, json, jsonify
from flask import url_for, redirect, request
from flask_cors import CORS, cross_origin
import ndjson

import pickle
import logging

from dotenv import load_dotenv
from requests.api import head
import requests

from authlib.integrations.flask_client import OAuth
from models import db, Event, Game, Member

load_dotenv()

app = Flask(__name__)
app.app_context().push()

CORS(app, support_credentials=True)

app.secret_key = os.getenv("SECRET_KEY")

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("SQLALCHEMY_DATABASE_URI")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

app.config['LICHESS_CLIENT_ID'] =  os.getenv("LICHESS_CLIENT_ID")
app.config['LICHESS_CLIENT_SECRET'] = os.getenv("LICHESS_CLIENT_SECRET")
app.config['LICHESS_ACCESS_TOKEN_URL'] = 'https://oauth.lichess.org/oauth'
app.config['LICHESS_AUTHORIZE_URL'] = 'https://oauth.lichess.org/oauth/authorize'

db.init_app(app)


def initialize_mock_db():
    db.drop_all()
    db.create_all()

    league_members = ['joaopf', 'dodo900', 'gspenny', 'hiperlicious', 'MrUnseen', 'eduardodsp', 'fckoch', 'guischmitd']
    for member in league_members:
        m = Member(lichess_username=member,
                acl_username=member,
                acl_elo=random.randint(800, 1350),
                date_joined=datetime.now())

        db.session.add(m)

    members = Member.query.all()

    event = Event(
        start_date = datetime.now(),
        start_timestamp = datetime.now(),
        active = True,
        n_rounds = 1,
        rounds_deadline = datetime(2021, 1, 31),
        playoffs_method = {'top': 2},
        tiebreak_method = {'time': 5, 'increment': 3, 'rounds': 1},
        players = [m.acl_username for m in members],
        current_phase = 'playoffs'
    )

    db.session.add(event)
    db.session.commit()


initialize_mock_db()

oauth = OAuth(app)
oauth.register('lichess')

def validate_game(lichess_gamedata):
    member_names = [m.lichess_username for m in Member.query.all()]
    
    return lichess_gamedata['players']['white']['user']['name'] in member_names and \
           lichess_gamedata['players']['black']['user']['name'] in member_names


@app.route('/')
def main():
    
    return jsonify({'message': 'Hello!'})
    # return redirect(url_for('login'))

@app.route('/login')
def login():
    redirect_uri = url_for("authorize", _external=True)
    
    """
    If you need to append scopes to your requests, add the `scope=...` named argument
    to the `.authorize_redirect()` method. For admissible values refer to https://lichess.org/api#section/Authentication. 
    Example with scopes for allowing the app to read the user's email address:
    `return oauth.lichess.authorize_redirect(redirect_uri, scope="email:read")`
    """
    return oauth.lichess.authorize_redirect(redirect_uri, scopre="email:read")


@app.route('/authorize')
def authorize():
    token = oauth.lichess.authorize_access_token()

    bearer = token['access_token']
    headers = {'Authorization': f'Bearer {bearer}'}

    response = requests.get(f"https://lichess.org/api/account", headers=headers)

    redirect_uri = url_for('get_games', username=response.json()['username'])

    return redirect(redirect_uri)


@app.route('/games')
def get_games():
    username = request.args.get('username')
    headers = {'Accept': 'application/x-ndjson'}

    response = requests.get(f"https://lichess.org/api/games/user/{username}", headers=headers)
    all_games = (response.json(cls=ndjson.Decoder))

    league_members = ['joaopf', 'dodo900', 'gspenny', 'hiperlicious', 'MrUnseen', 'eduardodsp', 'fckoch', 'guischmitd']
    league_members.remove(username)

    league_games = []
    for game in all_games:
        white, black = None, None

        if 'user' in game['players']['white']:
            white = game['players']['white']['user']['id']

        if 'user' in game['players']['black']:
            black = game['players']['black']['user']['id']

        if white in league_members or black in league_members:
           league_games.append(game)

    return jsonify({'n_league_games': len(league_games), 'username': username, 'league_games': league_games})


@app.route('/game')
@cross_origin(supports_credentials=True)

def add_game():
    game_url = request.args.get('url')
    game_id = game_url.split('/')[-1][:8]  # Use only 8 first characters
    headers = {'Accept': 'application/json'}

    # TODO Validate input and update database accordingly
    response = requests.get(f"https://lichess.org/game/export/{game_id}", headers=headers)
    lichess_gamedata = response.json()

    outcome = lichess_gamedata['winner'] if 'winner' in lichess_gamedata else 'draw'
    game_data = dict(zip(['white', 'black'], [lichess_gamedata['players']['white']['user']['name'], lichess_gamedata['players']['black']['user']['name']]))
    
    game_data['winner'] = lichess_gamedata['players'][outcome]['user']['name'] if outcome != 'draw' else None
    game_data['timestamp'] = datetime.utcfromtimestamp(lichess_gamedata['createdAt'] * 1e-3)

    game_data['base_time'] = lichess_gamedata['clock']['initial']
    game_data['increment'] = lichess_gamedata['clock']['increment']
    
    if validate_game(lichess_gamedata):
        game = Game(date_played=game_data['timestamp'],
                    date_added=datetime.now(),
                    white=game_data['white'],
                    black=game_data['black'],
                    outcome=outcome,
                    winner=game_data['winner'],
                    time_base=game_data['base_time'],
                    time_increment=game_data['increment'],
                    lichess_gamedata=lichess_gamedata,
                    event=Event.query.first().id,
                    )
        
        db.session.add(game)
        db.session.commit()

        lichess_gamedata['valid'] = True
    
    else:
        lichess_gamedata['valid'] = False
    
    return jsonify(lichess_gamedata)