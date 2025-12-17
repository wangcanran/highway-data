# 代码重构计划 - DGM生成器

## 当前评级：B-（中等偏上，有较大提升空间）

---

## 🚨 致命问题清单

### 1. 裸except块泛滥（P0 - 最高优先级）

**当前状态**：82+ 处 `except: pass`
**风险等级**：🔴 **生产环境禁止使用**

**问题**：
```python
# ❌ 错误示例 - 吞掉所有异常
try:
    vtype = int(sample.get("vehicle_type", "1"))
except:
    return "客车"  # 无法知道为什么失败
```

**修复方案**：
```python
# ✅ 正确做法 - 具体异常捕获 + 日志
try:
    vtype = int(sample.get("vehicle_type", "1"))
except (ValueError, TypeError) as e:
    logger.warning(f"车型转换失败: {e}, 样本: {sample.get('gantry_transaction_id')}")
    return "客车"  # 降级处理
except KeyError as e:
    logger.error(f"缺少必填字段: {e}")
    raise  # 必填字段缺失应该抛出
```

---

### 2. 类型转换地狱（P0）

**问题位置**：行3015-3047（用户查看的代码）

```python
# ❌ 当前代码 - 多重嵌套转换
mileage_val = s.get("fee_mileage")
if isinstance(mileage_val, str):
    mileage = int(float(mileage_val))  # str->float->int
else:
    mileage = int(mileage_val) if mileage_val else 0
```

**问题**：
- 可能抛出ValueError、TypeError、AttributeError
- None、空字符串、非数字字符串都会崩溃
- 没有日志，无法追踪错误

**修复方案**：
```python
def safe_int_conversion(value: Any, default: int = 0, field_name: str = "") -> int:
    """安全的整数转换，带日志和类型提示
    
    Args:
        value: 待转换的值
        default: 失败时的默认值
        field_name: 字段名（用于日志）
    
    Returns:
        转换后的整数
    """
    if value is None:
        return default
    
    try:
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return default
            return int(float(value))
        logger.warning(f"未知类型 {type(value)} for {field_name}: {value}")
        return default
    except (ValueError, TypeError) as e:
        logger.warning(f"{field_name} 转换失败: {value} -> {e}")
        return default

# 使用
mileage = safe_int_conversion(s.get("fee_mileage"), default=0, field_name="fee_mileage")
```

---

### 3. 魔法数字和硬编码（P1）

**问题示例**：
```python
# ❌ 魔法数字到处都是
if 1 <= vtype <= 4:        # 为什么是4？
    score *= 0.6           # 为什么是0.6？
elif 11 <= vtype <= 16:    # 为什么是16？
    score *= 0.8

limits = {"2": 18000, "3": 25000, "4": 31000, "5": 43000, "6": 49000}
```

**修复方案**：
```python
# ✅ 使用常量和配置类
from dataclasses import dataclass
from enum import IntEnum

class VehicleType(IntEnum):
    """车辆类型枚举"""
    PASSENGER_MIN = 1
    PASSENGER_MAX = 4
    TRUCK_MIN = 11
    TRUCK_MAX = 16
    SPECIAL_MIN = 21
    SPECIAL_MAX = 26

@dataclass(frozen=True)
class BusinessConstants:
    """业务常量（不可变）"""
    AXLE_WEIGHT_LIMITS: dict = field(default_factory=lambda: {
        "2": 18_000,   # 2轴限重18吨
        "3": 25_000,   # 3轴限重25吨
        "4": 31_000,
        "5": 43_000,
        "6": 49_000
    })
    
    SCORE_WEIGHTS: dict = field(default_factory=lambda: {
        "time_consistency": 0.30,
        "fee_logic": 0.25,
        "vehicle_logic": 0.20,
        "field_completeness": 0.25
    })
    
    PASSENGER_SCORE_PENALTY = 0.6
    TRUCK_SCORE_PENALTY = 0.8

CONSTANTS = BusinessConstants()

# 使用
if VehicleType.PASSENGER_MIN <= vtype <= VehicleType.PASSENGER_MAX:
    score *= CONSTANTS.PASSENGER_SCORE_PENALTY
```

---

### 4. 重复代码（DRY原则违反）（P1）

**问题**：车型判断逻辑重复了15+次

```python
# ❌ 到处都是这段代码
try:
    vcode = int(sample.get("vehicle_type", "1"))
    return "货车" if 11 <= vcode <= 16 or 21 <= vcode <= 26 else "客车"
except:
    return "客车"
```

**修复方案**：
```python
# ✅ 抽取为工具类
class VehicleClassifier:
    """车辆分类工具（单一职责）"""
    
    @staticmethod
    def classify(vehicle_type: Union[str, int]) -> str:
        """分类车辆类型
        
        Args:
            vehicle_type: 车型代码
            
        Returns:
            "客车" | "货车" | "专项车"
        
        Raises:
            ValueError: 车型代码无效
        """
        try:
            vcode = int(vehicle_type)
        except (ValueError, TypeError) as e:
            raise ValueError(f"无效的车型代码: {vehicle_type}") from e
        
        if 1 <= vcode <= 4:
            return "客车"
        elif 11 <= vcode <= 16:
            return "货车"
        elif 21 <= vcode <= 26:
            return "专项车"
        else:
            raise ValueError(f"未知车型代码: {vcode}")
    
    @staticmethod
    def classify_safe(vehicle_type: Union[str, int], default: str = "客车") -> str:
        """分类车辆类型（容错版本）"""
        try:
            return VehicleClassifier.classify(vehicle_type)
        except ValueError:
            logger.warning(f"车型分类失败，使用默认值: {default}")
            return default
```

---

### 5. 性能问题（P2）

**问题1：没有批量处理**
```python
# ❌ 当前：一条一条处理
for sample in samples:
    response = client.chat.completions.create(...)  # 50次API调用
```

**修复**：
```python
# ✅ 批量处理
def generate_batch(conditions: List[GenerationCondition], batch_size: int = 10):
    """批量生成，减少API调用"""
    for i in range(0, len(conditions), batch_size):
        batch = conditions[i:i+batch_size]
        # 一次API调用生成多条
        prompt = self._build_batch_prompt(batch)
        response = client.chat.completions.create(...)
```

**问题2：没有缓存**
```python
# ❌ 重复计算
def _calculate_sample_weights(self, samples):
    # 每次都重新计算相同样本的权重
```

**修复**：
```python
# ✅ 使用LRU缓存
from functools import lru_cache

@lru_cache(maxsize=1024)
def _get_sample_hash(sample_json: str) -> str:
    """可缓存的样本哈希"""
    return hashlib.md5(sample_json.encode()).hexdigest()
```

---

### 6. 缺少单元测试（P1）

**当前状态**：0个测试
**目标**：核心逻辑100%覆盖

**必须测试的模块**：
```python
# tests/test_vehicle_classifier.py
def test_classify_passenger():
    assert VehicleClassifier.classify("1") == "客车"
    assert VehicleClassifier.classify(2) == "客车"

def test_classify_invalid():
    with pytest.raises(ValueError):
        VehicleClassifier.classify("abc")

# tests/test_type_conversion.py
def test_safe_int_conversion():
    assert safe_int_conversion("123") == 123
    assert safe_int_conversion("123.45") == 123
    assert safe_int_conversion(None) == 0
    assert safe_int_conversion("abc", default=-1) == -1
```

---

## 📊 重构优先级

| 优先级 | 问题 | 影响 | 工作量 | 截止时间 |
|-------|------|------|--------|---------|
| P0 | 裸except替换 | 🔴 生产崩溃 | 4小时 | 立即 |
| P0 | 类型转换安全化 | 🔴 数据丢失 | 3小时 | 立即 |
| P1 | 魔法数字消除 | 🟡 可维护性 | 2小时 | 本周 |
| P1 | 重复代码抽取 | 🟡 可维护性 | 3小时 | 本周 |
| P1 | 单元测试 | 🟡 回归风险 | 8小时 | 本周 |
| P2 | 性能优化 | 🟢 体验 | 6小时 | 下周 |

**总工作量**：约26小时（3-4个工作日）

---

## 🔧 重构步骤

### Step 1: 创建工具模块（2小时）
```bash
# 创建公共工具
touch utils/type_conversion.py
touch utils/vehicle_classifier.py
touch utils/constants.py
touch utils/logger.py
```

### Step 2: 替换裸except（4小时）
```bash
# 使用脚本辅助
python scripts/refactor_exceptions.py
```

### Step 3: 添加类型提示（2小时）
```bash
# 使用mypy检查
mypy dgm_gantry_generator.py --strict
```

### Step 4: 添加单元测试（8小时）
```bash
pytest tests/ --cov=. --cov-report=html
```

### Step 5: 性能优化（6小时）
```bash
# 使用profiler分析
python -m cProfile -o profile.stats dgm_gantry_generator.py
```

---

## 📝 重构检查清单

### 代码质量
- [ ] pylint评分 > 8.0（当前: 未知）
- [ ] mypy --strict无错误
- [ ] 0个裸except
- [ ] 0个魔法数字
- [ ] 测试覆盖率 > 80%

### 性能
- [ ] 生成50条数据 < 60秒
- [ ] 内存使用 < 500MB
- [ ] API调用次数 < 20次

### 文档
- [ ] 所有公共函数有docstring
- [ ] README包含使用示例
- [ ] API文档自动生成

---

## 🎯 重构后的代码示例

```python
# ✅ 重构后的代码风格
from typing import Dict, List, Optional
from utils.type_conversion import safe_int_conversion
from utils.vehicle_classifier import VehicleClassifier
from utils.constants import CONSTANTS
from utils.logger import get_logger

logger = get_logger(__name__)

class ImprovedSampleFilter:
    """改进的样本过滤器（符合SOLID原则）"""
    
    def __init__(self, constants: BusinessConstants = CONSTANTS):
        self.constants = constants
        self.classifier = VehicleClassifier()
    
    def validate_sample(self, sample: Dict) -> tuple[float, List[str]]:
        """验证样本质量
        
        Args:
            sample: 待验证的样本
            
        Returns:
            (质量分数, 问题列表)
            
        Raises:
            ValueError: 样本格式错误
        """
        if not sample:
            raise ValueError("样本不能为空")
        
        score = 1.0
        issues = []
        
        # 1. 时间一致性检查
        try:
            time_score, time_issues = self._check_time_consistency(sample)
            score *= time_score
            issues.extend(time_issues)
        except ValueError as e:
            logger.error(f"时间检查失败: {e}")
            score *= 0.5
            issues.append(f"时间验证错误: {e}")
        
        # 2. 费用逻辑检查
        try:
            fee_score, fee_issues = self._check_fee_logic(sample)
            score *= fee_score
            issues.extend(fee_issues)
        except ValueError as e:
            logger.error(f"费用检查失败: {e}")
            score *= 0.6
            issues.append(f"费用验证错误: {e}")
        
        return score, issues
    
    def _check_time_consistency(self, sample: Dict) -> tuple[float, List[str]]:
        """检查时间一致性（单一职责）"""
        issues = []
        
        entrance_str = sample.get("entrance_time")
        transaction_str = sample.get("transaction_time")
        
        if not entrance_str or not transaction_str:
            return 0.8, ["缺少时间字段"]
        
        try:
            entrance = datetime.fromisoformat(entrance_str)
            transaction = datetime.fromisoformat(transaction_str)
        except ValueError as e:
            raise ValueError(f"时间格式错误: {e}") from e
        
        if entrance >= transaction:
            issues.append("入口时间晚于交易时间")
            return 0.3, issues
        
        diff_hours = (transaction - entrance).total_seconds() / 3600
        if diff_hours > 6:
            issues.append(f"行程时间过长: {diff_hours:.1f}小时")
            return 0.8, issues
        
        return 1.0, issues
```

---

## ✅ 验收标准

### 重构完成后必须满足：
1. **pylint评分 ≥ 8.5**
2. **mypy --strict 通过**
3. **pytest覆盖率 ≥ 80%**
4. **0个裸except**
5. **生成时间 < 60秒（50条）**
6. **代码行数减少20%+**

---

## 🚀 下一步行动

**建议执行顺序**：
1. 立即运行 `pylint dgm_gantry_generator.py` 查看具体问题
2. 创建 `utils/` 模块
3. 修复P0问题（异常处理+类型转换）
4. 添加单元测试
5. 重新评估代码质量

**预期提升**：
- 代码评级：B- → A-
- 生产可用性：❌ → ✅
- 维护成本：高 → 中

需要我开始执行重构吗？
