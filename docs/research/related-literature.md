# 赶梗潮 · 开题相关文献（全部逐条核验过）

核验时间：2026-09-28。核验方式：**Crossref REST API 解析 DOI**（英文期刊/会议论文）、
**CNKI 期刊门户页面**、**期刊官网落地页的 citation_\* 元数据**、**论文 PDF 首页原文**。
每条后面标注了核验来源与 DOI/链接；**核不到的文献一律不列**，
放在最后一节"没核到，别直接引用"里说明原因。

复现：`python scripts/fetch_literature.py > docs/research/literature-raw.txt`
（原始 JSON 输出也留在那份文件里，可逐条对账）

---

## 一、模因 / 网络梗：概念与研究传统

| # | 文献 | 对接本项目的哪一块 | 核验 |
| --- | --- | --- | --- |
| 1 | DAWKINS R. The Selfish Gene[M]. Oxford: Oxford University Press, 1976. | "meme（模因）"一词的出处：文化信息单元靠**模仿与复制**扩散，本项目把"梗"当作可观测的复制单元来度量 | 书目（1976 年图书无 DOI；Crossref 只能查到书评，见文末说明） |
| 2 | SHIFMAN L. An anatomy of a YouTube meme[J]. New Media & Society, 2012, 14(2): 187-203. DOI [10.1177/1461444811412160](https://doi.org/10.1177/1461444811412160) | 给出"一个梗 = 一组相互模仿的变体"的可操作定义，支撑本项目"同一梗名/别名归并"的相关性判定 | Crossref |
| 3 | SHIFMAN L. Memes in Digital Culture[M]. Cambridge: MIT Press, 2013. 章节 DOI [10.7551/mitpress/9429.003.0012](https://doi.org/10.7551/mitpress/9429.003.0012) | 互联网模因的三种传播模式与"参与式文化"框架；本书结尾列出的研究缺口正是本项目要做的"量化生命周期" | Crossref（章节） |
| 4 | BAUCKHAGE C. Insights into Internet Memes[C]// Proceedings of the International AAAI Conference on Web and Social Media, 2011, 5(1): 42-49. DOI [10.1609/icwsm.v5i1.14097](https://doi.org/10.1609/icwsm.v5i1.14097) | **最直接相关**：用搜索/YouTube 时间序列刻画单个梗的流行曲线，指出热度分布近似对数正态、且"梗的寿命有限"——本项目对数区间归一与阶段划分可引此文 | Crossref（注：Crossref 登记年份 2021 是会议论文重上线时间，正文为 ICWSM 2011） |
| 5 | WARD M R. Internet Meme Marketing over the Fad Cycle[J]. Journal of Interactive Marketing, 2026, 61(1): 25-40（2025 在线）. DOI [10.1177/10949968251320612](https://doi.org/10.1177/10949968251320612) | 把"梗"放进 **fad cycle（风潮周期）** 里讨论品牌跟风时机——与本项目"现在赶还来得及吗"是同一个问题的营销学版本 | Crossref |
| 6 | RAZZA A, RAFIQ M, BALEANU D, et al. Numerical simulations for stochastic meme epidemic model[J]. Advances in Difference Equations, 2020, 2020(1). DOI [10.1186/s13662-020-02593-1](https://doi.org/10.1186/s13662-020-02593-1) | 用**传染病模型（SIR 族）**给梗的传播建微分方程，可作为"为什么过气梗热度会归零"的机理性引文 | Crossref |
| 7 | 谢朝群, 何自然. 语言模因说略[J]. 现代外语, 2007(1): 30-39, 108-109. [CNKI 期刊页](https://xdwy.cbpt.cnki.net/portal/journal/portal/client/paper/b18bab169a63fb2d18ddfb9dd242b76b) | 中文模因论的奠基文献：把"梗"这类语言复制现象界定为**基因型/表现型模因**，为"同一梗的不同写法应归并"提供理论依据 | CNKI 页面 |
| 8 | 薛一飞. 网络热梗背后的青年群体社会心态探析[J]. 人民论坛, 2024-10-16(06 版). [原文](https://paper.people.com.cn/rmlt/pc/content/202410/16/content_30030026.html) | 中文语境下"热梗"的社会心态解释，可用于开题的研究意义（为什么值得做给年轻人看的产品） | 期刊官网落地页 |

## 二、集体注意力与生命周期（对应"六阶段"和"还剩多久"）

| # | 文献 | 对接本项目的哪一块 | 核验 |
| --- | --- | --- | --- |
| 9 | DOWNS A. Up and down with ecology: the "issue-attention cycle"[J]. The Public Interest, 1972(28): 38-50. [原文 PDF](https://gwern.net/doc/sociology/1972-downs.pdf)｜[出版方页](https://nationalaffairs.com/public_interest/detail/up-and-down-with-ecologythe-issue-attention-cycle) | **议题注意力周期**五阶段模型：本项目"萌芽→爆发→退潮→过气"的思想源头，开题时用来论证阶段划分的合法性 | 原文 PDF + 出版方页面 |
| 10 | CRANE R, SORNETTE D. Robust dynamic classes revealed by measuring the response function of a social system[J]. PNAS, 2008, 105(41): 15649-15653. DOI [10.1073/pnas.0803685105](https://doi.org/10.1073/pnas.0803685105) | 用亚马逊书单销量证明**在线注意力存在少数几种可复用的脉冲响应形状**（本项目的 6 条生命周期原型曲线正是这一思路的工程化） | Crossref |
| 11 | KLEINBERG J. Bursty and hierarchical structure in streams[C]// KDD 2002: 91-101. DOI [10.1145/775047.775061](https://doi.org/10.1145/775047.775061) | **突发检测（burst detection）**：从时间序列里自动识别"某词突然被大量使用"，对应本项目的发现层与"上升期"判定 | Crossref |
| 12 | LORENZ-SPREEN P, MØNSTED B M, HÖVEL P, LEHMANN S. Accelerating dynamics of collective attention[J]. Nature Communications, 2019, 10(1). DOI [10.1038/s41467-019-09311-w](https://doi.org/10.1038/s41467-019-09311-w) | 实证结论：**集体注意力的半衰期在系统性地缩短**——这就是"梗平均只有两三周"的依据，也是本项目"赶梗窗口"存在的前提 | Crossref |
| 13 | YANG J, LESKOVEC J. Patterns of temporal variation in online media[C]// WSDM 2011: 177-186. DOI [10.1145/1935826.1935863](https://doi.org/10.1145/1935826.1935863) | 把新闻/话题的时间曲线聚成若干**响应形状类别**，是"生命周期分型"的标准引文 | Crossref |
| 14 | LIN C X, ZHAO B, MEI Q, HAN J. PET: a statistical model for popular events tracking in social contexts[C]// KDD 2010: 929-938. DOI [10.1145/1835804.1835922](https://doi.org/10.1145/1835804.1835922) | 在社交平台上**持续追踪热点事件**的统计模型，对应本项目的逐日采集 + 快照更新机制 | Crossref |
| 15 | 宋宁, 刘婵君. 过程与要素视角下的突发事件网络舆情演化规律研究综述[J]. 图书情报工作, 2016, 60(15). DOI [10.13266/j.issn.0252-3116.2016.15.019](https://www.lis.ac.cn/CN/article/downloadArticleFile.do?attachType=PDF&id=21080) | 中文文献里明确把舆情演化分成**形成期 / 发展期 / 消弭期**并讨论"关键节点"，可与本项目六阶段做对照 | 论文 PDF 首页（卷期、DOI、作者、单位均在原文中） |
| 16 | 史伟, 薛广聪, 何绍义. 情感视角下的网络舆情研究综述[J]. 图书情报知识, 2022(1): 105 起. DOI [10.13366/j.dik.2022.01.105](http://dik.whu.edu.cn/jwk3/tsqbzs/CN/10.13366/j.dik.2022.01.105) | 综述了舆情的**情感演化与预测**，为本项目"讨论量/弹幕/评论"这类互动因子提供依据 | 期刊官网落地页 + PDF |

## 三、流行度量化与预测（对应热度指数与赶梗判断）

| # | 文献 | 对接本项目的哪一块 | 核验 |
| --- | --- | --- | --- |
| 17 | SZABO G, HUBERMAN B A. Predicting the popularity of online content[J]. Communications of the ACM, 2010, 53(8): 80-88. DOI [10.1145/1787234.1787254](https://doi.org/10.1145/1787234.1787254) | 经典结论：Digg/YouTube 上的流行度服从幂律、**早期增速可预测最终热度**——本项目"增长权重 0.25"的实证依据 | Crossref |
| 18 | JENDERS M, KASNECI G, NAUMANN F. Analyzing and predicting viral tweets[C]// WWW 2013 Companion: 657-664. DOI [10.1145/2487788.2488017](https://doi.org/10.1145/2487788.2488017) | 转发级联的**流行度预测**方法，可对照本项目"头部 20 条样本"的抽样口径 | Crossref |
| 19 | LI H, MA X, WANG F, LIU J, XU K. On popularity prediction of videos shared in online social networks[C]// CIKM 2013: 169-178. DOI [10.1145/2505515.2505523](https://doi.org/10.1145/2505515.2505523) | **视频**流行度预测（含社交传播特征），与 B 站视频粒度的数据最贴近 | Crossref |
| 20 | TAN Z, ZHANG Y, LI C, LIU N. Lifetime popularity prediction for online videos[C]// BMSB 2014: 1-6. DOI [10.1109/BMSB.2014.6873564](https://doi.org/10.1109/bmsb.2014.6873564) | 直接研究视频热度的**寿命（lifetime）**，即"还能热多久"，与赶梗判断同题 | Crossref |
| 21 | LI C, LIU J, OUYANG S. Characterizing and predicting the popularity of online videos[J]. IEEE Access, 2016, 4: 1630-1641. DOI [10.1109/ACCESS.2016.2552218](https://doi.org/10.1109/access.2016.2552218) | 大规模视频热度特征刻画（播放增长曲线、上传后早期表现），可支撑本项目"样本过小不外推"的规则 | Crossref |
| 22 | ZHOU F, XU X, TRAJCEVSKI G, ZHANG K. A survey of information cascade analysis: models, foundations and applications[J]. ACM Computing Surveys, 2021, 54(2): 1-36. DOI [10.1145/3433000](https://doi.org/10.1145/3433000) | 信息级联研究的**综述**，开题"国内外研究现状"一节可用作全景引文 | Crossref |
| 23 | XU Y, WU J, WAN H, LI Y, HOU Z, KAN M Y. Forecasting the buzz: enriching hashtag popularity prediction with LLM reasoning[C]// CIKM 2025: 5396-5400. DOI [10.1145/3746252.3760970](https://doi.org/10.1145/3746252.3760970) | 2025 年最新工作：**LLM 只做推理辅助、数值预测仍由模型给出**，与本项目"LLM 不参与计算"的边界设计正好互相印证 | Crossref |
| 24 | 沈婕, 等. 网络舆情态势及情感多维特征分析与可视化——以 COVID-19 疫情为例[J]. 地球信息科学学报, 2021, 23(2): 318-330. DOI [10.12082/dqxxkx.2021.200268](https://www.dqxxkx.cn/CN/10.12082/dqxxkx.2021.200268) | 中文的**舆情热度态势 + 可视化**方法，可作为"数据产品怎么呈现热度"的对照 | 期刊官网 citation 元数据 |
| 25 | 汪明, 等. 基于改进 SEIQR 模型的网络舆情传播建模与仿真研究[J]. 知识管理论坛, 2026, 11(4): 381-399. DOI [10.13266/j.issn.2095-5472.2026.032](https://www.kmf.ac.cn/CN/10.13266/j.issn.2095-5472.2026.032) | 中文的舆情**传播动力学建模**（SEIQR），可放进"生命周期机理"一节 | 期刊官网 citation 元数据 |

## 四、B 站与弹幕的既有研究（平台侧）

| # | 文献 | 对接本项目的哪一块 | 核验 |
| --- | --- | --- | --- |
| 26 | ZHANG L T, CASSANY D. Making sense of danmu: Coherence in massive anonymous chats on Bilibili.com[J]. Discourse Studies, 2020, 22(4): 483-502. DOI [10.1177/1461445620940051](https://doi.org/10.1177/1461445620940051) | 以 B 站为对象的大规模弹幕研究：说明弹幕是**梗的主要载体**，本项目把弹幕计入互动因子有据可依 | Crossref |
| 27 | WANG R. Community-building on Bilibili: The social impact of danmu comments[J]. Media and Communication, 2022, 10(2): 54-65. DOI [10.17645/mac.v10i2.4996](https://doi.org/10.17645/mac.v10i2.4996) | B 站弹幕与社区认同：支撑"为什么年轻人需要知道自己落下了哪个梗" | Crossref |
| 28 | 闫方洁. 媒介文化研究视角下"弹幕"的生成机制及其亚文化意义[J]. 思想理论教育, 2017(10): 81-85. [原文 PDF](https://mks.ecnu.edu.cn/_upload/article/files/04/97/ab876468417c91d7607e007819fa/c90c106b-acb9-4589-9fb6-3b92ffeb6b58.pdf) | 明确写清弹幕经 A 站、B 站引入国内的路径，以及"戏仿/拼贴/挪用"的造梗方式——是"梗怎么被生产出来"的中文质性研究 | PDF 首页（含文章编号 1007-192X(2017)10-0081-05） |
| 29 | 曾一果. 弹幕背后青年群体的情感需要与价值诉求[J]. 人民论坛, 2021(4 上期). [原文](https://paper.people.com.cn/rmlt/html/2021-04/01/content_25887106.htm) | 弹幕的情感动机分析，可用于产品定位（用户为什么要"赶上"一个梗） | 期刊官网落地页 |

---

## 五、这些文献留给本项目的缺口（开题的"创新点"就写在这里）

1. **研究对象的错位。** 传播学/文化研究一侧（#2、#3、#7、#8、#26-29）把梗当文本与亚文化来解读，几乎不给出可复算的时间度量；
   计算机一侧（#10、#13、#17-23）度量的是**新闻、话题标签、单条视频**，而不是"梗"这一跨视频、跨创作者的聚合对象。
2. **中文短视频平台的量化工作稀缺。** #4、#15、#24 分别做了梗的曲线、舆情阶段、舆情热度可视化，
   但没有一项把 B 站的梗做成"逐日采集 → 热度指数 → 阶段判定 → 赶梗时机"的完整闭环。
3. **本项目的落点。** 以两位解说 UP 主的真实投稿作为梗的**存在性证明**（并集准入、90 天滚动窗口），
   用每日头部相关视频构造可比的热度指数（对数区间归一 + 五因子），再用规则引擎输出阶段与赶梗三态，
   并且把口径与数据新鲜度直接显示在产品上——这三件事在现有文献里是分散在不同学科的，本项目把它们接成一条链路。

## 六、没核到，别直接引用

| 常被提到的文献 | 情况 |
| --- | --- |
| ADAR E 等. Modeling the evolution of Internet topics（WWW 2004） | Crossref 标题精搜被同名噪声占位、ACM DL 链接未取到，**卷期页码无法确认**。要用的话请在 scholar.google.com 或 ACM DL 手工核对后再写。 |
| CHENG S 等. Memetracker（ICWSM 2020） | 只找到引用它的二手文献（如 #22 相关综述），未拿到原始条目页，**暂不列入**。 |
| ARIF A A 等. The Meme Machine: A Review of Online Meme Studies（Frontiers in Communication, 2022） | Crossref 命中的是 1999 年同名书评，**未核验到该综述本身**，需要时去 Frontiers 官网确认。 |
| GAGNON M 等. You call this a meme? A taxonomy of internet memes（WebSci 2019） | 同上，未取到条目页。 |
| DAWKINS 1976 原书 | 图书无 DOI，Crossref 只有书评；引用时按图书馆目录/WorldCat 核对版次与 ISBN。 |

> 说明：这份表里所有英文条目都由 Crossref 直接解析 DOI 得到标题、作者、刊名、年卷期页；
> 中文条目由 CNKI 期刊门户、期刊官网 citation 元数据或论文 PDF 首页取得。
> 页码缺失的（#15、#16）是因为源页面只给起始页或在线优先发布，DOI 落地页可补全。
