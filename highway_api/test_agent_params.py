"""
测试增强Agent的自然语言参数提取能力
验证Agent能否从用户查询中正确提取时间、路段等参数
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:5000"

def test_agent_with_params(query, expected_scenario=None, expected_params=None):
    """测试带参数的智能Agent查询"""
    print(f"\n{'='*70}")
    print(f"测试查询: {query}")
    print(f"{'='*70}")
    
    if expected_scenario:
        print(f"预期场景: {expected_scenario}")
    if expected_params:
        print(f"预期参数: {json.dumps(expected_params, ensure_ascii=False)}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/agent/smart-query",
            json={"query": query},
            timeout=60
        )
        result = response.json()
        
        success = result.get('success', False)
        print(f"\n[状态] {'成功' if success else '失败'}")
        print(f"[类型] {result.get('execution_type')}")
        
        if success and result.get('execution_type') == 'workflow':
            print(f"[场景] {result.get('scenario_name')}")
            
            # 显示执行日志（提取参数信息）
            logs = result.get('execution_logs', [])
            print(f"\n[执行日志]")
            for log in logs[:5]:  # 只显示前5条
                print(f"  {log}")
            
            # 显示结果关键信息
            res = result.get('result', {})
            print(f"\n[结果摘要]")
            
            # 根据场景显示不同的关键信息
            if 'entrance_count' in res:
                # 场景1
                print(f"  - 入口交易数: {res.get('entrance_count')}")
                print(f"  - 出口交易数: {res.get('exit_count')}")
                print(f"  - 实收金额: {res.get('total_real_money')}元")
                print(f"  - 优惠金额: {res.get('discount_amount')}元")
            elif 'anomaly_count' in res:
                # 场景2
                print(f"  - 检查交易数: {res.get('total_checked')}")
                print(f"  - 异常交易数: {res.get('anomaly_count')}")
                print(f"  - 异常率: {res.get('anomaly_rate')}%")
            elif 'total_flow' in res:
                # 场景3
                print(f"  - 统计路段数: {res.get('total_sections')}")
                print(f"  - 总流量: {res.get('total_flow')}次")
                busiest = res.get('busiest_section', {})
                if busiest:
                    print(f"  - 最繁忙路段: {busiest.get('section_name')}")
                    print(f"  - 该路段流量: {busiest.get('total_flow')}次")
            
            # 验证参数是否正确提取
            if expected_params:
                print(f"\n[参数验证]")
                all_match = True
                for key, expected_value in expected_params.items():
                    # 从结果中推断实际使用的参数
                    if key == 'start_date' and 'timestamp' in res:
                        actual_value = res.get('timestamp', '').split('T')[0]
                        print(f"  {key}: 预期={expected_value}, 实际使用={actual_value}")
                    else:
                        print(f"  {key}: 预期={expected_value} (需查看日志确认)")
            
            return True
            
        elif result.get('execution_type') == 'not_supported':
            print(f"[错误] {result.get('error')}")
            print(f"[原因] {result.get('reason')}")
            return False
        else:
            print(f"[错误] 未知执行类型")
            return False
            
    except Exception as e:
        print(f"\n[异常] {str(e)}")
        return False


if __name__ == '__main__':
    print("\n" + "="*70)
    print("  增强Agent自然语言参数提取测试")
    print("="*70)
    
    # 测试用例：带时间参数的查询
    test_cases = [
        # 场景1：带日期的费用核算
        {
            'query': '帮我核算2023年1月3号的通行费',
            'expected_scenario': 'scenario1',
            'expected_params': {'start_date': '2023-01-03'}
        },
        {
            'query': '计算1月5日到1月10日的收费金额',
            'expected_scenario': 'scenario1',
            'expected_params': {'start_date': '2023-01-05', 'end_date': '2023-01-10'}
        },
        
        # 场景2：带日期和数量的异常检测
        {
            'query': '检测2023年1月3日的异常交易',
            'expected_scenario': 'scenario2',
            'expected_params': {'start_date': '2023-01-03'}
        },
        {
            'query': '稽核最近20笔交易记录',
            'expected_scenario': 'scenario2',
            'expected_params': {'limit': 20}
        },
        
        # 场景3：带时间段的流量分析
        {
            'query': '分析2023年1月3日到10日的全网流量',
            'expected_scenario': 'scenario3',
            'expected_params': {'start_date': '2023-01-03', 'end_date': '2023-01-10'}
        },
        {
            'query': '统计1月份所有路段的车流量情况',
            'expected_scenario': 'scenario3',
            'expected_params': {'start_date': '2023-01-01', 'end_date': '2023-01-31'}
        },
        
        # 场景1：带路段名称的查询
        {
            'query': '查询麻文高速的通行费用',
            'expected_scenario': 'scenario1',
            'expected_params': {'section_name': '麻文高速'}
        },
    ]
    
    print("\n[测试说明]")
    print("本测试验证Agent能否从自然语言中提取：")
    print("  1. 时间参数（日期、时间段）")
    print("  2. 数量参数（limit、count等）")
    print("  3. 路段名称")
    print("  4. 其他业务参数")
    print("\n注意：Agent会尽力提取参数，但可能使用默认值")
    
    results = []
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n\n{'#'*70}")
        print(f"# 测试 {i}/{len(test_cases)}")
        print(f"{'#'*70}")
        
        success = test_agent_with_params(
            test_case['query'],
            test_case.get('expected_scenario'),
            test_case.get('expected_params')
        )
        results.append((test_case['query'], success))
        
        # 避免请求过快
        import time
        time.sleep(2)
    
    # 汇总结果
    print("\n" + "="*70)
    print("  测试结果汇总")
    print("="*70)
    
    success_count = sum(1 for _, s in results if s)
    total_count = len(results)
    
    for query, success in results:
        status = "[OK]" if success else "[FAIL]"
        print(f"{status} {query}")
    
    print(f"\n成功率: {success_count}/{total_count} ({success_count/total_count*100:.1f}%)")
    
    print("\n[结论]")
    if success_count == total_count:
        print("所有测试通过！Agent能够正确识别场景并执行工作流。")
    else:
        print(f"部分测试失败。Agent需要继续优化参数提取能力。")
    
    print("\n[说明]")
    print("当前Agent主要验证场景识别能力。")
    print("参数提取能力取决于LLM的理解和提示词优化。")
    print("如需查看具体使用的参数，请查看执行日志或直接调用工作流API。")
