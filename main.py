from typing import Optional
import requests
import xml.etree.ElementTree as ET
from typing import Dict, Tuple, List, Union
from pydantic import BaseModel
from fastapi import FastAPI

app = FastAPI()

PLAYER_POINTS_URL = "https://www.fansaka.info/xml/sokuho.xml"
PLAYER_ID = str
PLAYER_NAME = str


"""
curl -X 'GET' \
  'http://127.0.0.1:8000/score' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "players": ["J34531", "J45270"]
}'
"""

class GameWeekPlayer:
    def __init__(self, id: str, name: str, gw_score: int):
        self.id: str = id
        self.name: str = name
        self.gw_score: int = gw_score

class GameWeekPlayerPoints:
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

        game_week_player_points = GameWeekPlayerPoints(gameweek)

        for player in xml_data[1]:
            id = player[0].text
            name = player[3].text
            gw_score = int(player[7][8].text)

            game_week_player_points.players[id] = GameWeekPlayer(id, name, gw_score)

        return game_week_player_points


class GameWeekRequest(BaseModel):
    players: Optional[List[PLAYER_ID]]
    #TODO Add game week

class GameWeekResponse(BaseModel):
    players_score: List[Tuple[PLAYER_NAME, int]]= []
    total_scores: Union[None, int] = None
    gameweek: Union[None, str] = None

@app.get("/score", response_model=GameWeekResponse)
async def get_score(req: GameWeekRequest):
    response = requests.get(PLAYER_POINTS_URL)
    assert response.status_code == 200
    game_week_player_points = GameWeekPlayerPoints.from_xml(response.content)

    resp = GameWeekResponse()

    for player_id in req.players:
        resp.players_score.append((game_week_player_points.players[player_id].name, 
                                   game_week_player_points.players[player_id].gw_score))
    resp.total_scores = sum([score for _, score in resp.players_score])
    resp.gameweek = game_week_player_points.gameweek
    return resp

