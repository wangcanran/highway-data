# DGM模块部署指南

## 🎯 概述

本文档说明如何在Highway API平台上部署和使用DGM（Data Generation Model）数据生成模块。

---

## 📦 部署架构

```
highway_api/
├── app.py                      # Flask主应用（已集成DGM）
├── dgm_api.py                  # DGM API封装模块（新增）
├── dgm_generator/              # DGM核心生成器
│   ├── dgm_gantry_generator.py
│   ├── auxiliary_models/
│   │   └── discriminative_verifier.py
│   └── ...
├── DGM_API_GUIDE.md           # API使用指南（新增）
└── test_dgm_api.py            # API测试脚本（新增）
```

---

## 🚀 快速启动

### 1. 启动Flask应用

```bash
cd d:\python_code\flaskProject\highway_api
python app.py
```

**输出**：
```
* Running on http://127.0.0.1:5000
* Running on http://192.168.1.100:5000
```

### 2. 测试API（新终端）

```bash
# 测试基本连接
curl http://localhost:5000/api/test/connection

# 快速生成DGM数据
curl "http://localhost:5000/api/generate/gantry?method=dgm&count=5"

# 运行完整测试
python test_dgm_api.py
```

---

## 📋 API端点清单

### 统一生成接口（推荐用于快速测试）

```http
GET/POST /api/generate/gantry
```

**参数**：
- `method`: `rule` | `model` | `dgm`
- `count`: 生成数量

**示例**：
```bash
# 快速生成10条DGM数据
curl "http://localhost:5000/api/generate/gantry?method=dgm&count=10"

# POST方式
curl -X POST http://localhost:5000/api/generate/gantry \
  -H "Content-Type: application/json" \
  -d '{"method": "dgm", "count": 10}'
```

### DGM专用接口（推荐用于生产）

#### 1. 初始化生成器

```http
POST /api/dgm/initialize
```

**请求体**：
```json
{
    "real_data_limit": 300,
    "evaluation_limit": 1000,
    "use_discriminative": true
}
```

#### 2. 生成数据（含评估）

```http
POST /api/dgm/generate
```

**请求体**：
```json
{
    "count": 50,
    "verbose": false
}
```

**响应示例**：
```json
{
    "status": "success",
    "count": 50,
    "samples": [ /* 生成的门架交易数据 */ ],
    "evaluation": {
        "direct": {
            "overall_score": 0.8994,
            "faithfulness": 0.9123,
            "diversity": 0.88,
            "benchmark_similarity": 0.8247
        },
        "indirect": {
            "overall_score": 0.9125,
            "tasks": {
                "anomaly_detection": 1.0,
                "fee_prediction": 0.6501,
                "vehicle_classification": 1.0,
                "time_consistency": 1.0
            }
        }
    },
    "quality_distribution": {
        "high": 40,
        "medium": 10,
        "low": 0
    }
}
```

#### 3. 查看统计信息

```http
GET /api/dgm/stats
```

#### 4. 查看状态

```http
GET /api/dgm/status
```

---

## 💻 使用示例

### Python示例

```python
import requests

BASE_URL = "http://localhost:5000"

# 方式1: 快速生成（自动初始化）
response = requests.get(
    f"{BASE_URL}/api/generate/gantry",
    params={"method": "dgm", "count": 20}
)
samples = response.json()
print(f"生成 {len(samples)} 条样本")

# 方式2: 完整流程（手动控制）
# 步骤1: 初始化
init_response = requests.post(
    f"{BASE_URL}/api/dgm/initialize",
    json={
        "real_data_limit": 300,
        "evaluation_limit": 1000,
        "use_discriminative": True
    }
)
print(init_response.json())

# 步骤2: 生成数据
gen_response = requests.post(
    f"{BASE_URL}/api/dgm/generate",
    json={"count": 100}
)
result = gen_response.json()

print(f"Direct评分: {result['evaluation']['direct']['overall_score']:.2%}")
print(f"高质量样本: {result['quality_distribution']['high']}")

# 保存样本
import json
with open('dgm_samples.json', 'w', encoding='utf-8') as f:
    json.dump(result['samples'], f, ensure_ascii=False, indent=2)
```

### JavaScript示例

```javascript
// 快速生成
fetch('http://localhost:5000/api/generate/gantry?method=dgm&count=10')
    .then(res => res.json())
    .then(data => {
        console.log(`生成 ${data.length} 条样本`);
        console.log(data[0]);
    });

// 完整流程
async function generateWithDGM() {
    // 初始化
    const initRes = await fetch('http://localhost:5000/api/dgm/initialize', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            real_data_limit: 300,
            evaluation_limit: 1000,
            use_discriminative: true
        })
    });
    console.log(await initRes.json());
    
    // 生成
    const genRes = await fetch('http://localhost:5000/api/dgm/generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({count: 50})
    });
    const result = await genRes.json();
    
    console.log(`Direct评分: ${(result.evaluation.direct.overall_score * 100).toFixed(2)}%`);
    console.log(`样本数: ${result.count}`);
    
    return result.samples;
}
```

---

## ⚙️ 配置说明

### 初始化参数

| 参数 | 默认值 | 说明 | 推荐值 |
|------|-------|------|--------|
| `real_data_limit` | 300 | 用于学习统计特征的真实数据量 | 300-500 |
| `evaluation_limit` | 1000 | 用于Benchmark评估的真实数据量 | 1000-2000 |
| `use_discriminative` | true | 是否使用判别式模型验证 | true（生产环境） |

### 生成参数

| 参数 | 默认值 | 说明 | 推荐范围 |
|------|-------|------|----------|
| `count` | 10 | 生成样本数量 | 10-500 |
| `verbose` | false | 是否输出详细日志 | false（API环境） |

---

## 📊 性能指标

### 生成速度

| 样本数 | 预计耗时 | 内存占用 |
|-------|---------|----------|
| 10条 | 5-10秒 | ~30MB |
| 50条 | 20-30秒 | ~30MB |
| 100条 | 40-60秒 | ~30MB |
| 500条 | 3-5分钟 | ~30MB |

### 质量指标（100条样本）

```
✓ Direct Evaluation: 89.94%
✓ Benchmark相似度: 82.47%
✓ 统计特征相似度: 81.13%
✓ 相关性相似度: 88.75%
✓ 高质量样本: 80%
✓ 低质量样本: 0%
```

---

## 🔧 故障排查

### 问题1: 初始化失败

**错误**：
```json
{
    "status": "error",
    "message": "Initialization failed: ..."
}
```

**解决方案**：
1. 检查数据库连接配置（`config.py`）
2. 确保数据库中有足够的真实数据
3. 检查OpenAI API配置

### 问题2: 生成速度慢

**原因**：
- LLM API调用延迟
- 判别式模型验证耗时

**优化方案**：
1. 减少`real_data_limit`（如100）
2. 设置`use_discriminative=false`（跳过判别式验证）
3. 使用更快的LLM模型

### 问题3: 内存占用高

**解决方案**：
1. 减少`evaluation_limit`（如500）
2. 分批生成（每次50-100条）
3. 定期重启服务释放内存

---

## 🔐 安全建议

### 生产环境部署

1. **启用API认证**：
```python
# config.py
ENABLE_AUTH = True
API_KEYS = ["your-secret-key-1", "your-secret-key-2"]
```

2. **限制请求速率**：
```python
from flask_limiter import Limiter

limiter = Limiter(app, key_func=lambda: request.remote_addr)

@app.route('/api/dgm/generate', methods=['POST'])
@limiter.limit("10 per minute")
def dgm_generate():
    # ...
```

3. **设置最大生成量**：
```python
MAX_COUNT = 500

count = min(data.get('count', 10), MAX_COUNT)
```

---

## 📈 监控与日志

### 添加日志记录

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dgm_api.log'),
        logging.StreamHandler()
    ]
)
```

### 关键指标监控

建议监控：
- ✓ 初始化时间
- ✓ 生成速度（样本/秒）
- ✓ 评估分数趋势
- ✓ 错误率
- ✓ 内存使用

---

## 🎓 进阶使用

### 自定义目标分布

```python
# 在DGMGantryGenerator初始化时指定
target_distribution = {
    "vehicle": {"货车": 0.3, "客车": 0.7},
    "time": {"早高峰": 0.3, "平峰": 0.5, "深夜": 0.2},
    "scenario": {"正常": 0.95, "超载": 0.05}
}

generator = DGMGantryGenerator(target_distribution=target_distribution)
```

### 批量生成和保存

```python
def batch_generate_and_save(total_count=1000, batch_size=100):
    """批量生成并保存"""
    all_samples = []
    
    for i in range(0, total_count, batch_size):
        response = requests.post(
            f"{BASE_URL}/api/dgm/generate",
            json={"count": batch_size}
        )
        result = response.json()
        
        if result['status'] == 'success':
            all_samples.extend(result['samples'])
            print(f"已生成: {len(all_samples)}/{total_count}")
    
    # 保存到文件
    with open('dgm_batch_samples.json', 'w', encoding='utf-8') as f:
        json.dump(all_samples, f, ensure_ascii=False, indent=2)
    
    return all_samples
```

---

## 📞 支持与反馈

- 📖 API文档：`DGM_API_GUIDE.md`
- 🏗️ 项目结构：`dgm_generator/PROJECT_STRUCTURE.md`
- 🚀 快速开始：`dgm_generator/QUICKSTART.md`
- 🧪 测试脚本：`test_dgm_api.py`

---

## ✅ 部署检查清单

部署前确认：

- [ ] Flask应用正常启动
- [ ] 数据库连接正常（`/api/test/connection`）
- [ ] OpenAI API配置正确
- [ ] DGM模块导入成功
- [ ] 统一接口测试通过（`method=dgm`）
- [ ] 专用接口测试通过（`/api/dgm/*`）
- [ ] 运行测试脚本无错误（`python test_dgm_api.py`）

部署后验证：

- [ ] 快速生成10条样本成功
- [ ] 初始化生成器成功
- [ ] 生成100条样本质量达标（Direct>85%）
- [ ] 查看统计信息正常
- [ ] 状态检查正常

---

**🎉 恭喜！DGM模块已成功部署到平台！**
