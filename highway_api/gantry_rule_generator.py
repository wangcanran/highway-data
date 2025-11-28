import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from models import GantryTransaction
from gantry_mappings import GANTRY_TO_SECTION, SECTION_NAME_BY_ID


# 基于真实库中枚举/状态字段的取值，定义规则生成所使用的“干净值域”
# 注意：这里只是规则生成侧的工程化取值，不等同于完整业务语义

# 直接从统计结果整理的枚举集合（去掉明显异常/脏值）
GANTRY_RULE_ENUMS: Dict[str, List[str]] = {
    # 门架类型：真实有 '1','2','3'，规则生成全部保留
    "gantry_type": ["1", "2", "3"],
    # 介质类型：真实有 '1','2'
    "media_type": ["1", "2"],
    # 车辆类型：使用真实数据中出现的 14 种全部编码
    # ['1', '11', '0', '13', '16', '12', '14', '2', '4', '3', '22', '21', '23', '24']
    "vehicle_type": [
        "1",
        "11",
        "0",
        "13",
        "16",
        "12",
        "14",
        "2",
        "4",
        "3",
        "22",
        "21",
        "23",
        "24",
    ],
    # 车牌标识：真实只有两种
    "vehicle_sign": ["0xff", "0x04"],
    # 通行状态：正常/异常
    "pass_state": ["1.0", "2.0"],
    # 入口车道类型：只用主力两种，其余视为异常
    "entrance_lane_type": ["01", "03"],
    # 车轴数：过滤掉 255.0 / 144.0 等可疑值
    "axle_count": ["2.0", "3.0", "4.0", "5.0", "6.0"],
    # CPU卡类型：允许空和两种有效值
    "cpu_card_type": ["", "1.0", "2.0"],
    # 省份编码：当前库中只有一个
    "fee_prov_begin_hex": ["000000"],
}


GANTRY_ID_VALUES: List[str] = list(GANTRY_TO_SECTION.keys())


def _random_choice(key: str) -> str:
    """从规则枚举中随机选择一个值。"""
    values = GANTRY_RULE_ENUMS[key]
    return random.choice(values)


def generate_rule_based_gantry_transaction(seed: Optional[int] = None) -> Dict[str, Any]:
    """基于规则生成一条门架交易记录（dict 形式，不落库）。

    规则特点：
    - 所有枚举字段取值在 GANTRY_RULE_ENUMS / GANTRY_ID_VALUES / SECTION_ID_VALUES 范围内
    - 过滤掉明显异常编码（如 axle_count=255.0 等）
    - 时间/金额做简单的合理范围控制
    """
    if seed is not None:
        random.seed(seed)

    record: Dict[str, Any] = {}

    # 1) 车辆与介质相关字段
    record["vehicle_type"] = _random_choice("vehicle_type")
    record["media_type"] = _random_choice("media_type")
    record["vehicle_sign"] = _random_choice("vehicle_sign")

    # 2) 时间相关：transaction_time / entrance_time
    # 门架交易时间：在一个月范围内均匀随机
    start = datetime(2023, 1, 3, 0, 0, 0)
    end = datetime(2023, 12, 23, 23, 59, 59)
    total_seconds = int((end - start).total_seconds())
    offset = random.randint(0, total_seconds)
    tx_time = start + timedelta(seconds=offset)
    record["transaction_time"] = tx_time.isoformat(sep=" ")

    # entrance_time 比 transaction_time 早 10 分钟 - 3 小时
    delta_minutes = random.randint(10, 180)
    entrance_time = tx_time - timedelta(minutes=delta_minutes)
    record["entrance_time"] = entrance_time.isoformat(sep=" ")

    # 3) 费用相关：对齐真实统计范围
    # transaction_time: 已按 2023-01-03 ~ 2023-12-23 生成
    # pay_fee: 0 ~ 20596，discount_fee: 0 ~ 4625（且不超过 pay_fee）

    # 绝大多数为小额，少量为大额：
    # - 90% 采样 0~500 区间
    # - 10% 采样 500~20596 区间
    u = random.random()
    if u < 0.9:
        pay_min, pay_max = 0, 500
    else:
        pay_min, pay_max = 500, 20596

    pay_fee = random.randint(pay_min, pay_max)
    record["pay_fee"] = pay_fee

    # 折扣：70% 为 0，其余在 0~min(4625, pay_fee) 范围内
    if random.random() < 0.7:
        discount_fee = 0
    else:
        max_disc = min(4625, pay_fee)
        if max_disc > 0:
            discount_fee = random.randint(0, max_disc)
        else:
            discount_fee = 0
    record["discount_fee"] = discount_fee

    # fee 简化为字符串金额
    record["fee"] = str(pay_fee)

    # 里程：假设单价约 0.8，加入轻微随机扰动
    mileage = pay_fee / 0.8 * random.uniform(0.9, 1.1)
    record["fee_mileage"] = f"{mileage:.1f}"

    # 4) 轴数与重量
    axle_str = _random_choice("axle_count")
    record["axle_count"] = axle_str

    # total_weight 在真实数据中大量为 0.0，常见非零值有 18000.0、25000.0 等，
    # 看起来单位更像 kg（或 0.01 吨）。这里做一个简化的阶梯式规则：
    # - 80% 生成 "0.0" 表示未知/未称重
    # - 20% 在若干常见重量档中按大致权重采样
    if random.random() < 0.8:
        record["total_weight"] = "0.0"
    else:
        common_weights = [
            18000.0,
            25000.0,
            31000.0,
            49000.0,
            2200.0,
            46000.0,
            2300.0,
            1800.0,
            1600.0,
            2400.0,
        ]
        # 粗略倾向于 18000、25000 这类高频档，给前两个更高权重
        weights = [5, 4, 2, 2, 1, 1, 1, 1, 1, 1]
        total = sum(weights)
        r = random.randint(1, total)
        acc = 0
        chosen = common_weights[0]
        for w, v in zip(weights, common_weights):
            acc += w
            if r <= acc:
                chosen = v
                break
        record["total_weight"] = f"{chosen:.1f}"

    # 5) 状态 / 编码
    record["gantry_type"] = _random_choice("gantry_type")
    record["transaction_type"] = "9.0"  # 当前真实数据只有这一种

    # 正常/异常：默认按 99% 正常、1% 异常
    record["pass_state"] = "1.0" if random.random() < 0.99 else "2.0"

    record["entrance_lane_type"] = _random_choice("entrance_lane_type")
    record["cpu_card_type"] = _random_choice("cpu_card_type")
    record["fee_prov_begin_hex"] = _random_choice("fee_prov_begin_hex")

    # 6) OBU 累计金额
    # 当前真实数据中 obu_fee_sum_before / after 和 pay_fee_prov_sum_local 为空字符串，
    # 为了贴合现有库，这里规则版默认也生成空；如需后续使用，可再根据新数据调整。
    record["obu_fee_sum_before"] = ""
    record["obu_fee_sum_after"] = ""
    record["pay_fee_prov_sum_local"] = ""

    # 7) 门架与路段信息
    gantry_id = random.choice(GANTRY_ID_VALUES)
    record["gantry_id"] = gantry_id

    # 根据真实映射确定 section_id
    section_id = GANTRY_TO_SECTION.get(gantry_id)
    record["section_id"] = section_id

    # section_name 与 section_id 是强约束关系：在规则生成中也使用固定映射
    if section_id in SECTION_NAME_BY_ID:
        record["section_name"] = SECTION_NAME_BY_ID[section_id]
    else:
        record["section_name"] = section_id

    # 8) 主键和 pass_id
    now_str = tx_time.strftime("%Y%m%d%H%M%S")
    record["gantry_transaction_id"] = f"GT{now_str}{random.randint(100000, 999999)}"
    record["pass_id"] = f"P{now_str}{random.randint(1000, 9999)}"

    # 9) 其他未细化字段给出合理占位
    record.setdefault("transaction_type", "9.0")
    record.setdefault("media_type", record["media_type"])

    return record
