from pydantic import BaseModel
from datetime import datetime
from typing import List, Dict, Optional

class MatchOption(BaseModel):
    id: str
    text: str
    odds: float
    bonusTotal: Optional[float]

class Match(BaseModel):
    id: str
    heading: str
    undertext: str
    endtime: str
    active: str
    countall: str
    optionsList: List[MatchOption]
    taxRate: float

class BetRecord(BaseModel):
    id: str
    gameid: str
    optionid: str
    userid: str
    bonus: float
    createdDate: str

class UserProfile(BaseModel):
    id: str
    bonus: float