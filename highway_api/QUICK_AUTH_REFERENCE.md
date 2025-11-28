# API认证快速参考

## 快速判断：我的接口需要认证吗？

### ❌ 不需要认证
```
/api/statistics/*          统计分析
/api/analytics/truck/*     货车分析
/api/agent/query          Agent查询
/api/health               健康检查
```

### ✅ 需要认证
```
/api/sections*            路段信息
/api/toll-stations*       收费站信息
/api/gantries*            门架信息
/api/transactions/*       交易记录
```

---

## 认证方法

**请求头添加**:
```
X-API-Key: highway_admin_key_2024
```

---

## 代码示例

### Python
```python
import requests

# 需要认证的接口
headers = {'X-API-Key': 'highway_admin_key_2024'}
r = requests.get('http://localhost:5000/api/sections', headers=headers)
```

### JavaScript
```javascript
fetch('http://localhost:5000/api/sections', {
  headers: {
    'X-API-Key': 'highway_admin_key_2024'
  }
})
```

### curl
```bash
curl -H "X-API-Key: highway_admin_key_2024" \
  http://localhost:5000/api/sections
```

---

## 错误码

| 状态码 | 说明 | 解决方法 |
|-------|------|---------|
| 401 | 未提供API Key | 添加 X-API-Key 请求头 |
| 403 | API Key无效 | 使用有效的密钥 |
| 200 | 成功 | - |

---

## 测试命令

```bash
# 测试认证机制
python test_api_auth.py

# 测试公开接口（无需Key）
curl http://localhost:5000/api/statistics/traffic-flow

# 测试受保护接口（需要Key）
curl -H "X-API-Key: highway_admin_key_2024" \
  http://localhost:5000/api/sections
```

---

## 配置位置

**API密钥**: `config.py` → `API_KEYS`  
**启用/禁用**: `config.py` → `ENABLE_AUTH`

---

详细文档: [API_AUTH_GUIDE.md](./API_AUTH_GUIDE.md)
