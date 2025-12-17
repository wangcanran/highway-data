# 项目结构说明

## 📁 完整目录树

```
dgm_generator/                          # 项目根目录
│
├── __init__.py                         # 包初始化文件
├── dgm_gantry_generator.py             # 主生成器（3500+行）
├── requirements.txt                    # Python依赖
├── .gitignore                          # Git忽略文件
│
├── README.md                           # 项目说明
├── QUICKSTART.md                       # 快速开始指南
├── PROJECT_STRUCTURE.md                # 本文件
│
├── utils/                              # 工具模块 ⭐
│   ├── __init__.py
│   ├── type_conversion.py              # 类型转换（安全转换、提取函数）
│   ├── vehicle_classifier.py           # 车辆分类（消除重复代码）
│   └── constants.py                    # 业务常量（消除魔法数字）
│
├── tests/                              # 单元测试 🧪
│   ├── __init__.py
│   ├── test_type_conversion.py         # 类型转换测试（48个用例）
│   └── test_vehicle_classifier.py      # 车辆分类测试（30个用例）
│
└── docs/                               # 文档目录 📚
    ├── DGM_FRAMEWORK_COMPLETE.md       # DGM框架100%实现报告
    ├── DGM_IMPLEMENTATION_STATUS.md    # 实现状态清单
    ├── CODE_REFACTORING_PLAN.md        # 代码重构计划
    ├── REFACTORING_GUIDE.md            # 重构指南（示例+最佳实践）
    ├── EVALUATION_FRAMEWORK.md         # 评估框架说明
    └── ... (其他文档)
```

---

## 📂 各目录说明

### 根目录文件

| 文件 | 说明 | 重要性 |
|------|------|--------|
| `dgm_gantry_generator.py` | **核心主文件**，包含所有DGM框架实现 | ⭐⭐⭐⭐⭐ |
| `__init__.py` | Python包初始化，定义版本号 | ⭐⭐⭐ |
| `requirements.txt` | 项目依赖列表 | ⭐⭐⭐⭐ |
| `README.md` | 项目主文档 | ⭐⭐⭐⭐⭐ |
| `QUICKSTART.md` | 5分钟快速上手 | ⭐⭐⭐⭐ |
| `.gitignore` | Git版本控制忽略规则 | ⭐⭐⭐ |

### utils/ - 工具模块

**作用**：消除代码问题，提高代码质量

| 文件 | 解决的问题 | 提供的功能 |
|------|-----------|-----------|
| `type_conversion.py` | ❌ 裸except<br>❌ 类型转换崩溃 | ✅ `safe_int_conversion()`<br>✅ `safe_float_conversion()`<br>✅ `safe_datetime_conversion()`<br>✅ `extract_mileage()`, `extract_fee()` |
| `vehicle_classifier.py` | ❌ 重复代码15+次<br>❌ 硬编码判断 | ✅ `VehicleClassifier.classify()`<br>✅ `is_passenger()`, `is_truck()`<br>✅ `get_expected_axles()` |
| `constants.py` | ❌ 魔法数字50+处<br>❌ 硬编码配置 | ✅ `CONSTANTS.axle_weights`<br>✅ `CONSTANTS.score_weights`<br>✅ `CONSTANTS.time_periods` |

### tests/ - 单元测试

**作用**：确保代码质量，防止回归

| 文件 | 测试内容 | 用例数 |
|------|----------|--------|
| `test_type_conversion.py` | 类型转换的各种场景 | 48个 |
| `test_vehicle_classifier.py` | 车辆分类逻辑 | 30个 |

**运行方式**：
```bash
pytest tests/ -v
pytest tests/ --cov=utils --cov-report=html
```

### docs/ - 文档目录

**作用**：项目知识库

| 文档类型 | 文件 | 说明 |
|---------|------|------|
| **框架实现** | `DGM_FRAMEWORK_COMPLETE.md` | DGM框架100%完成报告 |
| **实现状态** | `DGM_IMPLEMENTATION_STATUS.md` | 功能清单和完成度 |
| **代码质量** | `CODE_REFACTORING_PLAN.md` | 重构计划（评级B-→A-） |
| **重构指南** | `REFACTORING_GUIDE.md` | 如何使用新工具模块 |
| **评估框架** | `EVALUATION_FRAMEWORK.md` | 评估方法详解 |

---

## 🎯 文件依赖关系

```
dgm_gantry_generator.py
    ↓ (将来会导入)
utils/
    ├── type_conversion.py
    ├── vehicle_classifier.py
    └── constants.py
        ↓ (被测试)
tests/
    ├── test_type_conversion.py
    └── test_vehicle_classifier.py
```

**当前状态**：
- ✅ 工具模块已创建
- ✅ 单元测试已完成
- ⏳ 主文件尚未迁移（待重构）

**重构后**：
主文件将导入工具模块，消除82+处裸except和50+个魔法数字。

---

## 📦 使用方式

### 命令行使用

```bash
cd dgm_generator
python dgm_gantry_generator.py --count 50 --output data.json
```

### Python包使用

```python
# 方式1：从项目根目录导入
from dgm_generator.dgm_gantry_generator import DGMGantryGenerator

# 方式2：使用工具模块
from dgm_generator.utils.type_conversion import safe_int_conversion
from dgm_generator.utils.vehicle_classifier import VehicleClassifier
```

---

## 🔄 项目演进

### 阶段1：初始版本（当前）
```
dgm_gantry_generator.py (3500行单文件)
```

### 阶段2：模块化（进行中）
```
dgm_generator/
├── dgm_gantry_generator.py
├── utils/               # ✅ 已完成
└── tests/               # ✅ 已完成
```

### 阶段3：重构版本（下一步）
```
dgm_generator/
├── dgm_gantry_generator.py  # 使用utils模块重构
├── utils/                    # ✅ 
├── tests/                    # ✅ + 更多测试
└── docs/                     # ✅ 完整文档
```

### 阶段4：生产版本（目标）
```
dgm_generator/
├── core/                     # 核心模块拆分
│   ├── generation.py
│   ├── curation.py
│   └── evaluation.py
├── utils/                    # ✅
├── tests/                    # 80%+覆盖率
├── docs/                     # ✅
└── examples/                 # 示例代码
```

---

## 💡 开发建议

### 新增功能
1. 在 `utils/` 中创建新的工具模块
2. 在 `tests/` 中添加对应测试
3. 在 `docs/` 中更新文档

### 重构代码
1. 参考 `docs/REFACTORING_GUIDE.md`
2. 使用 `utils/` 中的工具函数
3. 运行测试确保无回归

### 添加文档
1. 技术文档放在 `docs/`
2. 使用说明放在根目录
3. API文档使用docstring

---

## 🎓 学习路径

**新手**：
1. `README.md` - 了解项目
2. `QUICKSTART.md` - 快速上手
3. 运行测试 - 理解功能

**开发者**：
1. `dgm_gantry_generator.py` - 理解架构
2. `utils/` - 学习工具模块
3. `docs/REFACTORING_GUIDE.md` - 最佳实践

**贡献者**：
1. `docs/CODE_REFACTORING_PLAN.md` - 了解改进方向
2. `tests/` - 编写测试
3. 提交PR

---

## 📞 支持

- 📖 文档: `docs/`
- 🧪 测试: `tests/`
- 💬 Issue: GitHub Issues

**版本**: 1.0.0  
**最后更新**: 2025-12-05
