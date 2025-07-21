import datetime
import re
from typing import Any, List, Dict, Tuple, Optional

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.chain.system import SystemChain
from app.core.config import settings
from app.helper.system import SystemHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType
from app.utils.http import RequestUtils

class BetGameNotify(_PluginBase):
    plugin_name = "BetGame比赛通知"
    plugin_desc = "获取新比赛并推送通知"
    plugin_icon = "BetGame_Icon.png"
    plugin_version = "1.0"
    plugin_author = "your_name"
    author_url = "https://github.com/your_name"
    plugin_config_prefix = "betgame_notify_"
    plugin_order = 30
    auth_level = 1

    _enabled = False
    
    _cron = None
    _notify = False
    _api_key = ""  # 存储API Key

    _scheduler: Optional[BackgroundScheduler] = None

    def init_plugin(self, config: dict = None):
        # 停止现有任务
        self.stop_service()

        if config:
            self._enabled = config.get("enabled")
            self._cron = config.get("cron")
            self._notify = config.get("notify")
            self._api_key = config.get("api_key", "")  # 从配置中获取API Key

    def __fetch_and_notify(self):
        """
        获取新比赛并推送通知
        """
        # 请求获取比赛列表
        response = self.__get_bet_game_list()
        if response and response.get('code') == '0':
            games = response.get('data', [])
            for game in games:
                # 生成比赛标题和内容
                title = game.get('heading', '未知比赛')
                endtime = game.get('endtime', '未知时间')
                options_list = game.get('optionsList', [])
                options = '\n'.join([f"{option['text']} - {option['odds']}" for option in options_list])

                # 推送通知
                self.__notify_game(title, endtime, options)
        else:
            logger.error("获取比赛列表失败或返回数据不正确")

    def __get_bet_game_list(self) -> dict:
        """
        调用API获取比赛列表
        """
        url = "https://api.m-team.io/api/bet/findBetgameList"  # 主接口
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "x-api-key": self._api_key  # 使用配置中的API Key
        }
        data = {
            "active": "LIVE",
            "fix": 0
        }
        response = RequestUtils(
            proxies=settings.PROXY,
            headers=headers
        ).post_res(url, data)
        return response.json() if response else {}

    def __notify_game(self, title: str, endtime: str, options: str):
        """
        推送比赛通知
        """
        if self._notify:
            message = f"新比赛通知：\n\n{title}\n结束时间：{endtime}\n赔率选项：\n{options}"
            self.post_message(
                mtype=NotificationType.SiteMessage,
                title="【新比赛通知】",
                text=message
            )

    def get_state(self) -> bool:
        return self._enabled

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_service(self) -> List[Dict[str, Any]]:
        """
        注册插件公共服务
        """
        if self._enabled and self._cron:
            return [
                {
                    "id": "BetGameNotify",
                    "name": "比赛通知服务",
                    "trigger": CronTrigger.from_crontab(self._cron),
                    "func": self.__fetch_and_notify,
                    "kwargs": {}
                }
            ]
        return []

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        配置插件页面
        """
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'notify',
                                            'label': '发送通知',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'api_key',
                                            'label': 'API Key',
                                            'placeholder': '请输入 M-Team API Key',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VCronField',
                                        'props': {
                                            'model': 'cron',
                                            'label': '检查周期',
                                            'placeholder': '5位cron表达式'
                                        }
                                    }
                                ]
                            },
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "notify": False,
            "cron": "0 9 * * *",
            "api_key": "",  # 默认空API Key
        }

    def get_page(self) -> List[dict]:
        pass


    def stop_service(self):
        """
        退出插件
        """
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown()
                self._scheduler = None
        except Exception as e:
            logger.error("退出插件失败：%s" % str(e))
