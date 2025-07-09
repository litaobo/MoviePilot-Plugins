from datetime import datetime, timedelta
from .api import MTeamAPI
from .bet_logic import BetLogic
from app.log import logger

try:
    from app.utils import post_message
    from app.schemas import NotificationType
except ImportError:
    logger.warning("app.utils.post_message 或 app.schemas.NotificationType 不可用，通知功能将受限")
    post_message = None
    NotificationType = None
from app.log import logger

class EventHandler:
    def __init__(self, api: MTeamAPI, bet_logic: BetLogic, config: Dict):
        self.api = api
        self.bet_logic = bet_logic
        self.config = config
        self.uid = config.get("uid", "326922")

    async def refresh_matches(self):
        """刷新比赛列表并调度下注任务"""
        logger.info("开始刷新比赛列表")
        try:
            matches = await self.api.get_matches()
            for match in matches:
             if post_message and NotificationType:
                post_message(
                    mtype="SiteMessage",
                    title="【M-Team 自动下注】新比赛",
                    text=f"━━━━━━━━━━━━━━\n"
                         f"📝 新比赛：{match.heading}\n"
                         f"⏱ 截止时间：{match.endtime}"
                )
                end_time = datetime.strptime(match.endtime, "%Y-%m-%d %H:%M:%S")
                now = datetime.now()
                if end_time > now:
                    seconds_until_bet = (end_time - now).total_seconds() - self.config.get("bet_before_seconds", 10)
                    if seconds_until_bet > 0:
                        logger.info(f"调度下注任务: 比赛 {match.heading} 将于 {seconds_until_bet} 秒后执行")
                        # 动态调度下注任务
                        from apscheduler.schedulers.asyncio import AsyncIOScheduler
                        scheduler = AsyncIOScheduler()
                        scheduler.add_job(
                            self.place_auto_bet,
                            "date",
                            run_date=datetime.now() + timedelta(seconds=seconds_until_bet),
                            args=[match]
                        )
                        scheduler.start()
            return matches
        except Exception as e:
            logger.error(f"刷新比赛列表失败: {e}")
         if post_message and NotificationType:
            post_message(
                mtype="SiteMessage",
                title="【M-Team 自动下注】错误",
                text=f"━━━━━━━━━━━━━━\n"
                     f"⚠️ 错误提示：刷新比赛列表失败\n"
                     f"📄 详情：{str(e)}"
            )
            return []

    async def place_auto_bet(self, match):
        """自动下注"""
        logger.info(f"执行自动下注: 比赛 {match.heading}")
        try:
            profile = await self.api.get_user_profile(self.uid)
            if not profile or profile.bonus < self.bet_logic.bet_amount:
             if post_message and NotificationType:
                post_message(
                    mtype="SiteMessage",
                    title="【M-Team 自动下注】余额不足",
                    text=f"━━━━━━━━━━━━━━\n"
                         f"⚠️ 当前积分：{profile.bonus if profile else 0}\n"
                         f"📄 需至少 {self.bet_logic.bet_amount} 积分"
                )
                return
            
            selection = self.bet_logic.select_option(match, profile.bonus)
            if not selection:
                logger.info(f"比赛 {match.heading} 无适合下注选项")
                return
            
            option = selection["option"]
            amount = selection["amount"]
            if not self.bet_logic.check_bet_validity(match.id, option.id):
             if post_message and NotificationType:
                post_message(
                    mtype="SiteMessage",
                    title="【M-Team 自动下注】重复下注",
                    text=f"━━━━━━━━━━━━━━\n"
                         f"📝 比赛：{match.heading}\n"
                         f"⚠️ 已下注，跳过"
                )
                return
            
            result = await self.api.place_bet(option.id, amount)
            if result.get("code") == "0":
             if post_message and NotificationType:
                post_message(
                    mtype="SiteMessage",
                    title="【M-Team 自动下注】下注成功",
                    text=f"━━━━━━━━━━━━━━\n"
                         f"📝 比赛：{match.heading}\n"
                         f"🎯 选项：{option.text}\n"
                         f"💰 金额：{amount} 积分"
                )
                self.bet_logic.update_bet_records(match.id, option.id, amount, True)
            else:
             if post_message and NotificationType:
                post_message(
                    mtype="SiteMessage",
                    title="【M-Team 自动下注】下注失败",
                    text=f"━━━━━━━━━━━━━━\n"
                         f"📝 比赛：{match.heading}\n"
                         f"⚠️ 错误：{result.get('message')}"
                )
                self.bet_logic.update_bet_records(match.id, option.id, amount, False)
        except Exception as e:
            logger.error(f"自动下注失败: {e}")
         if post_message and NotificationType:
            post_message(
                mtype="SiteMessage",
                title="【M-Team 自动下注】错误",
                text=f"━━━━━━━━━━━━━━\n"
                     f"⚠️ 错误提示：自动下注失败\n"
                     f"📄 详情：{str(e)}"
            )
