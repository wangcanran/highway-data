"""业务常量定义 - 消除魔法数字

修复问题：
1. 硬编码的魔法数字
2. 配置散落在代码各处
3. 缺少注释说明
"""
from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class AxleWeightLimits:
    """轴数限重标准（国家标准GB1589-2016）
    
    单位：千克（kg）
    """
    AXLE_2: int = 18_000   # 2轴限重18吨
    AXLE_3: int = 25_000   # 3轴限重25吨
    AXLE_4: int = 31_000   # 4轴限重31吨
    AXLE_5: int = 43_000   # 5轴限重43吨
    AXLE_6: int = 49_000   # 6轴限重49吨
    
    def get_limit(self, axle_count: str) -> int:
        """获取指定轴数的限重
        
        Args:
            axle_count: 轴数（字符串格式："2", "3"等）
            
        Returns:
            限重值（kg）
        """
        limits = {
            "2": self.AXLE_2,
            "3": self.AXLE_3,
            "4": self.AXLE_4,
            "5": self.AXLE_5,
            "6": self.AXLE_6,
        }
        return limits.get(axle_count, self.AXLE_6)
    
    def to_dict(self) -> Dict[str, int]:
        """转换为字典格式（兼容旧代码）"""
        return {
            "2": self.AXLE_2,
            "3": self.AXLE_3,
            "4": self.AXLE_4,
            "5": self.AXLE_5,
            "6": self.AXLE_6,
        }


@dataclass(frozen=True)
class ScoreWeights:
    """评分权重配置"""
    # 样本质量评分权重
    TIME_CONSISTENCY: float = 0.30      # 时间一致性权重
    FEE_LOGIC: float = 0.25             # 费用逻辑权重
    VEHICLE_LOGIC: float = 0.20         # 车辆逻辑权重
    FIELD_COMPLETENESS: float = 0.25    # 字段完整性权重
    
    # 直接评估权重
    FAITHFULNESS: float = 0.60          # 忠实度权重
    DIVERSITY: float = 0.40             # 多样性权重
    
    # Faithfulness子权重
    CONSTRAINT_CHECK: float = 0.50      # 约束检查权重
    BENCHMARK: float = 0.50             # 基准评估权重


@dataclass(frozen=True)
class ScorePenalties:
    """评分惩罚系数"""
    # 时间逻辑错误惩罚
    TIME_ORDER_ERROR: float = 0.3       # 时间顺序错误
    TIME_TOO_LONG: float = 0.8          # 时间过长
    TIME_FORMAT_ERROR: float = 0.5      # 时间格式错误
    
    # 费用逻辑错误惩罚
    DISCOUNT_EXCEED: float = 0.4        # 优惠费超过应付费
    FEE_NEGATIVE: float = 0.0           # 费用为负数（完全失败）
    FEE_FORMAT_ERROR: float = 0.6       # 费用格式错误
    
    # 车辆类型惩罚
    PASSENGER_PENALTY: float = 0.6      # 客车类型不匹配
    TRUCK_PENALTY: float = 0.8          # 货车类型不匹配
    VEHICLE_ERROR: float = 0.7          # 车辆逻辑错误


@dataclass(frozen=True)
class TimePeriods:
    """时间段定义"""
    MORNING_RUSH_START: int = 7         # 早高峰开始（小时）
    MORNING_RUSH_END: int = 9           # 早高峰结束
    
    EVENING_RUSH_START: int = 17        # 晚高峰开始
    EVENING_RUSH_END: int = 19          # 晚高峰结束
    
    NIGHT_START: int = 23               # 深夜开始
    NIGHT_END: int = 5                  # 深夜结束
    
    def get_period(self, hour: int) -> str:
        """根据小时数获取时间段
        
        Args:
            hour: 小时数（0-23）
            
        Returns:
            时间段："早高峰" | "晚高峰" | "深夜" | "平峰"
        """
        if self.MORNING_RUSH_START <= hour < self.MORNING_RUSH_END:
            return "早高峰"
        elif self.EVENING_RUSH_START <= hour < self.EVENING_RUSH_END:
            return "晚高峰"
        elif hour >= self.NIGHT_START or hour < self.NIGHT_END:
            return "深夜"
        else:
            return "平峰"


@dataclass(frozen=True)
class VehicleWeightRanges:
    """车辆重量范围（kg）"""
    # 客车重量范围
    PASSENGER_MIN: int = 2_000          # 客车最小重量2吨
    PASSENGER_MAX: int = 5_000          # 客车最大重量5吨
    
    # 货车重量范围
    TRUCK_MIN: int = 5_000              # 货车最小重量5吨
    TRUCK_MAX: int = 49_000             # 货车最大重量49吨


@dataclass(frozen=True)
class TravelTimeConstraints:
    """行程时间约束（小时）"""
    MAX_TRAVEL_HOURS: float = 6.0      # 最大行程时间6小时
    MIN_TRAVEL_HOURS: float = 0.5      # 最小行程时间30分钟


@dataclass(frozen=True)
class ReWeightingThresholds:
    """重加权质量阈值"""
    HIGH_QUALITY: float = 1.2           # 高质量阈值（权重>1.2）
    LOW_QUALITY: float = 0.8            # 低质量阈值（权重<0.8）


@dataclass(frozen=True)
class BusinessConstants:
    """业务常量集合（不可变）"""
    axle_weights: AxleWeightLimits = field(default_factory=AxleWeightLimits)
    score_weights: ScoreWeights = field(default_factory=ScoreWeights)
    score_penalties: ScorePenalties = field(default_factory=ScorePenalties)
    time_periods: TimePeriods = field(default_factory=TimePeriods)
    vehicle_weights: VehicleWeightRanges = field(default_factory=VehicleWeightRanges)
    travel_constraints: TravelTimeConstraints = field(default_factory=TravelTimeConstraints)
    reweighting: ReWeightingThresholds = field(default_factory=ReWeightingThresholds)


# 全局常量实例（单例模式）
CONSTANTS = BusinessConstants()


# 兼容旧代码的常量（逐步迁移）
AXLE_WEIGHT_LIMITS = CONSTANTS.axle_weights.to_dict()
