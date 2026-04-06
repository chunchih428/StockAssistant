"""Dashboard HTML template."""
DASHBOARD_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Portfolio Pulse</title>
<script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft JhengHei',sans-serif;background:#f8fafc;color:#1e293b;line-height:1.6;-webkit-font-smoothing:antialiased}
::-webkit-scrollbar{width:6px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:3px}::-webkit-scrollbar-thumb:hover{background:#94a3b8}
@keyframes fadeUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
.anim{animation:fadeUp .4s cubic-bezier(.16,1,.3,1) forwards}
.panel{background:#fff;border:1px solid #e2e8f0;border-radius:1.25rem;box-shadow:0 4px 6px -1px rgba(0,0,0,.04),0 2px 4px -1px rgba(0,0,0,.02);transition:box-shadow .2s}
.panel:hover{box-shadow:0 8px 16px -4px rgba(0,0,0,.08)}
.text-up{color:#059669}.text-down{color:#dc2626}.bg-up{background:#ecfdf5}.bg-down{background:#fef2f2}
.sg{display:grid;grid-template-columns:repeat(2,1fr);gap:.5rem}
.sb{padding:.65rem .75rem;border-radius:.75rem;background:#f8fafc;border:1px solid #e2e8f0;transition:background .15s}
.sb:hover{background:#f1f5f9}
.sl{font-size:.7rem;color:#94a3b8;margin-bottom:.15rem}
.sv{font-size:.95rem;font-weight:600;color:#1e293b}
.pt{height:6px;background:#e2e8f0;border-radius:3px;overflow:hidden}
.pf{height:100%;border-radius:3px;transition:width .8s ease-out}
.nc{padding:.85rem;border-radius:.85rem;background:#f8fafc;border:1px solid #e2e8f0;transition:all .15s;cursor:default}
.nc:hover{background:#fff;border-color:#93c5fd;box-shadow:0 2px 8px rgba(59,130,246,.08)}
.nc a{text-decoration:none;color:#334155;font-size:.84rem;line-height:1.5}.nc a:hover{color:#2563eb}
.nm{font-size:.7rem;color:#94a3b8;margin-top:.35rem;display:flex;align-items:center;gap:.35rem}
.rel-tag{font-size:.65rem;padding:.1rem .45rem;border-radius:.75rem;white-space:nowrap;flex-shrink:0;font-weight:600}
.rel-high{background:#dcfce7;color:#166534;border:1px solid #bbf7d0}
.rel-mid{background:#fef9c3;color:#854d0e;border:1px solid #fde68a}
.rel-low{background:#f1f5f9;color:#94a3b8;border:1px solid #e2e8f0}
.na-summary{display:flex;flex-wrap:wrap;align-items:center;gap:.5rem;margin-bottom:1rem;padding:.65rem .85rem;border-radius:.75rem;background:#f8fafc;border:1px solid #e2e8f0}
.na-sent{font-size:.78rem;font-weight:700;padding:.2rem .6rem;border-radius:.5rem;letter-spacing:.02em}
.na-sent-strongly_bullish{background:#16a34a;color:#fff}.na-sent-bullish{background:#bbf7d0;color:#14532d}.na-sent-neutral{background:#f1f5f9;color:#475569}.na-sent-mixed{background:#fef9c3;color:#854d0e}.na-sent-bearish{background:#fee2e2;color:#991b1b}.na-sent-strongly_bearish{background:#450a0a;color:#fff}
.na-theme{font-size:.78rem;color:#475569;flex:1;min-width:0}
.na-chip{font-size:.68rem;padding:.15rem .45rem;border-radius:.75rem;font-weight:600;border:1px solid}
.na-chip-bull{background:#f0fdf4;color:#166534;border-color:#bbf7d0}.na-chip-bear{background:#fef2f2;color:#991b1b;border-color:#fecaca}.na-chip-neut{background:#f1f5f9;color:#64748b;border-color:#e2e8f0}
.na-grid{display:grid;grid-template-columns:1fr 1fr;gap:.75rem}
@media(max-width:700px){.na-grid{grid-template-columns:1fr}}
.na-col{display:flex;flex-direction:column;gap:.45rem}
.na-col-head{font-size:.78rem;font-weight:700;padding:.25rem .6rem;border-radius:.5rem;margin-bottom:.15rem}
.na-col-bull .na-col-head{background:#f0fdf4;color:#166534}.na-col-bear .na-col-head{background:#fef2f2;color:#991b1b}
.na-item{padding:.65rem .75rem;border-radius:.7rem;border:1px solid #e2e8f0;background:#fff;transition:all .15s}
.na-item:hover{box-shadow:0 2px 8px rgba(0,0,0,.05)}
.na-item[style*="cursor:pointer"]:hover{box-shadow:0 4px 12px rgba(0,0,0,.1);transform:translateY(-1px)}
.na-item-title{display:flex;align-items:flex-start;gap:.4rem}
.na-item-title a{text-decoration:none;color:#334155;font-size:.82rem;line-height:1.45;flex:1;white-space:pre-wrap}.na-item-title a:hover{color:#2563eb}
.na-reason{font-size:.75rem;color:#64748b;line-height:1.55;margin-top:.3rem;white-space:pre-wrap}
.na-meta{font-size:.68rem;color:#94a3b8;margin-top:.25rem;display:flex;align-items:center;gap:.3rem}
.imp-tag{font-size:.62rem;padding:.1rem .4rem;border-radius:.5rem;font-weight:700;flex-shrink:0;text-transform:uppercase;letter-spacing:.03em}
.imp-high-bull{background:#7c3aed!important;color:#fff}.imp-medium-bull{background:#eab308!important;color:#fff}.imp-low-bull{background:#f1f5f9;color:#64748b}
.imp-high-bear{background:#7c3aed!important;color:#fff}.imp-medium-bear{background:#eab308!important;color:#fff}.imp-low-bear{background:#f1f5f9;color:#64748b}
.imp-high-neut{background:#7c3aed!important;color:#fff}.imp-medium-neut{background:#eab308!important;color:#fff}.imp-low-neut{background:#f1f5f9;color:#94a3b8}
.na-neutral-wrap{margin-top:.5rem}
.na-neutral-btn{background:none;border:1px solid #e2e8f0;border-radius:.5rem;padding:.3rem .7rem;font-size:.72rem;color:#64748b;cursor:pointer;display:flex;align-items:center;gap:.3rem}
.na-neutral-btn:hover{background:#f8fafc}
.ac{font-size:.85rem;line-height:1.8}
.ac h1,.ac h2,.ac h3{margin:1rem 0 .5rem;color:#0f172a}
.ac h2{font-size:1rem;border-bottom:1px solid #e2e8f0;padding-bottom:.4rem}
.ac h3{font-size:.92rem}
.ac table{width:100%;border-collapse:collapse;margin:.6rem 0;font-size:.82rem}
.ac th,.ac td{padding:4px 8px;border:1px solid #e2e8f0;text-align:left}
.ac th{background:#f8fafc;font-weight:600}
.ac ul,.ac ol{padding-left:1.2rem;margin:.5rem 0}
.ac strong{color:#0f172a}
.ac blockquote{border-left:3px solid #3b82f6;padding:.5rem 1rem;margin:.6rem 0;background:#f8fafc;border-radius:0 .4rem .4rem 0}
.ab{display:flex;height:1.5rem;border-radius:.5rem;overflow:hidden;gap:2px}
.as{transition:width .3s;cursor:pointer;position:relative}.as:hover{opacity:.85}
.ot{width:100%;border-collapse:collapse;font-size:.82rem}
.ot th,.ot td{padding:.5rem .65rem;border:1px solid #e2e8f0;text-align:left}
.ot th{background:#f1f5f9;font-weight:600;white-space:nowrap}.ot tr:hover{background:#f8fafc}
.ot td.num{text-align:right;font-variant-numeric:tabular-nums}
.badge{display:inline-flex;align-items:center;gap:.25rem;font-size:.7rem;font-weight:600;padding:.15rem .55rem;border-radius:.4rem}
.view-btn{padding:.45rem 1rem;border-radius:.5rem;border:1px solid #e2e8f0;cursor:pointer;font-size:.8rem;font-weight:600;transition:all .15s;background:#fff;color:#64748b}
.view-btn.active{background:#0f172a;color:#fff;border-color:#0f172a;box-shadow:0 2px 4px rgba(0,0,0,.1)}
.kpi{text-align:center;padding:1rem;border-radius:1rem;background:#f8fafc;border:1px solid #e2e8f0;flex:1;min-width:140px}
.kpi .kv{font-size:1.35rem;font-weight:800;color:#0f172a;margin-bottom:.15rem}
.kpi .kl{font-size:.7rem;color:#94a3b8}
.cat-hdr{display:flex;align-items:center;gap:.5rem;padding:.5rem 0;margin-top:.75rem;border-bottom:2px solid #e2e8f0;cursor:pointer;user-select:none}
.cat-hdr:first-child{margin-top:0}
.cat-hdr h4{font-size:.88rem;font-weight:700;color:#334155}
.crit-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem}
.crit-card{padding:1rem;border-radius:.85rem;border:1px solid #e2e8f0;background:#fff}
.crit-card h4{font-size:.85rem;font-weight:700;margin-bottom:.5rem;display:flex;align-items:center;gap:.4rem}
.crit-card ul{list-style:none;padding:0;font-size:.78rem;color:#475569}
.crit-card li{padding:.25rem 0;display:flex;align-items:baseline;gap:.35rem}
.crit-card li::before{content:'';width:5px;height:5px;border-radius:50%;flex-shrink:0;margin-top:.35rem}
.row-click{cursor:pointer;transition:background .1s}.row-click:hover{background:#eff6ff!important}
@media(max-width:1024px){.bento{grid-template-columns:1fr!important}.bento>*:first-child{grid-row:auto!important}}
@media(max-width:768px){.kpi-row{flex-direction:column}.ot{font-size:.75rem}}
</style>
</head>
<body>

<div id="app">
  <!-- Header -->
  <header style="position:sticky;top:0;z-index:50;background:rgba(255,255,255,.85);backdrop-filter:blur(12px);border-bottom:1px solid #e2e8f0;padding:1rem 1.5rem;box-shadow:0 1px 3px rgba(0,0,0,.04)">
    <div style="max-width:76rem;margin:0 auto">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.75rem">
        <div style="display:flex;align-items:center;gap:.75rem">
          <div style="width:2.5rem;height:2.5rem;border-radius:.75rem;background:linear-gradient(135deg,#3b82f6,#6366f1);display:flex;align-items:center;justify-content:center;box-shadow:0 2px 8px rgba(59,130,246,.3)">
            <svg width="22" height="22" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
          </div>
          <div>
            <h1 style="font-size:1.15rem;font-weight:800;color:#0f172a;letter-spacing:.02em">Portfolio Pulse</h1>
            <p style="font-size:.7rem;color:#94a3b8">智能投資組合儀表板</p>
          </div>
        </div>
        <!-- View Toggle -->
        <div style="display:flex;gap:.35rem;background:#f1f5f9;padding:.25rem;border-radius:.6rem">
          <button class="view-btn" :class="{active:view==='summary'}" @click="switchView('summary')">
            <span style="display:flex;align-items:center;gap:.35rem"><svg width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>持股總覽</span>
          </button>
          <button class="view-btn" :class="{active:view==='scores'}" @click="switchView('scores')">
            <span style="display:flex;align-items:center;gap:.35rem"><svg width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>持股評分</span>
          </button>
          <button class="view-btn" :class="{active:view==='candidates'}" @click="switchView('candidates')">
            <span style="display:flex;align-items:center;gap:.35rem"><svg width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.86L12 17.77 5.82 21l1.18-6.86-5-4.87 6.91-1.01z"/></svg>候選評分</span>
          </button>
          <button class="view-btn" :class="{active:view==='detail'}" @click="switchView('detail')">
            <span style="display:flex;align-items:center;gap:.35rem"><svg width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>個股</span>
          </button>
        </div>
        <div style="text-align:right">
          <p style="font-size:.7rem;color:#94a3b8;margin-bottom:.15rem">投資組合總值</p>
          <div style="display:flex;align-items:baseline;gap:.5rem;justify-content:flex-end">
            <span style="font-size:1.5rem;font-weight:800;color:#0f172a">{{fmtMoney(data.allocation.total_value)}}</span>
            <span :style="{background:data.allocation.total_pnl>=0?'#ecfdf5':'#fef2f2',color:data.allocation.total_pnl>=0?'#059669':'#dc2626',padding:'.15rem .5rem',borderRadius:'.35rem',fontSize:'.82rem',fontWeight:600}">
              {{data.allocation.total_pnl>=0?'+':''}}{{fmtMoney(data.allocation.total_pnl)}}
            </span>
          </div>
        </div>
      </div>
    </div>
  </header>

  <!-- ==================== SUMMARY VIEW ==================== -->
  <main v-if="view==='summary'" style="max-width:76rem;margin:0 auto;padding:1.5rem">

    <!-- KPI Cards -->
    <div class="kpi-row" style="display:flex;gap:1rem;margin-bottom:1.25rem;flex-wrap:wrap">
      <div class="kpi anim">
        <div class="kv">{{fmtMoney(data.allocation.total_value)}}</div>
        <div class="kl">投資組合總值</div>
      </div>
      <div class="kpi anim" style="animation-delay:.05s">
        <div class="kv">{{fmtMoney(data.allocation.total_cost)}}</div>
        <div class="kl">總成本</div>
      </div>
      <div class="kpi anim" style="animation-delay:.1s">
        <div class="kv" :class="data.allocation.total_pnl>=0?'text-up':'text-down'">{{data.allocation.total_pnl>=0?'+':''}}{{fmtMoney(data.allocation.total_pnl)}}</div>
        <div class="kl">未實現損益</div>
      </div>
      <div class="kpi anim" style="animation-delay:.15s">
        <div class="kv" :class="totalPnlPct>=0?'text-up':'text-down'">{{totalPnlPct>=0?'+':''}}{{totalPnlPct.toFixed(2)}}%</div>
        <div class="kl">損益百分比</div>
      </div>
      <div class="kpi anim" style="animation-delay:.2s">
        <div class="kv">{{fmtMoney(data.allocation.cash)}}</div>
        <div class="kl">現金 ({{data.allocation.cash_pct.toFixed(1)}}%)</div>
      </div>
      <div class="kpi anim" style="animation-delay:.25s">
        <div class="kv">{{actualStocksCount}}</div>
        <div class="kl">持股數量</div>
      </div>
    </div>

    <!-- Allocation Bar -->
    <div class="panel anim" style="padding:1.25rem;margin-bottom:1.25rem;animation-delay:.1s">
      <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.75rem">
        <div style="padding:.4rem;background:#fce7f3;border-radius:.5rem;color:#db2777;display:flex"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg></div>
        <h3 style="font-size:.95rem;font-weight:700;color:#0f172a">配置比例</h3>
      </div>
      <div class="ab" style="height:1.75rem;margin-bottom:.5rem">
        <div v-for="(pos,i) in visPos" :key="pos.symbol" class="as" :style="'width:'+pos.alloc_pct+'%;background:'+colors[i%colors.length]" :title="pos.symbol+' '+pos.alloc_pct.toFixed(1)+'%'" @click="goDetail(pos.symbol)"></div>
        <div v-if="data.allocation.options_pct>=0.5" class="as" :style="'width:'+data.allocation.options_pct+'%;background:#818cf8'" title="Options"></div>
        <div v-if="data.allocation.cash_pct>=0.5" class="as" :style="'width:'+data.allocation.cash_pct+'%;background:#cbd5e1'" title="Cash"></div>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:.4rem .85rem">
        <span v-for="(pos,i) in visPos" :key="pos.symbol" style="font-size:.72rem;color:#475569;display:flex;align-items:center;gap:.3rem;cursor:pointer" @click="goDetail(pos.symbol)">
          <span style="width:.55rem;height:.55rem;border-radius:.12rem;flex-shrink:0" :style="'background:'+colors[i%colors.length]"></span>
          {{pos.symbol}} {{pos.alloc_pct.toFixed(1)}}%
        </span>
        <span v-if="data.allocation.options_pct>=0.5" style="font-size:.72rem;color:#475569;display:flex;align-items:center;gap:.3rem">
          <span style="width:.55rem;height:.55rem;border-radius:.12rem;background:#818cf8"></span>Options {{data.allocation.options_pct.toFixed(1)}}%
        </span>
        <span v-if="data.allocation.cash_pct>=0.5" style="font-size:.72rem;color:#475569;display:flex;align-items:center;gap:.3rem">
          <span style="width:.55rem;height:.55rem;border-radius:.12rem;background:#cbd5e1"></span>Cash {{data.allocation.cash_pct.toFixed(1)}}%
        </span>
      </div>
    </div>

    <!-- Portfolio Risk Metrics (Step 5-7: Tech / Fundamental / Risk) -->
    <div v-if="data.allocation.portfolio_risk && data.allocation.portfolio_risk.hhi != null" class="panel anim" style="padding:1.25rem;margin-bottom:1.25rem;animation-delay:.13s">
      <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.85rem">
        <div style="padding:.4rem;background:#fef3c7;border-radius:.5rem;color:#d97706;display:flex"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg></div>
        <h3 style="font-size:.95rem;font-weight:700;color:#0f172a">組合風險指標</h3>
      </div>
      <div style="display:flex;gap:.75rem;flex-wrap:wrap">
        <!-- HHI -->
        <div class="kpi" style="min-width:9rem;padding:.75rem 1rem">
          <div class="kv" style="font-size:1.25rem">{{data.allocation.portfolio_risk.hhi}}</div>
          <div class="kl">HHI 集中度</div>
          <div style="font-size:.68rem;margin-top:.2rem;padding:.1rem .4rem;border-radius:.3rem;display:inline-block"
               :style="data.allocation.portfolio_risk.hhi > 0.25 ? 'background:#fee2e2;color:#dc2626' : data.allocation.portfolio_risk.hhi > 0.15 ? 'background:#fef3c7;color:#d97706' : 'background:#dcfce7;color:#16a34a'">
            {{data.allocation.portfolio_risk.hhi_label}}
          </div>
        </div>
        <!-- Concentration -->
        <div class="kpi" style="min-width:9rem;padding:.75rem 1rem">
          <div class="kv" style="font-size:1.25rem">{{data.allocation.portfolio_risk.top1_concentration}}%</div>
          <div class="kl">最大單一持倉</div>
          <div style="font-size:.68rem;color:#94a3b8;margin-top:.2rem">
            Top-3: {{data.allocation.portfolio_risk.top3_concentration}}% &nbsp;·&nbsp; Top-5: {{data.allocation.portfolio_risk.top5_concentration}}%
          </div>
        </div>
        <!-- Effective Leverage -->
        <div class="kpi" style="min-width:9rem;padding:.75rem 1rem">
          <div class="kv" :style="'font-size:1.25rem' + (data.allocation.portfolio_risk.effective_leverage > 1.5 ? ';color:#dc2626' : '')">
            {{data.allocation.portfolio_risk.effective_leverage}}x
          </div>
          <div class="kl">有效槓桿</div>
          <div style="font-size:.68rem;color:#94a3b8;margin-top:.2rem">含選擇權市值</div>
        </div>
        <!-- Portfolio Beta -->
        <div v-if="data.allocation.portfolio_risk.portfolio_beta != null" class="kpi" style="min-width:9rem;padding:.75rem 1rem">
          <div class="kv" :style="'font-size:1.25rem' + (data.allocation.portfolio_risk.portfolio_beta > 1.5 ? ';color:#dc2626' : '')">
            {{data.allocation.portfolio_risk.portfolio_beta}}
          </div>
          <div class="kl">加權平均 Beta</div>
          <div style="font-size:.68rem;color:#94a3b8;margin-top:.2rem">相對大盤波動</div>
        </div>
      </div>
    </div>

    <!-- Holdings Table grouped by category -->
    <div class="panel anim" style="padding:1.25rem;margin-bottom:1.25rem;animation-delay:.15s">
      <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:1rem">
        <div style="padding:.4rem;background:#dbeafe;border-radius:.5rem;color:#2563eb;display:flex"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg></div>
        <h3 style="font-size:.95rem;font-weight:700;color:#0f172a">股票持倉明細</h3>
        <span style="margin-left:auto;font-size:.72rem;color:#94a3b8">點擊任一行查看個股詳情</span>
      </div>

      <div v-for="cat in categories" :key="cat.name" style="margin-bottom:.5rem">
        <div class="cat-hdr" @click="cat.open=!cat.open">
          <svg width="14" height="14" fill="none" stroke="#64748b" stroke-width="2" viewBox="0 0 24 24" :style="cat.open?'transform:rotate(90deg);transition:transform .15s':'transition:transform .15s'"><polyline points="9 18 15 12 9 6"/></svg>
          <h4>{{cat.name}}</h4>
          <span style="font-size:.72rem;color:#94a3b8">{{cat.items.length}} 檔 · 市值 {{fmtMoney(cat.totalMV)}}</span>
          <span style="margin-left:auto;font-size:.75rem;font-weight:600" :class="cat.totalPnl>=0?'text-up':'text-down'">{{cat.totalPnl>=0?'+':''}}{{fmtMoney(cat.totalPnl)}}</span>
        </div>
        <div v-show="cat.open" style="overflow-x:auto">
          <table class="ot">
            <thead><tr>
              <th>代號</th><th style="text-align:right">股數</th><th style="text-align:right">成本</th>
              <th style="text-align:right">現價</th><th style="text-align:right">市值</th><th style="text-align:right">損益</th>
              <th style="text-align:right">損益%</th><th style="text-align:right">配置%</th>
            </tr></thead>
            <tbody>
              <tr v-for="p in cat.items" :key="p.symbol" class="row-click" @click="goDetail(p.symbol)">
                <td style="font-weight:700">{{p.symbol}}</td>
                <td class="num">{{p.shares.toFixed(0)}}</td>
                <td class="num">${{p.cost_basis.toFixed(2)}}</td>
                <td class="num">{{p.current_price?'$'+p.current_price.toFixed(2):'N/A'}}</td>
                <td class="num">{{fmtMoney(p.market_value)}}</td>
                <td class="num" :class="p.pnl>=0?'text-up':'text-down'">{{p.pnl>=0?'+':''}}{{fmtMoney(p.pnl)}}</td>
                <td class="num" :class="p.pnl_pct>=0?'text-up':'text-down'">{{p.pnl_pct>=0?'+':''}}{{p.pnl_pct.toFixed(2)}}%</td>
                <td class="num">{{p.alloc_pct.toFixed(1)}}%</td>
              </tr>
            </tbody>
            <tfoot style="font-weight:700;background:#f8fafc">
              <tr>
                <td colspan="1">小計</td>
                <td class="num">{{cat.items.reduce((a,p)=>a+p.shares,0).toFixed(0)}}</td>
                <td></td><td></td>
                <td class="num">{{fmtMoney(cat.totalMV)}}</td>
                <td class="num" :class="cat.totalPnl>=0?'text-up':'text-down'">{{cat.totalPnl>=0?'+':''}}{{fmtMoney(cat.totalPnl)}}</td>
                <td class="num" :class="cat.totalPnl>=0?'text-up':'text-down'">{{cat.totalCost>0?((cat.totalPnl/cat.totalCost)*100).toFixed(2)+'%':'—'}}</td>
                <td class="num">{{cat.items.reduce((a,p)=>a+p.alloc_pct,0).toFixed(1)}}%</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>

    <!-- Options Table -->
    <div v-if="data.options.length" class="panel anim" style="padding:1.25rem;margin-bottom:1.25rem;animation-delay:.2s">
      <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:1rem">
        <div style="padding:.4rem;background:#e0e7ff;border-radius:.5rem;color:#4f46e5;display:flex"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/></svg></div>
        <h3 style="font-size:.95rem;font-weight:700;color:#0f172a">選擇權持倉</h3>
        <span style="margin-left:auto;font-size:.72rem;color:#94a3b8">總市值 {{fmtMoney(data.allocation.options_value)}}</span>
      </div>
      <div style="overflow-x:auto">
        <table class="ot">
          <thead><tr>
            <th>代號</th><th>Option Type</th><th>Strike Price</th><th>Expiration Date</th><th style="text-align:right">股數</th><th style="text-align:right">成本</th>
            <th style="text-align:right">現價</th><th style="text-align:right">市值</th><th style="text-align:right">損益</th>
            <th style="text-align:right">損益%</th><th style="text-align:right">配置%</th>
          </tr></thead>
          <tbody><tr v-for="o in data.options" :key="o.underlying+o.strike+o.expiry">
            <td style="font-weight:700">{{o.underlying}}</td>
            <td>{{o.type}}</td>
            <td class="num">${{o.strike.toFixed(2)}}</td>
            <td>{{o.expiry}}</td>
            <td class="num">{{o.shares}}</td>
            <td class="num">${{o.cost_basis.toFixed(2)}}</td>
            <td class="num">{{o.current_price?'$'+o.current_price.toFixed(2):'N/A'}}</td>
            <td class="num">{{fmtMoney(o.market_value||0)}}</td>
            <td class="num" :class="(o.pnl||0)>=0?'text-up':'text-down'">{{(o.pnl||0)>=0?'+':''}}{{fmtMoney(o.pnl||0)}}</td>
            <td class="num" :class="(o.pnl_pct||0)>=0?'text-up':'text-down'">{{(o.pnl_pct||0)>=0?'+':''}}{{(o.pnl_pct||0).toFixed(2)}}%</td>
            <td class="num">{{(((o.market_value||0)/(data.allocation.total_value||1))*100).toFixed(1)}}%</td>
          </tr></tbody>
          <tfoot style="font-weight:700;background:#f8fafc">
            <tr>
              <td colspan="4">合計</td>
              <td class="num">{{data.options.reduce((a,o)=>a+o.shares,0)}}</td>
              <td></td><td></td>
              <td class="num">{{fmtMoney(data.options.reduce((a,o)=>a+(o.market_value||0),0))}}</td>
              <td class="num" :class="data.options.reduce((a,o)=>a+(o.pnl||0),0)>=0?'text-up':'text-down'">{{data.options.reduce((a,o)=>a+(o.pnl||0),0)>=0?'+':''}}{{fmtMoney(data.options.reduce((a,o)=>a+(o.pnl||0),0))}}</td>
              <td class="num" :class="data.options.reduce((a,o)=>a+(o.pnl||0),0)>=0?'text-up':'text-down'">{{(data.options.reduce((a,o)=>a+(o.total_cost||0),0)>0)?((data.options.reduce((a,o)=>a+(o.pnl||0),0)/data.options.reduce((a,o)=>a+(o.total_cost||0),0))*100).toFixed(2)+'%':'0.00%'}}</td>
              <td class="num">{{((data.options.reduce((a,o)=>a+(o.market_value||0),0)/(data.allocation.total_value||1))*100).toFixed(1)}}%</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>


  </main>

  <!-- ==================== SCORES VIEW ==================== -->
  <main v-if="view==='scores'" style="max-width:76rem;margin:0 auto;padding:1.5rem">

    <!-- ── 個股評分一覽 ── -->
    <div class="panel anim" style="padding:1.25rem;margin-bottom:1.25rem">
      <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.85rem">
        <div style="padding:.4rem;background:#ede9fe;border-radius:.5rem;color:#7c3aed;display:flex"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg></div>
        <h3 style="font-size:.95rem;font-weight:700;color:#0f172a">個股評分一覽</h3>
        <span style="margin-left:auto;font-size:.7rem;color:#94a3b8">基本面 / 技術面 / 風險  均為 0–100，分數愈高愈佳</span>
      </div>
      <!-- 組合層級警示（整合自監測系統）-->
      <div v-if="data.alerts&&data.alerts.portfolio&&data.alerts.portfolio.length" style="display:flex;flex-wrap:wrap;align-items:center;gap:.4rem;margin-bottom:.85rem;padding:.55rem .75rem;border-radius:.65rem;background:#fef2f2;border:1px solid #fecaca">
        <span style="font-size:.72rem;font-weight:700;color:#991b1b;margin-right:.2rem;display:flex;align-items:center;gap:.25rem"><svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>組合警示</span>
        <span v-for="a in data.alerts.portfolio" :key="a.rule" style="display:inline-flex;align-items:center;gap:.3rem;padding:.25rem .55rem;border-radius:.45rem;font-size:.72rem;font-weight:600;border:1px solid" :style="'background:'+a.level_color+'18;color:'+a.level_color+';border-color:'+a.level_color+'44'">{{a.msg}}</span>
      </div>
      <div style="overflow-x:auto">
        <table class="ot">
          <thead><tr>
            <th style="text-align:center">代號</th>
            <th style="text-align:center;cursor:pointer" @click="toggleScoreSort('fund')">基本面 <span v-if="sortScoreKey==='fund'">{{sortScoreDesc?'↓':'↑'}}</span></th>
            <th style="text-align:center;cursor:pointer" @click="toggleScoreSort('tech')">技術面 <span v-if="sortScoreKey==='tech'">{{sortScoreDesc?'↓':'↑'}}</span></th>
            <th style="text-align:center;cursor:pointer" @click="toggleScoreSort('risk')">風險 <span v-if="sortScoreKey==='risk'">{{sortScoreDesc?'↓':'↑'}}</span></th>
            <th style="text-align:center">趨勢</th>
            <th style="text-align:center;cursor:pointer" @click="toggleScoreSort('news')">消息面 <span v-if="sortScoreKey==='news'">{{sortScoreDesc?'↓':'↑'}}</span></th>
            <th v-if="data.alerts&&data.alerts.holdings" style="text-align:center;cursor:pointer" @click="toggleScoreSort('alert')">警示 <span v-if="sortScoreKey==='alert'">{{sortScoreDesc?'↓':'↑'}}</span></th>
          </tr></thead>
          <tbody>
            <template v-for="s in sortedScoreStocks" :key="s.symbol">
              <tr>
                <td style="font-weight:700;text-align:center;cursor:pointer;color:#2563eb" @click="goDetail(s.symbol)">{{s.symbol}}</td>
                <!-- 基本面 -->
                <td style="text-align:center">
                  <span v-if="s.fundamental.fund_score!=null">
                    <span :style="'font-weight:700;font-size:.82rem;color:'+(s.fundamental.fund_score>=80?'#16a34a':s.fundamental.fund_score>=60?'#2563eb':s.fundamental.fund_score>=40?'#d97706':'#dc2626')">{{s.fundamental.fund_score}}</span>
                    <div style="width:3.5rem;height:.3rem;background:#e2e8f0;border-radius:.2rem;margin:.2rem auto 0">
                      <div :style="'height:100%;border-radius:.2rem;background:'+(s.fundamental.fund_score>=80?'#16a34a':s.fundamental.fund_score>=60?'#2563eb':s.fundamental.fund_score>=40?'#d97706':'#dc2626')+';width:'+Math.min(s.fundamental.fund_score,100)+'%'"></div>
                    </div>
                  </span>
                  <span v-else style="color:#94a3b8;font-size:.78rem">—</span>
                </td>
                <!-- 技術面 -->
                <td style="text-align:center">
                  <span v-if="s.technical.tech_score!=null">
                    <span :style="'font-weight:700;font-size:.82rem;color:'+(s.technical.tech_score>=80?'#16a34a':s.technical.tech_score>=60?'#2563eb':s.technical.tech_score>=40?'#d97706':'#dc2626')">{{s.technical.tech_score}}</span>
                    <div style="width:3.5rem;height:.3rem;background:#e2e8f0;border-radius:.2rem;margin:.2rem auto 0">
                      <div :style="'height:100%;border-radius:.2rem;background:'+(s.technical.tech_score>=80?'#16a34a':s.technical.tech_score>=60?'#2563eb':s.technical.tech_score>=40?'#d97706':'#dc2626')+';width:'+Math.min(s.technical.tech_score,100)+'%'"></div>
                    </div>
                  </span>
                  <span v-else style="color:#94a3b8;font-size:.78rem">—</span>
                </td>
                <!-- 風險 -->
                <td style="text-align:center">
                  <span v-if="s.technical.risk_score!=null">
                    <span :style="'font-weight:700;font-size:.82rem;color:'+(s.technical.risk_score>=80?'#16a34a':s.technical.risk_score>=60?'#2563eb':s.technical.risk_score>=40?'#d97706':'#dc2626')">{{s.technical.risk_score}}</span>
                    <div style="width:3.5rem;height:.3rem;background:#e2e8f0;border-radius:.2rem;margin:.2rem auto 0">
                      <div :style="'height:100%;border-radius:.2rem;background:'+(s.technical.risk_score>=80?'#16a34a':s.technical.risk_score>=60?'#2563eb':s.technical.risk_score>=40?'#d97706':'#dc2626')+';width:'+Math.min(s.technical.risk_score,100)+'%'"></div>
                    </div>
                  </span>
                  <span v-else style="color:#94a3b8;font-size:.78rem">—</span>
                </td>
                <!-- 趨勢 -->
                <td style="text-align:center">
                  <span style="font-size:.68rem;padding:.15rem .45rem;border-radius:.3rem;font-weight:600"
                    :style="s.technical.trend_status==='UPTREND'||s.technical.trend_status==='OVERSOLD_UPTREND'?'background:#dcfce7;color:#16a34a':s.technical.trend_status==='DOWNTREND'||s.technical.trend_status==='BREAKDOWN'?'background:#fee2e2;color:#dc2626':'background:#f1f5f9;color:#475569'">
                    {{trendLabel(s.technical.trend_status)}}
                  </span>
                </td>
                <!-- 消息面 -->
                <td style="text-align:center">
                  <span style="font-size:.7rem;padding:.15rem .5rem;border-radius:.3rem;font-weight:600"
                        :style="newsSentStyle(s)">
                    {{newsSentLabel(s)}}
                  </span>
                </td>
                <!-- 警示 -->
                <td v-if="data.alerts&&data.alerts.holdings" style="white-space:nowrap">
                  <template v-if="data.alerts.holdings[s.symbol]&&data.alerts.holdings[s.symbol].top_level<4">
                    <span style="font-size:.68rem;font-weight:700;padding:.12rem .4rem;border-radius:.35rem;display:inline-flex;align-items:center;gap:.2rem" :style="'background:'+data.alerts.holdings[s.symbol].top_level_color+'20;color:'+data.alerts.holdings[s.symbol].top_level_color">{{data.alerts.holdings[s.symbol].alerts[0].level_label}}</span>
                    <div style="font-size:.68rem;color:#64748b;margin-top:.15rem;white-space:nowrap">{{data.alerts.holdings[s.symbol].alerts[0].msg}}</div>
                  </template>
                  <span v-else style="font-size:.68rem;font-weight:700;padding:.12rem .4rem;border-radius:.35rem;display:inline-flex;align-items:center;background:#05966920;color:#059669">✅ 持有</span>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ── 評分規則說明 ── -->
    <div class="panel anim" style="padding:1.25rem;margin-bottom:1.25rem">
      <button @click="crOpen=!crOpen" style="width:100%;display:flex;align-items:center;justify-content:space-between;background:none;border:none;cursor:pointer;padding:0">
        <div style="display:flex;align-items:center;gap:.5rem">
          <div style="padding:.4rem;background:#f0fdf4;border-radius:.5rem;color:#16a34a;display:flex"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg></div>
          <h3 style="font-size:.95rem;font-weight:700;color:#0f172a">評分規則說明</h3>
          <span style="font-size:.68rem;color:#94a3b8;background:#f1f5f9;padding:.15rem .5rem;border-radius:1rem;border:1px solid #e2e8f0">分色：<span style="color:#16a34a">●</span> 80+ &nbsp;<span style="color:#2563eb">●</span> 60–79 &nbsp;<span style="color:#d97706">●</span> 40–59 &nbsp;<span style="color:#dc2626">●</span> &lt;40</span>
        </div>
        <svg width="18" height="18" fill="none" stroke="#94a3b8" stroke-width="2" viewBox="0 0 24 24" :style="crOpen?'transform:rotate(180deg);transition:transform .2s':'transition:transform .2s'"><polyline points="6 9 12 15 18 9"/></svg>
      </button>
      <div v-show="crOpen" style="margin-top:1rem;border-top:1px solid #e2e8f0;padding-top:1rem">
        <div style="display:grid;grid-template-columns:1fr;gap:1rem">

          <!-- 基本面 -->
          <div style="background:#fff;border-radius:.85rem;padding:1.15rem 1.25rem;border:1px solid #e2e8f0;border-left:3px solid #2563eb">
            <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.85rem">
              <span style="display:inline-flex;align-items:center;justify-content:center;width:1.5rem;height:1.5rem;border-radius:.4rem;background:#dbeafe;color:#2563eb;font-size:.7rem;font-weight:800">F</span>
              <span style="font-size:.88rem;font-weight:700;color:#0f172a">基本面評分</span>
              <span style="font-size:.68rem;color:#64748b;background:#f1f5f9;padding:.1rem .45rem;border-radius:.3rem">fund_score · 滿分 100</span>
            </div>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(14rem,1fr));gap:.75rem">
              <div v-for="(card,ci) in (data.scoring_config&&data.scoring_config.fundamental||[])" :key="ci" style="border:1px solid #e2e8f0;border-radius:.65rem;overflow:hidden">
                <div style="background:#dbeafe;padding:.35rem .6rem;font-size:.74rem;font-weight:700;color:#1e40af;display:flex;justify-content:space-between"><span>{{card.title}}</span><span>{{card.max}}</span></div>
                <table style="width:100%;font-size:.72rem;border-collapse:collapse">
                  <tr v-for="(row,ri) in card.rows" :key="ri" :style="ri%2===1?'background:#f8fafc':''">
                    <td style="padding:.3rem .6rem;color:#334155">{{row.cond}}</td>
                    <td style="padding:.3rem .6rem;text-align:right;font-weight:700" :style="row.val>0?'color:#16a34a':row.val<0?'color:#dc2626':'color:#475569'">{{row.val>0?'+':''}}{{row.val}}</td>
                  </tr>
                </table>
              </div>
            </div>
            <div style="margin-top:.75rem;padding:.45rem .65rem;background:#eff6ff;border-radius:.5rem;font-size:.7rem;color:#1e40af;display:flex;align-items:center;gap:.35rem">
              <svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
              完全按客觀財報數據計分，各項加總最高 100 分。ETF 因無財報欄位，預設給予 60 分保底。
            </div>
          </div>

          <!-- 技術面 -->
          <div style="background:#fff;border-radius:.85rem;padding:1.15rem 1.25rem;border:1px solid #e2e8f0;border-left:3px solid #7c3aed">
            <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.85rem">
              <span style="display:inline-flex;align-items:center;justify-content:center;width:1.5rem;height:1.5rem;border-radius:.4rem;background:#f3e8ff;color:#7c3aed;font-size:.7rem;font-weight:800">T</span>
              <span style="font-size:.88rem;font-weight:700;color:#0f172a">技術面評分</span>
              <span style="font-size:.68rem;color:#64748b;background:#f1f5f9;padding:.1rem .45rem;border-radius:.3rem">tech_score · 滿分 100</span>
            </div>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(14rem,1fr));gap:.75rem">
              <div v-for="(card,ci) in (data.scoring_config&&data.scoring_config.technical||[])" :key="ci" style="border:1px solid #e2e8f0;border-radius:.65rem;overflow:hidden">
                <div style="background:#f3e8ff;padding:.35rem .6rem;font-size:.74rem;font-weight:700;color:#6b21a8;display:flex;justify-content:space-between"><span>{{card.title}}</span><span>{{card.max}}</span></div>
                <table style="width:100%;font-size:.72rem;border-collapse:collapse">
                  <tr v-for="(row,ri) in card.rows" :key="ri" :style="ri%2===1?'background:#f8fafc':''">
                    <td style="padding:.3rem .6rem;color:#334155">{{row.cond}}</td>
                    <td style="padding:.3rem .6rem;text-align:right;font-weight:700" :style="row.val>0?'color:#16a34a':row.val<0?'color:#dc2626':'color:#475569'">{{row.val>0?'+':''}}{{row.val}}</td>
                  </tr>
                </table>
              </div>
            </div>
          </div>

          <!-- 風險 -->
          <div style="background:#fff;border-radius:.85rem;padding:1.15rem 1.25rem;border:1px solid #e2e8f0;border-left:3px solid #d97706">
            <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.85rem">
              <span style="display:inline-flex;align-items:center;justify-content:center;width:1.5rem;height:1.5rem;border-radius:.4rem;background:#fef3c7;color:#d97706;font-size:.7rem;font-weight:800">R</span>
              <span style="font-size:.88rem;font-weight:700;color:#0f172a">風險評分</span>
              <span style="font-size:.68rem;color:#64748b;background:#f1f5f9;padding:.1rem .45rem;border-radius:.3rem">risk_score · 滿分 100 · 分數愈高風險愈低</span>
            </div>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(14rem,1fr));gap:.75rem">
              <div v-for="(card,ci) in (data.scoring_config&&data.scoring_config.risk||[])" :key="ci" style="border:1px solid #e2e8f0;border-radius:.65rem;overflow:hidden">
                <div style="background:#fef3c7;padding:.35rem .6rem;font-size:.74rem;font-weight:700;color:#92400e;display:flex;justify-content:space-between"><span>{{card.title}}</span><span>{{card.max}}</span></div>
                <table style="width:100%;font-size:.72rem;border-collapse:collapse">
                  <tr v-for="(row,ri) in card.rows" :key="ri" :style="ri%2===1?'background:#f8fafc':''">
                    <td style="padding:.3rem .6rem;color:#334155">{{row.cond}}</td>
                    <td style="padding:.3rem .6rem;text-align:right;font-weight:700" :style="row.val>0?'color:#16a34a':row.val<0?'color:#dc2626':'color:#475569'">{{row.val>0?'+':''}}{{row.val}}</td>
                  </tr>
                </table>
              </div>
            </div>
            <div style="margin-top:.75rem;padding:.45rem .65rem;background:#fffbeb;border-radius:.5rem;font-size:.7rem;color:#92400e;display:flex;align-items:center;gap:.35rem">
              <svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
              歷史資料不足時給中庸分 50。以近一年日報酬率計算（yfinance 1y）
            </div>
          </div>

        </div>
      </div>
    </div>

  </main>

  <!-- ==================== CANDIDATES VIEW ==================== -->
  <main v-if="view==='candidates'" style="max-width:76rem;margin:0 auto;padding:1.5rem">
    <div v-if="!candidateStocks.length" class="panel" style="padding:1.25rem;color:#64748b;font-size:.9rem">
      候選清單沒有可顯示的標的。請確認 `config/candidates.txt` 內代號是否已在本次資料中載入。
    </div>
    <div v-else class="panel anim" style="padding:1.25rem">
      <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.85rem">
        <div style="padding:.4rem;background:#ede9fe;border-radius:.5rem;color:#7c3aed;display:flex"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg></div>
        <h3 style="font-size:.95rem;font-weight:700;color:#0f172a">個股評分一覽</h3>
        <span style="margin-left:auto;font-size:.7rem;color:#94a3b8">基本面 / 技術面 / 風險  均為 0–100，分數愈高愈佳</span>
      </div>
      <div style="overflow-x:auto">
        <table class="ot">
          <thead><tr>
            <th>代號</th>
            <th style="text-align:center;cursor:pointer" @click="toggleScoreSort('fund')">基本面 <span v-if="sortScoreKey==='fund'">{{sortScoreDesc?'↓':'↑'}}</span></th>
            <th style="text-align:center;cursor:pointer" @click="toggleScoreSort('tech')">技術面 <span v-if="sortScoreKey==='tech'">{{sortScoreDesc?'↓':'↑'}}</span></th>
            <th style="text-align:center;cursor:pointer" @click="toggleScoreSort('risk')">風險 <span v-if="sortScoreKey==='risk'">{{sortScoreDesc?'↓':'↑'}}</span></th>
            <th style="text-align:center">趨勢</th>
            <th style="text-align:center">消息面</th>
            <th v-if="data.alerts&&data.alerts.candidates" style="text-align:left;cursor:pointer" @click="toggleScoreSort('csignal')">警示/信號 <span v-if="sortScoreKey==='csignal'">{{sortScoreDesc?'↓':'↑'}}</span></th>
          </tr></thead>
          <tbody>
            <template v-for="s in sortedScoreCandidates" :key="s.symbol">
              <tr>
                <td style="font-weight:700;cursor:pointer;color:#2563eb" @click="goDetail(s.symbol)">{{s.symbol}}</td>
                <!-- 基本面 -->
                <td style="text-align:center">
                  <span v-if="s.fundamental&&s.fundamental.fund_score!=null">
                    <span :style="'font-weight:700;font-size:.82rem;color:'+(s.fundamental.fund_score>=80?'#16a34a':s.fundamental.fund_score>=60?'#2563eb':s.fundamental.fund_score>=40?'#d97706':'#dc2626')">{{s.fundamental.fund_score}}</span>
                    <div style="width:3.5rem;height:.3rem;background:#e2e8f0;border-radius:.2rem;margin:.2rem auto 0">
                      <div :style="'height:100%;border-radius:.2rem;background:'+(s.fundamental.fund_score>=80?'#16a34a':s.fundamental.fund_score>=60?'#2563eb':s.fundamental.fund_score>=40?'#d97706':'#dc2626')+';width:'+Math.min(s.fundamental.fund_score,100)+'%'"></div>
                    </div>
                  </span>
                  <span v-else style="color:#94a3b8;font-size:.78rem">—</span>
                </td>
                <!-- 技術面 -->
                <td style="text-align:center">
                  <span v-if="s.technical&&s.technical.tech_score!=null">
                    <span :style="'font-weight:700;font-size:.82rem;color:'+(s.technical.tech_score>=80?'#16a34a':s.technical.tech_score>=60?'#2563eb':s.technical.tech_score>=40?'#d97706':'#dc2626')">{{s.technical.tech_score}}</span>
                    <div style="width:3.5rem;height:.3rem;background:#e2e8f0;border-radius:.2rem;margin:.2rem auto 0">
                      <div :style="'height:100%;border-radius:.2rem;background:'+(s.technical.tech_score>=80?'#16a34a':s.technical.tech_score>=60?'#2563eb':s.technical.tech_score>=40?'#d97706':'#dc2626')+';width:'+Math.min(s.technical.tech_score,100)+'%'"></div>
                    </div>
                  </span>
                  <span v-else style="color:#94a3b8;font-size:.78rem">—</span>
                </td>
                <!-- 風險 -->
                <td style="text-align:center">
                  <span v-if="s.technical&&s.technical.risk_score!=null">
                    <span :style="'font-weight:700;font-size:.82rem;color:'+(s.technical.risk_score>=80?'#16a34a':s.technical.risk_score>=60?'#2563eb':s.technical.risk_score>=40?'#d97706':'#dc2626')">{{s.technical.risk_score}}</span>
                    <div style="width:3.5rem;height:.3rem;background:#e2e8f0;border-radius:.2rem;margin:.2rem auto 0">
                      <div :style="'height:100%;border-radius:.2rem;background:'+(s.technical.risk_score>=80?'#16a34a':s.technical.risk_score>=60?'#2563eb':s.technical.risk_score>=40?'#d97706':'#dc2626')+';width:'+Math.min(s.technical.risk_score,100)+'%'"></div>
                    </div>
                  </span>
                  <span v-else style="color:#94a3b8;font-size:.78rem">—</span>
                </td>
                <!-- 趨勢 -->
                <td style="text-align:center">
                  <span v-if="s.technical&&s.technical.trend_status"
                    style="font-size:.68rem;padding:.15rem .45rem;border-radius:.3rem;font-weight:600"
                    :style="s.technical.trend_status==='UPTREND'||s.technical.trend_status==='OVERSOLD_UPTREND'?'background:#dcfce7;color:#16a34a':s.technical.trend_status==='DOWNTREND'||s.technical.trend_status==='BREAKDOWN'?'background:#fee2e2;color:#dc2626':'background:#f1f5f9;color:#475569'">
                    {{trendLabel(s.technical.trend_status)}}
                  </span>
                  <span v-else style="color:#94a3b8;font-size:.78rem">—</span>
                </td>
                <!-- 消息面 -->
                <td style="text-align:center">
                  <span style="font-size:.7rem;padding:.15rem .5rem;border-radius:.3rem;font-weight:600"
                        :style="newsSentStyle(s)">{{newsSentLabel(s)}}</span>
                </td>
                <!-- 警示/信號 -->
                <td v-if="data.alerts&&data.alerts.candidates" style="white-space:nowrap">
                  <template v-if="getCandAlert(s.symbol)">
                    <span style="font-size:.7rem;font-weight:700;padding:.12rem .4rem;border-radius:.35rem;display:inline-flex;align-items:center;gap:.2rem" :style="'background:'+getCandAlert(s.symbol).signal_color+'20;color:'+getCandAlert(s.symbol).signal_color">{{getCandAlert(s.symbol).signal}}</span>
                    <div style="font-size:.68rem;color:#64748b;margin-top:.15rem;max-width:14rem;white-space:normal;line-height:1.4">{{(getCandAlert(s.symbol).reasons||[]).slice(0,2).join(' / ')}}</div>
                  </template>
                  <span v-else style="color:#94a3b8;font-size:.78rem">—</span>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>
  </main>

  <!-- ==================== DETAIL / COMPETITORS VIEW ==================== -->
  <main v-if="view==='detail'||view==='competitors'" style="max-width:76rem;margin:0 auto;padding:1.5rem">

    <!-- Stock Selector -->
    <div style="position:relative;max-width:24rem;margin-bottom:1.25rem">
      <button @click="ddOpen=!ddOpen" style="width:100%;display:flex;align-items:center;justify-content:space-between;padding:.65rem 1rem;background:#fff;border:1px solid #cbd5e1;border-radius:.75rem;box-shadow:0 1px 2px rgba(0,0,0,.04);cursor:pointer;font-size:.9rem;transition:border-color .15s" :style="ddOpen?'border-color:#3b82f6;box-shadow:0 0 0 3px rgba(59,130,246,.15)':''">
        <div style="display:flex;align-items:center;gap:.5rem">
          <span style="font-weight:700;color:#0f172a">{{cur.symbol}}</span>
          <span style="color:#64748b">{{cur.company}}</span>
          <span style="font-size:.68rem;font-weight:700;padding:.1rem .4rem;border-radius:.45rem" :style="newsSentStyle(cur)">{{newsSentLabel(cur)}}</span>
        </div>
        <svg width="18" height="18" fill="none" stroke="#94a3b8" stroke-width="2" viewBox="0 0 24 24" :style="ddOpen?'transform:rotate(180deg);transition:transform .2s':'transition:transform .2s'"><polyline points="6 9 12 15 18 9"/></svg>
      </button>

      <div v-if="ddOpen" style="position:absolute;top:calc(100% + .5rem);left:0;right:0;background:#fff;border:1px solid #e2e8f0;border-radius:.85rem;box-shadow:0 10px 25px -5px rgba(0,0,0,.12);z-index:50;overflow:hidden;display:flex;flex-direction:column;max-height:22rem;animation:fadeUp .2s ease-out">
        <div style="padding:.65rem;border-bottom:1px solid #f1f5f9">
          <div style="position:relative">
            <svg width="16" height="16" fill="none" stroke="#94a3b8" stroke-width="2" viewBox="0 0 24 24" style="position:absolute;left:.65rem;top:50%;transform:translateY(-50%)"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input v-model="sq" type="text" placeholder="搜尋代號或名稱..." style="width:100%;padding:.5rem .75rem .5rem 2.2rem;background:#f8fafc;border:1px solid #e2e8f0;border-radius:.5rem;font-size:.85rem;outline:none">
          </div>
        </div>
        <div style="overflow-y:auto;padding:.25rem;flex:1">
          <button v-for="(s,i) in filtered" :key="s.symbol" @click="pick(s)" style="width:100%;display:flex;align-items:center;justify-content:space-between;gap:.5rem;padding:.55rem .75rem;border-radius:.5rem;border:none;cursor:pointer;font-size:.85rem;text-align:left;transition:background .1s" :style="idx===oidx(s)?'background:#eff6ff;color:#1d4ed8':'background:transparent;color:#334155'">
            <div style="display:flex;align-items:center;gap:.5rem;min-width:0;flex:1">
              <span style="font-weight:700">{{s.symbol}}</span>
              <span style="font-size:.8rem;opacity:.7;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{s.company}}</span>
              <span style="font-size:.66rem;font-weight:700;padding:.08rem .38rem;border-radius:.42rem;white-space:nowrap;flex:0 0 auto" :style="newsSentStyle(s)">{{newsSentLabel(s)}}</span>
            </div>
            <div style="display:flex;align-items:center;gap:.5rem;flex:0 0 auto;white-space:nowrap;padding-left:.35rem">
              <span :class="s.pnl_pct>=0?'text-up':'text-down'" style="font-size:.78rem;font-weight:600">{{s.pnl_pct>=0?'+':''}}{{s.pnl_pct.toFixed(1)}}%</span>
              <span style="font-weight:600">{{s.price?'$'+s.price.toFixed(2):'N/A'}}</span>
            </div>
          </button>
          <div v-if="!filtered.length" style="padding:1rem;text-align:center;color:#94a3b8;font-size:.85rem">找不到相符的標的</div>
        </div>
      </div>
    </div>

    <div v-if="ddOpen" @click="ddOpen=false" style="position:fixed;inset:0;z-index:40"></div>

    <div v-if="view==='candidates'&&!candidateStocks.length" class="panel" style="padding:1.25rem;color:#64748b;font-size:.9rem">
      候選清單沒有可顯示的標的。請確認 `config/candidates.txt` 內代號是否已在本次資料中載入。
    </div>

    <div v-else :style="anim?'opacity:0;transition:opacity .15s':'opacity:1;transition:opacity .15s'">

      <!-- Hero Card -->
      <div class="panel anim" style="padding:1.5rem 2rem;margin-bottom:1.25rem;position:relative;overflow:hidden">
        <div :style="'position:absolute;top:0;right:0;width:16rem;height:16rem;border-radius:50%;filter:blur(80px);opacity:.15;pointer-events:none;background:'+(cur.pnl_pct>=0?'#34d399':'#f87171')"></div>
        <div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-start;gap:1.5rem;position:relative;z-index:1">
          <div style="flex:1;min-width:280px">
            <div style="display:flex;align-items:center;gap:.65rem;margin-bottom:.5rem;flex-wrap:wrap">
              <h2 style="font-size:1.75rem;font-weight:800;color:#0f172a">{{cur.company}}</h2>
              <span style="padding:.2rem .6rem;border-radius:.35rem;background:#f1f5f9;border:1px solid #e2e8f0;font-size:.8rem;font-weight:500;color:#475569">{{cur.symbol}}</span>
              <span v-if="cur.category" style="padding:.2rem .6rem;border-radius:.35rem;background:#eff6ff;border:1px solid #bfdbfe;font-size:.75rem;font-weight:500;color:#1d4ed8">{{cur.category}}</span>
              <span v-if="ri" class="badge" :style="'background:'+ri.bg+';color:'+ri.color">{{ri.label}}</span>
            </div>
            <div style="display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;margin-bottom:.75rem">
              <span v-if="cur.fundamental&&cur.fundamental.sector" style="font-size:.78rem;color:#94a3b8">{{cur.fundamental.sector}} / {{cur.fundamental.industry}}</span>
              <span v-if="earningsInfo" :style="'display:inline-flex;align-items:center;gap:.3rem;font-size:.72rem;font-weight:500;padding:.2rem .55rem;border-radius:.35rem;border:1px solid '+earningsInfo.border+';background:'+earningsInfo.bg+';color:'+earningsInfo.color"><svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg> 財報 {{earningsInfo.label}}</span>
            </div>
            <div v-if="cur.price" style="display:flex;align-items:baseline;gap:.75rem;flex-wrap:wrap">
              <span style="font-size:2.75rem;font-weight:900;color:#0f172a;letter-spacing:-.02em">${{cur.price.toFixed(2)}}</span>
              <div :class="cur.pnl_pct>=0?'text-up bg-up':'text-down bg-down'" style="display:flex;align-items:center;gap:.3rem;font-size:1rem;font-weight:700;padding:.25rem .65rem;border-radius:.5rem">
                <svg v-if="cur.pnl_pct>=0" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>
                <svg v-else width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="22 17 13.5 8.5 8.5 13.5 2 7"/><polyline points="16 17 22 17 22 11"/></svg>
                <span>{{cur.pnl_pct>=0?'+':''}}{{cur.pnl_pct.toFixed(2)}}%</span>
                <span style="font-size:.82rem;font-weight:500">({{cur.pnl>=0?'+':''}}{{fmtMoney(cur.pnl)}})</span>
              </div>
            </div>
            <div v-if="cur.price" style="font-size:.78rem;color:#94a3b8;margin-top:.35rem">
              成本 ${{cur.cost_basis.toFixed(2)}} x {{cur.shares.toFixed(0)}} 股 = {{fmtMoney(cur.cost_basis*cur.shares)}}
            </div>
            <div v-if="cur.error" style="margin-top:.75rem;padding:.75rem;background:#fef2f2;color:#991b1b;border-radius:.5rem;font-size:.85rem">{{cur.error}}</div>
          </div>

          <div style="display:flex;align-items:center;gap:1.25rem;background:#f8fafc;padding:1rem 1.25rem;border-radius:1rem;border:1px solid #e2e8f0">
            <div v-if="cur.technical&&cur.technical.high_52w" style="min-width:7.5rem">
              <p style="font-size:.7rem;color:#94a3b8;font-weight:500;margin-bottom:.5rem">52 週相對位置</p>
              <div class="pt" style="margin-bottom:.35rem"><div class="pf" style="background:linear-gradient(90deg,#3b82f6,#6366f1)" :style="'width:'+pp+'%'"></div></div>
              <div style="display:flex;justify-content:space-between;font-size:.65rem;color:#94a3b8"><span>${{cur.technical.low_52w}}</span><span>${{cur.technical.high_52w}}</span></div>
            </div>
            <div v-if="cur.technical&&cur.technical.high_52w&&hasScores" style="width:1px;height:3.5rem;background:#e2e8f0"></div>
            <div v-if="hasScores" style="display:flex;gap:1rem">
              <div v-for="sc in scoreItems" :key="sc.label" style="text-align:center">
                <div style="font-size:1.2rem;font-weight:700" :style="'color:'+sc.color">{{sc.value}}</div>
                <div style="font-size:.65rem;color:#94a3b8">{{sc.label}}</div>
              </div>
            </div>
            <div v-if="(!cur.technical||!cur.technical.high_52w)&&!hasScores" style="font-size:.8rem;color:#94a3b8">數據載入中...</div>
          </div>
        </div>
      </div>

      <!-- Company Overview -->
      <div v-if="cur.fundamental && cur.fundamental.longBusinessSummary" class="panel anim" style="padding:1.25rem;margin-bottom:1.25rem;animation-delay:.05s">
        <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.75rem">
          <div style="padding:.45rem;background:#fef3c7;border-radius:.5rem;color:#b45309;display:flex"><svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg></div>
          <h3 style="font-size:1.05rem;font-weight:700;color:#0f172a">公司概況</h3>
        </div>
        <div style="font-size:.9rem;line-height:1.6;color:#475569;background:#f8fafc;padding:1rem;border-radius:.75rem;border:1px solid #e2e8f0;">
          {{ cur.fundamental.longBusinessSummary }}
        </div>
      </div>

      <!-- Bento Grid -->
      <!-- 技術面 + 基本面 -->
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:1.25rem;margin-bottom:1.25rem">

        <!-- 技術面 -->
        <div class="panel anim" style="padding:1.25rem;display:flex;flex-direction:column;animation-delay:.08s">
          <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:1rem">
            <div style="padding:.45rem;background:#f3e8ff;border-radius:.5rem;color:#7c3aed;display:flex"><svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg></div>
            <h3 style="font-size:1.05rem;font-weight:700;color:#0f172a">技術面</h3>
          </div>
          <div v-if="cur.technical&&Object.keys(cur.technical).length" style="display:flex;flex-direction:column;gap:.65rem">
            <div class="sg">
              <div class="sb"><div class="sl">50 日均線</div><div class="sv" :class="cur.price>cur.technical.ma50?'text-up':'text-down'">{{cur.technical.ma50?'$'+cur.technical.ma50.toFixed(2):'N/A'}}</div></div>
              <div class="sb"><div class="sl">200 日均線</div><div class="sv" :class="cur.price>cur.technical.ma200?'text-up':'text-down'">{{cur.technical.ma200?'$'+cur.technical.ma200.toFixed(2):'N/A'}}</div></div>
            </div>
            <div class="sg">
              <div class="sb"><div class="sl">52 週高點</div><div class="sv">{{cur.technical.high_52w?'$'+cur.technical.high_52w.toFixed(2):'N/A'}}</div></div>
              <div class="sb"><div class="sl">52 週低點</div><div class="sv">{{cur.technical.low_52w?'$'+cur.technical.low_52w.toFixed(2):'N/A'}}</div></div>
            </div>
            <div class="sg">
              <div class="sb"><div class="sl">近 3 月漲跌</div><div class="sv" :class="(cur.technical.change_3mo_pct||0)>=0?'text-up':'text-down'">{{cur.technical.change_3mo_pct!=null?(cur.technical.change_3mo_pct>=0?'+':'')+cur.technical.change_3mo_pct.toFixed(1)+'%':'N/A'}}</div></div>
              <div class="sb"><div class="sl">成交量 (20日均)</div><div class="sv">{{cur.technical.avg_vol_20d?fmtNum(cur.technical.avg_vol_20d):'N/A'}}</div></div>
            </div>
            <div v-if="cur.technical.current_vol&&cur.technical.avg_vol_20d" style="padding:.5rem 0">
              <div style="display:flex;justify-content:space-between;font-size:.7rem;color:#94a3b8;margin-bottom:.3rem">
                <span>今日量 vs 20日均量</span>
                <span style="font-weight:600" :class="vr>1?'text-up':'text-down'">{{(vr*100).toFixed(0)}}%</span>
              </div>
              <div class="pt"><div class="pf" :style="'width:'+Math.min(vr*100,100)+'%;background:'+(vr>1?'#10b981':'#f59e0b')"></div></div>
            </div>
          </div>
          <div v-else style="flex:1;display:flex;align-items:center;justify-content:center;color:#94a3b8;font-size:.85rem">無技術面數據</div>
        </div>

        <!-- 基本面 -->
        <div class="panel anim" style="padding:1.25rem;display:flex;flex-direction:column;animation-delay:.15s">
          <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:1rem">
            <div style="padding:.45rem;background:#fef3c7;border-radius:.5rem;color:#d97706;display:flex"><svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/></svg></div>
            <h3 style="font-size:1.05rem;font-weight:700;color:#0f172a">基本面</h3>
            <div style="margin-left:auto;display:flex;gap:.25rem">
              <button v-for="t in ftabs" :key="t.key" @click="ftab=t.key" style="font-size:.68rem;padding:.2rem .5rem;border-radius:.35rem;border:1px solid #e2e8f0;cursor:pointer;transition:all .1s" :style="ftab===t.key?'background:#0f172a;color:#fff;border-color:#0f172a':'background:#fff;color:#64748b'">{{t.label}}</button>
            </div>
          </div>
          <div v-show="ftab==='valuation'" class="sg" style="gap:.45rem">
            <div class="sb" v-for="item in valItems" :key="item.label"><div class="sl">{{item.label}}</div><div class="sv" :class="item.hl?'text-up':''">{{item.value}}</div></div>
          </div>
          <div v-show="ftab==='profit'" class="sg" style="gap:.45rem">
            <div class="sb" v-for="item in profItems" :key="item.label"><div class="sl">{{item.label}}</div><div class="sv" :class="item.hl?'text-up':''">{{item.value}}</div></div>
          </div>
          <div v-show="ftab==='growth'" class="sg" style="gap:.45rem">
            <div class="sb" v-for="item in growItems" :key="item.label"><div class="sl">{{item.label}}</div><div class="sv" :class="item.hl?'text-up':''">{{item.value}}</div></div>
          </div>
          <div v-show="ftab==='competitors'" style="overflow-x:auto">
            <div v-if="competitorData.length" style="font-size:.72rem;color:#64748b;margin-bottom:.5rem">比較 {{cur.symbol}} 與同領域競品的關鍵指標</div>
            <table v-if="competitorData.length" style="width:100%;border-collapse:collapse;font-size:.75rem">
              <thead>
                <tr style="border-bottom:2px solid #e2e8f0">
                  <th style="padding:.4rem .5rem;text-align:left;font-weight:600;color:#64748b">公司</th>
                  <th style="padding:.4rem .5rem;text-align:right;font-weight:600;color:#64748b">P/E</th>
                  <th style="padding:.4rem .5rem;text-align:right;font-weight:600;color:#64748b">市值</th>
                  <th style="padding:.4rem .5rem;text-align:right;font-weight:600;color:#64748b">營收成長</th>
                  <th style="padding:.4rem .5rem;text-align:right;font-weight:600;color:#64748b">ROE</th>
                  <th style="padding:.4rem .5rem;text-align:right;font-weight:600;color:#64748b">淨利率</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="comp in competitorData" :key="comp.symbol" @click="!comp.isCurrent&&goDetail(comp.symbol)" :style="(comp.isCurrent?'background:#f0f9ff;font-weight:600;':'')+(!comp.isCurrent?'cursor:pointer;':'')" style="border-bottom:1px solid #f1f5f9">
                  <td style="padding:.5rem .5rem">
                    <div style="display:flex;align-items:center;gap:.4rem">
                      <button @click.stop="goDetail(comp.symbol)" :disabled="comp.isCurrent" :style="comp.isCurrent?'color:#0284c7;background:none;border:none;padding:0;font:inherit':'color:#334155;background:none;border:none;padding:0;font:inherit;cursor:pointer;text-decoration:none'" style="line-height:1">{{comp.symbol}}</button>
                      <span v-if="comp.isCurrent" style="font-size:.65rem;background:#0284c7;color:#fff;padding:.1rem .3rem;border-radius:.25rem">當前</span>
                    </div>
                  </td>
                  <td style="padding:.5rem .5rem;text-align:right;color:#334155">{{comp.pe}}</td>
                  <td style="padding:.5rem .5rem;text-align:right;color:#334155">{{comp.marketCap}}</td>
                  <td style="padding:.5rem .5rem;text-align:right" :style="comp.revenueGrowthNum>0?'color:#10b981':'color:#ef4444'">{{comp.revenueGrowth}}</td>
                  <td style="padding:.5rem .5rem;text-align:right" :style="comp.roeNum>0.15?'color:#10b981':'color:#334155'">{{comp.roe}}</td>
                  <td style="padding:.5rem .5rem;text-align:right" :style="comp.profitMarginNum>0.15?'color:#10b981':'color:#334155'">{{comp.profitMargin}}</td>
                </tr>
              </tbody>
            </table>
            <div v-else style="padding:2rem;text-align:center;color:#94a3b8;font-size:.8rem">尚未配置競品資料</div>
          </div>
        </div>
      </div>

      <!-- 消息面 -->
      <div v-if="cur.news_analysis||(cur.news&&cur.news.length)" class="panel anim" style="padding:1.25rem;margin-bottom:1.25rem;animation-delay:.22s">
        <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:1rem">
          <div style="padding:.45rem;background:#dbeafe;border-radius:.5rem;color:#2563eb;display:flex"><svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></div>
          <h3 style="font-size:1.05rem;font-weight:700;color:#0f172a">消息面</h3>
          <span v-if="cur.news_analysis" style="margin-left:auto;font-size:.7rem;color:#94a3b8;background:#f1f5f9;padding:.15rem .5rem;border-radius:1rem;border:1px solid #e2e8f0">{{cur.news_analysis.summary.total}} 則分析</span>
          <span v-else style="margin-left:auto;font-size:.7rem;color:#94a3b8;background:#f1f5f9;padding:.15rem .5rem;border-radius:1rem;border:1px solid #e2e8f0">{{cur.news.length}} 則</span>
        </div>

        <!-- ── 有 analysis：利多/利空分欄 ── -->
        <template v-if="cur.news_analysis">
          <div class="na-summary">
            <span class="na-sent" :class="'na-sent-'+cur.news_analysis.summary.overall_sentiment">
              {{cur.news_analysis.summary.overall_sentiment==='strongly_bullish'?'🔥 強力利多':cur.news_analysis.summary.overall_sentiment==='bullish'?'看多':cur.news_analysis.summary.overall_sentiment==='strongly_bearish'?'🚨 強力利空':cur.news_analysis.summary.overall_sentiment==='bearish'?'看空':cur.news_analysis.summary.overall_sentiment==='mixed'?'多空分歧':'中性'}}
            </span>
            <span class="na-theme">{{cur.news_analysis.summary.key_theme}}</span>
            <span class="na-chip na-chip-bull" v-if="cur.news_analysis.summary.bullish_count">利多 {{cur.news_analysis.summary.bullish_count}}</span>
            <span class="na-chip na-chip-bear" v-if="cur.news_analysis.summary.bearish_count">利空 {{cur.news_analysis.summary.bearish_count}}</span>
            <span class="na-chip na-chip-neut" v-if="cur.news_analysis.summary.neutral_count">中性 {{cur.news_analysis.summary.neutral_count}}</span>
          </div>
          <div class="na-grid">
            <div class="na-col na-col-bull" v-if="cur.news_analysis.bullish.length">
              <div class="na-col-head">利多消息</div>
              <div v-for="(item,i) in cur.news_analysis.bullish" :key="'b'+i" class="na-item" :style="item.link?'cursor:pointer':''" @click="openNews(item.link)">
                <div class="na-item-title">
                  <span class="imp-tag" :class="'imp-'+item.impact+'-bull'">{{item.impact}}</span>
                  <span style="flex:1;font-size:.82rem;color:#334155;line-height:1.45;white-space:pre-wrap">{{item.title}}</span>
                </div>
                <div class="na-reason">{{item.reason}}</div>
                <div class="na-meta"><span>{{item.publisher}}</span><span v-if="item.date">· {{item.date}}</span><span v-if="item.category" style="margin-left:auto;background:#f0fdf4;padding:.05rem .35rem;border-radius:.35rem;color:#166534">{{item.category}}</span></div>
              </div>
            </div>
            <div class="na-col na-col-bear" v-if="cur.news_analysis.bearish.length">
              <div class="na-col-head">利空消息</div>
              <div v-for="(item,i) in cur.news_analysis.bearish" :key="'e'+i" class="na-item" :style="item.link?'cursor:pointer':''" @click="openNews(item.link)">
                <div class="na-item-title">
                  <span class="imp-tag" :class="'imp-'+item.impact+'-bear'">{{item.impact}}</span>
                  <span style="flex:1;font-size:.82rem;color:#334155;line-height:1.45;white-space:pre-wrap">{{item.title}}</span>
                </div>
                <div class="na-reason">{{item.reason}}</div>
                <div class="na-meta"><span>{{item.publisher}}</span><span v-if="item.date">· {{item.date}}</span><span v-if="item.category" style="margin-left:auto;background:#fef2f2;padding:.05rem .35rem;border-radius:.35rem;color:#991b1b">{{item.category}}</span></div>
              </div>
            </div>
          </div>
        </template>

        <!-- ── 無 analysis：原始新聞 fallback ── -->
        <template v-else>
          <div v-if="cur.news&&cur.news.length" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:.5rem">
            <div v-for="(n,i) in cur.news" :key="i" class="nc">
              <div style="display:flex;align-items:flex-start;gap:.5rem">
                <a :href="n.link" target="_blank" rel="noopener" style="flex:1">{{n.title}}</a>
                <span v-if="n.score>=70" class="rel-tag rel-high">高相關</span>
                <span v-else-if="n.score>=40" class="rel-tag rel-mid">中相關</span>
                <span v-else class="rel-tag rel-low">一般</span>
              </div>
              <div class="nm">
                <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                <span>{{n.publisher}}</span><span v-if="n.date">· {{n.date}}</span>
              </div>
            </div>
          </div>
          <div v-else style="padding:1.5rem;text-align:center;color:#94a3b8;font-size:.85rem">暫無最新消息</div>
        </template>
      </div>

      <!-- AI Analysis -->
      <div v-if="cur.analysis_html" class="panel anim" style="padding:1.25rem;margin-bottom:1.25rem;animation-delay:.3s">
        <button @click="ao=!ao" style="width:100%;display:flex;align-items:center;justify-content:space-between;background:none;border:none;cursor:pointer;padding:0">
          <div style="display:flex;align-items:center;gap:.5rem">
            <div style="padding:.45rem;background:#ecfdf5;border-radius:.5rem;color:#059669;display:flex"><svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg></div>
            <h3 style="font-size:1.05rem;font-weight:700;color:#0f172a">Claude AI 分析</h3>
          </div>
          <svg width="20" height="20" fill="none" stroke="#94a3b8" stroke-width="2" viewBox="0 0 24 24" :style="ao?'transform:rotate(180deg);transition:transform .2s':'transition:transform .2s'"><polyline points="6 9 12 15 18 9"/></svg>
        </button>
        <div v-show="ao" style="margin-top:1rem;border-top:1px solid #e2e8f0;padding-top:1rem">
          <div class="ac" v-html="cur.analysis_html"></div>
        </div>
      </div>

    </div>
  </main>

  <footer style="text-align:center;padding:1.5rem;color:#94a3b8;font-size:.75rem">
    Portfolio Pulse · Data: Yahoo Finance + Finnhub + Google News · {{data.generated_at}}
  </footer>
</div>

<script>
const D=__DATA_JSON__;
const RI=__REC_INFO_JSON__;
const C=__COLORS_JSON__;
const {createApp}=Vue;
createApp({
  data(){return{data:D,RI:RI,view:'summary',idx:0,ddOpen:false,sq:'',anim:false,ftab:'valuation',ao:false,naNeut:false,crOpen:false,monCandOpen:true,colors:C,sortScoreKey:null,sortScoreDesc:true,
    ftabs:[{key:'valuation',label:'估值'},{key:'profit',label:'獲利'},{key:'growth',label:'成長'},{key:'competitors',label:'競品'}]}},
  computed:{
    cur(){return this.data.stocks[this.idx]||{}},
    ri(){const r=this.cur.recommendation;return r&&r!=='unknown'?RI[r]:null},
    filtered(){const v=this.view;const base=v==='competitors'?this.data.stocks.filter(s=>s.category==='競品參考'):v==='candidates'?this.candidateStocks:v==='detail'?this.data.stocks.filter(s=>s.category!=='競品參考'):this.data.stocks;const dropdownBase=base.filter(s=>s.news_analysis&&s.technical&&Object.keys(s.technical).length>0);const source=dropdownBase.length?dropdownBase:base;const now=new Date();const today=now.getFullYear()+'-'+String(now.getMonth()+1).padStart(2,'0')+'-'+String(now.getDate()).padStart(2,'0');const sorted=source.slice().sort((a,b)=>{const ea=a.fundamental&&a.fundamental.next_earnings_date;const eb=b.fundamental&&b.fundamental.next_earnings_date;const fa=ea&&ea>=today;const fb=eb&&eb>=today;if(fa&&fb)return ea<eb?-1:ea>eb?1:0;if(fa)return-1;if(fb)return 1;if(!ea&&!eb)return 0;if(!ea)return eb<today?1:-1;if(!eb)return ea<today?-1:1;return ea<eb?-1:ea>eb?1:0});const q=this.sq.toLowerCase();if(!q)return sorted;return sorted.filter(s=>s.symbol.toLowerCase().includes(q)||s.company.toLowerCase().includes(q))},
    sortedScoreStocks() {
      let arr = this.data.stocks.filter(s => s.shares > 0);
      if (!this.sortScoreKey) return arr;
      const newsOrd = {'strongly_bullish':5,'bullish':4,'neutral':3,'mixed':2,'bearish':1,'strongly_bearish':0};
      return arr.sort((a, b) => {
        let valA = 0, valB = 0;
        if (this.sortScoreKey === 'fund') { valA = a.fundamental?.fund_score || 0; valB = b.fundamental?.fund_score || 0; }
        else if (this.sortScoreKey === 'tech') { valA = a.technical?.tech_score || 0; valB = b.technical?.tech_score || 0; }
        else if (this.sortScoreKey === 'risk') { valA = a.technical?.risk_score || 0; valB = b.technical?.risk_score || 0; }
        else if (this.sortScoreKey === 'news') { valA = newsOrd[this.newsSentimentKey(a)] ?? -1; valB = newsOrd[this.newsSentimentKey(b)] ?? -1; }
        else if (this.sortScoreKey === 'alert') { const alertOrd={3:5,4:4,2:3,1:2,0:1}; const h=this.data.alerts?.holdings||{}; valA=alertOrd[h[a.symbol]?.top_level??4]??4; valB=alertOrd[h[b.symbol]?.top_level??4]??4; }
        return this.sortScoreDesc ? valB - valA : valA - valB;
      });
    },
    candidateStocks(){const list=Array.isArray(this.data.candidates)?this.data.candidates:[];const set=new Set(list.map(s=>String(s||'').toUpperCase()));const raw=this.data.stocks.filter(s=>s.category==='候選'||set.has(String(s.symbol||'').toUpperCase()));const seen=new Map();raw.forEach(s=>{const sym=s.symbol;if(!seen.has(sym)||s.category==='候選')seen.set(sym,s);});return Array.from(seen.values());},
    sortedScoreCandidates(){let arr=this.candidateStocks.slice();if(!this.sortScoreKey)return arr;return arr.sort((a,b)=>{let va=0,vb=0;if(this.sortScoreKey==='fund'){va=a.fundamental?.fund_score||0;vb=b.fundamental?.fund_score||0;}else if(this.sortScoreKey==='tech'){va=a.technical?.tech_score||0;vb=b.technical?.tech_score||0;}else if(this.sortScoreKey==='risk'){va=a.technical?.risk_score||0;vb=b.technical?.risk_score||0;}else if(this.sortScoreKey==='csignal'){const ca=this.getCandAlert(a.symbol);const cb=this.getCandAlert(b.symbol);va=ca?.composite??-999;vb=cb?.composite??-999;}return this.sortScoreDesc?vb-va:va-vb;});},
    monHoldingAlerts(){const h=this.data.alerts&&this.data.alerts.holdings||{};return Object.values(h).filter(x=>x.top_level<4).sort((a,b)=>a.top_level-b.top_level)},
    pp(){const s=this.cur;if(!s.price||!s.technical||!s.technical.high_52w||!s.technical.low_52w)return 50;const r=s.technical.high_52w-s.technical.low_52w;return r<=0?50:Math.max(0,Math.min(100,(s.price-s.technical.low_52w)/r*100))},
    vr(){const t=this.cur.technical||{};return t.current_vol&&t.avg_vol_20d?t.current_vol/t.avg_vol_20d:0},
    earningsInfo(){const f=this.cur.fundamental||{};const ed=f.next_earnings_date;if(!ed)return null;const d=new Date(ed+'T00:00:00');const now=new Date();const diff=Math.ceil((d-now)/(1000*60*60*24));const mm=String(d.getMonth()+1).padStart(2,'0');const dd=String(d.getDate()).padStart(2,'0');const label=d.getFullYear()+'/'+mm+'/'+dd+(diff>=0?' ('+diff+'天後)':' (已過)');if(diff<=14&&diff>=0)return{label,bg:'#fef2f2',border:'#fecaca',color:'#dc2626'};if(diff<=30&&diff>=0)return{label,bg:'#fffbeb',border:'#fde68a',color:'#d97706'};return{label,bg:'#f0f9ff',border:'#bae6fd',color:'#0284c7'}},
    hasScores(){return (this.cur.fundamental&&this.cur.fundamental.fund_score!=null)||(this.cur.technical&&(this.cur.technical.tech_score!=null||this.cur.technical.risk_score!=null))},
    scoreItems(){const f=this.cur.fundamental||{};const t=this.cur.technical||{};const r=[];const gc=v=>v>=80?'#16a34a':v>=60?'#2563eb':v>=40?'#d97706':'#dc2626';if(f.fund_score!=null)r.push({label:'基本面',value:f.fund_score,color:gc(f.fund_score)});if(t.tech_score!=null)r.push({label:'技術面',value:t.tech_score,color:gc(t.tech_score)});if(t.risk_score!=null)r.push({label:'風險',value:t.risk_score,color:gc(t.risk_score)});return r},
    valItems(){const f=this.cur.fundamental||{};return[{label:'Trailing P/E',value:this.fv(f.trailingPE)},{label:'Forward P/E',value:this.fv(f.forwardPE)},{label:'P/S (TTM)',value:this.fv(f.priceToSalesTrailing12Months)},{label:'PEG',value:this.fv(f.pegRatio)},{label:'P/B',value:this.fv(f.priceToBook)},{label:'Beta',value:this.fv(f.beta)},{label:'市值',value:this.fmtL(f.marketCap),hl:true},{label:'EV',value:this.fmtL(f.enterpriseValue)}]},
    profItems(){const f=this.cur.fundamental||{};return[{label:'毛利率',value:this.fp(f.grossMargins),hl:(f.grossMargins||0)>.5},{label:'營業利益率',value:this.fp(f.operatingMargins)},{label:'淨利率',value:this.fp(f.profitMargins)},{label:'ROE',value:this.fp(f.returnOnEquity),hl:(f.returnOnEquity||0)>.2},{label:'ROA',value:this.fp(f.returnOnAssets)},{label:'EPS (TTM)',value:this.fv(f.trailingEps)},{label:'FCF Margin',value:f.fcf_margin!=null?f.fcf_margin.toFixed(1)+'%':'N/A'},{label:'殖利率',value:this.fp(f.dividendYield)}]},
    growItems(){const f=this.cur.fundamental||{};return[{label:'營收成長 YoY',value:this.fp(f.revenueGrowth),hl:(f.revenueGrowth||0)>0},{label:'盈餘成長 YoY',value:this.fp(f.earningsGrowth),hl:(f.earningsGrowth||0)>0},{label:'總營收 TTM',value:this.fmtL(f.totalRevenue)},{label:'EPS Forward',value:this.fv(f.forwardEps)},{label:'FCF TTM',value:this.fmtL(f.freeCashflow)},{label:'營業現金流',value:this.fmtL(f.operatingCashflow)},{label:'D/E',value:this.fv(f.debtToEquity)},{label:'流動比率',value:this.fv(f.currentRatio)}]},
    competitorData(){const cur=this.cur;if(!cur.competitors||!cur.competitors.length)return[];const result=[];result.push(this.formatCompetitor(cur,true));cur.competitors.forEach(sym=>{const stock=this.data.stocks.find(s=>s.symbol===sym);if(stock)result.push(this.formatCompetitor(stock,false))});return result},
    visPos(){return this.data.allocation.positions.filter(p=>p.alloc_pct>=0.5&&p.category!=='競品參考')},
    totalPnlPct(){const c=this.data.allocation.total_cost-this.data.allocation.cash;return c>0?(this.data.allocation.total_pnl/c)*100:0},
    actualStocksCount(){return this.data.stocks.filter(s=>s.shares>0).length},
    categories(){const map={};this.data.allocation.positions.forEach(p=>{const c=p.category||'未分類';if(c==='競品參考'||c==='候選')return;if(!map[c])map[c]={name:c,items:[],totalMV:0,totalPnl:0,totalCost:0,open:true};map[c].items.push(p);map[c].totalMV+=p.market_value;map[c].totalPnl+=p.pnl;map[c].totalCost+=p.cost_total});const order=['長期霸主','長期穩健','中期題材(股票)','短期投機(股票)','未分類'];return order.filter(k=>map[k]).map(k=>map[k]).concat(Object.keys(map).filter(k=>!order.includes(k)).map(k=>map[k]))},
  },
  methods:{
    trendLabel(status){
      const map = {
        'UPTREND':'多頭排列',
        'OVERSOLD_UPTREND':'多頭超賣',
        'OVERBOUGHT_UPTREND':'多頭超買',
        'DOWNTREND':'空頭排列',
        'REBOUND':'跌深反彈',
        'RECOVERY':'跌深反彈',
        'BREAKDOWN':'跌破支撐',
        'SIDEWAYS':'盤整整固',
        'CONSOLIDATION':'盤整整固'
      };
      return map[status] || status || '—';
    },
    toggleScoreSort(key) {
      if (this.sortScoreKey === key) {
        this.sortScoreDesc = !this.sortScoreDesc;
      } else {
        this.sortScoreKey = key;
        this.sortScoreDesc = true;
      }
    },
    switchView(v){if(v===this.view)return;this.sq='';this.ddOpen=false;this.ao=false;this.naNeut=false;this.ftab='valuation';this.view=v;if(v==='detail'||v==='competitors'||v==='candidates'){if(this.filtered.length>0)this.idx=this.oidx(this.filtered[0])}window.scrollTo(0,0)},
    pick(s){const i=this.oidx(s);if(i===this.idx){this.ddOpen=false;return}this.anim=true;this.ddOpen=false;this.sq='';this.ao=false;this.naNeut=false;this.ftab='valuation';setTimeout(()=>{this.idx=i;this.anim=false},150)},
    goSym(sym){const i=this.data.stocks.findIndex(s=>s.symbol===sym);if(i>=0&&i!==this.idx){this.anim=true;this.ao=false;this.naNeut=false;this.ftab='valuation';setTimeout(()=>{this.idx=i;this.anim=false},150)}},
    goDetail(sym){const i=this.data.stocks.findIndex(s=>s.symbol===sym);if(i>=0){this.idx=i;this.view='detail';this.ao=false;this.naNeut=false;this.ftab='valuation';window.scrollTo(0,0)}},
    oidx(s){return this.data.stocks.findIndex(st=>st.symbol===s.symbol)},
    getCandAlert(sym){return (this.data.alerts&&this.data.alerts.candidates)?this.data.alerts.candidates.find(c=>c.symbol===sym):null;},
    newsSentimentKey(s){
      const raw=s&&s.news_analysis&&s.news_analysis.summary&&s.news_analysis.summary.overall_sentiment;
      if(!raw)return'';
      const k=raw.toLowerCase().trim();
      // English exact match (6-level)
      if(k==='strongly_bullish'||k==='bullish'||k==='neutral'||k==='mixed'||k==='bearish'||k==='strongly_bearish')return k;
      // Chinese exact map
      const zhMap={'看多':'bullish','偏多':'bullish','看空':'bearish','偏空':'bearish','中性':'neutral','中立':'neutral','多空分歧':'mixed','分歧':'mixed','混合':'mixed'};
      if(zhMap[raw])return zhMap[raw];
      // Chinese keyword fallback: 混合/分歧 → mixed first, then 多/空 direction
      if(raw.includes('混合')||raw.includes('分歧'))return'mixed';
      if(raw.includes('多')&&raw.includes('空'))return'mixed';
      if(raw.includes('多'))return'bullish';
      if(raw.includes('空'))return'bearish';
      if(raw.includes('中性')||raw.includes('中立'))return'neutral';
      return'';
    },
    newsSentLabel(s){const k=this.newsSentimentKey(s);if(!k)return'—';if(k==='strongly_bullish')return'🔥 強力利多';if(k==='bullish')return'利多';if(k==='mixed')return'分歧';if(k==='bearish')return'利空';if(k==='strongly_bearish')return'🚨 強力利空';return'中立'},
    newsSentStyle(s){const k=this.newsSentimentKey(s);if(!k)return'color:#94a3b8;font-size:.78rem';if(k==='strongly_bullish')return'background:#16a34a;color:#fff;border:1px solid #15803d';if(k==='bullish')return'background:#bbf7d0;color:#14532d;border:1px solid #4ade80';if(k==='strongly_bearish')return'background:#450a0a;color:#fff;border:1px solid #991b1b';if(k==='bearish')return'background:#fee2e2;color:#991b1b;border:1px solid #fecaca';if(k==='mixed')return'background:#fef9c3;color:#854d0e;border:1px solid #fde68a';return'background:#f1f5f9;color:#475569;border:1px solid #e2e8f0'},
    stockName(sym){const s=this.data.stocks.find(x=>x.symbol===sym);return s?s.company:sym},
    stockRec(sym){const s=this.data.stocks.find(x=>x.symbol===sym);return s?s.recommendation:'unknown'},
    fmtMoney(v){if(v==null)return'N/A';return'$'+v.toLocaleString('en-US',{minimumFractionDigits:0,maximumFractionDigits:0})},
    fv(v){if(v==null)return'N/A';return typeof v==='number'?v.toFixed(2):String(v)},
    fp(v){if(v==null)return'N/A';return(v*100).toFixed(1)+'%'},
    fmtL(v){if(v==null)return'N/A';const a=Math.abs(v);const s=v<0?'-':'';if(a>=1e12)return s+'$'+(a/1e12).toFixed(2)+'T';if(a>=1e9)return s+'$'+(a/1e9).toFixed(2)+'B';if(a>=1e6)return s+'$'+(a/1e6).toFixed(1)+'M';return s+'$'+a.toLocaleString()},
    fmtNum(v){if(v==null)return'N/A';if(v>=1e6)return(v/1e6).toFixed(1)+'M';if(v>=1e3)return(v/1e3).toFixed(0)+'K';return v.toLocaleString()},
    openNews(link){if(link)window.open(link,'_blank')},
    formatCompetitor(stock,isCurrent){const f=stock.fundamental||{};return{symbol:stock.symbol,isCurrent,pe:this.fv(f.trailingPE),marketCap:this.fmtL(f.marketCap),revenueGrowth:this.fp(f.revenueGrowth),revenueGrowthNum:f.revenueGrowth||0,roe:this.fp(f.returnOnEquity),roeNum:f.returnOnEquity||0,profitMargin:this.fp(f.profitMargins),profitMarginNum:f.profitMargins||0}},
  },
}).mount('#app');
</script>

</body>
</html>"""



