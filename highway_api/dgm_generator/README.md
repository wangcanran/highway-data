# DGM门架数据生成器

基于DGM(Deep Generative Model)框架的高速公路门架交易数据生成器

## 📁 项目结构

```
dgm_generator/
├── __init__.py                      # 包初始化
├── dgm_gantry_generator.py          # 主生成器（3500+行）
├── utils/                           # 工具模块
│   ├── __init__.py
│   ├── type_conversion.py           # 类型转换工具
│   ├── vehicle_classifier.py        # 车辆分类工具
│   └── constants.py                 # 业务常量
├── tests/                           # 单元测试
│   ├── __init__.py
│   ├── test_type_conversion.py      # 类型转换测试
│   └── test_vehicle_classifier.py   # 车辆分类测试
└── docs/                            # 文档
    ├── DGM_FRAMEWORK_COMPLETE.md    # 框架实现报告
    ├── DGM_IMPLEMENTATION_STATUS.md # 实现状态
    ├── CODE_REFACTORING_PLAN.md     # 重构计划
    └── REFACTORING_GUIDE.md         # 重构指南
```

## 🚀 快速开始

### 安装依赖

```bash
pip install openai numpy pymysql
pip install pytest pytest-cov  # 用于测试
```

### 基础使用

#### 命令行方式

```bash
# 生成50条数据
python dgm_gantry_generator.py --count 50 --output gantry_50.json

# 指定货车比例
python dgm_gantry_generator.py --count 100 --truck-ratio 0.7 --output data.json

# 使用种子数据
python dgm_gantry_generator.py --count 100 --seed-data real_samples.json --output generated.json
```

#### Python API

```python
from dgm_gantry_generator import DGMGantryGenerator

# 创建生成器
generator = DGMGantryGenerator()

# 从数据库加载真实数据（训练+评估）
generator.load_real_samples(
    limit=300,              # 训练数据
    evaluation_limit=1000   # 评估数据
)

# 生成数据
result = generator.generate(count=50, verbose=True)

# 获取结果
samples = result["samples"]              # 生成的样本
weighted_samples = result["weighted_samples"]  # 按质量排序的样本
evaluation = result["evaluation"]        # 评估结果
statistics = result["statistics"]        # 统计信息
```

## 🎯 核心特性

### ✅ DGM框架100%实现

1. **Generation（生成阶段）**
   - Task Specification
   - Generation Conditions
   - In-Context Demonstrations
   - Sample-Wise Decomposition
   - Dataset-Wise Decomposition

2. **Curation（策展阶段）**
   - Sample Filtering
   - Label Enhancement
   - Re-Weighting Strategies
   - Auxiliary Model Enhancement

3. **Evaluation（评估阶段）**
   - Direct Evaluation (Faithfulness + Diversity)
   - Benchmark Evaluation
   - Indirect Evaluation (下游任务)

### 📊 评估结果

根据最新测试（50条数据）：

```
[Direct Evaluation] 总分: 82.32%
  - Faithfulness: 82.87%
    * Constraint Check: 100.00%    ← 完美！
    * Benchmark: 65.75%
      - 时间模式: 98.96%           ← 优秀！
      - 相关性: 72.26%
  - Diversity: 81.50%

[Indirect Evaluation] 总分: 100.00%  ← 完美！
  - anomaly_detection: 100.00%
  - fee_prediction: 100.00%
  - vehicle_classification: 100.00%
  - time_consistency: 100.00%
```

### 🔧 工具模块

#### 类型转换工具

```python
from utils.type_conversion import safe_int_conversion, extract_mileage

# 安全转换（带日志、异常处理）
value = safe_int_conversion("123.45")  # -> 123
mileage = extract_mileage(sample)      # 从样本提取里程
```

#### 车辆分类工具

```python
from utils.vehicle_classifier import VehicleClassifier, classify_vehicle

# 分类车辆
category = VehicleClassifier.classify(12)  # -> "货车"
is_truck = VehicleClassifier.is_truck(12)  # -> True

# 从样本分类
category = classify_vehicle(sample)
```

#### 业务常量

```python
from utils.constants import CONSTANTS

# 获取限重
limit = CONSTANTS.axle_weights.get_limit("3")  # -> 25000kg

# 获取评分权重
weight = CONSTANTS.score_weights.FAITHFULNESS  # -> 0.6
```

## 🧪 运行测试

### 运行所有测试

```bash
cd dgm_generator
pytest tests/ -v
```

### 查看覆盖率

```bash
pytest tests/ --cov=utils --cov-report=html
# 打开 htmlcov/index.html
```

### 运行单个测试

```bash
pytest tests/test_type_conversion.py -v
pytest tests/test_vehicle_classifier.py -v
```

## 📋 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--count` | 生成数据条数 | 100 |
| `--output` | 输出文件路径 | 无（输出到控制台） |
| `--truck-ratio` | 货车比例 | 0.6 |
| `--seed-data` | 种子数据JSON文件 | 无（从数据库加载） |
| `--quiet` | 安静模式（不显示进度） | False |

## 📚 文档

- **框架实现报告**: `docs/DGM_FRAMEWORK_COMPLETE.md`
- **实现状态**: `docs/DGM_IMPLEMENTATION_STATUS.md`
- **重构计划**: `docs/CODE_REFACTORING_PLAN.md`
- **重构指南**: `docs/REFACTORING_GUIDE.md`

## 🔍 代码质量

### 当前评级：B-

**强项**：
- ✅ 架构清晰，模块边界合理
- ✅ 类型提示覆盖率高
- ✅ 考虑了多种业务场景

**待改进**：
- ⚠️ 82+处裸except块需要替换
- ⚠️ 类型转换需要增强健壮性
- ⚠️ 需要增加单元测试覆盖率

### 改进方案

详见 `docs/CODE_REFACTORING_PLAN.md` 和 `docs/REFACTORING_GUIDE.md`

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

MIT License

## 👥 作者

DGM Generator Team

---

**版本**: 1.0.0  
**最后更新**: 2025-12-05
