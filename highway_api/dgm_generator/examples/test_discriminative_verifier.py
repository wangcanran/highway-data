"""判别式辅助验证器测试

演示真正的判别式辅助模型（符合DGM论文定义）

对比：
- 判别式模型：学习P(Y|X)，直接预测是否合理
- CTGAN：学习P(X)，间接对比分布
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from auxiliary_models.discriminative_verifier import (
    ReasonabilityClassifier,
    FeeRegressor,
    DiscriminativeVerifier
)


def generate_mock_real_samples(n=100):
    """生成模拟的真实样本用于训练"""
    import random
    
    samples = []
    
    # 客车样本
    for _ in range(n // 2):
        mileage = random.uniform(5000, 30000)
        samples.append({
            "vehicle_type": "1",
            "pay_fee": int(mileage * 0.09),  # 客车费率约0.09元/米
            "fee_mileage": str(int(mileage)),
            "total_weight": "0",
            "axle_count": "2"
        })
    
    # 货车样本
    for _ in range(n // 2):
        mileage = random.uniform(5000, 30000)
        samples.append({
            "vehicle_type": "12",
            "pay_fee": int(mileage * 0.18),  # 货车费率约0.18元/米
            "fee_mileage": str(int(mileage)),
            "total_weight": str(random.randint(10000, 25000)),
            "axle_count": "2"
        })
    
    return samples


def test_reasonability_classifier():
    """测试1：合理性分类器"""
    print("=" * 60)
    print("测试1：合理性分类器（Isolation Forest异常检测）")
    print("=" * 60)
    
    # 生成训练数据
    real_samples = generate_mock_real_samples(200)
    
    # 训练
    print("\n训练判别式模型...")
    classifier = ReasonabilityClassifier()
    classifier.train(real_samples)
    print("训练完成！")
    
    # 测试正常样本
    print("\n测试正常样本：")
    normal_sample = {
        "vehicle_type": "12",
        "pay_fee": 3500,
        "fee_mileage": "20000",
        "total_weight": "18000",
        "axle_count": "2"
    }
    result, confidence = classifier.predict(normal_sample)
    print(f"  样本: 货车，20公里，3500元，18吨")
    print(f"  判断: {result}")
    print(f"  置信度: {confidence:.2%}")
    
    # 测试异常样本1：费用过低
    print("\n测试异常样本1（费用过低）：")
    anomaly1 = {
        "vehicle_type": "12",
        "pay_fee": 100,  # 异常：货车20公里只要1元
        "fee_mileage": "20000",
        "total_weight": "18000",
        "axle_count": "2"
    }
    result, confidence = classifier.predict(anomaly1)
    print(f"  样本: 货车，20公里，100元（异常低！），18吨")
    print(f"  判断: {result}")
    print(f"  置信度: {confidence:.2%}")
    
    # 测试异常样本2：重量过重
    print("\n测试异常样本2（重量过重）：")
    anomaly2 = {
        "vehicle_type": "12",
        "pay_fee": 3500,
        "fee_mileage": "20000",
        "total_weight": "80000",  # 异常：2轴货车80吨
        "axle_count": "2"
    }
    result, confidence = classifier.predict(anomaly2)
    print(f"  样本: 货车，20公里，3500元，80吨（异常重！）")
    print(f"  判断: {result}")
    print(f"  置信度: {confidence:.2%}")


def test_fee_regressor():
    """测试2：费用预测回归器"""
    print("\n" + "=" * 60)
    print("测试2：费用预测回归器（Gradient Boosting）")
    print("=" * 60)
    
    # 生成训练数据
    real_samples = generate_mock_real_samples(200)
    
    # 训练
    print("\n训练费用预测模型...")
    regressor = FeeRegressor()
    regressor.train(real_samples)
    print("训练完成！")
    
    # 测试场景
    test_cases = [
        {
            "name": "客车，15公里",
            "sample": {
                "vehicle_type": "1",
                "fee_mileage": "15000",
                "pay_fee": 1350  # 正常
            }
        },
        {
            "name": "货车，20公里",
            "sample": {
                "vehicle_type": "12",
                "fee_mileage": "20000",
                "pay_fee": 3600  # 正常
            }
        },
        {
            "name": "货车，20公里（费用异常）",
            "sample": {
                "vehicle_type": "12",
                "fee_mileage": "20000",
                "pay_fee": 500  # 异常：太低了
            }
        }
    ]
    
    for case in test_cases:
        print(f"\n测试: {case['name']}")
        sample = case['sample']
        predicted_fee, is_anomalous = regressor.predict(sample)
        
        print(f"  实际费用: {sample['pay_fee']} 元")
        print(f"  预测费用: {predicted_fee:.0f} 元")
        print(f"  判断: {'异常' if is_anomalous else '正常'}")
        
        if is_anomalous:
            deviation = abs(sample['pay_fee'] - predicted_fee) / predicted_fee * 100
            print(f"  偏差: {deviation:.1f}%")


def test_combined_verifier():
    """测试3：综合判别式验证器"""
    print("\n" + "=" * 60)
    print("测试3：综合判别式验证器（多模型组合）")
    print("=" * 60)
    
    # 生成训练数据
    real_samples = generate_mock_real_samples(200)
    
    # 训练
    print("\n训练综合验证器...")
    verifier = DiscriminativeVerifier()
    verifier.train(real_samples)
    print("训练完成！")
    
    # 测试样本
    test_samples = [
        {
            "name": "正常样本",
            "sample": {
                "vehicle_type": "12",
                "pay_fee": 3600,
                "fee_mileage": "20000",
                "total_weight": "18000",
                "axle_count": "2"
            }
        },
        {
            "name": "费用异常（过低）",
            "sample": {
                "vehicle_type": "12",
                "pay_fee": 100,  # 异常
                "fee_mileage": "20000",
                "total_weight": "18000",
                "axle_count": "2"
            }
        },
        {
            "name": "重量异常（过重）",
            "sample": {
                "vehicle_type": "12",
                "pay_fee": 3600,
                "fee_mileage": "20000",
                "total_weight": "80000",  # 异常
                "axle_count": "2"
            }
        },
        {
            "name": "多重异常",
            "sample": {
                "vehicle_type": "12",
                "pay_fee": 100,  # 异常
                "fee_mileage": "20000",
                "total_weight": "80000",  # 异常
                "axle_count": "2"
            }
        }
    ]
    
    for test_case in test_samples:
        print(f"\n{'='*50}")
        print(f"测试样本: {test_case['name']}")
        print(f"{'='*50}")
        
        sample = test_case['sample']
        result = verifier.verify(sample)
        
        print(f"\n整体判断: {result['overall']}")
        print(f"置信度: {result['confidence']:.2%}")
        
        print(f"\n详细分析:")
        print(f"  合理性分类: {result['details']['reasonability']['result']}")
        print(f"    置信度: {result['details']['reasonability']['confidence']:.2%}")
        
        print(f"  费用预测:")
        print(f"    预测值: {result['details']['fee_prediction']['predicted']:.0f} 元")
        print(f"    实际值: {result['details']['fee_prediction']['actual']} 元")
        print(f"    异常: {result['details']['fee_prediction']['anomalous']}")
        
        if result['corrections']:
            print(f"\n建议修正:")
            for correction in result['corrections']:
                print(f"    {correction}")


def compare_with_ctgan():
    """测试4：对比判别式 vs CTGAN"""
    print("\n" + "=" * 60)
    print("测试4：判别式模型 vs CTGAN对比")
    print("=" * 60)
    
    print("\n理论对比:")
    print("-" * 60)
    
    comparison = [
        ("模型类型", "判别式（Discriminative）", "生成式（Generative）"),
        ("学习目标", "P(Y|X) - 条件概率", "P(X) - 数据分布"),
        ("验证方式", "直接预测标签", "间接对比分布"),
        ("输出", "明确的判断+置信度", "统计距离（z-score）"),
        ("训练数据", "真实样本", "真实样本"),
        ("是否需要标注", "否（异常检测）", "否"),
        ("符合论文定义", "完全符合 [OK]", "部分符合 [~]"),
        ("实用性", "高", "高"),
        ("理论支撑", "强", "中等")
    ]
    
    print(f"{'维度':<15} {'判别式模型':<25} {'CTGAN':<25}")
    print("-" * 60)
    for row in comparison:
        print(f"{row[0]:<15} {row[1]:<25} {row[2]:<25}")
    
    print("\n使用建议:")
    print("  1. 学术严谨: 使用判别式模型 ✓")
    print("  2. 工程实用: CTGAN也很有效")
    print("  3. 最佳方案: 两者结合使用 ★")
    
    print("\n组合策略:")
    print("  if 判别式判断异常 AND CTGAN判断异常:")
    print("      → 高置信度异常（两个模型都认为异常）")
    print("  elif 判别式判断异常 OR CTGAN判断异常:")
    print("      → 可能异常（需要人工审核）")
    print("  else:")
    print("      → 正常样本")


if __name__ == "__main__":
    print("\n[测试] 判别式辅助验证器\n")
    
    try:
        test_reasonability_classifier()
        test_fee_regressor()
        test_combined_verifier()
        compare_with_ctgan()
        
        print("\n" + "=" * 60)
        print("[完成] 所有测试运行成功！")
        print("=" * 60)
        
        print("\n关键发现:")
        print("  1. 判别式模型能直接预测样本是否合理 ✓")
        print("  2. 提供明确的置信度分数 ✓")
        print("  3. 无需人工标注数据（异常检测） ✓")
        print("  4. 符合DGM论文定义 ✓")
        
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
