"""
Marshmallow序列化Schema
用于API数据的序列化和验证
"""
from flask_marshmallow import Marshmallow
from marshmallow import fields, Schema
from models import Section, TollStation, Gantry, EntranceTransaction, ExitTransaction, GantryTransaction
import json

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

class AuditLogSchema(Schema):
    """审计日志序列化器"""
    id = fields.Int(dump_only=True)
    operation_type = fields.Str()
    api_endpoint = fields.Str()
    http_method = fields.Str()
    
    # 使用Method字段处理JSON字符串到Dict的转换
    request_params = fields.Method("get_request_params")
    request_body = fields.Method("get_request_body")
    request_headers = fields.Method("get_request_headers")
    
    response_status = fields.Int()
    response_body = fields.Method("get_response_body")
    response_time_ms = fields.Int()
    
    user_id = fields.Str(allow_none=True)
    session_id = fields.Str(allow_none=True)
    user_agent = fields.Str()
    
    client_ip = fields.Str()
    server_ip = fields.Str()
    trace_id = fields.Str()
    parent_trace_id = fields.Str(allow_none=True)
    
    created_at = fields.DateTime()
    ended_at = fields.DateTime(allow_none=True)
    
    is_success = fields.Boolean()
    error_message = fields.Str(allow_none=True)
    
    def _safe_json_load(self, value):
        """安全地将JSON字符串转换为dict"""
        if value is None:
            return None
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return {"_raw": value}
        return {"_raw": str(value)}
    
    def get_request_params(self, obj):
        return self._safe_json_load(getattr(obj, 'request_params', None))
    
    def get_request_body(self, obj):
        return self._safe_json_load(getattr(obj, 'request_body', None))
    
    def get_request_headers(self, obj):
        return self._safe_json_load(getattr(obj, 'request_headers', None))
    
    def get_response_body(self, obj):
        return self._safe_json_load(getattr(obj, 'response_body', None))


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

audit_log_schema = AuditLogSchema()
audit_logs_schema = AuditLogSchema(many=True)