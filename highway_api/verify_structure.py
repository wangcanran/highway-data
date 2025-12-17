#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证新评估结构 - 快速测试
不调用LLM，只验证结构是否正确
"""

from dgm_gantry_generator import DGMGantryGenerator, DirectEvaluator, BenchmarkEvaluator

def verify_structure():
    """验证新的评估结构设置"""
    print("=" * 70)
    print("验证新评估结构（图2对齐）")
    print("=" * 70)
    
    # 1. 验证生成器初始化
    print("\n[验证1] 生成器初始化")
    generator = DGMGantryGenerator()
    
    assert generator.direct_evaluator is not None, "DirectEvaluator未创建"
    assert generator.benchmark_evaluator is not None, "BenchmarkEvaluator未创建"
    print("  [OK] 评估器创建成功")
    
    # 2. 验证Benchmark连接到DirectEvaluator
    print("\n[验证2] Benchmark连接")
    assert generator.direct_evaluator.benchmark_evaluator is not None, \
        "Benchmark未连接到DirectEvaluator"
    assert generator.direct_evaluator.benchmark_evaluator is generator.benchmark_evaluator, \
        "Benchmark引用不一致"
    print("  [OK] Benchmark已正确连接到DirectEvaluator（用于Faithfulness）")
    
    # 3. 验证target_distribution默认值
    print("\n[验证3] 默认分布")
    assert generator.target_distribution is not None, "target_distribution为None"
    assert isinstance(generator.target_distribution, dict), "target_distribution不是字典"
    assert 'vehicle' in generator.target_distribution, "缺少vehicle分布"
    assert 'time' in generator.target_distribution, "缺少time分布"
    print("  [OK] 默认分布设置正确")
    print(f"    - 车型: {list(generator.target_distribution['vehicle'].keys())}")
    print(f"    - 时段: {list(generator.target_distribution['time'].keys())}")
    
    # 4. 模拟Faithfulness评估（包含Benchmark）
    print("\n[验证4] Faithfulness评估结构")
    
    # 创建测试样本
    test_samples = [
        {
            "gantry_transaction_id": "TEST001",
            "vehicle_type": "1",
            "transaction_time": "2023-03-15 10:00:00",
            "entrance_time": "2023-03-15 09:00:00",
            "pay_fee": "100",
            "discount_fee": "90",
            "fee_mileage": "10000",
            "section_id": "S0010530010"
        }
    ]
    
    # 加载一些真实数据到Benchmark
    try:
        generator.load_real_samples(limit=10, verbose=False)
        print("  [OK] 成功加载真实数据到Benchmark")
    except Exception as e:
        print(f"  [警告] 无法加载真实数据: {e}")
        print("    （这是正常的，如果数据库不可用）")
    
    # 执行评估
    result = generator.direct_evaluator.evaluate(test_samples)
    
    # 验证结构
    assert 'faithfulness' in result, "缺少faithfulness"
    assert 'diversity' in result, "缺少diversity"
    
    faith = result['faithfulness']
    assert 'score' in faith, "Faithfulness缺少score"
    assert 'constraint_check' in faith, "Faithfulness缺少constraint_check"
    
    print("  [OK] Faithfulness结构正确")
    print(f"    - 有constraint_check: {'constraint_check' in faith}")
    print(f"    - 有benchmark_evaluation: {'benchmark_evaluation' in faith}")
    print(f"    - 忠实度得分: {faith['score']:.2%}")
    
    if 'benchmark_evaluation' in faith:
        bench = faith['benchmark_evaluation']
        print(f"    - Benchmark相似度: {bench.get('overall_similarity', 0):.2%}")
    
    # 5. 验证评估报告方法存在
    print("\n[验证5] 评估报告方法")
    assert hasattr(generator, '_print_evaluation_report'), "缺少_print_evaluation_report方法"
    print("  [OK] 评估报告方法存在")
    
    # 总结
    print("\n" + "=" * 70)
    print("验证结果汇总")
    print("=" * 70)
    print("\n[成功] 所有结构验证通过！")
    print("\n新结构特点：")
    print("  1. Benchmark在Faithfulness下（符合图2）")
    print("  2. Faithfulness = Constraint Check + Benchmark")
    print("  3. DirectEvaluator持有BenchmarkEvaluator引用")
    print("  4. target_distribution有合理默认值")
    print("\n准备就绪，可以运行完整测试！")
    print("=" * 70)


if __name__ == "__main__":
    try:
        verify_structure()
    except AssertionError as e:
        print(f"\n[失败] 验证失败: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"\n[错误] 错误: {e}")
        import traceback
        traceback.print_exc()
