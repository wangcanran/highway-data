import random
from typing import Dict, Any, Optional

from models import GantryTransaction
from gantry_mappings import GANTRY_TO_SECTION, SECTION_NAME_BY_ID


# 统计生成：直接使用真实数据的经验分布（频数）作为采样权重
# 注意：这里只整理了枚举/离散字段的分布，连续字段仍使用简单规则或区间采样

GANTRY_STAT_DISTS: Dict[str, Dict[str, int]] = {
    # 来自 gantry_value_analysis.txt
    "gantry_type": {"1": 43158, "3": 10, "2": 1},
    "media_type": {"2": 23132, "1": 20037},
    "vehicle_type": {
        "1": 30367,
        "11": 6943,
        "0": 3917,
        "13": 933,
        "16": 220,
        "12": 193,
        "14": 164,
        "2": 127,
        "4": 105,
        "3": 78,
        "22": 66,
        "21": 34,
        "23": 17,
        "24": 5,
    },
    "vehicle_sign": {"0xff": 43116, "0x04": 53},
    "transaction_type": {"9.0": 43169},
    "pass_state": {"1.0": 43132, "2.0": 37},
    "entrance_lane_type": {
        "01": 22756,
        "03": 16494,
        "": 3917,
        "04": 1,
        "02": 1,
    },
    # axle_count 的边际分布保留在这里，但在生成时会优先按
    # P(axle_count | vehicle_type) 条件分布抽样
    "axle_count": {
        "2.0": 27921,
        "255.0": 13911,
        "6.0": 966,
        "4.0": 170,
        "3.0": 154,
        "5.0": 46,
        "144.0": 1,
    },
    "cpu_card_type": {"": 23132, "2.0": 18433, "1.0": 1604},
    "fee_prov_begin_hex": {"000000": 43169},
    # section_name 与 section_id 一一对应
    "section_name": {
        "麻文高速": 14949,
        "宜宾至毕节高速威信至镇雄段": 10116,
        "彝良至镇雄高速公路": 9279,
        "彝良至昭通高速": 4228,
        "都香高速": 2573,
        "昭阳西环高速公路": 1552,
        "大关至永善高速": 468,
        "青龙咀至水田新区高速": 4,
    },
}


"""统计生成所需的经验分布和映射常量。"""

# 直接从 analysis.txt 拷贝的 section_id 频数（仍保留，可用于校验边际分布是否接近真实）
SECTION_ID_DISTS: Dict[str, int] = {
    "G5615530120": 14949,
    "S0014530010": 10116,
    "S0010530020": 9279,
    "S0010530010": 4228,
    "G7611530010": 2573,
    "S0071530020": 1552,
    "S0014530030": 468,
    "S0014530020": 4,
}


# gantry_id 分布（频数）
GANTRY_ID_DISTS: Dict[str, int] = {
    "G561553012000420010": 3539,
    "G561553012000320010": 3378,
    "G561553012000410010": 2881,
    "G561553012000310010": 2869,
    "S001053002000420010": 2742,
    "S001053002000410010": 2604,
    "S001053002000320010": 1510,
    "S001053002000310010": 1319,
    "G561553012000220010": 1077,
    "S001453001000810010": 1046,
    "S001053001000410010": 1042,
    "G761153001000510010": 1037,
    "G761153001000520010": 1016,
    "S001053001000420010": 1009,
    "G561553012000210010": 1000,
    "S001453001000820010": 991,
    "S001453001000310010": 762,
    "S001453001000410010": 723,
    "S001453001000420010": 693,
    "S001453001000920010": 687,
    "S001453001000910010": 679,
    "S001453001000320010": 669,
    "S001453001000520010": 661,
    "S001453001000510010": 587,
    "S001053002000220010": 550,
    "S001053002000210010": 529,
    "S001453001000710010": 501,
    "S001453001000610010": 499,
    "S001453001000620010": 468,
    "S001053001000510010": 431,
    "S001053001000520010": 421,
    "S001453001000720010": 400,
    "S001453001000210010": 398,
    "S001053001000610010": 377,
    "S001053001000620010": 364,
    "S001453001000220010": 348,
    "S007153002000320010": 316,
    "S007153002000310010": 315,
    "S007153002000410010": 289,
    "S007153002000420010": 272,
    "G761153001000420010": 248,
    "S001053001000710010": 234,
    "S001453003000310010": 234,
    "S001453003000320010": 234,
    "S001053001000720010": 224,
    "G761153001000410010": 198,
    "S007153002000210010": 182,
    "S007153002000220010": 175,
    "G561553012000610010": 61,
    "S001053001000310010": 59,
    "G561553012000510010": 57,
    "S001053001000320010": 56,
    "G561553012000520010": 51,
    "G561553012000620010": 35,
    "G761153001000220010": 20,
    "G761153001000320010": 20,
    "G761153001000210010": 17,
    "G761153001000310010": 15,
    "S001053002000110010": 13,
    "S001053002000120010": 10,
    "S001053001000810010": 5,
    "S001053001000810020": 5,
    "G761153001001710010": 2,
    "S001453001002010010": 2,
    "S001453001002020010": 2,
    "S001453002000110010": 2,
    "S001453002000120010": 2,
    "G561553012000710010": 1,
    "S001053001000820010": 1,
    "S001053002000510010": 1,
    "S001053002000520010": 1,
    "S007153002000120010": 1,
    "S007153002000510010": 1,
    "S007153002000520010": 1,
}


def _sample_from_counts(dist: Dict[str, int]) -> str:
    """按照频数分布进行一次离散采样。"""
    values = list(dist.keys())
    weights = list(dist.values())
    return random.choices(values, weights=weights, k=1)[0]


# vehicle_type 与 axle_count 的联合分布（来自 gantry_vehicle_axle_joint.txt），
# 用于构造条件分布 P(axle_count | vehicle_type)
AXLE_BY_VEHICLE_DISTS: Dict[str, Dict[str, int]] = {
    "0": {"2.0": 3917},
    "1": {"2.0": 16506, "255.0": 13861},
    "2": {"2.0": 79, "255.0": 48},
    "3": {"2.0": 76, "255.0": 2},
    "4": {"2.0": 105},
    "11": {"2.0": 6941, "144.0": 1, "3.0": 1},
    "12": {"2.0": 188, "5.0": 4, "4.0": 1},
    "13": {"6.0": 752, "3.0": 136, "5.0": 36, "2.0": 9},
    "14": {"4.0": 164},
    "16": {"6.0": 214, "5.0": 6},
    "21": {"2.0": 34},
    "22": {"2.0": 66},
    "23": {"3.0": 17},
    "24": {"4.0": 5},
}


def generate_statistical_gantry_transaction(seed: Optional[int] = None) -> Dict[str, Any]:
    """基于经验分布（统计）生成一条门架交易记录。

    与规则版的区别：
    - 所有离散字段按真实频数加权采样
    - 不再过滤冷门/疑似脏值（如 axle_count=255.0 等）
    - 连续字段使用简单区间采样或保留规则版逻辑
    """
    if seed is not None:
        random.seed(seed)

    record: Dict[str, Any] = {}

    # 1) 离散字段：按统计分布采样
    record["gantry_type"] = _sample_from_counts(GANTRY_STAT_DISTS["gantry_type"])
    record["media_type"] = _sample_from_counts(GANTRY_STAT_DISTS["media_type"])
    # 先按边际分布采样 vehicle_type，再基于条件分布采样 axle_count
    vt = _sample_from_counts(GANTRY_STAT_DISTS["vehicle_type"])
    record["vehicle_type"] = vt
    record["vehicle_sign"] = _sample_from_counts(GANTRY_STAT_DISTS["vehicle_sign"])
    record["transaction_type"] = _sample_from_counts(GANTRY_STAT_DISTS["transaction_type"])
    record["pass_state"] = _sample_from_counts(GANTRY_STAT_DISTS["pass_state"])
    record["entrance_lane_type"] = _sample_from_counts(GANTRY_STAT_DISTS["entrance_lane_type"])

    # axle_count：优先使用按 vehicle_type 拆分的条件分布；
    # 如遇到缺失/未覆盖的车型，则退回边际分布
    axle_dist = AXLE_BY_VEHICLE_DISTS.get(vt)
    if axle_dist:
        record["axle_count"] = _sample_from_counts(axle_dist)
    else:
        record["axle_count"] = _sample_from_counts(GANTRY_STAT_DISTS["axle_count"])
    record["cpu_card_type"] = _sample_from_counts(GANTRY_STAT_DISTS["cpu_card_type"])
    record["fee_prov_begin_hex"] = _sample_from_counts(GANTRY_STAT_DISTS["fee_prov_begin_hex"])

    # 2) gantry_id / section_id / section_name：
    #    先按统计分布采样 gantry_id，再通过 GANTRY_TO_SECTION 与 SECTION_NAME_BY_ID
    #    保证一对一的结构性约束
    gantry_id = _sample_from_counts(GANTRY_ID_DISTS)
    record["gantry_id"] = gantry_id

    section_id = GANTRY_TO_SECTION.get(gantry_id)
    record["section_id"] = section_id

    # section_name 优先用 section_id 的映射；如遇未知 section_id，则退回到统计分布采样
    if section_id in SECTION_NAME_BY_ID:
        record["section_name"] = SECTION_NAME_BY_ID[section_id]
    else:
        record["section_name"] = _sample_from_counts(GANTRY_STAT_DISTS["section_name"])

    # 3) 时间与费用字段：沿用规则版的大致逻辑，保证范围对齐
    from datetime import datetime, timedelta

    start = datetime(2023, 1, 3, 0, 0, 0)
    end = datetime(2023, 12, 23, 23, 59, 59)
    total_seconds = int((end - start).total_seconds())
    offset = random.randint(0, total_seconds)
    tx_time = start + timedelta(seconds=offset)
    record["transaction_time"] = tx_time.isoformat(sep=" ")

    delta_minutes = random.randint(10, 180)
    entrance_time = tx_time - timedelta(minutes=delta_minutes)
    record["entrance_time"] = entrance_time.isoformat(sep=" ")

    # pay_fee / discount_fee 按相同区间分段抽样（但不依赖车型）
    u = random.random()
    if u < 0.9:
        pay_min, pay_max = 0, 500
    else:
        pay_min, pay_max = 500, 20596
    pay_fee = random.randint(pay_min, pay_max)
    record["pay_fee"] = pay_fee

    if random.random() < 0.7:
        discount_fee = 0
    else:
        max_disc = min(4625, pay_fee)
        discount_fee = random.randint(0, max_disc) if max_disc > 0 else 0
    record["discount_fee"] = discount_fee

    record["fee"] = str(pay_fee)

    mileage = pay_fee / 0.8 * random.uniform(0.9, 1.1)
    record["fee_mileage"] = f"{mileage:.1f}"

    # 4) total_weight：此处保持与规则版相同的阶梯式近似
    if random.random() < 0.8:
        record["total_weight"] = "0.0"
    else:
        common_weights = [18000.0, 25000.0, 31000.0, 49000.0, 2200.0, 46000.0, 2300.0, 1800.0, 1600.0, 2400.0]
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

    # 5) OBU 字段：与当前真实数据保持为空
    record["obu_fee_sum_before"] = ""
    record["obu_fee_sum_after"] = ""
    record["pay_fee_prov_sum_local"] = ""

    # 6) 主键与 pass_id
    now_str = tx_time.strftime("%Y%m%d%H%M%S")
    record["gantry_transaction_id"] = f"GT{now_str}{random.randint(100000, 999999)}"
    record["pass_id"] = f"P{now_str}{random.randint(1000, 9999)}"

    return record
