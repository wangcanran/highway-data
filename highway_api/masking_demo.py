"""
数据脱敏前后对比演示
演示 overweight-rate API 的掩码脱敏效果
"""

import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

# 掩码函数
def mask_section_id(section_id):
    """
    掩码脱敏：保留首尾字符，中间用*替换
    例如：G0001-001 → G*******1
    """
    if not section_id or len(section_id) < 3:
        return '***'
    return section_id[0] + '*' * (len(section_id) - 2) + section_id[-1]

# 模拟原始数据（脱敏前）
original_data = [
    {
        'section_id': 'G0001-001',
        'total_count': 1234,
        'overweight_count': 56,
        'overweight_rate': 0.0454,
        'overweight_percentage': 4.54
    },
    {
        'section_id': 'G0002-003',
        'total_count': 890,
        'overweight_count': 23,
        'overweight_rate': 0.0258,
        'overweight_percentage': 2.58
    },
    {
        'section_id': 'S1001-002',
        'total_count': 2100,
        'overweight_count': 89,
        'overweight_rate': 0.0424,
        'overweight_percentage': 4.24
    }
]

# 脱敏后数据
masked_data = [{
    'section_id': mask_section_id(item['section_id']),
    'section_id_masked': True,
    'total_count': item['total_count'],
    'overweight_count': item['overweight_count'],
    'overweight_rate': item['overweight_rate'],
    'overweight_percentage': item['overweight_percentage']
} for item in original_data]

# 打印对比
print("=" * 60)
print("数据脱敏前后对比 - overweight-rate API")
print("脱敏方法: 掩码(Masking)")
print("=" * 60)

print("\n【脱敏前】原始数据:")
print("-" * 60)
for item in original_data:
    print(f"  section_id: {item['section_id']:<12} | "
          f"total: {item['total_count']:<6} | "
          f"overweight: {item['overweight_count']:<4} | "
          f"rate: {item['overweight_percentage']}%")

print("\n【脱敏后】掩码处理:")
print("-" * 60)
for item in masked_data:
    print(f"  section_id: {item['section_id']:<12} | "
          f"total: {item['total_count']:<6} | "
          f"overweight: {item['overweight_count']:<4} | "
          f"rate: {item['overweight_percentage']}%")

print("\n" + "=" * 60)
print("对比分析:")
print("=" * 60)
print("┌─────────────┬─────────────┬─────────────┐")
print("│   原始值    │   脱敏后    │   保护效果   │")
print("├─────────────┼─────────────┼─────────────┤")
for orig, masked in zip(original_data, masked_data):
    print(f"│ {orig['section_id']:<11} │ {masked['section_id']:<11} │ 无法定位路段 │")
print("└─────────────┴─────────────┴─────────────┘")

print("\n【API 完整响应对比】")
print("\n--- 脱敏前 ---")
response_before = {
    'success': True,
    'data': original_data,
    'category': '合规监测类'
}
print(json.dumps(response_before, indent=2, ensure_ascii=False))

print("\n--- 脱敏后 ---")
response_after = {
    'success': True,
    'data': masked_data,
    'category': '合规监测类',
    'data_masking': {
        'enabled': True,
        'method': '掩码(Masking)',
        'fields': ['section_id'],
        'description': '对路段ID进行掩码处理，保留首尾字符，中间用*替换'
    }
}
print(json.dumps(response_after, indent=2, ensure_ascii=False))

print("\n" + "=" * 60)
print("安全分析:")
print("=" * 60)
print("攻击场景: 攻击者尝试通过 section_id 关联外部数据")
print("├─ 脱敏前: G0001-001 → 可精确定位到具体路段")
print("├─ 脱敏后: G*******1 → 无法确定具体路段")
print("└─ 结论: 掩码有效阻止了关联攻击")
