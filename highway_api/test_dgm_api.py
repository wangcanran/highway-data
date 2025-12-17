"""
DGM API测试脚本
测试DGM数据生成API的各个端点
"""
import requests
import json
import time

# 配置
BASE_URL = "http://localhost:5000"


def test_quick_generate():
    """测试快速生成（统一接口）"""
    print("\n" + "="*60)
    print("测试1: 快速生成（统一接口）")
    print("="*60)
    
    # 方法1: GET请求
    print("\n[GET请求]")
    url = f"{BASE_URL}/api/generate/gantry?method=dgm&count=3"
    print(f"URL: {url}")
    
    response = requests.get(url)
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"生成样本数: {len(data)}")
        if data:
            print(f"第一个样本: {json.dumps(data[0], indent=2, ensure_ascii=False)}")
    else:
        print(f"错误: {response.text}")
    
    # 方法2: POST请求
    print("\n[POST请求]")
    url = f"{BASE_URL}/api/generate/gantry"
    payload = {"method": "dgm", "count": 3}
    print(f"URL: {url}")
    print(f"Payload: {payload}")
    
    response = requests.post(url, json=payload)
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"生成样本数: {len(data)}")
    else:
        print(f"错误: {response.text}")


def test_full_workflow():
    """测试完整工作流程"""
    print("\n" + "="*60)
    print("测试2: 完整工作流程")
    print("="*60)
    
    # 步骤1: 检查状态
    print("\n[步骤1] 检查初始化状态")
    response = requests.get(f"{BASE_URL}/api/dgm/status")
    status = response.json()
    print(f"状态: {json.dumps(status, indent=2)}")
    
    # 步骤2: 初始化（如果未初始化）
    if not status.get('is_initialized', False):
        print("\n[步骤2] 初始化生成器")
        init_payload = {
            "real_data_limit": 100,
            "evaluation_limit": 500,
            "use_discriminative": True
        }
        print(f"初始化参数: {init_payload}")
        
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/api/dgm/initialize", json=init_payload)
        init_time = time.time() - start_time
        
        result = response.json()
        print(f"初始化结果: {json.dumps(result, indent=2)}")
        print(f"初始化耗时: {init_time:.2f}秒")
    else:
        print("\n[步骤2] 生成器已初始化，跳过")
    
    # 步骤3: 查看学习到的统计信息
    print("\n[步骤3] 查看学习到的统计信息")
    response = requests.get(f"{BASE_URL}/api/dgm/stats")
    stats = response.json()
    
    if stats['status'] == 'success':
        learned = stats['learned_stats']
        if 'by_vehicle' in learned:
            passenger = learned['by_vehicle'].get('passenger', {})
            print(f"客车统计:")
            print(f"  - 费用均值: {passenger.get('pay_fee', {}).get('mean', 'N/A')}")
            print(f"  - 里程均值: {passenger.get('fee_mileage', {}).get('mean', 'N/A')}")
            print(f"  - 相关系数: {passenger.get('correlation', 'N/A')}")
    
    # 步骤4: 生成数据（小批量）
    print("\n[步骤4] 生成10条样本（含评估）")
    gen_payload = {
        "count": 10,
        "verbose": False
    }
    
    start_time = time.time()
    response = requests.post(f"{BASE_URL}/api/dgm/generate", json=gen_payload)
    gen_time = time.time() - start_time
    
    result = response.json()
    
    if result['status'] == 'success':
        print(f"✓ 生成成功")
        print(f"  - 样本数: {result['count']}")
        print(f"  - 生成耗时: {gen_time:.2f}秒")
        
        # 评估结果
        direct = result['evaluation']['direct']
        indirect = result['evaluation']['indirect']
        
        print(f"\n评估结果:")
        print(f"  Direct Evaluation: {direct['overall_score']:.2%}")
        print(f"    - Faithfulness: {direct['faithfulness']:.2%}")
        print(f"    - Diversity: {direct['diversity']:.2%}")
        print(f"    - Benchmark相似度: {direct['benchmark_similarity']:.2%}")
        
        print(f"\n  Indirect Evaluation: {indirect['overall_score']:.2%}")
        for task, score in indirect['tasks'].items():
            print(f"    - {task}: {score:.2%}")
        
        # 质量分布
        quality = result['quality_distribution']
        print(f"\n质量分布:")
        print(f"  - 高质量: {quality.get('high', 0)}")
        print(f"  - 中等质量: {quality.get('medium', 0)}")
        print(f"  - 低质量: {quality.get('low', 0)}")
        
        # 样本预览
        print(f"\n样本预览（前2条）:")
        for i, sample in enumerate(result['samples'][:2], 1):
            print(f"\n样本{i}:")
            print(f"  - 门架ID: {sample.get('gantry_id')}")
            print(f"  - 路段: {sample.get('section_name')}")
            print(f"  - 车型: {sample.get('vehicle_type')}")
            print(f"  - 费用: {sample.get('pay_fee')}分")
            print(f"  - 里程: {sample.get('fee_mileage')}米")
    else:
        print(f"✗ 生成失败: {result.get('message')}")


def test_method_comparison():
    """测试不同方法的对比"""
    print("\n" + "="*60)
    print("测试3: 方法对比（rule vs model vs dgm）")
    print("="*60)
    
    methods = ['rule', 'model', 'dgm']
    count = 5
    
    for method in methods:
        print(f"\n[{method.upper()}方法]")
        
        start_time = time.time()
        response = requests.get(
            f"{BASE_URL}/api/generate/gantry?method={method}&count={count}"
        )
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            samples = response.json()
            print(f"✓ 生成{len(samples)}条样本，耗时: {elapsed:.2f}秒")
            
            if samples:
                sample = samples[0]
                print(f"  示例: 门架={sample.get('gantry_id')}, 费用={sample.get('pay_fee')}")
        else:
            print(f"✗ 失败: {response.text}")


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("DGM API 测试套件")
    print("="*60)
    
    try:
        # 测试1: 快速生成
        test_quick_generate()
        
        # 测试2: 完整流程
        test_full_workflow()
        
        # 测试3: 方法对比
        test_method_comparison()
        
        print("\n" + "="*60)
        print("✓ 所有测试完成")
        print("="*60)
        
    except requests.exceptions.ConnectionError:
        print("\n✗ 错误: 无法连接到API服务器")
        print(f"请确保Flask应用正在运行: {BASE_URL}")
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")


if __name__ == "__main__":
    main()
