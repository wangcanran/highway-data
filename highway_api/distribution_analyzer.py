"""
真实数据分布分析器

功能：
1. 从数据库统计真实数据的分布
2. 提取各字段的概率分布和统计特征
3. 为LLM生成提供分布约束
4. 评估生成数据与真实数据的分布一致性
"""

import json
import math
from collections import Counter
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

import numpy as np


@dataclass
class FieldDistribution:
    """单个字段的分布统计"""
    field_name: str
    field_type: str  # categorical / numerical / datetime
    
    # 类别型字段
    value_counts: Dict[str, int] = field(default_factory=dict)
    value_probs: Dict[str, float] = field(default_factory=dict)
    
    # 数值型字段
    min_val: float = 0.0
    max_val: float = 0.0
    mean_val: float = 0.0
    std_val: float = 0.0
    percentiles: Dict[str, float] = field(default_factory=dict)  # 25%, 50%, 75%
    
    # 时间型字段
    hour_distribution: Dict[int, float] = field(default_factory=dict)
    weekday_distribution: Dict[int, float] = field(default_factory=dict)


@dataclass
class DatasetDistribution:
    """数据集的完整分布"""
    total_count: int = 0
    field_distributions: Dict[str, FieldDistribution] = field(default_factory=dict)
    
    # 字段间的联合分布 (重要关联)
    joint_distributions: Dict[str, Dict] = field(default_factory=dict)


class DistributionAnalyzer:
    """分布分析器"""
    
    # 字段类型定义
    CATEGORICAL_FIELDS = [
        "vehicle_type", "gantry_type", "media_type", "transaction_type",
        "pass_state", "axle_count", "cpu_card_type", "vehicle_sign"
    ]
    
    NUMERICAL_FIELDS = [
        "pay_fee", "discount_fee", "fee_mileage", "total_weight"
    ]
    
    DATETIME_FIELDS = [
        "transaction_time", "entrance_time"
    ]
    
    def analyze_from_db(self, limit: int = 10000) -> DatasetDistribution:
        """从数据库分析真实数据分布"""
        from app import app, db
        from models import GantryTransaction
        
        distribution = DatasetDistribution()
        
        with app.app_context():
            query = db.session.query(GantryTransaction).limit(limit)
            rows = query.all()
            
            distribution.total_count = len(rows)
            print(f"[分析] 从数据库读取 {len(rows)} 条记录")
            
            # 收集各字段数据
            field_data = {f: [] for f in self.CATEGORICAL_FIELDS + self.NUMERICAL_FIELDS + self.DATETIME_FIELDS}
            
            for row in rows:
                for f in field_data:
                    val = getattr(row, f, None)
                    if val is not None:
                        field_data[f].append(val)
            
            # 分析各字段分布
            for f in self.CATEGORICAL_FIELDS:
                if field_data[f]:
                    distribution.field_distributions[f] = self._analyze_categorical(f, field_data[f])
            
            for f in self.NUMERICAL_FIELDS:
                if field_data[f]:
                    distribution.field_distributions[f] = self._analyze_numerical(f, field_data[f])
            
            for f in self.DATETIME_FIELDS:
                if field_data[f]:
                    distribution.field_distributions[f] = self._analyze_datetime(f, field_data[f])
            
            # 分析联合分布 (车型-轴数)
            if field_data["vehicle_type"] and field_data["axle_count"]:
                distribution.joint_distributions["vehicle_type_axle_count"] = self._analyze_joint(
                    list(zip(field_data["vehicle_type"], field_data["axle_count"]))
                )
        
        return distribution
    
    def analyze_from_samples(self, samples: List[Dict]) -> DatasetDistribution:
        """从样本列表分析分布 (用于评估生成数据)"""
        distribution = DatasetDistribution()
        distribution.total_count = len(samples)
        
        # 收集各字段数据
        field_data = {f: [] for f in self.CATEGORICAL_FIELDS + self.NUMERICAL_FIELDS}
        
        for sample in samples:
            for f in field_data:
                val = sample.get(f)
                if val is not None:
                    field_data[f].append(str(val) if f in self.CATEGORICAL_FIELDS else val)
        
        # 分析分布
        for f in self.CATEGORICAL_FIELDS:
            if field_data[f]:
                distribution.field_distributions[f] = self._analyze_categorical(f, field_data[f])
        
        for f in self.NUMERICAL_FIELDS:
            if field_data[f]:
                values = [int(v) if isinstance(v, str) else v for v in field_data[f]]
                distribution.field_distributions[f] = self._analyze_numerical(f, values)
        
        return distribution
    
    def _analyze_categorical(self, field_name: str, values: List) -> FieldDistribution:
        """分析类别型字段"""
        dist = FieldDistribution(field_name=field_name, field_type="categorical")
        
        counter = Counter(str(v) for v in values)
        total = sum(counter.values())
        
        dist.value_counts = dict(counter)
        dist.value_probs = {k: v / total for k, v in counter.items()}
        
        return dist
    
    def _analyze_numerical(self, field_name: str, values: List) -> FieldDistribution:
        """分析数值型字段"""
        dist = FieldDistribution(field_name=field_name, field_type="numerical")
        
        # 转换为数值
        nums = []
        for v in values:
            try:
                nums.append(float(v))
            except:
                pass
        
        if nums:
            arr = np.array(nums)
            dist.min_val = float(np.min(arr))
            dist.max_val = float(np.max(arr))
            dist.mean_val = float(np.mean(arr))
            dist.std_val = float(np.std(arr))
            dist.percentiles = {
                "25%": float(np.percentile(arr, 25)),
                "50%": float(np.percentile(arr, 50)),
                "75%": float(np.percentile(arr, 75))
            }
        
        return dist
    
    def _analyze_datetime(self, field_name: str, values: List) -> FieldDistribution:
        """分析时间型字段"""
        dist = FieldDistribution(field_name=field_name, field_type="datetime")
        
        hours = []
        weekdays = []
        
        for v in values:
            if isinstance(v, datetime):
                hours.append(v.hour)
                weekdays.append(v.weekday())
        
        if hours:
            hour_counter = Counter(hours)
            total = sum(hour_counter.values())
            dist.hour_distribution = {h: c / total for h, c in hour_counter.items()}
        
        if weekdays:
            weekday_counter = Counter(weekdays)
            total = sum(weekday_counter.values())
            dist.weekday_distribution = {w: c / total for w, c in weekday_counter.items()}
        
        return dist
    
    def _analyze_joint(self, pairs: List[Tuple]) -> Dict:
        """分析联合分布"""
        counter = Counter(pairs)
        total = sum(counter.values())
        return {str(k): v / total for k, v in counter.items()}


class DistributionConstraintGenerator:
    """将分布转换为LLM可理解的约束描述"""
    
    def generate_constraints(self, distribution: DatasetDistribution) -> str:
        """生成分布约束的自然语言描述"""
        constraints = []
        
        constraints.append("# 真实数据分布约束\n")
        constraints.append("生成数据时，必须严格遵循以下从真实数据中统计得到的分布：\n")
        
        # 1. 类别型字段分布
        for field_name, field_dist in distribution.field_distributions.items():
            if field_dist.field_type == "categorical":
                # 只保留主要类别 (概率 > 1%)
                major_probs = {k: v for k, v in field_dist.value_probs.items() if v > 0.01}
                if major_probs:
                    desc = ", ".join([f'"{k}": {v:.1%}' for k, v in sorted(major_probs.items(), key=lambda x: -x[1])])
                    constraints.append(f"## {field_name} 分布:\n{desc}\n")
        
        # 2. 数值型字段范围
        for field_name, field_dist in distribution.field_distributions.items():
            if field_dist.field_type == "numerical":
                constraints.append(
                    f"## {field_name} 统计:\n"
                    f"范围: [{field_dist.min_val:.0f}, {field_dist.max_val:.0f}], "
                    f"均值: {field_dist.mean_val:.0f}, 标准差: {field_dist.std_val:.0f}\n"
                    f"分位数: 25%={field_dist.percentiles.get('25%', 0):.0f}, "
                    f"50%={field_dist.percentiles.get('50%', 0):.0f}, "
                    f"75%={field_dist.percentiles.get('75%', 0):.0f}\n"
                )
        
        # 3. 时间分布
        for field_name, field_dist in distribution.field_distributions.items():
            if field_dist.field_type == "datetime" and field_dist.hour_distribution:
                # 找出高峰时段
                peak_hours = sorted(field_dist.hour_distribution.items(), key=lambda x: -x[1])[:5]
                peak_desc = ", ".join([f"{h}时({p:.1%})" for h, p in peak_hours])
                constraints.append(f"## {field_name} 时段分布:\n高峰时段: {peak_desc}\n")
        
        return "\n".join(constraints)
    
    def generate_sampling_weights(self, distribution: DatasetDistribution) -> Dict[str, Dict]:
        """生成采样权重，用于控制生成分布"""
        weights = {}
        
        for field_name, field_dist in distribution.field_distributions.items():
            if field_dist.field_type == "categorical":
                weights[field_name] = field_dist.value_probs
        
        return weights


class DistributionEvaluator:
    """分布一致性评估器"""
    
    def kl_divergence(self, p: Dict[str, float], q: Dict[str, float]) -> float:
        """计算 KL 散度 (P相对于Q)"""
        all_keys = set(p.keys()) | set(q.keys())
        
        kl = 0.0
        for k in all_keys:
            p_val = p.get(k, 1e-10)
            q_val = q.get(k, 1e-10)
            if p_val > 0:
                kl += p_val * math.log(p_val / q_val)
        
        return kl
    
    def js_divergence(self, p: Dict[str, float], q: Dict[str, float]) -> float:
        """计算 JS 散度 (对称版本的KL散度)"""
        all_keys = set(p.keys()) | set(q.keys())
        
        # 计算 M = (P + Q) / 2
        m = {}
        for k in all_keys:
            m[k] = (p.get(k, 0) + q.get(k, 0)) / 2
        
        return (self.kl_divergence(p, m) + self.kl_divergence(q, m)) / 2
    
    def evaluate_distribution_match(
        self, 
        real_dist: DatasetDistribution, 
        generated_dist: DatasetDistribution
    ) -> Dict[str, float]:
        """评估生成数据与真实数据的分布匹配度"""
        results = {}
        
        for field_name in real_dist.field_distributions:
            real_field = real_dist.field_distributions.get(field_name)
            gen_field = generated_dist.field_distributions.get(field_name)
            
            if real_field and gen_field and real_field.field_type == "categorical":
                # 计算 JS 散度
                js = self.js_divergence(real_field.value_probs, gen_field.value_probs)
                # 转换为相似度 (0-1，越高越好)
                similarity = 1 / (1 + js)
                results[field_name] = similarity
        
        # 计算平均匹配度
        if results:
            results["overall"] = sum(results.values()) / len(results)
        
        return results
    
    def print_comparison_report(
        self,
        real_dist: DatasetDistribution,
        generated_dist: DatasetDistribution
    ):
        """打印分布对比报告"""
        print("\n" + "=" * 60)
        print("分布一致性评估报告")
        print("=" * 60)
        
        match_scores = self.evaluate_distribution_match(real_dist, generated_dist)
        
        print(f"\n总体匹配度: {match_scores.get('overall', 0):.2%}\n")
        
        print("-" * 60)
        print(f"{'字段名':<20} {'真实分布':<25} {'生成分布':<25} {'匹配度':<10}")
        print("-" * 60)
        
        for field_name in real_dist.field_distributions:
            real_field = real_dist.field_distributions.get(field_name)
            gen_field = generated_dist.field_distributions.get(field_name)
            
            if real_field and real_field.field_type == "categorical":
                # 获取 top-3 类别
                real_top = sorted(real_field.value_probs.items(), key=lambda x: -x[1])[:3]
                real_str = ", ".join([f"{k}:{v:.0%}" for k, v in real_top])
                
                if gen_field:
                    gen_top = sorted(gen_field.value_probs.items(), key=lambda x: -x[1])[:3]
                    gen_str = ", ".join([f"{k}:{v:.0%}" for k, v in gen_top])
                    match = match_scores.get(field_name, 0)
                else:
                    gen_str = "N/A"
                    match = 0
                
                print(f"{field_name:<20} {real_str:<25} {gen_str:<25} {match:.2%}")
        
        print("-" * 60)


# ==================== 示例用法 ====================

def demo_analyze_real_data():
    """演示：分析真实数据分布"""
    analyzer = DistributionAnalyzer()
    
    print("正在分析数据库中的真实数据分布...")
    real_dist = analyzer.analyze_from_db(limit=5000)
    
    # 生成约束描述
    constraint_gen = DistributionConstraintGenerator()
    constraints = constraint_gen.generate_constraints(real_dist)
    
    print("\n生成的分布约束描述:")
    print(constraints)
    
    # 保存分布信息
    output = {
        "total_count": real_dist.total_count,
        "fields": {}
    }
    
    for field_name, field_dist in real_dist.field_distributions.items():
        output["fields"][field_name] = {
            "type": field_dist.field_type,
            "value_probs": field_dist.value_probs if field_dist.field_type == "categorical" else None,
            "stats": {
                "min": field_dist.min_val,
                "max": field_dist.max_val,
                "mean": field_dist.mean_val,
                "std": field_dist.std_val
            } if field_dist.field_type == "numerical" else None
        }
    
    with open("real_data_distribution.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print("\n分布信息已保存到 real_data_distribution.json")
    
    return real_dist, constraints


if __name__ == "__main__":
    demo_analyze_real_data()
