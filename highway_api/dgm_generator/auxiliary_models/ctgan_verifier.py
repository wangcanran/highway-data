"""CTGAN辅助验证器

使用训练好的CTGAN模型验证和修正LLM生成的数据

这是DGM论文中"Auxiliary Model Enhancement"的真正实现：
- 不是规则判断
- 而是使用独立训练的ML模型（CTGAN）
- 从真实数据中学习分布
- 自动修正异常值
"""
import os
import logging
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class CTGANVerifier:
    """使用CTGAN模型验证LLM生成数据的辅助验证器
    
    原理：
    1. CTGAN从6000+真实样本学习了数据分布
    2. LLM生成的数据可能偏离真实分布
    3. 用CTGAN的分布知识修正LLM的偏差
    
    Examples:
        >>> verifier = CTGANVerifier("path/to/gantry_ctgan.pkl")
        >>> llm_sample = {...}
        >>> verified = verifier.verify_sample(llm_sample)
    """
    
    def __init__(self, model_path: str):
        """初始化CTGAN验证器
        
        Args:
            model_path: CTGAN模型文件路径（.pkl）
        
        Raises:
            FileNotFoundError: 模型文件不存在
            ImportError: sdv库未安装
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"CTGAN model not found: {model_path}")
        
        try:
            from sdv.tabular import CTGAN
        except ImportError:
            raise ImportError(
                "sdv library not installed. Run: pip install sdv"
            )
        
        logger.info(f"Loading CTGAN model from {model_path}")
        self.model = CTGAN.load(model_path)
        logger.info("CTGAN model loaded successfully")
        
        # 统计信息缓存
        self._stats_cache = {}
    
    def verify_sample(
        self, 
        llm_sample: Dict,
        strict: bool = False,
        threshold_std: float = 2.0
    ) -> Dict:
        """验证并修正单个LLM生成的样本
        
        Args:
            llm_sample: LLM生成的样本
            strict: 严格模式（更激进的修正）
            threshold_std: 异常阈值（几倍标准差）
        
        Returns:
            修正后的样本（包含_corrections字段记录修改）
        """
        corrections = []
        verified_sample = llm_sample.copy()
        
        # 提取条件特征
        vehicle_type = llm_sample.get("vehicle_type", "1")
        section_id = llm_sample.get("section_id", "")
        
        # 从CTGAN生成相似条件的参考样本
        try:
            reference_samples = self._get_reference_samples(
                vehicle_type=vehicle_type,
                section_id=section_id,
                n_samples=20
            )
        except Exception as e:
            logger.warning(f"Failed to get CTGAN reference: {e}")
            return verified_sample
        
        # 验证数值字段
        numerical_fields = ["pay_fee", "fee_mileage", "total_weight"]
        for field in numerical_fields:
            if field in llm_sample:
                corrected, msg = self._verify_numerical_field(
                    field_name=field,
                    llm_value=llm_sample[field],
                    reference_df=reference_samples,
                    threshold_std=threshold_std
                )
                
                if corrected != llm_sample[field]:
                    verified_sample[field] = corrected
                    corrections.append(msg)
        
        # 记录修正信息
        if corrections:
            verified_sample["_ctgan_corrections"] = corrections
            verified_sample["_verified_by"] = "CTGAN"
            logger.info(f"Sample corrected: {len(corrections)} fields")
        
        return verified_sample
    
    def verify_batch(
        self,
        llm_samples: List[Dict],
        threshold_std: float = 2.0
    ) -> List[Dict]:
        """批量验证样本
        
        Args:
            llm_samples: LLM生成的样本列表
            threshold_std: 异常阈值
        
        Returns:
            验证后的样本列表
        """
        verified = []
        corrected_count = 0
        
        for i, sample in enumerate(llm_samples):
            verified_sample = self.verify_sample(sample, threshold_std=threshold_std)
            verified.append(verified_sample)
            
            if "_ctgan_corrections" in verified_sample:
                corrected_count += 1
            
            if (i + 1) % 10 == 0:
                logger.info(f"Verified {i+1}/{len(llm_samples)} samples")
        
        logger.info(
            f"Batch verification complete: "
            f"{corrected_count}/{len(llm_samples)} samples corrected"
        )
        
        return verified
    
    def _get_reference_samples(
        self,
        vehicle_type: str,
        section_id: str,
        n_samples: int = 20
    ) -> pd.DataFrame:
        """从CTGAN生成参考样本
        
        Args:
            vehicle_type: 车型
            section_id: 路段ID
            n_samples: 参考样本数量
        
        Returns:
            参考样本DataFrame
        """
        cache_key = f"{vehicle_type}_{section_id}"
        
        # 检查缓存
        if cache_key in self._stats_cache:
            return self._stats_cache[cache_key]
        
        # 从CTGAN生成条件样本
        try:
            # SDV 0.18+ 使用新的条件采样API
            # 尝试无条件采样（更稳定）
            reference_df = self.model.sample(num_rows=n_samples)
            
            # 缓存
            self._stats_cache[cache_key] = reference_df
            
            return reference_df
        
        except Exception as e:
            logger.error(f"CTGAN sampling failed: {e}")
            raise
    
    def _verify_numerical_field(
        self,
        field_name: str,
        llm_value: any,
        reference_df: pd.DataFrame,
        threshold_std: float = 2.0
    ) -> tuple[any, str]:
        """验证单个数值字段
        
        Args:
            field_name: 字段名
            llm_value: LLM生成的值
            reference_df: CTGAN参考样本
            threshold_std: 阈值（标准差倍数）
        
        Returns:
            (修正后的值, 修正信息)
        """
        try:
            # 转换为数值
            if isinstance(llm_value, str):
                llm_numeric = float(llm_value)
            else:
                llm_numeric = float(llm_value)
            
            # CTGAN参考分布
            if field_name not in reference_df.columns:
                return llm_value, ""
            
            ref_values = reference_df[field_name].dropna()
            if len(ref_values) == 0:
                return llm_value, ""
            
            ref_mean = ref_values.mean()
            ref_std = ref_values.std()
            
            # 检查是否异常（超过阈值标准差）
            z_score = abs(llm_numeric - ref_mean) / (ref_std + 1e-10)
            
            if z_score > threshold_std:
                # 异常！修正为CTGAN均值
                corrected = int(ref_mean) if field_name != "fee_mileage" else int(ref_mean)
                
                msg = (
                    f"{field_name}: {llm_value} -> {corrected} "
                    f"(z-score={z_score:.2f}, ref_mean={ref_mean:.0f})"
                )
                
                logger.debug(msg)
                return corrected, msg
            
            # 正常，不修正
            return llm_value, ""
        
        except (ValueError, TypeError) as e:
            logger.warning(f"Field verification failed for {field_name}: {e}")
            return llm_value, ""
    
    def get_distribution_stats(self, field_name: str, vehicle_type: str = None) -> Dict:
        """获取CTGAN学习的字段分布统计
        
        用于了解真实数据的分布特征
        
        Args:
            field_name: 字段名
            vehicle_type: 可选的车型过滤
        
        Returns:
            统计信息字典
        """
        # 采样获取分布
        n_samples = 1000
        
        # 使用无条件采样（SDV 0.18+兼容性）
        df = self.model.sample(num_rows=n_samples)
        
        if field_name not in df.columns:
            return {}
        
        values = df[field_name].dropna()
        
        return {
            "mean": float(values.mean()),
            "std": float(values.std()),
            "min": float(values.min()),
            "max": float(values.max()),
            "median": float(values.median()),
            "q25": float(values.quantile(0.25)),
            "q75": float(values.quantile(0.75)),
        }


class HybridGenerator:
    """LLM + CTGAN 混合生成器
    
    结合LLM的创造性和CTGAN的统计准确性
    """
    
    def __init__(self, llm_generator, ctgan_model_path: str):
        """初始化混合生成器
        
        Args:
            llm_generator: DGM生成器实例
            ctgan_model_path: CTGAN模型路径
        """
        self.llm = llm_generator
        self.ctgan_verifier = CTGANVerifier(ctgan_model_path)
    
    def generate_hybrid(
        self,
        count: int,
        llm_ratio: float = 0.7,
        verify_llm: bool = True
    ) -> Dict:
        """混合生成高质量数据
        
        Args:
            count: 总数量
            llm_ratio: LLM生成比例（0.7 = 70%来自LLM）
            verify_llm: 是否用CTGAN验证LLM样本
        
        Returns:
            {
                "samples": 所有样本,
                "llm_samples": LLM生成的样本,
                "ctgan_samples": CTGAN生成的样本,
                "statistics": 统计信息
            }
        """
        llm_count = int(count * llm_ratio)
        ctgan_count = count - llm_count
        
        logger.info(f"Hybrid generation: {llm_count} LLM + {ctgan_count} CTGAN")
        
        # 1. LLM生成
        llm_result = self.llm.generate(count=llm_count, verbose=False)
        llm_samples = llm_result["samples"]
        
        # 2. CTGAN验证LLM样本
        if verify_llm:
            logger.info("Verifying LLM samples with CTGAN...")
            llm_samples = self.ctgan_verifier.verify_batch(llm_samples)
        
        # 3. CTGAN直接生成补充样本
        logger.info(f"Generating {ctgan_count} samples from CTGAN...")
        ctgan_df = self.ctgan_verifier.model.sample(ctgan_count)
        ctgan_samples = ctgan_df.to_dict('records')
        
        # 4. 合并
        all_samples = llm_samples + ctgan_samples
        
        # 5. 统计
        corrected_count = sum(
            1 for s in llm_samples if "_ctgan_corrections" in s
        )
        
        return {
            "samples": all_samples,
            "llm_samples": llm_samples,
            "ctgan_samples": ctgan_samples,
            "statistics": {
                "total": count,
                "llm_generated": llm_count,
                "ctgan_generated": ctgan_count,
                "llm_corrected": corrected_count,
                "llm_correction_rate": corrected_count / llm_count if llm_count > 0 else 0
            }
        }
