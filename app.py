# Standard packages
import os
import sys
import pickle
import logging
from datetime import datetime
from pathlib import Path
import unidecode

# Web utilities
import ndjson
import requests
from dotenv import load_dotenv
from dotenv.main import resolve_nested_variables

from flask import Flask, json, jsonify, session
from flask import url_for, redirect, request
from flask_cors import CORS, cross_origin

import ndjson

import pickle
import logging

from dotenv import load_dotenv
from requests.api import head
import base64

from authlib.integrations.flask_client import OAuth
from models import db, Event, Game, Member, Fixture, User
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)

# Authentication/Authorization imports
from oauthlib.oauth2 import WebApplicationClient
from authlib.integrations.flask_client import OAuth
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

# Database internal imports
from models import User, db, Event, Game, Member, Fixture
from mock_db import initialize_mock_db
from db_ops import get_user, create_user, validate_game, add_game_to_db, update_acl_elo
import db_ops

# Initialize environment, log and flask app
load_dotenv()

log_dir = Path('./.logs')
log_dir.mkdir(exist_ok=True, parents=True)

log_path = log_dir / datetime.now().strftime('%Y%m%d.log')

app = Flask(__name__)
app.app_context().push()
CORS(app, support_credentials=True)
login_manager = LoginManager()

app.secret_key = os.getenv("SECRET_KEY") or os.urandom(128)
app.logger.debug(f'Secret Key: {app.secret_key}')

# filehandler = logging.FileHandler(log_path)

# app.logger.addHandler(handler)
# app.logger.addHandler(filehandler)
app.logger.setLevel(logging.DEBUG)

app.logger.info('===== Log has been initialized. New run starts here. =====')


# Configure flask app with environment variables
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("SQLALCHEMY_DATABASE_URI")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

app.config['LICHESS_CLIENT_ID'] =  os.getenv("LICHESS_CLIENT_ID")
app.config['LICHESS_CLIENT_SECRET'] = os.getenv("LICHESS_CLIENT_SECRET")
app.config['LICHESS_ACCESS_TOKEN_URL'] = 'https://oauth.lichess.org/oauth'
app.config['LICHESS_AUTHORIZE_URL'] = 'https://oauth.lichess.org/oauth/authorize'

app.secret_key = os.getenv("SECRET_KEY") or os.urandom(24)

login_manager = LoginManager()
login_manager.init_app(app)

# Initialize SQL Database
db.init_app(app)
login_manager.init_app(app)

app.logger.debug(f'WERKZEUG_RUN_MAIN = {os.getenv("WERKZEUG_RUN_MAIN")}')

if os.environ.get("WERKZEUG_RUN_MAIN") is None:
    app.logger.info('Initializing database...')
    input_games_path = Path('test_data/acl1_gamelist.json')
    initialize_mock_db(db, app, input_games= input_games_path if input_games_path.exists() else None)


# OAuth setup (lichess and google)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", None)
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", None)
GOOGLE_DISCOVERY_URL = (
    "https://accounts.google.com/.well-known/openid-configuration"
)
client = WebApplicationClient(GOOGLE_CLIENT_ID)

def get_google_provider_cfg():
    # TODO Add error handling in case google API returns a failure
    return requests.get(GOOGLE_DISCOVERY_URL).json()


@login_manager.user_loader
def load_user(user_id):
    return get_user(user_id)

oauth = OAuth(app)
oauth.register('lichess')

# API Routes
@app.route('/')
def main():
    response = (
                "<h3>Welcome to the backend!</h3>"
                "<p>There's actually nothing here, fellow aowgher.</p>"
                "<p>Maybe you meant to go <a href={}>here</a>?</p>".format('http://localhost:3000')
            )
    if current_user.is_authenticated:
        response += "<p>Current user: <a href={}>{}</a> logged in with the email: {}</p>".format(current_user.lichess_url,
                                                                                                current_user.username, 
                                                                                                current_user.email)
    return response


@app.route('/debug')
def debug():
    data = {'current_user': current_user.json() if current_user.is_authenticated else None,
            'test_decode': unidecode.unidecode('François')}
    
    return jsonify(data)


@app.route('/connect_lichess')
def connect_lichess():
    # Not currently used. Lichess connection might be better handled by frontend
    app.logger.debug('Accessing connect_lichess endpoint')
    redirect_uri = url_for("authorize_lichess", _external=True)
    app.logger.debug(f'Redirecting to {redirect_uri}')

    """
    If you need to append scopes to your requests, add the `scope=...` named argument
    to the `.authorize_redirect()` method. For admissible values refer to https://lichess.org/api#section/Authentication. 
    Example with scopes for allowing the app to read the user's email address:
    `return oauth.lichess.authorize_redirect(redirect_uri, scope="email:read")`
    """
    return oauth.lichess.authorize_redirect(redirect_uri, scope="email:read")


@app.route('/authorize_lichess')
def authorize_lichess():
    # Not currently used. Lichess authorization might be better handled by frontend
    token = oauth.lichess.authorize_access_token()

    bearer = token['access_token']
    headers = {'Authorization': f'Bearer {bearer}'}

    response = requests.get(f"https://lichess.org/api/account", headers=headers)

    # db_ops.update_user_lichess_data(current_user.id, response.json())

    return jsonify({'lichess_data': response.json()})


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


@app.route('/game', methods=['POST', 'OPTIONS'])
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
        app.logger.warn('Invalid game!')
        for k, v in validation_data.items():
            app.logger.warn('{k} = {v}')
    
    return jsonify({'validation': validation_data, 'ranking': db_ops.get_ranking_data(), 'fixtures': db_ops.get_fixtures()})


@app.route('/ranking')
@cross_origin(supports_credentials=True)
def ranking():
    return jsonify(db_ops.get_ranking_data())


@app.route('/fixtures')
@cross_origin(supports_credentials=True)
def fixtures():
    return jsonify(db_ops.get_fixtures())


@app.route('/login', methods=['POST', 'OPTIONS'])
@cross_origin(supports_credentials=True)
def login():
    payload = json.loads(request.data)
    gtoken = payload['gtoken']
    user_data = validate_google_JWT(gtoken)

    if user_data:
        logout_user()
        user = User.query.get(user_data['sub'])

        if user:
            login_user(user)
            status = 'existing_user_login'

        else:
            app.logger.debug(f'User {user_data["sub"]} is not registered. Creating new user')
            name_parts = user_data['name'].split(' ')
            username = ''.join([part[0] for part in name_parts[:-1]] + [name_parts[-1]]).lower()
            username = unidecode.unidecode(username)
            user = db_ops.create_user(**{'id': user_data["sub"], 'lichess_connected': False, 
                                         'date_joined': datetime.now(), 'email': user_data['email'], 'username': username,
                                         'google_name': user_data['name'], 'profile_picture': user_data['picture'], 
                                         'aelo': 1000})
            
            status = 'new_user_registered'

        res = login_user(user)

    else:
        # Invalid token
        status = 'invalid_google_token'
        res = False

    return jsonify({'login_status': status, 'current_user': current_user.json(), 'login_success': res})


@app.route('/logout', methods=['POST', 'OPTIONS'])
@cross_origin(supports_credentials=True)
def logout():
    result = logout_user()
    app.logger.debug(result)
    return jsonify({'logout_result': result, 'current_user': current_user if not result else None})


def validate_google_JWT(gtoken):
    try:
        # Specify the CLIENT_ID of the app that accesses the backend:
        idinfo = id_token.verify_oauth2_token(gtoken.encode('utf-8'), google_requests.Request(), os.getenv("FRONTEND_GOOGLE_CLIENT_ID"))
        
        # Or, if multiple clients access the backend server:
        # idinfo = id_token.verify_oauth2_token(token, requests.Request())
        # if idinfo['aud'] not in [CLIENT_ID_1, CLIENT_ID_2, CLIENT_ID_3]:
        #     raise ValueError('Could not verify audience.')

        # If auth request is from a G Suite domain:
        # if idinfo['hd'] != GSUITE_DOMAIN_NAME:
        #     raise ValueError('Wrong hosted domain.')

        # ID token is valid. Get the user's Google Account ID from the decoded token.
        app.logger.debug('Valid token for user ' + idinfo['sub'])
        return idinfo
        
    except ValueError:
        # Invalid token
        app.logger.debug('Invalid Token')
        return False


if __name__ == "__main__":
    # use_reloader=False prevents flask from running twice in debug mode
    app.run(debug=True, use_reloader=True)
    
    # # Generate certificates and add authority to chrome so you can run flask in https
    # # https://stackoverflow.com/questions/7580508/getting-chrome-to-accept-self-signed-localhost-certificate
    # app.run(debug=True, ssl_context=(".cert/localhost.crt", ".cert/localhost.key"))
