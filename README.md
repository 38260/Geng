# 赶梗潮 GengChao

> **今天，赶什么梗？** —— 只看 B 站数据，判断一个梗正在起飞、爆发、退潮，还是已经过气。

一个只分析 **Bilibili 网络梗** 热度与生命周期的 Web 数据产品。

```
B站数据 → 采集 → 清洗 → 梗匹配 → 双UP认证 → 时间序列聚合 → 热度指数 → 生命周期 → LongCat 解释 → FastAPI → React
```

分工：**数据负责证明，算法负责判断，LongCat 负责解释，UI 负责呈现。**

---

## 一、快速开始

### 1. 后端（Python 3.10+）

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env              # 需要真实 AI 文案时填 LLM_API_KEY
python -m app.scripts.seed_data   # 灌演示数据（幂等，可反复跑）
python -m app.scripts.run_pipeline --report   # 算热度/生命周期并打印榜单
uvicorn app.main:app --port 8010
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
| `python -m pytest`（backend 目录） | 100 个后端测试 |
| `python scripts/smoke_api.py` | 对运行中的后端逐个打接口 |
| `bash scripts/screenshot.sh` | Chrome 无头截图，做视觉比对 |
| `bash scripts/restart-backend.sh` | 重启本地后端 |
| `python -m app.scripts.collect_data --source bilibili --limit 3` | 真实 B 站采集 |

---

## 二、页面

| 路由 | 内容 |
| --- | --- |
| `/` | Hero + 筛选（全部/正在爆/快起飞/退潮中）+ 今日热榜 5 卡 + 精选推荐 + 数据透明度页脚 |
| `/meme/:id` | 梗头卡（热度/阶段/赶梗状态/数据来源）、四项指标带增幅、ECharts 热度趋势 7/30 天、生命周期轨道、赶梗判断、趋势解释、相关视频、双 UP 认证证据 |
| `/library` | 全量已认证梗，筛选 + 搜索 + 排序 |
| `/trends` | 热度榜表格（相对位置 + 增幅 + 赶梗结论） |
| `/favorites` | 本机 localStorage 收藏，无账号体系 |
| `/settings` | LLM 配置（Provider/BaseURL/Key/Model/Temperature/MaxTokens）+ 测试连接 + 系统信息 |

---

## 三、核心机制

### 双 UP 梗认证（真实落在数据模型上，不是 README 里的一句话）

```
certified = encyclopedia_confirmed AND guide_confirmed
```

* 梗百科 `space.bilibili.com/1544008396`、梗指南 `space.bilibili.com/94510621`
* 证据存在 `meme_certifications` 表，撤销任一 UP 认证会自动退回 `candidate`
* 分析管线入口 `require_certified()` 直接拒绝未认证梗；接口对未认证梗返回 409 并说明缺哪一边
* 演示梗库里刻意保留 3 个未认证梗，用来验证这道闸门确实在工作

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

### 赶梗判断

`can_catch / caution / too_late` 三态由算法给出，附带置信度与一句算法自己的判断。
LLM 只能润色这句话，**不能改状态**：模型返回的 `status` 与算法不一致时以算法为准，
文案里出现「预计/未来 7 天/一定会爆」这类预测口吻会被直接丢弃。

### AI 不是单点故障

* 未配 Key：文案位置显示算法自己写的那句话，并标注「文案来源：算法兜底」
* 调用失败/超时：`catch_up_advice` 返回 `unavailable`，卡片给出「暂时无法生成 + 重新判断」
* 热度、生命周期、图表、B 站数据全部不依赖 AI，照常渲染
* 结果按 `(meme_id, kind, data_version)` 缓存，数据没明显变化不再打接口
* 429/5xx/超时会重试，但次数有限（默认 2 次，指数退避），绝不无限重试

---

## 四、数据来源与诚实性

* 默认 `DATA_SOURCE=mock`，**全站标注「演示数据」**，页脚写明更新时间，不伪装实时
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

## 五、目录结构

```
backend/
  app/
    api/          # FastAPI 路由：memes / llm / settings / jobs / meta
    models/       # SQLAlchemy：Meme, MemeCertification, Video, MemeDailyStats,
                  #           HotnessSnapshot, LifecycleSnapshot, AIInsight
    schemas/      # 请求体模型
    services/
      llm/        # config / client / service（LongCat 走 OpenAI 兼容接口）
      meme/       # certification（双 UP 闸门）、query（读侧组装）
      pipeline.py # 采集 → 匹配 → 聚合 → 热度 → 生命周期
      settings_store.py  # 把前端填的配置写回 .env
    analytics/    # relevance / series / hotness / lifecycle / catch_up / aggregation
    collectors/   # mock_collector / bilibili_collector / base 契约
    prompts/      # trend-explanation.txt / catch-up-advice.txt
    config/       # settings(.env) / algorithms(阈值) / logging(带密钥脱敏)
    mock/         # 演示梗库与曲线
    scripts/      # seed_data / run_pipeline / collect_data
  tests/          # 100 例
frontend/src/
  api/  types/  hooks/  components/  pages/  utils/
docs/             # 产品与前端提示词、UI 参考图（前端按它 1:1 复刻）
scripts/          # smoke_api.py / screenshot.sh / restart-backend.sh
```

---

## 六、验收清单

### 产品

- [x] 名称「赶梗潮」，首页标题「今天，赶什么梗？」，副标题为 B 站梗定位说明
- [x] 首页梗榜 → 详情页 → 热度 → 生命周期 → 趋势 → 还来得及/慎赶/你来晚了，闭环成立
- [x] 首页不出现「AI 智能分析 / AI 预测 / AI 助手」字样
- [x] AI 文案是自然中文、不报数字、不写成报告、不自称 AI

### 数据

- [x] 只分析 Bilibili，无抖音/小红书/微博等
- [x] 只有双 UP 认证梗进入正式梗库（模型 + 管线 + 接口三处强制，且有测试）
- [x] 热度与生命周期均由算法计算，AI 不参与任何数值判断
- [x] Mock 数据全站明确标注，接口与前端都带 `data_source`

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

## 七、安全

* `backend/.env` 已在 `.gitignore`，仓库里只有 `.env.example`
* 日志经 `SecretRedactionFilter` 脱敏，`api_key=` / `Bearer` / `sk-` 形态会被替换
* `/api/settings/llm` GET 只返回掩码；PUT 时留空表示不修改 Key
* 前端构建产物已扫描，无任何密钥字样
