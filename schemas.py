from typing import Dict, Tuple, List, Optional, Union
from pydantic import BaseModel

PLAYER_ID = str
PLAYER_NAME = str

# Score request
class GameWeekRequest(BaseModel):
    players: Optional[List[PLAYER_ID]]
    #TODO Add game week

# Score response
class GameWeekResponse(BaseModel):
    players_score: List[Tuple[PLAYER_NAME, int]]= []
    total_scores: Union[None, int] = None
    gameweek: Union[None, str] = None
    message: str = None

# User roaster request
class UserSelectedPlayer(BaseModel):
    id: str
    is_substitute: bool = False
    is_captain: bool = False
    class Config:
        extra = 'forbid'

class GameWeekRoasterRequest(BaseModel):
    user_id: str
    add_players: Optional[List[UserSelectedPlayer]] = []
    delete_players: Optional[List[PLAYER_ID]] = []
    gameweek: str

    class Config:
        extra = 'forbid'

# User roaster response
class SelectedPlayer(BaseModel):
    id: str
    is_substitute: bool = False
    name: str
    position: str
    price: int
    is_captain: bool = False

class GameWeekRoasterResponse(BaseModel):
    user_id: str
    players: List[SelectedPlayer] = []
    total_value: int = 0
    bank_moeny: int = 0
    message: str = None


# Player internal state per game week, saved in redis
class GameWeekUserState(BaseModel):
    roaster: Dict[PLAYER_ID, SelectedPlayer]
    gameweek: str
    bank_money: int = 0