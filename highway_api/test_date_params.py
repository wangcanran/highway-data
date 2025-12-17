"""
测试日期参数是否正确传递给工作流
"""
import requests
import json

BASE_URL = "http://localhost:5000"

def test_date_extraction(query):
    """测试Agent是否正确提取日期参数"""
    print(f"\n{'='*60}")
    print(f"测试查询: {query}")
    print(f"{'='*60}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/agent/smart-query",
            json={"query": query},
            timeout=30
        )
        result = response.json()
        
        print(f"\n[执行状态] {'成功' if result.get('success') else '失败'}")
        
        if result.get('success'):
            print(f"[场景名称] {result.get('scenario_name')}")
            
            # 检查执行日志中的参数信息
            logs = result.get('execution_logs', [])
            print(f"\n[执行日志]")
            for log in logs:
                print(f"  {log}")
            
            # 显示结果数据
            res = result.get('result', {})
            print(f"\n[结果数据]")
            print(f"  入口交易数: {res.get('entrance_count', 0)}")
            print(f"  出口交易数: {res.get('exit_count', 0)}")
            print(f"  实收金额: {res.get('total_real_money', 0)}元")
            print(f"  时间戳: {res.get('timestamp', '')}")
            
            return True
        else:
            print(f"[错误] {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"\n[异常] {str(e)}")
        return False


if __name__ == '__main__':
    print("\n" + "="*60)
    print("  日期参数传递测试")
    print("="*60)
    print("\n说明：测试不同日期的查询，观察输出是否变化")
    print("注意：需要先重启Flask服务才能加载新代码！")
    
    # 测试不同日期
    test_cases = [
        "帮我核算2023年1月3号的通行费",
        "帮我核算2023年2月1号的通行费",
        "帮我核算2023年12月22号的通行费",
    ]
    
    results = []
    for query in test_cases:
        success = test_date_extraction(query)
        results.append((query, success))
        
        import time
        time.sleep(2)
    
    # 汇总
    print("\n" + "="*60)
    print("  测试结果汇总")
    print("="*60)
    
    for query, success in results:
        status = "[OK]" if success else "[FAIL]"
        print(f"{status} {query}")
    
    print("\n说明：")
    print("- 如果不同日期返回相同的数据，说明参数没有正确传递")
    print("- 如果返回的数据不同，说明参数传递正确")
    print("- 请在Flask终端中查看 [DEBUG] 开头的调试日志")
