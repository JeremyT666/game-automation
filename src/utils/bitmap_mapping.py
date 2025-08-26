def decimal_to_bitmap(decimal_value, bit_length=32):
    """將十進位數字轉換為bitmap
    
    Args:
        decimal_value: 十進位數值
        bit_length: 位元長度，預設32位
        
    Returns:
        str: 二進位字串 (如 "10100011")
    """
    if decimal_value < 0:
        raise ValueError("Decimal value must be non-negative")
    
    # 轉換為二進位並移除 '0b' 前綴
    binary_str = bin(decimal_value)[2:]
    
    # 補齊到指定長度
    return binary_str.zfill(bit_length)

def check_bit(decimal_value, position):
    """檢查指定位置的位元是否為1
    
    Args:
        decimal_value: 十進位數值
        position: 位置 (1-based, 從右開始)
        
    Returns:
        bool: 該位置是否為1
    """
    # << 是左移運算符，將位元向左移動
    return (decimal_value & (1 << (position - 1))) != 0

def extract_bits(decimal_value, start_pos, length):
    """提取指定範圍的位元
    
    Args:
        decimal_value: 十進位數值
        start_pos: 起始位置 (1-based, 從右開始)
        length: 要提取的位元數量
        
    Returns:
        int: 提取出的位元值
    """
    # 創建遮罩
    mask = (1 << length) - 1
    # 右移到起始位置，然後應用遮罩
    return (decimal_value >> (start_pos - 1)) & mask

class BitmapParser:
    """bitmap解析器"""
    
    def __init__(self, decimal_value):
        self.decimal_value = decimal_value
        self.binary_str = decimal_to_bitmap(decimal_value)
    
    def get_bit(self, position):
        """獲取指定位置的位元值"""
        return check_bit(self.decimal_value, position)
    
    def get_bits(self, start_pos, length):
        """獲取指定範圍的位元值"""
        return extract_bits(self.decimal_value, start_pos, length)
    
    def parse(self):
        """解析bitmap數據，子類必須實現此方法"""
        raise NotImplementedError("Subclasses must implement parse method")