from datetime import datetime
import random

import os
from pathlib import Path
from dotenv.main import resolve_nested_variables

from flask import Flask, json, jsonify
from flask import url_for, redirect, request
from flask_cors import CORS, cross_origin
from flask_login import LoginManager
import google.oauth2.credentials
import google_auth_oauthlib.flow

import ndjson

import pickle
import logging

from dotenv import load_dotenv
from requests.api import head
import requests
import base64

from authlib.integrations.flask_client import OAuth
from models import db, Event, Game, Member, Fixture, User
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
login_manager = LoginManager()

app.secret_key = os.getenv("SECRET_KEY") or os.urandom(128)
logger.debug(f'Secret Key: {app.secret_key}')

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("SQLALCHEMY_DATABASE_URI")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

app.config['LICHESS_CLIENT_ID'] =  os.getenv("LICHESS_CLIENT_ID")
app.config['LICHESS_CLIENT_SECRET'] = os.getenv("LICHESS_CLIENT_SECRET")
app.config['LICHESS_ACCESS_TOKEN_URL'] = 'https://oauth.lichess.org/oauth'
app.config['LICHESS_AUTHORIZE_URL'] = 'https://oauth.lichess.org/oauth/authorize'

db.init_app(app)
login_manager.init_app(app)

if os.environ.get("WERKZEUG_RUN_MAIN") == "false":
    logger.info('Initializing database...')
    initialize_mock_db(db, app)

oauth = OAuth(app)
oauth.register('lichess')


@app.route('/')
def main():
    
    return (
        "<h3>Welcome to the backend!</h3>"
        "<p>There's actually nothing here, fellow aowgher.</p>"
        "<p>Maybe you meant to go <a href={}>here</a>?</p>".format('http://localhost:3000')
    )
    # return redirect(url_for('login'))

@app.route('/connect_lichess')
def connect_lichess():
    redirect_uri = url_for("authorize_lichess", _external=True)
    
    """
    If you need to append scopes to your requests, add the `scope=...` named argument
    to the `.authorize_redirect()` method. For admissible values refer to https://lichess.org/api#section/Authentication. 
    Example with scopes for allowing the app to read the user's email address:
    `return oauth.lichess.authorize_redirect(redirect_uri, scope="email:read")`
    """
    return oauth.lichess.authorize_redirect(redirect_uri, scope="email:read")


@app.route('/authorize_lichess')
def authorize_lichess():
    token = oauth.lichess.authorize_access_token()

    bearer = token['access_token']
    headers = {'Authorization': f'Bearer {bearer}'}

    response = requests.get(f"https://lichess.org/api/account", headers=headers)

    # redirect_uri = url_for('get_games', username=response.json()['username'])

    return jsonify({'session_data': session, 'lichess_data': response.json()})

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
        logger.warn('Invalid game!')
        for k, v in validation_data.items():
            logger.warn('{k} = {v}')
    
    return jsonify({'validation': validation_data, 'ranking': db_ops.get_ranking_data(), 'fixtures': db_ops.get_fixtures()})


@app.route('/ranking')
@cross_origin(supports_credentials=True)
def ranking():
    return jsonify(db_ops.get_ranking_data())


@app.route('/fixtures')
@cross_origin(supports_credentials=True)
def fixtures():
    return jsonify(db_ops.get_fixtures())


# @app.route('/login', methods=['GET', 'POST', 'OPTIONS'])
# def login():
#     token = request.args.get('token')
#     redirect_uri = request.args.get('redirect_uri')

#     user_registered = False  # Check on database

#     if user_registered:
#         # Do login stuff
#         return redirect(redirect_uri)
#     else:
#         return redirect(f'/signup')


# @app.route('/signup')
# def signup():
#     # Use the client_secret.json file to identify the application requesting
#     # authorization. The client ID (from that file) and access scopes are required.
#     flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
#         'google_client_secret.json',
#         scopes=['https://www.googleapis.com/auth/drive.metadata.readonly'])

#     # Indicate where the API server will redirect the user after the user completes
#     # the authorization flow. The redirect URI is required. The value must exactly
#     # match one of the authorized redirect URIs for the OAuth 2.0 client, which you
#     # configured in the API Console. If this value doesn't match an authorized URI,
#     # you will get a 'redirect_uri_mismatch' error.
#     flow.redirect_uri = "http://localhost:3000"

#     # Generate URL for request to Google's OAuth 2.0 server.
#     # Use kwargs to set optional request parameters.
#     authorization_url, state = flow.authorization_url(
#         # Enable offline access so that you can refresh an access token without
#         # re-prompting the user for permission. Recommended for web server apps.
#         access_type='offline',
#         # Enable incremental authorization. Recommended as a best practice.
#         include_granted_scopes='true')

#     print("Authorization returned:", '\n', state, '\n', authorization_url)

#     return redirect(authorization_url) # jsonify({"hey dude": "ready to signup?"})


@app.route('/login/<string:gtoken>')
@cross_origin(supports_credentials=True)
def login(gtoken):
    # header.body.signature
    # gtoken = b'eyJhbGciOiJSUzI1NiIsImtpZCI6ImUxYWMzOWI2Y2NlZGEzM2NjOGNhNDNlOWNiYzE0ZjY2ZmFiODVhNGMiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJhY2NvdW50cy5nb29nbGUuY29tIiwiYXpwIjoiODUyNzY3MTI5ODY5LXZnczhtNmt0cGF0MWI0MmFkdjY0azNncHNxc3BxcDE2LmFwcHMuZ29vZ2xldXNlcmNvbnRlbnQuY29tIiwiYXVkIjoiODUyNzY3MTI5ODY5LXZnczhtNmt0cGF0MWI0MmFkdjY0azNncHNxc3BxcDE2LmFwcHMuZ29vZ2xldXNlcmNvbnRlbnQuY29tIiwic3ViIjoiMTA0MDE1MTcxOTc1ODk0OTY3NjU2IiwiZW1haWwiOiJndWlzY2htaXRkQGdtYWlsLmNvbSIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJhdF9oYXNoIjoiMklaTmdleDFsRUlIa3NjM2tZNk9RQSIsIm5hbWUiOiJHdWlsaGVybWUgQmFyYcO6bmEgU2NobWl0ZCIsInBpY3R1cmUiOiJodHRwczovL2xoMy5nb29nbGV1c2VyY29udGVudC5jb20vYS0vQU9oMTRHaGNneFpJRE1sUFVSZWEyanoxR3JURjhCUkVKWi1zUEx1YnFwWVFMUT1zOTYtYyIsImdpdmVuX25hbWUiOiJHdWlsaGVybWUiLCJmYW1pbHlfbmFtZSI6IkJhcmHDum5hIFNjaG1pdGQiLCJsb2NhbGUiOiJlbiIsImlhdCI6MTYxNzQ1Mjk3OSwiZXhwIjoxNjE3NDU2NTc5LCJqdGkiOiIyZGFlODU4YzYzNzFiNDJjOWYxMThkMGE1ODY2MTY3MzBhYjQ0YjkxIn0.BKEmSuaCRHm-ylafU5zaY3ktZlieZeyRvuNGiiwNd1gNbnX9wrMSWJe58WnNpwaU4qJA3Uar0F_hin5BKVwMgjywWbtoUpkdD2qH7rLoJy8fVRvIcExjMKv5FD-bU9Yk0dFv5pduDdOj8eYXEopMKkNh0gAJ-lwhmwFz-FROUfibkQ0bp6Uc6JZ_YGrj33Lg1dp3ct46DNzcqO91J3IE8PL0yEx_d7J8qYrnMJ6MZ9IyTX9ItESGrAqM2Hj_LNM5CYFSFveaK_zCiJoRQcgg9r-FcyZbG_ApKvdllMk5Ivifwosd0G3GEXZUWgy2hll4kvlevQH0MFG3fknn8Ks2oA'
    header, body, signature = gtoken.split('.')
    header = json.loads(base64.b64decode((header + '========').encode('utf-8')).decode('utf-8'))
    body = json.loads(base64.b64decode((body + '========').encode('utf-8')).decode('utf-8'))

    user = User.query.get(body['sub'])
    if user:
        return user.json()
    else:
        session['registering_user_id'] = body['sub']
        return redirect(url_for('connect_lichess'))
    
    return jsonify({'header': header, 'body': body, 'signature': signature})


if __name__ == "__main__":
    # use_reloader=False prevents flask from running twice in debug mode
    app.run(debug=True, use_reloader=True)