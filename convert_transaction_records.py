#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
转换成交记录JSON文件中的文本字段为数值格式
处理买卖记录(buy)和租赁记录(rent)
"""

import json
import os
import re
from typing import Dict, Any, Optional
import shutil


class TransactionRecordConverter:
    """成交记录转换器"""
    
    def __init__(self, input_dir: str = 'transaction_records', 
                 output_dir: str = 'transaction_records_trans'):
        """
        初始化转换器
        
        Args:
            input_dir: 输入目录（原始数据）
            output_dir: 输出目录（转换后数据）
        """
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.warnings = []
        
    def extract_number(self, text: str) -> Optional[float]:
        """
        从文本中提取数字（去除逗号等分隔符）
        
        Args:
            text: 输入文本
            
        Returns:
            提取的数字，失败返回None
        """
        if not text or not isinstance(text, str):
            return None
        
        # 移除所有逗号、空格、换行符
        text = text.replace(',', '').replace(' ', '').replace('\n', '').replace('\t', '')
        
        # 尝试提取数字（包括小数点）
        match = re.search(r'[-+]?\d+\.?\d*', text)
        if match:
            try:
                return float(match.group())
            except ValueError:
                return None
        return None
    
    def convert_area(self, area_text: str) -> Optional[int]:
        """
        转换面积文本为数字
        
        Args:
            area_text: 面积文本，如 "實1,199呎", "實498呎"
            
        Returns:
            面积数字（整数），失败返回None
        """
        if not area_text:
            return None
        
        num = self.extract_number(area_text)
        if num is not None:
            return int(num)
        return None
    
    def convert_total_price(self, price_text: str) -> Optional[int]:
        """
        转换总价文本为数字（单位：元）
        
        Args:
            price_text: 价格文本，如 "$4,100 萬元", "$500 萬元"
            
        Returns:
            价格数字（元），失败返回None
        """
        if not price_text:
            return None
        
        num = self.extract_number(price_text)
        if num is None:
            return None
        
        # 检查是否是"萬元"单位
        if '萬' in price_text or '万' in price_text:
            return int(num * 10000)
        else:
            return int(num)
    
    def convert_price_per_sqft(self, price_text: str) -> Optional[int]:
        """
        转换每平方尺价格为数字
        
        Args:
            price_text: 价格文本，如 "$34,195", "$5,000"
            
        Returns:
            价格数字（整数），失败返回None
        """
        if not price_text:
            return None
        
        num = self.extract_number(price_text)
        if num is not None:
            return int(num)
        return None
    
    def convert_profit_loss_rate(self, rate_text: str) -> Optional[float]:
        """
        转换盈利/蝕让率为小数
        
        Args:
            rate_text: 百分比文本，如 "- 7.6%", "+ 5.2%", ""
            
        Returns:
            小数值，失败返回None
        """
        if not rate_text or rate_text.strip() in ['-', '']:
            return None
        
        # 提取数字（包括负号）
        match = re.search(r'([-+]?\s*\d+\.?\d*)', rate_text)
        if match:
            try:
                num_str = match.group(1).replace(' ', '')
                num = float(num_str)
                return round(num / 100.0, 5)
            except ValueError:
                return None
        return None
    
    def convert_total_rent(self, rent_text: str) -> Optional[int]:
        """
        转换租金总价为数字（单位：元）
        
        Args:
            rent_text: 租金文本，如 "租\n $25,000 元", "租 $15,000 元"
            
        Returns:
            租金数字（元），失败返回None
        """
        if not rent_text:
            return None
        
        num = self.extract_number(rent_text)
        if num is not None:
            return int(num)
        return None
    
    def convert_rent_per_sqft(self, rent_text: str) -> Optional[int]:
        """
        转换每平方尺租金为数字
        
        Args:
            rent_text: 租金文本，如 "$50", "$65"
            
        Returns:
            租金数字（整数），失败返回None
        """
        if not rent_text:
            return None
        
        num = self.extract_number(rent_text)
        if num is not None:
            return int(num)
        return None
    
    def convert_buy_transaction(self, transaction: Dict) -> Dict:
        """
        转换单条买卖记录
        
        Args:
            transaction: 原始交易记录字典
            
        Returns:
            转换后的交易记录字典
        """
        converted = transaction.copy()
        
        # 转换面积
        if 'area' in transaction:
            area = self.convert_area(transaction['area'])
            if area is not None:
                converted['area'] = area
                converted['area_text'] = transaction['area']  # 保留原始文本
            else:
                self.warnings.append(f"无法转换面积: {transaction.get('area')}")
        
        # 转换总价
        if 'total_price' in transaction:
            price = self.convert_total_price(transaction['total_price'])
            if price is not None:
                converted['total_price'] = price
                converted['total_price_text'] = transaction['total_price']  # 保留原始文本
            else:
                self.warnings.append(f"无法转换总价: {transaction.get('total_price')}")
        
        # 转换尺价
        if 'price_per_sqft' in transaction:
            price_sqft = self.convert_price_per_sqft(transaction['price_per_sqft'])
            if price_sqft is not None:
                converted['price_per_sqft'] = price_sqft
                converted['price_per_sqft_text'] = transaction['price_per_sqft']  # 保留原始文本
            else:
                self.warnings.append(f"无法转换尺价: {transaction.get('price_per_sqft')}")
        
        # 转换盈利/蝕让率
        if 'profit_loss_rate' in transaction:
            rate = self.convert_profit_loss_rate(transaction['profit_loss_rate'])
            if rate is not None:
                converted['profit_loss_rate'] = rate
                converted['profit_loss_rate_text'] = transaction['profit_loss_rate']  # 保留原始文本
        
        return converted
    
    def convert_rent_transaction(self, transaction: Dict) -> Dict:
        """
        转换单条租赁记录
        
        Args:
            transaction: 原始交易记录字典
            
        Returns:
            转换后的交易记录字典
        """
        converted = transaction.copy()
        
        # 转换面积
        if 'area' in transaction:
            area = self.convert_area(transaction['area'])
            if area is not None:
                converted['area'] = area
                converted['area_text'] = transaction['area']  # 保留原始文本
            else:
                self.warnings.append(f"无法转换面积: {transaction.get('area')}")
        
        # 转换租金总价
        if 'total_rent' in transaction:
            rent = self.convert_total_rent(transaction['total_rent'])
            if rent is not None:
                converted['total_rent'] = rent
                converted['total_rent_text'] = transaction['total_rent']  # 保留原始文本
            else:
                self.warnings.append(f"无法转换租金: {transaction.get('total_rent')}")
        
        # 转换租金尺价
        if 'rent_per_sqft' in transaction:
            rent_sqft = self.convert_rent_per_sqft(transaction['rent_per_sqft'])
            if rent_sqft is not None:
                converted['rent_per_sqft'] = rent_sqft
                converted['rent_per_sqft_text'] = transaction['rent_per_sqft']  # 保留原始文本
            else:
                self.warnings.append(f"无法转换租金尺价: {transaction.get('rent_per_sqft')}")
        
        return converted
    
    def process_json_file(self, input_path: str, output_path: str, record_type: str):
        """
        处理单个JSON文件
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            record_type: 记录类型 ('buy' 或 'rent')
        """
        try:
            # 读取JSON文件
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 转换交易记录
            if 'transactions' in data and isinstance(data['transactions'], list):
                converted_transactions = []
                
                for transaction in data['transactions']:
                    if record_type == 'buy':
                        converted = self.convert_buy_transaction(transaction)
                    else:  # rent
                        converted = self.convert_rent_transaction(transaction)
                    converted_transactions.append(converted)
                
                data['transactions'] = converted_transactions
            
            # 创建输出目录
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 保存转换后的JSON
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return True
        
        except Exception as e:
            self.warnings.append(f"处理文件失败 {input_path}: {e}")
            return False
    
    def process_all(self):
        """处理所有文件"""
        print("=" * 70)
        print("成交记录数据转换工具")
        print("=" * 70)
        
        # 处理买卖记录
        buy_input_dir = os.path.join(self.input_dir, 'buy')
        buy_output_dir = os.path.join(self.output_dir, 'buy')
        
        print(f"\n📊 处理买卖记录...")
        print(f"  输入目录: {buy_input_dir}")
        print(f"  输出目录: {buy_output_dir}")
        
        if os.path.exists(buy_input_dir):
            buy_files = [f for f in os.listdir(buy_input_dir) if f.endswith('.json')]
            print(f"  找到 {len(buy_files)} 个文件")
            
            buy_success = 0
            for i, filename in enumerate(buy_files, 1):
                input_path = os.path.join(buy_input_dir, filename)
                output_path = os.path.join(buy_output_dir, filename)
                
                if self.process_json_file(input_path, output_path, 'buy'):
                    buy_success += 1
                
                if i % 100 == 0 or i == len(buy_files):
                    print(f"    进度: {i}/{len(buy_files)} ({i*100//len(buy_files)}%)")
            
            print(f"  ✓ 完成: {buy_success}/{len(buy_files)} 个文件")
        else:
            print(f"  ⚠️  目录不存在: {buy_input_dir}")
        
        # 处理租赁记录
        rent_input_dir = os.path.join(self.input_dir, 'rent')
        rent_output_dir = os.path.join(self.output_dir, 'rent')
        
        print(f"\n📊 处理租赁记录...")
        print(f"  输入目录: {rent_input_dir}")
        print(f"  输出目录: {rent_output_dir}")
        
        if os.path.exists(rent_input_dir):
            rent_files = [f for f in os.listdir(rent_input_dir) if f.endswith('.json')]
            print(f"  找到 {len(rent_files)} 个文件")
            
            rent_success = 0
            for i, filename in enumerate(rent_files, 1):
                input_path = os.path.join(rent_input_dir, filename)
                output_path = os.path.join(rent_output_dir, filename)
                
                if self.process_json_file(input_path, output_path, 'rent'):
                    rent_success += 1
                
                if i % 100 == 0 or i == len(rent_files):
                    print(f"    进度: {i}/{len(rent_files)} ({i*100//len(rent_files)}%)")
            
            print(f"  ✓ 完成: {rent_success}/{len(rent_files)} 个文件")
        else:
            print(f"  ⚠️  目录不存在: {rent_input_dir}")
        
        # 输出警告信息
        if self.warnings:
            print(f"\n⚠️  警告信息 (共{len(self.warnings)}条，显示前10条):")
            for warning in self.warnings[:10]:
                print(f"  - {warning}")
            if len(self.warnings) > 10:
                print(f"  ... 还有 {len(self.warnings) - 10} 条警告")
        
        print("\n" + "=" * 70)
        print("转换完成！")
        print("=" * 70)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='转换成交记录JSON文件格式')
    parser.add_argument('--input', type=str, default='transaction_records',
                       help='输入目录 (默认: transaction_records)')
    parser.add_argument('--output', type=str, default='transaction_records_trans',
                       help='输出目录 (默认: transaction_records_trans)')
    
    args = parser.parse_args()
    
    # 创建转换器并处理
    converter = TransactionRecordConverter(args.input, args.output)
    converter.process_all()


if __name__ == '__main__':
    main()
