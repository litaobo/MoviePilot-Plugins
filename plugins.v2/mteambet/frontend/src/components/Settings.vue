<template>
  <v-form @submit.prevent="saveConfig">
    <v-card-title>基本设置</v-card-title>
    <v-switch v-model="config.enabled" label="启用插件" />
    <v-switch v-model="config.use_proxy" label="使用代理" />
    <v-text-field v-model="config.api_key" label="M-Team API Key" type="password" />
    <v-text-field v-model="config.uid" label="用户 ID" />

    <v-card-title>执行设置</v-card-title>
    <v-select v-model="config.bet_strategy" :items="['套利', '动态概率均衡', '高赔率']" label="下注逻辑" />
    <v-select v-model="config.match_type" :items="['英雄联盟', '足球', '篮球']" label="比赛类型" />
    <v-slider v-model="config.min_odds" label="最低赔率" :min="1.0" :max="5.0" step="0.1" />

    <v-card-title>自动下注设置</v-card-title>
    <v-switch v-model="config.auto_bet" label="自动下注" />
    <v-text-field v-model.number="config.bet_amount" label="固定下注金额" type="number" />
    <v-text-field v-model.number="config.bet_before_seconds" label="下注前秒数" type="number" min="5" max="30" />
    <v-text-field v-model.number="config.max_daily_bet" label="每日下注比例 (%)" type="number" min="0" max="100" />
    <v-text-field v-model.number="config.stop_loss" label="止损比例 (%)" type="number" min="0" max="100" />

    <v-btn type="submit" color="primary">保存</v-btn>
  </v-form>
</template>
<script>
export default {
  data() {
    return {
      config: {
        enabled: true,
        use_proxy: false,
        api_key: "",
        uid: "326922",
        bet_strategy: "套利",
        match_type: "英雄联盟",
        min_odds: 1.5,
        auto_bet: true,
        bet_amount: 100,
        bet_before_seconds: 10,
        max_daily_bet: 20,
        stop_loss: 20
      }
    };
  },
  methods: {
    async saveConfig() {
      await fetch("/api/v2/plugins/mteam-auto-bet/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(this.config)
      });
      this.$emit("notify", "配置已保存");
    }
  }
};
</script>