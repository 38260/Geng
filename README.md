# 赶梗潮 GengChao

> **今天，赶什么梗？** —— 只看 B 站数据，判断一个梗正在起飞、爆发、退潮，还是已经过气。

一个只分析 **Bilibili 网络梗** 热度与生命周期的 Web 数据产品。

```
B站数据 → 采集 → 清洗 → 梗匹配 → 发现层准入（并集）+ 双UP认证标签 → 时间序列聚合 → 热度指数 → 生命周期 → LongCat 解释 → FastAPI → React
```

分工：**数据负责证明，算法负责判断，LongCat 负责解释，UI 负责呈现。**

---

## 一、快速开始

### 0. 一键启动（推荐，Windows）

双击仓库根目录的 **`start.bat`**：自动检查环境 → 缺依赖就装 → 选空闲端口 →
起后端与前端 → 等健康检查通过 → 打印访问地址与当前数据源。

| 文件 | 作用 |
| --- | --- |
| `start.bat` | 一键启动。启动后**按任意键即停止全部服务** |
| `start.bat --detach` | 启动后保持后台运行（服务开在两个最小化窗口里） |
| `stop.bat` | 停止 `start.bat` 记录过的全部服务 |

已实测的行为：

* 默认端口 8010 / 5173 被占用时自动往后找空闲端口（并同步告诉前端代理目标）；
* 可以同时起多份，`stop.bat` 会把记录过的端口全部停掉；
* 依赖已就绪时约 11 秒完成启动；首次运行会自动 `pip install` / `npm install`；
* 空库启动会自动灌演示数据，且此时界面与接口都会如实标成「演示数据」
  （站点标签按**库里实际数据**判定，不按 `.env` 配置判定）。

> 技术注记：两个 `.bat` 必须以 **GBK(ANSI)** 保存且不要调用 `chcp 65001`——
> UTF-8 编码的中文批处理会被中文 Windows 的 cmd 解析器切碎，实测会把
> `rem`/`echo`/`start` 标题当成命令执行报错。

### 1. 后端（Python 3.10+）

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env              # 需要真实 AI 文案时填 LLM_API_KEY
python -m app.scripts.seed_data   # 建梗库骨架（幂等；库里有真实采集数据时会拒绝，除非 --force）
python -m app.scripts.run_pipeline --report   # 算热度/生命周期并打印榜单
uvicorn app.main:app --port 8010
```

想用真实 B 站数据替换演示数据（本机已验证可跑通，约 15 分钟）：

```bash
python -m app.scripts.rebuild_from_bilibili   # 逐日真实采集 + 在线核验 + 重算
# 可选：在 backend/.env 填 BILI_COOKIE 后加 --pages 20 --refresh-index，
# 才能把双 UP 认证从"未在线核验"升级为"已核验 + 真实投稿链接"
```

> 端口用 8010 是因为本机 8000 已被另一个服务占用；换端口不影响功能，下一步告诉前端即可。
> 空库启动时后端会自动灌一次演示数据，所以 `uvicorn` 单独起也能跑。

### 2. 前端（Node 18+）

```bash
cd frontend
npm install
VITE_API_TARGET=http://127.0.0.1:8010 npm run dev    # Windows PowerShell 见下
```

PowerShell：

```powershell
$env:VITE_API_TARGET="http://127.0.0.1:8010"; npm run dev
```

打开 http://localhost:5173

### 3. 常用脚本

| 命令 | 作用 |
| --- | --- |
| `python -m pytest`（backend 目录） | 102 个后端测试 |
| `python scripts/smoke_api.py` | 对运行中的后端逐个打接口 |
| `bash scripts/screenshot.sh` | Chrome 无头截图，做视觉比对 |
| `bash scripts/ui_shot.sh home "/"` | 截图 + 缩到参考图画板宽度，输出并排图与 50% 叠图（`.shots/cmp-*.png` / `blend-*.png`） |
| `python scripts/extract_ref_assets.py` | 从 `docs/design/reference-ui.png` 重切前端素材（封面、Logo、Hero 装饰带） |
| `bash scripts/restart-backend.sh` | 重启本地后端 |
| `python -m app.scripts.collect_data --source bilibili --limit 3` | 真实 B 站采集 |

---

## 二、页面

| 路由 | 内容 |
| --- | --- |
| `/` | Hero + 筛选（全部/正在爆/快起飞/退潮中）+ 今日热榜 5 卡 + 精选推荐 + 数据透明度页脚 |
| `/meme/:id` | 梗头卡（热度/阶段/赶梗状态/数据来源）、四项指标带增幅、ECharts 热度趋势 7/30 天、生命周期轨道、赶梗判断、趋势解释、相关视频、认证证据（含认证强度标签） |
| `/library` | 全量已认证梗，筛选 + 搜索 + 排序 |
| `/trends` | 热度榜表格（相对位置 + 增幅 + 赶梗结论） |
| `/favorites` | 本机 localStorage 收藏，无账号体系 |
| `/manage` | 梗管理：挑封面（从该梗已采集的真实视频封面里选，或粘贴图片地址）、写介绍、维护别名与关键词；候选梗也能管 |
| `/settings` | LLM 配置（Provider/BaseURL/Key/Model/Temperature/MaxTokens）+ 测试连接 + 系统信息 |

---

## 三、核心机制

### 梗库准入与双 UP 认证（两层，真实落在数据模型上）

```
准入（发现层，并集）= encyclopedia_confirmed OR guide_confirmed   → 进梗库、被采集、被算分、上榜
认证（徽章，交集）  = encyclopedia_confirmed AND guide_confirmed  → 标签「双 UP 认证」
```

* 梗百科 `space.bilibili.com/1544008396`（主来源，日更）、梗指南 `space.bilibili.com/94510621`（补充）
* **认证窗口 90 天滚动**（`CERT_WINDOW_DAYS`）：介绍过没有看 90 天，报告/分析窗口仍是 30 天。
  解说视频通常比梗的爆发期早 1~2 周，两个窗口合成一个就会漏掉正在热的梗
* 准入为什么从交集改成并集（2026-09-27 实测）：90 天内梗百科单独介绍过 37 个梗、梗指南 22 个，
  交集只剩 8 个——交集等于让日更 UP 的选题被周更 UP 的排期否决。
  实测「闪身步」热度 81.0（当期最高）就因为只在梗百科做过而被挡在库外
* 卡片与详情页如实标出证据来自哪一位：`cert_label` = 双 UP 认证 / 梗百科认证 / 梗指南认证，
  `verification_state` = verified_both / partially_verified / unverified（只认真实抓到的投稿，
  演示数据自记自认的 `confirmed` 一律算未核验）
* 证据存在 `meme_certifications` 表；撤销一边只掉「双 UP」徽章，不会把梗踢出池子，
  两位都没做过才退回 `candidate`
* 分析管线入口 `require_certified()` 拒绝未入池梗；接口对未入池梗返回 409 并说明原因
* 演示梗库里刻意保留单 UP 入池（新梗观察A/B）与未入池（网友投稿梗）各例，用来验证两层规则各在工作

### 梗热度指数（0-100，自有算法）

```
Hotness = 0.25*ViewScore + 0.20*InteractionScore + 0.16*ContentScore
        + 0.14*CreatorScore + 0.25*GrowthScore
```

* 绝对量做**对数区间归一化**，一条爆款视频吃不掉整个榜
* 增长权重给到 0.25，只看「最近 7 天 vs 前 7 天」——去年 1 亿播放、今天没人做的梗不会霸榜
* 近两周样本过小时，增长率不外推（考古区冒出一条视频不算 +100%），整体打折
* 权重与阈值全部集中在 `backend/app/config/algorithms.py`，前端不写任何判定逻辑

### 生命周期（时间序列 + 规则，不由 LLM 决定）

🌱 萌芽 → 📈 上升 → 🔥 爆发 → 🌊 平稳 → 📉 退潮 → 🪦 过气，自上而下匹配规则，
判定依据（增长率、距峰值差、连续下滑天数、活跃度）会显示在详情页。

### 上榜门槛（准入 ≠ 上榜）

```
热榜 = 通过发现层准入（并集）∧ 有指标快照 ∧ 不是过气 ∧ 近 7 天头部播放 ≥ 1 万
```

* 准入只回答"这是不是个真梗"，首页还要回答"今天玩什么"，所以过气（考古区）的梗不进热榜，
  近 7 天连 1 万次头部播放都没有的也不进（例：「omg你吓到我了」30 天里 26 天有内容，
  但近 7 天只有 3,770 次播放，属于历史残值）
* **刻意不用"有内容天数"当门槛**：「琵琶曲」30 天只有 4 天有内容，那几天却播了 3,976 万，
  按天数卡会把脉冲型梗误杀。`active_days` 只作为诊断量存进快照与门槛理由里
* 门槛只影响首页/趋势：`GET /api/memes?scope=all` 返回完整梗库，梗库页与收藏页用的就是它；
  `/api/meta` 同时给出 `certified_count`（热榜数）、`library_count`（梗库数）与 `gated_out`（被挡掉数），
  并把门槛口径写进 `transparency.board_gate`
* 实测效果（2026-09-28）：31 个入池有数据的梗 → 12 个上热榜，被挡掉的 17 个全是过气、2 个只剩残值
* 关掉用 `LEADERBOARD_GATE=false`（只在排查数据时用）

### 赶梗判断

`can_catch / caution / too_late` 三态由算法给出，附带置信度与一句算法自己的判断。
LLM 只能润色这句话，**不能改状态**：模型返回的 `status` 与算法不一致时以算法为准，
文案里出现「预计/未来 7 天/一定会爆」这类预测口吻会被直接丢弃。

### 梗管理：人工只碰展示层

`/manage`（接口 `/api/manage/memes*`）允许人工维护**四个字段**：封面、介绍、别名、关键词。
白名单写死在 `app/services/meme/manage.py` 里，请求 `hotness`、`certified` 这类字段会被 400 拒绝，
保存也不会触发重算——热度、生命周期、赶梗结论只能由算法从数据里算出来。

* 封面优先级：人工挑的 > 该梗播放量最高视频的 B 站真实封面 > 演示素材图 > 表情贴纸；
  人工封面在接口里带 `manual: true`，详情页会显示「人工封面」标记
* 可挑的封面来自已采集的真实视频（按播放量排序、去重），演示数据没真封面就是空列表
* 别名与关键词影响搜索命中与后续采集的相关性过滤，改完不会追溯已算好的指标
* ⚠️ V1 不做登录体系，这些写接口**没有鉴权**：只适合本机或内网使用，
  要放到公网必须先自行加访问控制

### 梗介绍：详情页的「这个梗是什么」

真实梗里 31/55 条 `description` 是空的，点进详情页只剩一片空白，用户会以为系统坏了。
所以介绍按三档来源合成（`app/services/meme/intro.py`），界面用 `intro.source` 标出来：

| 来源 | 什么时候用 | 界面标注 |
| --- | --- | --- |
| `manual` | 梗管理里人工写过介绍 | 「人工撰写」 |
| `evidence` | 没人工介绍，但抓到了真实证据 | 「证据原文拼出」 |
| `none` | 两样都没有 | 「暂无介绍」+ 去梗管理补的入口，不留白 |

`evidence` 这条路的每个字都能在 `meme_certifications` / `videos` 两张表里找到出处：
先列「哪位 UP 主、哪一期解说视频」（标题是 B 站返回的原文），再附一段头部相关视频的
简介原文。**系统不做改写、不做归纳，LLM 也不参与**（V1 约定：AI 只复述算法结论，
不生产事实）。摘录只清洗噪声——话题标签、外链/BV 号、"求三连"式刷屏（这类占比超过
35% 直接判为不可用），剥完不足 40 字就不摘。

### AI 不是单点故障

* 未配 Key：文案位置显示算法自己写的那句话，并标注「文案来源：算法兜底」
* 调用失败/超时：`catch_up_advice` 返回 `unavailable`，卡片给出「暂时无法生成 + 重新判断」
* 热度、生命周期、图表、B 站数据全部不依赖 AI，照常渲染
* 结果按 `(meme_id, kind, data_version)` 缓存，数据没明显变化不再打接口
* 429/5xx/超时会重试，但次数有限（默认 2 次，指数退避），绝不无限重试

---

## 四、当前数据集：真实 B 站数据

本仓库当前数据库里的指标**全部来自 B 站真实抓取**（`backend/.env` 里 `DATA_SOURCE=bilibili`）：

| 项目 | 实测结果 |
| --- | --- |
| 采集到的真实视频 | 2,500+ 条候选，相关性过滤后保留约 1,100 条 |
| 被剔除的无关视频 | 1,446 条（短词会被 B 站模糊匹配到大量无关内容） |
| 有真实数据的梗 | 28 个（另 8 个近 30 天无相关视频，已清空而非保留演示值） |
| 榜首示例 | 哈基米 66.6 / 上升期 / +89%（真实播放量最高单条 643.3 万） |

重建整个数据集（约 15 分钟，会覆盖现有数据）：

```bash
cd backend
python -m app.scripts.seed_data                # 先建梗库骨架（有真实数据时会被拦下）
python -m app.scripts.rebuild_from_bilibili    # 在线核验 + 逐日真实采集 + 重算指标
```

### 真实采集的统计口径（重要，别误读）

* **逐日区间查询**：对每个梗的最近 30 天，每天单独查一次 B 站搜索
  （`pubtime_begin_s/pubtime_end_s` + `order=click`），取当日播放量最高的前 20 条相关视频作为样本。
  所以「当日播放量」是**该日头部内容的合计**，不是该梗全站绝对量；跨日、跨梗用同一把尺子，形状与排序可信。
* 为什么不一次搜完再聚合：不带日期区间时搜索结果会被最近发布的内容占满，早期日期根本查不到，
  直接聚合会算出 **+23616%** 这种被截断放大的假增长（第一版就是这么翻车的）。
* 日统计的互动量 = 评论 + 弹幕（搜索接口给得到的字段）；点赞/投币/收藏只对头部视频逐条补齐，
  用于详情页视频卡展示，不回灌日统计，避免两个口径混用。
* 不含"今天"：当天还没过完，计入会让最后一天假性下跌。顶栏日期位与页脚因此显示
  **「统计截至 YYYY-MM-DD」**，不是"今天"——这是口径，不是数据没刷新。
* 增幅有基数门槛：前 7 天讨论量不足 30（`MIN_GROWTH_DISCUSSION`）时不报百分比，
  卡片显示"—"。基数 3 涨到 20 也是 +567%，但那是噪声。
* **短别名不能单独判定相关**：中文 2~3 字的别名基本就是常用词。
  「我不是黄豆」的别名"黄豆"会撞上琵琶曲黄豆版、炒黄豆、树叶做豆腐——旧规则里
  别名命中即 0.85，`0.6×0.85=0.51` 直接过阈值，于是 418 条样本里 343 条其实只在讲黄豆
  （该梗当时还是热度榜第一）。现在短别名（< `STRONG_ALIAS_LEN`=4）只算弱证据，
  必须再有第二个词（描述/标签/另一关键词）佐证；4 字以上别名（赛博木鱼）与梗名命中不变。
* 梗名是常用口语时（「啊对对对」「这很难评」）B 站会把结果模糊匹配到无关内容，
  采集会自动退回**别名**再查一轮，取有内容天数更多的那一版。
* 一次空窗不会删掉上次采到的真实快照（只清掉非同源/演示行），
  重采结果比上次薄时会打 WARNING 并计入 `thinned`。

刷新数据（约 20~35 分钟，可中断）：

```bash
bash scripts/refresh-data.sh          # 全量重采 + 重算，末尾回报覆盖率与前 5
LIMIT=5 bash scripts/refresh-data.sh  # 先拿 5 个梗试一下
```

### 梗库怎么长出来：发现层脚本 + 在线核验受风控限制

入库口径由 `app.scripts.list_recent_certified` 决定：翻两位 UP 主的真实投稿 →
从标题抽梗名 → **并集入池**（写法不同的同一梗会保守合并）→ 带真实 bvid / 标题 / 发布时间入库 →
逐日采集 → 重算。

```bash
cd backend
PYTHONIOENCODING=utf-8 python -m app.scripts.list_recent_certified --ingest   # 报告 30 天 / 认证 90 天
```

但本机实测：**只能拉到每位 UP 主最近约 150~400 条投稿**（`space/wbi/arc/search` 深翻页被 -352/412 挡住），
拉不到就如实记在报告的「缺口」一节里，不会拿旧证据凑数。因此：

* 只有一位的投稿被拉到，池子照样出（准入是并集），该梗标 `partially_verified`；
* 演示阶段造的假 BV 号已全部清除，未核验的证据**不给可点开的链接**（`linkable=false`）；
* 手写演示梗的 `certified` 是自记自认的，不算真实证据，所以真实模式下 `verification_state=unverified`
  的梗一律不进榜单（`LEADERBOARD_REQUIRE_VERIFIED`）；
* 想要更完整的核验：在 `backend/.env` 填 `BILI_COOKIE`（浏览器登录 B 站后复制），
  再跑 `python -m app.scripts.rebuild_from_bilibili --pages 20 --refresh-index`，
  命中的梗会自动升级为「已在线核验」并带上真实投稿链接。

---

## 五、数据来源与诚实性

* `DATA_SOURCE` 决定全站标注：`mock` 显示「演示数据」，`bilibili` 显示「B站真实数据」，
  两者都不会互相冒充；每个梗还额外带 `meme_data_source`，混跑时也能分清
* 演示数据按生命周期原型生成曲线（上升/爆发/平稳/退潮/过气各有形状），
  且「当日播放量 = 当日视频数 × 单条播放量」自洽，过气梗近两周真的归零
* 梗名称/别名取自真实存在的 B 站梗文化说法，但**所有数值都是生成的**
* 梗封面用「主题色 + 表情」贴纸块占位（本机无图像生成额度），
  比例/圆角/裁剪与参考图一致，换成真实封面不需要改布局
* 侧栏吉祥物与 Hero 吉祥物直接复用项目提供的 `docs/design/元素1.png`、`元素2.png`

### 真实 B 站采集（已跑通，默认关闭）

在本机验证过：WBI 签名后 `搜索接口` 与 `视频详情接口` 匿名可用，
一次 `--limit 2` 的采集真实拉回 218 条视频并算出了热度与生命周期。

```bash
python -m app.scripts.collect_data --source bilibili --limit 3
# 或
curl -X POST "http://127.0.0.1:8010/api/jobs/collect?source=bilibili&limit=3"
```

已知限制（重要）：

1. **UP 主空间接口被风控**（`code=-352`），要拉两位 UP 主的真实投稿作为认证证据，
   需要在 `backend/.env` 填 `BILI_COOKIE`。没有 Cookie 时认证仍沿用梗库既有记录，
   且**不会拼半份证据**。
2. 单次抓取只能得到「当天发布的视频 + 此刻的累计指标」，
   越早的日期样本越稀疏，所以**首次真实采集会把增长率算得偏高**。
   要得到可信的时间序列，需要每天定时跑一次采集积累。
3. 一个梗只保留一份数据来源：采集时会先清掉该梗旧数据，避免演示与真实混算。

---

## 六、目录结构

```
backend/
  app/
    api/          # FastAPI 路由：memes / llm / settings / jobs / meta
    models/       # SQLAlchemy：Meme, MemeCertification, Video, MemeDailyStats,
                  #           HotnessSnapshot, LifecycleSnapshot, AIInsight
    schemas/      # 请求体模型
    services/
      llm/        # config / client / service（LongCat 走 OpenAI 兼容接口）
      meme/       # certification（准入并集 + 双 UP 徽章）、discovery（发现层并集）、query（读侧组装）
      pipeline.py # 采集 → 匹配 → 聚合 → 热度 → 生命周期
      settings_store.py  # 把前端填的配置写回 .env
    analytics/    # relevance / series / hotness / lifecycle / catch_up / aggregation
    collectors/   # mock_collector / bilibili_collector / base 契约
    prompts/      # trend-explanation.txt / catch-up-advice.txt
    config/       # settings(.env) / algorithms(阈值) / logging(带密钥脱敏)
    mock/         # 演示梗库与曲线
    scripts/      # seed_data / run_pipeline / collect_data
  tests/          # 177 例
frontend/src/
  api/  types/  hooks/  components/  pages/  utils/
miniprogram/      # 微信小程序端（Taro 4 + React + TS）：一份源码出 weapp / h5
  src/api/        # 只读接口封装（地址可按环境覆盖），不调没有鉴权的写接口
  src/pages/      # 热榜 / 梗库 / 口径 三个 tab + 详情页
  tests/          # 14 例：展示层纯函数 + 对着真实后端的接口契约
docs/             # 产品与前端提示词、UI 参考图（前端按它 1:1 复刻）
scripts/          # smoke_api.py / screenshot.sh / restart-backend.sh
```

小程序端的启动、上线前置条件（HTTPS + 合法域名 + AppID + 给写接口加鉴权）与
响应式做法见 [miniprogram/README.md](miniprogram/README.md)。

---

## 七、验收清单

### 产品

- [x] 名称「赶梗潮」，首页标题「今天，赶什么梗？」，副标题为 B 站梗定位说明
- [x] 首页梗榜 → 详情页 → 热度 → 生命周期 → 趋势 → 还来得及/慎赶/你来晚了，闭环成立
- [x] 首页不出现「AI 智能分析 / AI 预测 / AI 助手」字样
- [x] AI 文案是自然中文、不报数字、不写成报告、不自称 AI

### 数据

- [x] 只分析 Bilibili，无抖音/小红书/微博等
- [x] 梗库准入（并集）与双 UP 认证（交集徽章）两层规则，模型 + 管线 + 接口三处强制，且有测试
- [x] 热度与生命周期均由算法计算，AI 不参与任何数值判断
- [x] 演示/真实数据全站明确标注，接口与前端都带 `meme_data_source` 与 `verification_state`
- [x] 真实数据已替换演示数据：28 个梗、约 1,100 条真实视频、逐日 30 天序列

### AI

- [x] Provider / Base URL / Model / Temperature / Max Tokens / Timeout 均可 `.env` 配置
- [x] API Key 不进前端、不进日志、不进 Git（`.env` 已忽略，日志有脱敏过滤器）
- [x] LLM 必须经后端：前端只调用自己的 FastAPI
- [x] 无 Key、错误 Key、超时三种情况都不会让页面崩，且可「重新判断」
- [x] 结果按数据版本缓存；不做未来数值预测

### UI

- [x] 冷白画布 + 纯白卡片 + 珊瑚红主强调，毛笔体标题，年轻向而非企业 BI
- [x] 无紫色渐变 / 机器人 / 芯片 / 神经网络 / 聊天框 / 玻璃拟态 / 粒子
- [x] 动画克制（卡片 hover 上浮、当前阶段脉冲、图表 tooltip），Desktop 优先，移动端单/双列可用

### 测试

- [x] `python -m pytest` → 100 passed（认证闸门、算法六态、热度边界与 NaN、
      相关性阈值、赶梗三态、LLM 降级与缓存、采集层离线全流程、接口集成）
- [x] `python scripts/smoke_api.py` → 46/46 通过（对运行中的真实服务）
- [x] `npm run build` 通过；首页 JS 204KB（gzip 66KB），ECharts 拆到详情页
- [x] 后端停机时前端渲染错误态 + 启动提示 + 重新加载，不白屏

---

## 八、安全

* `backend/.env` 已在 `.gitignore`，仓库里只有 `.env.example`
* 日志经 `SecretRedactionFilter` 脱敏，`api_key=` / `Bearer` / `sk-` 形态会被替换
* `/api/settings/llm` GET 只返回掩码；PUT 时留空表示不修改 Key
* 前端构建产物已扫描，无任何密钥字样
