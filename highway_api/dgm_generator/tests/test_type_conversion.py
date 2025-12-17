"""类型转换工具测试

运行测试：
    pytest tests/test_type_conversion.py -v
    
覆盖率：
    pytest tests/test_type_conversion.py --cov=utils.type_conversion --cov-report=html
"""
import pytest
from datetime import datetime
from utils.type_conversion import (
    safe_int_conversion,
    safe_float_conversion,
    safe_datetime_conversion,
    extract_mileage,
    extract_fee,
    extract_vehicle_type
)


class TestSafeIntConversion:
    """测试safe_int_conversion函数"""
    
    def test_convert_int(self):
        """测试整数转换"""
        assert safe_int_conversion(123) == 123
        assert safe_int_conversion(0) == 0
        assert safe_int_conversion(-456) == -456
    
    def test_convert_float(self):
        """测试浮点数转换"""
        assert safe_int_conversion(123.45) == 123
        assert safe_int_conversion(123.99) == 123
        assert safe_int_conversion(-123.45) == -123
    
    def test_convert_string(self):
        """测试字符串转换"""
        assert safe_int_conversion("123") == 123
        assert safe_int_conversion("  123  ") == 123
        assert safe_int_conversion("123.45") == 123
        assert safe_int_conversion("-123") == -123
    
    def test_convert_none(self):
        """测试None值"""
        assert safe_int_conversion(None) == 0
        assert safe_int_conversion(None, default=999) == 999
    
    def test_convert_empty_string(self):
        """测试空字符串"""
        assert safe_int_conversion("") == 0
        assert safe_int_conversion("   ") == 0
        assert safe_int_conversion("", default=-1) == -1
    
    def test_convert_invalid(self):
        """测试无效输入"""
        assert safe_int_conversion("abc") == 0
        assert safe_int_conversion("abc", default=-1) == -1
        assert safe_int_conversion([1, 2, 3]) == 0
        assert safe_int_conversion({"a": 1}) == 0
    
    def test_strict_mode(self):
        """测试严格模式"""
        with pytest.raises(ValueError):
            safe_int_conversion(None, strict=True)
        
        with pytest.raises(ValueError):
            safe_int_conversion("", strict=True)
        
        with pytest.raises(ValueError):
            safe_int_conversion("abc", strict=True)
    
    def test_field_name_logging(self, caplog):
        """测试字段名记录"""
        safe_int_conversion("invalid", field_name="test_field")
        assert "test_field" in caplog.text


class TestSafeFloatConversion:
    """测试safe_float_conversion函数"""
    
    def test_convert_float(self):
        """测试浮点数转换"""
        assert safe_float_conversion(123.45) == pytest.approx(123.45)
        assert safe_float_conversion(0.0) == 0.0
    
    def test_convert_int(self):
        """测试整数转浮点"""
        assert safe_float_conversion(123) == pytest.approx(123.0)
    
    def test_convert_string(self):
        """测试字符串转浮点"""
        assert safe_float_conversion("123.45") == pytest.approx(123.45)
        assert safe_float_conversion("  123.45  ") == pytest.approx(123.45)
    
    def test_convert_invalid(self):
        """测试无效输入"""
        assert safe_float_conversion("abc") == 0.0
        assert safe_float_conversion("abc", default=999.9) == pytest.approx(999.9)


class TestSafeDatetimeConversion:
    """测试safe_datetime_conversion函数"""
    
    def test_convert_datetime(self):
        """测试datetime对象"""
        dt = datetime(2023, 1, 1, 12, 0, 0)
        assert safe_datetime_conversion(dt) == dt
    
    def test_convert_iso_string(self):
        """测试ISO格式字符串"""
        result = safe_datetime_conversion("2023-01-01T12:00:00")
        assert result == datetime(2023, 1, 1, 12, 0, 0)
    
    def test_convert_iso_with_z(self):
        """测试带Z的ISO格式"""
        result = safe_datetime_conversion("2023-01-01T12:00:00Z")
        assert result is not None
        assert result.year == 2023
    
    def test_convert_none(self):
        """测试None值"""
        assert safe_datetime_conversion(None) is None
        
        default = datetime(2023, 1, 1)
        assert safe_datetime_conversion(None, default=default) == default
    
    def test_convert_invalid(self):
        """测试无效输入"""
        assert safe_datetime_conversion("invalid") is None
        assert safe_datetime_conversion("") is None


class TestExtractFunctions:
    """测试便捷提取函数"""
    
    def test_extract_mileage(self):
        """测试里程提取"""
        assert extract_mileage({"fee_mileage": "12345"}) == 12345
        assert extract_mileage({"fee_mileage": 12345}) == 12345
        assert extract_mileage({"fee_mileage": "12345.67"}) == 12345
        assert extract_mileage({}) == 0
        assert extract_mileage({"fee_mileage": None}) == 0
    
    def test_extract_fee(self):
        """测试费用提取"""
        assert extract_fee({"pay_fee": 1000}) == 1000
        assert extract_fee({"pay_fee": "1000"}) == 1000
        assert extract_fee({}) == 0
    
    def test_extract_vehicle_type(self):
        """测试车型提取"""
        assert extract_vehicle_type({"vehicle_type": "12"}) == 12
        assert extract_vehicle_type({"vehicle_type": 12}) == 12
        assert extract_vehicle_type({}) == 1  # 默认客车
        assert extract_vehicle_type({"vehicle_type": "invalid"}) == 1


# Pytest fixtures
@pytest.fixture
def sample_data():
    """测试用样本数据"""
    return {
        "gantry_transaction_id": "TEST123",
        "vehicle_type": "12",
        "fee_mileage": "12345",
        "pay_fee": 1000
    }


def test_full_extraction(sample_data):
    """测试完整数据提取"""
    assert extract_vehicle_type(sample_data) == 12
    assert extract_mileage(sample_data) == 12345
    assert extract_fee(sample_data) == 1000
