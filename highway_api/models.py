"""
SQLAlchemy数据库模型
基于MySQL数据库的ORM模型定义
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Section(db.Model):
    """路段信息表"""
    __tablename__ = 'section'
    
    section_id = db.Column(db.String(20), primary_key=True)
    section_name = db.Column(db.String(50))
    
    # 关联关系
    toll_stations = db.relationship('TollStation', backref='section', lazy='dynamic')
    gantries = db.relationship('Gantry', backref='section', lazy='dynamic')
    entrance_transactions = db.relationship('EntranceTransaction', backref='section', lazy='dynamic')
    exit_transactions = db.relationship('ExitTransaction', backref='section', lazy='dynamic')
    
    def __repr__(self):
        return f'<Section {self.section_id}: {self.section_name}>'


class TollStation(db.Model):
    """收费站信息表"""
    __tablename__ = 'tollstation'
    
    toll_station_id = db.Column(db.String(20), primary_key=True)
    station_name = db.Column(db.String(50), nullable=False)
    section_id = db.Column(db.String(20), db.ForeignKey('section.section_id'), nullable=False)
    station_type = db.Column(db.String(10))
    operation_status = db.Column(db.String(10))
    station_code = db.Column(db.String(20))
    station_status = db.Column(db.String(10))
    real_type = db.Column(db.String(10))
    agency_gantry_ids = db.Column(db.String(100))
    gantry_type = db.Column(db.String(10))
    longitude = db.Column(db.Text)
    latitude = db.Column(db.Text)
    
    def __repr__(self):
        return f'<TollStation {self.toll_station_id}: {self.station_name}>'


class Gantry(db.Model):
    """门架信息表"""
    __tablename__ = 'gantry'
    
    gantry_id = db.Column(db.String(20), primary_key=True)
    gantry_name = db.Column(db.String(50), nullable=False)
    section_id = db.Column(db.String(20), db.ForeignKey('section.section_id'), nullable=False)
    gantry_type = db.Column(db.String(10))
    length = db.Column(db.Text)
    gantry_status = db.Column(db.String(10))
    etc_gantry_hex = db.Column(db.String(20))
    boundary_type = db.Column(db.String(10))
    gantry_sign = db.Column(db.String(20))
    is_gantry_type = db.Column(db.String(10))
    lane_count = db.Column(db.String(10))
    lane_gantry = db.Column(db.String(20))
    reetc_gantry_hex = db.Column(db.String(20))
    agency_gantry_ids = db.Column(db.String(100))
    direction = db.Column(db.Text)
    start_station_id = db.Column(db.String(20))
    end_station_id = db.Column(db.String(20))
    neighbor_id = db.Column(db.String(20))
    reverse_id = db.Column(db.String(20))
    
    # 关联关系
    gantry_transactions = db.relationship('GantryTransaction', backref='gantry', lazy='dynamic')
    
    def __repr__(self):
        return f'<Gantry {self.gantry_id}: {self.gantry_name}>'


class EntranceTransaction(db.Model):
    """入口交易记录表"""
    __tablename__ = 'entrancetransaction'
    
    entrance_transaction_id = db.Column(db.String(40), primary_key=True)
    vehicle_class = db.Column(db.String(10))
    entrance_time = db.Column(db.DateTime, nullable=False, index=True)
    vehicle_color_id = db.Column(db.String(10))
    card_type = db.Column(db.String(10))
    pass_id = db.Column(db.String(40), nullable=False, index=True)
    vehicle_sign = db.Column(db.String(10))
    section_id = db.Column(db.String(20), db.ForeignKey('section.section_id'), nullable=False, index=True)
    section_name = db.Column(db.String(50))
    
    def __repr__(self):
        return f'<EntranceTransaction {self.pass_id}>'


class ExitTransaction(db.Model):
    """出口交易记录表"""
    __tablename__ = 'exittransaction'
    
    exit_transaction_id = db.Column(db.String(40), primary_key=True)
    vehicle_class = db.Column(db.String(10))
    exit_time = db.Column(db.DateTime, nullable=False, index=True)
    vehicle_plate_color_id = db.Column(db.String(10))
    axis_count = db.Column(db.String(10))
    total_limit = db.Column(db.String(10))
    total_weight = db.Column(db.String(20))
    card_type = db.Column(db.String(10))
    pay_type = db.Column(db.String(10))
    pay_card_type = db.Column(db.String(10))
    toll_money = db.Column(db.Numeric(10, 2))
    real_money = db.Column(db.Numeric(10, 2))
    card_pay_toll = db.Column(db.Numeric(10, 2))
    discount_type = db.Column(db.String(10))
    section_id = db.Column(db.String(20), db.ForeignKey('section.section_id'), nullable=False, index=True)
    pass_id = db.Column(db.String(40), nullable=False, index=True)
    section_name = db.Column(db.String(50))
    
    def __repr__(self):
        return f'<ExitTransaction {self.pass_id}>'


class GantryTransaction(db.Model):
    """门架交易记录表"""
    __tablename__ = 'gantrytransaction'
    
    gantry_transaction_id = db.Column(db.String(40), primary_key=True)
    gantry_id = db.Column(db.String(20), db.ForeignKey('gantry.gantry_id'), nullable=False, index=True)
    gantry_type = db.Column(db.String(10))
    transaction_time = db.Column(db.DateTime, nullable=False, index=True)
    pay_fee = db.Column(db.Integer)
    fee = db.Column(db.Text)
    discount_fee = db.Column(db.Integer)
    media_type = db.Column(db.String(10))
    vehicle_type = db.Column(db.String(10))
    vehicle_sign = db.Column(db.String(10))
    transaction_type = db.Column(db.String(10))
    pass_state = db.Column(db.String(10))
    entrance_time = db.Column(db.DateTime)
    entrance_lane_type = db.Column(db.String(10))
    pass_id = db.Column(db.String(40), nullable=False, index=True)
    axle_count = db.Column(db.String(10))
    total_weight = db.Column(db.String(20))
    cpu_card_type = db.Column(db.String(10))
    fee_mileage = db.Column(db.String(20))
    fee_prov_begin_hex = db.Column(db.String(20))
    obu_fee_sum_before = db.Column(db.String(20))
    obu_fee_sum_after = db.Column(db.String(20))
    pay_fee_prov_sum_local = db.Column(db.String(20))
    section_id = db.Column(db.String(20), nullable=False, index=True)
    section_name = db.Column(db.String(50))
    
    def __repr__(self):
        return f'<GantryTransaction {self.gantry_transaction_id}: {self.pass_id}>'
