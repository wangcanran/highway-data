"""车辆分类工具 - 消除重复代码

修复问题：
1. 车型判断逻辑重复15+次
2. 裸except块
3. 缺少类型提示
"""
import logging
from typing import Union, Literal
from enum import IntEnum

logger = logging.getLogger(__name__)


class VehicleType(IntEnum):
    """车辆类型代码范围"""
    # 客车范围
    PASSENGER_MIN = 1
    PASSENGER_MAX = 4
    
    # 货车范围  
    TRUCK_MIN = 11
    TRUCK_MAX = 16
    
    # 专项车范围
    SPECIAL_MIN = 21
    SPECIAL_MAX = 26


VehicleCategory = Literal["客车", "货车", "专项车"]


class VehicleClassifier:
    """车辆分类器（单一职责原则）"""
    
    @staticmethod
    def classify(vehicle_type: Union[str, int]) -> VehicleCategory:
        """分类车辆类型
        
        Args:
            vehicle_type: 车型代码（1-4客车, 11-16货车, 21-26专项车）
            
        Returns:
            车辆类别："客车" | "货车" | "专项车"
            
        Raises:
            ValueError: 车型代码无效
            
        Examples:
            >>> VehicleClassifier.classify(1)
            '客车'
            >>> VehicleClassifier.classify("12")
            '货车'
            >>> VehicleClassifier.classify(25)
            '专项车'
        """
        try:
            vcode = int(vehicle_type)
        except (ValueError, TypeError) as e:
            raise ValueError(f"无效的车型代码: {vehicle_type}") from e
        
        if VehicleType.PASSENGER_MIN <= vcode <= VehicleType.PASSENGER_MAX:
            return "客车"
        elif VehicleType.TRUCK_MIN <= vcode <= VehicleType.TRUCK_MAX:
            return "货车"
        elif VehicleType.SPECIAL_MIN <= vcode <= VehicleType.SPECIAL_MAX:
            return "专项车"
        else:
            raise ValueError(
                f"未知车型代码: {vcode}. "
                f"有效范围: 1-4(客车), 11-16(货车), 21-26(专项车)"
            )
    
    @staticmethod
    def classify_safe(
        vehicle_type: Union[str, int],
        default: VehicleCategory = "客车"
    ) -> VehicleCategory:
        """分类车辆类型（容错版本）
        
        Args:
            vehicle_type: 车型代码
            default: 分类失败时的默认值
            
        Returns:
            车辆类别
            
        Examples:
            >>> VehicleClassifier.classify_safe("abc")
            '客车'
            >>> VehicleClassifier.classify_safe(999, default="货车")
            '货车'
        """
        try:
            return VehicleClassifier.classify(vehicle_type)
        except ValueError as e:
            logger.warning(f"车型分类失败，使用默认值'{default}': {e}")
            return default
    
    @staticmethod
    def is_passenger(vehicle_type: Union[str, int]) -> bool:
        """判断是否为客车
        
        Args:
            vehicle_type: 车型代码
            
        Returns:
            是否为客车
        """
        try:
            category = VehicleClassifier.classify(vehicle_type)
            return category == "客车"
        except ValueError:
            return False
    
    @staticmethod
    def is_truck(vehicle_type: Union[str, int]) -> bool:
        """判断是否为货车（包含专项车）
        
        Args:
            vehicle_type: 车型代码
            
        Returns:
            是否为货车或专项车
        """
        try:
            category = VehicleClassifier.classify(vehicle_type)
            return category in ("货车", "专项车")
        except ValueError:
            return False
    
    @staticmethod
    def get_expected_axles(vehicle_type: Union[str, int]) -> str:
        """获取车型对应的期望轴数
        
        Args:
            vehicle_type: 车型代码
            
        Returns:
            期望轴数（字符串格式："2", "3"等）
            
        Raises:
            ValueError: 车型代码无效
            
        Examples:
            >>> VehicleClassifier.get_expected_axles(1)
            '2'
            >>> VehicleClassifier.get_expected_axles(13)
            '3'
        """
        try:
            vcode = int(vehicle_type)
        except (ValueError, TypeError) as e:
            raise ValueError(f"无效的车型代码: {vehicle_type}") from e
        
        # 客车固定2轴
        if VehicleType.PASSENGER_MIN <= vcode <= VehicleType.PASSENGER_MAX:
            return "2"
        
        # 货车根据代码映射
        axle_mapping = {
            11: "2", 12: "2",  # 2轴货车
            13: "3",           # 3轴货车
            14: "4",           # 4轴货车
            15: "5",           # 5轴货车
            16: "6",           # 6轴货车
            21: "2", 22: "2",  # 2轴专项车
            23: "3",           # 3轴专项车
            24: "4",           # 4轴专项车
            25: "5",           # 5轴专项车
            26: "6",           # 6轴专项车
        }
        
        if vcode in axle_mapping:
            return axle_mapping[vcode]
        
        raise ValueError(f"未知车型代码: {vcode}")


def classify_vehicle(sample: dict) -> VehicleCategory:
    """从样本中提取并分类车辆类型
    
    这是一个便捷函数，用于快速从样本字典中获取车辆类别
    
    Args:
        sample: 样本字典
        
    Returns:
        车辆类别
        
    Examples:
        >>> classify_vehicle({"vehicle_type": "12"})
        '货车'
        >>> classify_vehicle({"vehicle_type": "abc"})
        '客车'
    """
    vehicle_type = sample.get("vehicle_type", "1")
    return VehicleClassifier.classify_safe(vehicle_type)
