from typing import Optional, Dict, Any, List
from app.plugins import _PluginBase
from app.core.config import settings
from app.scheduler import Scheduler
from app.schemas import NotificationType
try:
    from app.events import EventType, eventmanager
except ImportError:
    print("警告: app.events 模块不可用，事件处理功能将受限")
    EventType = None
    eventmanager = None

from .src.api import MTeamAPI
from .src.bet_logic import BetLogic
from .src.event_handler import EventHandler
from .src.models import Match, BetRecord
from app.log import logger

class MTeamAutoBet(_PluginBase):
    """M-Team PT 站菠菜板块自动下注插件"""
    # 插件元数据
    plugin_name = "MTeamAutoBet"
    plugin_desc = "自动下注 M-Team PT 站菠菜板块，优化积分收益"
    plugin_icon = "mteam_bet.png"
    plugin_version = "1.0.0"
    plugin_author = "YourName"
    author_url = "https://github.com/YourName"
    plugin_config_prefix = "mteambet_"
    plugin_order = 27
    auth_level = 2

    # 配置与状态
    _enabled: bool = False
    _notify: bool = True
    _use_proxy: bool = False
    _cron: Optional[str] = "0 * * * *"
    _api_key: Optional[str] = None
    _uid: Optional[str] = None
    _bet_before_seconds: int = 10

    def __init__(self):
        super().__init__()

    def init_plugin(self, config: dict = None):
        """初始化插件，加载配置并注册定时任务"""
        try:
            self.stop_service()
            self.config = config or {}
            self._enabled = self.config.get("enabled", False)
            self._notify = self.config.get("notify", True)
            self._use_proxy = self.config.get("use_proxy", False)
            self._cron = self.config.get("cron", "0 * * * *")
            self._api_key = self.config.get("api_key")
            self._uid = self.config.get("uid", "326922")
            self._bet_before_seconds = int(self.config.get("bet_before_seconds", 10))

            if not self._enabled:
                logger.info(f"{self.plugin_name}: 服务未启用")
                return

            self.api = MTeamAPI(self._api_key, self._use_proxy)
            self.bet_logic = BetLogic(self.config)
            self.event_handler = EventHandler(self.api, self.bet_logic, self.config)

            if self._cron:
                logger.info(f"{self.plugin_name}: 已配置 CRON '{self._cron}'，任务将通过公共服务注册")
            else:
                logger.info(f"{self.plugin_name}: 未配置定时任务")
        except Exception as e:
            logger.error(f"{self.plugin_name}: 服务启动失败: {str(e)}")
            self._enabled = False

    def get_state(self) -> bool:
        """获取插件状态"""
        return bool(self._enabled)

    def get_api(self) -> List[Dict[str, Any]]:
        """注册插件 API"""
        return [
            {
                "path": "/config",
                "endpoint": self._get_config,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取配置"
            },
            {
                "path": "/config",
                "endpoint": self._save_config,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "保存配置"
            },
            {
                "path": "/status",
                "endpoint": self._get_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取状态"
            },
            {
                "path": "/matches",
                "endpoint": self.event_handler.refresh_matches,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "刷新比赛列表"
            },
            {
                "path": "/bet-details",
                "endpoint": self._get_bet_details,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取下注详情"
            },
            {
                "path": "/result-posts",
                "endpoint": self.api.get_result_posts,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取比赛结果帖子"
            },
            {
                "path": "/post-detail",
                "endpoint": self.api.get_post_detail,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取帖子详情"
            }
        ]

    def _get_config(self) -> Dict[str, Any]:
        """返回当前插件配置"""
        return {
            "enabled": self._enabled,
            "notify": self._notify,
            "use_proxy": self._use_proxy,
            "cron": self._cron,
            "api_key": self._api_key,
            "uid": self._uid,
            "bet_before_seconds": self._bet_before_seconds,
            "min_odds": self.config.get("min_odds", 1.5),
            "bet_amount": self.config.get("bet_amount", 100),
            "max_daily_bet": self.config.get("max_daily_bet", 20),
            "stop_loss": self.config.get("stop_loss", 20),
            "bet_strategy": self.config.get("bet_strategy", "套利"),
            "match_type": self.config.get("match_type", "英雄联盟")
        }

    def _save_config(self, config_payload: dict) -> Dict[str, Any]:
        """保存插件配置"""
        logger.info(f"{self.plugin_name}: 收到配置保存请求: {config_payload}")
        try:
            def to_bool(val):
                if isinstance(val, bool):
                    return val
                if isinstance(val, str):
                    return val.lower() == 'true'
                return bool(val)

            self._enabled = to_bool(config_payload.get('enabled', self._enabled))
            self._notify = to_bool(config_payload.get('notify', self._notify))
            self._use_proxy = to_bool(config_payload.get('use_proxy', self._use_proxy))
            self._cron = config_payload.get('cron', self._cron)
            self._api_key = config_payload.get('api_key', self._api_key)
            self._uid = config_payload.get('uid', self._uid)
            self._bet_before_seconds = int(config_payload.get('bet_before_seconds', self._bet_before_seconds))
            self.config.update({
                "min_odds": float(config_payload.get('min_odds', self.config.get("min_odds", 1.5))),
                "bet_amount": float(config_payload.get('bet_amount', self.config.get("bet_amount", 100))),
                "max_daily_bet": float(config_payload.get('max_daily_bet', self.config.get("max_daily_bet", 20))),
                "stop_loss": float(config_payload.get('stop_loss', self.config.get("stop_loss", 20))),
                "bet_strategy": config_payload.get('bet_strategy', self.config.get("bet_strategy", "套利")),
                "match_type": config_payload.get('match_type', self.config.get("match_type", "英雄联盟"))
            })

            config_to_save = self._get_config()
            self.update_config(config_to_save)
            self.stop_service()
            self.init_plugin(config_to_save)
            logger.info(f"{self.plugin_name}: 配置已保存并重新初始化")
            return {"message": "配置已成功保存", "saved_config": self._get_config()}
        except Exception as e:
            logger.error(f"{self.plugin_name}: 保存配置失败: {e}")
            return {"message": f"保存配置失败: {e}", "error": True, "saved_config": self._get_config()}

    def _get_status(self) -> Dict[str, Any]:
        """返回插件状态和历史记录"""
        history = self.get_data('bet_history') or []
        next_run_time = "未配置定时任务"
        time_until_next = None
        task_status = "未启用"

        if self._enabled and self._cron:
            try:
                scheduler = Scheduler()
                schedule_list = scheduler.list()
                plugin_task = next((task for task in schedule_list if task.provider == self.plugin_name), None)
                if plugin_task:
                    task_status = plugin_task.status
                    if hasattr(plugin_task, 'next_run') and plugin_task.next_run:
                        next_run_time = plugin_task.next_run
                        time_until_next = plugin_task.next_run
                    else:
                        next_run_time = "等待执行" if plugin_task.status != "正在运行" else "正在运行中"
                        time_until_next = next_run_time
                else:
                    next_run_time = f"按配置执行: {self._cron}"
            except Exception as e:
                logger.warning(f"获取定时任务信息失败: {e}")
                task_status = "获取失败"
                next_run_time = f"按配置执行: {self._cron}"

        return {
            "enabled": self._enabled,
            "cron": self._cron,
            "next_run_time": next_run_time,
            "time_until_next": time_until_next,
            "task_status": task_status,
            "bet_history": history
        }

    async def _get_bet_details(self, gameId: str) -> List[Dict]:
        """获取下注详情"""
        try:
            bets = await self.api.get_bet_details(gameId)
            return [bet.dict() for bet in bets]
        except Exception as e:
            logger.error(f"获取下注详情失败: {e}")
            return []

    def get_form(self) -> Tuple[Optional[List[dict]], Dict[str, Any]]:
        """返回前端表单配置"""
        return None, self._get_config()

    def get_page(self) -> List[dict]:
        """返回前端页面配置"""
        return []

    def get_service(self) -> List[Dict[str, Any]]:
        """注册插件公共服务"""
        if self._enabled and self._cron:
            from apscheduler.triggers.cron import CronTrigger
            return [{
                "id": "MTeamAutoBet",
                "name": "M-Team 自动下注 - 定时任务",
                "trigger": CronTrigger.from_crontab(self._cron),
                "func": self.event_handler.refresh_matches,
                "kwargs": {}
            }]
        return []

    def stop_service(self) -> None:
        """退出插件，注销定时任务"""
        try:
            Scheduler().remove_plugin_job(self.__class__.__name__.lower())
            logger.info(f"{self.plugin_name}: 插件服务已停止")
        except Exception as e:
            logger.error(f"{self.plugin_name}: stop_service 执行异常: {e}")

    def get_render_mode(self) -> Tuple[str, Optional[str]]:
        """返回 Vue 渲染模式和组件路径"""
        return "vue", "dist/assets"