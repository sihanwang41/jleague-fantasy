import json
from typing import Optional
import requests
import xml.etree.ElementTree as ET
from typing import Dict, Tuple, List, Union
from pydantic import BaseModel
from fastapi import FastAPI
import redis

app = FastAPI()

PLAYER_POINTS_URL = "https://www.fansaka.info/xml/sokuho.xml"
PLAYER_ID = str
PLAYER_NAME = str
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
    {"id": "J499H0"}, {"id": "J46A71"}, {"id": "J47251"}, {"id": "J50970"}], "gameweek": "2"}'

    
curl -X 'POST'   'http://127.0.0.1:8000/gameweek_roaster'   -H 'accept: application/json'   -H 'Content-Type: application/json'   -d '{
  "user_id": "0", "add_players": [
    {"id": "J54940"}], "delete_players": ["J46A71"], "gameweek": "2"}'
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


class GameWeekRequest(BaseModel):
    players: Optional[List[PLAYER_ID]]
    #TODO Add game week

class GameWeekResponse(BaseModel):
    players_score: List[Tuple[PLAYER_NAME, int]]= []
    total_scores: Union[None, int] = None
    gameweek: Union[None, str] = None
    message: str = None

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


class SelectedPlayer(BaseModel):
    id: str
    is_substitute: bool = False
    name: str = None
    position: str = None
    price: Union[None, int] = None 

class GameWeekRoasterRequest(BaseModel):
    user_id: str
    add_players: Optional[List[SelectedPlayer]] = []
    delete_players: Optional[List[PLAYER_ID]] = []
    gameweek: str

class GameWeekRoasterResponse(BaseModel):
    user_id: str
    players: List[SelectedPlayer] = []
    total_value: int = 0


def _construct_roaster_response(user_id: str, gameweek: str, all_players: dict, game_week_player_summary: GameWeekPlayerSummary) -> GameWeekRoasterResponse:
    resp = GameWeekRoasterResponse(user_id=user_id)
    for player_id in all_players:
        player = SelectedPlayer(id=player_id, is_substitute=all_players[player_id])
        player.name = game_week_player_summary.players[player_id].name
        player.position = game_week_player_summary.players[player_id].position
        if gameweek == game_week_player_summary.gameweek:
            player.price = game_week_player_summary.players[player_id].cur_price
        else:
            player.price = game_week_player_summary.players[player_id].next_price
        resp.players.append(player)
        resp.total_value += player.price
    return resp

@app.post("/gameweek_roaster", response_model=GameWeekRoasterResponse)
async def update_roaster(req: GameWeekRoasterRequest):
    response = requests.get(PLAYER_POINTS_URL)
    assert response.status_code == 200
    game_week_player_summary = GameWeekPlayerSummary.from_xml(response.content)

    assert req.user_id in VALID_USER_IDS
    assert int(req.gameweek) == int(game_week_player_summary.gameweek) + 1 or int(req.gameweek) == int(game_week_player_summary.gameweek)

    resp = GameWeekRoasterResponse(user_id=req.user_id)

    redis_key = f"{req.gameweek}_{req.user_id}"
    redis_client = get_redis_client()
    
    content_bytes = redis_client.get(redis_key)
    if content_bytes:
        all_players = json.loads(content_bytes)
    else:
        all_players = {}
    
    for player in req.add_players:
        all_players[player.id] = player.is_substitute
    
    for player in req.delete_players:
        all_players.pop(player, None)


    resp = _construct_roaster_response(req.user_id, req.gameweek, all_players, game_week_player_summary)

    redis_client.set(redis_key, json.dumps(all_players))

    return resp

@app.get("/gameweek_roaster")
async def update_roaster(gameweek: str, user_id: str):

    response = requests.get(PLAYER_POINTS_URL)
    assert response.status_code == 200
    game_week_player_summary = GameWeekPlayerSummary.from_xml(response.content)

    assert user_id in VALID_USER_IDS
    assert int(gameweek) == int(game_week_player_summary.gameweek) + 1 or int(gameweek) == int(game_week_player_summary.gameweek)

    redis_key = f"{gameweek}_{user_id}"
    redis_client = get_redis_client()
    content_bytes = redis_client.get(redis_key)
    if content_bytes:
        all_players = json.loads(content_bytes)
    else:
        all_players = {}
    
    resp = _construct_roaster_response(user_id, gameweek, all_players, game_week_player_summary)
    
    return resp
