#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
对已生成的数据进行Benchmark评估

使用方法：
1. 如果有真实数据：
   python evaluate_generated_data.py --generated generated.json --real real_data.json

2. 如果没有真实数据，使用部分生成数据作为模拟基准（仅用于演示）：
   python evaluate_generated_data.py --generated generated.json --demo
"""

import json
import sys
from dgm_gantry_generator import BenchmarkEvaluator

def evaluate_with_real_data(generated_file: str, real_file: str):
    """使用真实数据进行Benchmark评估"""
    print("\n" + "=" * 70)
    print("Benchmark评估：对比生成数据与真实数据")
    print("=" * 70)
    
    # 1. 加载生成数据
    print(f"\n[步骤1] 加载生成数据: {generated_file}")
    try:
        with open(generated_file, 'r', encoding='utf-8') as f:
            generated_samples = json.load(f)
        print(f"  [OK] 已加载 {len(generated_samples)} 条生成数据")
    except Exception as e:
        print(f"  [ERROR] 加载失败: {e}")
        return
    
    # 2. 加载真实数据
    print(f"\n[步骤2] 加载真实数据: {real_file}")
    try:
        with open(real_file, 'r', encoding='utf-8') as f:
            real_samples = json.load(f)
        print(f"  [OK] 已加载 {len(real_samples)} 条真实数据作为基准")
    except Exception as e:
        print(f"  [ERROR] 加载失败: {e}")
        return
    
    # 3. 创建评估器并加载真实数据
    print(f"\n[步骤3] 初始化Benchmark评估器...")
    evaluator = BenchmarkEvaluator(real_samples=real_samples)
    print(f"  [OK] 已配置基准数据")
    
    # 4. 执行评估
    print(f"\n[步骤4] 执行Benchmark评估...")
    print("  (正在计算统计分布、数值特征、时间模式、相关性...)")
    
    try:
        benchmark_result = evaluator.evaluate(generated_samples)
    except Exception as e:
        print(f"  [ERROR] 评估失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 5. 显示评估结果
    print_evaluation_report(benchmark_result, len(generated_samples), len(real_samples))


def evaluate_demo_mode(generated_file: str):
    """演示模式：使用部分生成数据作为"模拟真实数据"进行评估"""
    print("\n" + "=" * 70)
    print("Benchmark评估：演示模式")
    print("=" * 70)
    print("\n[注意] 此模式使用前50条数据作为'模拟真实数据'，")
    print("       后50条作为'生成数据'进行对比，仅用于演示评估功能。")
    print("       真实场景请使用实际的真实数据！")
    
    # 1. 加载数据
    print(f"\n[步骤1] 加载数据: {generated_file}")
    try:
        with open(generated_file, 'r', encoding='utf-8') as f:
            all_samples = json.load(f)
        print(f"  [OK] 已加载 {len(all_samples)} 条数据")
    except Exception as e:
        print(f"  [ERROR] 加载失败: {e}")
        return
    
    if len(all_samples) < 20:
        print("  [ERROR] 数据量太少，至少需要20条数据")
        return
    
    # 2. 分割数据
    split_point = len(all_samples) // 2
    real_samples = all_samples[:split_point]
    generated_samples = all_samples[split_point:]
    
    print(f"\n[步骤2] 分割数据")
    print(f"  模拟真实数据: {len(real_samples)} 条")
    print(f"  模拟生成数据: {len(generated_samples)} 条")
    
    # 3. 创建评估器
    print(f"\n[步骤3] 初始化Benchmark评估器...")
    evaluator = BenchmarkEvaluator(real_samples=real_samples)
    print(f"  [OK] 已配置基准数据")
    
    # 4. 执行评估
    print(f"\n[步骤4] 执行Benchmark评估...")
    print("  (正在计算统计分布、数值特征、时间模式、相关性...)")
    
    try:
        benchmark_result = evaluator.evaluate(generated_samples)
    except Exception as e:
        print(f"  [ERROR] 评估失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 5. 显示评估结果
    print_evaluation_report(benchmark_result, len(generated_samples), len(real_samples))


def print_evaluation_report(benchmark_result: dict, gen_count: int, real_count: int):
    """打印评估报告"""
    print("\n" + "=" * 70)
    print("评估报告")
    print("=" * 70)
    
    print(f"\n数据规模:")
    print(f"  生成数据: {gen_count} 条")
    print(f"  真实数据（基准）: {real_count} 条")
    
    # 核心指标
    print("\n" + "─" * 70)
    print("【核心指标】")
    print("─" * 70)
    
    overall_sim = benchmark_result.get('overall_similarity', 0)
    print(f"\n>> 整体相似度: {overall_sim:.2%}")
    
    # 相似度解读
    if overall_sim >= 0.95:
        quality = "优秀"
        comment = "生成数据与真实数据高度相似，可以替代真实数据使用"
    elif overall_sim >= 0.85:
        quality = "良好"
        comment = "生成数据基本符合真实数据特征，可用但建议优化"
    else:
        quality = "需改进"
        comment = "生成数据与真实数据差异较大，需要优化Generation配置"
    
    print(f"   质量评级: {quality}")
    print(f"   建议: {comment}")
    
    # 详细维度
    print("\n" + "─" * 70)
    print("【详细评估】")
    print("─" * 70)
    
    # 1. 分布相似度
    dist_sim = benchmark_result.get('distribution_similarity', {})
    print(f"\n1. 统计分布相似度: {dist_sim.get('score', 0):.2%} (权重: 35%)")
    for field in ['vehicle_type', 'section_id', 'media_type']:
        if field in dist_sim:
            field_result = dist_sim[field]
            js_div = field_result['js_divergence']
            similarity = field_result['similarity']
            
            # 显示实际分布对比
            gen_dist = field_result.get('generated_dist', {})
            real_dist = field_result.get('real_dist', {})
            
            print(f"\n   {field}: {similarity:.2%} (JS散度: {js_div:.4f})")
            
            # 只显示前3个最常见的值
            if gen_dist and real_dist:
                print(f"      真实分布: {dict(list(real_dist.items())[:3])}")
                print(f"      生成分布: {dict(list(gen_dist.items())[:3])}")
    
    # 2. 统计特征相似度
    stat_sim = benchmark_result.get('statistical_similarity', {})
    print(f"\n2. 数值特征相似度: {stat_sim.get('score', 0):.2%} (权重: 25%)")
    for field in ['pay_fee', 'fee_mileage']:
        if field in stat_sim:
            field_result = stat_sim[field]
            mean_sim = field_result['mean_similarity']
            std_sim = field_result['std_similarity']
            
            gen_stats = field_result.get('generated', {})
            real_stats = field_result.get('real', {})
            
            print(f"\n   {field}:")
            print(f"      均值相似度: {mean_sim:.2%}")
            if real_stats:
                print(f"         真实: {real_stats.get('mean', 0):.0f}, 生成: {gen_stats.get('mean', 0):.0f}")
            print(f"      标准差相似度: {std_sim:.2%}")
            if real_stats:
                print(f"         真实: {real_stats.get('std', 0):.0f}, 生成: {gen_stats.get('std', 0):.0f}")
    
    # 3. 时间模式相似度
    temp_sim = benchmark_result.get('temporal_similarity', {})
    print(f"\n3. 时间模式相似度: {temp_sim.get('score', 0):.2%} (权重: 20%)")
    if 'generated_distribution' in temp_sim and 'real_distribution' in temp_sim:
        gen_time = temp_sim['generated_distribution']
        real_time = temp_sim['real_distribution']
        
        print(f"\n   时段分布对比:")
        for period in ['早高峰', '平峰', '晚高峰', '深夜']:
            real_pct = real_time.get(period, 0)
            gen_pct = gen_time.get(period, 0)
            diff = abs(gen_pct - real_pct)
            print(f"      {period}: 真实 {real_pct:.1%}, 生成 {gen_pct:.1%}, 差异 {diff:.1%}")
    
    # 4. 相关性相似度
    corr_sim = benchmark_result.get('correlation_similarity', {})
    print(f"\n4. 关键相关性相似度: {corr_sim.get('score', 0):.2%} (权重: 20%)")
    if 'generated_correlation' in corr_sim and 'real_correlation' in corr_sim:
        gen_corr = corr_sim['generated_correlation']
        real_corr = corr_sim['real_correlation']
        diff = corr_sim.get('difference', 0)
        
        print(f"\n   费用-里程相关系数:")
        print(f"      真实数据: {real_corr:.4f}")
        print(f"      生成数据: {gen_corr:.4f}")
        print(f"      差异: {diff:.4f}")
    
    # 优化建议
    print("\n" + "─" * 70)
    print("【优化建议】")
    print("─" * 70)
    
    suggestions = []
    
    if dist_sim.get('score', 1) < 0.90:
        suggestions.append("- 分布相似度较低，建议增加样例数量或检查样例的多样性")
    
    if stat_sim.get('score', 1) < 0.90:
        suggestions.append("- 统计特征相似度较低，建议检查数值生成逻辑（费用、里程计算）")
    
    if temp_sim.get('score', 1) < 0.90:
        suggestions.append("- 时间模式相似度较低，建议优化时间相关的提示词或约束")
    
    if corr_sim.get('score', 1) < 0.90:
        suggestions.append("- 相关性相似度较低，建议检查业务规则的理解（如费用与里程的关系）")
    
    if not suggestions:
        print("\n>> 各维度表现均良好，无需特别优化")
    else:
        print()
        for suggestion in suggestions:
            print(suggestion)
    
    print("\n" + "=" * 70)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='对已生成的数据进行Benchmark评估',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法：

  1. 使用真实数据作为基准：
     python evaluate_generated_data.py --generated generated.json --real real_data.json
  
  2. 演示模式（使用部分生成数据作为模拟基准）：
     python evaluate_generated_data.py --generated generated.json --demo
        """
    )
    
    parser.add_argument('--generated', '-g', 
                       default='generated.json',
                       help='生成数据的文件路径 (默认: generated.json)')
    
    parser.add_argument('--real', '-r',
                       help='真实数据的文件路径（用作基准）')
    
    parser.add_argument('--demo', '-d',
                       action='store_true',
                       help='演示模式：使用部分生成数据作为模拟基准')
    
    args = parser.parse_args()
    
    # 检查参数
    if not args.real and not args.demo:
        print("\n错误：必须指定 --real 或 --demo 参数")
        print("\n使用 --help 查看详细说明")
        parser.print_help()
        sys.exit(1)
    
    # 执行评估
    if args.demo:
        evaluate_demo_mode(args.generated)
    else:
        evaluate_with_real_data(args.generated, args.real)


if __name__ == "__main__":
    main()
