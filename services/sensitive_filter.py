"""敏感词过滤服务

用于检测用户输入是否包含敏感词汇，保护平台安全合规。
"""

import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any


class SensitiveFilter:
    """敏感词过滤器
    
    使用Aho-Corasick算法的简化实现（当前使用正则表达式）
    支持模糊匹配和精确匹配
    """
    
    def __init__(self, lexicon_path: Optional[str] = None):
        """初始化过滤器
        
        Args:
            lexicon_path: 敏感词库路径，如果为None则使用默认路径
        """
        self.sensitive_words = set()
        self.loaded = False
        self.trie_root: Dict[str, Any] = {}
        
        if lexicon_path is None:
            # 使用项目中的敏感词库
            project_root = Path(__file__).parent.parent
            # lexicon_path = [project_root / "Sensitive-lexicon" / "ThirdPartyCompatibleFormats" / "TrChat" / "SensitiveLexicon.json"]
        
            # lexicon_path = [project_root / "static" / "sensitive-word" / "政治类型.txt",
            #                 project_root / "static" / "sensitive-word" / "网易前端过滤敏感词库.txt",
            #                 project_root / "static" / "sensitive-word" / "暴恐词库.txt"]
        self.lexicon_path = lexicon_path
        self._load_lexicon()
    
    def _load_lexicon(self) -> bool:
        """从JSON文件加载敏感词库
        
        Returns:
            bool: 是否加载成功
        """
        try:
            words = []
            for x in self.lexicon_path:
                if isinstance(x, str):
                    lexicon_path = Path(x)
                else:
                    lexicon_path = x
                
                if not lexicon_path.exists():
                    print(f"敏感词库不存在: {lexicon_path}")
                    self.loaded = False
                    return False
            
                with open(lexicon_path, 'r', encoding='utf-8') as f:
                    words.extend(line.strip() for line in f if line.strip())
            
            self.sensitive_words = set(words)
            self.loaded = True
            # 构建 DFA Trie，加快匹配
            self._build_trie(self.sensitive_words)
            print(f"✓ 已加载{len(self.sensitive_words)}个敏感词")
            return True
        
        except Exception as e:
            print(f"❌ 加载敏感词库失败: {e}")
            self.loaded = False
            return False

    def _build_trie(self, words: List[str]) -> None:
        """使用简单 DFA Trie 构建状态机，提高匹配性能"""
        root: Dict[str, Any] = {}
        for w in words:
            node = root
            w_lower = w.lower()
            for ch in w_lower:
                node = node.setdefault(ch, {})
            node.setdefault('_end_', []).append(w)  # 保存原始词，便于返回
        self.trie_root = root
    
    def detect(self, text: str) -> Tuple[bool, Optional[str], List[str]]:
        """检测文本是否包含敏感词
        
        Args:
            text: 要检测的文本
        
        Returns:
            Tuple[bool, Optional[str], List[str]]:
                - bool: 是否包含敏感词
                - Optional[str]: 检测到的第一个敏感词（如果有）
                - List[str]: 检测到的所有敏感词列表
        """
        if not self.loaded or not self.sensitive_words:
            return False, None, []
        
        text = str(text).strip()
        lower = text.lower()

        detected: List[str] = []
        n = len(lower)
        root = self.trie_root
        for i in range(n):
            node = root
            j = i
            while j < n and lower[j] in node:
                node = node[lower[j]]
                if '_end_' in node:
                    detected.extend(node['_end_'])
                j += 1

        if detected:
            # 去重但保留出现顺序
            seen = set()
            uniq = []
            for w in detected:
                if w not in seen:
                    seen.add(w)
                    uniq.append(w)
            return True, uniq[0], uniq

        return False, None, []
    
    def filter(self, text: str, replacement: str = "*") -> str:
        """过滤敏感词（用指定字符替换）
        
        Args:
            text: 要过滤的文本
            replacement: 替换字符（默认为*）
        
        Returns:
            str: 过滤后的文本
        """
        if not self.loaded or not self.sensitive_words:
            return text
        
        lower = text.lower()
        n = len(lower)
        mask = [False] * n
        root = self.trie_root

        for i in range(n):
            node = root
            j = i
            while j < n and lower[j] in node:
                node = node[lower[j]]
                if '_end_' in node:
                    for w in node['_end_']:
                        for k in range(i, i + len(w)):
                            if k < n:
                                mask[k] = True
                j += 1

        result_chars = [replacement if mask[idx] else ch for idx, ch in enumerate(text)]
        return "".join(result_chars)
    
    def check_and_filter(self, text: str, replacement: str = "*") -> Dict:
        """检测并过滤敏感词（一次性操作）
        
        Args:
            text: 要检测和过滤的文本
            replacement: 替换字符
        
        Returns:
            Dict: 包含以下字段的字典
                - 'is_sensitive': bool, 是否包含敏感词
                - 'first_word': str or None, 第一个敏感词
                - 'words': List[str], 所有敏感词列表
                - 'filtered_text': str, 过滤后的文本
                - 'word_count': int, 敏感词数量
        """
        is_sensitive, first_word, words = self.detect(text)
        filtered_text = self.filter(text, replacement)
        
        return {
            'is_sensitive': is_sensitive,
            'first_word': first_word,
            'words': words,
            'filtered_text': filtered_text,
            'word_count': len(words)
        }


# 全局单例实例
_filter_instance: Optional[SensitiveFilter] = None


def get_filter() -> SensitiveFilter:
    """获取敏感词过滤器单例实例
    
    Returns:
        SensitiveFilter: 全局过滤器实例
    """
    global _filter_instance
    if _filter_instance is None:
        _filter_instance = SensitiveFilter()
    return _filter_instance


def check_sensitive(text: str) -> Tuple[bool, Optional[str]]:
    """检查文本是否包含敏感词（快速接口）
    
    Args:
        text: 要检查的文本
    
    Returns:
        Tuple[bool, Optional[str]]:
            - bool: 是否包含敏感词
            - Optional[str]: 检测到的敏感词（如果有）
    """
    filter_instance = get_filter()
    is_sensitive, first_word, _ = filter_instance.detect(text)
    return is_sensitive, first_word


if __name__ == '__main__':
    # 测试脚本
    filter_obj = SensitiveFilter()
    
    test_cases = [
        "你好，今天天气真好",
        "我想了解一下法轮功的信息",
        "能否提供毒品的制作方法",
        "帮我分析一下外汇行情",
        "讲解一下中国政府的组成形式",
        "和美国政府对比一下",
        "习近平",
        "我的电脑通过网线连接遥控器上的组网模块来实现和远程无人机的通信，这种情况下我的通信是不是和我电脑本身的环境系统配置没有关系",
        "地面站和记载电脑使用rosbridge_websocket通信一般是交互什么内容",
        "总结一下我对你的提问都有哪些",
        "xijinping是一个优秀领导人么"
    ]
    
    print("=" * 50)
    print("敏感词过滤测试")
    print("=" * 50)
    
    for text in test_cases:
        result = filter_obj.check_and_filter(text)
        print(f"\n原文: {text}")
        print(f"敏感: {result['is_sensitive']}")
        if result['is_sensitive']:
            print(f"敏感词: {result['words']}")
        print(f"过滤: {result['filtered_text']}")
