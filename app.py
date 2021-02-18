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
from models import db, Event, Game, Member, Fixture
from mock_db import initialize_mock_db
from db_ops import validate_game, add_game_to_db, update_acl_elo
import db_ops

import sys
import logging

load_dotenv()

log_dir = Path('./.logs')
log_dir.mkdir(exist_ok=True, parents=True)

log_path = log_dir / datetime.now().strftime('%Y%m%d.log')
logging.basicConfig(level=logging.DEBUG, filename=log_path, filemode='a',
                        format=f'[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s')

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.info('===== Log has been initialized. New run starts here. =====')

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

initialize_mock_db(db, app)

oauth = OAuth(app)
oauth.register('lichess')


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
    # Not currently used. Just for early api testing.
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


@app.route('/game', methods=['POST'])
@cross_origin(supports_credentials=True)
def add_game():
    # This endpoint will be called only after user confirmation on the frontend
    data = json.loads(request.data.decode())
    fixture_id = data['fixture_id']
    lichess_gamedata = data['data']
    validation_data = validate_game(fixture_id, lichess_gamedata)

    if all([v for k, v in validation_data.items()]):
        add_game_to_db(fixture_id, lichess_gamedata)
        update_acl_elo(fixture_id)

    else:
        logger.warn('Invalid game!')
        for k, v in validation_data.items():
            logger.warn(k, '=', v)
    
    return jsonify({'validation': validation_data, 'ranking': db_ops.get_ranking_data(), 'fixtures': db_ops.get_fixtures()})


@app.route('/ranking')
@cross_origin(supports_credentials=True)
def ranking():
    return jsonify(db_ops.get_ranking_data())


@app.route('/fixtures')
@cross_origin(supports_credentials=True)
def fixtures():
    return jsonify(db_ops.get_fixtures())
