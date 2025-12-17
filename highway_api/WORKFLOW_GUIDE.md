# LangGraph工作流使用指南

## 🎯 Person 1 + Person 3 完成内容

### ✅ 已实现功能

1. **3个业务场景的LangGraph编排**
2. **增强型Agent自动决策调用**
3. **完整的API接口集成**

---

## 📦 安装依赖

```bash
cd highway_api
pip install -r requirements.txt
```

新增依赖：
- langgraph>=0.2.0
- langchain>=0.3.0
- langchain-openai>=0.2.0

---

## 🚀 快速开始

### 1. 启动服务

```bash
python app.py
```

服务将在 `http://localhost:5000` 启动。

### 2. 测试工作流

#### 方式1: 直接调用工作流API

```bash
# 场景1: 跨路段通行费核算
curl -X POST http://localhost:5000/api/workflow/execute \
  -H "Content-Type: application/json" \
  -d '{
    "scenario": "scenario1",
    "params": {
      "start_date": "2023-01-03"
    }
  }'

# 场景2: 异常交易稽核
curl -X POST http://localhost:5000/api/workflow/execute \
  -H "Content-Type: application/json" \
  -d '{
    "scenario": "scenario2",
    "params": {
      "start_date": "2023-01-03",
      "limit": 20,
      "synthetic_count": 10
    }
  }'

# 场景3: 全网流量分析
curl -X POST http://localhost:5000/api/workflow/execute \
  -H "Content-Type: application/json" \
  -d '{
    "scenario": "scenario3",
    "params": {
      "start_date": "2023-01-03",
      "end_date": "2023-01-10"
    }
  }'
```

#### 方式2: 使用增强型Agent（推荐）

```bash
# Agent自动识别场景并执行
curl -X POST http://localhost:5000/api/agent/smart-query \
  -H "Content-Type: application/json" \
  -d '{"query": "帮我核算2023年1月3号的通行费用"}'

curl -X POST http://localhost:5000/api/agent/smart-query \
  -H "Content-Type: application/json" \
  -d '{"query": "检测一下最近的异常交易"}'

curl -X POST http://localhost:5000/api/agent/smart-query \
  -H "Content-Type: application/json" \
  -d '{"query": "分析全网的流量情况"}'
```

---

## 📋 3个业务场景详解

### 场景1: 跨路段通行费核算

**业务价值**: 联网收费结算，跨路段费用核算

**涉及主体**: 
- 入口收费站
- 出口收费站
- 结算中心

**API调用流程**:
1. `GET /api/transactions/entrance` - 获取入口交易
2. `GET /api/transactions/exit` - 获取出口交易
3. 计算费用差异和优惠金额

**参数**:
```json
{
  "start_date": "2023-01-03",
  "vehicle_id": "粤A12345" (可选)
}
```

**返回示例**:
```json
{
  "success": true,
  "scenario": "scenario1",
  "result": {
    "scenario": "跨路段通行费核算",
    "entrance_count": 10,
    "exit_count": 10,
    "total_toll_money": 300.50,
    "total_real_money": 285.45,
    "discount_amount": 15.05,
    "average_fee": 28.55
  }
}
```

---

### 场景2: 异常交易稽核

**业务价值**: 交易监管，异常检测，风险控制

**涉及主体**:
- 监管部门
- 收费站
- DGM数据生成系统

**API调用流程**:
1. `GET /api/transactions/exit` - 获取真实交易
2. `GET /api/generate/gantry?method=dgm` - 生成对比数据
3. 统计分析检测异常（超过2个标准差）

**参数**:
```json
{
  "start_date": "2023-01-03",
  "limit": 20,
  "synthetic_count": 10
}
```

**返回示例**:
```json
{
  "success": true,
  "scenario": "scenario2",
  "result": {
    "scenario": "异常交易稽核",
    "total_checked": 20,
    "anomaly_count": 3,
    "anomaly_rate": 15.0,
    "anomalies": [
      {
        "transaction_id": "G561...",
        "fee": 150.50,
        "deviation": 80.23,
        "reason": "费用异常"
      }
    ],
    "statistics": {
      "avg_fee": 30.25,
      "std_fee": 12.50,
      "threshold": 25.0
    }
  }
}
```

---

### 场景3: 全网流量分析

**业务价值**: 宏观调度，资源规划，态势感知

**涉及主体**:
- 路网运营中心
- 各路段管理处
- 调度指挥中心

**API调用流程**:
1. `GET /api/sections` - 获取所有路段
2. `GET /api/statistics/traffic-flow` - 逐路段统计流量
3. 聚合分析，识别繁忙路段

**参数**:
```json
{
  "start_date": "2023-01-03",
  "end_date": "2023-01-10"
}
```

**返回示例**:
```json
{
  "success": true,
  "scenario": "scenario3",
  "result": {
    "scenario": "全网流量分析",
    "total_sections": 3,
    "total_flow": 15000,
    "busiest_section": {
      "section_id": "G5615530120",
      "section_name": "河段",
      "total_flow": 8000,
      "daily_avg": 1142.86
    },
    "section_summary": [...]
  }
}
```

---

## 🤖 增强型Agent使用

### Agent工作原理

```
用户自然语言查询
    ↓
LLM分析查询意图
    ↓
判断：简单查询 or 复杂场景？
    ↓                    ↓
推荐API接口        执行LangGraph工作流
```

### 关键词触发规则

- **"核算"、"费用计算"、"收费结算"** → 场景1
- **"异常"、"稽核"、"检测"、"对比"** → 场景2
- **"全网"、"所有路段"、"整体分析"** → 场景3
- 其他简单查询 → 推荐API

### 测试示例

```python
# Python示例
import requests

# 测试1: 自动识别场景1
response = requests.post(
    'http://localhost:5000/api/agent/smart-query',
    json={'query': '帮我核算一下通行费'}
)
print(response.json())

# 测试2: 自动识别场景2
response = requests.post(
    'http://localhost:5000/api/agent/smart-query',
    json={'query': '检测异常交易'}
)
print(response.json())

# 测试3: 简单查询
response = requests.post(
    'http://localhost:5000/api/agent/smart-query',
    json={'query': '查询路段信息'}
)
print(response.json())
```

---

## 📊 API接口汇总

### 工作流相关

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/workflow/execute` | POST | 执行指定工作流 |
| `/api/workflow/scenarios` | GET | 获取所有场景信息 |
| `/api/workflow/scenarios?scenario=scenario1` | GET | 获取单个场景信息 |

### Agent相关

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/agent/query` | POST | 原版Agent（API推荐） |
| `/api/agent/smart-query` | POST | 增强Agent（自动编排） |

---

## 🧪 独立测试脚本

### 测试LangGraph工作流

```bash
# 直接运行工作流模块
cd highway_api
python langgraph_workflows.py
```

这将依次测试3个场景。

### 测试增强Agent

```bash
# 直接运行Agent模块
python enhanced_agent.py
```

这将测试不同类型的查询。

---

## 🎨 前端集成示例

```javascript
// JavaScript示例：调用智能Agent
async function queryAgent(userInput) {
  const response = await fetch('http://localhost:5000/api/agent/smart-query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: userInput })
  });
  
  const result = await response.json();
  
  if (result.execution_type === 'workflow') {
    // 执行了工作流
    console.log('场景:', result.scenario_name);
    console.log('结果:', result.result);
    console.log('日志:', result.execution_logs);
  } else {
    // 推荐了API
    console.log('推荐API:', result.recommendations);
  }
}

// 使用示例
queryAgent('帮我核算通行费');
```

---

## ⚡ 性能说明

- **场景1执行时间**: ~2-3秒（2个API调用）
- **场景2执行时间**: ~5-8秒（含DGM数据生成）
- **场景3执行时间**: ~3-5秒（多路段查询）
- **Agent分析时间**: ~1-2秒（LLM调用）

---

## 🐛 故障排查

### 1. LangGraph导入失败

```bash
pip install langgraph langchain langchain-openai
```

### 2. API连接超时

检查`config.py`中的`OPENAI_API_KEY`和`OPENAI_API_BASE`配置。

### 3. 数据库连接失败

确保MySQL/SQLite数据库正常运行，检查`config.py`中的数据库配置。

### 4. 工作流执行失败

查看返回的`execution_logs`字段，定位具体失败步骤。

---

## 📝 扩展开发

### 添加新场景

1. 在`langgraph_workflows.py`中定义新的节点函数
2. 使用`StateGraph`构建工作流
3. 在`WorkflowExecutor`中注册新场景
4. 更新场景描述信息

### 扩展Agent能力

1. 在`enhanced_agent.py`的`_analyze_query`中添加新的场景识别逻辑
2. 更新system prompt添加新场景说明
3. 实现对应的工作流

---

## ✅ Person 1 + Person 3 交付清单

- [x] LangGraph工作流模块 (`langgraph_workflows.py`)
- [x] 3个业务场景实现（场景1、2、3）
- [x] 增强型Agent (`enhanced_agent.py`)
- [x] Flask API集成
- [x] 测试脚本
- [x] 使用文档

---

## 🚀 下一步

Person 4（前端）和Person 5（审计+集成）可以基于以下接口开始开发：

- `POST /api/workflow/execute` - 执行工作流
- `GET /api/workflow/scenarios` - 获取场景信息
- `POST /api/agent/smart-query` - 智能Agent入口

**演示时推荐流程**：
1. 展示简单查询（推荐API）
2. 展示复杂场景（自动执行工作流）
3. 对比3个场景的执行结果
4. 展示执行日志的可追溯性

---

**版本**: v1.0  
**完成时间**: 2025-12-17  
**负责人**: Person 1 + Person 3
