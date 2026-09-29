# 两份答辩 PPT 的说明与数字出处

> 这两份 deck 由脚本生成，数字全部来自 `backend/data/gengv1.db` 的实测查询，
> 以及仓库里已有文档记录的实验结论。生成脚本在 `build_ppt/` 下。

## 文件

| 文件 | 用途 | 页数 | 备注 |
| --- | --- | --- | --- |
| `赶梗潮-开题汇报.pptx` | 开题汇报 | 16 | 每页都带讲稿备注（放映者视图可见） |
| `赶梗潮-结题答辩.pptx` | 结题答辩 | 13 | 同上；第 9 页是「未做实验」的空白面板 |

设计语言沿用你原先的 `docs/pitch/赶梗潮-开题答辩-v2.pptx`：冷白画布 + 白卡片 + 珊瑚红
`#FB3A5E` 主强调 + 藏青 `#3C5989`，标题用 KaiTi，正文 Microsoft YaHei，16:9。

## 需要你自己填的地方

| 位置 | 内容 |
| --- | --- |
| 两份 deck 第 1 页信息卡 | `汇报人` / `学号` / `指导教师` / 日期 |
| 结题答辩第 9 页 | 四块「待补实验」面板里的 `_____`：标注人数、Kappa、排名相关系数、实验人数与准确率 |

第 9 页的面板刻意做成**灰底 + 金色顶条**，一眼能看出是没做完的部分——
不建议在答辩前把它填成结果，除非实验真的跑完了。

## 数字出处（被追问时可当场复核）

| 数字 | 出处 |
| --- | --- |
| 85 条梗记录 / 71 入池 / 35 真实且已核验 / 20 上热榜 | `memes` + `hotness_snapshots` + `lifecycle_snapshots` 按 `query.py` 的闸门复算 |
| 榜首「闪身步」80.4（爆发期，还来得及，置信度 0.95） | `hotness_snapshots` / `lifecycle_snapshots` |
| 5,044 条真实视频；108 条演示视频 | `videos.data_source` |
| 2,209 行日统计；1,139 行 `observed=1`；2026-08-28 ~ 09-28 | `meme_daily_stats` |
| 平均观测覆盖度 55.3% | `hotness_snapshots.metrics.coverage` 均值 |
| 阶段分布：数据不足 33 / 退潮 12 / 萌芽 9 / 上升 8 / 平稳 4 / 过气 3 / 爆发 2 | `lifecycle_snapshots` |
| 核验状态：8 双 UP / 38 单 UP / 39 未核验 | `memes.verification_state` |
| 1,150 条视频带站内名次，61 个梗有排名 | `videos.search_rank` |
| Pearson r = +0.40 (p = 0.028)、Spearman ρ = +0.29 (p = 0.12)、R² ≈ 0.16、n = 31 | `docs/research/开题报告.md` 第 6 节；脚本 `docs/pitch/facts.json` |
| 252 项后端测试 / 125 项接口冒烟 / 21 项小程序测试 | `python -m pytest --collect-only`、`scripts/smoke_api.py` |
| 69 个后端模块 10,409 行 / 前端 31 文件 4,666 行 | 仓库实测统计 |
| +23,616% 假增长、4 天 3,976 万 → 1 天 18 条、418 条样本 343 条污染 | `docs/research/开题报告.md` 4.7 与 `defense-qa.md` 第 6 问 |

## 重新生成

工具都在 `docs/ppt/tools/`（都从仓库根目录跑）。

```powershell
# 图表：读 backend/data/gengv1.db，输出 docs/ppt/assets/*.png 与 tools/deck_facts.json
python docs\ppt\tools\make_charts.py

# 开题汇报（assemble 先把三段拼成一个完整脚本，再执行）
python docs\ppt\tools\assemble.py ; python docs\ppt\tools\_build_opening.py

# 结题答辩
python docs\ppt\tools\build_defense.py
```

改文案直接改 `tools/build_proposal_[abc].py`（开题三段）与
`tools/_defense_p[123].py`（结题三段），然后重跑上面的命令。
`tools/gstyle.py` 是共用的设计系统（配色、字号、卡片、页眉页脚）。

> ⚠️ 顺序有讲究：**先跑 `make_charts.py`，再重建 deck**。
> 图表里的阶段分布、漏斗数、榜首曲线都是生成时从库里读的快照，
> 算法改动后必须先重算快照（`cd backend; python -m app.scripts.run_pipeline`），
> 否则 deck 上的数字会跟界面不一致。

## 自检工具

```powershell
# 文字是否溢出文本框（按真实 PowerPoint 中文字宽模型计算）
python docs\ppt\tools\audit.py docs\ppt\赶梗潮-开题汇报.pptx docs\ppt\赶梗潮-结题答辩.pptx

# 是否有元素超出页面/页边距
python docs\ppt\tools\bounds.py docs\ppt\赶梗潮-开题汇报.pptx docs\ppt\赶梗潮-结题答辩.pptx
```

两个脚本目前都是 0 问题。**注意**：本机 LibreOffice 预览会把所有字体替换成同一个
后备字体，中文宽度约为真实值的 1.7 倍，所以预览图右侧看起来会「出框」——
那是预览环境的问题，实际 PowerPoint（有微软雅黑/楷体）不会。上面两个脚本用的是
真实中文字宽模型，判据以它们为准。

## 导出 PDF

```powershell
# 用捆绑的 LibreOffice Kit（node 与 cli 的绝对路径见 office-pptx skill）
& $node $cli convert --input "docs\ppt\赶梗潮-开题汇报.pptx" --output "docs\ppt\赶梗潮-开题汇报.pdf"
```

`convert` 的输出文件**必须不存在**，否则报 `EEXIST`；重导前先删掉旧的 PDF。
