#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DGM数据生成器 - 新结构演示
展示Benchmark评估在Faithfulness下的新架构（符合图2）
"""

from dgm_gantry_generator import DGMGantryGenerator
import json

def demo():
    """演示新的评估结构"""
    print("=" * 70)
    print("DGM数据生成器 - 新结构演示（符合图2）")
    print("=" * 70)
    
    # 创建生成器
    print("\n[步骤1] 创建生成器")
    generator = DGMGantryGenerator()
    print("  已创建，默认分布已设置")
    
    # 从数据库加载真实数据
    print("\n[步骤2] 从数据库加载真实数据")
    generator.load_real_samples(
        source=None,      # None = 从数据库
        limit=50,         # 只加载50条，快速演示
        verbose=True
    )
    
    # 生成少量数据进行快速演示
    print("\n[步骤3] 生成数据（少量，快速演示）")
    result = generator.generate(count=10, verbose=True)
    
    # 展示新的评估结构
    print("\n" + "=" * 70)
    print("新的评估结构（符合图2）")
    print("=" * 70)
    
    # 先检查返回结构
    if 'evaluation' not in result:
        print("\n❌ 错误：result中没有'evaluation'键")
        print(f"result的键: {list(result.keys())}")
        return result
    
    evaluation = result['evaluation']
    
    # 检查evaluation结构
    if 'direct' not in evaluation:
        print("\n❌ 错误：evaluation中没有'direct'键")
        print(f"evaluation的键: {list(evaluation.keys())}")
        return result
    
    # ========== I. Direct Evaluation ==========
    print("\n[I. Direct Evaluation]")
    print("-" * 70)
    
    direct = evaluation['direct']
    
    # 1. Faithfulness (包含 Constraint Check + Benchmark)
    faith = direct['faithfulness']
    print(f"\n1. Data Faithfulness: {faith['score']:.2%}")
    
    # 1.1 Constraint Check
    if 'constraint_check' in faith:
        const = faith['constraint_check']
        print(f"\n   [Constraint Check - 约束检查]")
        print(f"   - 约束遵守率: {const['score']:.2%}")
        print(f"   - 合格样本: {const['valid_count']}/{const['total_count']}")
    
    # 1.2 Benchmark Evaluation (在Faithfulness下！)
    if 'benchmark_evaluation' in faith:
        bench = faith['benchmark_evaluation']
        print(f"\n   [Benchmark Evaluation - 与真实数据对比]")
        print(f"   - 整体相似度: {bench['overall_similarity']:.2%}")
        print(f"   - 分布相似度: {bench['distribution_similarity']['score']:.2%}")
        print(f"   - 统计特征: {bench['statistical_similarity']['score']:.2%}")
        print(f"   - 时间模式: {bench['temporal_similarity']['score']:.2%}")
        print(f"   - 相关性: {bench['correlation_similarity']['score']:.2%}")
    
    # 2. Diversity
    div = direct['diversity']
    print(f"\n2. Data Diversity: {div['score']:.2%}")
    print(f"   - 样本独特性: {div['uniqueness']:.2%}")
    
    # ========== II. Indirect Evaluation ==========
    print("\n\n[II. Indirect Evaluation]")
    print("-" * 70)
    
    indirect = evaluation['indirect']
    
    # Open Evaluation
    if 'open_evaluation' in indirect:
        open_eval = indirect['open_evaluation']
        print(f"\nOpen Evaluation - 下游任务:")
        if 'anomaly_detection' in open_eval:
            print(f"  - 异常检测: {open_eval['anomaly_detection']['precision']:.2%}")
        if 'fee_prediction' in open_eval:
            print(f"  - 费用预测: {open_eval['fee_prediction']['accuracy']:.2%}")
    
    # Benchmark Evaluation (任务性能对比，待实现)
    print(f"\n  [注] Benchmark Evaluation (任务性能对比) 待实现")
    
    # ========== 关键亮点 ==========
    print("\n\n" + "=" * 70)
    print("关键亮点（符合图2）")
    print("=" * 70)
    
    print("\n✓ Benchmark评估现在在 Faithfulness 下")
    print("  这是 Direct Evaluation 的一部分，用于评估数据质量")
    
    print("\n✓ Faithfulness = 50% Constraint Check + 50% Benchmark")
    if 'constraint_check' in faith and 'benchmark_evaluation' in faith:
        const_score = faith['constraint_check']['score']
        bench_score = faith['benchmark_evaluation']['overall_similarity']
        print(f"  = 50% × {const_score:.2%} + 50% × {bench_score:.2%}")
        print(f"  = {faith['score']:.2%}")
    
    print("\n✓ Indirect Evaluation 保留用于下游任务和性能对比")
    
    # 保存结果
    print("\n" + "=" * 70)
    print("[步骤4] 保存结果")
    with open('demo_result.json', 'w', encoding='utf-8') as f:
        json.dump({
            'samples': result['samples'][:3],  # 只保存前3个样本
            'evaluation_structure': {
                'direct': {
                    'faithfulness': {
                        'has_constraint_check': 'constraint_check' in faith,
                        'has_benchmark': 'benchmark_evaluation' in faith,
                        'score': faith['score']
                    },
                    'diversity': {
                        'score': div['score']
                    }
                },
                'indirect': {
                    'has_open_evaluation': 'open_evaluation' in indirect,
                    'has_benchmark': 'benchmark_evaluation' in indirect
                }
            }
        }, f, ensure_ascii=False, indent=2)
    print("  已保存到 demo_result.json")
    
    print("\n" + "=" * 70)
    print("演示完成！")
    print("=" * 70)
    
    return result


if __name__ == "__main__":
    try:
        demo()
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
