# CTGAN数据格式修复说明

## 🐛 问题描述

### 症状
CTGAN生成的数值字段被拼接成字符串：
```python
# 错误的输出
total_weight: "0.00.018000.00.018000..."
fee_mileage: "14670.017165.07765.014670..."
```

### 根本原因
训练时**没有明确指定数值字段的数据类型**，导致CTGAN将数值字段当做字符串处理。

---

## ✅ 修复方案

### 1. 明确数值类型转换

在 `train_gantry_ctgan.py` 的 `load_real_gantry_data` 函数中添加：

```python
# 数值字段明确转换为数值类型
numerical_fields = [
    "pay_fee", "discount_fee", "fee", "fee_mileage",
    "total_weight", "obu_fee_sum_before", "obu_fee_sum_after",
    "pay_fee_prov_sum_local"
]

for col in numerical_fields:
    if col in df.columns:
        # 转换为数值类型，无法转换的设为NaN
        df[col] = pd.to_numeric(df[col], errors='coerce')
        # 填充NaN为0
        df[col] = df[col].fillna(0)
```

### 2. 整数字段转换

```python
# 整数字段转换为int
integer_fields = ["axle_count", "vehicle_type", "media_type", "gantry_type",
                  "transaction_type", "pass_state", "entrance_lane_type", "cpu_card_type"]

for col in integer_fields:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        df[col] = df[col].fillna(0).astype(int)
```

### 3. 添加数据验证

```python
# 打印数据统计，确保数据正常
print("\n数据统计检查:")
print(f"DataFrame shape: {df.shape}")
print(f"\n数值字段统计:")
numerical_cols = ["pay_fee", "fee_mileage", "total_weight"]
for col in numerical_cols:
    if col in df.columns:
        print(f"  {col}: mean={df[col].mean():.2f}, std={df[col].std():.2f}, "
              f"min={df[col].min():.2f}, max={df[col].max():.2f}")
```

---

## 🔧 重新训练步骤

### 1. 确认修复已应用

```bash
cd d:\python_code\flaskProject\highway_api

# 检查train_gantry_ctgan.py是否已更新
```

### 2. 重新训练CTGAN

```bash
# 删除旧模型
rm ..\models\gantry_ctgan.pkl

# 重新训练（约5-10分钟）
python train_gantry_ctgan.py
```

### 3. 验证输出

训练时应该看到：
```
Data types after conversion:
pay_fee              float64
fee_mileage          float64
total_weight         float64
vehicle_type         int64
...

数据统计检查:
DataFrame shape: (4800, 26)

数值字段统计:
  pay_fee: mean=1234.56, std=890.12, min=0.00, max=8500.00
  fee_mileage: mean=12345.67, std=8901.23, min=0.00, max=45000.00
  total_weight: mean=12000.00, std=15000.00, min=0.00, max=51000.00
```

### 4. 测试新模型

```bash
# 生成测试数据
python generate_ctgan_10000.py

# 检查生成的数据
python -c "
import pandas as pd
df = pd.read_csv('../models/gantry_ctgan_10000.csv')
print('数据类型:')
print(df[['pay_fee', 'fee_mileage', 'total_weight']].dtypes)
print('\n统计:')
print(df[['pay_fee', 'fee_mileage', 'total_weight']].describe())
"
```

**应该看到**：
```
数据类型:
pay_fee         float64  ✅
fee_mileage     float64  ✅
total_weight    float64  ✅

统计:
              pay_fee  fee_mileage  total_weight
count     10000.000     10000.000     10000.000
mean       1250.340     12500.560     11800.230
std         880.450      8900.120     14500.780
min           0.000         0.000         0.000
max        8400.000     44000.000     51000.000
```

---

## 🧪 集成测试

重新训练后，测试CTGAN验证器：

```bash
cd dgm_generator/examples
python test_ctgan_verification.py
```

**预期结果**：
```
[CTGAN] 辅助验证器测试

示例1：CTGAN验证单个LLM样本
  LLM生成的费用: 100 元 [!] 太低了！
  
[OK] 发现异常并已修正:
  pay_fee: 100 -> 3500 (z-score=2.57, ref_mean=3500)
  
  修正后的样本:
  费用: 3500 元 [OK]  ✅ 数值正常！
  重量: 18000 kg [OK]  ✅ 数值正常！
```

---

## 📊 修复前后对比

### 修复前 ❌
```python
# CTGAN生成的数据
{
    "pay_fee": "100.03500.01200.0",  # 字符串拼接
    "total_weight": "18000.00.00.0"   # 字符串拼接
}

# 验证器无法处理
Field verification failed: Could not convert "100.03500.0" to numeric
```

### 修复后 ✅
```python
# CTGAN生成的数据
{
    "pay_fee": 3500.0,      # 正确的float
    "total_weight": 18000.0  # 正确的float
}

# 验证器正常工作
z_score = |100 - 3500| / 1200 = 2.83
修正: pay_fee: 100 -> 3500 ✅
```

---

## 🎯 关键要点

### 为什么会出现这个问题？

1. **数据库字段可能是VARCHAR类型**
   ```sql
   -- 数据库定义
   pay_fee VARCHAR(20)  -- 不是INT或DECIMAL
   ```

2. **ORM读取后是字符串**
   ```python
   row.pay_fee  # 返回 "3500" (str)，不是 3500 (int)
   ```

3. **CTGAN没有类型提示**
   ```python
   # 错误：CTGAN把字符串当做分类变量
   model.fit(df)  # df['pay_fee'] 是 object类型
   ```

4. **生成时拼接字符串**
   ```python
   # CTGAN学到的是字符串模式
   generated = "100.0" + "3500.0" + "1200.0"  # 拼接！
   ```

### 如何避免？

✅ **总是明确指定数据类型**
```python
df['pay_fee'] = pd.to_numeric(df['pay_fee'], errors='coerce')
```

✅ **训练前检查dtypes**
```python
print(df.dtypes)
# pay_fee应该是float64，不是object
```

✅ **训练后测试生成**
```python
samples = model.sample(5)
assert samples['pay_fee'].dtype == 'float64'
```

---

## 📚 相关资源

- 原始训练脚本: `train_gantry_ctgan.py`
- CTGAN验证器: `dgm_generator/auxiliary_models/ctgan_verifier.py`
- 测试脚本: `dgm_generator/examples/test_ctgan_verification.py`
- 集成文档: `dgm_generator/docs/CTGAN_INTEGRATION.md`

---

## ✅ 检查清单

重新训练前：
- [ ] 确认 `train_gantry_ctgan.py` 已包含数值类型转换代码
- [ ] 数据库连接正常
- [ ] 有足够的数据（建议>=1000条）

训练时：
- [ ] 看到 "Data types after conversion" 输出
- [ ] 数值字段是 `float64` 或 `int64`，不是 `object`
- [ ] 统计信息合理（mean, std在预期范围）

训练后：
- [ ] 生成5个测试样本，数值字段是float
- [ ] 保存的模型文件大小合理（>1MB）
- [ ] 测试集CSV文件正常

验证时：
- [ ] `test_ctgan_verification.py` 运行成功
- [ ] 修正率在10-40%之间（合理范围）
- [ ] 无 "Could not convert xxx to numeric" 错误

---

**修复完成后，CTGAN将成为真正有效的辅助验证模型！** 🎉

---

**版本**: 1.0  
**日期**: 2025-12-05  
**状态**: 修复完成，待重新训练
