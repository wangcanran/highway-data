# KACA算法实现说明

## 概述

本项目已将k-匿名实现从简单的固定泛化规则升级为基于聚类的KACA算法（K-Anonymity Clustering Algorithm）。

## KACA算法原理

KACA是一种高级k-匿名算法，通过聚类分析实现自适应泛化，相比传统固定规则泛化具有更好的数据效用和隐私保护效果。

### 算法步骤（核心：先聚类，再泛化）

**重要原则**：KACA算法的核心是先基于原始数据的相似度进行聚类，然后再对聚类结果进行泛化，而不是一开始就泛化。

1. **特征编码**（非泛化） - 将准标识符转换为数值特征以便聚类
   - 地理特征：从路段ID（section_id）提取完整数字部分（如G5615530120 → 5615530120）
   - 时间特征：从出口时间（exit_time）提取精确时间（小时+分钟）
   - **注意**：这一步只是特征编码，保留完整信息，不是泛化

2. **K-Means聚类** - 基于特征相似度对记录进行分组
   - 聚类数计算：`n_clusters = max(total_records // k, 1)`
   - 使用K-Means算法对数值特征进行聚类
   - 后处理：合并大小 < k 的小聚类到最近的大聚类

3. **自适应泛化**（聚类后才进行） - 对每个聚类内的**原始准标识符**进行泛化
   - 地理泛化：提取聚类内section_id的公共前缀 + "区域"
   - 时间泛化：基于聚类内时间范围自适应确定时段
   - **关键**：基于聚类结果自适应调整泛化粒度，而非固定规则

4. **聚合统计** - 计算每个等价类的统计信息
   - 货车数量（truck_count）
   - 平均通行费（avg_toll）

5. **k-匿名验证** - 确保每个聚类大小 >= k，抑制不满足条件的聚类

## 核心设计：先聚类，再泛化

```
原始数据 
   ↓
特征编码（保留完整信息）
   ↓
K-Means聚类（基于相似度分组）
   ↓
聚类后处理（合并小聚类）
   ↓
【此时才开始泛化】
   ↓
自适应泛化（基于聚类结果）
   ↓
聚合统计
   ↓
k-匿名数据输出
```

**关键点**：
- ✅ 聚类使用完整的原始数据信息（通过特征编码）
- ✅ 泛化发生在聚类之后，基于聚类结果自适应调整
- ❌ 不是一开始就泛化，避免信息过早丢失

## 相比传统固定泛化的优势

| 特性 | 传统固定泛化 | KACA算法 |
|------|------------|----------|
| 执行顺序 | 先泛化再分组 | **先聚类再泛化** |
| 泛化策略 | 固定规则（如前3位+区域） | 基于聚类自适应泛化 |
| 数据效用 | 较低，过度泛化 | 较高，精确泛化 |
| 隐私保护 | 满足k-匿名 | 满足k-匿名 |
| 适应性 | 差，无法适应数据分布 | 好，自动适应数据分布 |
| 信息损失 | 较多 | 较少 |

## 实现文件

- **kaca_anonymizer.py** - KACA算法核心实现
- **app.py** - API接口实现（使用KACA算法）
- **agent.py** - API描述和LLM代理配置

## API使用示例

### 端点
```
GET /api/analytics/truck/exit-hourly-flow-k-anonymized
```

### 参数
- `start_date` (可选): 开始日期，格式：YYYY-MM-DD
- `end_date` (可选): 结束日期，格式：YYYY-MM-DD
- `k` (可选): k-匿名的k值，默认5

### 示例请求
```
GET /api/analytics/truck/exit-hourly-flow-k-anonymized?start_date=2023-01-02&end_date=2023-01-04&k=5
```

### 响应示例
```json
{
  "success": true,
  "data": [
    {
      "section_region": "G561区域",
      "time_period": "下午时段(12-18)",
      "truck_count": 420,
      "avg_toll": 24.8,
      "k_anonymized": true,
      "algorithm": "KACA"
    }
  ],
  "count": 4,
  "category": "📊 流量统计类（k-匿名保护）",
  "privacy_protection": {
    "method": "KACA (K-Anonymity Clustering Algorithm)",
    "algorithm": "KACA",
    "k_value": 5,
    "input_source": "原始出口交易记录",
    "quasi_identifiers": ["section_id", "exit_time"],
    "clustering": {
      "algorithm": "K-Means",
      "clusters": 4,
      "description": "基于聚类的自适应泛化"
    },
    "generalization": {
      "geographic": "聚类内section_id公共前缀 + \"区域\"",
      "temporal": "聚类内时间范围泛化"
    },
    "statistics": {
      "total_records": 2100,
      "anonymized_groups": 4,
      "suppressed_records": 0,
      "retention_rate": 100.0
    }
  }
}
```

## 依赖安装

KACA算法需要以下Python包：

```bash
pip install numpy>=1.24.0
pip install scikit-learn>=1.3.0
```

或使用requirements.txt：

```bash
pip install -r requirements.txt
```

## 性能指标

- **数据保留率（Retention Rate）**: 未被抑制的记录占总记录的百分比
- **聚类数（Clusters）**: 形成的等价类数量
- **抑制记录数（Suppressed Records）**: 因不满足k-匿名而被抑制的记录数

## 隐私保证

- ✅ 满足k-匿名性：每个等价类至少包含k条原始记录
- ✅ 准标识符泛化：地理位置和时间信息被泛化
- ✅ 敏感属性保护：通过聚合统计保护个体隐私
- ✅ 自适应泛化：基于数据分布优化泛化粒度

## 参考文献

KACA算法基于以下研究成果：
- k-Anonymity: A Model for Protecting Privacy (Sweeney, 2002)
- Clustering-based k-Anonymity Algorithms
- Adaptive Generalization Strategies for Privacy-Preserving Data Publishing
