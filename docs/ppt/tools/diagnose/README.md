# 采集诊断脚本

用来判断「拿不到数据」到底是平台的限制、还是我们自己的问题。
起因：库里 1070 行 `observed=0`，分不清是「当天真没人做这个梗」还是「被限流吞了」。

## 结论先说

B 站搜索的「没有结果」有三种返回，长得完全不一样：

| 情况 | 返回体 | 含义 |
| --- | --- | --- |
| 有结果 | `{"result": [...20条], "numResults": 682, "numPages": 35}` | 正常 |
| 真的没内容 | `{"result": [], "numResults": 0, "numPages": 0}` | **可信**：当天确实没有 |
| 被限流吞掉 | `{"v_voucher": "voucher_xxxx"}` | **不可信**：这次没给我 |

第三种是风控应答：HTTP 200、没有错误码、结果被整个拿掉。
实测搜「动画」这种绝对有内容的词也会被这样吞掉。

**限流是会话级的累积状态**，实测（匿名 + 设备指纹）：

* 冷启动命中率 ~98%
* 连续打几百次之后掉到 **0~30%**
* 完全停手静默约 **5 分钟**恢复（实测 t=305s 恢复到 3/3）

间隔的影响远小于会话状态的影响，所以「拉长间隔」不是主要解法：

| 请求间隔 | 命中率 |
| --- | --- |
| 2 秒 | ~17% |
| 20 秒 | ~33% |
| 1.2 秒 | ~73% |

处方是**退避 + 提前停**（见 `collect_throttle_backoff_factor` /
`collect_throttle_stop_after`），而不是单纯放慢。

## 脚本

都需要从**仓库根目录**跑。

| 脚本 | 用途 |
| --- | --- |
| `probe_search.py` | 搜一个梗：综合排序 / 播放量排序 / 逐日区间，看能拿到什么 |
| `diag_payload.py` | **看原始返回体**，区分 v_voucher 与真空返回（排查第一步） |
| `diag_e2e.py` | 端到端：跑 5 个梗 × 30 天真实采集，统计实际观测覆盖率 |
| `diag_recover.py` | 测限流恢复时间：静默后每隔一段时间试 3 次 |
| `rollback_meme.py` | 只回滚**单只梗**的采集数据到某个备份的状态 |

```powershell
# 先看返回体，确认是不是被限流
python docs\ppt\tools\diagnose\diag_payload.py

# 端到端测覆盖率（约 15 分钟，会真实打接口）
python docs\ppt\tools\diagnose\diag_e2e.py

# 排查性采集改到了库，只回滚那一只梗
python docs\ppt\tools\diagnose\rollback_meme.py --from backend\data\某备份.db --name 琵琶曲
python docs\ppt\tools\diagnose\rollback_meme.py --from ... --name 琵琶曲 --apply
# 回滚后必须重算，否则结论与数据不一致：
cd backend; python -m app.scripts.run_pipeline
```

## 注意

* 这些脚本会**真实请求 B 站**，密集跑会把当前会话打进限流状态
  （自己把自己测成 0% 是很容易发生的）。测完最好静默几分钟。
* `rollback_meme.py` 只动 `meme_daily_stats` 与 `videos` 两张表里该梗的行，
  快照表留给 `run_pipeline` 重算，避免出现「数据是新的、结论是旧的」。
* 覆盖率的逐次波动是正常的（会话状态不同），别把单次结果当结论。
