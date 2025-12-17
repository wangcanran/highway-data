# 高速公路数据API使用指南

## 📋 目录

- [概述](#概述)
- [快速开始](#快速开始)
- [智能Agent](#智能agent)
- [API接口详情](#api接口详情)
  - [路段信息](#路段信息)
  - [收费站信息](#收费站信息)
  - [门架信息](#门架信息)
  - [交易记录](#交易记录)
  - [统计分析](#统计分析)
  - [系统状态](#系统状态)
- [响应格式](#响应格式)
- [错误处理](#错误处理)
- [使用示例](#使用示例)

---

## 概述

高速公路数据API服务提供了完整的高速公路收费系统数据访问接口，包括：

- 🛣️ **路段信息**：高速公路路段基础数据
- 🏢 **收费站信息**：收费站详细信息和位置数据
- 🚪 **门架信息**：ETC门架相关信息
- 📄 **交易记录**：入口、出口、门架交易流水
- 📊 **统计分析**：交通流量、收费统计、车型分布等
- 🤖 **智能Agent**：自然语言查询，智能推荐API

### 基础信息

- **基础URL**: `http://localhost:5000`
- **数据格式**: JSON
- **字符编码**: UTF-8
- **CORS**: 已启用，支持跨域请求

---

## 快速开始

### 安装依赖

```bash
cd highway_api
pip install -r requirements.txt
```

### 启动服务

```bash
python app.py
```

服务将在 `http://localhost:5000` 启动。

### 第一个API请求

```bash
# 获取所有路段信息
curl http://localhost:5000/api/sections

# 健康检查
curl http://localhost:5000/api/health
```

---

## 智能Agent

### 概述

智能Agent可以理解您的自然语言描述，自动推荐最合适的API接口。

### 使用方法

**接口地址**: `POST /api/agent/query`

**请求示例**:

```bash
curl -X POST http://localhost:5000/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{"query": "我想查询2023年1月的交易记录"}'
```

**请求参数**:

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| query | string | 是 | 自然语言描述的需求 |

**响应示例**:

```json
{
  "understood": true,
  "query": "我想查询2023年1月的交易记录",
  "matched_categories": ["transactions"],
  "explanation": "根据您的需求，我为您找到了3个相关API接口...",
  "recommendations": [
    {
      "api_name": "获取入口交易记录",
      "endpoint": "/api/transactions/entrance",
      "method": "GET",
      "full_url": "http://localhost:5000/api/transactions/entrance",
      "example_url": "http://localhost:5000/api/transactions/entrance?start_date=2023-01-01&limit=10",
      "parameters": [...],
      "response_example": {...}
    }
  ],
  "total_apis": 3
}
```

### 查询示例

- "查询所有路段信息"
- "获取2023年1月的交易记录"
- "统计交通流量"
- "查询某个收费站的信息"
- "分析车型分布情况"
- "获取某个门架的交易数据"

---

## API接口详情

### 路段信息

#### 1. 获取所有路段

**接口**: `GET /api/sections`

**说明**: 获取数据库中所有高速公路路段信息

**请求示例**:
```bash
curl http://localhost:5000/api/sections
```

**响应示例**:
```json
{
  "success": true,
  "data": [
    {
      "section_id": "G5615530120",
      "section_name": "河段"
    }
  ],
  "count": 8
}
```

#### 2. 获取指定路段

**接口**: `GET /api/sections/{section_id}`

**参数**:
| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| section_id | string | 是 | 路段ID（路径参数） |

**请求示例**:
```bash
curl http://localhost:5000/api/sections/G5615530120
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "section_id": "G5615530120",
    "section_name": "河段"
  }
}
```

---

### 收费站信息

#### 1. 获取收费站列表

**接口**: `GET /api/toll-stations`

**参数**:
| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| section_id | string | 否 | 按路段筛选 |
| station_type | string | 否 | 按站点类型筛选 |

**请求示例**:
```bash
# 获取所有收费站
curl http://localhost:5000/api/toll-stations

# 按路段筛选
curl "http://localhost:5000/api/toll-stations?section_id=G5615530120"
```

**响应示例**:
```json
{
  "success": true,
  "data": [
    {
      "toll_station_id": "G5615530120010",
      "station_name": "新宝站",
      "section_id": "G5615530120",
      "station_type": "2",
      "operation_status": "1",
      "longitude": "104.69",
      "latitude": "23.17"
    }
  ],
  "count": 10
}
```

#### 2. 获取指定收费站

**接口**: `GET /api/toll-stations/{station_id}`

**参数**:
| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| station_id | string | 是 | 收费站ID（路径参数） |

**请求示例**:
```bash
curl http://localhost:5000/api/toll-stations/G5615530120010
```

---

### 门架信息

#### 1. 获取门架列表

**接口**: `GET /api/gantries`

**参数**:
| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| section_id | string | 否 | 按路段筛选 |
| gantry_type | string | 否 | 按门架类型筛选 |

**请求示例**:
```bash
curl "http://localhost:5000/api/gantries?section_id=G5615530120"
```

**响应示例**:
```json
{
  "success": true,
  "data": [
    {
      "gantry_id": "G561553012000210010",
      "gantry_name": "新宝站-人境站",
      "section_id": "G5615530120",
      "gantry_type": "0",
      "direction": "1"
    }
  ],
  "count": 15
}
```

#### 2. 获取指定门架

**接口**: `GET /api/gantries/{gantry_id}`

---

### 交易记录

#### 1. 获取入口交易记录

**接口**: `GET /api/transactions/entrance`

**参数**:
| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| section_id | string | 否 | 路段ID |
| start_date | string | 否 | 开始日期 (YYYY-MM-DD) |
| end_date | string | 否 | 结束日期 (YYYY-MM-DD) |
| vehicle_class | string | 否 | 车型分类 |
| limit | integer | 否 | 返回记录数，默认100 |
| offset | integer | 否 | 偏移量，默认0 |

**请求示例**:
```bash
curl "http://localhost:5000/api/transactions/entrance?section_id=G5615530120&start_date=2023-01-03&limit=10"
```

**响应示例**:
```json
{
  "success": true,
  "data": [
    {
      "entrance_transaction_id": "G561553012004010100102023010314390098",
      "vehicle_class": "1",
      "entrance_time": "2023-01-03 14:39:32.000000",
      "section_id": "G5615530120",
      "section_name": "河段"
    }
  ],
  "count": 10,
  "total": 22525,
  "limit": 10,
  "offset": 0
}
```

#### 2. 获取出口交易记录

**接口**: `GET /api/transactions/exit`

**参数**: 与入口交易类似

**请求示例**:
```bash
curl "http://localhost:5000/api/transactions/exit?start_date=2023-01-03&limit=10"
```

**响应示例**:
```json
{
  "success": true,
  "data": [
    {
      "exit_transaction_id": "G561553012002020104102023010300330006",
      "vehicle_class": "1",
      "exit_time": "2023-01-03 00:33:06.000000",
      "toll_money": 25.73,
      "real_money": 24.44,
      "section_id": "G5615530120"
    }
  ],
  "count": 10,
  "total": 22525
}
```

#### 3. 获取门架交易记录

**接口**: `GET /api/transactions/gantry`

**参数**:
| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| gantry_id | string | 否 | 门架ID |
| section_id | string | 否 | 路段ID |
| start_date | string | 否 | 开始日期 |
| end_date | string | 否 | 结束日期 |
| limit | integer | 否 | 返回记录数 |
| offset | integer | 否 | 偏移量 |

**请求示例**:
```bash
curl "http://localhost:5000/api/transactions/gantry?section_id=G5615530120&limit=10"
```

---

### 统计分析

#### 1. 交通流量统计

**接口**: `GET /api/statistics/traffic-flow`

**说明**: 按日期和车型分组统计交通流量

**参数**:
| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| section_id | string | 否 | 路段ID |
| start_date | string | 否 | 开始日期 |
| end_date | string | 否 | 结束日期 |

**请求示例**:
```bash
curl "http://localhost:5000/api/statistics/traffic-flow?section_id=G5615530120&start_date=2023-01-01&end_date=2023-01-31"
```

**响应示例**:
```json
{
  "success": true,
  "data": [
    {
      "date": "2023-01-03",
      "count": 500,
      "vehicle_class": "1"
    }
  ],
  "count": 30
}
```

#### 2. 收费统计

**接口**: `GET /api/statistics/revenue`

**说明**: 按日期汇总收费金额

**参数**: 与流量统计类似

**请求示例**:
```bash
curl "http://localhost:5000/api/statistics/revenue?section_id=G5615530120&start_date=2023-01-01"
```

**响应示例**:
```json
{
  "success": true,
  "data": [
    {
      "date": "2023-01-03",
      "transaction_count": 500,
      "total_toll": 15000.50,
      "total_real_money": 14250.45,
      "avg_toll": 30.00
    }
  ],
  "count": 30
}
```

#### 3. 车型分布统计

**接口**: `GET /api/statistics/vehicle-distribution`

**说明**: 统计各车型的数量和占比

**参数**:
| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| section_id | string | 否 | 路段ID |
| start_date | string | 否 | 开始日期 |
| end_date | string | 否 | 结束日期 |

**请求示例**:
```bash
curl "http://localhost:5000/api/statistics/vehicle-distribution?section_id=G5615530120"
```

**响应示例**:
```json
{
  "success": true,
  "data": [
    {
      "vehicle_class": "1",
      "count": 15000,
      "percentage": 66.67
    },
    {
      "vehicle_class": "16",
      "count": 5000,
      "percentage": 22.22
    }
  ],
  "count": 5
}
```

---

### 系统状态

#### 健康检查

**接口**: `GET /api/health`

**说明**: 检查服务和数据库连接状态

**请求示例**:
```bash
curl http://localhost:5000/api/health
```

**响应示例**:
```json
{
  "success": true,
  "status": "healthy",
  "database": "connected",
  "sections_count": 8
}
```

---

## 响应格式

### 成功响应

```json
{
  "success": true,
  "data": [...],
  "count": 10
}
```

### 分页响应

```json
{
  "success": true,
  "data": [...],
  "count": 10,
  "total": 100,
  "limit": 10,
  "offset": 0
}
```

### 错误响应

```json
{
  "success": false,
  "error": "错误信息描述"
}
```

---

## 错误处理

### HTTP状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

### 常见错误

1. **路段不存在**
```json
{
  "success": false,
  "error": "路段不存在"
}
```

2. **参数缺失**
```json
{
  "success": false,
  "error": "请提供查询描述"
}
```

---

## 使用示例

### Python 示例

```python
import requests

base_url = "http://localhost:5000"

# 1. 使用Agent查询
response = requests.post(
    f"{base_url}/api/agent/query",
    json={"query": "查询2023年1月的交易记录"}
)
result = response.json()
print(result['explanation'])

# 2. 获取路段信息
response = requests.get(f"{base_url}/api/sections")
sections = response.json()['data']

# 3. 获取交易记录（分页）
params = {
    'section_id': 'G5615530120',
    'start_date': '2023-01-03',
    'limit': 100,
    'offset': 0
}
response = requests.get(
    f"{base_url}/api/transactions/entrance",
    params=params
)
transactions = response.json()['data']

# 4. 统计分析
response = requests.get(
    f"{base_url}/api/statistics/traffic-flow",
    params={'start_date': '2023-01-01', 'end_date': '2023-01-31'}
)
stats = response.json()['data']
```

### JavaScript 示例

```javascript
const baseUrl = 'http://localhost:5000';

// 1. 使用Agent查询
async function queryAgent(query) {
  const response = await fetch(`${baseUrl}/api/agent/query`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ query })
  });
  const data = await response.json();
  console.log(data.explanation);
  return data.recommendations;
}

// 2. 获取交易记录
async function getTransactions() {
  const params = new URLSearchParams({
    section_id: 'G5615530120',
    start_date: '2023-01-03',
    limit: 100
  });
  
  const response = await fetch(
    `${baseUrl}/api/transactions/entrance?${params}`
  );
  const data = await response.json();
  return data.data;
}

// 3. 统计分析
async function getStatistics() {
  const response = await fetch(
    `${baseUrl}/api/statistics/traffic-flow?start_date=2023-01-01`
  );
  const data = await response.json();
  return data.data;
}
```

### cURL 示例

```bash
# 使用Agent
curl -X POST http://localhost:5000/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{"query": "统计交通流量"}'

# 获取路段
curl http://localhost:5000/api/sections

# 获取交易记录
curl "http://localhost:5000/api/transactions/entrance?section_id=G5615530120&start_date=2023-01-03&limit=10"

# 统计分析
curl "http://localhost:5000/api/statistics/revenue?start_date=2023-01-01&end_date=2023-01-31"
```

---

## 💡 使用建议

1. **分页查询**: 交易记录数据量较大，建议使用`limit`和`offset`参数进行分页查询
2. **日期格式**: 日期参数格式为 `YYYY-MM-DD` 或 `YYYY-MM-DD HH:MM:SS`
3. **路段ID**: 首次使用建议先调用 `/api/sections` 了解可用的路段ID
4. **统计API**: 统计类API适合用于生成报表和数据可视化
5. **Agent**: 不确定使用哪个API时，可以使用Agent接口进行智能推荐

---

## 🎯 典型应用场景

### 场景1: 生成日报表
```bash
# 获取某天的收费统计
curl "http://localhost:5000/api/statistics/revenue?start_date=2023-01-03&end_date=2023-01-03"
```

### 场景2: 分析车流量
```bash
# 获取某路段一个月的流量统计
curl "http://localhost:5000/api/statistics/traffic-flow?section_id=G5615530120&start_date=2023-01-01&end_date=2023-01-31"
```

### 场景3: 查询交易明细
```bash
# 分页查询交易记录
curl "http://localhost:5000/api/transactions/entrance?limit=100&offset=0"
```

---

## 📞 技术支持

如有问题或建议，请联系技术团队。

---

**版本**: v1.0  
**最后更新**: 2024-11-20
