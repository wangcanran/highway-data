# AI SQL 自然语言查询功能

## 🎯 功能概述

您现在可以使用**自然语言**查询数据库，AI会自动：
1. 理解您的查询意图
2. 生成安全的SQL语句
3. 执行查询并返回结果
4. **推荐对应的API端点**（如果有）

---

## 🚀 API端点

### 1. `/api/ai/sql` - 自然语言查询并执行

**功能**：将自然语言转换为SQL，执行查询，返回结果和API链接

**方法**：POST

**请求格式**：
```json
{
  "query": "你的自然语言查询"
}
```

**响应格式**：
```json
{
  "success": true,
  "user_query": "查询所有路段",
  "explanation": "查询所有路段信息，限制返回100条记录",
  "sql": "SELECT * FROM section LIMIT 100",
  "query_type": "simple",
  "data": [...],
  "count": 8,
  "columns": ["section_id", "section_name"],
  "api_endpoint": "http://localhost:5000/api/sections",
  "note": "这是AI生成的SQL查询结果。如果需要固定的API端点，请联系管理员。"
}
```

### 2. `/api/ai/sql/generate` - 只生成SQL（不执行）

**功能**：将自然语言转换为SQL，但不执行查询

**方法**：POST

**请求格式**：
```json
{
  "query": "你的自然语言查询"
}
```

**响应格式**：
```json
{
  "success": true,
  "sql": "SELECT * FROM section LIMIT 100",
  "explanation": "查询所有路段信息，限制返回100条记录",
  "query_type": "simple",
  "estimated_rows": 8
}
```

---

## 💡 使用示例

### 示例1：简单查询

**自然语言**：
```
查询所有路段
```

**AI生成的SQL**：
```sql
SELECT * FROM section LIMIT 100
```

**返回的API端点**：
```
http://localhost:5000/api/sections
```

---

### 示例2：条件查询

**自然语言**：
```
查询大关至永善高速的收费站
```

**AI生成的SQL**：
```sql
SELECT * FROM tollstation WHERE section_id = 'S0014530030' LIMIT 100
```

**返回的API端点**：
```
http://localhost:5000/api/toll-stations?section_id=S0014530030
```

---

### 示例3：聚合统计

**自然语言**：
```
统计每个路段有多少个收费站
```

**AI生成的SQL**：
```sql
SELECT s.section_name, COUNT(t.toll_station_id) as station_count 
FROM section s 
LEFT JOIN tollstation t ON s.section_id = t.section_id 
GROUP BY s.section_id, s.section_name
```

**返回的API端点**：
```
该查询为自定义SQL，没有对应的固定API端点
```

---

### 示例4：时间范围查询

**自然语言**：
```
查询最近的10条出口交易记录，包括通行费金额
```

**AI生成的SQL**：
```sql
SELECT * FROM exittransaction 
ORDER BY exit_time DESC 
LIMIT 10
```

**返回的API端点**：
```
http://localhost:5000/api/transactions/exit?limit=10
```

---

### 示例5：复杂分析

**自然语言**：
```
统计货车（车型11-16）的总通行费
```

**AI生成的SQL**：
```sql
SELECT SUM(toll_money) as total_toll 
FROM exittransaction 
WHERE vehicle_class IN ('11','12','13','14','15','16')
```

---

## 🔧 使用方法

### 方式1：使用curl

```bash
curl -X POST http://localhost:5000/api/ai/sql \
  -H "Content-Type: application/json" \
  -d '{"query": "查询所有路段"}'
```

### 方式2：使用Python

```python
import requests

response = requests.post(
    'http://localhost:5000/api/ai/sql',
    json={'query': '查询所有路段'}
)

result = response.json()
print(f"SQL: {result['sql']}")
print(f"结果数: {result['count']}")
print(f"API端点: {result['api_endpoint']}")
```

### 方式3：使用JavaScript

```javascript
fetch('http://localhost:5000/api/ai/sql', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    query: '查询所有路段'
  })
})
.then(response => response.json())
.then(data => {
  console.log('SQL:', data.sql);
  console.log('结果数:', data.count);
  console.log('API端点:', data.api_endpoint);
});
```

---

## 🛡️ 安全保护

AI SQL查询系统内置多重安全保护：

### 1. SQL类型限制
- ✅ 只允许 SELECT 查询
- ❌ 禁止 INSERT、UPDATE、DELETE
- ❌ 禁止 DROP、ALTER、CREATE

### 2. 危险关键字检测
自动检测并拒绝包含以下关键字的查询：
- DROP
- DELETE  
- INSERT
- UPDATE
- ALTER
- CREATE
- TRUNCATE

### 3. 结果数量限制
- 自动添加 LIMIT 限制（默认100条）
- 防止一次性返回过多数据

### 4. 参数化查询
- 使用 SQLAlchemy 的参数化查询
- 自动防止 SQL 注入

---

## 📊 支持的查询类型

### 1. 简单查询 (simple)
```
查询所有路段
查询所有收费站
查询所有门架
```

### 2. 条件查询 (conditional)
```
查询section_id为S0014530030的收费站
查询运营状态为正常的收费站
查询车型为11的入口交易记录
```

### 3. 聚合查询 (aggregate)
```
统计每个路段的收费站数量
计算每个路段的平均通行费
统计货车的总通行次数
```

### 4. 关联查询 (join)
```
查询所有门架及其所在路段名称
查询收费站和对应的路段信息
```

### 5. 时间范围查询 (time-range)
```
查询最近的100条交易记录
查询2023年12月的出口交易
```

---

## 🎓 高级用法

### 1. 预览SQL（不执行）

如果您只想看看AI会生成什么SQL，而不想执行查询：

```bash
curl -X POST http://localhost:5000/api/ai/sql/generate \
  -H "Content-Type": "application/json" \
  -d '{"query": "统计每个路段的门架数量"}'
```

返回：
```json
{
  "success": true,
  "sql": "SELECT section_name, COUNT(*) FROM gantry GROUP BY section_id",
  "explanation": "统计每个路段的门架数量",
  "query_type": "aggregate",
  "estimated_rows": 8
}
```

### 2. 获取对应的API端点

AI会自动识别查询模式，并推荐对应的固定API端点：

| 查询模式 | 推荐的API端点 |
|---------|--------------|
| 查询所有路段 | `/api/sections` |
| 查询所有收费站 | `/api/toll-stations` |
| 查询所有门架 | `/api/gantries` |
| 查询入口交易 | `/api/transactions/entrance` |
| 查询出口交易 | `/api/transactions/exit` |
| 查询门架交易 | `/api/transactions/gantry` |

### 3. 复杂分析查询

AI可以理解复杂的分析需求：

```
查询通行费超过100元的出口交易记录
统计每个路段每天的交易笔数
找出最繁忙的收费站（按交易次数）
分析不同车型的平均通行费
```

---

## 📝 数据库Schema

AI已知道以下数据库结构：

### 表1：section (路段表)
- `section_id` - 路段ID
- `section_name` - 路段名称

### 表2：tollstation (收费站表)
- `toll_station_id` - 收费站ID
- `station_name` - 收费站名称
- `section_id` - 路段ID
- `station_type` - 收费站类型
- `operation_status` - 运营状态
- `latitude`、`longitude` - 经纬度

### 表3：gantry (门架表)
- `gantry_id` - 门架ID
- `gantry_name` - 门架名称
- `section_id` - 路段ID
- `lane_count` - 车道数

### 表4：entrancetransaction (入口交易表)
- `entrance_transaction_id` - 交易ID
- `pass_id` - 通行标识
- `entrance_time` - 入口时间
- `vehicle_class` - 车型

### 表5：exittransaction (出口交易表)
- `exit_transaction_id` - 交易ID
- `pass_id` - 通行标识
- `exit_time` - 出口时间
- `vehicle_class` - 车型
- `toll_money` - 应收金额
- `real_money` - 实收金额
- `total_weight` - 总重量

### 表6：gantrytransaction (门架交易表)
- `gantry_transaction_id` - 交易ID
- `gantry_id` - 门架ID
- `transaction_time` - 交易时间
- `vehicle_type` - 车辆类型

---

## ⚠️ 注意事项

1. **API认证**：该功能不需要API Key认证，公开访问
2. **结果限制**：默认最多返回100条记录
3. **查询类型**：只支持SELECT查询
4. **AI理解**：AI会尽力理解您的意图，但复杂查询可能需要多次尝试
5. **性能考虑**：大数据量查询会自动添加LIMIT限制

---

## 🔍 故障排查

### 问题1：AI返回"安全检查失败"
**原因**：您的查询被识别为非SELECT操作  
**解决**：确保查询是数据查询，而不是数据修改

### 问题2：没有返回结果
**原因**：查询条件不匹配或表名错误  
**解决**：检查查询描述，使用正确的表名和字段名

### 问题3：返回的API端点是"没有对应的固定API端点"
**原因**：这是一个自定义SQL查询，系统没有预定义的API端点  
**解决**：使用AI SQL查询功能，或联系管理员添加新的固定API

---

## 📞 联系与反馈

如果您发现AI生成的SQL不准确，或者需要添加新的固定API端点，请联系系统管理员。

---

## 🎉 总结

AI SQL查询功能让您可以：
✅ 用自然语言查询数据库  
✅ 自动生成安全的SQL  
✅ 获取查询结果  
✅ 获得对应的API端点推荐  

**不再需要学习SQL语法，只需描述您想要什么！**
