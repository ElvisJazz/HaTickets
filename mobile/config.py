# -*- coding: UTF-8 -*-
"""
__Author__ = "WECENG"
__Version__ = "1.0.0"
__Description__ = "配置类"
__Created__ = 2023/10/27 09:54
"""
import json
import re


def _strip_jsonc_comments(text):
    """移除 JSONC 文件中的 // 和 /* */ 注释"""
    # 移除单行注释（不在字符串内的 //）
    text = re.sub(r'(?<!:)//.*?$', '', text, flags=re.MULTILINE)
    # 移除多行注释
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    return text


class Config:
    def __init__(self, server_url, keyword, users, city, date, price, price_index, if_commit_order):
        self.server_url = server_url
        self.keyword = keyword
        self.users = users
        self.city = city
        self.date = date
        self.price = price
        self.price_index = price_index
        self.if_commit_order = if_commit_order

    @staticmethod
    def load_config():
        try:
            with open('config.jsonc', 'r', encoding='utf-8') as config_file:
                raw_text = config_file.read()
        except FileNotFoundError:
            raise FileNotFoundError("配置文件 config.jsonc 未找到，请确认文件存在")

        try:
            config = json.loads(_strip_jsonc_comments(raw_text))
        except json.JSONDecodeError as e:
            raise ValueError(f"配置文件格式错误: {e}")

        required_keys = ['server_url', 'keyword', 'users', 'city', 'date', 'price', 'price_index', 'if_commit_order']
        missing = [k for k in required_keys if k not in config]
        if missing:
            raise KeyError(f"配置文件缺少必需字段: {', '.join(missing)}")

        return Config(config['server_url'],
                      config['keyword'],
                      config['users'],
                      config['city'],
                      config['date'],
                      config['price'],
                      config['price_index'],
                      config['if_commit_order'])