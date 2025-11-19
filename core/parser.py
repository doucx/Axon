import re
from abc import ABC, abstractmethod
from typing import List, Type
from .types import Statement

class BaseParser(ABC):
    """所有解析器的抽象基类"""
    
    @abstractmethod
    def parse(self, text: str) -> List[Statement]:
        """
        将文本解析为语句列表。
        必须由子类实现。
        """
        pass

class RegexBlockParser(BaseParser):
    """
    基于正则匹配代码块的通用解析器。
    适用于使用成对符号（如 ``` 或 ~~~）包裹的情况。
    """
    def __init__(self, start_fence: str, end_fence: str = None):
        self.start_fence = start_fence
        self.end_fence = end_fence or start_fence
        
        # 构建正则：
        # 1. fence (转义以防特殊字符)
        # 2. (\w+)? -> 语言标记 (group 1)
        # 3. \n    -> 强制换行，确保标记和内容分开
        # 4. (.*?) -> 内容 (group 2)，非贪婪匹配
        # 5. fence -> 结束标记
        s = re.escape(self.start_fence)
        e = re.escape(self.end_fence)
        self.pattern = re.compile(rf"{s}(\w+)?\n(.*?){e}", re.DOTALL)

    def parse(self, text: str) -> List[Statement]:
        matches = self.pattern.findall(text)
        
        statements: List[Statement] = []
        current_statement: Statement | None = None

        for lang, content in matches:
            lang_tag = lang.strip().lower() if lang else ""
            
            if lang_tag == "act":
                # 动词：开始新语句
                action_name = content.strip()
                current_statement = {
                    "act": action_name,
                    "contexts": []
                }
                statements.append(current_statement)
            
            elif lang_tag == "end":
                # 结束符：强制终止当前语句
                current_statement = None
            
            else:
                # 名词 (上下文)
                if current_statement is not None:
                    current_statement["contexts"].append(content)
                else:
                    pass # 忽略游离的块（不在 act 和 end 之间的块）
        
        return statements

class BacktickParser(RegexBlockParser):
    """标准 Markdown 解析器 (```) - 相当于 '绿幕'"""
    def __init__(self):
        super().__init__("```")

class TildeParser(RegexBlockParser):
    """波浪号解析器 (~~~) - 相当于 '蓝幕'"""
    def __init__(self):
        super().__init__("~~~")

# --- 解析器注册表 ---

_PARSERS = {
    "backtick": BacktickParser,
    "tilde": TildeParser,
    # 可以在这里扩展更多，例如 XML 风格的 parser
}

def get_parser(name: str) -> BaseParser:
    """工厂函数：根据名称获取解析器实例"""
    if name not in _PARSERS:
        raise ValueError(f"未知的解析器: {name}. 可用选项: {list(_PARSERS.keys())}")
    return _PARSERS[name]()

def list_parsers() -> List[str]:
    return list(_PARSERS.keys())
