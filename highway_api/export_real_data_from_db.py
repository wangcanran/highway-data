#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从数据库导出真实数据用于Benchmark评估

使用方法：
1. 配置数据库连接信息
2. 运行脚本导出数据：
   python export_real_data_from_db.py --output real_data.json --limit 100

3. 使用导出的数据进行Benchmark评估：
   python evaluate_generated_data.py --generated generated.json --real real_data.json
"""

import json
import sys
from datetime import datetime

# 数据库连接配置（从config.py导入）
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '051005',
    'database': 'highway_db',
    'charset': 'utf8mb4'
}

# SQL查询（使用实际表名 gantrytransaction）
SAMPLE_QUERY = """
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
WHERE transaction_time >= '2023-01-01'
  AND transaction_time < '2023-12-31'
ORDER BY RAND()
LIMIT %s
"""


def export_from_mysql(limit: int = 100, output_file: str = 'real_data.json'):
    """从MySQL数据库导出真实数据"""
    try:
        import pymysql
    except ImportError:
        print("[ERROR] 缺少 pymysql 库，请安装：pip install pymysql")
        return False
    
    print("\n" + "=" * 70)
    print("从MySQL数据库导出真实数据")
    print("=" * 70)
    
    # 连接数据库
    print(f"\n[步骤1] 连接数据库...")
    print(f"  主机: {DB_CONFIG['host']}")
    print(f"  数据库: {DB_CONFIG['database']}")
    
    try:
        connection = pymysql.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            charset=DB_CONFIG['charset'],
            cursorclass=pymysql.cursors.DictCursor
        )
        print(f"  [OK] 连接成功")
    except Exception as e:
        print(f"  [ERROR] 连接失败: {e}")
        print("\n请检查 DB_CONFIG 配置是否正确")
        return False
    
    # 查询数据
    print(f"\n[步骤2] 查询数据 (限制: {limit} 条)...")
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(SAMPLE_QUERY, (limit,))
            results = cursor.fetchall()
            
            print(f"  [OK] 查询到 {len(results)} 条数据")
            
            if not results:
                print("  [WARNING] 未查询到数据，请检查SQL语句")
                return False
            
    except Exception as e:
        print(f"  [ERROR] 查询失败: {e}")
        print("\n请检查 SAMPLE_QUERY 是否与表结构匹配")
        return False
    finally:
        connection.close()
    
    # 数据转换
    print(f"\n[步骤3] 转换数据格式...")
    samples = []
    
    for row in results:
        # 转换datetime对象为ISO格式字符串
        sample = {}
        for key, value in row.items():
            if isinstance(value, datetime):
                sample[key] = value.isoformat()
            else:
                sample[key] = value
        samples.append(sample)
    
    print(f"  [OK] 转换完成")
    
    # 数据统计
    print(f"\n[步骤4] 数据统计...")
    stats = {
        'total_count': len(samples),
        'vehicle_types': set(),
        'section_ids': set(),
        'date_range': {'min': None, 'max': None}
    }
    
    for sample in samples:
        if 'vehicle_type' in sample:
            stats['vehicle_types'].add(str(sample['vehicle_type']))
        
        if 'section_id' in sample:
            stats['section_ids'].add(sample['section_id'])
        
        if 'transaction_time' in sample:
            time_str = sample['transaction_time']
            if stats['date_range']['min'] is None or time_str < stats['date_range']['min']:
                stats['date_range']['min'] = time_str
            if stats['date_range']['max'] is None or time_str > stats['date_range']['max']:
                stats['date_range']['max'] = time_str
    
    print(f"  总数量: {stats['total_count']} 条")
    print(f"  车型种类: {len(stats['vehicle_types'])} 种")
    print(f"  路段数量: {len(stats['section_ids'])} 个")
    if stats['date_range']['min']:
        print(f"  时间范围: {stats['date_range']['min'][:10]} 至 {stats['date_range']['max'][:10]}")
    
    # 保存文件
    print(f"\n[步骤5] 保存到文件: {output_file}")
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(samples, f, ensure_ascii=False, indent=2)
        
        print(f"  [OK] 保存成功")
        
        # 显示文件大小
        import os
        file_size = os.path.getsize(output_file)
        print(f"  文件大小: {file_size / 1024:.2f} KB")
        
    except Exception as e:
        print(f"  [ERROR] 保存失败: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("数据导出完成！")
    print("\n下一步：使用导出的数据进行Benchmark评估")
    print(f"  python evaluate_generated_data.py --generated generated.json --real {output_file}")
    print("=" * 70)
    
    return True


def export_from_sqlite(db_path: str, limit: int = 100, output_file: str = 'real_data.json'):
    """从SQLite数据库导出真实数据"""
    try:
        import sqlite3
    except ImportError:
        print("[ERROR] SQLite支持不可用")
        return False
    
    print("\n" + "=" * 70)
    print("从SQLite数据库导出真实数据")
    print("=" * 70)
    
    print(f"\n[步骤1] 连接数据库: {db_path}")
    
    try:
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        print(f"  [OK] 连接成功")
    except Exception as e:
        print(f"  [ERROR] 连接失败: {e}")
        return False
    
    # 查询数据（SQLite版本的SQL）
    query = SAMPLE_QUERY.replace('RAND()', 'RANDOM()')
    
    print(f"\n[步骤2] 查询数据 (限制: {limit} 条)...")
    
    try:
        cursor = connection.cursor()
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()
        
        results = [dict(row) for row in rows]
        print(f"  [OK] 查询到 {len(results)} 条数据")
        
        if not results:
            print("  [WARNING] 未查询到数据")
            return False
        
    except Exception as e:
        print(f"  [ERROR] 查询失败: {e}")
        return False
    finally:
        connection.close()
    
    # 保存文件
    print(f"\n[步骤3] 保存到文件: {output_file}")
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"  [OK] 保存成功 ({len(results)} 条)")
    except Exception as e:
        print(f"  [ERROR] 保存失败: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("数据导出完成！")
    print("=" * 70)
    
    return True


def show_sample_data(file_path: str, n: int = 3):
    """显示样本数据"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"\n[预览] 前 {min(n, len(data))} 条数据:")
        print("-" * 70)
        
        for i, sample in enumerate(data[:n], 1):
            print(f"\n样本 {i}:")
            # 只显示关键字段
            key_fields = ['gantry_transaction_id', 'vehicle_type', 'section_id', 
                         'transaction_time', 'pay_fee', 'fee_mileage']
            for field in key_fields:
                if field in sample:
                    print(f"  {field}: {sample[field]}")
        
        print("\n" + "-" * 70)
        
    except Exception as e:
        print(f"[ERROR] 读取文件失败: {e}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='从数据库导出真实数据用于Benchmark评估',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法：

  1. 从MySQL导出100条数据：
     python export_real_data_from_db.py --db mysql --limit 100 --output real_data.json
  
  2. 从SQLite导出数据：
     python export_real_data_from_db.py --db sqlite --db-path data.db --limit 100
  
  3. 导出后预览数据：
     python export_real_data_from_db.py --db mysql --limit 100 --preview

使用前请修改脚本中的 DB_CONFIG 和 SAMPLE_QUERY！
        """
    )
    
    parser.add_argument('--db', '-d',
                       choices=['mysql', 'sqlite'],
                       default='mysql',
                       help='数据库类型 (默认: mysql)')
    
    parser.add_argument('--db-path',
                       help='SQLite数据库文件路径')
    
    parser.add_argument('--limit', '-l',
                       type=int,
                       default=100,
                       help='导出数据条数 (默认: 100)')
    
    parser.add_argument('--output', '-o',
                       default='real_data.json',
                       help='输出文件路径 (默认: real_data.json)')
    
    parser.add_argument('--preview', '-p',
                       action='store_true',
                       help='导出后预览数据')
    
    args = parser.parse_args()
    
    # 导出数据
    success = False
    
    if args.db == 'mysql':
        success = export_from_mysql(args.limit, args.output)
    
    elif args.db == 'sqlite':
        if not args.db_path:
            print("[ERROR] SQLite模式需要指定 --db-path")
            sys.exit(1)
        success = export_from_sqlite(args.db_path, args.limit, args.output)
    
    # 预览数据
    if success and args.preview:
        show_sample_data(args.output)


if __name__ == "__main__":
    main()
