"""DGM门架数据生成器

基于DGM(Deep Generative Model)框架的高速公路门架交易数据生成器

完整实现三阶段框架：
- Generation（生成阶段）
- Curation（策展阶段）  
- Evaluation（评估阶段）

使用方法：
    from dgm_generator import DGMGantryGenerator
    
    generator = DGMGantryGenerator()
    generator.load_real_samples(limit=300, evaluation_limit=1000)
    result = generator.generate(count=50)

或命令行：
    python dgm_gantry_generator.py --count 50 --output data.json
"""

__version__ = "1.0.0"
__author__ = "DGM Generator Team"
