# MTeam 自动下注插件

import requests
from datetime import datetime, timedelta
from typing import Any, List, Dict, Optional,Tuple

from app.plugins import _PluginBase
from app.log import logger
from app.scheduler import Scheduler
from app.schemas import NotificationType
from app.utils.http import RequestUtils
from app.db.site_oper import SiteOper

class ManToumt(_PluginBase):
    plugin_name = "mt自动助手"
    plugin_desc = "mt自动助手"
    plugin_icon = "signin.png"
    plugin_version = "1.0.0"
    plugin_author = "litaobo"
    author_url = "https://github.com/litaobo"
    plugin_config_prefix = "mantoumt_"
    plugin_order = 25
    auth_level = 2

    _enabled: bool = False
    _use_proxy: bool = True
    _notify: bool = True
    _onlyonce: bool = False

    _api_key: Optional[str] = None
    _bet_seconds_before: int = 10
    _bet_amount: int = 1000

    _siteoper = None

    # 初始化插件配置并根据配置启动任务
    def init_plugin(self, config: Optional[dict] = None) -> None:
        self._siteoper = SiteOper()

        if config:
            self._enabled = config.get("enabled", False)
            self._use_proxy = config.get("use_proxy", True)
            self._notify = config.get("notify", True)
            self._onlyonce = config.get("onlyonce", False)
            self._api_key = config.get("api_key", "")
            self._bet_seconds_before = int(config.get("bet_seconds_before", 10))
            self._bet_amount = int(config.get("bet_amount", 1000))

        if self._onlyonce:
            logger.info("MTeam 自动下注助手 - 立即执行一次任务")
            self._onlyonce = False
            self.update_config({"onlyonce": False})
            self._run_once_or_schedule()

    # 获取比赛并为每场比赛安排下注定时任务
    def _run_once_or_schedule(self):
        games = self.fetch_games()
        logger.info(f"共获取 {len(games)} 场 LIVE 比赛")
        for game in games:
            try:
                end_time = datetime.strptime(game["endtime"], "%Y-%m-%d %H:%M:%S")
                bet_time = end_time - timedelta(seconds=self._bet_seconds_before)
                Scheduler().add_date_job(
                    job_id=f"MTeamBetHelper_{game['id']}",
                    func=self.auto_bet,
                    kwargs={"game": game},
                    run_date=bet_time
                )
                logger.info(f"已安排比赛 {game['heading']} 的下注任务于 {bet_time}")
            except Exception as e:
                logger.error(f"下注任务安排失败: {e}")
      
    # 负责调用 M-Team API 获取当前 LIVE 比赛数据列表。
    def fetch_games(self) -> List[Dict[str, Any]]:
        url = self._get_base_url() + "/api/bet/findBetgameList"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "x-api-key": self._api_key
        }
        data = {"active": "LIVE", "fix": 0}
        try:
            res = requests.post(url, headers=headers, data=data, proxies=self._get_proxies())
            return res.json().get("data", [])
        except Exception as e:
            logger.error(f"获取比赛失败：{e}")
            return []
    # 执行实际的下注操作，选择赔率最高的选项并发送下注请求。
    def auto_bet(self, game: Dict[str, Any]):
        try:
            best_option = max(game["optionsList"], key=lambda x: float(x["odds"]))
            url = self._get_base_url() + "/api/bet/betgameOdds"
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "x-api-key": self._api_key
            }
            data = {"optId": best_option["id"], "bonus": self._bet_amount}
            res = requests.post(url, headers=headers, data=data, proxies=self._get_proxies())
            logger.info(f"下注成功: {res.text}")
            if self._notify:
                self.post_message(
                    mtype=NotificationType.SiteMessage,
                    title="M-Team 自动下注",
                    text=f"✅ 比赛 {game['heading']} 成功下注 {best_option['text']}，赔率 {best_option['odds']}"
                )
        except Exception as e:
            logger.error(f"下注失败：{e}")
    # 用于获取系统代理配置（如启用代理时）。
    def _get_proxies(self):
        if not self._use_proxy:
            return None
        try:
            from app.core.config import settings
            return settings.PROXY if hasattr(settings, "PROXY") else None
        except Exception as e:
            logger.error(f"获取代理失败: {e}")
            return None
    # 该方法根据是否有 API Key 判断使用主站或备用站。
    def _get_base_url(self) -> str:
        return "https://api.m-team.io" if self._api_key else "https://api.m-team.cc"
    # 此方法返回插件是否启用的状态。
    def get_state(self) -> bool:
        return self._enabled
     # 注册需要 MoviePilot 调度器执行的任务，目前为空。
    def get_service(self) -> List[Dict[str, Any]]:
        return []
     # 拼装插件的配置页面表单结构。
    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        # 动态判断MoviePilot版本，决定定时任务输入框组件类型
        version = getattr(settings, "VERSION_FLAG", "v1")
        cron_field_component = "VCronField" if version == "v2" else "VTextField"
        return [
        {
            "component": "VForm",
            "content": [
                # 基本设置
                {
                    "component": "VCard",
                    "props": {"variant": "flat", "class": "mb-4"},
                    "content": [
                        {"component": "VCardTitle", "text": "基本设置"},
                        {"component": "VSwitch", "props": {"model": "enabled", "label": "启用插件"}},
                        {"component": "VSwitch", "props": {"model": "use_proxy", "label": "使用代理"}},
                        {"component": "VSwitch", "props": {"model": "notify", "label": "开启通知"}},
                        {"component": "VSwitch", "props": {"model": "onlyonce", "label": "立即运行一次"}},
                    ]
                },
                # 功能设置
                {
                    "component": "VCard",
                    "props": {"variant": "flat", "class": "mb-4"},
                    "content": [
                        {"component": "VCardTitle", "text": "功能设置"},
                        {"component": "VTextField", "props": {"model": "api_key", "label": "API Key"}},
                        {"component": "VTextField", "props": {"model": "bet_seconds_before", "label": "提前下注秒数", "type": "number"}},
                        {"component": "VTextField", "props": {"model": "bet_amount", "label": "下注积分", "type": "number"}},
                    ]
                }
            ]
        }
    ], {
        "enabled": False,
        "use_proxy": True,
        "notify": True,
        "onlyonce": False,
        "api_key": "",
        "bet_seconds_before": 10,
        "bet_amount": 1000
    }
   #  构建插件的查询结果页面，目前未实现内容。
    def get_page(self) -> List[dict]:
    return [
        {
            "component": "VCard",
            "props": {"variant": "flat", "class": "mb-4"},
            "content": [
                {
                    "component": "VCardTitle",
                    "props": {"class": "text-h6"},
                    "text": "M-Team 当前状态"
                },
                {
                    "component": "VCardText",
                    "content": [
                        {
                            "component": "div",
                            "props": {"class": "text-body-1"},
                            "text": "暂无比赛数据。请先启用插件并配置 API Key。"
                        }
                    ]
                }
            ]
        }
    ]
        # 插件关闭清理任务
    def stop_service(self) -> None:
    """
    插件停止时清理所有任务
    """
    try:
        Scheduler().remove_plugin_jobs(self.__class__.__name__)
        logger.info("M-Team 自动下注助手任务已停止")
    except Exception as e:
        logger.error("退出插件失败：%s" % str(e))
