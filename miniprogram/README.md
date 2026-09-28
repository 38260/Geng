# 赶梗潮 · 微信小程序

`miniprogram/` 是独立于 `frontend/`（Web）的第二端：**Taro 4 + React + TypeScript**，
一份源码出两个目标。

| 目标 | 命令 | 产物 | 用途 |
| --- | --- | --- | --- |
| 微信小程序 | `npm run build:weapp` | `dist/weapp/` | 交给微信开发者工具上传 |
| H5 预览 | `npm run build:h5` | `dist/h5/` | 手机浏览器看效果，也用来做视觉核验 |

只做**只读**：小程序不调 `/api/manage`、`/api/jobs` 这些写接口——V1 没有登录体系，
那些接口本来就没鉴权，把它们接到小程序等于把改数据的口子开到公网。

## 一、跑起来

```bash
cd miniprogram
npm install                 # 依赖装的是 Taro 4.1.6 + React 18
npm run build:weapp         # 产出 dist/weapp
```

然后打开**微信开发者工具**：导入项目 → 目录选 `miniprogram/`（不是 `dist/`，
`project.config.json` 里 `miniprogramRoot` 已指向 `dist/weapp/`）→ AppID 填自己的，
没有就选"测试号"。

后端默认打 `http://127.0.0.1:8010`。开发者工具右上角 **详情 → 本地设置 →
勾选「不校验合法域名…」**，模拟器才能连本机 HTTP。

真机预览时手机连不到你电脑的 `127.0.0.1`：在小程序「口径」页把后端地址改成
电脑的局域网 IP（如 `http://192.168.1.20:8010`）保存即可，存在 storage 里、
不用重新编译。

## 二、上线前必须做的三件事

1. **HTTPS + 合法域名**：微信只允许 `https` 且在小程序后台配过的域名。
   本机 HTTP 只能用于开发。
2. **给 `/api/manage/*` 加访问控制**：这些写接口现在无鉴权（见根 README 的
   「安全」一节），公网部署前必须先加。
3. **AppID**：`project.config.json` 里是占位的 `touristappid`，换成自己的再上传。

## 三、页面

| 页面 | 路径 | 内容 |
| --- | --- | --- |
| 热榜 | `pages/home` | 过了"活着"门槛的梗，卡片带热度/阶段/赶梗/认证标签，下拉刷新、触底分页 |
| 梗库 | `pages/library` | 完整梗库（含没上热榜的），搜索（名称/别名/关键词）+ 四种排序 |
| 详情 | `pages/detail` | **梗介绍**、热度四指标、趋势柱、生命周期、赶梗判断、相关视频、这条数据的口径 |
| 口径 | `pages/about` | 热榜/梗库/被挡/候选池四个数、准入与门槛规则原文、热度算法、后端地址切换 |

详情页的介绍块与 Web 端同源（`backend/app/services/meme/intro.py`）：
人工介绍优先；没有就用抓取到的解说视频标题与简介**原文**拼，界面标「证据原文拼出」；
两样都没有就明说「暂无介绍」，不留白。小程序打不开站外链接，所以出处做成
"点一下复制视频地址"。

## 四、分享

四个页面都接了 `useShareAppMessage`，转发路径带上下文：

| 页面 | 分享标题 | 落点 |
| --- | --- | --- |
| 详情 | 「闪身步」现在赶还来得及吗？ | `/pages/detail/index?id=51` |
| 热榜 | 今天赶什么梗？B 站热榜 12 个活梗 | `/pages/home/index` |
| 梗库 | B 站梗库 31 个梗，热度与生命周期都能查 | `/pages/library/index` |
| 口径 | 赶梗潮：这些数字是怎么算出来的 | `/pages/about/index` |

标题刻意写成一句人话问句，不出现"AI 智能分析"这类词。详情页右上角还有一个
「分享」按钮（`open-type="share"`）——小程序里没有"复制链接"这种原生入口，
转发才是它的分发路径。

两点没做，原因写在代码注释里：**不用自定义分享图**（B 站封面有防盗链，
跨端引用不稳，宁可让微信截默认页面图）；**不开朋友圈单页模式**（`shareTimeline`
打开的是受限的 singlePage 环境，本机没有开发者工具无法核验，宁可不给）。
`open-type="share"` 只在微信里生效，H5 预览上那个按钮点了没反应，属正常。

## 五、响应式做法

- 样式里写小写 `px`，Taro 按 `designWidth: 750` 编译成 `rpx`，跟着屏宽缩放；
  不想跟着放大的（1 物理像素分割线、平板上给内容列封顶）写大写 `PX`。
- 底部留 `calc(env(safe-area-inset-bottom) + 140px)`，最后一张卡不会被 Home 条压住。
- `@media (min-width: 500PX)` 把内容列封顶 480PX 居中，iPad/桌面大屏不会拉成横幅。
- 数字统一 `font-variant-numeric: tabular-nums`，榜单右对齐不抖。

## 六、测试

```bash
npm test          # node --test，不引 jest/vitest
npm run typecheck
npm run build:weapp && npm run build:h5
```

- `tests/format.test.ts`：格式化与配色映射的纯函数单测（万/亿、增长率 `—`、
  新鲜度文案、真实/演示判定、趋势归一不产生 NaN）。
- `tests/contract.test.ts`：对着**真实后端**逐字段核对小程序的类型假设——
  榜单与梗库的分母关系、卡片必填字段、详情介绍不许空白、趋势窗口只收 7/30、
  采信视频都过相关性阈值。后端没起时每条各自 skip 并说明原因，不会静默假通过。

## 七、这一端刻意没做什么

- 没有收藏/登录：V1 不做用户体系，Web 端的收藏是 localStorage，不跨端同步。
- 趋势图用 CSS 柱子而不是 ECharts/canvas：canvas 在 weapp 与 h5 两套实现差异大，
  柱子两边渲染一致，才能拿 H5 截图当 weapp 的视觉证据。
- 不接 AI 文案接口（`POST /api/memes/{id}/insight`）：详情页展示的是算法自己写的
  那句理由，AI 生成的那段只在 Web 端有，小程序不重复引一次 LLM 依赖。
