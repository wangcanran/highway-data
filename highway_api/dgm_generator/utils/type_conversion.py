"""类型转换工具模块 - 提供安全的类型转换函数

修复问题：
1. 裸except块
2. 类型转换崩溃
3. 缺少日志
"""
import logging
from typing import Any, Union, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def safe_int_conversion(
    value: Any, 
    default: int = 0, 
    field_name: str = "",
    strict: bool = False
) -> int:
    """安全的整数转换
    
    Args:
        value: 待转换的值（支持int, float, str, None）
        default: 转换失败时的默认值
        field_name: 字段名（用于日志记录）
        strict: 严格模式，失败时抛出异常而不是返回默认值
    
    Returns:
        转换后的整数
    
    Raises:
        ValueError: strict=True时转换失败
    
    Examples:
        >>> safe_int_conversion("123")
        123
        >>> safe_int_conversion("123.45")
        123
        >>> safe_int_conversion(None, default=-1)
        -1
        >>> safe_int_conversion("abc", default=0)
        0
    """
    if value is None:
        if strict:
            raise ValueError(f"{field_name or 'Value'} is None")
        return default
    
    try:
        # 已经是数字类型
        if isinstance(value, (int, float)):
            return int(value)
        
        # 字符串类型
        if isinstance(value, str):
            value = value.strip()
            if not value:
                if strict:
                    raise ValueError(f"{field_name or 'Value'} is empty string")
                return default
            
            # 处理可能的浮点数字符串
            return int(float(value))
        
        # 未知类型
        error_msg = f"Unsupported type {type(value).__name__} for {field_name or 'value'}: {value}"
        logger.warning(error_msg)
        if strict:
            raise TypeError(error_msg)
        return default
        
    except (ValueError, TypeError) as e:
        error_msg = f"{field_name or 'Value'} conversion failed: {value} -> {e}"
        logger.warning(error_msg)
        if strict:
            raise ValueError(error_msg) from e
        return default


def safe_float_conversion(
    value: Any,
    default: float = 0.0,
    field_name: str = "",
    strict: bool = False
) -> float:
    """安全的浮点数转换
    
    Args:
        value: 待转换的值
        default: 转换失败时的默认值
        field_name: 字段名（用于日志）
        strict: 严格模式
    
    Returns:
        转换后的浮点数
    
    Raises:
        ValueError: strict=True时转换失败
    """
    if value is None:
        if strict:
            raise ValueError(f"{field_name or 'Value'} is None")
        return default
    
    try:
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, str):
            value = value.strip()
            if not value:
                if strict:
                    raise ValueError(f"{field_name or 'Value'} is empty")
                return default
            return float(value)
        
        error_msg = f"Unsupported type {type(value).__name__} for {field_name}"
        logger.warning(error_msg)
        if strict:
            raise TypeError(error_msg)
        return default
        
    except (ValueError, TypeError) as e:
        error_msg = f"{field_name} conversion failed: {value} -> {e}"
        logger.warning(error_msg)
        if strict:
            raise ValueError(error_msg) from e
        return default


def safe_datetime_conversion(
    value: Any,
    default: Optional[datetime] = None,
    field_name: str = "",
    strict: bool = False
) -> Optional[datetime]:
    """安全的日期时间转换
    
    Args:
        value: 待转换的值（ISO格式字符串或datetime对象）
        default: 转换失败时的默认值
        field_name: 字段名
        strict: 严格模式
    
    Returns:
        转换后的datetime对象，失败时返回default
    
    Raises:
        ValueError: strict=True时转换失败
    """
    if value is None:
        if strict:
            raise ValueError(f"{field_name or 'Value'} is None")
        return default
    
    try:
        if isinstance(value, datetime):
            return value
        
        if isinstance(value, str):
            value = value.strip()
            if not value:
                if strict:
                    raise ValueError(f"{field_name} is empty")
                return default
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        
        error_msg = f"Unsupported type {type(value).__name__} for {field_name}"
        logger.warning(error_msg)
        if strict:
            raise TypeError(error_msg)
        return default
        
    except (ValueError, TypeError) as e:
        error_msg = f"{field_name} datetime conversion failed: {value} -> {e}"
        logger.warning(error_msg)
        if strict:
            raise ValueError(error_msg) from e
        return default


def extract_mileage(sample: dict) -> int:
    """从样本中安全提取里程数
    
    专门处理fee_mileage字段的复杂类型转换情况
    
    Args:
        sample: 样本字典
    
    Returns:
        里程数（米）
    
    Examples:
        >>> extract_mileage({"fee_mileage": "12345"})
        12345
        >>> extract_mileage({"fee_mileage": "12345.67"})
        12345
        >>> extract_mileage({"fee_mileage": 12345})
        12345
        >>> extract_mileage({})
        0
    """
    return safe_int_conversion(
        sample.get("fee_mileage"),
        default=0,
        field_name="fee_mileage"
    )


def extract_fee(sample: dict) -> int:
    """从样本中安全提取费用
    
    Args:
        sample: 样本字典
    
    Returns:
        费用（分）
    """
    return safe_int_conversion(
        sample.get("pay_fee"),
        default=0,
        field_name="pay_fee"
    )


def extract_vehicle_type(sample: dict) -> int:
    """从样本中安全提取车型代码
    
    Args:
        sample: 样本字典
    
    Returns:
        车型代码（1-26）
    """
    return safe_int_conversion(
        sample.get("vehicle_type"),
        default=1,
        field_name="vehicle_type"
    )
