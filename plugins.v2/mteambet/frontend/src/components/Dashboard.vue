<template>
  <v-container>
    <v-card>
      <v-card-title>
        插件状态: <v-chip :color="status.enabled ? 'green' : 'red'">{{ status.enabled ? '启用' : '禁用' }}</v-chip>
        代理: <v-chip :color="status.use_proxy ? 'blue' : 'yellow'">{{ status.use_proxy ? '启用' : '禁用' }}</v-chip>
        下次执行: {{ status.next_run }}
      </v-card-title>
      <v-switch v-model="darkTheme" label="暗色主题" @change="toggleTheme" />
    </v-card>

    <v-card class="mt-4">
      <v-card-title>比赛列表</v-card-title>
      <v-btn color="primary" @click="refreshMatches">刷新比赛列表</v-btn>
      <v-data-table
        :headers="matchHeaders"
        :items="matches"
        :loading="loading"
        @click:row="showBetDetails"
      >
        <template v-slot:item.odds="{ item }">
          <div v-for="opt in item.optionsList" :key="opt.id">
            {{ opt.text }}: {{ opt.odds }}
            <v-text-field
              v-model="externalOdds[item.id][opt.text]"
              label="外部赔率"
              type="number"
              step="0.01"
              @blur="saveExternalOdds(item.id)"
            />
          </div>
        </template>
        <template v-slot:item.actions="{ item }">
          <v-btn @click.stop="showBetDetails(item)">查看详情</v-btn>
          <v-btn v-if="isFinished(item.endtime)" @click.stop="showResult(item.id)">查看结果</v-btn>
        </template>
      </v-data-table>
    </v-card>

    <v-dialog v-model="showDetails" max-width="600">
      <v-card>
        <v-card-title>{{ selectedMatch?.heading }}</v-card-title>
        <v-list>
          <v-list-item v-for="bet in betDetails" :key="bet.id">
            <v-list-item-content>
              <v-list-item-title>用户: {{ bet.userid }}</v-list-item-title>
              <v-list-item-subtitle>选项: {{ bet.optionid }} | 金额: {{ bet.bonus }} 积分</v-list-item-subtitle>
            </v-list-item-content>
          </v-list-item>
        </v-list>
        <v-card-text>总下注金额: {{ totalBetAmount }} 积分</v-card-text>
        <v-btn @click="showDetails = false">关闭</v-btn>
      </v-card>
    </v-dialog>

    <v-dialog v-model="showResultDialog" max-width="600">
      <v-card>
        <v-card-title>比赛结果</v-card-title>
        <v-card-text v-html="resultContent"></v-card-text>
        <v-btn @click="showResultDialog = false">关闭</v-btn>
      </v-card>
    </v-dialog>
  </v-container>
</template>
<script>
export default {
  data() {
    return {
      status: { enabled: true, use_proxy: false, next_run: "" },
      darkTheme: false,
      matches: [],
      externalOdds: {},
      betDetails: [],
      totalBetAmount: 0,
      selectedMatch: null,
      showDetails: false,
      showResultDialog: false,
      resultContent: "",
      loading: false,
      matchHeaders: [
        { text: "比赛名称", value: "heading" },
        { text: "队伍", value: "undertext" },
        { text: "赔率", value: "odds" },
        { text: "截止时间", value: "endtime" },
        { text: "总下注数", value: "countall" },
        { text: "下注人数", value: "bettors" },
        { text: "操作", value: "actions" }
      ]
    };
  },
  async mounted() {
    await this.refreshMatches();
    this.loadExternalOdds();
  },
  methods: {
    async refreshMatches() {
      this.loading = true;
      const response = await fetch("/api/v2/plugins/mteam-auto-bet/matches");
      this.matches = await response.json();
      this.matches.forEach(match => {
        this.$set(this.externalOdds, match.id, {});
        match.optionsList.forEach(opt => {
          this.$set(this.externalOdds[match.id], opt.text, "");
        });
        this.getBettorsCount(match.id);
      });
      this.loading = false;
    },
    async getBettorsCount(matchId) {
      const response = await fetch(`/api/v2/plugins/mteam-auto-bet/bet-details?gameId=${matchId}`);
      const bets = await response.json();
      const bettors = new Set(bets.map(bet => bet.userid)).size;
      const match = this.matches.find(m => m.id === matchId);
      if (match) this.$set(match, "bettors", bettors);
    },
    async saveExternalOdds(matchId) {
      await fetch("/api/v2/plugins/mteam-auto-bet/external-odds", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ matchId, odds: this.externalOdds[matchId] })
      });
    },
    async showBetDetails(match) {
      this.selectedMatch = match;
      const response = await fetch(`/api/v2/plugins/mteam-auto-bet/bet-details?gameId=${match.id}`);
      this.betDetails = await response.json();
      this.totalBetAmount = match.optionsList.reduce((sum, opt) => sum + (parseFloat(opt.bonusTotal) || 0), 0);
      this.showDetails = true;
    },
    async showResult(matchId) {
      const posts = await fetch("/api/v2/plugins/mteam-auto-bet/result-posts").then(res => res.json());
      const post = posts.find(p => p.subject.includes(matchId));
      if (post) {
        const response = await fetch(`/api/v2/plugins/mteam-auto-bet/post-detail?tid=${post.id}`);
        const data = await response.json();
        this.resultContent = data.data?.comments?.data[0]?.body || "无结果";
        this.showResultDialog = true;
      }
    },
    isFinished(endtime) {
      return new Date(endtime) < new Date();
    },
    toggleTheme() {
      this.$vuetify.theme.dark = this.darkTheme;
    }
  }
};
</script>