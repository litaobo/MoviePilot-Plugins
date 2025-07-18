import json
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from threading import Lock

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

from app.core.config import settings
from app.log import logger
from app.plugins import _PluginBase
from app.utils.http import RequestUtils


class MTeamBetHelper(_PluginBase):
    # 插件元信息
    plugin_name = "M-Team菠菜助手"
    plugin_desc = "M-Team菠菜比赛自动下注，支持实时比赛列表获取和定时自动下注"
    plugin_icon = "https://api.m-team.io/favicon.ico"
    plugin_version = "1.0.0"
    plugin_author = "Assistant"
    plugin_config_prefix = "mteambet_"
    plugin_order = 25
    auth_level = 2
    
    # 私有状态变量
    _enabled: bool = False
    _notify: bool = False
    _use_proxy: bool = True
    _onlyonce: bool = False
    _scheduler: Optional[BackgroundScheduler] = None
    _lock = Lock()
    
    # 配置参数
    _api_key: str = ""
    _auto_bet: bool = False
    _bet_seconds_before: int = 10
    _bet_amount: str = "100"
    _main_api_url: str = "https://api.m-team.io"
    _backup_api_url: str = "https://api.m-team.cc"
    
    # 数据存储
    _bet_games: List[Dict] = []
    _bet_history: List[Dict] = []
    
    def init_plugin(self, config: Optional[dict] = None):
        """初始化插件"""
        if config:
            self._enabled = config.get("enabled", False)
            self._notify = config.get("notify", False)
            self._use_proxy = config.get("use_proxy", True)
            self._onlyonce = config.get("onlyonce", False)
            self._api_key = config.get("api_key", "")
            self._auto_bet = config.get("auto_bet", False)
            self._bet_seconds_before = config.get("bet_seconds_before", 10)
            self._bet_amount = config.get("bet_amount", "100")
            
        if self._enabled:
            # 启动定时任务调度器
            if not self._scheduler:
                self._scheduler = BackgroundScheduler(timezone=settings.TZ)
                self._scheduler.start()
                
            # 如果启用了立即运行一次
            if self._onlyonce:
                self._scheduler.add_job(
                    func=self.__sync_bet_games,
                    trigger='date',
                    run_date=datetime.now() + timedelta(seconds=3),
                    name="M-Team菠菜比赛同步"
                )
                # 重置一次性运行状态
                self._onlyonce = False
                self.update_config({
                    "onlyonce": False,
                    "enabled": self._enabled,
                    "notify": self._notify,
                    "use_proxy": self._use_proxy,
                    "api_key": self._api_key,
                    "auto_bet": self._auto_bet,
                    "bet_seconds_before": self._bet_seconds_before,
                    "bet_amount": self._bet_amount
                })
                
            logger.info("M-Team菠菜助手插件已启动")
            
    def __sync_bet_games(self):
        """同步比赛数据"""
        try:
            with self._lock:
                logger.info("开始同步M-Team菠菜比赛数据...")
                
                # 获取比赛列表
                games = self.__get_live_games()
                if not games:
                    logger.warning("未获取到比赛数据")
                    return
                    
                self._bet_games = games
                logger.info(f"成功获取到 {len(games)} 场比赛")
                
                # 如果启用了自动下注，为每场比赛安排下注任务
                if self._auto_bet:
                    self.__schedule_auto_bets(games)
                    
                # 发送通知
                if self._notify:
                    self.post_message(
                        mtype="info",
                        title="M-Team菠菜助手",
                        text=f"成功同步 {len(games)} 场比赛数据"
                    )
                    
        except Exception as e:
            logger.error(f"同步比赛数据失败: {str(e)}")
            if self._notify:
                self.post_message(
                    mtype="error",
                    title="M-Team菠菜助手",
                    text=f"同步比赛数据失败: {str(e)}"
                )
                
    def __get_live_games(self) -> List[Dict]:
        """获取LIVE比赛列表"""
        try:
            # 首先尝试主API
            api_url = self._main_api_url
            games = self.__fetch_games_from_api(api_url)
            
            if not games:
                # 如果主API失败，尝试备用API
                logger.warning("主API获取失败，尝试备用API")
                api_url = self._backup_api_url
                games = self.__fetch_games_from_api(api_url)
                
            return games if games else []
            
        except Exception as e:
            logger.error(f"获取比赛列表失败: {str(e)}")
            return []
            
    def __fetch_games_from_api(self, api_url: str) -> Optional[List[Dict]]:
        """从指定API获取比赛数据"""
        try:
            url = f"{api_url}/api/bet/findBetgameList"
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "x-api-key": self._api_key
            }
            data = {
                "active": "LIVE",
                "fix": 0
            }
            
            response = RequestUtils(
                proxies=self._get_proxies() if self._use_proxy else None,
                timeout=30
            ).post(url, headers=headers, data=data)
            
            if response and response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    return result.get("data", [])
                else:
                    logger.error(f"API返回错误: {result.get('message', 'Unknown error')}")
            else:
                logger.error(f"API请求失败，状态码: {response.status_code if response else 'None'}")
                
        except Exception as e:
            logger.error(f"请求API失败: {str(e)}")
            
        return None
        
    def __schedule_auto_bets(self, games: List[Dict]):
        """为比赛安排自动下注任务"""
        if not games:
            return
            
        for game in games:
            try:
                # 解析比赛截止时间
                end_time_str = game.get("endTime")
                if not end_time_str:
                    continue
                    
                # 假设时间格式为ISO格式或时间戳
                if isinstance(end_time_str, str):
                    end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
                else:
                    end_time = datetime.fromtimestamp(end_time_str)
                    
                # 计算下注时间（比赛截止前N秒）
                bet_time = end_time - timedelta(seconds=self._bet_seconds_before)
                
                # 如果下注时间已过，跳过
                if bet_time <= datetime.now():
                    continue
                    
                # 获取投注选项（这里需要根据实际数据结构调整）
                bet_options = game.get("betOptions", [])
                if not bet_options:
                    continue
                    
                # 选择第一个投注选项（可以根据策略调整）
                opt_id = bet_options[0].get("id")
                if not opt_id:
                    continue
                    
                # 添加定时下注任务
                job_id = f"auto_bet_{game.get('id')}_{opt_id}"
                self._scheduler.add_job(
                    func=self.__auto_bet,
                    trigger=DateTrigger(run_date=bet_time),
                    args=[opt_id, self._bet_amount],
                    id=job_id,
                    name=f"自动下注-{game.get('name', 'Unknown')}",
                    replace_existing=True
                )
                
                logger.info(f"已安排自动下注任务: {game.get('name')} 在 {bet_time}")
                
            except Exception as e:
                logger.error(f"安排自动下注任务失败: {str(e)}")
                
    def __auto_bet(self, opt_id: str, bonus: str):
        """执行自动下注"""
        try:
            logger.info(f"开始执行自动下注: 选项ID={opt_id}, 金额={bonus}")
            
            # 首先尝试主API
            api_url = self._main_api_url
            success = self.__place_bet(api_url, opt_id, bonus)
            
            if not success:
                # 如果主API失败，尝试备用API
                logger.warning("主API下注失败，尝试备用API")
                api_url = self._backup_api_url
                success = self.__place_bet(api_url, opt_id, bonus)
                
            # 记录下注历史
            bet_record = {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "opt_id": opt_id,
                "bonus": bonus,
                "success": success,
                "api_url": api_url
            }
            self._bet_history.append(bet_record)
            
            # 发送通知
            if self._notify:
                status = "成功" if success else "失败"
                self.post_message(
                    mtype="success" if success else "error",
                    title="M-Team菠菜助手",
                    text=f"自动下注{status}: 选项ID={opt_id}, 金额={bonus}"
                )
                
        except Exception as e:
            logger.error(f"执行自动下注失败: {str(e)}")
            if self._notify:
                self.post_message(
                    mtype="error",
                    title="M-Team菠菜助手",
                    text=f"自动下注失败: {str(e)}"
                )
                
    def __place_bet(self, api_url: str, opt_id: str, bonus: str) -> bool:
        """发送下注请求"""
        try:
            url = f"{api_url}/api/bet/betgameOdds"
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "x-api-key": self._api_key
            }
            data = {
                "optId": opt_id,
                "bonus": bonus
            }
            
            response = RequestUtils(
                proxies=self._get_proxies() if self._use_proxy else None,
                timeout=30
            ).post(url, headers=headers, data=data)
            
            if response and response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    logger.info(f"下注成功: {result}")
                    return True
                else:
                    logger.error(f"下注失败: {result.get('message', 'Unknown error')}")
            else:
                logger.error(f"下注请求失败，状态码: {response.status_code if response else 'None'}")
                
        except Exception as e:
            logger.error(f"发送下注请求失败: {str(e)}")
            
        return False
        
    def _get_proxies(self):
        """获取代理设置"""
        return settings.PROXY if self._use_proxy else None
        
    def refresh_bet_games(self):
        """手动刷新比赛列表"""
        self.__sync_bet_games()
        
    def get_service(self) -> List[Dict[str, Any]]:
        """注册定时任务服务"""
        if self._enabled:
            return [{
                "id": "MTeamBetSync",
                "name": "M-Team菠菜比赛同步",
                "trigger": "cron",
                "func": self.__sync_bet_games,
                "kwargs": {},
                "minute": "*/5"  # 每5分钟同步一次
            }]
        return []
        
    def get_state(self) -> bool:
        """获取插件状态"""
        return self._enabled
        
    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """拼装插件设置页面"""
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
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                            'hint': '开启后将启用M-Team菠菜助手功能',
                                            'persistent-hint': True
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
                                            'model': 'use_proxy',
                                            'label': '使用代理',
                                            'hint': '访问M-Team API时是否使用代理',
                                            'persistent-hint': True
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
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'notify',
                                            'label': '开启通知',
                                            'hint': '运行结果是否发送通知',
                                            'persistent-hint': True
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
                                            'model': 'onlyonce',
                                            'label': '立即运行一次',
                                            'hint': '保存配置后立即运行一次',
                                            'persistent-hint': True
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
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'api_key',
                                            'label': 'M-Team API Key',
                                            'placeholder': '请输入M-Team API密钥',
                                            'hint': '在M-Team个人设置中获取API密钥',
                                            'persistent-hint': True,
                                            'type': 'password'
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
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'auto_bet',
                                            'label': '自动下注',
                                            'hint': '是否启用自动下注功能',
                                            'persistent-hint': True
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
                                            'model': 'bet_seconds_before',
                                            'label': '提前下注秒数',
                                            'placeholder': '10',
                                            'hint': '比赛截止前多少秒开始下注',
                                            'persistent-hint': True,
                                            'type': 'number'
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
                                            'model': 'bet_amount',
                                            'label': '下注金额',
                                            'placeholder': '100',
                                            'hint': '每次自动下注的积分数量',
                                            'persistent-hint': True
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
            "use_proxy": True,
            "notify": False,
            "onlyonce": False,
            "api_key": "",
            "auto_bet": False,
            "bet_seconds_before": 10,
            "bet_amount": "100"
        }
        
    def get_page(self) -> List[dict]:
        """查询页面（比赛列表 + 下注历史）"""
        # 构建比赛列表表格
        bet_games_table = {
            'component': 'VCard',
            'props': {
                'variant': 'tonal',
                'class': 'mb-4'
            },
            'content': [
                {
                    'component': 'VCardTitle',
                    'props': {
                        'class': 'd-flex align-center'
                    },
                    'content': [
                        {
                            'component': 'VIcon',
                            'props': {
                                'icon': 'mdi-trophy-outline',
                                'class': 'me-2'
                            }
                        },
                        {
                            'component': 'span',
                            'text': '比赛列表'
                        },
                        {
                            'component': 'VSpacer'
                        },
                        {
                            'component': 'VBtn',
                            'props': {
                                'variant': 'outlined',
                                'size': 'small',
                                'color': 'primary',
                                'onClick': lambda: self.refresh_bet_games()
                            },
                            'content': [
                                {
                                    'component': 'VIcon',
                                    'props': {
                                        'icon': 'mdi-refresh'
                                    }
                                },
                                {
                                    'component': 'span',
                                    'text': '刷新'
                                }
                            ]
                        }
                    ]
                },
                {
                    'component': 'VCardText',
                    'content': [
                        {
                            'component': 'VDataTable',
                            'props': {
                                'headers': [
                                    {'title': '比赛名称', 'key': 'name'},
                                    {'title': '状态', 'key': 'status'},
                                    {'title': '开始时间', 'key': 'startTime'},
                                    {'title': '截止时间', 'key': 'endTime'},
                                    {'title': '投注选项', 'key': 'options'}
                                ],
                                'items': [
                                    {
                                        'name': game.get('name', 'Unknown'),
                                        'status': game.get('status', 'Unknown'),
                                        'startTime': game.get('startTime', 'Unknown'),
                                        'endTime': game.get('endTime', 'Unknown'),
                                        'options': len(game.get('betOptions', []))
                                    } for game in self._bet_games
                                ],
                                'density': 'compact',
                                'hover': True
                            }
                        }
                    ]
                }
            ]
        }
        
        # 构建下注历史表格
        bet_history_table = {
            'component': 'VCard',
            'props': {
                'variant': 'tonal'
            },
            'content': [
                {
                    'component': 'VCardTitle',
                    'content': [
                        {
                            'component': 'VIcon',
                            'props': {
                                'icon': 'mdi-history',
                                'class': 'me-2'
                            }
                        },
                        {
                            'component': 'span',
                            'text': '下注历史'
                        }
                    ]
                },
                {
                    'component': 'VCardText',
                    'content': [
                        {
                            'component': 'VDataTable',
                            'props': {
                                'headers': [
                                    {'title': '时间', 'key': 'time'},
                                    {'title': '选项ID', 'key': 'opt_id'},
                                    {'title': '金额', 'key': 'bonus'},
                                    {'title': '结果', 'key': 'success'},
                                    {'title': 'API地址', 'key': 'api_url'}
                                ],
                                'items': self._bet_history,
                                'density': 'compact',
                                'hover': True
                            }
                        }
                    ]
                }
            ]
        }
        
        return [bet_games_table, bet_history_table]
        
    def stop_service(self) -> None:
        """停止插件任务"""
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown()
                self._scheduler = None
                
            logger.info("M-Team菠菜助手插件已停止")
            
        except Exception as e:
            logger.error(f"停止插件服务失败: {str(e)}")
