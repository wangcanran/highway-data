"""
Marshmallow序列化Schema
用于API数据的序列化和验证
"""
from flask_marshmallow import Marshmallow
from marshmallow import fields
from models import Section, TollStation, Gantry, EntranceTransaction, ExitTransaction, GantryTransaction

ma = Marshmallow()


class SectionSchema(ma.SQLAlchemyAutoSchema):
    """路段信息序列化Schema"""
    class Meta:
        model = Section
        load_instance = True
        include_fk = True


class TollStationSchema(ma.SQLAlchemyAutoSchema):
    """收费站信息序列化Schema"""
    class Meta:
        model = TollStation
        load_instance = True
        include_fk = True


class GantrySchema(ma.SQLAlchemyAutoSchema):
    """门架信息序列化Schema"""
    class Meta:
        model = Gantry
        load_instance = True
        include_fk = True


class EntranceTransactionSchema(ma.SQLAlchemyAutoSchema):
    """入口交易记录序列化Schema"""
    class Meta:
        model = EntranceTransaction
        load_instance = True
        include_fk = True


class ExitTransactionSchema(ma.SQLAlchemyAutoSchema):
    """出口交易记录序列化Schema"""
    class Meta:
        model = ExitTransaction
        load_instance = True
        include_fk = True


class GantryTransactionSchema(ma.SQLAlchemyAutoSchema):
    """门架交易记录序列化Schema"""
    class Meta:
        model = GantryTransaction
        load_instance = True
        include_fk = True


# 创建Schema实例
section_schema = SectionSchema()
sections_schema = SectionSchema(many=True)

toll_station_schema = TollStationSchema()
toll_stations_schema = TollStationSchema(many=True)

gantry_schema = GantrySchema()
gantries_schema = GantrySchema(many=True)

entrance_transaction_schema = EntranceTransactionSchema()
entrance_transactions_schema = EntranceTransactionSchema(many=True)

exit_transaction_schema = ExitTransactionSchema()
exit_transactions_schema = ExitTransactionSchema(many=True)

gantry_transaction_schema = GantryTransactionSchema()
gantry_transactions_schema = GantryTransactionSchema(many=True)
