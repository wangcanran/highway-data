"""
KACA (K-Anonymity Clustering Algorithm) 实现
基于聚类的k-匿名算法，用于高速公路货车出口交易数据的隐私保护
"""
import numpy as np
from sklearn.cluster import KMeans
from datetime import datetime
from typing import List, Dict, Any, Tuple


class KACAAnonymizer:
    """基于KACA算法的k-匿名处理器"""
    
    def __init__(self, k_value: int = 5):
        """
        初始化KACA匿名器
        
        Args:
            k_value: k-匿名的k值，每个等价类至少包含k条记录
        """
        self.k_value = k_value
    
    def anonymize_exit_transactions(self, records: List[Any]) -> Dict[str, Any]:
        """
        对出口交易记录进行KACA k-匿名处理（记录级输出）。
        
        流程（先聚类，再泛化）：
        1. 特征编码：将准标识符(section_id, exit_time)转为数值特征，仅用于聚类。
        2. K-Means聚类：基于特征相似度分组，形成候选等价类。
        3. 聚类后处理：合并大小 < k 的小聚类到最近的大聚类，确保每类大小≥k。
        4. 自适应泛化：对每个聚类内的原始准标识符进行泛化，得到统一的
           section_region 和 time_period。
        5. 记录级输出：对聚类内的每条记录，删除标识符字段，附加泛化后的
           section_region / time_period，并保留其他非标识符字段（包括敏感字段）。
        
        Args:
            records: 原始交易记录列表（SQLAlchemy模型实例）
            
        Returns:
            {
                'records': [  # 记录级k匿名结果
                    {
                        'section_region': str,
                        'time_period': str,
                        ...  # 其他非标识符字段
                    },
                    ...
                ],
                'suppressed_count': int,   # 被抑制的记录数（来自小于k的聚类）
                'total_records': int,      # 原始记录总数
                'equivalence_classes': int # 等价类（聚类）数量
            }
        """
        if not records:
            return {
                'records': [],
                'suppressed_count': 0,
                'total_records': 0,
                'equivalence_classes': 0
            }
        
        total_records = len(records)
        
        # 步骤1: 特征编码（非泛化，仅为聚类准备数值特征）
        features, record_data = self._extract_features(records)
        
        # 步骤2: K-Means聚类（基于特征相似度分组）
        clusters = self._kaca_clustering(features, total_records)
        
        # 步骤3: 聚类后泛化，并生成记录级输出
        anonymized_records: List[Dict[str, Any]] = []
        suppressed_count = 0
        equivalence_classes = 0
        
        max_cluster_id = max(clusters) if len(clusters) > 0 else -1
        
        for cluster_id in range(max_cluster_id + 1):
            # 获取该聚类的所有记录索引
            cluster_indices = [i for i, c in enumerate(clusters) if c == cluster_id]
            cluster_size = len(cluster_indices)
            
            if cluster_size < self.k_value:
                # 抑制：聚类大小 < k
                suppressed_count += cluster_size
                continue
            
            # 获取聚类中的原始记录数据
            cluster_records = [record_data[i] for i in cluster_indices]
            
            # 基于聚类结果，对原始准标识符进行自适应泛化
            generalized_region, generalized_time = self._generalize_qids(cluster_records)
            equivalence_classes += 1
            
            # 生成记录级输出：对簇内每条记录附加泛化后的QID，并删除标识符字段
            for r in cluster_records:
                anonymized_record: Dict[str, Any] = {}
                
                # 泛化后的准标识符
                anonymized_record['section_region'] = generalized_region
                anonymized_record['time_period'] = generalized_time
                
                # 其它非标识符字段（包括敏感字段）
                # 这里不返回任何显式标识符（如ID、原始section_id/exit_time等）
                # record_data中目前只存了我们手动放入的字段，因此在构建时
                # 需要确保不加入标识符。
                for key, value in r.items():
                    if key in ['section_id', 'exit_time']:
                        continue
                    anonymized_record[key] = value
                
                # 标记k匿名信息
                anonymized_record['k_anonymized'] = True
                anonymized_record['algorithm'] = 'KACA'
                
                anonymized_records.append(anonymized_record)
        
        return {
            'records': anonymized_records,
            'suppressed_count': suppressed_count,
            'total_records': total_records,
            'equivalence_classes': equivalence_classes
        }
    
    def _extract_features(self, records: List[Any]) -> Tuple[np.ndarray, List[Dict]]:
        """
        从交易记录中提取数值特征用于聚类（特征编码，非泛化）
        
        重要：这里只是将准标识符转换为数值特征以便K-Means聚类，
        NOT泛化。真正的泛化发生在聚类完成后。
        
        准标识符特征编码：
        - section_id: 提取所有数字部分转换为整数（保留完整信息）
        - exit_time: 转换为小时数（0-23）和分钟数的组合
        
        Returns:
            (特征矩阵, 原始记录数据列表)
        """
        features = []
        record_data = []
        
        for record in records:
            section_id = record.section_id if getattr(record, 'section_id', None) else ''
            exit_time = getattr(record, 'exit_time', None)
            
            # 特征编码（非泛化）：提取完整数值信息用于聚类
            # 地理特征：提取section_id中的所有数字
            geo_numeric = self._encode_section_id(section_id)
            
            # 时间特征：小时 + 分钟/60（0-23.xx的浮点数）
            hour = exit_time.hour if exit_time else 0
            minute = exit_time.minute if exit_time else 0
            time_numeric = hour + minute / 60.0
            
            # 构建特征向量 [地理编码, 时间编码]
            features.append([geo_numeric, time_numeric])
            
            # 保存完整的原始记录数据（用于聚类后的泛化和记录级输出）
            # 注意：此处可以加入所有希望在匿名结果中保留的字段，
            # 标识符字段(section_id, exit_time)只用于后续泛化，不直接暴露。
            record_dict: Dict[str, Any] = {
                'section_id': section_id,
                'exit_time': exit_time,
            }
            
            # 业务/敏感字段（根据需要保留）
            for attr in [
                'vehicle_class',
                'vehicle_plate_color_id',
                'axis_count',
                'total_limit',
                'total_weight',
                'card_type',
                'pay_type',
                'pay_card_type',
                'toll_money',
                'real_money',
                'card_pay_toll',
                'discount_type',
                'section_name',
            ]:
                if hasattr(record, attr):
                    value = getattr(record, attr)
                    # 金额类字段转float，避免Decimal序列化问题
                    if attr in ['toll_money', 'real_money', 'card_pay_toll'] and value is not None:
                        record_dict[attr] = float(value)
                    else:
                        record_dict[attr] = value
            
            record_data.append(record_dict)
        
        return np.array(features), record_data
    
    def _encode_section_id(self, section_id: str) -> int:
        """
        将路段ID编码为数值特征（特征编码，非泛化）
        
        保留完整数字信息用于聚类，泛化将在聚类后进行
        例如：G5615530120 -> 5615530120
        """
        if not section_id:
            return 0
        
        # 提取所有数字部分，保留完整信息
        numeric_part = ''.join(c for c in section_id if c.isdigit())
        if numeric_part:
            # 限制最大值避免溢出
            return int(numeric_part) % 10000000000  # 保留10位数字
        return 0
    
    def _kaca_clustering(self, features: np.ndarray, total_records: int) -> List[int]:
        """
        KACA聚类算法
        
        策略：
        1. 计算聚类数：n_clusters = max(total_records // k, 1)
        2. 使用K-Means进行初始聚类
        3. 后处理：合并大小 < k 的小聚类到最近的大聚类
        
        Args:
            features: 特征矩阵
            total_records: 总记录数
            
        Returns:
            聚类标签列表
        """
        # 计算初始聚类数
        n_clusters = max(total_records // self.k_value, 1)
        
        if n_clusters == 1:
            # 所有记录归为一个聚类
            return [0] * total_records
        
        # K-Means聚类
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        initial_labels = kmeans.fit_predict(features)
        
        # 后处理：合并小聚类
        final_labels = self._merge_small_clusters(
            features, 
            initial_labels, 
            kmeans.cluster_centers_
        )
        
        return final_labels.tolist()
    
    def _merge_small_clusters(
        self, 
        features: np.ndarray, 
        labels: np.ndarray, 
        centers: np.ndarray
    ) -> np.ndarray:
        """
        合并大小 < k 的小聚类到最近的大聚类
        
        Args:
            features: 特征矩阵
            labels: 初始聚类标签
            centers: 聚类中心
            
        Returns:
            合并后的聚类标签
        """
        merged_labels = labels.copy()
        unique_labels = np.unique(labels)
        
        # 计算每个聚类的大小
        cluster_sizes = {label: np.sum(labels == label) for label in unique_labels}
        
        # 找出小聚类（大小 < k）
        small_clusters = [label for label, size in cluster_sizes.items() if size < self.k_value]
        large_clusters = [label for label, size in cluster_sizes.items() if size >= self.k_value]
        
        if not large_clusters:
            # 没有大聚类，将所有记录归为一个聚类
            return np.zeros_like(labels)
        
        # 合并小聚类
        for small_label in small_clusters:
            # 找到小聚类中的所有记录
            small_indices = np.where(labels == small_label)[0]
            
            # 找到最近的大聚类
            small_center = centers[small_label]
            min_dist = float('inf')
            nearest_large_label = large_clusters[0]
            
            for large_label in large_clusters:
                large_center = centers[large_label]
                dist = np.linalg.norm(small_center - large_center)
                if dist < min_dist:
                    min_dist = dist
                    nearest_large_label = large_label
            
            # 合并到最近的大聚类
            merged_labels[small_indices] = nearest_large_label
        
        return merged_labels
    
    def _generalize_qids(self, cluster_records: List[Dict[str, Any]]) -> Tuple[str, str]:
        """
        对聚类内的记录进行准标识符泛化（不做聚合），返回：
        - generalized_region: 泛化后的地区标识
        - generalized_time:   泛化后的时间段描述
        """
        # 地理泛化：提取公共前缀
        section_ids = [r['section_id'] for r in cluster_records if r.get('section_id')]
        generalized_region = self._generalize_geographic(section_ids)
        
        # 时间泛化：确定时段范围
        exit_times = [r['exit_time'] for r in cluster_records if r.get('exit_time')]
        generalized_time = self._generalize_temporal(exit_times)
        
        return generalized_region, generalized_time
    
    def _generalize_geographic(self, section_ids: List[str]) -> str:
        """
        地理泛化：基于聚类内的section_id提取公共区域
        
        策略：
        1. 提取所有section_id的前3位
        2. 如果前3位相同，返回"XXX区域"
        3. 如果不同，返回最常见的前3位 + "等区域"
        """
        if not section_ids:
            return '未知区域'
        
        # 提取前3位
        prefixes = []
        for sid in section_ids:
            if len(sid) >= 4:
                # 提取字母后的前3位数字
                numeric_part = ''.join(c for c in sid if c.isdigit())
                if len(numeric_part) >= 3:
                    prefixes.append(numeric_part[:3])
        
        if not prefixes:
            return '未知区域'
        
        # 统计最常见的前缀
        from collections import Counter
        prefix_counts = Counter(prefixes)
        most_common_prefix = prefix_counts.most_common(1)[0][0]
        
        # 检查是否所有前缀相同
        if len(prefix_counts) == 1:
            return f"G{most_common_prefix}区域"
        else:
            return f"G{most_common_prefix}等区域"
    
    def _generalize_temporal(self, exit_times: List[datetime]) -> str:
        """
        时间泛化：基于聚类内的exit_time确定时段
        
        策略：
        1. 提取所有小时
        2. 计算小时范围（最小-最大）
        3. 返回时段描述
        """
        if not exit_times:
            return '未知时段'
        
        # 提取小时
        hours = [t.hour for t in exit_times]
        min_hour = min(hours)
        max_hour = max(hours)
        
        # 确定时段范围
        if max_hour - min_hour <= 6:
            # 小范围时段
            if min_hour < 6:
                return '凌晨时段(00-06)'
            elif min_hour < 12:
                return '上午时段(06-12)'
            elif min_hour < 18:
                return '下午时段(12-18)'
            else:
                return '晚上时段(18-24)'
        else:
            # 大范围时段
            return f'时段({min_hour:02d}-{max_hour:02d})'
