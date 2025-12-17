"""车辆分类器测试"""
import pytest
from utils.vehicle_classifier import (
    VehicleClassifier,
    VehicleType,
    classify_vehicle
)


class TestVehicleClassifier:
    """测试车辆分类器"""
    
    def test_classify_passenger(self):
        """测试客车分类"""
        assert VehicleClassifier.classify(1) == "客车"
        assert VehicleClassifier.classify(2) == "客车"
        assert VehicleClassifier.classify(3) == "客车"
        assert VehicleClassifier.classify(4) == "客车"
        assert VehicleClassifier.classify("1") == "客车"
        assert VehicleClassifier.classify("4") == "客车"
    
    def test_classify_truck(self):
        """测试货车分类"""
        assert VehicleClassifier.classify(11) == "货车"
        assert VehicleClassifier.classify(12) == "货车"
        assert VehicleClassifier.classify(16) == "货车"
        assert VehicleClassifier.classify("11") == "货车"
    
    def test_classify_special(self):
        """测试专项车分类"""
        assert VehicleClassifier.classify(21) == "专项车"
        assert VehicleClassifier.classify(26) == "专项车"
        assert VehicleClassifier.classify("21") == "专项车"
    
    def test_classify_invalid(self):
        """测试无效车型"""
        with pytest.raises(ValueError, match="无效的车型代码"):
            VehicleClassifier.classify("abc")
        
        with pytest.raises(ValueError, match="未知车型代码"):
            VehicleClassifier.classify(999)
        
        with pytest.raises(ValueError, match="未知车型代码"):
            VehicleClassifier.classify(5)
    
    def test_classify_safe(self):
        """测试安全分类"""
        assert VehicleClassifier.classify_safe("abc") == "客车"
        assert VehicleClassifier.classify_safe(999) == "客车"
        assert VehicleClassifier.classify_safe(999, default="货车") == "货车"
        assert VehicleClassifier.classify_safe(1) == "客车"
        assert VehicleClassifier.classify_safe(12) == "货车"
    
    def test_is_passenger(self):
        """测试是否客车"""
        assert VehicleClassifier.is_passenger(1) is True
        assert VehicleClassifier.is_passenger(4) is True
        assert VehicleClassifier.is_passenger(12) is False
        assert VehicleClassifier.is_passenger(999) is False
    
    def test_is_truck(self):
        """测试是否货车"""
        assert VehicleClassifier.is_truck(12) is True
        assert VehicleClassifier.is_truck(16) is True
        assert VehicleClassifier.is_truck(21) is True  # 专项车也算货车
        assert VehicleClassifier.is_truck(1) is False
        assert VehicleClassifier.is_truck(999) is False
    
    def test_get_expected_axles(self):
        """测试期望轴数"""
        # 客车固定2轴
        assert VehicleClassifier.get_expected_axles(1) == "2"
        assert VehicleClassifier.get_expected_axles(4) == "2"
        
        # 货车根据代码
        assert VehicleClassifier.get_expected_axles(11) == "2"
        assert VehicleClassifier.get_expected_axles(13) == "3"
        assert VehicleClassifier.get_expected_axles(14) == "4"
        assert VehicleClassifier.get_expected_axles(15) == "5"
        assert VehicleClassifier.get_expected_axles(16) == "6"
        
        # 无效车型
        with pytest.raises(ValueError):
            VehicleClassifier.get_expected_axles(999)


def test_classify_vehicle_helper():
    """测试便捷分类函数"""
    sample1 = {"vehicle_type": "1"}
    assert classify_vehicle(sample1) == "客车"
    
    sample2 = {"vehicle_type": "12"}
    assert classify_vehicle(sample2) == "货车"
    
    sample3 = {"vehicle_type": "invalid"}
    assert classify_vehicle(sample3) == "客车"  # 容错
    
    sample4 = {}
    assert classify_vehicle(sample4) == "客车"  # 默认


class TestVehicleType:
    """测试车型枚举"""
    
    def test_enum_values(self):
        """测试枚举值"""
        assert VehicleType.PASSENGER_MIN == 1
        assert VehicleType.PASSENGER_MAX == 4
        assert VehicleType.TRUCK_MIN == 11
        assert VehicleType.TRUCK_MAX == 16
        assert VehicleType.SPECIAL_MIN == 21
        assert VehicleType.SPECIAL_MAX == 26
