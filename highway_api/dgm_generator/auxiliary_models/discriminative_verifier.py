"""判别式辅助验证器

这是DGM论文中真正要求的"辅助模型"：
- 判别式模型（分类器/回归器）
- 直接预测样本是否合理
- 符合论文P(Y|X)的定义

与CTGAN对比：
- CTGAN: 生成式，学习P(X)，间接验证
- Discriminative: 判别式，学习P(Y|X)，直接预测
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.preprocessing import StandardScaler
import logging

logger = logging.getLogger(__name__)


class ReasonabilityClassifier:
    """合理性分类器
    
    判别式辅助模型 - 直接预测样本是否合理
    这是论文中真正要求的辅助模型类型
    
    原理：
    - 从真实数据学习"合理"样本的特征模式
    - 使用Isolation Forest检测异常（无需标注）
    - 输出明确的合理性判断和置信度
    """
    
    def __init__(self):
        self.model = IsolationForest(
            contamination=0.1,  # 假设10%的样本可能异常
            random_state=42
        )
        self.scaler = StandardScaler()
        self.feature_names = None
    
    def train(self, real_samples: List[Dict]):
        """从真实样本训练判别模型
        
        Args:
            real_samples: 真实样本列表
        """
        logger.info(f"Training discriminative model on {len(real_samples)} samples")
        
        # 提取特征
        X = self._extract_features(real_samples)
        
        # 标准化
        X_scaled = self.scaler.fit_transform(X)
        
        # 训练异常检测器
        self.model.fit(X_scaled)
        
        logger.info("Discriminative model trained successfully")
    
    def predict(self, sample: Dict) -> Tuple[str, float]:
        """预测样本是否合理
        
        Args:
            sample: 待验证样本
        
        Returns:
            (判断结果, 置信度分数)
            - 结果: "reasonable" 或 "anomalous"
            - 分数: -1到1之间，越接近1越正常
        """
        # 提取特征
        X = self._extract_features([sample])
        X_scaled = self.scaler.transform(X)
        
        # 预测 (-1=异常, 1=正常)
        prediction = self.model.predict(X_scaled)[0]
        
        # 异常分数（越负越异常）
        score = self.model.score_samples(X_scaled)[0]
        
        # 转换为置信度 [0, 1]
        confidence = 1 / (1 + np.exp(-score))
        
        if prediction == 1:
            return "reasonable", confidence
        else:
            return "anomalous", confidence
    
    def _extract_features(self, samples: List[Dict]) -> np.ndarray:
        """提取验证特征
        
        特征工程：选择对合理性判断最重要的特征
        """
        features = []
        
        for sample in samples:
            # 数值特征（带数据清洗）
            vehicle_type = int(sample.get("vehicle_type", 1))
            pay_fee = float(sample.get("pay_fee", 0))
            fee_mileage = float(sample.get("fee_mileage", 0))
            
            # 清洗total_weight：移除'kg'等单位
            weight_str = str(sample.get("total_weight", 0))
            weight_str = weight_str.replace('kg', '').replace('KG', '').strip()
            try:
                total_weight = float(weight_str) if weight_str else 0
            except ValueError:
                total_weight = 0
            
            axle_count = int(sample.get("axle_count", 2))
            
            # 派生特征（关键！）
            fee_per_km = pay_fee / (fee_mileage + 1)  # 单位里程费用
            weight_per_axle = total_weight / (axle_count + 1)  # 单轴重量
            
            # 组合特征向量
            feature_vector = [
                vehicle_type,
                pay_fee,
                fee_mileage,
                total_weight,
                axle_count,
                fee_per_km,
                weight_per_axle
            ]
            
            features.append(feature_vector)
        
        self.feature_names = [
            "vehicle_type", "pay_fee", "fee_mileage", 
            "total_weight", "axle_count", 
            "fee_per_km", "weight_per_axle"
        ]
        
        return np.array(features)


class FeeRegressor:
    """费用预测回归器
    
    判别式辅助模型 - 预测合理的费用
    P(fee|vehicle_type, mileage)
    """
    
    def __init__(self):
        from sklearn.ensemble import GradientBoostingRegressor
        self.model = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )
    
    def train(self, real_samples: List[Dict]):
        """训练费用预测模型"""
        X = []
        y = []
        
        for sample in real_samples:
            vehicle_type = int(sample.get("vehicle_type", 1))
            fee_mileage = float(sample.get("fee_mileage", 0))
            pay_fee = float(sample.get("pay_fee", 0))
            
            if fee_mileage > 0 and pay_fee > 0:
                X.append([vehicle_type, fee_mileage])
                y.append(pay_fee)
        
        logger.info(f"Training fee regressor on {len(X)} samples")
        self.model.fit(X, y)
    
    def predict(self, sample: Dict) -> Tuple[float, bool]:
        """预测合理费用
        
        Returns:
            (预测费用, 是否异常)
        """
        vehicle_type = int(sample.get("vehicle_type", 1))
        fee_mileage = float(sample.get("fee_mileage", 0))
        actual_fee = float(sample.get("pay_fee", 0))
        
        # 预测
        predicted_fee = self.model.predict([[vehicle_type, fee_mileage]])[0]
        
        # 判断异常（偏差>50%）
        if actual_fee > 0:
            deviation = abs(actual_fee - predicted_fee) / predicted_fee
            is_anomalous = deviation > 0.5
        else:
            is_anomalous = True
        
        return predicted_fee, is_anomalous


class DiscriminativeVerifier:
    """组合判别式验证器
    
    集成多个判别式辅助模型：
    - 合理性分类器（异常检测）
    - 费用预测回归器
    - 其他特定验证器...
    
    这是论文真正要求的辅助模型架构
    """
    
    def __init__(self):
        self.reasonability = ReasonabilityClassifier()
        self.fee_regressor = FeeRegressor()
        self.trained = False
    
    def train(self, real_samples: List[Dict]):
        """训练所有判别式模型"""
        logger.info("Training discriminative verifiers...")
        
        self.reasonability.train(real_samples)
        self.fee_regressor.train(real_samples)
        
        self.trained = True
        logger.info("All discriminative models trained")
    
    def verify(self, sample: Dict) -> Dict:
        """综合验证样本
        
        Returns:
            {
                "overall": "reasonable" / "anomalous",
                "confidence": 0.85,
                "details": {
                    "reasonability": {...},
                    "fee_prediction": {...}
                }
            }
        """
        if not self.trained:
            raise ValueError("Models not trained yet")
        
        # 1. 合理性判断
        reason_result, reason_conf = self.reasonability.predict(sample)
        
        # 2. 费用预测
        predicted_fee, fee_anomalous = self.fee_regressor.predict(sample)
        
        # 3. 综合判断
        is_anomalous = (
            reason_result == "anomalous" or 
            fee_anomalous
        )
        
        overall_confidence = reason_conf * (0 if fee_anomalous else 1)
        
        return {
            "overall": "anomalous" if is_anomalous else "reasonable",
            "confidence": overall_confidence,
            "details": {
                "reasonability": {
                    "result": reason_result,
                    "confidence": reason_conf
                },
                "fee_prediction": {
                    "predicted": predicted_fee,
                    "actual": sample.get("pay_fee", 0),
                    "anomalous": fee_anomalous
                }
            },
            "corrections": self._suggest_corrections(sample, predicted_fee, fee_anomalous)
        }
    
    def _suggest_corrections(
        self, 
        sample: Dict, 
        predicted_fee: float,
        fee_anomalous: bool
    ) -> List[str]:
        """建议修正"""
        corrections = []
        
        if fee_anomalous:
            corrections.append(
                f"pay_fee: {sample.get('pay_fee')} -> {int(predicted_fee)} "
                f"(predicted by discriminative model)"
            )
        
        return corrections


# ============================================================
# 对比总结：判别式 vs 生成式（CTGAN）
# ============================================================

"""
方法对比：

1. 判别式辅助模型（本文件） ✅ 符合论文
   - 类型: Discriminative Model  
   - 学习: P(Y|X) - 给定特征预测标签
   - 验证: 直接预测是否合理
   - 优点: 理论严谨，预测明确
   - 缺点: 可能需要标注数据

2. CTGAN分布验证（ctgan_verifier.py） ⚠️ 变通方案
   - 类型: Generative Model
   - 学习: P(X) - 数据分布
   - 验证: 间接对比统计距离
   - 优点: 无需标注，更灵活
   - 缺点: 不完全符合论文定义

推荐使用场景：
- 学术严谨: 使用判别式模型
- 工程实用: CTGAN也很有效
- 最佳方案: 两者结合使用
"""
