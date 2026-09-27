# 赶梗潮 GengChao

> 今天，赶什么梗？—— 只看 B 站数据，判断一个梗正在起飞、爆发、退潮，还是已经过气。

一个只分析 **Bilibili 网络梗** 热度与生命周期的 Web 数据产品。

```
B站数据 → 采集 → 清洗 → 梗匹配 → 双UP认证 → 时间序列聚合 → 热度指数 → 生命周期 → LongCat 解释 → FastAPI → React
```

分工原则：**数据负责证明，算法负责判断，LongCat 负责解释，UI 负责呈现。**

## 目录结构

```
backend/
  app/
    api/         # FastAPI 路由
    models/      # SQLAlchemy 数据模型（含双UP认证）
    schemas/     # Pydantic 出入参
    services/
      llm/       # LongCat 客户端 / 配置 / 业务封装 + 缓存
      meme/      # 梗认证与查询服务
    analytics/   # 相关性过滤 / 聚合 / 热度指数 / 生命周期 / 赶梗判断
    collectors/  # B站采集（默认 Mock，可切真实数据）
    prompts/     # LLM 提示词（不硬编码进组件）
    config/      # 运行配置 + 算法阈值 + 日志
    mock/        # 演示数据生成
  tests/
frontend/        # React + TS + Vite + Tailwind + ECharts
docs/            # 产品/设计提示词与 UI 参考图
```

## 快速开始

### 1. 后端

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env          # 需要真实 LLM 时填 LLM_API_KEY
python -m app.scripts.seed_data   # 生成演示数据
uvicorn app.main:app --reload --port 8000
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

## 数据说明

- 默认 `DATA_SOURCE=mock`，页面会明确标注 **演示数据**，不会伪装成实时 B 站数据。
- 只有 **梗百科 + 梗指南** 两个 UP 主都独立发视频介绍过的梗，才会进入正式梗库（`certified = encyclopedia_confirmed AND guide_confirmed`）。
- 热度指数（0-100）与生命周期（🌱📈🌊📉）全部由后端算法计算，LLM 不参与数值判断、不做未来预测。
- LongCat 未配置或调用失败时，热度、生命周期、图表、数据照常展示，AI 文案位置显示降级提示。

## 测试

```bash
cd backend && python -m pytest -q
```
