# DGM数据生成API使用指南

## 📚 概述

DGM (Data Generation Model) 是一个基于论文级别框架的高质量门架交易数据生成系统，提供三阶段数据生成流程：
- **Generation**: 使用LLM分步生成数据
- **Curation**: 判别式模型验证和修正
- **Evaluation**: 直接评估和间接评估

### 🎯 核心优势

- ✅ **高质量**: Direct评估>89%, 统计特征相似度>81%
- ✅ **可控性**: 基于真实数据学习的统计分布
- ✅ **可扩展**: 100-500条稳定生成
- ✅ **评估体系**: 完整的Faithfulness和Diversity评估

---

## 🚀 快速开始

### 方式1：快速生成（推荐用于测试）

使用统一的生成API，自动初始化：

```bash
# GET请求
GET /api/generate/gantry?method=dgm&count=10

# POST请求
POST /api/generate/gantry
{
    "method": "dgm",
    "count": 10
}
```

**响应**：
```json
[
    {
        "gantry_transaction_id": "S001453001000820010202512051209310347",
        "pass_id": "010000PASS2025120512093192381465",
        "gantry_id": "S001453001000720010",
        "section_id": "S0014530010",
        "section_name": "宜宾至毕节高速威信至镇雄段",
        "transaction_time": "2023-03-15T13:47:25Z",
        "entrance_time": "2023-03-15T11:42:25Z",
        "vehicle_type": "2",
        "axle_count": "2",
        "total_weight": "3725",
        "vehicle_sign": "0x01",
        "pay_fee": 3079,
        "discount_fee": 154,
        "fee_mileage": "41056"
    },
    ...
]
```

---

### 方式2：完整流程（推荐用于生产）

#### 步骤1：初始化生成器

```bash
POST /api/dgm/initialize
{
    "real_data_limit": 300,      # 用于学习统计的真实数据量
    "evaluation_limit": 1000,    # 用于Benchmark评估的真实数据量
    "use_discriminative": true   # 是否使用判别式模型验证
}
```

**响应**：
```json
{
    "status": "success",
    "message": "DGM Generator initialized successfully",
    "config": {
        "training_samples": 300,
        "evaluation_samples": 1000,
        "use_discriminative": true,
        "data_source": "database"
    }
}
```

**说明**：
- 初始化只需要执行一次（单例模式）
- 会从数据库加载真实数据并学习统计特征
- 训练判别式模型（Isolation Forest + Gradient Boosting）

---

#### 步骤2：生成数据（包含评估）

```bash
POST /api/dgm/generate
{
    "count": 50,
    "verbose": false
}
```

**响应**：
```json
{
    "status": "success",
    "count": 50,
    "samples": [ /* 生成的样本 */ ],
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

---

#### 步骤3：查看统计信息（可选）

```bash
GET /api/dgm/stats
```

**响应**：
```json
{
    "status": "success",
    "learned_stats": {
        "by_vehicle": {
            "passenger": {
                "pay_fee": {
                    "mean": 1420,
                    "std": 1200,
                    "min": 63,
                    "max": 10557
                },
                "fee_mileage": {
                    "mean": 13107,
                    "std": 8500
                },
                "correlation": 0.7499
            },
            "truck": { /* ... */ }
        }
    }
}
```

---

#### 步骤4：检查状态（可选）

```bash
GET /api/dgm/status
```

**响应**：
```json
{
    "status": "success",
    "is_initialized": true,
    "use_discriminative": true
}
```

---

## 📊 API端点总览

| 端点 | 方法 | 说明 | 适用场景 |
|------|------|------|---------|
| `/api/generate/gantry` | GET/POST | 统一生成接口（支持rule/model/dgm） | 快速测试 |
| `/api/dgm/initialize` | POST | 初始化DGM生成器 | 首次使用 |
| `/api/dgm/generate` | POST | 生成数据（含评估） | 生产环境 |
| `/api/dgm/stats` | GET | 查看学习到的统计 | 调试分析 |
| `/api/dgm/status` | GET | 查看生成器状态 | 健康检查 |

---

## 🎯 方法对比

| 方法 | 质量 | 速度 | 评估 | 推荐场景 |
|------|------|------|------|---------|
| **rule** | ⭐⭐ | ⚡⚡⚡ | ❌ | 快速原型 |
| **model** | ⭐⭐⭐ | ⚡⚡ | ❌ | 中等质量需求 |
| **dgm** | ⭐⭐⭐⭐⭐ | ⚡ | ✅ | 生产级质量 |

---

## 📈 性能指标

### DGM生成质量（100条样本）

```
Direct Evaluation: 89.94%
├─ Faithfulness: 91.23%
│  ├─ Constraint Check: 100.00%
│  └─ Benchmark: 82.47%
│     ├─ 统计特征相似度: 81.13%
│     ├─ 相关性相似度: 88.75%
│     ├─ 分布相似度: 70.17%
│     └─ 时间模式相似度: 99.39%
└─ Diversity: 88.00%

Indirect Evaluation: 91.25%
├─ anomaly_detection: 100.00%
├─ fee_prediction: 65.01%
├─ vehicle_classification: 100.00%
└─ time_consistency: 100.00%

Quality Distribution:
├─ High Quality: 80%
├─ Medium Quality: 20%
└─ Low Quality: 0%
```

---

## 💡 使用建议

### 批量大小建议

| 用途 | 建议数量 | 说明 |
|------|---------|------|
| 测试 | 10-50 | 快速验证 |
| 开发 | 50-100 | 中等规模 |
| 生产 | 100-500 | 大规模生成 |

### 初始化参数建议

```python
# 推荐配置
{
    "real_data_limit": 300,        # 足够学习统计特征
    "evaluation_limit": 1000,      # 充分的Benchmark基准
    "use_discriminative": true     # 启用质量验证
}

# 快速测试配置
{
    "real_data_limit": 100,
    "evaluation_limit": 500,
    "use_discriminative": false
}

# 高质量配置
{
    "real_data_limit": 500,
    "evaluation_limit": 2000,
    "use_discriminative": true
}
```

---

## 🔧 Python客户端示例

```python
import requests

BASE_URL = "http://localhost:5000"

# 1. 初始化
init_response = requests.post(f"{BASE_URL}/api/dgm/initialize", json={
    "real_data_limit": 300,
    "evaluation_limit": 1000,
    "use_discriminative": True
})
print(init_response.json())

# 2. 生成数据
gen_response = requests.post(f"{BASE_URL}/api/dgm/generate", json={
    "count": 100,
    "verbose": False
})
result = gen_response.json()

print(f"生成样本数: {result['count']}")
print(f"Direct评分: {result['evaluation']['direct']['overall_score']:.2%}")
print(f"高质量样本: {result['quality_distribution']['high']}")

# 3. 获取样本
samples = result['samples']
for sample in samples[:3]:
    print(f"门架ID: {sample['gantry_id']}, 费用: {sample['pay_fee']}")
```

---

## 🚨 注意事项

### 1. 首次初始化

- 首次调用会从数据库加载数据并训练模型，耗时约30-60秒
- 建议在应用启动时预先初始化
- 使用单例模式，无需重复初始化

### 2. 内存占用

- 加载300条训练数据 + 1000条评估数据：约10-20MB
- 判别式模型：约5-10MB
- 总计：约15-30MB

### 3. 生成速度

- 10条样本：约5-10秒
- 50条样本：约20-30秒
- 100条样本：约40-60秒

### 4. 并发处理

- 当前使用单例模式，不支持并发生成
- 如需并发，建议使用队列机制

---

## 📖 技术细节

### 核心技术栈

- **Generation**: OpenAI GPT-4 (分步生成)
- **Curation**: Isolation Forest + Gradient Boosting
- **Evaluation**: 统计相似度 + 下游任务评估

### 采样方法

- **条件分布采样**: 保持费用-里程相关性
- **自适应缓存**: 每50个样本重置，避免累积偏差
- **边界保护**: 三重clip机制防止极端outlier

### 评估框架

```
Evaluation
├── Direct Evaluation
│   ├── Faithfulness
│   │   ├── Constraint Check (规则验证)
│   │   └── Benchmark (与真实数据对比)
│   └── Diversity (样本多样性)
└── Indirect Evaluation
    └── Open Evaluation (下游任务)
        ├── anomaly_detection (异常检测)
        ├── fee_prediction (费用预测)
        ├── vehicle_classification (车型分类)
        └── time_consistency (时间一致性)
```

---

## 📞 支持

如有问题，请查看：
- 主文档: `README.md`
- 项目结构: `dgm_generator/PROJECT_STRUCTURE.md`
- 快速开始: `dgm_generator/QUICKSTART.md`
