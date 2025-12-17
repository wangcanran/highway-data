"""
测试增强Agent的中文查询识别能力
"""
import requests
import json

BASE_URL = "http://localhost:5000"

def test_agent(query):
    """测试智能Agent"""
    print(f"\n{'='*60}")
    print(f"查询: {query}")
    print(f"{'='*60}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/agent/smart-query",
            json={"query": query},
            timeout=30
        )
        result = response.json()
        
        print(f"状态: {'[OK] 成功' if result.get('success') else '[FAIL] 失败'}")
        print(f"执行类型: {result.get('execution_type')}")
        
        if result.get('success'):
            print(f"场景名称: {result.get('scenario_name')}")
            print(f"场景描述: {result.get('scenario_description')}")
            print(f"\n执行日志:")
            for log in result.get('execution_logs', []):
                print(f"  {log}")
            
            print(f"\n结果摘要:")
            res = result.get('result', {})
            for key, value in list(res.items())[:5]:
                print(f"  {key}: {value}")
        else:
            print(f"错误: {result.get('error')}")
            print(f"原因: {result.get('reason')}")
            print(f"建议: {result.get('suggestion')}")
        
        return result.get('success', False)
        
    except Exception as e:
        print(f"[ERROR] 请求失败: {str(e)}")
        return False


if __name__ == '__main__':
    print("\n" + "="*60)
    print("  增强Agent中文查询测试")
    print("="*60)
    
    # 测试用例
    test_cases = [
        # 场景1测试
        ("帮我核算通行费", "场景1"),
        ("计算收费金额", "场景1"),
        ("费用结算", "场景1"),
        
        # 场景2测试
        ("检测异常交易", "场景2"),
        ("稽核交易记录", "场景2"),
        
        # 场景3测试
        ("分析全网流量", "场景3"),
        ("统计所有路段的车流量", "场景3"),
        
        # 简单查询（应拒绝）
        ("查询路段信息", "简单查询"),
    ]
    
    results = []
    for query, expected in test_cases:
        print(f"\n预期: {expected}")
        success = test_agent(query)
        results.append((query, expected, success))
    
    # 汇总
    print("\n" + "="*60)
    print("  测试结果汇总")
    print("="*60)
    
    success_count = sum(1 for _, _, s in results if s)
    total_count = len([r for r in results if "简单查询" not in r[1]])  # 不计入简单查询
    
    for query, expected, success in results:
        status = "[OK]" if success else "[FAIL]"
        print(f"{status} {query} (预期: {expected})")
    
    print(f"\n工作流识别成功率: {success_count}/{total_count} ({success_count/total_count*100:.1f}%)")
