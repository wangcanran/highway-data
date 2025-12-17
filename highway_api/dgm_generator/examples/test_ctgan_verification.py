"""CTGAN辅助验证测试示例

演示如何使用CTGAN作为辅助模型验证LLM生成的数据
"""
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from auxiliary_models.ctgan_verifier import CTGANVerifier, HybridGenerator


def demo_single_verification():
    """演示：验证单个样本"""
    print("=" * 60)
    print("示例1：CTGAN验证单个LLM样本")
    print("=" * 60)
    
    # 模拟一个LLM生成的样本（有明显异常）
    llm_sample = {
        "gantry_transaction_id": "TEST123",
        "vehicle_type": "12",  # 货车
        "axle_count": "2",
        "pay_fee": 100,  # [!] 异常！货车费用不可能这么低
        "fee_mileage": "50000",  # 50公里
        "total_weight": "50000",  # [!] 异常！2轴货车不可能50吨
        "section_id": "S0014530010"
    }
    
    print("\nLLM生成的样本（包含异常值）:")
    print(f"  车型: 12 (货车)")
    print(f"  费用: {llm_sample['pay_fee']} 元 [!] 太低了！")
    print(f"  重量: {llm_sample['total_weight']} kg [!] 太重了！")
    
    # 加载CTGAN验证器
    model_path = "../../models/gantry_ctgan.pkl"
    
    if not os.path.exists(model_path):
        print(f"\n[WARNING] CTGAN模型文件不存在: {model_path}")
        print("请先运行 train_gantry_ctgan.py 训练模型")
        return
    
    verifier = CTGANVerifier(model_path)
    
    # 验证并修正
    print("\n使用CTGAN验证...")
    verified_sample = verifier.verify_sample(llm_sample, threshold_std=2.0)
    
    # 查看修正结果
    if "_ctgan_corrections" in verified_sample:
        print("\n[OK] 发现异常并已修正:")
        for correction in verified_sample["_ctgan_corrections"]:
            print(f"  {correction}")
        
        print(f"\n修正后的样本:")
        print(f"  费用: {verified_sample['pay_fee']} 元 [OK]")
        print(f"  重量: {verified_sample['total_weight']} kg [OK]")
    else:
        print("\n[OK] 样本正常，无需修正")


def demo_batch_verification():
    """演示：批量验证"""
    print("\n" + "=" * 60)
    print("示例2：批量验证LLM样本")
    print("=" * 60)
    
    # 模拟多个LLM样本
    llm_samples = [
        {
            "gantry_transaction_id": f"TEST{i}",
            "vehicle_type": "12",
            "pay_fee": 3500 if i % 3 != 0 else 100,  # 每3个就有1个异常
            "fee_mileage": "50000",
            "total_weight": "18000" if i % 3 != 0 else "50000",
            "section_id": "S0014530010"
        }
        for i in range(10)
    ]
    
    print(f"\nLLM生成了 {len(llm_samples)} 个样本")
    print(f"其中 {sum(1 for s in llm_samples if s['pay_fee'] == 100)} 个有费用异常")
    print(f"其中 {sum(1 for s in llm_samples if s['total_weight'] == '50000')} 个有重量异常")
    
    model_path = "../../models/gantry_ctgan.pkl"
    if not os.path.exists(model_path):
        print(f"\n[WARNING] CTGAN模型文件不存在")
        return
    
    verifier = CTGANVerifier(model_path)
    
    # 批量验证
    print("\n批量验证中...")
    verified_samples = verifier.verify_batch(llm_samples, threshold_std=2.0)
    
    # 统计修正情况
    corrected_samples = [s for s in verified_samples if "_ctgan_corrections" in s]
    
    print(f"\n[OK] 验证完成:")
    print(f"  总样本数: {len(verified_samples)}")
    print(f"  修正样本数: {len(corrected_samples)}")
    print(f"  修正率: {len(corrected_samples) / len(verified_samples) * 100:.1f}%")
    
    if corrected_samples:
        print(f"\n修正详情（前3个）:")
        for i, sample in enumerate(corrected_samples[:3]):
            print(f"\n  样本{i+1} ({sample['gantry_transaction_id']}):")
            for correction in sample["_ctgan_corrections"]:
                print(f"    - {correction}")


def demo_hybrid_generation():
    """演示：混合生成"""
    print("\n" + "=" * 60)
    print("示例3：LLM + CTGAN 混合生成")
    print("=" * 60)
    
    print("\n[WARNING] 需要完整的DGM生成器环境")
    print("这个示例需要:")
    print("  1. 配置好的OpenAI API")
    print("  2. 数据库连接")
    print("  3. 完整的DGM生成器")
    
    print("\n可以运行以下命令测试:")
    print("  python examples/hybrid_generation_demo.py")


def demo_distribution_analysis():
    """演示：分析CTGAN学习的分布"""
    print("\n" + "=" * 60)
    print("示例4：分析CTGAN学习的数据分布")
    print("=" * 60)
    
    model_path = "../../models/gantry_ctgan.pkl"
    if not os.path.exists(model_path):
        print(f"\n[WARNING] CTGAN模型文件不存在")
        return
    
    verifier = CTGANVerifier(model_path)
    
    # 分析不同车型的费用分布
    vehicle_types = [
        ("1", "客车"),
        ("12", "2轴货车"),
        ("13", "3轴货车")
    ]
    
    print("\nCTGAN学习到的费用分布:")
    print("-" * 60)
    
    for vtype, name in vehicle_types:
        stats = verifier.get_distribution_stats("pay_fee", vehicle_type=vtype)
        
        if stats:
            print(f"\n{name} (车型{vtype}):")
            print(f"  平均费用: {stats['mean']:.0f} 元")
            print(f"  标准差: {stats['std']:.0f} 元")
            print(f"  范围: {stats['min']:.0f} ~ {stats['max']:.0f} 元")
            print(f"  中位数: {stats['median']:.0f} 元")
    
    # 分析重量分布
    print("\n\nCTGAN学习到的重量分布:")
    print("-" * 60)
    
    for vtype, name in vehicle_types[1:]:  # 只看货车
        stats = verifier.get_distribution_stats("total_weight", vehicle_type=vtype)
        
        if stats:
            print(f"\n{name} (车型{vtype}):")
            print(f"  平均重量: {stats['mean']:.0f} kg ({stats['mean']/1000:.1f}吨)")
            print(f"  标准差: {stats['std']:.0f} kg")
            print(f"  范围: {stats['min']:.0f} ~ {stats['max']:.0f} kg")


if __name__ == "__main__":
    print("\n[CTGAN] 辅助验证器测试\n")
    
    # 运行所有示例
    try:
        demo_single_verification()
        demo_batch_verification()
        demo_distribution_analysis()
        demo_hybrid_generation()
        
        print("\n" + "=" * 60)
        print("[OK] 所有示例运行完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] 错误: {e}")
        import traceback
        traceback.print_exc()
