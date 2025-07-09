from typing import List, Dict, Optional
from .models import Match, MatchOption
from datetime import datetime, timedelta
import json

class BetLogic:
    def __init__(self, config: Dict):
        self.config = config
        self.min_odds = config.get("min_odds", 1.5)
        self.bet_amount = config.get("bet_amount", 100)
        self.max_daily_bet = config.get("max_daily_bet", 0.2)  # 20% of balance
        self.stop_loss = config.get("stop_loss", 0.2)  # 20% daily loss
        self.bet_before_seconds = config.get("bet_before_seconds", 10)
        self.daily_bets = 0
        self.daily_loss = 0
        self.bet_records = []

    def load_external_odds(self, match_id: str) -> Dict:
        """加载外部赔率（从配置或文件）"""
        try:
            with open("external_odds.json", "r") as f:
                return json.load(f).get(match_id, {})
        except:
            return {}

    def save_external_odds(self, match_id: str, odds: Dict):
        """保存外部赔率"""
        try:
            with open("external_odds.json", "r+") as f:
                data = json.load(f)
                data[match_id] = odds
                f.seek(0)
                json.dump(data, f)
        except:
            with open("external_odds.json", "w") as f:
                json.dump({match_id: odds}, f)

    def calculate_kelly(self, odds: float, external_odds: float) -> float:
        """凯利公式计算下注比例"""
        p = 1 / external_odds if external_odds else 0.5
        q = 1 - p
        b = odds - 1
        f = (b * p - q) / b if b > 0 else 0
        return max(0, min(f, 0.1))  # 限制 0~10%

    def dynamic_probability(self, match: Match, external_odds: Dict) -> Optional[MatchOption]:
        """动态概率均衡逻辑"""
        total_bet = sum(float(opt.bonusTotal or 0) for opt in match.optionsList)
        if total_bet == 0:
            return None
        best_option = None
        max_value = 0
        for opt in match.optionsList:
            weight = float(opt.bonusTotal or 0) / total_bet
            external_p = 1 / external_odds.get(opt.text, opt.odds) if external_odds else 0.5
            p_adj = (external_p * weight) / (1 + match.taxRate)
            value = p_adj - (1 / opt.odds)
            if value > max_value and opt.odds >= self.min_odds:
                max_value = value
                best_option = opt
        return best_option

    def select_option(self, match: Match, balance: float) -> Optional[Dict]:
        """选择下注选项和金额"""
        external_odds = self.load_external_odds(match.id)
        
        # 逻辑 1: 套利
        for opt in match.optionsList:
            ext_odds = external_odds.get(opt.text, 0)
            if ext_odds and opt.odds > ext_odds and opt.odds >= self.min_odds:
                f = self.calculate_kelly(opt.odds, ext_odds)
                amount = min(f * balance, self.bet_amount, balance * 0.1)
                if self.daily_bets + amount <= balance * self.max_daily_bet:
                    return {"option": opt, "amount": amount}
        
        # 逻辑 2: 动态概率均衡
        best_option = self.dynamic_probability(match, external_odds)
        if best_option:
            f = self.calculate_kelly(best_option.odds, external_odds.get(best_option.text, best_option.odds))
            amount = min(f * balance, self.bet_amount, balance * 0.1)
            if self.daily_bets + amount <= balance * self.max_daily_bet:
                return {"option": best_option, "amount": amount}
        
        # 逻辑 3: 高赔率
        best_option = max(match.optionsList, key=lambda x: x.odds if x.odds >= self.min_odds else 0)
        if best_option.odds >= self.min_odds:
            amount = min(self.bet_amount, balance * 0.1)
            if self.daily_bets + amount <= balance * self.max_daily_bet:
                return {"option": best_option, "amount": amount}
        
        return None

    def check_bet_validity(self, game_id: str, option_id: str) -> bool:
        """检查是否已下注"""
        return not any(record["game_id"] == game_id and record["option_id"] == option_id for record in self.bet_records)

    def update_bet_records(self, game_id: str, option_id: str, amount: float, success: bool):
        """更新下注记录"""
        self.bet_records.append({
            "game_id": game_id,
            "option_id": option_id,
            "amount": amount,
            "success": success,
            "timestamp": datetime.now().isoformat()
        })
        self.daily_bets += amount if success else 0