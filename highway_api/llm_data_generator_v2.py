"""
基于大模型的数据生成框架 V2

实现论文方法论：
1. 任务说明 (Task Specification) - 明确生成目标
2. 生成条件 (Generation Conditions) - 控制生成属性
3. 上下文示例 (In-context Demonstrations) - Few-shot 引导

任务拆解策略：
- Sample-wise Decomposition: 将复杂样本拆解为多个字段组块分步生成
- Dataset-wise Decomposition: 数据集级别的生成调度，确保多样性

质量控制：
- 高质量样本过滤
- 标记增强 (使用第三方模型校验)
- 样本加权

评估：
- 直接评估: 忠实度 + 多样性
- 间接评估: 下游任务效果
"""

import json
import random
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from openai import OpenAI

import config

# 延迟导入分布分析器，避免循环依赖
def get_distribution_analyzer():
    from distribution_analyzer import (
        DistributionAnalyzer, 
        DistributionConstraintGenerator,
        DistributionEvaluator
    )
    return DistributionAnalyzer, DistributionConstraintGenerator, DistributionEvaluator


client = OpenAI(
    api_key=config.OPENAI_API_KEY,
    base_url=config.OPENAI_API_BASE,
    timeout=config.REQUEST_TIMEOUT
)


# ==================== 数据结构定义 ====================

@dataclass
class GenerationTask:
    """生成子任务定义"""
    task_id: str
    prompt: str  # p_i
    model: str   # M_i
    depends_on: List[str] = field(default_factory=list)  # 依赖的前置任务


@dataclass 
class GenerationCondition:
    """生成条件"""
    vehicle_type: Optional[str] = None      # 车型: 客车/货车
    time_period: Optional[str] = None       # 时段: 早高峰/晚高峰/深夜
    scenario: Optional[str] = None          # 场景: 正常/超载/异常
    region: Optional[str] = None            # 区域: 广东/江苏等


@dataclass
class QualityScore:
    """质量评分"""
    fidelity: float = 0.0      # 忠实度 (0-1)
    diversity: float = 0.0     # 多样性 (0-1)
    consistency: float = 0.0   # 一致性 (0-1)
    overall: float = 0.0       # 综合分


# ==================== In-context 示例库 ====================

DEMONSTRATION_EXAMPLES = {
    "gantry_truck": [
        {
            "gantry_transaction_id": "GT20231115093021847362",
            "gantry_id": "G440101",
            "gantry_type": "2",
            "transaction_time": "2023-11-15T09:30:21",
            "entrance_time": "2023-11-15T07:15:43",
            "pay_fee": 4500,
            "discount_fee": 225,
            "media_type": "1",
            "vehicle_type": "2",
            "axle_count": "4",
            "total_weight": "28500",
            "fee_mileage": "90000",
            "pass_id": "PASS20231115071543001",
            "section_id": "S440101",
            "section_name": "广州-东莞高速"
        }
    ],
    "gantry_car": [
        {
            "gantry_transaction_id": "GT20231115101532156789",
            "gantry_id": "G440102",
            "gantry_type": "2", 
            "transaction_time": "2023-11-15T10:15:32",
            "entrance_time": "2023-11-15T09:45:10",
            "pay_fee": 1500,
            "discount_fee": 75,
            "media_type": "1",
            "vehicle_type": "1",
            "axle_count": "2",
            "total_weight": "2500",
            "fee_mileage": "30000",
            "pass_id": "PASS20231115094510002",
            "section_id": "S440102",
            "section_name": "东莞-深圳高速"
        }
    ]
}


# ==================== Sample-wise Decomposition ====================

class SampleWiseDecomposer:
    """
    样本维度拆解器
    将一个完整样本拆解为多个组块 (chunks)，分步生成
    """
    
    # 定义字段组块
    CHUNKS = {
        "identity": ["gantry_transaction_id", "pass_id", "gantry_id", "section_id", "section_name"],
        "time": ["transaction_time", "entrance_time"],
        "vehicle": ["vehicle_type", "axle_count", "total_weight", "vehicle_sign"],
        "fee": ["pay_fee", "discount_fee", "fee_mileage", "fee"],
        "status": ["gantry_type", "media_type", "transaction_type", "pass_state", "cpu_card_type"]
    }
    
    def __init__(self):
        self.model = config.FIXED_MODEL_NAME
    
    def generate_chunk(self, chunk_name: str, context: Dict, condition: GenerationCondition) -> Dict:
        """生成单个组块"""
        
        chunk_fields = self.CHUNKS[chunk_name]
        
        prompts = {
            "identity": self._get_identity_prompt(condition),
            "time": self._get_time_prompt(context, condition),
            "vehicle": self._get_vehicle_prompt(context, condition),
            "fee": self._get_fee_prompt(context, condition),
            "status": self._get_status_prompt(context, condition)
        }
        
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是数据生成专家。只输出JSON对象，不要有其他文字。"},
                {"role": "user", "content": prompts[chunk_name]}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        
        return json.loads(content)
    
    def _get_identity_prompt(self, condition: GenerationCondition) -> str:
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        region = condition.region or "广东"
        return f"""生成门架交易的身份标识字段：
- gantry_transaction_id: "GT" + 时间戳 + 6位随机数，基于 {ts}
- pass_id: "PASS" + 时间戳 + 8位随机数
- gantry_id: "G" + 6位数字 (如 G440101)
- section_id: "S" + 6位数字
- section_name: {region}地区的高速公路名称

输出JSON对象。"""

    def _get_time_prompt(self, context: Dict, condition: GenerationCondition) -> str:
        time_desc = {
            "早高峰": "07:00-09:00",
            "晚高峰": "17:00-19:00",
            "深夜": "23:00-05:00",
            None: "任意时段"
        }.get(condition.time_period, "任意时段")
        
        return f"""生成时间字段：
- transaction_time: 交易时间，时段要求: {time_desc}
- entrance_time: 入口时间，必须早于 transaction_time，时间差 30分钟-3小时

输出JSON对象，时间格式为 ISO (YYYY-MM-DDTHH:MM:SS)。"""

    def _get_vehicle_prompt(self, context: Dict, condition: GenerationCondition) -> str:
        vehicle_desc = {
            "货车": 'vehicle_type="2"，axle_count 2-6轴，限重规则：2轴18吨/3轴25吨/4轴31吨/5轴43吨/6轴49吨',
            "客车": 'vehicle_type="1"，axle_count="2"，total_weight 2000-5000kg',
            "超载货车": 'vehicle_type="2"，total_weight 要超过对应轴数的限重10%-30%',
            None: "随机车型"
        }.get(condition.scenario or condition.vehicle_type, "随机车型")
        
        return f"""生成车辆字段：
要求: {vehicle_desc}
- vehicle_type: "1"客车, "2"货车
- axle_count: 轴数字符串
- total_weight: 重量(kg)字符串
- vehicle_sign: "0"普通车, "1"军警车

输出JSON对象。"""

    def _get_fee_prompt(self, context: Dict, condition: GenerationCondition) -> str:
        mileage = context.get("fee_mileage", "50000")
        return f"""生成费用字段，里程约 {mileage} 米：
- pay_fee: 应付金额(分)，约 0.5元/公里
- discount_fee: 优惠金额(分)，ETC用户约5%优惠，否则为0
- fee_mileage: 收费里程(米)字符串
- fee: 费用明细字符串

输出JSON对象。"""

    def _get_status_prompt(self, context: Dict, condition: GenerationCondition) -> str:
        scenario = condition.scenario or "正常"
        return f"""生成状态字段，场景: {scenario}
- gantry_type: "1"省界/"2"普通/"3"入口/"4"出口
- media_type: "1"ETC/"2"CPC卡/"3"纸券
- transaction_type: "1"正常/"2"补费/"3"退费
- pass_state: "1"正常/"2"异常
- cpu_card_type: "1"记账卡/"2"储值卡

{'异常场景需要 pass_state="2" 或 transaction_type!="1"' if scenario == "异常" else ''}
输出JSON对象。"""

    def generate_sample(self, condition: GenerationCondition) -> Dict:
        """分步生成完整样本"""
        sample = {}
        
        # 按依赖顺序生成各组块
        for chunk_name in ["identity", "time", "vehicle", "status"]:
            chunk_data = self.generate_chunk(chunk_name, sample, condition)
            sample.update(chunk_data)
        
        # fee 依赖 vehicle 和 status
        fee_data = self.generate_chunk("fee", sample, condition)
        sample.update(fee_data)
        
        return sample


# ==================== Dataset-wise Decomposition ====================

class DatasetWiseScheduler:
    """
    数据集维度调度器
    控制数据集的整体分布和多样性
    """
    
    def __init__(self):
        self.generated_count = {"货车": 0, "客车": 0}
        self.time_distribution = {"早高峰": 0, "晚高峰": 0, "平峰": 0, "深夜": 0}
        self.scenario_distribution = {"正常": 0, "超载": 0, "异常": 0}
    
    def get_next_condition(self, target_distribution: Dict = None) -> GenerationCondition:
        """根据目标分布决定下一个生成条件"""
        
        if target_distribution is None:
            target_distribution = {
                "vehicle": {"货车": 0.6, "客车": 0.4},
                "time": {"早高峰": 0.3, "晚高峰": 0.3, "平峰": 0.3, "深夜": 0.1},
                "scenario": {"正常": 0.8, "超载": 0.1, "异常": 0.1}
            }
        
        # 计算当前分布与目标分布的差距，选择最需要补充的类别
        total_vehicles = sum(self.generated_count.values()) or 1
        vehicle_gaps = {
            k: target_distribution["vehicle"].get(k, 0) - self.generated_count[k] / total_vehicles
            for k in self.generated_count
        }
        vehicle_type = max(vehicle_gaps, key=vehicle_gaps.get)
        
        total_time = sum(self.time_distribution.values()) or 1
        time_gaps = {
            k: target_distribution["time"].get(k, 0) - self.time_distribution[k] / total_time
            for k in self.time_distribution
        }
        time_period = max(time_gaps, key=time_gaps.get)
        
        total_scenario = sum(self.scenario_distribution.values()) or 1
        scenario_gaps = {
            k: target_distribution["scenario"].get(k, 0) - self.scenario_distribution[k] / total_scenario
            for k in self.scenario_distribution
        }
        scenario = max(scenario_gaps, key=scenario_gaps.get)
        
        return GenerationCondition(
            vehicle_type=vehicle_type,
            time_period=time_period,
            scenario=scenario if scenario != "正常" else None
        )
    
    def update_distribution(self, sample: Dict, condition: GenerationCondition):
        """更新分布统计"""
        vehicle = "货车" if sample.get("vehicle_type") == "2" else "客车"
        self.generated_count[vehicle] = self.generated_count.get(vehicle, 0) + 1
        
        if condition.time_period:
            self.time_distribution[condition.time_period] += 1
        else:
            self.time_distribution["平峰"] += 1
        
        scenario = condition.scenario or "正常"
        self.scenario_distribution[scenario] = self.scenario_distribution.get(scenario, 0) + 1


# ==================== 质量控制 ====================

class QualityController:
    """质量控制器"""
    
    # 业务规则
    AXLE_WEIGHT_LIMITS = {
        "2": 18000, "3": 25000, "4": 31000, "5": 43000, "6": 49000
    }
    
    def validate_sample(self, sample: Dict) -> Tuple[bool, List[str]]:
        """验证样本，返回 (是否有效, 问题列表)"""
        issues = []
        
        # 1. 时间逻辑检查
        if "entrance_time" in sample and "transaction_time" in sample:
            try:
                entrance = datetime.fromisoformat(sample["entrance_time"])
                transaction = datetime.fromisoformat(sample["transaction_time"])
                if entrance >= transaction:
                    issues.append("entrance_time >= transaction_time")
                elif (transaction - entrance).total_seconds() > 14400:  # 4小时
                    issues.append("行程时间超过4小时")
            except:
                issues.append("时间格式错误")
        
        # 2. 费用逻辑检查
        pay_fee = int(sample.get("pay_fee", 0))
        discount_fee = int(sample.get("discount_fee", 0))
        if discount_fee > pay_fee:
            issues.append(f"discount_fee({discount_fee}) > pay_fee({pay_fee})")
        
        # 3. 车辆逻辑检查
        vehicle_type = sample.get("vehicle_type")
        axle_count = str(sample.get("axle_count", "2"))
        total_weight = int(sample.get("total_weight", 0))
        
        if vehicle_type == "2":  # 货车
            limit = self.AXLE_WEIGHT_LIMITS.get(axle_count, 49000)
            if total_weight > limit * 1.5:  # 超载50%以上视为异常
                issues.append(f"货车超载过多: {total_weight}kg > {limit}kg * 1.5")
        
        return len(issues) == 0, issues
    
    def calculate_quality_score(self, sample: Dict) -> QualityScore:
        """计算质量分数"""
        score = QualityScore()
        
        # 忠实度: 基于规则验证
        is_valid, issues = self.validate_sample(sample)
        score.fidelity = 1.0 if is_valid else max(0, 1 - len(issues) * 0.2)
        
        # 一致性: 字段间逻辑一致性
        consistency_checks = 0
        if sample.get("vehicle_type") == "1" and sample.get("axle_count") == "2":
            consistency_checks += 1
        if int(sample.get("pay_fee", 0)) > 0:
            consistency_checks += 1
        score.consistency = consistency_checks / 2
        
        score.overall = (score.fidelity * 0.5 + score.consistency * 0.5)
        return score
    
    def enhance_labels(self, sample: Dict) -> Dict:
        """标记增强: 修正明显的错误"""
        enhanced = sample.copy()
        
        # 修正 discount_fee 超过 pay_fee
        pay_fee = int(enhanced.get("pay_fee", 0))
        discount_fee = int(enhanced.get("discount_fee", 0))
        if discount_fee > pay_fee:
            enhanced["discount_fee"] = int(pay_fee * 0.05)
        
        # 确保时间顺序
        if "entrance_time" in enhanced and "transaction_time" in enhanced:
            try:
                entrance = datetime.fromisoformat(enhanced["entrance_time"])
                transaction = datetime.fromisoformat(enhanced["transaction_time"])
                if entrance >= transaction:
                    # 修正: 入口时间提前1-2小时
                    new_entrance = transaction - timedelta(hours=random.uniform(1, 2))
                    enhanced["entrance_time"] = new_entrance.isoformat()
            except:
                pass
        
        return enhanced


# ==================== 评估器 ====================

class DatasetEvaluator:
    """数据集评估器"""
    
    def evaluate_diversity(self, samples: List[Dict]) -> float:
        """评估多样性: 计算样本间的重复程度"""
        if len(samples) < 2:
            return 1.0
        
        # 基于关键字段计算唯一性
        unique_vehicles = len(set(s.get("vehicle_type") for s in samples))
        unique_gantries = len(set(s.get("gantry_id") for s in samples))
        unique_sections = len(set(s.get("section_id") for s in samples))
        
        max_unique = min(len(samples), 10)  # 最多期望10种不同值
        diversity = (unique_vehicles + unique_gantries/2 + unique_sections/2) / (max_unique * 2)
        return min(1.0, diversity)
    
    def evaluate_fidelity(self, samples: List[Dict], controller: QualityController) -> float:
        """评估忠实度: 符合业务规则的比例"""
        if not samples:
            return 0.0
        
        valid_count = sum(1 for s in samples if controller.validate_sample(s)[0])
        return valid_count / len(samples)
    
    def print_report(self, samples: List[Dict], controller: QualityController):
        """打印评估报告"""
        print("\n" + "=" * 50)
        print("数据集质量评估报告")
        print("=" * 50)
        
        diversity = self.evaluate_diversity(samples)
        fidelity = self.evaluate_fidelity(samples, controller)
        
        print(f"样本数量: {len(samples)}")
        print(f"多样性得分: {diversity:.2%}")
        print(f"忠实度得分: {fidelity:.2%}")
        print(f"综合得分: {(diversity + fidelity) / 2:.2%}")
        
        # 分布统计
        vehicle_dist = {}
        for s in samples:
            vt = "货车" if s.get("vehicle_type") == "2" else "客车"
            vehicle_dist[vt] = vehicle_dist.get(vt, 0) + 1
        
        print(f"\n车型分布: {vehicle_dist}")


# ==================== 主生成器 ====================

class LLMDataGeneratorV2:
    """
    基于大模型的数据生成器 V2
    整合所有组件
    """
    
    def __init__(self, use_real_distribution: bool = False):
        """
        Args:
            use_real_distribution: 是否从数据库学习真实数据分布
        """
        self.decomposer = SampleWiseDecomposer()
        self.scheduler = DatasetWiseScheduler()
        self.quality_controller = QualityController()
        self.evaluator = DatasetEvaluator()
        
        # 真实数据分布相关
        self.real_distribution = None
        self.distribution_constraints = None
        self.dist_evaluator = None
        
        if use_real_distribution:
            self._load_real_distribution()
    
    def _load_real_distribution(self, sample_limit: int = 5000):
        """从数据库加载真实数据分布"""
        DistributionAnalyzer, DistributionConstraintGenerator, DistributionEvaluator = get_distribution_analyzer()
        
        analyzer = DistributionAnalyzer()
        constraint_gen = DistributionConstraintGenerator()
        
        print("[分布] 正在从数据库分析真实数据分布...")
        self.real_distribution = analyzer.analyze_from_db(limit=sample_limit)
        
        # 生成分布约束描述（用于注入LLM prompt）
        self.distribution_constraints = constraint_gen.generate_constraints(self.real_distribution)
        
        # 生成采样权重（用于调度器）
        self.sampling_weights = constraint_gen.generate_sampling_weights(self.real_distribution)
        
        # 初始化评估器
        self.dist_evaluator = DistributionEvaluator()
        
        print("[分布] 真实数据分布加载完成")
        print(f"[分布] 样本数: {self.real_distribution.total_count}")
        
        # 将真实分布转换为调度器可用的格式
        self._update_scheduler_with_real_distribution()
    
    def _update_scheduler_with_real_distribution(self):
        """根据真实分布更新调度器的目标分布"""
        if not self.real_distribution:
            return
        
        # 从真实分布提取车型分布
        vehicle_dist = self.real_distribution.field_distributions.get("vehicle_type")
        if vehicle_dist:
            # 映射: "1" -> "客车", "2" -> "货车"
            truck_prob = vehicle_dist.value_probs.get("2", 0.5)
            car_prob = vehicle_dist.value_probs.get("1", 0.5)
            self.scheduler.target_vehicle_dist = {"货车": truck_prob, "客车": car_prob}
            print(f"[分布] 车型分布: 货车 {truck_prob:.1%}, 客车 {car_prob:.1%}")
    
    def get_distribution_prompt_injection(self) -> str:
        """获取用于注入LLM的分布约束提示"""
        if self.distribution_constraints:
            return f"\n\n重要：请严格按照以下真实数据分布生成：\n{self.distribution_constraints}"
        return ""
    
    def evaluate_distribution_match(self, generated_samples: List[Dict]):
        """评估生成数据与真实数据的分布匹配度"""
        if not self.real_distribution or not self.dist_evaluator:
            print("[警告] 未加载真实分布，无法评估")
            return
        
        DistributionAnalyzer, _, _ = get_distribution_analyzer()
        analyzer = DistributionAnalyzer()
        
        gen_dist = analyzer.analyze_from_samples(generated_samples)
        self.dist_evaluator.print_comparison_report(self.real_distribution, gen_dist)
    
    def generate_dataset(
        self,
        count: int,
        target_distribution: Dict = None,
        quality_threshold: float = 0.6
    ) -> List[Dict]:
        """
        生成数据集
        
        Args:
            count: 目标数量
            target_distribution: 目标分布
            quality_threshold: 质量阈值，低于此分数的样本将被过滤或增强
        """
        samples = []
        attempts = 0
        max_attempts = count * 2  # 最多尝试2倍数量
        
        print(f"[生成] 目标: {count} 条数据")
        
        while len(samples) < count and attempts < max_attempts:
            attempts += 1
            
            # 1. Dataset-wise: 获取下一个生成条件
            condition = self.scheduler.get_next_condition(target_distribution)
            
            # 2. Sample-wise: 分步生成样本
            try:
                sample = self.decomposer.generate_sample(condition)
            except Exception as e:
                print(f"[警告] 生成失败: {e}")
                continue
            
            # 3. 质量评估
            score = self.quality_controller.calculate_quality_score(sample)
            
            if score.overall < quality_threshold:
                # 4. 标记增强
                sample = self.quality_controller.enhance_labels(sample)
                score = self.quality_controller.calculate_quality_score(sample)
            
            # 5. 过滤或接受
            if score.overall >= quality_threshold * 0.8:  # 增强后仍需满足80%阈值
                samples.append(sample)
                self.scheduler.update_distribution(sample, condition)
                print(f"[进度] {len(samples)}/{count} (质量: {score.overall:.2f})")
            else:
                print(f"[过滤] 样本质量不足: {score.overall:.2f}")
        
        # 6. 评估报告
        self.evaluator.print_report(samples, self.quality_controller)
        
        # 7. 分布一致性评估（如果加载了真实分布）
        if self.real_distribution:
            self.evaluate_distribution_match(samples)
        
        return samples


# ==================== 命令行接口 ====================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='基于大模型的数据生成框架 V2')
    parser.add_argument('--count', type=int, default=5, help='生成数量')
    parser.add_argument('--output', type=str, default=None, help='输出文件')
    parser.add_argument('--truck-ratio', type=float, default=0.6, help='货车比例 (仅在不使用真实分布时生效)')
    parser.add_argument('--use-real-dist', action='store_true', 
                        help='从数据库学习真实数据分布，确保生成数据分布一致')
    parser.add_argument('--eval-only', action='store_true',
                        help='仅评估已有生成数据与真实分布的一致性')
    
    args = parser.parse_args()
    
    # 创建生成器
    generator = LLMDataGeneratorV2(use_real_distribution=args.use_real_dist)
    
    # 确定目标分布
    if args.use_real_dist and generator.real_distribution:
        # 使用从真实数据学习的分布
        target_dist = None  # 调度器会自动使用真实分布
        print("[模式] 使用真实数据分布约束生成")
    else:
        # 使用手动指定的分布
        target_dist = {
            "vehicle": {"货车": args.truck_ratio, "客车": 1 - args.truck_ratio},
            "time": {"早高峰": 0.3, "晚高峰": 0.3, "平峰": 0.3, "深夜": 0.1},
            "scenario": {"正常": 0.85, "超载": 0.1, "异常": 0.05}
        }
        print("[模式] 使用手动指定分布")
    
    samples = generator.generate_dataset(
        count=args.count,
        target_distribution=target_dist
    )
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(samples, f, ensure_ascii=False, indent=2)
        print(f"\n[保存] 数据已保存到 {args.output}")
    else:
        print("\n[样例] 前2条数据:")
        for s in samples[:2]:
            print(json.dumps(s, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
