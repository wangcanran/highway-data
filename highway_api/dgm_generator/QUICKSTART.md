# 快速开始指南

## 5分钟上手DGM数据生成器

### 1️⃣ 安装依赖

```bash
cd dgm_generator
pip install -r requirements.txt
```

### 2️⃣ 生成第一批数据

```bash
# 生成10条测试数据（快速）
python dgm_gantry_generator.py --count 10 --output test_10.json

# 生成50条完整数据（带评估）
python dgm_gantry_generator.py --count 50 --output gantry_50.json
```

### 3️⃣ 查看输出

生成过程会显示：

```
============================================================
DGM 门架数据生成器
============================================================

[阶段 I] Generation - 数据生成
----------------------------------------
  [生成进度] 10/10
  [完成] 生成 10 条原始数据

[阶段 II] Curation - 数据策展
----------------------------------------
  [过滤] 通过: 10, 失败: 0
  [增强] 完成标签增强

[阶段 III] Evaluation - 数据评估
----------------------------------------
  直接评估: 82.32%
  间接评估: 100.00%

[保存] 已保存 10 条数据到 test_10.json
```

### 4️⃣ 查看生成的数据

```bash
# Windows PowerShell
Get-Content test_10.json | ConvertFrom-Json | Select-Object -First 1 | ConvertTo-Json

# 或使用Python
python -c "import json; print(json.dumps(json.load(open('test_10.json'))[0], indent=2, ensure_ascii=False))"
```

### 5️⃣ 运行测试（可选）

```bash
# 运行所有测试
pytest tests/ -v

# 查看测试覆盖率
pytest tests/ --cov=utils --cov-report=term
```

---

## 常用命令

### 生成不同比例的数据

```bash
# 70%货车，30%客车
python dgm_gantry_generator.py --count 100 --truck-ratio 0.7 --output trucks_70.json

# 40%货车，60%客车
python dgm_gantry_generator.py --count 100 --truck-ratio 0.4 --output trucks_40.json
```

### 使用种子数据

```bash
# 从JSON文件学习
python dgm_gantry_generator.py --count 100 --seed-data real_samples.json --output generated.json
```

### 安静模式（不显示进度）

```bash
python dgm_gantry_generator.py --count 100 --output data.json --quiet
```

---

## Python API使用

### 基础用法

```python
from dgm_gantry_generator import DGMGantryGenerator

# 创建生成器
generator = DGMGantryGenerator()

# 加载真实数据（从数据库）
generator.load_real_samples(
    limit=300,              # 训练数据
    evaluation_limit=1000   # 评估数据
)

# 生成数据
result = generator.generate(count=50, verbose=True)

# 获取高质量样本（按权重排序）
high_quality_samples = result["weighted_samples"][:20]

# 保存
import json
with open("high_quality.json", "w", encoding="utf-8") as f:
    json.dump(high_quality_samples, f, ensure_ascii=False, indent=2)
```

### 获取质量分层

```python
result = generator.generate(count=100, verbose=True)

# 获取质量分层
tiers = result.get("quality_tiers")
if tiers:
    print(f"高质量: {len(tiers['high_quality'])} 条")
    print(f"中等质量: {len(tiers['medium_quality'])} 条")
    print(f"低质量: {len(tiers['low_quality'])} 条")
    
    # 只使用高质量数据
    high_quality = tiers["high_quality"]
```

### 查看评估结果

```python
result = generator.generate(count=50)

# Direct Evaluation
direct = result["evaluation"]["direct"]
print(f"Faithfulness: {direct['faithfulness']['score']:.2%}")
print(f"Diversity: {direct['diversity']['score']:.2%}")

# Indirect Evaluation
indirect = result["evaluation"]["indirect"]
open_eval = indirect["open_evaluation"]
print(f"Overall: {open_eval['overall']['score']:.2%}")
```

---

## 使用工具模块

### 类型转换工具

```python
from utils.type_conversion import safe_int_conversion, extract_mileage

# 安全转换
value = safe_int_conversion("123.45")  # -> 123
value = safe_int_conversion("abc", default=0)  # -> 0

# 从样本提取
sample = {"fee_mileage": "12345", "pay_fee": "1000"}
mileage = extract_mileage(sample)  # -> 12345
```

### 车辆分类工具

```python
from utils.vehicle_classifier import VehicleClassifier

# 分类
category = VehicleClassifier.classify(12)  # -> "货车"
category = VehicleClassifier.classify_safe("abc")  # -> "客车"（容错）

# 判断
is_truck = VehicleClassifier.is_truck(12)  # -> True
is_passenger = VehicleClassifier.is_passenger(1)  # -> True

# 获取期望轴数
axles = VehicleClassifier.get_expected_axles(13)  # -> "3"
```

### 业务常量

```python
from utils.constants import CONSTANTS

# 轴数限重
limit = CONSTANTS.axle_weights.get_limit("3")  # -> 25000kg

# 时间段判断
period = CONSTANTS.time_periods.get_period(8)  # -> "早高峰"

# 评分权重
weight = CONSTANTS.score_weights.FAITHFULNESS  # -> 0.6
```

---

## 下一步

- 📖 阅读完整文档: `README.md`
- 🔍 了解DGM框架: `docs/DGM_FRAMEWORK_COMPLETE.md`
- 🛠️ 代码重构指南: `docs/REFACTORING_GUIDE.md`
- 🧪 查看测试: `tests/`

有问题？查看 `docs/` 目录下的详细文档！
