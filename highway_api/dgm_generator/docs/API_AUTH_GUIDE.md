# API认证指南

## 概述

为保障数据安全，本系统对API接口进行了分级保护：

- **🔓 公开接口**：统计分析类接口，无需认证即可访问
- **🔒 受保护接口**：原始数据接口，需要提供有效的API Key

---

## 接口分类

### 🔓 公开接口（无需认证）

#### 1. Agent智能查询
- `/api/agent/query` - AI驱动的API推荐

#### 2. 统计分析类
- `/api/statistics/traffic-flow` - 交通流量统计
- `/api/statistics/revenue` - 收费统计
- `/api/statistics/vehicle-distribution` - 车型分布统计

#### 3. 货车分析类（10个接口）
- `/api/analytics/truck/hourly-flow` - 货车小时流量
- `/api/analytics/truck/avg-travel-time` - 平均通行时间
- `/api/analytics/truck/avg-toll-fee` - 平均通行费
- `/api/analytics/truck/congestion-index` - 拥堵指数
- `/api/analytics/truck/overweight-rate` - 超载比例
- `/api/analytics/truck/discount-rate` - 优惠比例
- `/api/analytics/truck/peak-hours` - 高峰时段
- `/api/analytics/truck/avg-axle-count` - 平均轴数
- `/api/analytics/truck/lane-utilization` - 车道利用率
- `/api/analytics/truck/toll-station-status` - 收费站状态

#### 4. 系统接口
- `/api/health` - 健康检查
- `/` - 首页

### 🔒 受保护接口（需要认证）

#### 1. 基础数据接口
- `/api/sections` - 路段列表
- `/api/sections/<section_id>` - 路段详情
- `/api/toll-stations` - 收费站列表
- `/api/toll-stations/<station_id>` - 收费站详情
- `/api/gantries` - 门架列表
- `/api/gantries/<gantry_id>` - 门架详情

#### 2. 交易记录接口
- `/api/transactions/entrance` - 入口交易记录
- `/api/transactions/exit` - 出口交易记录
- `/api/transactions/gantry` - 门架交易记录

---

## 认证方式

### API Key认证

受保护的接口需要在HTTP请求头中提供API Key：

```http
X-API-Key: your_api_key_here
```

### 获取API Key

请联系系统管理员获取API Key。系统预置了以下密钥（仅供参考）：
- `highway_admin_key_2024` - 管理员密钥
- `highway_internal_key_2024` - 内部系统密钥

**⚠️ 重要提示**：
- API Key应当妥善保管，不要泄露给未授权人员
- 建议在生产环境中修改默认密钥
- 可以在 `config.py` 中配置密钥列表

---

## 使用示例

### 示例1：访问公开接口（无需认证）

```python
import requests

# 访问货车流量分析API - 无需认证
response = requests.get(
    'http://localhost:5000/api/analytics/truck/hourly-flow',
    params={'section_id': 'G5615530120'}
)

data = response.json()
print(data)
```

```bash
# 使用curl
curl "http://localhost:5000/api/analytics/truck/hourly-flow?section_id=G5615530120"
```

### 示例2：访问受保护接口（需要认证）

```python
import requests

# 访问路段信息API - 需要提供API Key
response = requests.get(
    'http://localhost:5000/api/sections',
    headers={'X-API-Key': 'highway_admin_key_2024'}
)

data = response.json()
print(data)
```

```bash
# 使用curl
curl -H "X-API-Key: highway_admin_key_2024" \
  "http://localhost:5000/api/sections"
```

### 示例3：访问交易记录（需要认证 + 分页）

```python
import requests

# 访问入口交易记录
response = requests.get(
    'http://localhost:5000/api/transactions/entrance',
    headers={'X-API-Key': 'highway_admin_key_2024'},
    params={
        'section_id': 'G5615530120',
        'limit': 50,
        'offset': 0
    }
)

data = response.json()
print(f"总数: {data['total']}")
print(f"当前页: {len(data['data'])} 条")
```

---

## 错误处理

### 401 Unauthorized - 未提供API Key

**请求**:
```bash
curl "http://localhost:5000/api/sections"
```

**响应**:
```json
{
  "success": false,
  "error": "未提供API Key",
  "message": "访问此接口需要在请求头中提供 X-API-Key"
}
```

**解决方法**：在请求头中添加 `X-API-Key`

---

### 403 Forbidden - API Key无效

**请求**:
```bash
curl -H "X-API-Key: invalid_key" \
  "http://localhost:5000/api/sections"
```

**响应**:
```json
{
  "success": false,
  "error": "API Key无效",
  "message": "提供的API Key无效或已过期"
}
```

**解决方法**：使用有效的API Key，或联系管理员获取新密钥

---

## 配置说明

### 修改API密钥

编辑 `config.py` 文件：

```python
# API认证配置
API_KEYS = [
    'your_custom_key_1',  # 自定义密钥1
    'your_custom_key_2',  # 自定义密钥2
]

# 是否启用认证（开发环境可设为False）
ENABLE_AUTH = True
```

### 禁用认证（仅开发环境）

在开发调试阶段，可以临时禁用认证：

```python
# config.py
ENABLE_AUTH = False  # 设置为False禁用认证
```

**⚠️ 警告**：生产环境务必启用认证！

---

## 测试工具

### 运行自动化测试

```bash
python test_api_auth.py
```

测试脚本会自动验证：
1. ✓ 公开接口无需认证即可访问
2. ✓ 受保护接口在无Key时返回401
3. ✓ 受保护接口在无效Key时返回403
4. ✓ 受保护接口在有效Key时正常返回数据

### 使用Postman测试

1. 创建新请求
2. 设置URL：`http://localhost:5000/api/sections`
3. 在 **Headers** 标签页添加：
   - Key: `X-API-Key`
   - Value: `highway_admin_key_2024`
4. 发送请求

---

## 最佳实践

### 1. 安全建议
- ✅ 使用HTTPS传输（生产环境）
- ✅ 定期更换API Key
- ✅ 为不同用户/系统分配不同的Key
- ✅ 记录API访问日志
- ❌ 不要在客户端代码中硬编码Key
- ❌ 不要在URL参数中传递Key

### 2. 错误处理
```python
import requests

def safe_api_call(url, api_key):
    try:
        response = requests.get(
            url,
            headers={'X-API-Key': api_key},
            timeout=10
        )
        
        if response.status_code == 401:
            print("错误：未提供或未识别API Key")
            return None
        elif response.status_code == 403:
            print("错误：API Key无效")
            return None
        elif response.status_code == 200:
            return response.json()
        else:
            print(f"错误：HTTP {response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        print("错误：请求超时")
        return None
    except Exception as e:
        print(f"错误：{str(e)}")
        return None
```

### 3. 环境变量管理
```python
import os

# 从环境变量读取API Key
API_KEY = os.getenv('HIGHWAY_API_KEY', 'default_key')

response = requests.get(
    url,
    headers={'X-API-Key': API_KEY}
)
```

---

## 常见问题

### Q1: 为什么部分接口需要认证？
**A**: 原始数据接口包含敏感信息（如车辆通行记录、收费详情等），需要保护。统计分析接口已经过数据聚合和脱敏，可以公开访问。

### Q2: 如何申请API Key？
**A**: 请联系系统管理员。管理员可以在 `config.py` 中添加新的密钥。

### Q3: API Key会过期吗？
**A**: 当前版本的Key不会自动过期，但建议定期更换以提高安全性。

### Q4: 可以使用其他认证方式吗？
**A**: 当前仅支持API Key认证。如需OAuth2、JWT等方式，请联系开发团队。

### Q5: 忘记API Key怎么办？
**A**: 联系管理员重置或查看 `config.py` 中的配置。

---

## 更新日志

### 2025-11-20
- ✅ 实现API Key认证机制
- ✅ 为8个原始数据接口添加认证保护
- ✅ 保持13个统计/分析接口公开访问
- ✅ 创建认证测试工具

---

## 技术支持

如有问题或建议，请联系：
- 开发团队
- 系统管理员

**API版本**: v1.0  
**最后更新**: 2025-11-20
