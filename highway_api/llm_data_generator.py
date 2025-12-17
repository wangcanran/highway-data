"""
基于大模型 (LLM) 的高速公路交易数据生成器

优势：
1. 理解业务语义，生成符合逻辑的数据（如入口时间 < 出口时间）
2. 可通过 prompt 灵活控制生成场景（如"生成超载货车数据"）
3. 字段之间的关联性更合理（如车型与轴数匹配）

使用方法：
    python llm_data_generator.py --type gantry --count 10
    python llm_data_generator.py --type gantry --count 5 --scenario "超载货车"
"""

import json
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional
from openai import OpenAI

import config


# 初始化 OpenAI 客户端
client = OpenAI(
    api_key=config.OPENAI_API_KEY,
    base_url=config.OPENAI_API_BASE,
    timeout=config.REQUEST_TIMEOUT
)


# ==================== Schema 定义 ====================

GANTRY_TRANSACTION_SCHEMA = """
GantryTransaction 门架交易记录表结构：
- gantry_transaction_id: 门架交易ID，格式为 "GT" + 14位时间戳 + 6位随机数，如 "GT20231201103045123456"
- gantry_id: 门架ID，格式为 "G" + 6位数字，如 "G440101"
- gantry_type: 门架类型，"1"=省界门架, "2"=普通门架, "3"=入口门架, "4"=出口门架
- transaction_time: 交易时间，ISO格式，如 "2023-12-01T10:30:45"
- entrance_time: 入口时间，必须早于 transaction_time
- pay_fee: 应付费用（分），整数
- fee: 费用明细，字符串
- discount_fee: 优惠金额（分），整数，不能超过 pay_fee
- media_type: 介质类型，"1"=ETC, "2"=CPC卡, "3"=纸券
- vehicle_type: 车型，"1"=客车, "2"=货车, "3"=专项作业车
- vehicle_sign: 车辆标识，"0"=普通车, "1"=军警车, "2"=紧急车
- transaction_type: 交易类型，"1"=正常, "2"=补费, "3"=退费
- pass_state: 通行状态，"1"=正常, "2"=异常
- axle_count: 轴数，货车2-6轴，客车通常为2轴
- total_weight: 总重量（kg），货车根据轴数有不同限重
- cpu_card_type: CPU卡类型，"1"=记账卡, "2"=储值卡
- fee_mileage: 收费里程（米），字符串
- pass_id: 通行ID，格式为 "PASS" + 14位时间戳 + 8位随机数
- section_id: 路段ID，格式为 "S" + 6位数字
- section_name: 路段名称，如 "广州-深圳高速"

业务规则：
1. entrance_time 必须早于 transaction_time，时间差通常在 30分钟 到 4小时 之间
2. 货车(vehicle_type="2")的 axle_count 范围是 2-6，不同轴数有不同限重：
   - 2轴: 18吨, 3轴: 25吨, 4轴: 31吨, 5轴: 43吨, 6轴: 49吨
3. 客车(vehicle_type="1")的 axle_count 通常为 2，total_weight 通常在 2000-5000kg
4. pay_fee 应该与 fee_mileage 正相关，大约 0.5元/公里 (50分/1000米)
5. discount_fee 不能超过 pay_fee
6. ETC用户(media_type="1") 通常有 5% 的优惠
"""

EXIT_TRANSACTION_SCHEMA = """
ExitTransaction 出口交易记录表结构：
- exit_transaction_id: 出口交易ID
- vehicle_class: 车辆分类，"1"-"4"为客车(按座位数), "11"-"16"为货车(按轴数)
- exit_time: 出口时间，ISO格式
- vehicle_plate_color_id: 车牌颜色，"0"=蓝色, "1"=黄色, "2"=黑色, "3"=白色, "4"=绿色
- axis_count: 轴数
- total_limit: 限重(吨)
- total_weight: 实际重量(kg)
- card_type: 卡类型
- pay_type: 支付类型，"1"=ETC, "2"=现金, "3"=移动支付
- toll_money: 应收金额
- real_money: 实收金额
- discount_type: 优惠类型
- section_id: 路段ID
- section_name: 路段名称
- pass_id: 通行ID

业务规则：
1. 货车车牌通常为黄色(vehicle_plate_color_id="1")
2. 客车车牌通常为蓝色(vehicle_plate_color_id="0")或绿色(新能源, "4")
3. total_weight 不应超过 total_limit，否则为超载
"""


# ==================== 生成函数 ====================

def generate_with_llm(
    data_type: str,
    count: int = 10,
    scenario: Optional[str] = None,
    base_time: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    使用大模型生成指定类型的数据
    
    Args:
        data_type: 数据类型，"gantry" 或 "exit"
        count: 生成数量，建议不超过 20 条（避免输出过长）
        scenario: 可选的场景描述，如 "超载货车"、"节假日高峰"、"异常交易"
        base_time: 基准时间，默认为当前时间
    
    Returns:
        生成的数据列表
    """
    if base_time is None:
        base_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    
    # 选择 schema
    if data_type == "gantry":
        schema = GANTRY_TRANSACTION_SCHEMA
        table_name = "GantryTransaction"
    elif data_type == "exit":
        schema = EXIT_TRANSACTION_SCHEMA
        table_name = "ExitTransaction"
    else:
        raise ValueError(f"不支持的数据类型: {data_type}")
    
    # 构建 prompt
    scenario_desc = f"\n特殊场景要求: {scenario}" if scenario else ""
    
    system_prompt = f"""你是一个高速公路交易数据生成专家。你需要根据给定的表结构和业务规则，生成真实、合理的模拟数据。

{schema}

生成要求：
1. 严格遵循上述字段格式和业务规则
2. 数据要有合理的多样性（不同车型、不同时段、不同路段）
3. 字段之间的关联要符合逻辑
4. 只输出 JSON 数组，不要有任何其他文字
{scenario_desc}"""

    user_prompt = f"""请生成 {count} 条 {table_name} 记录。

基准时间: {base_time}
输出格式: JSON 数组

直接输出 JSON，不要有 markdown 代码块或其他说明。"""

    print(f"[LLM] 正在生成 {count} 条 {table_name} 数据...")
    if scenario:
        print(f"[LLM] 场景: {scenario}")
    
    response = client.chat.completions.create(
        model=config.FIXED_MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.8,  # 稍高的温度增加多样性
        max_tokens=4096
    )
    
    content = response.choices[0].message.content.strip()
    
    # 清理可能的 markdown 代码块
    if content.startswith("```"):
        content = content.split("\n", 1)[1]  # 移除第一行
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
    
    try:
        data = json.loads(content)
        print(f"[LLM] 成功生成 {len(data)} 条数据")
        return data
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON 解析失败: {e}")
        print(f"[DEBUG] 原始输出:\n{content[:500]}...")
        return []


def validate_gantry_data(records: List[Dict]) -> List[Dict]:
    """验证并修正门架交易数据"""
    valid_records = []
    
    for i, rec in enumerate(records):
        issues = []
        
        # 检查时间逻辑
        if 'entrance_time' in rec and 'transaction_time' in rec:
            try:
                entrance = datetime.fromisoformat(rec['entrance_time'])
                transaction = datetime.fromisoformat(rec['transaction_time'])
                if entrance >= transaction:
                    issues.append("入口时间晚于交易时间")
            except:
                pass
        
        # 检查费用逻辑
        if 'pay_fee' in rec and 'discount_fee' in rec:
            pay = int(rec.get('pay_fee', 0))
            discount = int(rec.get('discount_fee', 0))
            if discount > pay:
                issues.append(f"优惠金额({discount})超过应付金额({pay})")
        
        if issues:
            print(f"[WARN] 记录 {i+1} 存在问题: {', '.join(issues)}")
        else:
            valid_records.append(rec)
    
    return valid_records


def save_to_json(records: List[Dict], filename: str):
    """保存数据到 JSON 文件"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"[SAVE] 数据已保存到 {filename}")


def demo_scenarios():
    """演示不同场景的数据生成"""
    scenarios = [
        ("正常交通流", None),
        ("超载货车", "生成5辆超载货车的数据，total_weight应该超过对应轴数的限重"),
        ("节假日高峰", "生成节假日高峰期数据，时间集中在上午9-11点，车流量大，以客车为主"),
        ("异常交易", "生成一些异常交易数据，包括：补费交易、pass_state异常、费用为0的情况"),
        ("ETC用户", "生成全部为ETC用户(media_type=1)的数据，都有5%优惠"),
    ]
    
    all_data = []
    for name, scenario in scenarios:
        print(f"\n{'='*50}")
        print(f"场景: {name}")
        print('='*50)
        
        data = generate_with_llm("gantry", count=3, scenario=scenario)
        if data:
            all_data.extend(data)
            print(f"样例数据:")
            print(json.dumps(data[0], ensure_ascii=False, indent=2))
    
    return all_data


# ==================== 主函数 ====================

def main():
    parser = argparse.ArgumentParser(description='基于大模型的数据生成器')
    parser.add_argument('--type', choices=['gantry', 'exit'], default='gantry',
                        help='数据类型: gantry(门架交易) 或 exit(出口交易)')
    parser.add_argument('--count', type=int, default=10,
                        help='生成数量 (建议不超过20)')
    parser.add_argument('--scenario', type=str, default=None,
                        help='场景描述，如 "超载货车"、"节假日高峰"')
    parser.add_argument('--output', type=str, default=None,
                        help='输出文件路径 (JSON格式)')
    parser.add_argument('--demo', action='store_true',
                        help='运行场景演示')
    
    args = parser.parse_args()
    
    if args.demo:
        data = demo_scenarios()
    else:
        data = generate_with_llm(
            data_type=args.type,
            count=args.count,
            scenario=args.scenario
        )
    
    if data:
        # 验证数据
        valid_data = validate_gantry_data(data) if args.type == 'gantry' else data
        
        # 保存或打印
        if args.output:
            save_to_json(valid_data, args.output)
        else:
            print(f"\n[RESULT] 生成的数据 ({len(valid_data)} 条):")
            print(json.dumps(valid_data[:3], ensure_ascii=False, indent=2))
            if len(valid_data) > 3:
                print(f"... 省略 {len(valid_data) - 3} 条 ...")


if __name__ == "__main__":
    main()
