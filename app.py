# Standard packages
import os
import sys
import pickle
import logging
from datetime import datetime
from pathlib import Path

# Web utilities
import ndjson
import requests
from dotenv import load_dotenv
from dotenv.main import resolve_nested_variables

from flask import Flask, json, jsonify
from flask import url_for, redirect, request
from flask_cors import CORS, cross_origin

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
print(__name__)
app.app_context().push()
CORS(app, support_credentials=True)
login_manager = LoginManager()

app.secret_key = os.getenv("SECRET_KEY") or os.urandom(128)
logger.debug(f'Secret Key: {app.secret_key}')

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
    initialize_mock_db(db, app, input_games='test_data/acl1_gamelist.json')


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
    if current_user.is_authenticated:
        return (
                "<h3>Welcome to the backend!</h3>"
                "<p>There's actually nothing here, fellow aowgher.</p>"
                "<p>Maybe you meant to go <a href={}>here</a>?</p>"
                "<p>Current user: <a href={}>{}</a> logged in with the email: {}</p>".format('http://localhost:3000', 
                                                                                                current_user.lichess_url, 
                                                                                                current_user.acl_username, 
                                                                                                current_user.email)
            )
    else:
        return (
                '<a class="button" href="/login">LOGIN</a>'.format('http://localhost:3000')
            )

@app.route('/login')
def login():
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    # Use library to construct the request for Google login and provide
    # scopes that let you retrieve user's profile from Google
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "/callback",
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)


@app.route('/debug')
def debug():
    data = [f.id for f in User.query.all()]
    
    return str(data)


@app.route('/login/callback')
def login_callback():
    # Get authorization code Google sent back to you
    code = request.args.get("code")

    # Find out what URL to hit to get tokens that allow you to ask for
    # things on behalf of a user
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]

    # Prepare and send a request to get tokens! Yay tokens!
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )

    # Parse the tokens!
    client.parse_request_body_response(json.dumps(token_response.json()))

    # Now that you have tokens (yay) let's find and hit the URL
    # from Google that gives you the user's profile information,
    # including their Google profile image and email
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    if userinfo_response.json().get("email_verified"):
        unique_id = userinfo_response.json()["sub"]
        users_email = userinfo_response.json()["email"]
        picture = userinfo_response.json()["picture"]
        users_name = userinfo_response.json()["given_name"]
    else:
        return "User email not available or not verified by Google.", 400

    user = get_user(unique_id)
    if not user:
        app.logger.info(f'No user found with ID {unique_id}. Creating new user.')
        create_user(id=unique_id, 
                    email=users_email, 
                    profile_picture=picture,
                    google_name=users_name,
                    acl_elo=1000,
                    date_joined=datetime.now(),
                    lichess_connected=False)
        user = get_user(unique_id)

    login_user(user)

    if not user.lichess_connected:
        return redirect(url_for('login_lichess'))
    else:
        return redirect(url_for('main'))


@app.route('/login/lichess')
def login_lichess():
    app.logger.debug('Accessing login_lichess endpoint')
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
    token = oauth.lichess.authorize_access_token()

    bearer = token['access_token']
    headers = {'Authorization': f'Bearer {bearer}'}

    response = requests.get(f"https://lichess.org/api/account", headers=headers)

    # db_ops.update_user_lichess_data(current_user.id, response.json())

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
    
    # # Generate certificates and add authority to chrome so you can run flask in https
    # # https://stackoverflow.com/questions/7580508/getting-chrome-to-accept-self-signed-localhost-certificate
    # app.run(debug=True, ssl_context=(".cert/localhost.crt", ".cert/localhost.key"))
