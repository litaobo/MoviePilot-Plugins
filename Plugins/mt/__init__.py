import datetime
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.plugins import _PluginBase
from app.schemas import NotificationType
from app.utils.http import RequestUtils
from app.log import logger
from app.core.config import settings

class BetGameNotify(_PluginBase):
    # 插件名称
    plugin_name = "BetGame更新推送"
    # 插件描述
    plugin_desc = "实时比赛信息和赔率更新推送"
    # 插件版本
    plugin_version = "1.0"
    # 插件作者
    plugin_author = "Your Name"
    # 作者主页
    author_url = "https://github.com/yourprofile"
    # 插件配置项ID前缀
    plugin_config_prefix = "betgamenotify_"
    # 加载顺序
    plugin_order = 10
    # 可使用的用户级别
    auth_level = 1

    _enabled = False
    _notify = False
    _cron = None
    _api_key = None
    _scheduler: Optional[BackgroundScheduler] = None

    def init_plugin(self, config: dict = None):
        """
        初始化插件，设置插件配置。
        """
        # 停止现有任务
        self.stop_service()

        if config:
            self._enabled = config.get("enabled", False)
            self._notify = config.get("notify", False)
            self._cron = config.get("cron", "0 * * * *")  # 默认每小时检查一次
            self._api_key = config.get("api_key", "")

    def __fetch_game_data(self):
        """
        获取比赛信息并推送通知
        """
        if not self._enabled:
            return

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "x-api-key": self._api_key
        }

        data = {
            "active": "LIVE",
            "fix": 0
        }

        url = "https://api.m-team.io/api/bet/findBetgameList"
        response = RequestUtils().post_res(url, headers=headers, data=data)

        if response and response.json()['code'] == "0":
            games = response.json().get('data', [])
            for game in games:
                self.__notify_game(game)

    def __notify_game(self, game):
        """
        推送比赛信息
        """
        if not self._notify:
            return

        heading = game.get('heading', '无标题')
        options = game.get('optionsList', [])
        odds = "\n".join([f"{option['text']}: {option['odds']}" for option in options])

        message = f"【比赛信息】\n{heading}\n赔率:\n{odds}"

        # 推送通知
        self.post_message(
            mtype=NotificationType.SiteMessage,
            title="实时比赛更新",
            text=message
        )

    def get_service(self) -> List[Dict[str, Any]]:
        """
        获取定时任务服务配置
        """
        if self._enabled and self._cron:
            return [
                {
                    "id": "BetGameNotify",
                    "name": "比赛信息检查服务",
                    "trigger": CronTrigger.from_crontab(self._cron),
                    "func": self.__fetch_game_data,
                    "kwargs": {}
                }
            ]
        return []

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
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
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'api_key',
                                            'label': 'API密钥',
                                            'type': 'text'
                                        }
                                    }
                                ]
                            },
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
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
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
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'notify',
                                            'label': '启用通知',
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "notify": False,
            "api_key": "",
            "cron": "0 * * * *"  # 默认每小时检查一次
        }

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

