import datetime
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

import time
import datetime

from authlib.integrations.flask_client import OAuth

load_dotenv()

app = Flask(__name__)
CORS(app, support_credentials=True)

app.secret_key = os.getenv("SECRET_KEY")
app.config['LICHESS_CLIENT_ID'] =  os.getenv("LICHESS_CLIENT_ID")
app.config['LICHESS_CLIENT_SECRET'] = os.getenv("LICHESS_CLIENT_SECRET")
app.config['LICHESS_ACCESS_TOKEN_URL'] = 'https://oauth.lichess.org/oauth'
app.config['LICHESS_AUTHORIZE_URL'] = 'https://oauth.lichess.org/oauth/authorize'

oauth = OAuth(app)
oauth.register('lichess')

@app.route('/')
def main():
    return redirect(url_for('login'))

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
    
    # TODO Validate input and update database accordingly

    headers = {'Accept': 'application/json'}
    
    response = requests.get(f"https://lichess.org/game/export/{game_id}", headers=headers)
    r_data = response.json()

    winner_color = r_data['winner']
    game_data = dict(zip(['white', 'black'], [r_data['players']['white']['user']['name'], r_data['players']['black']['user']['name']]))
    game_data['winner'] = r_data['players'][winner_color]['user']['name']
    game_data['timestamp'] = datetime.datetime.utcfromtimestamp(r_data['createdAt'] * 1e-3)

    game_data['base_time'] = r_data['clock']['initial'] // 60
    game_data['increment'] = r_data['clock']['increment']
    
    return jsonify(r_data)


@app.route('/ranking')
@cross_origin(supports_credentials=True)
def ranking():
    league_members = ['joaopf', 'dodo900', 'gspenny', 'hiperlicious', 'MrUnseen', 'eduardodsp', 'fckoch', 'guischmitd']
    ranking_data = []
    for member in league_members:
        player_data = {}
        player_data['name'] = member
        player_data['wins'] = random.randint(0, 11)
        player_data['losses'] = random.randint(0, 11)
        player_data['draws'] = random.randint(0, 9)
        player_data['aelo'] = random.randint(840, 1340)
        player_data['games_played'] = player_data['wins'] + player_data['losses'] + player_data['draws']
        player_data['games_required'] = 36
        ranking_data.append(player_data)

    return jsonify(ranking_data)