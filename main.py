import json
import requests
import xml.etree.ElementTree as ET
from typing import Dict, Union
from pydantic import BaseModel
from fastapi import FastAPI
import redis

from schemas import PLAYER_ID, GameWeekRequest, GameWeekResponse, GameWeekRoasterRequest, GameWeekRoasterResponse, GameWeekUserState, SelectedPlayer
app = FastAPI()

PLAYER_POINTS_URL = "https://www.fansaka.info/xml/sokuho.xml"
REDIS_URL="rediss://red-cngeb3fsc6pc73dno3dg:tNIy8bGlSQXmmzM4BSANLKREd8h4OieI@oregon-redis.render.com:6379"
# Only have 3 players to play the game.
VALID_USER_IDS = ["test", "0", "1", "2"]

"""
curl -X 'GET' \
  'http://127.0.0.1:8000/score' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "players": ["J34531", "J45270"]
}'

curl -X 'POST'   'http://127.0.0.1:8000/gameweek_roaster'   -H 'accept: application/json'   -H 'Content-Type: application/json'   -d '{
  "user_id": "test", "add_players": [
    {"id": "J494D1"}, {"id": "J439F0"}, {"id": "J467R1"}, 
    {"id": "J468N0"}, {"id": "J456B1"}, {"id": "J477N0"}, {"id": "J44AL0"},
    {"id": "J499H0"}, {"id": "J46A71"}, {"id": "J47251"}, {"id": "J50970"}], "gameweek": "3"}'

    
curl -X 'POST'   'http://127.0.0.1:8000/gameweek_roaster'   -H 'accept: application/json'   -H 'Content-Type: application/json'   -d '{
  "user_id": "test", "add_players": [
    {"id": "J45270"}], "delete_players": ["J44AL0"], "gameweek": "3"}'
"""

def get_redis_client():
    return redis.from_url(REDIS_URL)

class GameWeekPlayer(BaseModel):
    id: str
    name: str
    position: str
    cur_price: int
    # None means not avaiable
    gw_score: Union[int, None]
    next_price: Union[int, None]

class GameWeekPlayerSummary:
    def __init__(self, gameweek: str):
        self.players: Dict[PLAYER_ID, GameWeekPlayer] = {}
        self.gameweek = gameweek

    @classmethod
    def from_xml(cls, data: str):
        """
        Parse the xml string content.
        data format is xml from fansaka public api.
        """
        xml_data = ET.fromstring(data)
        gameweek = xml_data[0][0].text
        assert int(gameweek)

        game_week_player_summary = GameWeekPlayerSummary(gameweek)

        for player in xml_data[1]:
            id = player[0].text
            position = player[2].text
            name = player[3].text
            cur_price = int(player[5].text)
            gw_score = None
            next_price = None
            if len(player) > 7:
                # Result is ready, otherwise set score and next_price to None
                gw_score = int(player[7][8].text)
                next_price = int(player[7][0].text)

            game_week_player_summary.players[id] = GameWeekPlayer(id=id, name=name, position=position, gw_score=gw_score, cur_price=cur_price, next_price=next_price)

        return game_week_player_summary

@app.get("/score", response_model=GameWeekResponse)
async def get_score(req: GameWeekRequest):
    response = requests.get(PLAYER_POINTS_URL)
    assert response.status_code == 200
    game_week_player_summary = GameWeekPlayerSummary.from_xml(response.content)

    resp = GameWeekResponse()

    for player_id in req.players:
        resp.players_score.append((game_week_player_summary.players[player_id].name, 
                                   game_week_player_summary.players[player_id].gw_score))
        if game_week_player_summary.players[player_id].gw_score is None:
            resp = GameWeekResponse()
            resp.message = f"Player {game_week_player_summary.players[player_id].name} doesn't have score, please try again later."
            return resp
            
    resp.total_scores = sum([score for _, score in resp.players_score])
    resp.gameweek = game_week_player_summary.gameweek
    return resp

@app.post("/gameweek_roaster", response_model=GameWeekRoasterResponse)
async def update_roaster(req: GameWeekRoasterRequest):
    response = requests.get(PLAYER_POINTS_URL)
    assert response.status_code == 200
    game_week_player_summary = GameWeekPlayerSummary.from_xml(response.content)

    assert req.user_id in VALID_USER_IDS
    assert int(req.gameweek) == int(game_week_player_summary.gameweek) + 1

    resp = GameWeekRoasterResponse(user_id=req.user_id)

    redis_key = f"{req.gameweek}_{req.user_id}"
    redis_client = get_redis_client()
    
    content_bytes = redis_client.get(redis_key)
    if not content_bytes:
        return resp
    gameweek_user_state: GameWeekUserState = GameWeekUserState.parse_obj(json.loads(content_bytes))

    for player_id in req.delete_players:
        if player_id in gameweek_user_state.roaster:
            deleted_player: SelectedPlayer = gameweek_user_state.roaster.pop(player_id)
            gameweek_user_state.bank_money += deleted_player.price

    for player in req.add_players:
        if player.id in gameweek_user_state.roaster:
            continue
        player_info = game_week_player_summary.players[player.id]
        if gameweek_user_state.bank_money < player_info.next_price:
            resp.message = "Bank money not enough to finish buying all players"
            return resp
        
        gameweek_user_state.bank_money -= player_info.next_price
        player = SelectedPlayer(id=player.id, is_substitute=player.is_substitute, name=player_info.name, position=player_info.position, price=player_info.next_price)
        gameweek_user_state.roaster[player.id] = player
    
    resp.players = list(gameweek_user_state.roaster.values())
    resp.bank_moeny = gameweek_user_state.bank_money
    resp.total_value = sum([player.price for _, player in gameweek_user_state.roaster.items()])

    redis_client.set(redis_key, json.dumps(gameweek_user_state.dict()))

    return resp


@app.get("/gameweek_roaster")
async def get_roaster(gameweek: str, user_id: str):

    assert user_id in VALID_USER_IDS

    redis_key = f"{gameweek}_{user_id}"
    redis_client = get_redis_client()
    content_bytes = redis_client.get(redis_key)
    resp = GameWeekRoasterResponse(user_id=user_id)
    if not content_bytes:
        return resp
    gameweek_user_state: GameWeekUserState = GameWeekUserState.parse_obj(json.loads(content_bytes))

    resp.players = list(gameweek_user_state.roaster.values())
    resp.bank_moeny = gameweek_user_state.bank_money
    resp.total_value = sum([player.price for _, player in gameweek_user_state.roaster.items()])
    
    return resp
