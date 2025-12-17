"""
DGM Gantry Generator API Module
提供RESTful接口用于生成高质量的门架交易数据
"""
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional
import logging

# 添加dgm_generator到路径
dgm_path = Path(__file__).parent / "dgm_generator"
if str(dgm_path) not in sys.path:
    sys.path.insert(0, str(dgm_path))

from dgm_gantry_generator import DGMGantryGenerator

logger = logging.getLogger(__name__)


class DGMGeneratorAPI:
    """DGM数据生成器API封装
    
    提供简单的接口用于生成门架交易数据
    """
    
    def __init__(self, use_discriminative: bool = True):
        """初始化DGM生成器
        
        Args:
            use_discriminative: 是否使用判别式模型验证（默认True）
        """
        self.generator = None
        self.use_discriminative = use_discriminative
        self.is_initialized = False
        
    def initialize(self, 
                   real_data_limit: int = 300,
                   evaluation_limit: int = 1000,
                   use_database: bool = True,
                   json_file: Optional[str] = None) -> Dict:
        """初始化生成器（加载真实数据）
        
        Args:
            real_data_limit: 用于学习统计特征的真实数据量
            evaluation_limit: 用于Benchmark评估的真实数据量
            use_database: 是否从数据库加载（默认True）
            json_file: JSON文件路径（use_database=False时使用）
            
        Returns:
            初始化结果
        """
        try:
            logger.info("Initializing DGM Generator...")
            
            # 创建生成器实例
            self.generator = DGMGantryGenerator(use_advanced_features=True)
            
            # 加载真实数据
            if use_database:
                logger.info(f"Loading {real_data_limit} samples from database for training...")
                self.generator.load_real_samples(
                    limit=real_data_limit,
                    evaluation_limit=evaluation_limit,
                    use_database=True
                )
            else:
                if not json_file or not os.path.exists(json_file):
                    raise ValueError(f"JSON file not found: {json_file}")
                logger.info(f"Loading data from JSON file: {json_file}")
                self.generator.load_real_samples(
                    limit=real_data_limit,
                    evaluation_limit=evaluation_limit,
                    use_database=False,
                    json_file=json_file
                )
            
            # 训练判别式模型
            if self.use_discriminative:
                logger.info("Training discriminative models...")
                # 判别式模型会在load_real_samples中自动训练
            
            self.is_initialized = True
            
            return {
                "status": "success",
                "message": "DGM Generator initialized successfully",
                "config": {
                    "training_samples": real_data_limit,
                    "evaluation_samples": evaluation_limit,
                    "use_discriminative": self.use_discriminative,
                    "data_source": "database" if use_database else json_file
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to initialize DGM Generator: {e}")
            return {
                "status": "error",
                "message": f"Initialization failed: {str(e)}"
            }
    
    def generate(self, 
                 count: int = 10,
                 target_distribution: Optional[Dict] = None,
                 verbose: bool = False) -> Dict:
        """生成门架交易数据
        
        Args:
            count: 生成数量
            target_distribution: 目标分布（可选）
            verbose: 是否输出详细日志
            
        Returns:
            生成结果，包含samples和evaluation
        """
        if not self.is_initialized:
            return {
                "status": "error",
                "message": "Generator not initialized. Please call initialize() first.",
                "samples": []
            }
        
        try:
            logger.info(f"Generating {count} samples...")
            
            # 执行生成
            result = self.generator.generate(count=count, verbose=verbose)
            
            # 提取关键信息
            samples = result.get("samples", [])
            evaluation = result.get("evaluation", {})
            
            # 格式化评估结果
            direct_eval = evaluation.get("direct", {})
            indirect_eval = evaluation.get("indirect", {}).get("open_evaluation", {})
            
            return {
                "status": "success",
                "count": len(samples),
                "samples": samples,
                "evaluation": {
                    "direct": {
                        "overall_score": direct_eval.get("overall_score", 0),
                        "faithfulness": direct_eval.get("faithfulness", {}).get("score", 0),
                        "diversity": direct_eval.get("diversity", {}).get("score", 0),
                        "benchmark_similarity": direct_eval.get("faithfulness", {}).get("benchmark_evaluation", {}).get("overall_similarity", 0)
                    },
                    "indirect": {
                        "overall_score": indirect_eval.get("overall", {}).get("score", 0),
                        "tasks": indirect_eval.get("tasks", {})
                    }
                },
                "quality_distribution": result.get("quality_distribution", {})
            }
            
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return {
                "status": "error",
                "message": f"Generation failed: {str(e)}",
                "samples": []
            }
    
    def get_stats(self) -> Dict:
        """获取学习到的统计信息
        
        Returns:
            learned_stats字典
        """
        if not self.is_initialized or not self.generator:
            return {
                "status": "error",
                "message": "Generator not initialized"
            }
        
        return {
            "status": "success",
            "learned_stats": self.generator.learned_stats
        }


# 全局单例实例
_dgm_api_instance = None


def get_dgm_api(use_discriminative: bool = True) -> DGMGeneratorAPI:
    """获取DGM API全局实例（单例模式）
    
    Args:
        use_discriminative: 是否使用判别式模型
        
    Returns:
        DGMGeneratorAPI实例
    """
    global _dgm_api_instance
    
    if _dgm_api_instance is None:
        _dgm_api_instance = DGMGeneratorAPI(use_discriminative=use_discriminative)
    
    return _dgm_api_instance


def generate_dgm_gantry(count: int = 10, 
                        auto_init: bool = True,
                        **kwargs) -> List[Dict]:
    """快捷函数：生成DGM门架数据
    
    Args:
        count: 生成数量
        auto_init: 如果未初始化，是否自动初始化（默认True）
        **kwargs: 其他参数传递给initialize()
        
    Returns:
        生成的样本列表
    """
    api = get_dgm_api()
    
    # 自动初始化
    if not api.is_initialized and auto_init:
        init_result = api.initialize(**kwargs)
        if init_result["status"] != "success":
            logger.error(f"Auto-initialization failed: {init_result['message']}")
            return []
    
    # 生成数据
    result = api.generate(count=count, verbose=False)
    
    if result["status"] == "success":
        return result["samples"]
    else:
        logger.error(f"Generation failed: {result.get('message', 'Unknown error')}")
        return []
