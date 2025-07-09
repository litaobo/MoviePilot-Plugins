import httpx
from typing import List, Dict, Optional
from .models import Match, BetRecord, UserProfile
from app.log import logger

class MTeamAPI:
    def __init__(self, api_key: str, use_proxy: bool = False):
        self.api_key = api_key
        self.base_url = "https://api.m-team.io"
        self.backup_url = "https://api.m-team.cc"
        self.headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "x-api-key": api_key
        }
        self.use_proxy = use_proxy

    async def get_matches(self) -> List[Match]:
        """获取 LIVE 比赛列表"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/bet/findBetgameList",
                    headers=self.headers,
                    data={"active": "LIVE", "fix": 0}
                )
                data = response.json()
                if data.get("code") == "0":
                    return [Match(**item) for item in data["data"]]
                return []
            except Exception as e:
                print(f"获取比赛列表失败: {e}")
                return []

    async def get_user_profile(self, uid: str) -> Optional[UserProfile]:
        """获取用户信息"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/member/profile",
                    headers=self.headers,
                    data={"uid": uid}
                )
                data = response.json()
                if data.get("code") == "0":
                    return UserProfile(**data["data"]["memberCount"])
                return None
            except Exception as e:
                print(f"获取用户信息失败: {e}")
                return None

    async def get_bet_details(self, game_id: str) -> List[BetRecord]:
        """获取比赛下注详情"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/bet/getDetailBetList",
                    headers=self.headers,
                    data={"gameId": game_id}
                )
                data = response.json()
                if data.get("code") == "0":
                    return [BetRecord(**item) for item in data["data"]]
                return []
            except Exception as e:
                print(f"获取下注详情失败: {e}")
                return []

    async def get_match_details(self, page: int = 1, size: int = 20) -> List[Match]:
        """获取所有比赛详情（含总下注金额）"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/bet/betgameDetailLog",
                    headers=self.headers,
                    data={"pageNumber": page, "pageSize": size}
                )
                data = response.json()
                if data.get("code") == "0":
                    return [Match(**item) for item in data["data"]["data"] if item["active"] == "LIVE"]
                return []
            except Exception as e:
                print(f"获取比赛详情失败: {e}")
                return []

    async def place_bet(self, opt_id: str, bonus: float) -> Dict:
        """提交下注请求"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/bet/betgameOdds",
                    headers=self.headers,
                    data={"optId": opt_id, "bonus": bonus}
                )
                return response.json()
            except Exception as e:
                print(f"下注失败: {e}")
                return {"code": "-1", "message": str(e)}

    async def get_result_posts(self, page: int = 1, size: int = 20) -> List[Dict]:
        """获取比赛结果帖子列表"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/forum/post/search",
                    headers={**self.headers, "Content-Type": "application/json"},
                    json={"pageNumber": page, "pageSize": size, "lastId": 0, "keyword": "", "authorId": 153459, "fid": 29, "author": 0}
                )
                data = response.json()
                if data.get("code") == "0":
                    return data["data"]["data"]
                return []
            except Exception as e:
                print(f"获取结果帖子失败: {e}")
                return []

    async def get_post_detail(self, tid: str) -> Dict:
        """获取比赛结果帖子详情"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/forum/topic/detail",
                    headers={**self.headers, "Content-Type": "application/json"},
                    json={"pageNumber": 1, "pageSize": 20, "lastId": 0, "tid": tid, "authorId": 0}
                )
                return response.json()
            except Exception as e:
                print(f"获取帖子详情失败: {e}")
                return {"code": "-1", "message": str(e)}
