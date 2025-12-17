import json
import random
import math
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from collections import Counter
from openai import OpenAI

import numpy as np

import config
from gantry_mappings import GANTRY_TO_SECTION, SECTION_NAME_BY_ID


# ============================================================================
#                           基础配置与客户端
# ============================================================================

client = OpenAI(
    api_key=config.OPENAI_API_KEY,
    base_url=config.OPENAI_API_BASE,
    timeout=config.REQUEST_TIMEOUT
)

MODEL_NAME = config.FIXED_MODEL_NAME


# ============================================================================
#                      I. GENERATION - 生成阶段
# ============================================================================

# ---------------------- 1.1 Task Specification ----------------------

GANTRY_TASK_SPECIFICATION = """
你是一个高速公路门架交易数据生成专家。你的任务是生成符合真实业务逻辑的门架通行记录。

## 门架交易数据表结构 (GantryTransaction)

| 字段名 | 类型 | 说明 | 约束 |
|--------|------|------|------|
| gantry_transaction_id | String | 门架交易ID | 门架编号+交易批次号+主备卡标记（1-ETC主、2- ETC备、3-CPC主、4-CPC备）+批次内流水号（5位，00001~99999） |
| gantry_id | String | 门架ID | 全网唯一编号 |
| gantry_type | String | 门架类型 | 1=路段, 2=省界入口, 3=省界出口 |
| transaction_time | DateTime | 交易时间 | ISO格式，必须晚于 entrance_time |
| entrance_time | DateTime | 入口时间 | ISO格式，早于 transaction_time 30分钟-4小时 |
| pay_fee | Integer | 应付费用(分) | 正整数，与里程正相关。单位：分，默认0。应收金额为优惠前金额 |
| discount_fee | Integer | 优惠金额(分) | 单位：分，默认0。优惠金额为优惠减免金额，未优惠填0 |
| fee_mileage | String | 收费里程(米) | 正整数字符串 |
| media_type | Int | 通行介质类型 | 1=OBU, 2=CPC卡 |
| vehicle_type | String | 车型 | 1-4=客车(一~四型), 11-16=货车(一~六型), 21-26=专项车 |
| vehicle_sign | String | 车辆状态标识 | 0x00=大件运输（交易成功时有效）,0x01=非优惠车, 0x02=绿通车, 0x03=联合收割机, 0x04=集装箱车, 0xff=默认 |
| axle_count | String | 轴数 | 客车通常2轴，货车2-6轴 |
| total_weight | String | 总重量(kg) | 字符串，货车根据轴数有限重，单位kg |
| transaction_type | String | 交易类型 | PBOC定义，如06为传统交易，09为复合交易。计费成功必填。 |
| pass_state | String | 通行状态 | 1=有入口, 2=无入口 |
| cpu_card_type | String | CPU卡类型 | 0=默认, 1=储值卡, 2=记账卡 |
| pass_id | String | 通行ID | ETC长度从30为调整为36位；  
（1）“01“+”卡网络编号“+”用户卡编号“+”卡内入口时间“，计费使用  
（2）“00“+”0000“+” OBU序号编码“+”OBU内入口时间“，  
CPC车辆通行标识passId，格式为“02“+”0000“+” CPC卡编码“+”入口时间“ |
| section_id | String | 路段ID |  |
| section_name | String | 路段名称 | |

## 核心业务规则

1. **时间约束**: entrance_time < transaction_time，时间差 30分钟 ~ 4小时
2. **货车限重规则**:
   - 2轴: ≤18吨, 3轴: ≤25吨, 4轴: ≤31吨, 5轴: ≤43吨, 6轴: ≤49吨
3. **费用计算** (云南省标准):
   - 客车: 一类0.45元/km, 二类0.75元/km, 三类1.05元/km, 四类1.25元/km
   - 货车: 普通路段0.45元/km, 桥隧路段1.15元/km (默认80%普通+20%桥隧)
4. **ETC优惠**: media_type=1 时，discount_fee = pay_fee × 5%
5. **客车特征**: vehicle_type=1-4(一~四型客车) 时，axle_count=2，total_weight 在 2000-5000kg
"""

# 云南省高速公路收费标准（单位：元/公里）
YUNNAN_TOLL_RATES = {
    "passenger": {
        "1": 0.45,   # 一类客车（1-9座）
        "2": 0.75,   # 二类客车（10-19座）
        "3": 1.05,   # 三类客车（20-39座）
        "4": 1.25    # 四类客车（40座以上）
    },
    "truck": {
        "normal": 0.45,   # 普通路段
        "bridge": 1.15    # 桥隧路段
    }
}

def calculate_expected_fee(mileage_meters: int, vehicle_type: str) -> int:
    """
    计算期望费用（云南省标准）
    
    Args:
        mileage_meters: 里程（米）
        vehicle_type: 车型代码（1-4客车，11-16货车，21-26专项车）
    
    Returns:
        期望费用（分）
    """
    if vehicle_type in ["1", "2", "3", "4"]:
        # 客车
        rate = YUNNAN_TOLL_RATES["passenger"].get(vehicle_type, 0.45)
    else:
        # 货车和专项车（80%普通路段 + 20%桥隧路段）
        rate = YUNNAN_TOLL_RATES["truck"]["normal"] * 0.8 + YUNNAN_TOLL_RATES["truck"]["bridge"] * 0.2
    
    # 里程(米) / 1000 * 费率(元/km) * 100(分/元)
    return int(mileage_meters / 1000 * rate * 100)

# ---------------------- 1.2 Generation Conditions ----------------------

@dataclass
class GenerationCondition:
    """生成条件 - Conditioning Scope & Values"""
    
    # 条件范围 (Conditioning Scope)
    vehicle_type: Optional[str] = None      # 车型约束
    time_period: Optional[str] = None       # 时段约束
    region: Optional[str] = None            # 区域约束
    scenario: Optional[str] = None          # 场景约束
    section_id: Optional[str] = None        # 路段约束 (新增)
    
    # 条件值 (Conditioning Values)
    base_time: Optional[datetime] = None    # 基准时间
    target_distribution: Optional[Dict] = None  # 目标分布
    
    def to_prompt(self) -> str:
        """将条件转换为提示词"""
        parts = []
        
        if self.vehicle_type:
            parts.append(f"车型: {self.vehicle_type}")
        if self.time_period:
            parts.append(f"时段: {self.time_period}")
        if self.region:
            parts.append(f"区域: {self.region}")
        if self.scenario:
            parts.append(f"场景: {self.scenario}")
        if self.section_id:
            parts.append(f"路段: {self.section_id}")
        if self.base_time:
            parts.append(f"基准时间: {self.base_time.isoformat()}")
        
        return "；".join(parts) if parts else "无特殊约束"


# ---------------------- 1.3 Section-Date Mapper ----------------------

# 预配置的路段-日期映射（根据真实采样情况配置）
PRECONFIGURED_SECTION_DATES = {
    "G5615530120": ["2023-01-03"],  # 麻文高速
    "G7611530010": ["2023-02-01"],  # 都香高速
    "S0010530010": ["2023-02-20", "2023-02-21"],  # 彝良至昭通高速
    "S0010530020": ["2023-03-08", "2023-03-09"],  # 彝良至镇雄高速公路
    "S0014530010": ["2023-03-15", "2023-03-16"],  # 宜宾至毕节高速威信至镇雄段
    "S0014530020": ["2023-03-22", "2023-03-23"],  # 青龙咎至水田新区高速
    "S0014530030": ["2023-12-22", "2023-12-23"],  # 大关至永善高速
    "S0071530020": ["2023-02-08", "2023-02-09"],  # 昭阳西环高速公路
}

class SectionDateMapper:
    """路段-日期映射管理器
    
    用于从原始数据中学习每个路段的采样日期分布，
    确保生成数据保持路段-日期的真实对应关系。
    """
    
    def __init__(self, use_preconfigured: bool = True):
        """初始化路段-日期映射器
        
        Args:
            use_preconfigured: 是否使用预配置的路段-日期映射
        """
        # 路段 -> 日期列表的映射
        self.section_dates: Dict[str, List[datetime]] = {}
        # 路段 -> (最小日期, 最大日期) 的映射
        self.section_date_ranges: Dict[str, Tuple[datetime, datetime]] = {}
        # 默认日期范围（当路段未知时使用）
        self.default_date_range: Optional[Tuple[datetime, datetime]] = None
        
        # 如果启用预配置，加载预配置的映射
        if use_preconfigured:
            self.load_preconfigured_dates()
    
    def load_preconfigured_dates(self, verbose: bool = False) -> None:
        """加载预配置的路段-日期映射
        
        Args:
            verbose: 是否输出详细信息
        """
        for section_id, date_strings in PRECONFIGURED_SECTION_DATES.items():
            dates = []
            for date_str in date_strings:
                try:
                    date = datetime.strptime(date_str, "%Y-%m-%d")
                    dates.append(date.replace(hour=0, minute=0, second=0, microsecond=0))
                except Exception as e:
                    if verbose:
                        print(f"  [警告] 日期格式错误: {section_id} - {date_str}")
            
            if dates:
                self.section_dates[section_id] = dates
                self.section_date_ranges[section_id] = (min(dates), max(dates))
        
        # 设置默认日期范围
        if self.section_dates:
            all_dates = []
            for dates in self.section_dates.values():
                all_dates.extend(dates)
            self.default_date_range = (min(all_dates), max(all_dates))
        else:
            # 如果没有数据，使用当前日期前后一个月
            now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            self.default_date_range = (now - timedelta(days=30), now)
        
        if verbose:
            print(f"  [预配置映射] 已加载 {len(self.section_dates)} 个路段的日期映射")
            for section_id, dates in list(self.section_dates.items())[:3]:
                section_name = SECTION_NAME_BY_ID.get(section_id, "未知")
                date_strs = [d.strftime("%Y-%m-%d") for d in dates]
                print(f"    - {section_name} ({section_id}): {', '.join(date_strs)}")
            if len(self.section_dates) > 3:
                print(f"    - ... 还有 {len(self.section_dates) - 3} 个路段")
    
    def learn_from_samples(self, samples: List[Dict], verbose: bool = True, override_preconfigured: bool = False) -> None:
        """从样本数据中学习路段-日期映射
        
        Args:
            samples: 原始样本数据列表
            verbose: 是否输出学习过程信息
            override_preconfigured: 是否覆盖预配置的映射（默认为合并）
        """
        from collections import defaultdict
        
        section_date_lists = defaultdict(list)
        
        # 提取每个路段的所有交易日期
        for sample in samples:
            section_id = sample.get("section_id")
            transaction_time_str = sample.get("transaction_time")
            
            if not section_id or not transaction_time_str:
                continue
            
            try:
                transaction_time = datetime.fromisoformat(transaction_time_str)
                # 只保留日期部分（去除时分秒）
                date_only = transaction_time.replace(hour=0, minute=0, second=0, microsecond=0)
                section_date_lists[section_id].append(date_only)
            except Exception:
                continue
        
        # 计算每个路段的日期范围
        all_dates = []
        for section_id, dates in section_date_lists.items():
            if dates:
                unique_dates = list(set(dates))  # 去重
                unique_dates.sort()
                
                # 如果不覆盖且已有预配置，合并日期
                if not override_preconfigured and section_id in self.section_dates:
                    existing_dates = self.section_dates[section_id]
                    combined_dates = list(set(existing_dates + unique_dates))
                    combined_dates.sort()
                    self.section_dates[section_id] = combined_dates
                else:
                    self.section_dates[section_id] = unique_dates
                
                # 更新日期范围
                self.section_date_ranges[section_id] = (min(self.section_dates[section_id]), 
                                                         max(self.section_dates[section_id]))
                all_dates.extend(self.section_dates[section_id])
        
        # 设置默认日期范围
        if all_dates:
            self.default_date_range = (min(all_dates), max(all_dates))
        else:
            # 如果没有数据，使用当前日期前后一个月
            now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            self.default_date_range = (now - timedelta(days=30), now)
        
        if verbose:
            print(f"  [路段-日期映射] 学习完成:")
            print(f"    - 已映射路段数: {len(self.section_date_ranges)}")
            print(f"    - 默认日期范围: {self.default_date_range[0].date()} ~ {self.default_date_range[1].date()}")
            
            # 显示前5个路段的日期范围作为示例
            for i, (section_id, (min_date, max_date)) in enumerate(list(self.section_date_ranges.items())[:5]):
                section_name = SECTION_NAME_BY_ID.get(section_id, "未知")
                date_count = len(self.section_dates[section_id])
                print(f"    - {section_name} ({section_id}): {min_date.date()} ~ {max_date.date()} (共{date_count}天)")
            
            if len(self.section_date_ranges) > 5:
                print(f"    - ... 还有 {len(self.section_date_ranges) - 5} 个路段")
    
    def get_date_for_section(self, section_id: Optional[str] = None) -> datetime:
        """获取指定路段的采样日期
        
        Args:
            section_id: 路段ID，如果为None则随机选择一个路段
        
        Returns:
            该路段对应的日期（datetime对象，时分秒为0）
        """
        # 如果没有指定路段，随机选择一个已知路段
        if not section_id:
            if self.section_dates:
                section_id = random.choice(list(self.section_dates.keys()))
            else:
                # 使用默认日期范围
                return self._random_date_in_range(self.default_date_range)
        
        # 如果路段在映射表中，从该路段的日期列表中随机选择
        if section_id in self.section_dates and self.section_dates[section_id]:
            return random.choice(self.section_dates[section_id])
        
        # 如果路段不在映射表中，从路段的日期范围中随机选择
        if section_id in self.section_date_ranges:
            return self._random_date_in_range(self.section_date_ranges[section_id])
        
        # 如果路段完全未知，使用默认日期范围
        return self._random_date_in_range(self.default_date_range)
    
    def _random_date_in_range(self, date_range: Optional[Tuple[datetime, datetime]]) -> datetime:
        """在日期范围内随机选择一个日期"""
        if not date_range:
            return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        min_date, max_date = date_range
        days_diff = (max_date - min_date).days
        
        if days_diff <= 0:
            return min_date
        
        random_days = random.randint(0, days_diff)
        return min_date + timedelta(days=random_days)
    
    def get_section_with_date(self) -> Tuple[str, datetime]:
        """随机选择一个路段及其对应的日期
        
        Returns:
            (section_id, date) 元组
        """
        if self.section_dates:
            section_id = random.choice(list(self.section_dates.keys()))
            date = self.get_date_for_section(section_id)
            return section_id, date
        else:
            # 如果没有学习到路段数据，使用默认值
            section_id = random.choice(list(GANTRY_TO_SECTION.values()))
            date = self._random_date_in_range(self.default_date_range)
            return section_id, date


# ---------------------- 1.4 In-Context Demonstrations ----------------------

class DemonstrationManager:
    """上下文示例管理器"""
    
    # 示例获取策略 (Demonstration Acquirement)
    DEMONSTRATIONS = {
        "货车_正常": {
            "gantry_transaction_id": "GT20231115071543001234",
            "gantry_id": "G561553012000210010",  # 真实门架ID
            "gantry_type": "1",  # String: 1=路段
            "transaction_time": "2023-11-15T07:15:43",
            "entrance_time": "2023-11-15T06:20:10",
            "pay_fee": 5310,  # Integer: 90km * 0.59元/km * 100 (货车费率)
            "discount_fee": 265,  # Integer: 5310 * 5%
            "fee_mileage": "90000",  # String: 90公里 = 90000米
            "media_type": 1,  # Int: 1=OBU
            "vehicle_type": "11",  # String: 2轴货车
            "vehicle_sign": "0x01",  # String: 车辆状态标识(非优惠车)
            "transaction_type": "06",  # String: PBOC传统交易
            "pass_state": "1",  # String: 1=有入口
            "axle_count": "2",  # String
            "total_weight": "15000",  # String: 15吨
            "cpu_card_type": "1",  # String: 1=储值卡
            "pass_id": "PASS2023111507154300123456",
            "section_id": "G5615530120",  # 真实路段ID
            "section_name": "麻文高速"  # 真实路段名称
        },
        "客车_正常": {
            "gantry_transaction_id": "GT20231115094510002345",
            "gantry_id": "G761153001000110010",  # 真实门架ID
            "gantry_type": "1",  # String: 1=路段
            "transaction_time": "2023-11-15T09:45:10",
            "entrance_time": "2023-11-15T08:30:25",
            "pay_fee": 2700,  # Integer: 60km * 0.45元/km * 100 (一类客车)
            "discount_fee": 135,  # Integer: 2700 * 5%
            "fee_mileage": "60000",  # String: 60公里
            "media_type": 1,  # Int: 1=OBU
            "vehicle_type": "1",  # String: 客车1型
            "vehicle_sign": "0x01",  # String: 车辆状态标识(非优惠车)
            "transaction_type": "06",  # String: PBOC传统交易
            "pass_state": "1",  # String: 1=有入口
            "axle_count": "2",  # String
            "total_weight": "2500",  # String: 2.5吨
            "cpu_card_type": "2",  # String: 2=记账卡
            "pass_id": "PASS2023111509451000234567",
            "section_id": "G7611530010",  # 真实路段ID
            "section_name": "都香高速"  # 真实路段名称
        },
        "货车_超载": {
            "gantry_transaction_id": "GT20231115121005003456",
            "gantry_id": "S001053001000210010",  # 真实门架ID
            "gantry_type": "1",  # String: 1=路段
            "transaction_time": "2023-11-15T12:10:05",
            "entrance_time": "2023-11-15T10:35:40",
            "pay_fee": 7080,  # Integer: 120km * 0.59元/km * 100 (货车费率)
            "discount_fee": 0,  # Integer: 超载无折扣
            "fee_mileage": "120000",  # String: 120公里
            "media_type": 2,  # Int: 2=CPC卡
            "vehicle_type": "12",  # String: 3轴货车
            "vehicle_sign": "0x01",  # String: 车辆状态标识(非优惠车)
            "transaction_type": "06",  # String: PBOC传统交易
            "pass_state": "2",  # String: 2=无入口
            "axle_count": "3",  # String
            "total_weight": "28000",  # String: 28吨（超过25吨限重）
            "cpu_card_type": "1",  # String: 1=储值卡
            "pass_id": "PASS2023111512100500345678",
            "section_id": "S0010530010",  # 真实路段ID
            "section_name": "彝良至昭通高速"  # 真实路段名称
        }
    }
    
    def __init__(self, use_heuristic: bool = True):
        self.demonstrations = self.DEMONSTRATIONS
        self.real_samples = []
        self.use_heuristic = use_heuristic  # 是否使用启发式高质量选择
        self.sample_quality_cache = {}  # 缓存样本质量评分

    def load_samples_from_file(self, file_path: str):
        """从文件加载真实样本作为示例"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                samples = json.load(f)
            
            if isinstance(samples, list):
                self.real_samples = samples
                print(f"  [提示] 已加载 {len(samples)} 条真实样本作为示例池")
            else:
                print("  [警告] 样本文件格式错误，应为JSON列表")
        except Exception as e:
            print(f"  [警告] 加载样本文件失败: {e}")

    def select_demonstrations(self, condition: GenerationCondition, k: int = 2, 
                             use_multi_candidate: bool = True) -> List[Dict]:
        """示例选择策略 (Demonstration Selection)
        
        启发式方法：
        1. SuperGen方法 - 基于生成能力（质量评分）
        2. 置信度过滤 - 移除低质量样本
        3. 不确定性评估 - 保留难样本
        4. 相似度排序 - 选择与条件最相关的样本
        5. 多候选验证 - 生成多个候选并选择最一致的（新增）
        """
        if self.use_heuristic and self.real_samples:
            if use_multi_candidate:
                return self._multi_candidate_select(condition, k)
            else:
                return self._heuristic_select(condition, k)
        
        # 简单随机选择（原方法）
        if self.real_samples:
            try:
                return random.sample(self.real_samples, min(k, len(self.real_samples)))
            except:
                pass

        selected = []
        
        # 根据条件选择最相关的示例
        if condition.scenario == "超载":
            selected.append(self.demonstrations["货车_超载"])
        
        if condition.vehicle_type == "货车":
            selected.append(self.demonstrations["货车_正常"])
        elif condition.vehicle_type == "客车":
            selected.append(self.demonstrations["客车_正常"])
        else:
            # 默认混合示例
            selected.extend([
                self.demonstrations["货车_正常"],
                self.demonstrations["客车_正常"]
            ])
        
        return selected[:k]
    
    def _heuristic_select(self, condition: GenerationCondition, k: int) -> List[Dict]:
        """启发式高质量样本选择
        
        核心思路：
        1. 样本质量评分 - 基于多个指标（置信度）
        2. 相似度排序 - 选择与条件最匹配的样本
        3. 不确定性过滤 - 保留中等难度样本
        4. 多样性保证 - 避免选择过于相似的样本
        """
        # Step 1: 质量评分与置信度过滤
        qualified_samples = []
        for sample in self.real_samples:
            quality_score = self._calculate_quality_score(sample)
            
            # 低置信度过滤：移除质量分 < 0.5 的样本
            if quality_score < 0.5:
                continue
                
            qualified_samples.append((sample, quality_score))
        
        if not qualified_samples:
            return random.sample(self.real_samples, min(k, len(self.real_samples)))
        
        # Step 2: 相似度计算与排序
        scored_samples = []
        for sample, quality in qualified_samples:
            similarity = self._calculate_similarity(sample, condition)
            uncertainty = self._calculate_uncertainty(sample)
            
            # 综合得分 = 质量 * 0.4 + 相似度 * 0.4 + 不确定性 * 0.2
            # 不确定性高（难样本）会获得更高分数
            final_score = quality * 0.4 + similarity * 0.4 + uncertainty * 0.2
            scored_samples.append((sample, final_score, uncertainty))
        
        # Step 3: 不确定性过滤 - 移除过于简单的样本（不确定性 < 0.2）
        filtered_samples = [(s, score) for s, score, unc in scored_samples if unc > 0.2]
        
        if not filtered_samples:
            filtered_samples = [(s, score) for s, score, _ in scored_samples]
        
        # Step 4: 按综合得分排序并选择 top-k
        filtered_samples.sort(key=lambda x: x[1], reverse=True)
        
        # Step 5: 多样性保证 - 从 top-2k 中选择 k 个多样化样本
        candidate_pool = filtered_samples[:min(k * 2, len(filtered_samples))]
        selected = self._diverse_sampling([s for s, _ in candidate_pool], k)
        
        return selected
    
    def _calculate_quality_score(self, sample: Dict) -> float:
        """样本质量评分（模拟生成能力/置信度）
        
        基于SuperGen思想：评估样本的生成概率/质量
        这里使用启发式规则近似：
        1. 字段完整性
        2. 数据一致性
        3. 业务逻辑合规性
        """
        # 使用缓存
        sample_id = sample.get("gantry_transaction_id", "")
        if sample_id in self.sample_quality_cache:
            return self.sample_quality_cache[sample_id]
        
        score = 1.0
        
        # 1. 字段完整性检查（占30%）
        required_fields = ["gantry_id", "vehicle_type", "transaction_time", 
                          "entrance_time", "pay_fee", "fee_mileage"]
        missing = sum(1 for f in required_fields if not sample.get(f))
        completeness = 1.0 - (missing / len(required_fields))
        score *= (0.3 * completeness + 0.7)
        
        # 2. 时间逻辑一致性（占25%）
        try:
            entrance = datetime.fromisoformat(sample.get("entrance_time", ""))
            transaction = datetime.fromisoformat(sample.get("transaction_time", ""))
            if entrance < transaction:
                time_diff = (transaction - entrance).total_seconds() / 3600
                if 0.5 <= time_diff <= 6:  # 合理范围
                    score *= 1.0
                else:
                    score *= 0.8
            else:
                score *= 0.3  # 时间顺序错误，严重扣分
        except:
            score *= 0.5
        
        # 3. 费用逻辑一致性（占25%）
        try:
            pay_fee = int(sample.get("pay_fee", 0))
            discount = int(sample.get("discount_fee", 0))
            mileage = int(sample.get("fee_mileage", "0"))
            vehicle_type = sample.get("vehicle_type", "1")
            
            # 根据车型计算期望费用（云南省标准）
            expected_fee = calculate_expected_fee(mileage, vehicle_type)
            if pay_fee > 0 and expected_fee > 0 and 0.7 <= pay_fee / expected_fee <= 1.3:
                score *= 1.0
            else:
                score *= 0.7
            
            # 优惠不应超过应付费用
            if discount <= pay_fee:
                score *= 1.0
            else:
                score *= 0.4
        except:
            score *= 0.6
        
        # 4. 车辆逻辑（占20%）
        try:
            vtype = int(sample.get("vehicle_type", "1"))
            axle = sample.get("axle_count", "2")
            
            # 客车轴数应为2
            if 1 <= vtype <= 4 and axle == "2":
                score *= 1.0
            elif 1 <= vtype <= 4:
                score *= 0.6
        except:
            score *= 0.7
        
        # 缓存结果
        self.sample_quality_cache[sample_id] = max(0.0, min(1.0, score))
        return self.sample_quality_cache[sample_id]
    
    def _calculate_similarity(self, sample: Dict, condition: GenerationCondition) -> float:
        """计算样本与生成条件的相似度"""
        similarity = 0.0
        
        # 车型匹配（权重40%）
        if condition.vehicle_type:
            try:
                vtype = int(sample.get("vehicle_type", "1"))
                is_truck = 11 <= vtype <= 16 or 21 <= vtype <= 26
                
                if condition.vehicle_type == "货车" and is_truck:
                    similarity += 0.4
                elif condition.vehicle_type == "客车" and not is_truck:
                    similarity += 0.4
            except:
                pass
        else:
            similarity += 0.2  # 无约束时给基础分
        
        # 场景匹配（权重30%）
        if condition.scenario:
            if condition.scenario == "超载":
                try:
                    axle = sample.get("axle_count", "2")
                    weight = int(sample.get("total_weight", "0"))
                    limits = {"2": 18000, "3": 25000, "4": 31000, "5": 43000, "6": 49000}
                    if weight > limits.get(axle, 49000):
                        similarity += 0.3
                except:
                    pass
            elif condition.scenario == "异常" and sample.get("pass_state") == "2":
                similarity += 0.3
        else:
            similarity += 0.15
        
        # 时段匹配（权重30%）
        if condition.time_period:
            try:
                hour = datetime.fromisoformat(sample["transaction_time"]).hour
                period_match = {
                    "早高峰": 7 <= hour < 9,
                    "晚高峰": 17 <= hour < 19,
                    "深夜": hour >= 23 or hour < 5,
                    "平峰": True
                }
                if period_match.get(condition.time_period, False):
                    similarity += 0.3
            except:
                pass
        else:
            similarity += 0.15
        
        return max(0.0, min(1.0, similarity))
    
    def _calculate_uncertainty(self, sample: Dict) -> float:
        """计算样本不确定性（难度）
        
        基于论文思想：保留难样本，过滤简单样本
        难度高的样本（不确定性高）对模型学习更有价值
        
        难度指标：
        1. 数据复杂度（字段数值范围）
        2. 边界情况（接近限制的值）
        3. 异常特征（非常规组合）
        """
        uncertainty = 0.5  # 基础不确定性
        
        # 1. 车辆复杂度（货车 > 客车）
        try:
            vtype = int(sample.get("vehicle_type", "1"))
            if 11 <= vtype <= 16:  # 货车
                uncertainty += 0.15
            elif 21 <= vtype <= 26:  # 专项车
                uncertainty += 0.25
        except:
            pass
        
        # 2. 接近限重边界（高难度）
        try:
            axle = sample.get("axle_count", "2")
            weight = int(sample.get("total_weight", "0"))
            limits = {"2": 18000, "3": 25000, "4": 31000, "5": 43000, "6": 49000}
            limit = limits.get(axle, 49000)
            
            weight_ratio = weight / limit
            # 在 0.85-1.15 范围内（接近边界）增加不确定性
            if 0.85 <= weight_ratio <= 1.15:
                uncertainty += 0.2
        except:
            pass
        
        # 3. 异常状态（增加难度）
        if sample.get("pass_state") == "2":  # 无入口信息
            uncertainty += 0.15
        if sample.get("transaction_type") != "1":  # 非正常交易
            uncertainty += 0.1
        
        return max(0.0, min(1.0, uncertainty))
    
    def _diverse_sampling(self, candidates: List[Dict], k: int) -> List[Dict]:
        """多样性采样 - 避免选择过于相似的样本"""
        if len(candidates) <= k:
            return candidates
        
        selected = [candidates[0]]  # 先选择最高分样本
        candidates = candidates[1:]
        
        while len(selected) < k and candidates:
            # 选择与已选样本最不相似的候选
            max_min_distance = -1
            best_candidate = None
            best_idx = -1
            
            for idx, candidate in enumerate(candidates):
                # 计算与所有已选样本的最小距离
                min_distance = min(
                    self._sample_distance(candidate, s) for s in selected
                )
                
                if min_distance > max_min_distance:
                    max_min_distance = min_distance
                    best_candidate = candidate
                    best_idx = idx
            
            if best_candidate:
                selected.append(best_candidate)
                candidates.pop(best_idx)
            else:
                break
        
        return selected
    
    def _sample_distance(self, s1: Dict, s2: Dict) -> float:
        """计算两个样本之间的距离（差异度）"""
        distance = 0.0
        
        # 车型差异
        try:
            v1 = int(s1.get("vehicle_type", "1"))
            v2 = int(s2.get("vehicle_type", "1"))
            distance += abs(v1 - v2) / 26.0  # 归一化
        except:
            pass
        
        # 里程差异
        try:
            m1 = int(s1.get("fee_mileage", "0"))
            m2 = int(s2.get("fee_mileage", "0"))
            distance += min(abs(m1 - m2) / 200000.0, 1.0)  # 最大200km
        except:
            pass
        
        # 时段差异
        try:
            h1 = datetime.fromisoformat(s1["transaction_time"]).hour
            h2 = datetime.fromisoformat(s2["transaction_time"]).hour
            distance += min(abs(h1 - h2) / 24.0, 1.0)
        except:
            pass
        
        return distance / 3.0  # 归一化到 [0, 1]
    
    def _multi_candidate_select(self, condition: GenerationCondition, k: int, 
                               n_runs: int = 3) -> List[Dict]:
        """多候选相互验证选择策略
        
        基于论文思想：生成多个候选结果，通过相互一致性验证质量
        
        Args:
            condition: 生成条件
            k: 需要选择的样本数
            n_runs: 运行次数，生成n_runs组候选
        
        Returns:
            经过一致性验证的高质量样本
        """
        # Step 1: 生成多组候选
        candidate_groups = []
        for _ in range(n_runs):
            candidates = self._heuristic_select(condition, k)
            candidate_groups.append(candidates)
        
        # Step 2: 计算候选之间的一致性（通过样本距离）
        # 对每个样本位置，选择在所有候选组中最一致的样本
        final_selection = []
        
        for pos in range(k):
            # 收集该位置的所有候选样本
            position_candidates = []
            for group in candidate_groups:
                if pos < len(group):
                    position_candidates.append(group[pos])
            
            if not position_candidates:
                continue
            
            # 计算每个候选与其他候选的平均相似度（1-距离）
            best_sample = None
            best_consistency = -1
            
            for candidate in position_candidates:
                # 计算该候选与其他所有候选的平均相似度
                similarities = []
                for other in position_candidates:
                    if candidate != other:
                        dist = self._sample_distance(candidate, other)
                        similarity = 1 - dist  # 距离越小，相似度越高
                        similarities.append(similarity)
                
                avg_similarity = sum(similarities) / len(similarities) if similarities else 0
                
                # 选择平均相似度最高的（最一致的）
                if avg_similarity > best_consistency:
                    best_consistency = avg_similarity
                    best_sample = candidate
            
            if best_sample:
                final_selection.append(best_sample)
        
        # Step 3: 如果一致性验证后样本不足，补充高质量样本
        if len(final_selection) < k:
            additional = self._heuristic_select(condition, k - len(final_selection))
            # 避免重复
            for sample in additional:
                if sample not in final_selection:
                    final_selection.append(sample)
                if len(final_selection) >= k:
                    break
        
        return final_selection[:k]
    
    def format_demonstrations(self, demos: List[Dict]) -> str:
        """格式化示例为提示词"""
        formatted = "## 参考示例\n\n"
        for i, demo in enumerate(demos, 1):
            formatted += f"### 示例 {i}\n```json\n{json.dumps(demo, ensure_ascii=False, indent=2)}\n```\n\n"
        return formatted


# ---------------------- 1.4 Sample-Wise Decomposition ----------------------

class SampleWiseDecomposer:
    """样本级别分解 - 将样本拆分为多个字段组分步生成"""
    
    # 字段分组
    FIELD_GROUPS = {
        "identity": ["gantry_transaction_id", "pass_id", "gantry_id", "section_id", "section_name"],
        "time": ["transaction_time", "entrance_time"],
        "vehicle": ["vehicle_type", "axle_count", "total_weight", "vehicle_sign"],
        "fee": ["pay_fee", "discount_fee", "fee_mileage"],
        "status": ["gantry_type", "media_type", "transaction_type", "pass_state", "cpu_card_type"]
    }
    
    def __init__(self, section_date_mapper: Optional['SectionDateMapper'] = None, learned_stats: Dict = None):
        """初始化样本分解器
        
        Args:
            section_date_mapper: 路段-日期映射器，用于确保生成的数据使用正确的日期
            learned_stats: 从真实数据学到的统计信息（费用、里程的均值和标准差）
        """
        self.section_date_mapper = section_date_mapper
        # 注意：必须保持引用，不能用or{}，否则空字典会被替换成新字典
        self.learned_stats = learned_stats if learned_stats is not None else {}
    
    def decompose_and_generate(self, condition: GenerationCondition) -> Dict:
        """分步生成完整样本"""
        sample = {}
        context = {"condition": condition}
        
        # 按依赖顺序生成
        generation_order = ["identity", "time", "vehicle", "status", "fee"]
        
        for group_name in generation_order:
            group_data = self._generate_field_group(group_name, sample, context)
            sample.update(group_data)
        
        return sample
    
    def _generate_field_group(self, group_name: str, current_sample: Dict, context: Dict) -> Dict:
        """生成单个字段组"""
        condition = context["condition"]
        
        prompts = {
            "identity": self._get_identity_prompt(condition),
            "time": self._get_time_prompt(condition, current_sample),
            "vehicle": self._get_vehicle_prompt(condition),
            "fee": self._get_fee_prompt(current_sample),
            "status": self._get_status_prompt(condition)
        }
        
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "你是数据字段生成器。只输出JSON对象，不要其他文字。"},
                {"role": "user", "content": prompts[group_name]}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        content = response.choices[0].message.content.strip()
        content = self._clean_json(content)
        
        try:
            result = json.loads(content)
            
            # 强制修正 identity 组的门架路段信息，确保符合真实拓扑
            if group_name == "identity":
                real_gantry_id = random.choice(list(GANTRY_TO_SECTION.keys()))
                real_section_id = GANTRY_TO_SECTION[real_gantry_id]
                real_section_name = SECTION_NAME_BY_ID.get(real_section_id, "未知路段")
                
                result["gantry_id"] = real_gantry_id
                result["section_id"] = real_section_id
                result["section_name"] = real_section_name
                
            return result
        except json.JSONDecodeError:
            # 回退到规则生成
            return self._fallback_generate(group_name, condition, current_sample)
    
    def _clean_json(self, content: str) -> str:
        """清理JSON格式"""
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
        return content.strip()
    
    def _get_identity_prompt(self, condition: GenerationCondition) -> str:
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        # 从真实映射中随机选择一个示例作为参考
        example_gantry = random.choice(list(GANTRY_TO_SECTION.keys()))
        example_section = GANTRY_TO_SECTION[example_gantry]
        example_name = SECTION_NAME_BY_ID.get(example_section, "")
        
        return f"""生成门架交易身份字段:
- gantry_transaction_id: 门架ID + 时间戳 + 随机数 (如: {example_gantry}{ts}1)
- pass_id: "010000PASS{ts}" + 8位随机数  
- gantry_id: 从固定集合中选择 (如: {example_gantry})
- section_id: 对应的路段ID (如: {example_section})
- section_name: 对应的路段名称 (如: {example_name})

注意：gantry_id、section_id、section_name 必须从真实映射关系中选择，保持一致性。

输出JSON对象:"""

    def _get_time_prompt(self, condition: GenerationCondition, sample: Dict) -> str:
        # 如果有section_date_mapper且样本中有section_id，使用路段对应的日期
        if self.section_date_mapper and sample.get("section_id"):
            base_date = self.section_date_mapper.get_date_for_section(sample.get("section_id"))
        elif condition.base_time:
            base_date = condition.base_time.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        time_hint = {
            "早高峰": "07:00-09:00",
            "晚高峰": "17:00-19:00",
            "平峰": "10:00-16:00",
            "深夜": "23:00-05:00"
        }.get(condition.time_period, "任意时段")
        
        return f"""生成时间字段:
- transaction_time: 交易时间，在 {base_date.date()} 的 {time_hint} 时段
- entrance_time: 入口时间，早于 transaction_time 30分钟到3小时

输出JSON对象 (ISO格式):"""

    def _get_vehicle_prompt(self, condition: GenerationCondition) -> str:
        if condition.vehicle_type == "货车" or condition.scenario == "超载":
            return """生成货车字段:
- vehicle_type: 字符串类型，"11"-"16"之间 (11=一型货车, 12=二型, 13=三型, 14=四型, 15=五型, 16=六型)
- axle_count: 字符串类型，"2"到"6"之间，与车型对应
- total_weight: 字符串类型，根据轴数，接近但不超过限重(2轴18000/3轴25000/4轴31000/5轴43000/6轴49000)，单位kg
- vehicle_sign: 字符串类型，"0x01"(非优惠车)/"0x02"(绿通车)/"0x04"(集装箱车)/"0xff"(默认)

""" + ("注意：这是超载场景，total_weight应超过限重5%-20%，如5轴车重量在45000-52000之间" if condition.scenario == "超载" else "") + """

输出JSON对象:"""
        else:
            return """生成客车字段:
- vehicle_type: 字符串类型，"1"-"4"之间 (1=一型客车, 2=二型, 3=三型, 4=四型)
- axle_count: 字符串类型，"2"
- total_weight: 字符串类型，2000-5000之间，单位kg
- vehicle_sign: 字符串类型，"0x01"(非优惠车)/"0xff"(默认)

输出JSON对象:"""

    def _get_fee_prompt(self, sample: Dict) -> str:
        mileage = random.randint(20000, 150000)
        
        # 根据车型计算费率（云南省标准）
        vehicle_type = sample.get("vehicle_type", "1")
        if vehicle_type in ["1", "2", "3", "4"]:
            rate = YUNNAN_TOLL_RATES["passenger"].get(vehicle_type, 0.45)
            rate_desc = f"{rate}元/公里(客车{vehicle_type}类)"
        else:
            rate = YUNNAN_TOLL_RATES["truck"]["normal"] * 0.8 + YUNNAN_TOLL_RATES["truck"]["bridge"] * 0.2
            rate_desc = f"{rate:.2f}元/公里(货车加权平均)"
        
        expected_fee = int(mileage / 1000 * rate * 100)
        
        return f"""生成费用字段，里程约 {mileage} 米:
- pay_fee: 应付金额(分)，约 {expected_fee} 分 ({rate_desc})
- discount_fee: ETC用户(约85%概率)为 pay_fee 的 5%，否则为 0
- fee_mileage: "{mileage}"

输出JSON对象:"""

    def _get_status_prompt(self, condition: GenerationCondition) -> str:
        scenario_hint = ""
        if condition.scenario == "超载":
            scenario_hint = "注意：超载场景下 pass_state 应为 \"2\"(异常)"
        elif condition.scenario == "异常":
            scenario_hint = "注意：异常场景下 transaction_type 可能为 \"09\"(复合交易) 或 pass_state 为 \"2\""
        
        return f"""生成状态字段（注意类型）:
- gantry_type: String类型，"1"(路段门架)/"2"(省界入口)/"3"(省界出口)，路段门架(1)占80%
- media_type: Int类型，1(OBU)/2(CPC卡)，OBU占85% 【注意：这是整数，不用引号】
- transaction_type: String类型，"06"(PBOC传统交易)/"09"(PBOC复合交易)，正常为"06"占95%
- pass_state: String类型，"1"(有入口)/"2"(无入口)，有入口占98%
- cpu_card_type: String类型，"0"(默认)/"1"(储值卡)/"2"(记账卡)

{scenario_hint}

输出JSON对象:"""

    def _fallback_generate(self, group_name: str, condition: GenerationCondition, sample: Dict) -> Dict:
        """基于规则的回退生成"""
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        rand6 = str(random.randint(100000, 999999))
        rand8 = str(random.randint(10000000, 99999999))
        
        if group_name == "identity":
            # 从真实映射中随机选择一个门架
            real_gantry_id = random.choice(list(GANTRY_TO_SECTION.keys()))
            real_section_id = GANTRY_TO_SECTION[real_gantry_id]
            real_section_name = SECTION_NAME_BY_ID.get(real_section_id, "未知路段")
            
            return {
                "gantry_transaction_id": f"{real_gantry_id}{ts}{rand6[:1]}",  # 门架ID(19)+时间(14)+1位 = 34位 (标准约50位内)
                "pass_id": f"010000PASS{ts}{rand8}",
                "gantry_id": real_gantry_id,
                "section_id": real_section_id,
                "section_name": real_section_name
            }
        elif group_name == "time":
            # 如果有section_date_mapper且样本中有section_id，使用路段对应的日期
            if self.section_date_mapper and sample.get("section_id"):
                base_date = self.section_date_mapper.get_date_for_section(sample.get("section_id"))
            elif condition.base_time:
                base_date = condition.base_time.replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            trans_time = base_date.replace(hour=random.randint(6, 22), minute=random.randint(0, 59))
            entrance_time = trans_time - timedelta(hours=random.uniform(0.5, 3))
            return {
                "transaction_time": trans_time.isoformat(),
                "entrance_time": entrance_time.isoformat()
            }
        elif group_name == "vehicle":
            if condition.vehicle_type == "货车" or random.random() < 0.6:
                # 货车轴数与车型对应: 2轴=11, 3轴=12, 4轴=13/14, 5轴=15, 6轴=16
                axle = random.choice(["2", "3", "4", "5", "6"])
                axle_to_vtype = {"2": "11", "3": "12", "4": "14", "5": "15", "6": "16"}
                limits = {"2": 18000, "3": 25000, "4": 31000, "5": 43000, "6": 49000}
                weight = int(limits[axle] * random.uniform(0.6, 0.95))
                if condition.scenario == "超载":
                    weight = int(limits[axle] * random.uniform(1.05, 1.20))
                return {"vehicle_type": axle_to_vtype[axle], "axle_count": axle, "total_weight": str(weight), "vehicle_sign": "0x01"}
            else:
                # 客车: 1=一型, 2=二型, 3=三型, 4=四型
                return {"vehicle_type": random.choice(["1", "2"]), "axle_count": "2", "total_weight": str(random.randint(2000, 5000)), "vehicle_sign": "0x01"}
        elif group_name == "fee":
            # 根据车型使用对应的统计信息生成（关键改进！）
            vehicle_type = sample.get("vehicle_type", "1")
            
            # 判断车型
            if vehicle_type in ["1", "2", "3", "4", "5"]:
                vtype_key = "passenger"  # 客车
            else:
                vtype_key = "truck"  # 货车
            
            # 优先使用按车型的统计信息
            if (self.learned_stats and 'by_vehicle' in self.learned_stats and 
                vtype_key in self.learned_stats['by_vehicle']):
                # 使用该车型的统计信息
                veh_stats = self.learned_stats['by_vehicle'][vtype_key]
                
                # 1. 先生成里程
                mileage_mean = veh_stats['fee_mileage']['mean']
                mileage_std = veh_stats['fee_mileage']['std']
                mileage = max(1000, int(random.gauss(mileage_mean, mileage_std)))
                
                # 2. 根据该车型的相关系数生成费用
                fee_mean = veh_stats['pay_fee']['mean']
                fee_std = veh_stats['pay_fee']['std']
                corr = veh_stats['correlation']
                
                if abs(corr) > 0.3:
                    # 相关性较强，使用线性关系
                    slope = corr * fee_std / (mileage_std + 1e-10)
                    expected_fee = fee_mean + slope * (mileage - mileage_mean)
                    noise_std = fee_std * np.sqrt(max(0, 1 - corr**2))
                    pay_fee = max(10, int(expected_fee + random.gauss(0, noise_std)))
                else:
                    # 相关性弱，独立生成
                    pay_fee = max(10, int(random.gauss(fee_mean, fee_std)))
            
            # 回退：使用总体统计信息
            elif self.learned_stats and 'mileage' in self.learned_stats and 'fee' in self.learned_stats:
                mileage_mean = self.learned_stats['mileage']['mean']
                mileage_std = self.learned_stats['mileage']['std']
                mileage = max(1000, int(random.gauss(mileage_mean, mileage_std)))
                
                fee_mean = self.learned_stats['fee']['mean']
                fee_std = self.learned_stats['fee']['std']
                
                if 'correlation' in self.learned_stats and abs(self.learned_stats['correlation']) > 0.3:
                    corr = self.learned_stats['correlation']
                    slope = corr * fee_std / (mileage_std + 1e-10)
                    expected_fee = fee_mean + slope * (mileage - mileage_mean)
                    noise_std = fee_std * np.sqrt(max(0, 1 - corr**2))
                    pay_fee = max(10, int(expected_fee + random.gauss(0, noise_std)))
                else:
                    pay_fee = max(10, int(random.gauss(fee_mean, fee_std)))
            else:
                # 回退到原来的逻辑
                mileage = random.randint(20000, 150000)  # 20-150公里
                
                # 根据车型计算费率（云南省标准）
                vehicle_type = sample.get("vehicle_type", "1")
                if vehicle_type in ["1", "2", "3", "4"]:
                    # 客车
                    rate = YUNNAN_TOLL_RATES["passenger"].get(vehicle_type, 0.45)
                else:
                    # 货车（11-16）和专项车（21-26），使用货车费率
                    # 80%普通路段 + 20%桥隧路段的加权平均
                    rate = YUNNAN_TOLL_RATES["truck"]["normal"] * 0.8 + YUNNAN_TOLL_RATES["truck"]["bridge"] * 0.2
                
                # 计算费用：里程(米) / 1000 * 费率(元/km) * 100(分/元)
                pay_fee = int(mileage / 1000 * rate * 100)
            
            discount = int(pay_fee * 0.05) if random.random() < 0.85 else 0
            return {"pay_fee": pay_fee, "discount_fee": discount, "fee_mileage": str(mileage)}
        else:  # status
            return {
                "gantry_type": random.choices(["1", "2", "3"], weights=[0.8, 0.1, 0.1])[0],  # String: 1=路段, 2=省界入口, 3=省界出口
                "media_type": random.choices([1, 2], weights=[0.85, 0.15])[0],  # Int: 1=OBU, 2=CPC卡
                "transaction_type": "06" if condition.scenario != "异常" else random.choice(["06", "09"]),  # String: PBOC定义
                "pass_state": "2" if condition.scenario in ["超载", "异常"] else "1",  # String: 1=有入口, 2=无入口
                "cpu_card_type": random.choices(["0", "1", "2"], weights=[0.1, 0.45, 0.45])[0]  # String: 0=默认, 1=储值卡, 2=记账卡
            }


# ---------------------- 1.5 Dataset-Wise Decomposition ----------------------

class DatasetWiseScheduler:
    """数据集级别分解 - 调度生成过程确保分布"""
    
    def __init__(self, target_distribution: Dict = None):
        self.target_distribution = target_distribution or {
            "vehicle": {"货车": 0.6, "客车": 0.4},
            "time": {"早高峰": 0.25, "晚高峰": 0.25, "平峰": 0.40, "深夜": 0.10},
            "scenario": {"正常": 0.90, "超载": 0.06, "异常": 0.04}
        }
        
        # 当前生成统计
        self.generated_stats = {
            "vehicle": Counter(),
            "time": Counter(),
            "scenario": Counter()
        }
    
    def get_next_condition(self) -> GenerationCondition:
        """基于指标的调度 (Metric Based)"""
        # 计算当前分布与目标分布的差距
        vehicle_type = self._select_by_gap("vehicle", {"货车": "货车", "客车": "客车"})
        time_period = self._select_by_gap("time", {"早高峰": "早高峰", "晚高峰": "晚高峰", "平峰": "平峰", "深夜": "深夜"})
        scenario = self._select_by_gap("scenario", {"正常": None, "超载": "超载", "异常": "异常"})
        
        return GenerationCondition(
            vehicle_type=vehicle_type,
            time_period=time_period,
            scenario=scenario,
            base_time=datetime.now()
        )
    
    def _select_by_gap(self, category: str, mapping: Dict) -> Optional[str]:
        """选择与目标分布差距最大的类别"""
        total = sum(self.generated_stats[category].values()) or 1
        
        gaps = {}
        for key, target_prob in self.target_distribution[category].items():
            current_prob = self.generated_stats[category].get(key, 0) / total
            gaps[key] = target_prob - current_prob
        
        # 选择差距最大的
        selected = max(gaps, key=gaps.get)
        return mapping.get(selected)
    
    def update_stats(self, sample: Dict):
        """更新生成统计"""
        # 车型: 1-4=客车, 11-16=货车, 21-26=专项车
        vtype_code = int(sample.get("vehicle_type", "1"))
        vtype = "货车" if 11 <= vtype_code <= 16 or 21 <= vtype_code <= 26 else "客车"
        self.generated_stats["vehicle"][vtype] += 1
        
        # 时段 (根据transaction_time推断)
        try:
            hour = datetime.fromisoformat(sample["transaction_time"]).hour
            if 7 <= hour < 9:
                period = "早高峰"
            elif 17 <= hour < 19:
                period = "晚高峰"
            elif 23 <= hour or hour < 5:
                period = "深夜"
            else:
                period = "平峰"
            self.generated_stats["time"][period] += 1
        except:
            self.generated_stats["time"]["平峰"] += 1
        
        # 场景
        if sample.get("pass_state") == "2":
            # 检查是否超载
            axle = sample.get("axle_count", "2")
            weight = int(sample.get("total_weight", "0"))
            limits = {"2": 18000, "3": 25000, "4": 31000, "5": 43000, "6": 49000}
            if weight > limits.get(axle, 49000):
                self.generated_stats["scenario"]["超载"] += 1
            else:
                self.generated_stats["scenario"]["异常"] += 1
        else:
            self.generated_stats["scenario"]["正常"] += 1


# ============================================================================
#                      II. CURATION - 策展阶段
# ============================================================================

# ---------------------- 2.1 Sample Filtering ----------------------

class SampleFilter:
    """样本过滤器"""
    
    # 轴数限重规则
    AXLE_WEIGHT_LIMITS = {"2": 18000, "3": 25000, "4": 31000, "5": 43000, "6": 49000}
    
    def __init__(self):
        self.filters = [
            self._check_time_logic,
            self._check_fee_logic,
            self._check_vehicle_logic,
            self._check_field_completeness
        ]
    
    def filter_samples(self, samples: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """过滤样本，返回 (合格样本, 不合格样本)"""
        passed = []
        failed = []
        
        for sample in samples:
            score, issues = self.evaluate_sample(sample)
            if score >= 0.6:  # 阈值
                passed.append(sample)
            else:
                failed.append({"sample": sample, "issues": issues, "score": score})
        
        return passed, failed
    
    def evaluate_sample(self, sample: Dict) -> Tuple[float, List[str]]:
        """评估单个样本，返回 (分数, 问题列表)"""
        issues = []
        
        for filter_func in self.filters:
            issue = filter_func(sample)
            if issue:
                issues.append(issue)
        
        # 计算分数 (每个问题扣0.2分)
        score = max(0, 1.0 - len(issues) * 0.2)
        return score, issues
    
    def _check_time_logic(self, sample: Dict) -> Optional[str]:
        """检查时间逻辑 (Consistency Based)"""
        try:
            entrance = datetime.fromisoformat(sample.get("entrance_time", ""))
            transaction = datetime.fromisoformat(sample.get("transaction_time", ""))
            
            if entrance >= transaction:
                return "时间错误: entrance_time >= transaction_time"
            
            diff = (transaction - entrance).total_seconds() / 3600
            if diff > 6:
                return f"时间异常: 行程时间 {diff:.1f} 小时过长"
        except:
            return "时间格式错误"
        return None
    
    def _check_fee_logic(self, sample: Dict) -> Optional[str]:
        """检查费用逻辑"""
        try:
            pay_fee = int(sample.get("pay_fee", 0))
            discount_fee = int(sample.get("discount_fee", 0))
            
            if discount_fee > pay_fee:
                return f"费用错误: discount_fee({discount_fee}) > pay_fee({pay_fee})"
            
            if pay_fee < 0:
                return "费用错误: pay_fee 为负数"
        except:
            return "费用字段格式错误"
        return None
    
    def _check_vehicle_logic(self, sample: Dict) -> Optional[str]:
        """检查车辆逻辑 (Learning Dynamics Based)"""
        try:
            vehicle_type = int(sample.get("vehicle_type", "1"))
        except:
            return "车型格式错误"
        axle_count = sample.get("axle_count", "2")
        
        # 客车(1-4)轴数应为2
        if 1 <= vehicle_type <= 4 and axle_count != "2":
            return f"车辆逻辑错误: 客车轴数应为2，实际为{axle_count}"
        
        # 货车(11-16)和专项车(21-26)检查限重
        if 11 <= vehicle_type <= 16 or 21 <= vehicle_type <= 26:
            try:
                weight = int(sample.get("total_weight", "0"))
                limit = self.AXLE_WEIGHT_LIMITS.get(axle_count, 49000)
                if weight > limit * 1.5:  # 超载50%以上视为数据错误
                    return f"重量异常: {weight}kg 超过 {axle_count}轴限重 {limit}kg 的50%"
            except:
                pass
        return None
    
    def _check_field_completeness(self, sample: Dict) -> Optional[str]:
        """检查字段完整性"""
        required = ["gantry_transaction_id", "vehicle_type", "transaction_time", "pay_fee"]
        missing = [f for f in required if not sample.get(f)]
        if missing:
            return f"缺失必要字段: {missing}"
        return None


# ---------------------- 2.2 Re-Weighting Strategies ----------------------

class SampleReweighter:
    """样本重加权策略 - SunGen双循环框架
    
    基于Gao等人的SunGen方法：
    - 内循环：保持权重不变，训练分类器
    - 外循环：基于验证集损失调整权重
    """
    
    def __init__(self, learning_rate: float = 0.1, n_iterations: int = 5):
        self.learning_rate = learning_rate
        self.n_iterations = n_iterations
        self.sample_filter = SampleFilter()
    
    def calculate_weights(self, samples: List[Dict], target_dist: Dict, 
                         validation_samples: Optional[List[Dict]] = None) -> List[float]:
        """计算每个样本的权重
        
        Args:
            samples: 训练样本集
            target_dist: 目标分布
            validation_samples: 验证集（可选）
        
        Returns:
            每个样本的权重列表
        """
        if validation_samples and len(validation_samples) > 0:
            # 使用SunGen双循环方法
            return self._sungen_reweight(samples, validation_samples, target_dist)
        else:
            # 回退到静态权重计算
            return self._static_reweight(samples, target_dist)
    
    def _static_reweight(self, samples: List[Dict], target_dist: Dict) -> List[float]:
        """静态权重计算（原方法）"""
        weights = []
        
        # 统计当前分布
        def get_vtype(s):
            try:
                vcode = int(s.get("vehicle_type", "1"))
                return "货车" if 11 <= vcode <= 16 or 21 <= vcode <= 26 else "客车"
            except:
                return "客车"
        
        current_dist = Counter()
        for s in samples:
            current_dist[get_vtype(s)] += 1
        
        total = len(samples)
        
        for s in samples:
            vtype = get_vtype(s)
            
            # 权重 = 目标比例 / 当前比例
            target_prob = target_dist.get("vehicle", {}).get(vtype, 0.5)
            current_prob = current_dist[vtype] / total
            
            weight = target_prob / current_prob if current_prob > 0 else 1.0
            weights.append(min(weight, 3.0))  # 限制最大权重
        
        return weights
    
    def _sungen_reweight(self, samples: List[Dict], validation_samples: List[Dict], 
                        target_dist: Dict) -> List[float]:
        """
SunGen双循环权重调整
        
        外循环：迭代调整权重
        内循环：基于当前权重评估样本质量
        """
        n_samples = len(samples)
        
        # 初始化权重（基于静态方法）
        weights = np.array(self._static_reweight(samples, target_dist))
        
        for iteration in range(self.n_iterations):
            # 内循环：评估当前权重下的样本质量
            sample_scores = self._evaluate_samples_with_weights(samples, weights)
            
            # 外循环：基于验证集计算损失并调整权重
            val_loss = self._compute_validation_loss(validation_samples)
            
            # 根据验证损失调整权重：
            # - 高质量样本（score > 0.7）增加权重
            # - 低质量样本（score < 0.5）减少权重
            for i, score in enumerate(sample_scores):
                if score > 0.7:
                    weights[i] *= (1 + self.learning_rate)
                elif score < 0.5:
                    weights[i] *= (1 - self.learning_rate)
            
            # 权重归一化
            weights = np.clip(weights, 0.1, 3.0)  # 限制范围
        
        return weights.tolist()
    
    def _evaluate_samples_with_weights(self, samples: List[Dict], 
                                       weights: np.ndarray) -> List[float]:
        """基于当前权重评估样本质量"""
        scores = []
        for sample in samples:
            score, _ = self.sample_filter.evaluate_sample(sample)
            scores.append(score)
        return scores
    
    def _compute_validation_loss(self, validation_samples: List[Dict]) -> float:
        """计算验证集损失"""
        if not validation_samples:
            return 0.0
        
        total_loss = 0.0
        for sample in validation_samples:
            score, _ = self.sample_filter.evaluate_sample(sample)
            # 损失 = 1 - 质量分
            loss = 1 - score
            total_loss += loss
        
        return total_loss / len(validation_samples)


# ---------------------- 2.3 Label Enhancement ----------------------

class LabelEnhancer:
    """标签增强器"""
    
    AXLE_WEIGHT_LIMITS = {"2": 18000, "3": 25000, "4": 31000, "5": 43000, "6": 49000}
    
    def enhance_sample(self, sample: Dict) -> Dict:
        """使用辅助模型增强标签 (Auxiliary Model Enhancement)"""
        enhanced = sample.copy()
        
        # 1. Label Refinery - 修正明显错误
        enhanced = self._refine_labels(enhanced)
        
        # 2. Knowledge Distillation - 补充缺失信息
        enhanced = self._distill_knowledge(enhanced)
        
        return enhanced
    
    def _refine_labels(self, sample: Dict) -> Dict:
        """标签修正"""
        # 修正 discount_fee 超过 pay_fee
        pay_fee = int(sample.get("pay_fee", 0))
        discount_fee = int(sample.get("discount_fee", 0))
        if discount_fee > pay_fee:
            sample["discount_fee"] = int(pay_fee * 0.05)
        
        # 修正时间顺序
        try:
            entrance = datetime.fromisoformat(sample.get("entrance_time", ""))
            transaction = datetime.fromisoformat(sample.get("transaction_time", ""))
            if entrance >= transaction:
                new_entrance = transaction - timedelta(hours=random.uniform(0.5, 2))
                sample["entrance_time"] = new_entrance.isoformat()
        except:
            pass
        
        # 修正客车轴数 (客车车型1-4)
        try:
            vtype = int(sample.get("vehicle_type", "1"))
            if 1 <= vtype <= 4:
                sample["axle_count"] = "2"
        except:
            pass
        
        # 修正 gantry_id、section_id、section_name 的一致性
        gantry_id = sample.get("gantry_id", "")
        section_id = sample.get("section_id", "")
        
        # 如果 gantry_id 在映射表中，确保 section_id 和 section_name 正确
        if gantry_id in GANTRY_TO_SECTION:
            correct_section_id = GANTRY_TO_SECTION[gantry_id]
            correct_section_name = SECTION_NAME_BY_ID.get(correct_section_id, "未知路段")
            
            # 如果不一致，强制修正
            if section_id != correct_section_id:
                sample["section_id"] = correct_section_id
                sample["section_name"] = correct_section_name
        # 如果 gantry_id 不在映射表中，随机分配一个真实的门架-路段组合
        elif gantry_id:
            real_gantry_id = random.choice(list(GANTRY_TO_SECTION.keys()))
            real_section_id = GANTRY_TO_SECTION[real_gantry_id]
            real_section_name = SECTION_NAME_BY_ID.get(real_section_id, "未知路段")
            
            sample["gantry_id"] = real_gantry_id
            sample["section_id"] = real_section_id
            sample["section_name"] = real_section_name
        
        return sample
    
    def _distill_knowledge(self, sample: Dict) -> Dict:
        """知识蒸馏 - 补充推断字段"""
        
        # 根据 media_type 推断 discount_fee (media_type是Int类型：1=OBU)
        if sample.get("media_type") == 1 and sample.get("discount_fee", 0) == 0:
            pay_fee = int(sample.get("pay_fee", 0))
            sample["discount_fee"] = int(pay_fee * 0.05)
        
        # 根据超载情况设置 pass_state (货车11-16, 专项车21-26)
        try:
            vtype = int(sample.get("vehicle_type", "1"))
            if 11 <= vtype <= 16 or 21 <= vtype <= 26:
                axle = sample.get("axle_count", "2")
                weight = int(sample.get("total_weight", "0"))
                limit = self.AXLE_WEIGHT_LIMITS.get(axle, 49000)
                if weight > limit:
                    sample["pass_state"] = "2"  # 超载标记为无入口
        except:
            pass
        
        return sample


# ---------------------- 2.4 Auxiliary Model Enhancement ----------------------

class AuxiliaryModelEnhancer:
    """辅助模型增强器 - 使用第三方模型验证/修正数据
    
    这是一个扩展接口，用户可以根据需要实现自己的辅助模型。
    论文框架中提到的"通过人工审核或者引入第三方模型进行修正"。
    """
    
    def __init__(self):
        """初始化辅助模型"""
        # 这里可以加载额外的模型，例如：
        # - 车辆分类模型
        # - 费用预测模型  
        # - 异常检测模型
        pass
    
    def verify_with_classifier(self, samples: List[Dict]) -> List[Dict]:
        """使用分类模型验证车辆类型是否与轴数、重量匹配
        
        Args:
            samples: 待验证的样本
            
        Returns:
            验证后的样本（不匹配的会被标记或修正）
        """
        verified_samples = []
        
        for sample in samples:
            # 示例：使用规则验证（可替换为实际ML模型）
            verified = self._verify_vehicle_consistency(sample)
            verified_samples.append(verified)
        
        return verified_samples
    
    def _verify_vehicle_consistency(self, sample: Dict) -> Dict:
        """验证车辆参数一致性"""
        try:
            vtype = int(sample.get("vehicle_type", "1"))
            axle = sample.get("axle_count", "2")
            weight = int(sample.get("total_weight", "0"))
            
            # 客车（1-4）应该是2轴，2-5吨
            if 1 <= vtype <= 4:
                if axle != "2":
                    sample["axle_count"] = "2"
                    sample["_auxiliary_fixed"] = "axle_count"
                if not (2000 <= weight <= 5000):
                    sample["total_weight"] = str(random.randint(2500, 4500))
                    sample["_auxiliary_fixed"] = "total_weight"
            
            # 货车（11-16）轴数与重量应该合理匹配
            elif 11 <= vtype <= 16:
                expected_axles = {"11": "2", "12": "2", "13": "3", "14": "4", "15": "5", "16": "6"}
                expected = expected_axles.get(str(vtype))
                if expected and axle != expected:
                    sample["axle_count"] = expected
                    sample["_auxiliary_fixed"] = "axle_count"
        
        except:
            pass
        
        return sample
    
    def verify_with_regressor(self, samples: List[Dict]) -> List[Dict]:
        """使用回归模型验证费用合理性
        
        Args:
            samples: 待验证的样本
            
        Returns:
            验证后的样本
        """
        verified_samples = []
        
        for sample in samples:
            # 示例：使用简单的费用公式验证
            verified = self._verify_fee_reasonableness(sample)
            verified_samples.append(verified)
        
        return verified_samples
    
    def _verify_fee_reasonableness(self, sample: Dict) -> Dict:
        """验证费用合理性"""
        try:
            mileage = int(sample.get("fee_mileage", "0"))
            pay_fee = int(sample.get("pay_fee", 0))
            vtype = sample.get("vehicle_type", "1")
            
            # 粗略计算期望费用（可替换为实际回归模型）
            # 云南省标准：0.45元/公里 * 车型系数
            type_coef = {
                "1": 1.0, "2": 1.0, "3": 1.0, "4": 1.0,
                "11": 1.5, "12": 1.5, "13": 2.0, "14": 2.5, "15": 3.0, "16": 3.5
            }
            coef = type_coef.get(vtype, 1.0)
            expected_fee = int((mileage / 1000) * 0.45 * coef * 100)  # 转成分
            
            # 如果偏差超过50%，标记为异常
            if pay_fee > 0 and abs(pay_fee - expected_fee) / expected_fee > 0.5:
                sample["_fee_anomaly"] = True
                sample["_expected_fee"] = expected_fee
        
        except:
            pass
        
        return sample
    
    def manual_review_interface(self, samples: List[Dict], review_callback=None) -> List[Dict]:
        """人工审核接口
        
        Args:
            samples: 待审核的样本
            review_callback: 审核回调函数，接收样本并返回修正后的样本
            
        Returns:
            审核后的样本
        """
        if review_callback is None:
            # 如果没有提供回调，直接返回
            return samples
        
        reviewed_samples = []
        for sample in samples:
            reviewed = review_callback(sample)
            reviewed_samples.append(reviewed)
        
        return reviewed_samples
    
    def batch_verify(self, samples: List[Dict], 
                    use_classifier: bool = True,
                    use_regressor: bool = True) -> List[Dict]:
        """批量验证样本
        
        Args:
            samples: 待验证的样本
            use_classifier: 是否使用分类器验证
            use_regressor: 是否使用回归器验证
            
        Returns:
            验证后的样本
        """
        verified = samples
        
        if use_classifier:
            verified = self.verify_with_classifier(verified)
        
        if use_regressor:
            verified = self.verify_with_regressor(verified)
        
        return verified


# ============================================================================
#                      III. EVALUATION - 评估阶段
# ============================================================================

# ---------------------- 3.1 Direct Evaluation ----------------------

class DirectEvaluator:
    """直接评估器"""
    
    def __init__(self):
        self.sample_filter = SampleFilter()
        self.real_samples = []  # 存储从文件加载的真实样本
        self.benchmark_evaluator = None  # 用于Faithfulness下的Benchmark评估
    
    def set_benchmark_evaluator(self, benchmark_evaluator):
        """设置Benchmark评估器（用于Faithfulness评估）"""
        self.benchmark_evaluator = benchmark_evaluator
    
    def evaluate(self, samples: List[Dict], real_distribution: Dict = None) -> Dict:
        """综合评估（符合图2分类）"""
        results = {
            "faithfulness": self._evaluate_faithfulness(samples),
            "diversity": self._evaluate_diversity(samples, real_distribution)
        }
        
        # 计算综合分数（忠实度权重60%，多样性权重40%）
        results["overall_score"] = (
            results["faithfulness"]["score"] * 0.6 +
            results["diversity"]["score"] * 0.4
        )
        
        return results
    
    def _evaluate_faithfulness(self, samples: List[Dict]) -> Dict:
        """数据忠实度评估（符合图2：包含约束检查和Benchmark评估）
        
        包括两部分：
        1. Constraint Check: 约束遵守检查
           - 时间逻辑错误（入口时间 >= 交易时间）
           - 费用逻辑错误（优惠费 > 应付费）
           - 车辆标签错误（客车轴数、货车限重）
           - 路段-日期映射错误（事实性错误）
           - 字段完整性错误
        
        2. Benchmark Evaluation: 与真实数据对比（如果有）
           - 分布相似度
           - 统计特征相似度
           - 时间模式相似度
           - 相关性相似度
        """
        if not samples:
            return {"score": 0, "valid_count": 0, "total_count": 0}
        
        # Part 1: 约束检查
        valid_count = 0
        issues_count = Counter()
        section_date_errors = 0
        
        for sample in samples:
            # 检查业务规则错误
            score, issues = self.sample_filter.evaluate_sample(sample)
            
            # 检查路段-日期映射错误（事实性错误）
            if self._check_section_date_error(sample):
                issues.append("路段日期映射错误")
                section_date_errors += 1
            
            if score >= 0.8 and not self._check_section_date_error(sample):
                valid_count += 1
            
            for issue in issues:
                issues_count[issue.split(":")[0]] += 1
        
        constraint_score = valid_count / len(samples)
        
        # Part 2: Benchmark评估（如果有真实数据）
        benchmark_result = None
        benchmark_score = None
        
        if self.benchmark_evaluator and self.benchmark_evaluator.real_samples:
            benchmark_result = self.benchmark_evaluator.evaluate(samples)
            benchmark_score = benchmark_result.get('overall_similarity', 0)
        
        # 计算综合忠实度分数
        if benchmark_score is not None:
            # 有Benchmark时：约束检查50% + Benchmark 50%
            overall_score = constraint_score * 0.5 + benchmark_score * 0.5
        else:
            # 无Benchmark时：只看约束检查
            overall_score = constraint_score
        
        result = {
            "constraint_check": {
                "score": constraint_score,
                "valid_count": valid_count,
                "total_count": len(samples),
                "common_issues": dict(issues_count.most_common(5)),
                "section_date_errors": section_date_errors
            },
            "score": overall_score
        }
        
        # 如果有Benchmark评估，加入结果
        if benchmark_result:
            result["benchmark_evaluation"] = benchmark_result
        
        return result
    
    def _check_section_date_error(self, sample: Dict) -> bool:
        """检查路段-日期映射是否错误（事实性错误）"""
        section_id = sample.get("section_id")
        transaction_time = sample.get("transaction_time", "")
        
        if not section_id or not transaction_time:
            return False
        
        try:
            date = transaction_time[:10]
            expected_dates = PRECONFIGURED_SECTION_DATES.get(section_id, [])
            
            # 如果有预配置日期，检查是否匹配
            if expected_dates and date not in expected_dates:
                return True
        except:
            pass
        
        return False
    
    def _evaluate_diversity(self, samples: List[Dict], target_dist: Dict = None) -> Dict:
        """数据多样性评估：确保数据多样性，避免过拟合
        
        包括：
        - 词汇多样性：车型、门架、路段、时段的不同值数量
        - 样本独特性：检查重复样本
        - 分布覆盖度：确保覆盖目标分布中的各类别
        """
        if not samples:
            return {"score": 0}
        
        # 1. 词汇多样性（Vocabulary Diversity）
        unique_values = {
            "vehicle_type": len(set(s.get("vehicle_type") for s in samples)),
            "gantry_id": len(set(s.get("gantry_id") for s in samples)),
            "section_id": len(set(s.get("section_id") for s in samples)),
            "time_period": len(set(self._get_time_period(s) for s in samples))
        }
        
        # 2. 样本独特性（Sample Uniqueness）
        all_ids = [s.get("gantry_transaction_id") for s in samples]
        uniqueness = len(set(all_ids)) / len(all_ids) if all_ids else 0
        
        # 3. 分布覆盖度（Distribution Coverage）
        coverage_score = 1.0
        if target_dist and target_dist.get("vehicle"):
            # 检查是否覆盖了目标分布中的所有类型
            target_types = set(target_dist["vehicle"].keys())
            actual_types = set()
            for s in samples:
                vtype = self._classify_vehicle(s)
                actual_types.add(vtype)
            coverage_score = len(actual_types & target_types) / len(target_types) if target_types else 1.0
        
        # 计算多样性分数
        diversity_score = (
            min(unique_values["vehicle_type"] / 10, 1.0) * 0.2 +
            min(unique_values["gantry_id"] / 30, 1.0) * 0.25 +
            min(unique_values["section_id"] / 8, 1.0) * 0.2 +
            min(unique_values["time_period"] / 4, 1.0) * 0.15 +
            uniqueness * 0.2
        )
        
        return {
            "score": diversity_score,
            "unique_values": unique_values,
            "uniqueness": uniqueness,
            "coverage": coverage_score
        }
    
    def _classify_vehicle(self, sample: Dict) -> str:
        """分类车辆类型"""
        try:
            vcode = int(sample.get("vehicle_type", "1"))
            return "货车" if 11 <= vcode <= 16 or 21 <= vcode <= 26 else "客车"
        except:
            return "客车"
    
    def _get_time_period(self, sample: Dict) -> str:
        """获取时段"""
        try:
            time = datetime.fromisoformat(sample.get("transaction_time", ""))
            hour = time.hour
            if 7 <= hour < 9:
                return "早高峰"
            elif 17 <= hour < 19:
                return "晚高峰"
            elif 23 <= hour or hour < 5:
                return "深夜"
            else:
                return "平峰"
        except:
            return "未知"


# ---------------------- 3.2 Benchmark Evaluation (与真实数据对比) ----------------------

class BenchmarkEvaluator:
    """Benchmark评估器：与真实数据对比（论文框架核心）
    
    评估维度：
    1. 统计分布相似度（车型、路段、时段、费用等）
    2. 数值特征相似度（均值、方差、相关性）
    3. 时间模式相似度（高峰分布、日期分布）
    4. 业务逻辑一致性（费用-里程关系、车型-轴数关系）
    """
    
    def __init__(self, real_samples: List[Dict] = None):
        """初始化Benchmark评估器
        
        Args:
            real_samples: 真实数据样本（用作基准）
        """
        self.real_samples = real_samples or []
        self.real_stats = None
        
        if self.real_samples:
            self.real_stats = self._compute_statistics(self.real_samples)
    
    def load_real_samples(self, samples: List[Dict]) -> None:
        """加载真实样本数据"""
        self.real_samples = samples
        self.real_stats = self._compute_statistics(samples)
    
    def evaluate(self, generated_samples: List[Dict]) -> Dict:
        """综合评估：生成数据与真实数据的相似度
        
        Returns:
            包含各维度相似度分数的字典
        """
        if not self.real_samples:
            return {
                "error": "未加载真实数据，无法进行Benchmark评估",
                "overall_similarity": 0
            }
        
        gen_stats = self._compute_statistics(generated_samples)
        
        results = {
            "distribution_similarity": self._compare_distributions(gen_stats, self.real_stats),
            "statistical_similarity": self._compare_statistics(gen_stats, self.real_stats),
            "temporal_similarity": self._compare_temporal_patterns(generated_samples, self.real_samples),
            "correlation_similarity": self._compare_correlations(generated_samples, self.real_samples)
        }
        
        # 计算综合相似度（加权平均）
        results["overall_similarity"] = (
            results["distribution_similarity"]["score"] * 0.35 +
            results["statistical_similarity"]["score"] * 0.25 +
            results["temporal_similarity"]["score"] * 0.20 +
            results["correlation_similarity"]["score"] * 0.20
        )
        
        return results
    
    def _compute_statistics(self, samples: List[Dict]) -> Dict:
        """计算样本的统计特征"""
        if not samples:
            return {}
        
        stats = {
            "count": len(samples),
            "distributions": {},
            "numerical": {},
            "temporal": {}
        }
        
        # 1. 分布统计
        stats["distributions"]["vehicle_type"] = self._get_distribution(samples, "vehicle_type")
        stats["distributions"]["section_id"] = self._get_distribution(samples, "section_id")
        stats["distributions"]["media_type"] = self._get_distribution(samples, "media_type")
        
        # 2. 数值特征统计
        fees = []
        for s in samples:
            if s.get("pay_fee"):
                try:
                    fees.append(int(s.get("pay_fee")))
                except (ValueError, TypeError):
                    pass
        
        mileages = []
        for s in samples:
            if s.get("fee_mileage"):
                try:
                    # 处理字符串或浮点数
                    val = s.get("fee_mileage")
                    if isinstance(val, str):
                        mileages.append(int(float(val)))
                    else:
                        mileages.append(int(val))
                except (ValueError, TypeError):
                    pass
        
        if fees:
            stats["numerical"]["pay_fee"] = {
                "mean": np.mean(fees),
                "std": np.std(fees),
                "min": min(fees),
                "max": max(fees),
                "median": np.median(fees)
            }
        
        if mileages:
            stats["numerical"]["fee_mileage"] = {
                "mean": np.mean(mileages),
                "std": np.std(mileages),
                "min": min(mileages),
                "max": max(mileages),
                "median": np.median(mileages)
            }
        
        # 3. 时间模式统计
        time_periods = []
        for s in samples:
            try:
                time = datetime.fromisoformat(s.get("transaction_time", ""))
                hour = time.hour
                if 7 <= hour < 9:
                    period = "早高峰"
                elif 17 <= hour < 19:
                    period = "晚高峰"
                elif 23 <= hour or hour < 5:
                    period = "深夜"
                else:
                    period = "平峰"
                time_periods.append(period)
            except:
                pass
        
        if time_periods:
            stats["temporal"]["time_period_dist"] = self._get_distribution_from_list(time_periods)
        
        return stats
    
    def _get_distribution(self, samples: List[Dict], field: str) -> Dict[str, float]:
        """获取字段的概率分布"""
        values = [s.get(field) for s in samples if s.get(field)]
        if not values:
            return {}
        
        counter = Counter(values)
        total = len(values)
        return {k: v / total for k, v in counter.items()}
    
    def _get_distribution_from_list(self, values: List) -> Dict[str, float]:
        """从值列表获取概率分布"""
        if not values:
            return {}
        counter = Counter(values)
        total = len(values)
        return {k: v / total for k, v in counter.items()}
    
    def _compare_distributions(self, gen_stats: Dict, real_stats: Dict) -> Dict:
        """比较分布相似度（使用JS散度）"""
        results = {}
        score_sum = 0
        count = 0
        
        for field in ["vehicle_type", "section_id", "media_type"]:
            gen_dist = gen_stats.get("distributions", {}).get(field, {})
            real_dist = real_stats.get("distributions", {}).get(field, {})
            
            if gen_dist and real_dist:
                js_div = self._js_divergence(gen_dist, real_dist)
                similarity = 1 / (1 + js_div)  # 转换为相似度分数
                results[field] = {
                    "js_divergence": js_div,
                    "similarity": similarity,
                    "generated_dist": gen_dist,
                    "real_dist": real_dist
                }
                score_sum += similarity
                count += 1
        
        results["score"] = score_sum / count if count > 0 else 0
        return results
    
    def _compare_statistics(self, gen_stats: Dict, real_stats: Dict) -> Dict:
        """比较数值统计特征相似度"""
        results = {}
        score_sum = 0
        count = 0
        
        for field in ["pay_fee", "fee_mileage"]:
            gen_num = gen_stats.get("numerical", {}).get(field, {})
            real_num = real_stats.get("numerical", {}).get(field, {})
            
            if gen_num and real_num:
                # 比较均值和标准差
                mean_diff = abs(gen_num["mean"] - real_num["mean"]) / (real_num["mean"] + 1e-10)
                std_diff = abs(gen_num["std"] - real_num["std"]) / (real_num["std"] + 1e-10)
                
                # 转换为相似度分数（差异越小，相似度越高）
                mean_sim = 1 / (1 + mean_diff)
                std_sim = 1 / (1 + std_diff)
                
                results[field] = {
                    "mean_similarity": mean_sim,
                    "std_similarity": std_sim,
                    "generated": gen_num,
                    "real": real_num
                }
                score_sum += (mean_sim + std_sim) / 2
                count += 1
        
        results["score"] = score_sum / count if count > 0 else 0
        return results
    
    def _compare_temporal_patterns(self, gen_samples: List[Dict], real_samples: List[Dict]) -> Dict:
        """比较时间模式相似度"""
        gen_periods = []
        real_periods = []
        
        for s in gen_samples:
            try:
                time = datetime.fromisoformat(s.get("transaction_time", ""))
                hour = time.hour
                if 7 <= hour < 9:
                    gen_periods.append("早高峰")
                elif 17 <= hour < 19:
                    gen_periods.append("晚高峰")
                elif 23 <= hour or hour < 5:
                    gen_periods.append("深夜")
                else:
                    gen_periods.append("平峰")
            except:
                pass
        
        for s in real_samples:
            try:
                time = datetime.fromisoformat(s.get("transaction_time", ""))
                hour = time.hour
                if 7 <= hour < 9:
                    real_periods.append("早高峰")
                elif 17 <= hour < 19:
                    real_periods.append("晚高峰")
                elif 23 <= hour or hour < 5:
                    real_periods.append("深夜")
                else:
                    real_periods.append("平峰")
            except:
                pass
        
        if not gen_periods or not real_periods:
            return {"score": 0}
        
        gen_dist = self._get_distribution_from_list(gen_periods)
        real_dist = self._get_distribution_from_list(real_periods)
        
        js_div = self._js_divergence(gen_dist, real_dist)
        similarity = 1 / (1 + js_div)
        
        return {
            "score": similarity,
            "js_divergence": js_div,
            "generated_distribution": gen_dist,
            "real_distribution": real_dist
        }
    
    def _compare_correlations(self, gen_samples: List[Dict], real_samples: List[Dict]) -> Dict:
        """比较关键变量间的相关性（按车型分别评估）"""
        def extract_fee_mileage_by_vehicle(samples):
            """按车型提取费用和里程"""
            vehicle_data = {
                'passenger': {'fees': [], 'mileages': []},
                'truck': {'fees': [], 'mileages': []}
            }
            
            for s in samples:
                try:
                    fee = int(s.get("pay_fee", 0))
                    mileage_val = s.get("fee_mileage")
                    if isinstance(mileage_val, str):
                        mileage = int(float(mileage_val))
                    else:
                        mileage = int(mileage_val) if mileage_val else 0
                    
                    if fee > 0 and mileage > 0:
                        vtype = str(s.get("vehicle_type", "1"))
                        if vtype in ["1", "2", "3", "4", "5"]:
                            vehicle_data['passenger']['fees'].append(fee)
                            vehicle_data['passenger']['mileages'].append(mileage)
                        else:
                            vehicle_data['truck']['fees'].append(fee)
                            vehicle_data['truck']['mileages'].append(mileage)
                except:
                    pass
            
            return vehicle_data
        
        # 按车型提取数据
        gen_vehicle_data = extract_fee_mileage_by_vehicle(gen_samples)
        real_vehicle_data = extract_fee_mileage_by_vehicle(real_samples)
        
        # 分车型计算相关性
        by_vehicle_results = {}
        total_similarity = 0
        total_samples = 0
        
        for vtype in ['passenger', 'truck']:
            gen_fees = gen_vehicle_data[vtype]['fees']
            gen_mileages = gen_vehicle_data[vtype]['mileages']
            real_fees = real_vehicle_data[vtype]['fees']
            real_mileages = real_vehicle_data[vtype]['mileages']
            
            if len(gen_fees) >= 2 and len(real_fees) >= 2:
                try:
                    gen_corr = np.corrcoef(gen_fees, gen_mileages)[0, 1]
                    real_corr = np.corrcoef(real_fees, real_mileages)[0, 1]
                    
                    corr_diff = abs(gen_corr - real_corr)
                    similarity = 1 / (1 + corr_diff)
                    
                    by_vehicle_results[vtype] = {
                        "generated_correlation": gen_corr,
                        "real_correlation": real_corr,
                        "difference": corr_diff,
                        "similarity": similarity,
                        "sample_count": len(gen_fees)
                    }
                    
                    # 加权平均（按样本数加权）
                    total_similarity += similarity * len(gen_fees)
                    total_samples += len(gen_fees)
                except:
                    pass
        
        # 计算加权平均相似度
        if total_samples > 0:
            overall_similarity = total_similarity / total_samples
        else:
            overall_similarity = 0
        
        # 也计算总体相关性（向后兼容）
        all_gen_fees = gen_vehicle_data['passenger']['fees'] + gen_vehicle_data['truck']['fees']
        all_gen_mileages = gen_vehicle_data['passenger']['mileages'] + gen_vehicle_data['truck']['mileages']
        all_real_fees = real_vehicle_data['passenger']['fees'] + real_vehicle_data['truck']['fees']
        all_real_mileages = real_vehicle_data['passenger']['mileages'] + real_vehicle_data['truck']['mileages']
        
        overall_gen_corr = 0
        overall_real_corr = 0
        if len(all_gen_fees) >= 2 and len(all_real_fees) >= 2:
            try:
                overall_gen_corr = np.corrcoef(all_gen_fees, all_gen_mileages)[0, 1]
                overall_real_corr = np.corrcoef(all_real_fees, all_real_mileages)[0, 1]
            except:
                pass
        
        return {
            "score": overall_similarity,  # 使用按车型的加权平均相似度
            "by_vehicle": by_vehicle_results,
            "overall": {
                "generated_correlation": overall_gen_corr,
                "real_correlation": overall_real_corr,
                "difference": abs(overall_gen_corr - overall_real_corr)
            }
        }
    
    def _js_divergence(self, p: Dict, q: Dict) -> float:
        """计算JS散度"""
        all_keys = set(p.keys()) | set(q.keys())
        m = {k: (p.get(k, 0) + q.get(k, 0)) / 2 for k in all_keys}
        
        def kl(a, b):
            return sum(a.get(k, 1e-10) * math.log(a.get(k, 1e-10) / b.get(k, 1e-10)) 
                      for k in all_keys if a.get(k, 0) > 0)
        
        return (kl(p, m) + kl(q, m)) / 2


# ---------------------- 1.6 Self-Instruct Iterative Generation ----------------------

class SelfInstructGenerator:
    """
Self-Instruct迭代生成器
    
    基于Wang等人的SELF-INSTRUCT方法：
    1. 从种子样本出发
    2. 使用模型生成新数据
    3. 启发式过滤低质量数据
    4. 将过滤后的数据加入示例池
    5. 迭代重复过程
    """
    
    def __init__(self, decomposer: 'SampleWiseDecomposer', 
                 sample_filter: 'SampleFilter',
                 demo_manager: 'DemonstrationManager',
                 section_date_mapper: Optional['SectionDateMapper'] = None):
        self.decomposer = decomposer
        self.sample_filter = sample_filter
        self.demo_manager = demo_manager
        self.section_date_mapper = section_date_mapper
        self.iteration_history = []  # 记录每次迭代的结果
    
    def iterative_generate(self, seed_samples: List[Dict], 
                          target_count: int,
                          n_iterations: int = 3,
                          quality_threshold: float = 0.6,
                          verbose: bool = True) -> List[Dict]:
        """
Self-Instruct迭代生成
        
        Args:
            seed_samples: 种子样本（初始示例）
            target_count: 目标生成数量
            n_iterations: 迭代次数
            quality_threshold: 质量阈值
            verbose: 是否输出进度
        
        Returns:
            高质量生成样本列表
        """
        # 初始化：将种子样本加入示例池
        self.demo_manager.real_samples = seed_samples.copy()
        all_generated = seed_samples.copy()
        
        if verbose:
            print(f"\n[Self-Instruct] 迭代生成启动")
            print(f"  种子样本数: {len(seed_samples)}")
            print(f"  目标数量: {target_count}")
            print(f"  迭代次数: {n_iterations}")
        
        for iteration in range(n_iterations):
            if len(all_generated) >= target_count:
                break
            
            if verbose:
                print(f"\n  --- 迭代 {iteration + 1}/{n_iterations} ---")
            
            # Step 1: 生成新样本
            batch_size = min(target_count - len(all_generated), 
                           max(50, target_count // n_iterations))
            
            new_samples = self._generate_batch(batch_size)
            
            if verbose:
                print(f"  生成新样本: {len(new_samples)} 条")
            
            # Step 2: 启发式过滤
            passed, failed = self.sample_filter.filter_samples(new_samples)
            
            if verbose:
                print(f"  过滤后保留: {len(passed)} 条 (过滤掉 {len(failed)} 条)")
            
            # Step 3: 质量检查 - 只保留高质量样本
            high_quality = []
            for sample in passed:
                score, _ = self.sample_filter.evaluate_sample(sample)
                if score >= quality_threshold:
                    high_quality.append(sample)
            
            if verbose:
                print(f"  高质量样本: {len(high_quality)} 条 (>= {quality_threshold})")
            
            # Step 4: 更新示例池（Self-Training）
            if high_quality:
                # 选择最高质量的样本加入示例池
                quality_scores = [(s, self.sample_filter.evaluate_sample(s)[0]) 
                                 for s in high_quality]
                quality_scores.sort(key=lambda x: x[1], reverse=True)
                
                # 只加入top 20%或最多50个
                n_to_add = min(len(high_quality) // 5, 50)
                new_demos = [s for s, _ in quality_scores[:n_to_add]]
                
                self.demo_manager.real_samples.extend(new_demos)
                all_generated.extend(high_quality)
                
                if verbose:
                    print(f"  加入示例池: {len(new_demos)} 条")
                    print(f"  当前总数: {len(all_generated)} 条")
            
            # 记录迭代结果
            self.iteration_history.append({
                "iteration": iteration + 1,
                "generated": len(new_samples),
                "passed_filter": len(passed),
                "high_quality": len(high_quality),
                "total_accumulated": len(all_generated)
            })
        
        if verbose:
            print(f"\n[Self-Instruct] 迭代完成，总共生成 {len(all_generated)} 条高质量数据")
        
        return all_generated[:target_count]
    
    def _generate_batch(self, batch_size: int) -> List[Dict]:
        """生成一批样本"""
        samples = []
        
        for _ in range(batch_size):
            try:
                # 随机生成条件
                condition = GenerationCondition(
                    vehicle_type=random.choice(["货车", "客车", None]),
                    time_period=random.choice(["早高峰", "晚高峰", "平峰", None]),
                    scenario=random.choice(["正常", "超载", None]),
                    base_time=datetime.now()
                )
                
                sample = self.decomposer.decompose_and_generate(condition)
                samples.append(sample)
            except Exception as e:
                continue
        
        return samples
    
    def get_iteration_summary(self) -> Dict:
        """获取迭代过程统计"""
        if not self.iteration_history:
            return {}
        
        return {
            "total_iterations": len(self.iteration_history),
            "total_generated": sum(h["generated"] for h in self.iteration_history),
            "total_high_quality": sum(h["high_quality"] for h in self.iteration_history),
            "avg_pass_rate": sum(h["passed_filter"] / h["generated"] 
                                 for h in self.iteration_history if h["generated"] > 0) / len(self.iteration_history),
            "iterations": self.iteration_history
        }


# ---------------------- 3.2 Indirect Evaluation ----------------------

class IndirectEvaluator:
    """间接评估器 - 通过下游任务评估。
    
    改进：增加更多下游任务评估方法
    """
    
    def evaluate_downstream_task(self, samples: List[Dict], task_name: str = "anomaly_detection") -> Dict:
        """下游任务评估"""
        
        if task_name == "anomaly_detection":
            return self._evaluate_anomaly_detection(samples)
        elif task_name == "fee_prediction":
            return self._evaluate_fee_prediction(samples)
        else:
            return {"error": f"Unknown task: {task_name}"}
    
    def _evaluate_anomaly_detection(self, samples: List[Dict]) -> Dict:
        """异常检测任务评估"""
        # 检查生成数据是否包含可识别的异常模式
        anomaly_samples = [s for s in samples if s.get("pass_state") == "2"]
        normal_samples = [s for s in samples if s.get("pass_state") == "1"]
        
        # 异常样本应该有明确的异常特征
        true_positives = 0
        for s in anomaly_samples:
            axle = s.get("axle_count", "2")
            weight = int(s.get("total_weight", "0"))
            limits = {"2": 18000, "3": 25000, "4": 31000, "5": 43000, "6": 49000}
            if weight > limits.get(axle, 49000):
                true_positives += 1
        
        precision = true_positives / len(anomaly_samples) if anomaly_samples else 0
        
        return {
            "task": "anomaly_detection",
            "total_samples": len(samples),
            "anomaly_samples": len(anomaly_samples),
            "true_positives": true_positives,
            "precision": precision
        }
    
    def _evaluate_fee_prediction(self, samples: List[Dict]) -> Dict:
        """费用预测任务评估"""
        errors = []
        
        for s in samples:
            try:
                mileage = int(s.get("fee_mileage", "0"))
                pay_fee = int(s.get("pay_fee", 0))
                vehicle_type = s.get("vehicle_type", "1")
                
                # 根据车型计算期望费用（云南省标准）
                expected_fee = calculate_expected_fee(mileage, vehicle_type)
                error = abs(pay_fee - expected_fee) / expected_fee if expected_fee > 0 else 0
                errors.append(error)
            except:
                pass
        
        mae = sum(errors) / len(errors) if errors else 1.0
        
        return {
            "task": "fee_prediction",
            "samples_evaluated": len(errors),
            "mean_absolute_error": mae,
            "accuracy": max(0, 1 - mae)
        }
    
    def evaluate_all_tasks(self, samples: List[Dict]) -> Dict:
        """评估所有下游任务
        
        Returns:
            所有任务的评估结果
        """
        results = {
            "anomaly_detection": self._evaluate_anomaly_detection(samples),
            "fee_prediction": self._evaluate_fee_prediction(samples),
            "vehicle_classification": self._evaluate_vehicle_classification(samples),
            "time_consistency": self._evaluate_time_consistency(samples)
        }
        
        # 计算综合得分
        task_scores = []
        for task_name, result in results.items():
            if "accuracy" in result:
                task_scores.append(result["accuracy"])
            elif "precision" in result:
                task_scores.append(result["precision"])
        
        overall_score = sum(task_scores) / len(task_scores) if task_scores else 0
        
        results["overall"] = {
            "score": overall_score,
            "tasks_evaluated": len(task_scores)
        }
        
        return results
    
    def _evaluate_vehicle_classification(self, samples: List[Dict]) -> Dict:
        """车辆分类任务评估 - 检查车辆类型与轴数、重量的一致性"""
        correct = 0
        total = 0
        
        for s in samples:
            try:
                vtype = int(s.get("vehicle_type", "1"))
                axle = s.get("axle_count", "2")
                weight = int(s.get("total_weight", "0"))
                
                total += 1
                
                # 客车（1-4）应为2轴，重量2-5吨
                if 1 <= vtype <= 4:
                    if axle == "2" and 2000 <= weight <= 5000:
                        correct += 1
                # 货车（11-16）轴数与重量应匹配
                elif 11 <= vtype <= 16:
                    limits = {"2": 18000, "3": 25000, "4": 31000, "5": 43000, "6": 49000}
                    expected_limit = limits.get(axle, 49000)
                    # 允许超载20%以内
                    if weight <= expected_limit * 1.2:
                        correct += 1
            except:
                pass
        
        accuracy = correct / total if total > 0 else 0
        
        return {
            "task": "vehicle_classification",
            "total_samples": total,
            "correct_predictions": correct,
            "accuracy": accuracy
        }
    
    def _evaluate_time_consistency(self, samples: List[Dict]) -> Dict:
        """时间一致性评估 - 检查入口时间与交易时间的逻辑"""
        valid = 0
        total = 0
        time_diffs = []
        
        for s in samples:
            try:
                entrance = datetime.fromisoformat(s.get("entrance_time", ""))
                transaction = datetime.fromisoformat(s.get("transaction_time", ""))
                
                total += 1
                
                if entrance < transaction:
                    diff_hours = (transaction - entrance).total_seconds() / 3600
                    time_diffs.append(diff_hours)
                    
                    # 合理范围：0.5-6小时
                    if 0.5 <= diff_hours <= 6:
                        valid += 1
            except:
                pass
        
        accuracy = valid / total if total > 0 else 0
        avg_diff = sum(time_diffs) / len(time_diffs) if time_diffs else 0
        
        return {
            "task": "time_consistency",
            "total_samples": total,
            "valid_samples": valid,
            "accuracy": accuracy,
            "avg_time_diff_hours": avg_diff
        }


# ============================================================================
#                          主生成器
# ============================================================================

class DGMGantryGenerator:
    """
    DGM 门架数据生成器
    整合三阶段框架
    """
    
    def __init__(self, target_distribution: Dict = None, use_advanced_features: bool = True):
        # 学到的统计信息（从真实数据中学习）
        self.learned_stats = {}
        
        # I. Generation 组件
        self.demo_manager = DemonstrationManager(use_heuristic=use_advanced_features)
        self.section_date_mapper = SectionDateMapper()  # 新增：路段-日期映射器
        self.decomposer = SampleWiseDecomposer(
            section_date_mapper=self.section_date_mapper,
            learned_stats=self.learned_stats  # 传递学到的统计信息
        )
        self.scheduler = DatasetWiseScheduler(target_distribution)
        
        # 新增：Self-Instruct迭代生成器
        self.self_instruct = SelfInstructGenerator(
            self.decomposer, 
            SampleFilter(),  # 为 Self-Instruct 创建独立的 filter
            self.demo_manager
        )
        
        # II. Curation 组件
        self.sample_filter = SampleFilter()
        self.reweighter = SampleReweighter()  # 支持SunGen双循环
        self.label_enhancer = LabelEnhancer()
        
        # III. Evaluation 组件
        self.direct_evaluator = DirectEvaluator()
        self.benchmark_evaluator = BenchmarkEvaluator()  # 新增：与真实数据对比
        self.indirect_evaluator = IndirectEvaluator()  # 支持多任务评估
        
        # 连接Benchmark Evaluator到Direct Evaluator（用于Faithfulness评估）
        self.direct_evaluator.set_benchmark_evaluator(self.benchmark_evaluator)
        
        # 确保target_distribution始终是字典
        if target_distribution is None:
            self.target_distribution = {
                "vehicle": {"货车": 0.4, "客车": 0.6},
                "time": {"早高峰": 0.25, "晚高峰": 0.25, "平峰": 0.40, "深夜": 0.10},
                "scenario": {"正常": 0.90, "超载": 0.06, "异常": 0.04}
            }
        else:
            self.target_distribution = target_distribution
        
        self.use_advanced_features = use_advanced_features
    
    def load_real_samples(self, source: str = None, 
                         limit: int = 100,
                         evaluation_limit: int = None,
                         section_id: str = None,
                         start_date: str = None,
                         end_date: str = None,
                         verbose: bool = True) -> None:
        """加载真实样本数据（支持JSON文件或数据库）
        
        重要改进：分离训练数据和评估数据
        - 训练数据（limit）：用于学习统计特征（可以较小，如300条）
        - 评估数据（evaluation_limit）：用于Benchmark评估（应该更大或全部数据）
        
        用于：
        1. 作为生成示例（使用训练数据）
        2. 学习路段-日期映射关系（使用训练数据）
        3. 学习真实数据的分布特征（使用训练数据）
        4. 作为Benchmark评估的基准数据（使用评估数据）
        
        Args:
            source: 数据源路径
                   - 如果以.json结尾，从JSON文件加载
                   - 如果是"database"或None，从数据库加载
            limit: 用于训练的样本数（学习统计特征）
            evaluation_limit: 用于评估的样本数（Benchmark对比）
                            - 如果为None，则使用与limit相同的数据
                            - 建议设置为更大值（如1000+）或-1表示全部数据
            section_id: 指定路段ID（仅数据库模式）
            start_date: 开始日期（仅数据库模式）
            end_date: 结束日期（仅数据库模式）
            verbose: 是否输出详细信息
        """
        samples = []
        
        # 判断数据源类型
        if source and source.endswith('.json'):
            # 方式1：从JSON文件加载
            if verbose:
                print(f"\n[加载真实数据] 从文件: {source}")
            
            try:
                with open(source, 'r', encoding='utf-8') as f:
                    samples = json.load(f)
                
                if not isinstance(samples, list) or not samples:
                    if verbose:
                        print("  [警告] 样本文件格式错误或为空")
                    return
                    
                if verbose:
                    print(f"  [OK] 从文件加载 {len(samples)} 条数据")
                    
            except Exception as e:
                if verbose:
                    print(f"  [错误] 文件加载失败: {e}")
                return
        else:
            # 方式2：从数据库加载
            if verbose:
                print(f"\n[加载真实数据] 从数据库")
            
            samples = self._load_from_database(
                limit=limit,
                section_id=section_id,
                start_date=start_date,
                end_date=end_date,
                verbose=verbose
            )
            
            if not samples:
                if verbose:
                    print("  [错误] 数据库加载失败")
                return
        
        # 统一处理加载的数据
        if samples:
            # 1. 作为生成示例
            self.demo_manager.samples = samples[:10]
            
            # 2. 学习路段-日期映射
            self.section_date_mapper.learn_from_samples(samples, verbose=verbose)
            
            # 3. 学习真实数据分布
            learned_dist = self._learn_distribution_from_samples(samples)
            if learned_dist and verbose:
                print(f"  [学习] 从真实数据中学到的分布:")
                if "vehicle" in learned_dist:
                    print(f"    - 车型分布: {learned_dist['vehicle']}")
                if "time" in learned_dist:
                    print(f"    - 时段分布: {learned_dist['time']}")
                if "statistics" in learned_dist:
                    stats = learned_dist['statistics']
                    if "pay_fee" in stats:
                        fee = stats['pay_fee']
                        print(f"    - 费用范围: {fee['min']}~{fee['max']}分 (均值:{fee['mean']}分)")
                    if "fee_mileage" in stats:
                        mile = stats['fee_mileage']
                        print(f"    - 里程范围: {mile['min']}~{mile['max']}米 (均值:{mile['mean']}米)")
                    if "correlation" in stats:
                        corr = stats['correlation']
                        print(f"    - 总体相关系数: {corr:.4f}")
                    
                    # 保存统计信息到learned_stats（总体，向后兼容）
                    self.learned_stats['fee'] = stats['pay_fee']
                    self.learned_stats['mileage'] = stats['fee_mileage']
                    if "correlation" in stats:
                        self.learned_stats['correlation'] = stats['correlation']
                
                # 保存按车型的统计信息（关键改进！）
                if "statistics_by_vehicle" in learned_dist:
                    stats_by_veh = learned_dist['statistics_by_vehicle']
                    print(f"    - 按车型统计:")
                    
                    for vtype, veh_stats in stats_by_veh.items():
                        vtype_name = "客车" if vtype == "passenger" else "货车"
                        print(f"      [{vtype_name}] 样本数:{veh_stats['sample_count']}, "
                              f"相关系数:{veh_stats['correlation']:.4f}")
                    
                    # 保存到learned_stats
                    self.learned_stats['by_vehicle'] = stats_by_veh
                    
                # 更新目标分布
                self.target_distribution.update(learned_dist)
            
            # 4. 加载到Benchmark评估器（关键改进：支持独立的评估数据集）
            evaluation_samples = samples  # 默认使用训练样本
            
            # 如果指定了不同的evaluation_limit，加载额外的评估数据
            if evaluation_limit is not None and evaluation_limit != limit:
                if verbose:
                    if evaluation_limit == -1:
                        print(f"\n  [评估数据] 加载全部数据用于Benchmark评估...")
                    else:
                        print(f"\n  [评估数据] 加载 {evaluation_limit} 条数据用于Benchmark评估...")
                
                # 从数据库加载评估数据
                if not (source and source.endswith('.json')):
                    evaluation_samples = self._load_from_database(
                        limit=evaluation_limit if evaluation_limit != -1 else 100000,  # -1表示尽可能多
                        section_id=section_id,
                        start_date=start_date,
                        end_date=end_date,
                        verbose=False  # 不重复打印详细信息
                    )
                    
                    if evaluation_samples and verbose:
                        print(f"  [OK] 评估数据集: {len(evaluation_samples)} 条")
                else:
                    # JSON文件模式：使用全部数据或截取
                    if evaluation_limit == -1:
                        evaluation_samples = samples  # 使用全部
                    else:
                        evaluation_samples = samples[:evaluation_limit]
                    
                    if verbose:
                        print(f"  [OK] 评估数据集: {len(evaluation_samples)} 条（从文件）")
            
            # 加载评估数据到Benchmark评估器
            self.benchmark_evaluator.load_real_samples(evaluation_samples)
            
            if verbose:
                print(f"  [完成] 真实数据已加载并应用到:")
                print(f"    - 生成示例: {len(self.demo_manager.samples)} 条")
                print(f"    - 路段映射: {len(self.section_date_mapper.section_dates)} 个路段")
                print(f"    - 训练数据: {len(samples)} 条（用于学习统计特征）")
                print(f"    - 评估数据: {len(evaluation_samples)} 条（用于Benchmark对比）")
                print(f"    - 目标分布: 已根据真实数据更新")
                
                if evaluation_limit and evaluation_limit != limit:
                    print(f"\n  [数据分离] 训练/评估分离模式")
                    print(f"    训练集大小: {len(samples)} 条")
                    print(f"    评估集大小: {len(evaluation_samples)} 条")
                    print(f"    → 更准确的评估结果！")
    
    def _load_from_database(self, limit: int = 100, 
                           section_id: str = None,
                           start_date: str = None,
                           end_date: str = None,
                           verbose: bool = True) -> List[Dict]:
        """从数据库加载真实数据"""
        try:
            import pymysql
            import config
            
            # 数据库配置
            db_config = {
                'host': config.MYSQL_CONFIG['host'],
                'port': config.MYSQL_CONFIG['port'],
                'user': config.MYSQL_CONFIG['user'],
                'password': config.MYSQL_CONFIG['password'],
                'database': config.MYSQL_CONFIG['database'],
                'charset': config.MYSQL_CONFIG['charset']
            }
            
            if verbose:
                print(f"  数据库: {db_config['database']}")
                print(f"  限制: {limit} 条")
                if section_id:
                    print(f"  路段: {section_id}")
                if start_date or end_date:
                    print(f"  时间范围: {start_date} ~ {end_date}")
            
            # 构建SQL
            sql = """
            SELECT 
                gantry_transaction_id, pass_id, gantry_id, section_id, section_name,
                transaction_time, entrance_time, vehicle_type, axle_count, total_weight,
                vehicle_sign, gantry_type, media_type, transaction_type, pass_state,
                cpu_card_type, pay_fee, discount_fee, fee_mileage
            FROM gantrytransaction
            WHERE 1=1
            """
            
            params = []
            if section_id:
                sql += " AND section_id = %s"
                params.append(section_id)
            if start_date:
                sql += " AND transaction_time >= %s"
                params.append(start_date)
            if end_date:
                sql += " AND transaction_time <= %s"
                params.append(end_date)
            
            sql += " ORDER BY RAND() LIMIT %s"
            params.append(limit)
            
            # 查询
            connection = pymysql.connect(**db_config)
            try:
                if verbose:
                    print(f"  [连接] 数据库连接成功")
                
                with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                    cursor.execute(sql, params)
                    results = cursor.fetchall()
                    
                    if verbose:
                        print(f"  [查询] 获取到 {len(results)} 条数据")
                    
                    # 转换datetime为字符串
                    samples = []
                    for row in results:
                        sample = {}
                        for key, value in row.items():
                            if hasattr(value, 'isoformat'):
                                sample[key] = value.isoformat()
                            else:
                                sample[key] = value
                        samples.append(sample)
                    
                    return samples
            finally:
                connection.close()
                
        except ImportError:
            if verbose:
                print("  [警告] pymysql未安装，无法从数据库加载")
            return []
        except Exception as e:
            if verbose:
                print(f"  [错误] 数据库查询失败: {e}")
            return []
    
    def _learn_distribution_from_samples(self, samples: List[Dict]) -> Dict:
        """从真实样本中学习分布"""
        from collections import Counter
        from datetime import datetime
        import numpy as np
        
        dist = {}
        
        # 1. 学习车型分布
        vehicle_types = []
        for s in samples:
            vtype = s.get("vehicle_type", "")
            if vtype:
                vtype_str = str(vtype)
                if vtype_str in ["0", "1", "2", "3", "4", "5"]:
                    vehicle_types.append("客车")
                else:
                    vehicle_types.append("货车")
        
        if vehicle_types:
            counter = Counter(vehicle_types)
            total = len(vehicle_types)
            dist["vehicle"] = {k: round(v/total, 2) for k, v in counter.items()}
        
        # 2. 学习时段分布
        time_periods = []
        for s in samples:
            time_str = s.get("transaction_time", "")
            if time_str:
                try:
                    if isinstance(time_str, str):
                        dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    else:
                        dt = time_str
                    
                    hour = dt.hour
                    if 7 <= hour < 9:
                        time_periods.append("早高峰")
                    elif 17 <= hour < 19:
                        time_periods.append("晚高峰")
                    elif 0 <= hour < 6:
                        time_periods.append("深夜")
                    else:
                        time_periods.append("平峰")
                except:
                    pass
        
        if time_periods:
            counter = Counter(time_periods)
            total = len(time_periods)
            dist["time"] = {k: round(v/total, 2) for k, v in counter.items()}
        
        # 3. 按车型学习费用和里程统计（关键改进！）
        # 分车型收集数据
        vehicle_data = {
            'passenger': {'fees': [], 'mileages': []},  # 客车
            'truck': {'fees': [], 'mileages': []}       # 货车
        }
        
        for s in samples:
            try:
                fee = int(s.get("pay_fee", 0))
                mileage_val = s.get("fee_mileage")
                if isinstance(mileage_val, str):
                    mileage = int(float(mileage_val))
                else:
                    mileage = int(mileage_val) if mileage_val else 0
                
                if fee > 0 and mileage > 0:
                    # 判断车型：1-4是客车，11-16和21-26是货车
                    vtype = str(s.get("vehicle_type", "1"))
                    if vtype in ["1", "2", "3", "4", "5"]:
                        vehicle_data['passenger']['fees'].append(fee)
                        vehicle_data['passenger']['mileages'].append(mileage)
                    else:
                        vehicle_data['truck']['fees'].append(fee)
                        vehicle_data['truck']['mileages'].append(mileage)
            except:
                pass
        
        # 分别计算每种车型的统计信息
        dist["statistics_by_vehicle"] = {}
        
        for vtype, data in vehicle_data.items():
            fees = data['fees']
            mileages = data['mileages']
            
            if len(fees) >= 2 and len(mileages) >= 2:
                correlation = 0
                try:
                    correlation = np.corrcoef(fees, mileages)[0, 1]
                except:
                    correlation = 0
                
                dist["statistics_by_vehicle"][vtype] = {
                    "pay_fee": {
                        "mean": int(np.mean(fees)),
                        "std": int(np.std(fees)),
                        "min": int(np.min(fees)),
                        "max": int(np.max(fees))
                    },
                    "fee_mileage": {
                        "mean": int(np.mean(mileages)),
                        "std": int(np.std(mileages)),
                        "min": int(np.min(mileages)),
                        "max": int(np.max(mileages))
                    },
                    "correlation": correlation,
                    "sample_count": len(fees)
                }
        
        # 保留总体统计（向后兼容）
        all_fees = vehicle_data['passenger']['fees'] + vehicle_data['truck']['fees']
        all_mileages = vehicle_data['passenger']['mileages'] + vehicle_data['truck']['mileages']
        
        if all_fees and all_mileages and len(all_fees) == len(all_mileages):
            overall_corr = 0
            if len(all_fees) >= 2:
                try:
                    overall_corr = np.corrcoef(all_fees, all_mileages)[0, 1]
                except:
                    overall_corr = 0
            
            dist["statistics"] = {
                "pay_fee": {
                    "mean": int(np.mean(all_fees)),
                    "std": int(np.std(all_fees)),
                    "min": int(np.min(all_fees)),
                    "max": int(np.max(all_fees))
                },
                "fee_mileage": {
                    "mean": int(np.mean(all_mileages)),
                    "std": int(np.std(all_mileages)),
                    "min": int(np.min(all_mileages)),
                    "max": int(np.max(all_mileages))
                },
                "correlation": overall_corr
            }
        
        return dist
    
    def generate(self, count: int, verbose: bool = True) -> Dict:
        """
        执行完整的三阶段生成流程
        
        Returns:
            {
                "samples": List[Dict],           # 最终生成的样本
                "evaluation": Dict,              # 评估结果
                "statistics": Dict               # 生成统计
            }
        """
        if verbose:
            print("=" * 60)
            print("DGM 门架数据生成器")
            print("=" * 60)
        
        # ==================== I. GENERATION ====================
        if verbose:
            print("\n[阶段 I] Generation - 数据生成")
            print("-" * 40)
        
        raw_samples = []
        attempts = 0
        max_attempts = count * 2
        
        while len(raw_samples) < count and attempts < max_attempts:
            attempts += 1
            
            # 1. 获取生成条件 (Dataset-Wise Scheduling)
            condition = self.scheduler.get_next_condition()
            
            # 2. 获取示例 (In-Context Demonstrations)
            # 使用多候选验证如果启用了高级功能
            demos = self.demo_manager.select_demonstrations(
                condition, 
                use_multi_candidate=self.use_advanced_features
            )
            
            # 3. 分步生成样本 (Sample-Wise Decomposition)
            try:
                sample = self.decomposer.decompose_and_generate(condition)
                raw_samples.append(sample)
                self.scheduler.update_stats(sample)
                
                if verbose and len(raw_samples) % 10 == 0:
                    print(f"  [生成进度] {len(raw_samples)}/{count}")
            except Exception as e:
                if verbose:
                    print(f"  [警告] 生成失败: {e}")
        
        if verbose:
            print(f"  [完成] 生成 {len(raw_samples)} 条原始数据")
        
        # ==================== II. CURATION ====================
        if verbose:
            print("\n[阶段 II] Curation - 数据策展")
            print("-" * 40)
        
        # 1. Sample Filtering
        passed_samples, failed_samples = self.sample_filter.filter_samples(raw_samples)
        if verbose:
            print(f"  [过滤] 通过: {len(passed_samples)}, 失败: {len(failed_samples)}")
        
        # 2. Label Enhancement
        enhanced_samples = [self.label_enhancer.enhance_sample(s) for s in passed_samples]
        if verbose:
            print(f"  [增强] 完成标签增强")
        
        # 3. 对失败样本进行增强后重新评估
        recovered = 0
        for item in failed_samples:
            enhanced = self.label_enhancer.enhance_sample(item["sample"])
            score, _ = self.sample_filter.evaluate_sample(enhanced)
            if score >= 0.6:
                enhanced_samples.append(enhanced)
                recovered += 1
        
        if verbose:
            print(f"  [恢复] 从失败样本中恢复 {recovered} 条")
        
        # 4. Re-Weighting (SunGen双循环) - 如果启用了高级功能
        sample_weights = None
        if self.use_advanced_features and len(enhanced_samples) > 20:
            # 使用部分数据作为验证集
            split_point = int(len(enhanced_samples) * 0.8)
            train_samples = enhanced_samples[:split_point]
            val_samples = enhanced_samples[split_point:]
            
            sample_weights = self.reweighter.calculate_weights(
                train_samples,
                self.target_distribution,
                validation_samples=val_samples
            )
            
            if verbose:
                print(f"  [权重调整] 使用SunGen方法计算权重")
        
        # ==================== III. EVALUATION ====================
        if verbose:
            print("\n[阶段 III] Evaluation - 数据评估")
            print("-" * 40)
        
        # 执行评估（符合图2分类）
        direct_eval = self.direct_evaluator.evaluate(enhanced_samples, self.target_distribution)
        indirect_eval = self.indirect_evaluator.evaluate_all_tasks(enhanced_samples)
        
        if verbose:
            print(f"  直接评估:")
            print(f"    - 忠实度: {direct_eval['faithfulness']['score']:.2%}")
            if 'benchmark_evaluation' in direct_eval['faithfulness']:
                bench = direct_eval['faithfulness']['benchmark_evaluation']
                print(f"      (包含Benchmark: {bench['overall_similarity']:.2%})")
            print(f"    - 多样性: {direct_eval['diversity']['score']:.2%}")
            print(f"    - 综合得分: {direct_eval['overall_score']:.2%}")
            print(f"  间接评估 - 综合得分: {indirect_eval['overall']['score']:.2%}")
        
        # 符合图2分类结构
        evaluation_result = {
            "direct": direct_eval,      # 包含 faithfulness (含benchmark) 和 diversity
            "indirect": {
                "open_evaluation": indirect_eval,        # Open评估：下游任务
                "benchmark_evaluation": None             # 任务性能Benchmark（待实现）
            }
        }
        
        # 应用Re-Weighting: 根据权重排序和标记样本
        weighted_samples = enhanced_samples
        quality_tiers = None
        
        if sample_weights is not None:
            # 为每个样本附加权重信息
            for i, sample in enumerate(enhanced_samples):
                sample["_quality_weight"] = sample_weights[i] if i < len(sample_weights) else 1.0
            
            # 按权重排序（可选，方便用户使用高质量样本）
            weighted_samples = sorted(enhanced_samples, key=lambda x: x.get("_quality_weight", 1.0), reverse=True)
            
            # 质量分层：高/中/低
            high_threshold = 1.2  # 高于平均权重20%
            low_threshold = 0.8   # 低于平均权重20%
            
            quality_tiers = {
                "high_quality": [s for s in weighted_samples if s.get("_quality_weight", 1.0) >= high_threshold],
                "medium_quality": [s for s in weighted_samples if low_threshold <= s.get("_quality_weight", 1.0) < high_threshold],
                "low_quality": [s for s in weighted_samples if s.get("_quality_weight", 1.0) < low_threshold]
            }
            
            if verbose:
                print(f"\n  [质量分层]")
                print(f"    - 高质量样本: {len(quality_tiers['high_quality'])} 条")
                print(f"    - 中等质量样本: {len(quality_tiers['medium_quality'])} 条")
                print(f"    - 低质量样本: {len(quality_tiers['low_quality'])} 条")
        
        return {
            "samples": enhanced_samples,              # 原始顺序的样本
            "weighted_samples": weighted_samples,     # 按权重排序的样本（推荐使用）
            "quality_tiers": quality_tiers,           # 质量分层
            "evaluation": evaluation_result,
            "statistics": {
                "raw_count": len(raw_samples),
                "passed_count": len(passed_samples),
                "failed_count": len(failed_samples),
                "recovered_count": recovered,
                "final_count": len(enhanced_samples),
                "sample_weights": sample_weights,
                "weighting_enabled": sample_weights is not None
            }
        }
    
    def generate_with_self_instruct(self, seed_samples: List[Dict], 
                                   target_count: int,
                                   n_iterations: int = 3,
                                   verbose: bool = True) -> Dict:
        """使用Self-Instruct迭代生成方法生成数据
        
        Args:
            seed_samples: 种子样本（初始示例）
            target_count: 目标生成数量
            n_iterations: 迭代次数
            verbose: 是否输出进度
        
        Returns:
            {
                "samples": List[Dict],
                "evaluation": Dict,
                "self_instruct_summary": Dict
            }
        """
        if verbose:
            print("=" * 60)
            print("DGM 门架数据生成器 - Self-Instruct模式")
            print("=" * 60)
        
        # 使用Self-Instruct迭代生成
        generated_samples = self.self_instruct.iterative_generate(
            seed_samples=seed_samples,
            target_count=target_count,
            n_iterations=n_iterations,
            quality_threshold=0.6,
            verbose=verbose
        )
        
        # 执行标签增强
        if verbose:
            print("\n[标签增强] 对生成的数据进行增强...")
        
        enhanced_samples = [self.label_enhancer.enhance_sample(s) for s in generated_samples]
        
        # 评估
        if verbose:
            print("\n[评估] 评估生成的数据质量...")
        
        # 执行评估（符合图2分类）
        direct_eval = self.direct_evaluator.evaluate(enhanced_samples, self.target_distribution)
        indirect_eval = self.indirect_evaluator.evaluate_all_tasks(enhanced_samples)
        
        if verbose:
            print(f"  直接评估:")
            print(f"    - 忠实度: {direct_eval['faithfulness']['score']:.2%}")
            if 'benchmark_evaluation' in direct_eval['faithfulness']:
                bench = direct_eval['faithfulness']['benchmark_evaluation']
                print(f"      (包含Benchmark: {bench['overall_similarity']:.2%})")
            print(f"    - 多样性: {direct_eval['diversity']['score']:.2%}")
            print(f"    - 综合得分: {direct_eval['overall_score']:.2%}")
            print(f"  间接评估 - 综合得分: {indirect_eval['overall']['score']:.2%}")
        
        # 符合图2分类结构
        evaluation_result = {
            "direct": direct_eval,      # 包含 faithfulness (含benchmark) 和 diversity
            "indirect": {
                "open_evaluation": indirect_eval,        # Open评估：下游任务
                "benchmark_evaluation": None             # 任务性能Benchmark（待实现）
            }
        }
        
        return {
            "samples": enhanced_samples,
            "evaluation": evaluation_result,
            "self_instruct_summary": self.self_instruct.get_iteration_summary()
        }
    
    def _print_evaluation_report(self, direct_eval: Dict, indirect_eval: Dict, benchmark_eval: Dict = None):
        """打印评估报告（完全符合图2分类）"""
        print("\n" + "=" * 70)
        print("评估报告（符合图2：Benchmark在Faithfulness下）")
        print("=" * 70)
        
        # 综合得分
        print(f"\n【综合指标】")
        print(f"  直接评估得分: {direct_eval['overall_score']:.2%}")
        
        # ========== I. 直接评估 (Direct Evaluation) ==========
        print("\n" + "=" * 70)
        print("[I. 直接评估 Direct Evaluation]")
        print("=" * 70)
        
        # I-A. Faithfulness (包含Constraint Check和Benchmark)
        faith = direct_eval.get("faithfulness", {})
        print(f"\n1. Data Faithfulness (忠实度): {faith.get('score', 0):.2%}")
        
        # Constraint Check
        if 'constraint_check' in faith:
            const = faith['constraint_check']
            print(f"\n   [约束检查 Constraint Check]")
            print(f"   - 约束遵守率: {const.get('score', 0):.2%} ({const.get('valid_count', 0)}/{const.get('total_count', 0)} 合格)")
            if const.get('section_date_errors', 0) > 0:
                print(f"   - 路段日期映射错误: {const.get('section_date_errors', 0)} 个")
            if const.get('common_issues'):
                print(f"   - 常见问题: {const.get('common_issues')}")
        
        # Benchmark Evaluation (在Faithfulness下)
        if 'benchmark_evaluation' in faith:
            bench = faith['benchmark_evaluation']
            print(f"\n   [Benchmark评估 - 与真实数据对比]")
            print(f"   - 整体相似度: {bench.get('overall_similarity', 0):.2%}")
            print(f"     * 分布相似度: {bench.get('distribution_similarity', {}).get('score', 0):.2%}")
            print(f"     * 统计特征: {bench.get('statistical_similarity', {}).get('score', 0):.2%}")
            print(f"     * 时间模式: {bench.get('temporal_similarity', {}).get('score', 0):.2%}")
            print(f"     * 相关性: {bench.get('correlation_similarity', {}).get('score', 0):.2%}")
        
        # I-B. Diversity
        div = direct_eval.get("diversity", {})
        print(f"\n2. Data Diversity (多样性): {div.get('score', 0):.2%}")
        if div.get("unique_values"):
            print(f"   - 唯一车型数: {div['unique_values'].get('vehicle_type', 0)}")
            print(f"   - 唯一门架ID数: {div['unique_values'].get('gantry_id', 0)}")
            print(f"   - 唯一路段ID数: {div['unique_values'].get('section_id', 0)}")
            print(f"   - 唯一时段数: {div['unique_values'].get('time_period', 0)}")
        print(f"   - 样本独特性: {div.get('uniqueness', 0):.2%}")
        if div.get('coverage') is not None:
            print(f"   - 分布覆盖度: {div.get('coverage', 0):.2%}")
        
        # ========== II. 间接评估 (Indirect Evaluation) ==========
        print("\n" + "=" * 70)
        print("[II. 间接评估 Indirect Evaluation]")
        print("=" * 70)
        
        # Open评估（下游任务）
        print(f"\nOpen Evaluation - 下游任务表现:")
        anomaly = indirect_eval.get("anomaly_detection", {})
        print(f"  - 异常检测任务: 精确率 {anomaly.get('precision', 0):.2%}")
        
        fee = indirect_eval.get("fee_prediction", {})
        print(f"  - 费用预测任务: 准确率 {fee.get('accuracy', 0):.2%}")
        
        # 说明：任务性能Benchmark（待实现）
        print(f"\n  [注] Benchmark Evaluation (任务性能对比) 待实现")
        print(f"       用于对比用生成数据vs真实数据训练模型的性能差异")
        
        print("\n" + "=" * 70)


# ============================================================================
#                          命令行接口
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='DGM 门架数据生成器')
    parser.add_argument('--count', type=int, default=20, help='生成数量')
    parser.add_argument('--output', type=str, default=None, help='输出文件路径')
    parser.add_argument('--truck-ratio', type=float, default=0.6, help='货车比例')
    parser.add_argument('--seed-data', type=str, default=None, help='真实样本数据文件路径(JSON)')
    parser.add_argument('--quiet', action='store_true', help='静默模式')
    
    args = parser.parse_args()
    
    # 配置目标分布
    target_dist = {
        "vehicle": {"货车": args.truck_ratio, "客车": 1 - args.truck_ratio},
        "time": {"早高峰": 0.25, "晚高峰": 0.25, "平峰": 0.40, "深夜": 0.10},
        "scenario": {"正常": 0.90, "超载": 0.06, "异常": 0.04}
    }
    
    # 创建生成器并执行
    generator = DGMGantryGenerator(target_distribution=target_dist)
    
    # 加载真实样本（训练/评估数据分离）
    if args.seed_data:
        # 从JSON文件加载
        generator.load_real_samples(args.seed_data, verbose=not args.quiet)
    else:
        # 从数据库加载（训练集300条 + 评估集1000条）
        try:
            generator.load_real_samples(
                limit=300,              # 训练数据：学习统计特征
                evaluation_limit=1000,  # 评估数据：Benchmark对比
                verbose=not args.quiet
            )
        except Exception as e:
            if not args.quiet:
                print(f"\n[警告] 无法从数据库加载真实数据: {e}")
                print("[提示] 将跳过Benchmark评估")
        
    result = generator.generate(count=args.count, verbose=not args.quiet)
    
    # 打印评估结果
    if not args.quiet and "evaluation" in result:
        print("\n" + "=" * 80)
        print("评估结果")
        print("=" * 80)
        
        evaluation = result["evaluation"]
        
        # Direct Evaluation
        if "direct" in evaluation:
            direct = evaluation["direct"]
            print(f"\n[Direct Evaluation] 总分: {direct.get('overall_score', 0):.2%}")
            
            if "faithfulness" in direct:
                faith = direct["faithfulness"]
                print(f"  - Faithfulness: {faith.get('score', 0):.2%}")
                
                if "constraint_check" in faith:
                    cc = faith["constraint_check"]
                    print(f"    * Constraint Check: {cc.get('score', 0):.2%}")
                
                if "benchmark_evaluation" in faith:
                    bench = faith["benchmark_evaluation"]
                    print(f"    * Benchmark: {bench.get('overall_similarity', 0):.2%}")
                    print(f"      - 分布相似度: {bench.get('distribution_similarity', {}).get('score', 0):.2%}")
                    print(f"      - 统计特征相似度: {bench.get('statistical_similarity', {}).get('score', 0):.2%}")
                    print(f"      - 时间模式相似度: {bench.get('temporal_similarity', {}).get('score', 0):.2%}")
                    print(f"      - 相关性相似度: {bench.get('correlation_similarity', {}).get('score', 0):.2%}")
            
            if "diversity" in direct:
                div = direct["diversity"]
                print(f"  - Diversity: {div.get('score', 0):.2%}")
        
        # Indirect Evaluation
        if "indirect" in evaluation:
            indirect = evaluation["indirect"]
            # 正确获取间接评估得分
            open_eval = indirect.get('open_evaluation', {})
            overall_score = open_eval.get('overall', {}).get('score', 0)
            print(f"\n[Indirect Evaluation] 总分: {overall_score:.2%}")
            
            # 显示各个下游任务的得分
            if open_eval:
                print(f"  下游任务评估:")
                for task_name, task_result in open_eval.items():
                    if task_name == 'overall':
                        continue
                    if isinstance(task_result, dict):
                        if 'accuracy' in task_result:
                            print(f"    - {task_name}: {task_result['accuracy']:.2%}")
                        elif 'precision' in task_result:
                            print(f"    - {task_name}: {task_result['precision']:.2%}")
        
        print("\n" + "=" * 80)
    
    # 保存结果（优先使用加权样本）
    samples_to_save = result.get("weighted_samples", result["samples"])
    
    # 移除内部权重字段（可选）
    clean_samples = []
    for s in samples_to_save:
        clean_s = {k: v for k, v in s.items() if not k.startswith('_')}
        clean_samples.append(clean_s)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(clean_samples, f, ensure_ascii=False, indent=2)
        
        # 显示保存信息
        stats = result.get("statistics", {})
        if stats.get("weighting_enabled"):
            print(f"\n[保存] 已保存 {len(clean_samples)} 条数据到 {args.output}")
            print(f"       数据已按质量权重排序（高质量样本在前）")
        else:
            print(f"\n[保存] 数据已保存到 {args.output}")
        
        # 如果有质量分层信息，显示统计
        if result.get("quality_tiers"):
            tiers = result["quality_tiers"]
            print(f"\n[质量分布]")
            print(f"  [高] 高质量: {len(tiers['high_quality'])} 条 ({len(tiers['high_quality'])/len(clean_samples)*100:.1f}%)")
            print(f"  [中] 中等质量: {len(tiers['medium_quality'])} 条 ({len(tiers['medium_quality'])/len(clean_samples)*100:.1f}%)")
            print(f"  [低] 低质量: {len(tiers['low_quality'])} 条 ({len(tiers['low_quality'])/len(clean_samples)*100:.1f}%)")
    else:
        print("\n[样例数据]（前2条，按质量排序）")
        for s in clean_samples[:2]:
            # 显示权重信息（如果有）
            original = [x for x in samples_to_save if x.get("gantry_transaction_id") == s.get("gantry_transaction_id")][0]
            weight = original.get("_quality_weight")
            if weight:
                print(f"\n### 样本质量权重: {weight:.3f}")
            print(json.dumps(s, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    # 主入口：直接运行主函数
    main()
