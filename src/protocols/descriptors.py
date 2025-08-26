import struct
from utils.logger import logger


class FieldDescriptor:
    """欄位描述器，描述如何解析一個協議欄位"""
    
    def __init__(self, name, size=None, field_type=None):
        self.name = name
        self.size = size
        self.field_type = field_type
    
    def parse(self, data, offset):
        """解析欄位數據，返回解析後的值和下一個偏移位置"""
        raise NotImplementedError("子類必須實現此方法")
        
class FixedField(FieldDescriptor):
    """固定大小的欄位描述器"""
    
    def __init__(self, name, size, field_type, format_char):
        super().__init__(name, size, field_type)
        self.format_char = format_char
        
    def parse(self, data, offset):
        """解析固定大小欄位"""
        if offset + self.size > len(data):
            raise ValueError(f"Data truncated for field {self.name}")
            
        value = struct.unpack(f">{self.format_char}", data[offset:offset+self.size])[0]
        
        # 對字符串類型做特殊處理
        if self.format_char.endswith('s'):
            value = value.decode("utf-8").strip("\x00")
            
        return value, offset + self.size
        
class StringField(FixedField):
    """字符串欄位描述器"""
    
    def __init__(self, name, size):
        super().__init__(name, size, "s", f"{size}s")
        
class IntField(FixedField):
    """整數欄位描述器"""
    
    def __init__(self, name, size=4):
        format_char = {1: 'B', 2: 'H', 4: 'I', 8: 'Q'}[size]
        super().__init__(name, size, format_char, format_char)
        
class FloatStringField(FixedField):
    """浮點數字符串欄位描述器 (如 settle_resp 中的 res)"""
    
    def __init__(self, name, size):
        super().__init__(name, size, "s", f"{size}s")
    
    def parse(self, data, offset):
        string_value, next_offset = super().parse(data, offset)
        try:
            return float(string_value), next_offset
        except ValueError:
            return 0.0, next_offset
            
class JsonField(FieldDescriptor):
    """JSON字符串欄位描述器"""
    
    def __init__(self, name):
        super().__init__(name)
        
    def parse(self, data, offset):
        """解析JSON字符串，一直解析到數據結尾"""
        import json
        
        if offset >= len(data):
            return {}, offset
            
        try:
            # 從offset到結尾的所有數據
            json_bytes = data[offset:]
            json_str = json_bytes.decode("utf-8").rstrip('\x00')
            
            # 嘗試解析為JSON對象
            try:
                json_obj = json.loads(json_str)
                return json_obj, len(data)
            except json.JSONDecodeError:
                return json_str, len(data)
        except Exception as e:
            logger.error(f"Error parsing JSON field: {e}")
            return {}, len(data)
            
class BettingDetailField(FieldDescriptor):
    """下注詳情欄位描述器 (用於 settle_resp)"""
    
    def __init__(self, name, count_field):
        super().__init__(name)
        self.count_field = count_field  # 引用計數欄位的名稱
        
    def parse(self, data, offset, field_values):
        """解析下注詳情列表"""
        count = field_values.get(self.count_field, 0)
        results = []
        current_offset = offset
        
        for _ in range(count):
            if current_offset + 31 > len(data):
                break
                
            # 解析玩法類型 (1 byte)
            playtype = struct.unpack(">B", data[current_offset:current_offset+1])[0]
            current_offset += 1
            
            # 解析輸贏金額 (30 bytes)
            winlose_bytes = struct.unpack(">30s", data[current_offset:current_offset+30])[0]
            current_offset += 30
            winlose_str = winlose_bytes.decode("utf-8").strip("\x00")
            winlose_value = float(winlose_str)
            
            results.append({"playtype": playtype, "winlose": winlose_value})
            
        return results, current_offset

# 協議描述器
class ProtocolDescriptor:
    """協議描述器，描述整個協議的結構"""
    
    def __init__(self, name, fields):
        self.name = name
        self.fields = fields
        
    def parse(self, data):
        """解析協議數據"""
        result = {}
        offset = 0
        
        for field in self.fields:
            if isinstance(field, BettingDetailField):
                # 特殊處理需要引用其他欄位值的欄位
                value, offset = field.parse(data, offset, result)
            else:
                value, offset = field.parse(data, offset)
                
            result[field.name] = value
            
        return result

# 預定義協議描述器
PROTOCOL_DESCRIPTORS = {
    "settle_resp": ProtocolDescriptor("settle_resp", [
        StringField("vid", 4),
        StringField("gmcode", 14),
        IntField("seat", 4),
        FloatStringField("res", 30),
        IntField("count", 1),
        BettingDetailField("detail_items", "count")
    ]),
    
    "game_result": ProtocolDescriptor("game_result", [
        StringField("vid", 4),
        StringField("gmtype", 4),
        JsonField("json")
    ]),
    
    # 可以添加更多協議...
}