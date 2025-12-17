#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单演示 - 带完整错误处理
"""

from dgm_gantry_generator import DGMGantryGenerator
import json
import traceback

def simple_demo():
    """简单演示，带完整错误处理"""
    print("=" * 70)
    print("DGM数据生成器 - 简单演示")
    print("=" * 70)
    
    try:
        # 步骤1: 创建生成器
        print("\n[步骤1] 创建生成器...")
        generator = DGMGantryGenerator()
        print("  [OK] 生成器创建成功")
        print(f"  - DirectEvaluator: {generator.direct_evaluator is not None}")
        print(f"  - BenchmarkEvaluator: {generator.benchmark_evaluator is not None}")
        print(f"  - Benchmark连接到DirectEvaluator: {generator.direct_evaluator.benchmark_evaluator is not None}")
        
        # 步骤2: 加载真实数据
        print("\n[步骤2] 加载真实数据...")
        try:
            generator.load_real_samples(limit=20, verbose=True)
            print("  [OK] 真实数据加载成功")
        except Exception as e:
            print(f"  [警告] 加载真实数据失败: {e}")
            print("  继续使用默认配置...")
        
        # 步骤3: 生成数据
        print("\n[步骤3] 生成数据...")
        print("  正在生成5条数据（可能需要几分钟）...")
        result = generator.generate(count=5, verbose=True)
        
        # 步骤4: 检查返回结构
        print("\n[步骤4] 检查返回结构...")
        print(f"  返回的键: {list(result.keys())}")
        
        if 'samples' in result:
            print(f"  [OK] 生成了 {len(result['samples'])} 条数据")
        
        if 'evaluation' not in result:
            print("  [错误] 缺少'evaluation'键")
            return
        
        evaluation = result['evaluation']
        print(f"  evaluation的键: {list(evaluation.keys())}")
        
        if 'direct' not in evaluation:
            print("  [错误] evaluation中缺少'direct'键")
            return
        
        # 步骤5: 显示评估结果
        print("\n[步骤5] 显示评估结果...")
        print("=" * 70)
        
        direct = evaluation['direct']
        print(f"\n[Direct Evaluation]")
        print(f"  综合得分: {direct.get('overall_score', 0):.2%}")
        
        # Faithfulness
        if 'faithfulness' in direct:
            faith = direct['faithfulness']
            print(f"\n  1. Faithfulness: {faith.get('score', 0):.2%}")
            
            # Constraint Check
            if 'constraint_check' in faith:
                const = faith['constraint_check']
                print(f"     [Constraint Check]")
                print(f"     - 约束遵守率: {const.get('score', 0):.2%}")
                print(f"     - 合格: {const.get('valid_count', 0)}/{const.get('total_count', 0)}")
            
            # Benchmark Evaluation (在Faithfulness下！)
            if 'benchmark_evaluation' in faith:
                bench = faith['benchmark_evaluation']
                print(f"     [Benchmark Evaluation] ← 在Faithfulness下！")
                print(f"     - 整体相似度: {bench.get('overall_similarity', 0):.2%}")
                print(f"     - 分布相似度: {bench.get('distribution_similarity', {}).get('score', 0):.2%}")
                print(f"     - 统计特征: {bench.get('statistical_similarity', {}).get('score', 0):.2%}")
                print(f"     - 时间模式: {bench.get('temporal_similarity', {}).get('score', 0):.2%}")
                print(f"     - 相关性: {bench.get('correlation_similarity', {}).get('score', 0):.2%}")
            else:
                print(f"     [注] 无Benchmark评估（未加载真实数据）")
        
        # Diversity
        if 'diversity' in direct:
            div = direct['diversity']
            print(f"\n  2. Diversity: {div.get('score', 0):.2%}")
            print(f"     - 样本独特性: {div.get('uniqueness', 0):.2%}")
        
        # Indirect Evaluation
        if 'indirect' in evaluation:
            indirect = evaluation['indirect']
            print(f"\n[Indirect Evaluation]")
            
            if 'open_evaluation' in indirect:
                open_eval = indirect['open_evaluation']
                print(f"  Open Evaluation:")
                if 'anomaly_detection' in open_eval:
                    print(f"    - 异常检测: {open_eval['anomaly_detection'].get('precision', 0):.2%}")
                if 'fee_prediction' in open_eval:
                    print(f"    - 费用预测: {open_eval['fee_prediction'].get('accuracy', 0):.2%}")
        
        # 关键亮点
        print("\n" + "=" * 70)
        print("[关键亮点] 符合图2")
        print("=" * 70)
        print("\n1. Benchmark评估现在在 Faithfulness 下")
        print("   这是 Direct Evaluation 的一部分")
        print("\n2. Faithfulness = 约束检查 + Benchmark评估")
        if 'faithfulness' in direct:
            faith = direct['faithfulness']
            if 'constraint_check' in faith and 'benchmark_evaluation' in faith:
                const_score = faith['constraint_check']['score']
                bench_score = faith['benchmark_evaluation']['overall_similarity']
                print(f"   = 50% × {const_score:.2%} + 50% × {bench_score:.2%}")
                print(f"   = {faith['score']:.2%}")
        
        print("\n" + "=" * 70)
        print("演示成功！")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n[错误] 错误: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    simple_demo()
