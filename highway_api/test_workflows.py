"""
快速测试脚本 - Person 1 & Person 3 功能验证
测试LangGraph工作流和增强型Agent
"""
import requests
import json
import time

BASE_URL = "http://localhost:5000"

def print_result(title, result):
    """格式化打印结果"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print()


def test_workflow_scenarios():
    """测试工作流场景信息查询"""
    print("\n🔍 测试1: 查询所有工作流场景")
    
    try:
        response = requests.get(f"{BASE_URL}/api/workflow/scenarios", timeout=10)
        result = response.json()
        print_result("所有可用场景", result)
        return True
    except Exception as e:
        print(f"❌ 失败: {str(e)}")
        return False


def test_scenario1():
    """测试场景1: 跨路段通行费核算"""
    print("\n💰 测试2: 场景1 - 跨路段通行费核算")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/workflow/execute",
            json={
                "scenario": "scenario1",
                "params": {
                    "start_date": "2023-01-03"
                }
            },
            timeout=30
        )
        result = response.json()
        print_result("场景1执行结果", result)
        
        if result.get('success'):
            print("✅ 场景1执行成功")
            return True
        else:
            print(f"❌ 场景1执行失败: {result.get('error')}")
            return False
    except Exception as e:
        print(f"❌ 失败: {str(e)}")
        return False


def test_scenario2():
    """测试场景2: 异常交易稽核"""
    print("\n🔍 测试3: 场景2 - 异常交易稽核")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/workflow/execute",
            json={
                "scenario": "scenario2",
                "params": {
                    "start_date": "2023-01-03",
                    "limit": 20,
                    "synthetic_count": 5
                }
            },
            timeout=60
        )
        result = response.json()
        print_result("场景2执行结果", result)
        
        if result.get('success'):
            print("✅ 场景2执行成功")
            return True
        else:
            print(f"❌ 场景2执行失败: {result.get('error')}")
            return False
    except Exception as e:
        print(f"❌ 失败: {str(e)}")
        return False


def test_scenario3():
    """测试场景3: 全网流量分析"""
    print("\n📊 测试4: 场景3 - 全网流量分析")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/workflow/execute",
            json={
                "scenario": "scenario3",
                "params": {
                    "start_date": "2023-01-03",
                    "end_date": "2023-01-10"
                }
            },
            timeout=30
        )
        result = response.json()
        print_result("场景3执行结果", result)
        
        if result.get('success'):
            print("✅ 场景3执行成功")
            return True
        else:
            print(f"❌ 场景3执行失败: {result.get('error')}")
            return False
    except Exception as e:
        print(f"❌ 失败: {str(e)}")
        return False


def test_enhanced_agent_workflow():
    """测试增强Agent自动识别工作流"""
    print("\n🤖 测试5: 增强Agent - 自动识别工作流场景")
    
    test_queries = [
        ("帮我核算2023年1月3号的通行费用", "应识别为场景1"),
        ("检测一下最近的异常交易", "应识别为场景2"),
        ("分析全网的流量情况", "应识别为场景3")
    ]
    
    success_count = 0
    
    for query, expected in test_queries:
        print(f"\n📝 查询: {query}")
        print(f"   预期: {expected}")
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/agent/smart-query",
                json={"query": query},
                timeout=60
            )
            result = response.json()
            
            if result.get('execution_type') == 'workflow':
                scenario_name = result.get('scenario_name', 'Unknown')
                print(f"   ✅ 成功识别为工作流: {scenario_name}")
                success_count += 1
            else:
                print(f"   ⚠️  识别为简单API调用")
            
            # 显示简化结果
            if result.get('result'):
                print(f"   结果: {list(result['result'].keys())}")
                
        except Exception as e:
            print(f"   ❌ 失败: {str(e)}")
        
        time.sleep(1)  # 避免API限流
    
    print(f"\n📊 工作流识别成功率: {success_count}/{len(test_queries)}")
    return success_count == len(test_queries)


def test_enhanced_agent_simple():
    """测试增强Agent识别简单查询"""
    print("\n🤖 测试6: 增强Agent - 简单API推荐")
    
    query = "查询路段信息"
    print(f"\n📝 查询: {query}")
    print(f"   预期: 应推荐简单API")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/agent/smart-query",
            json={"query": query},
            timeout=30
        )
        result = response.json()
        
        if result.get('execution_type') == 'simple_api':
            print(f"   ✅ 正确识别为简单查询")
            if result.get('recommendations'):
                print(f"   推荐API数量: {len(result['recommendations'])}")
            return True
        else:
            print(f"   ⚠️  错误识别为工作流")
            return False
            
    except Exception as e:
        print(f"   ❌ 失败: {str(e)}")
        return False


def main():
    """主测试流程"""
    print("\n" + "="*70)
    print("  Person 1 & Person 3 功能测试")
    print("  测试LangGraph工作流和增强型Agent")
    print("="*70)
    
    # 检查服务是否运行
    print("\n🔌 检查服务状态...")
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if response.status_code == 200:
            print("✅ 服务正常运行")
        else:
            print("❌ 服务状态异常")
            return
    except Exception as e:
        print(f"❌ 无法连接到服务: {str(e)}")
        print(f"   请确保服务已启动: python app.py")
        return
    
    # 运行测试
    results = []
    
    # 测试工作流场景查询
    results.append(("场景信息查询", test_workflow_scenarios()))
    
    # 测试3个场景
    results.append(("场景1-通行费核算", test_scenario1()))
    results.append(("场景2-异常交易稽核", test_scenario2()))
    results.append(("场景3-全网流量分析", test_scenario3()))
    
    # 测试增强Agent
    results.append(("Agent-工作流识别", test_enhanced_agent_workflow()))
    results.append(("Agent-简单查询识别", test_enhanced_agent_simple()))
    
    # 汇总结果
    print("\n" + "="*70)
    print("  测试结果汇总")
    print("="*70)
    
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status}  {name}")
    
    success_rate = sum(1 for _, s in results if s) / len(results) * 100
    print(f"\n总体通过率: {success_rate:.1f}% ({sum(1 for _, s in results if s)}/{len(results)})")
    
    if success_rate == 100:
        print("\n🎉 所有测试通过！Person 1 & Person 3 的功能已完成！")
    elif success_rate >= 80:
        print("\n✅ 大部分测试通过，功能基本可用")
    else:
        print("\n⚠️  部分测试失败，需要检查")
    
    print("\n" + "="*70)


if __name__ == '__main__':
    main()
