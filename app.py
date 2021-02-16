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

    fixture_id = Fixture.query.filter_by(white=lichess_gamedata['players']['white']['user']['id'], 
                                         black=lichess_gamedata['players']['black']['user']['id']).first().id
    print(f'Fixture is {fixture_id}:', Fixture.query.get(fixture_id))

    if validate_game(fixture_id, lichess_gamedata):
        add_game_to_db(fixture_id, lichess_gamedata)
        update_acl_elo(fixture_id)

    else:
        print('Invalid game!')
    
    return jsonify(lichess_gamedata)


@app.route('/ranking')
@cross_origin(supports_credentials=True)
def ranking():
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

        print(member.lichess_id, member.acl_elo)
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

    return jsonify(ranking_data)


@app.route('/fixtures')
@cross_origin(supports_credentials=True)
def fixtures():
    fixtures = []
    
    for f in Fixture.query.all():
        fixture = {'id': f.id, 'white':f.white, 'black': f.black, 
                   'game_id': f.game_id, 'outcome': f.outcome,
                   'event_id': f.event_id, 'round_id': f.round_id,
                   'deadline': f.deadline, 
                   'time_base': f.time_base, 'time_increment': f.time_increment}
        fixtures.append(fixture)

    return jsonify(fixtures)