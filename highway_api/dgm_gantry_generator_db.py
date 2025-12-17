#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DGM数据生成器 - 数据库增强版

支持直接从数据库加载真实数据，无需先导出JSON文件

使用方法：
1. 使用JSON文件（原方法）：
   generator.load_real_samples("real_data.json")

2. 直接从数据库（新方法）：
   generator.load_real_samples_from_db(limit=100)
"""

from dgm_gantry_generator import DGMGantryGenerator
import pymysql
from typing import List, Dict
import config

class DGMGantryGeneratorDB(DGMGantryGenerator):
    """数据库增强版生成器
    
    继承自DGMGantryGenerator，增加了直接从数据库加载真实数据的功能
    """
    
    def __init__(self, target_distribution: Dict = None, use_advanced_features: bool = True):
        """初始化生成器"""
        # 如果没有指定目标分布，使用默认分布
        if target_distribution is None:
            target_distribution = {
                "vehicle": {"货车": 0.4, "客车": 0.6},
                "time": {"早高峰": 0.25, "晚高峰": 0.25, "平峰": 0.40, "深夜": 0.10},
                "scenario": {"正常": 0.90, "超载": 0.06, "异常": 0.04}
            }
        
        super().__init__(target_distribution, use_advanced_features)
        self.db_config = None
    
    def configure_database(self, db_config: Dict = None):
        """配置数据库连接
        
        Args:
            db_config: 数据库配置字典，如果为None则使用config.py中的配置
        """
        if db_config is None:
            # 使用config.py中的配置
            self.db_config = {
                'host': config.MYSQL_CONFIG['host'],
                'port': config.MYSQL_CONFIG['port'],
                'user': config.MYSQL_CONFIG['user'],
                'password': config.MYSQL_CONFIG['password'],
                'database': config.MYSQL_CONFIG['database'],
                'charset': config.MYSQL_CONFIG['charset']
            }
        else:
            self.db_config = db_config
        
        print(f"[数据库配置] {self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}")
    
    def load_real_samples_from_db(self, 
                                   limit: int = 100, 
                                   section_id: str = None,
                                   start_date: str = None,
                                   end_date: str = None,
                                   verbose: bool = True) -> List[Dict]:
        """直接从数据库加载真实样本数据
        
        Args:
            limit: 加载数据条数
            section_id: 指定路段ID（可选）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            verbose: 是否输出详细信息
            
        Returns:
            加载的真实样本列表
        """
        if not self.db_config:
            self.configure_database()
        
        if verbose:
            print(f"\n[从数据库加载真实数据]")
            print(f"  数据库: {self.db_config['database']}")
            print(f"  限制: {limit} 条")
            if section_id:
                print(f"  路段: {section_id}")
            if start_date or end_date:
                print(f"  时间范围: {start_date} ~ {end_date}")
        
        # 构建SQL查询
        sql = """
        SELECT 
            gantry_transaction_id,
            pass_id,
            gantry_id,
            section_id,
            section_name,
            transaction_time,
            entrance_time,
            vehicle_type,
            axle_count,
            total_weight,
            vehicle_sign,
            gantry_type,
            media_type,
            transaction_type,
            pass_state,
            cpu_card_type,
            pay_fee,
            discount_fee,
            fee_mileage
        FROM gantrytransaction
        WHERE 1=1
        """
        
        params = []
        
        # 添加过滤条件
        if section_id:
            sql += " AND section_id = %s"
            params.append(section_id)
        
        if start_date:
            sql += " AND transaction_time >= %s"
            params.append(start_date)
        
        if end_date:
            sql += " AND transaction_time <= %s"
            params.append(end_date)
        
        sql += " ORDER BY RAND() LIMIT %s"
        params.append(limit)
        
        # 连接数据库并查询
        try:
            connection = pymysql.connect(**self.db_config)
            
            if verbose:
                print(f"  [连接] 数据库连接成功")
            
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(sql, params)
                results = cursor.fetchall()
                
                if verbose:
                    print(f"  [查询] 获取到 {len(results)} 条数据")
                
                # 转换datetime对象为ISO格式字符串
                samples = []
                for row in results:
                    sample = {}
                    for key, value in row.items():
                        if hasattr(value, 'isoformat'):  # datetime对象
                            sample[key] = value.isoformat()
                        else:
                            sample[key] = value
                    samples.append(sample)
                
        except Exception as e:
            if verbose:
                print(f"  [错误] 数据库查询失败: {e}")
            return []
        finally:
            connection.close()
        
        # 使用查询到的数据
        if samples:
            # 1. 作为生成示例
            self.demo_manager.samples = samples[:10]  # 使用前10条作为示例
            
            # 2. 学习路段-日期映射
            self.section_date_mapper.learn_from_samples(samples, verbose=verbose)
            
            # 3. 加载到Benchmark评估器
            self.benchmark_evaluator.load_real_samples(samples)
            
            # 4. 从真实数据学习目标分布（可选，更贴近真实数据）
            learned_dist = self._learn_distribution_from_samples(samples)
            if learned_dist and verbose:
                print(f"  [学习] 从真实数据中学到的分布:")
                if "vehicle" in learned_dist:
                    print(f"    - 车型分布: {learned_dist['vehicle']}")
                if "time" in learned_dist:
                    print(f"    - 时段分布: {learned_dist['time']}")
                if "statistics" in learned_dist:
                    stats = learned_dist['statistics']
                    if "pay_fee" in stats:
                        fee = stats['pay_fee']
                        print(f"    - 费用范围: {fee['min']}~{fee['max']}分 (均值:{fee['mean']}分)")
                    if "fee_mileage" in stats:
                        mile = stats['fee_mileage']
                        print(f"    - 里程范围: {mile['min']}~{mile['max']}米 (均值:{mile['mean']}米)")
                # 更新目标分布
                self.target_distribution.update(learned_dist)
            
            if verbose:
                print(f"  [完成] 真实数据已加载并应用到:")
                print(f"    - 生成示例: {len(self.demo_manager.samples)} 条")
                print(f"    - 路段映射: {len(self.section_date_mapper.section_dates)} 个路段")
                print(f"    - Benchmark基准: {len(samples)} 条")
                print(f"    - 目标分布: 已根据真实数据更新")
        
        return samples
    
    def _learn_distribution_from_samples(self, samples: List[Dict]) -> Dict:
        """从真实样本中学习分布
        
        Args:
            samples: 真实样本列表
            
        Returns:
            学习到的分布字典
        """
        from collections import Counter
        from datetime import datetime
        import numpy as np
        
        dist = {}
        
        # 1. 学习车型分布
        vehicle_types = []
        for s in samples:
            vtype = s.get("vehicle_type", "")
            if vtype:
                # 判断是客车还是货车
                vtype_str = str(vtype)
                if vtype_str in ["0", "1", "2", "3", "4", "5"]:
                    vehicle_types.append("客车")
                else:
                    vehicle_types.append("货车")
        
        if vehicle_types:
            counter = Counter(vehicle_types)
            total = len(vehicle_types)
            dist["vehicle"] = {k: round(v/total, 2) for k, v in counter.items()}
        
        # 2. 学习时段分布
        time_periods = []
        for s in samples:
            time_str = s.get("transaction_time", "")
            if time_str:
                try:
                    # 解析时间
                    if isinstance(time_str, str):
                        dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    else:
                        dt = time_str
                    
                    hour = dt.hour
                    # 分类时段
                    if 7 <= hour < 9:
                        time_periods.append("早高峰")
                    elif 17 <= hour < 19:
                        time_periods.append("晚高峰")
                    elif 0 <= hour < 6:
                        time_periods.append("深夜")
                    else:
                        time_periods.append("平峰")
                except:
                    pass
        
        if time_periods:
            counter = Counter(time_periods)
            total = len(time_periods)
            dist["time"] = {k: round(v/total, 2) for k, v in counter.items()}
        
        # 3. 学习费用和里程的统计特征（新增！）
        fees = []
        mileages = []
        for s in samples:
            if s.get("pay_fee"):
                try:
                    fees.append(int(s.get("pay_fee")))
                except (ValueError, TypeError):
                    pass
            
            if s.get("fee_mileage"):
                try:
                    val = s.get("fee_mileage")
                    if isinstance(val, str):
                        mileages.append(int(float(val)))
                    else:
                        mileages.append(int(val))
                except (ValueError, TypeError):
                    pass
        
        if fees and mileages:
            dist["statistics"] = {
                "pay_fee": {
                    "mean": int(np.mean(fees)),
                    "std": int(np.std(fees)),
                    "min": int(np.min(fees)),
                    "max": int(np.max(fees))
                },
                "fee_mileage": {
                    "mean": int(np.mean(mileages)),
                    "std": int(np.std(mileages)),
                    "min": int(np.min(mileages)),
                    "max": int(np.max(mileages))
                }
            }
        
        return dist
    
    def generate_with_db_samples(self, 
                                  count: int = 100,
                                  db_sample_limit: int = 100,
                                  section_id: str = None,
                                  verbose: bool = True) -> Dict:
        """一站式：从数据库加载真实数据 + 生成新数据 + Benchmark评估
        
        Args:
            count: 生成数据条数
            db_sample_limit: 从数据库加载的真实数据条数
            section_id: 指定路段（可选）
            verbose: 是否输出详细信息
            
        Returns:
            生成结果（包含samples和evaluation）
        """
        print("\n" + "=" * 70)
        print("一站式数据生成与评估（直接使用数据库）")
        print("=" * 70)
        
        # 步骤1：从数据库加载真实数据
        print("\n【步骤1】从数据库加载真实样本")
        real_samples = self.load_real_samples_from_db(
            limit=db_sample_limit,
            section_id=section_id,
            verbose=verbose
        )
        
        if not real_samples:
            print("[错误] 未能从数据库加载真实数据")
            return None
        
        # 步骤2：生成新数据
        print("\n【步骤2】基于真实数据生成新样本")
        result = self.generate(count=count, verbose=verbose)
        
        # 步骤3：Benchmark评估已自动完成（在generate中）
        print("\n【步骤3】评估完成")
        
        # 注意：按照标准分类，benchmark现在在 indirect.benchmark_evaluation 下
        if 'evaluation' in result and 'indirect' in result['evaluation']:
            indirect = result['evaluation']['indirect']
            if 'benchmark_evaluation' in indirect and indirect['benchmark_evaluation']:
                benchmark = indirect['benchmark_evaluation']
                print(f"\n[OK] Benchmark相似度: {benchmark['overall_similarity']:.2%}")
                print(f"  - 分布相似度: {benchmark['distribution_similarity']['score']:.2%}")
                print(f"  - 统计特征相似度: {benchmark['statistical_similarity']['score']:.2%}")
                print(f"  - 时间模式相似度: {benchmark['temporal_similarity']['score']:.2%}")
                print(f"  - 相关性相似度: {benchmark['correlation_similarity']['score']:.2%}")
        
        print("\n" + "=" * 70)
        
        return result


def example_usage():
    """使用示例"""
    print("=" * 70)
    print("DGM数据生成器 - 数据库增强版示例")
    print("=" * 70)
    
    # 方法1：使用默认配置（从config.py读取）
    print("\n[方法1] 使用默认数据库配置")
    generator = DGMGantryGeneratorDB()
    
    # 直接从数据库生成
    result = generator.generate_with_db_samples(
        count=50,              # 生成50条
        db_sample_limit=100,   # 从数据库加载100条真实数据作为基准
        verbose=True
    )
    
    # 方法2：指定路段
    print("\n\n[方法2] 指定路段生成")
    generator2 = DGMGantryGeneratorDB()
    result2 = generator2.generate_with_db_samples(
        count=30,
        db_sample_limit=50,
        section_id="S0010530010",  # 只使用这个路段的真实数据
        verbose=True
    )
    
    # 方法3：分步操作
    print("\n\n[方法3] 分步操作（更灵活）")
    generator3 = DGMGantryGeneratorDB()
    
    # 第1步：配置数据库（可选，不配置则使用config.py）
    generator3.configure_database()
    
    # 第2步：加载真实数据
    real_samples = generator3.load_real_samples_from_db(
        limit=100,
        start_date='2023-01-01',
        end_date='2023-12-31',
        verbose=True
    )
    
    # 第3步：生成数据
    result3 = generator3.generate(count=50, verbose=True)
    
    # 第4步：查看Benchmark评估结果
    if 'evaluation' in result3 and 'indirect' in result3['evaluation']:
        indirect = result3['evaluation']['indirect']
        if 'benchmark_evaluation' in indirect and indirect['benchmark_evaluation']:
            print("\nBenchmark评估结果:")
            print(f"整体相似度: {indirect['benchmark_evaluation']['overall_similarity']:.2%}")
    
    print("\n" + "=" * 70)
    print("示例完成！")
    print("=" * 70)


if __name__ == "__main__":
    example_usage()
