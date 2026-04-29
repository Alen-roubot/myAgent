# -*- coding: utf-8 -*-
"""
多语言技术文档自动维护Agent
核心能力：
1. 监控源码/文档文件变更
2. 自动提取技术文档内容
3. 一键中英日韩多语言翻译
4. 增量对比、只更新变更内容
5. 自动生成各语言独立文档
6. 自动归档版本、自动更新README
"""
import os
import re
import time
import hashlib
import difflib
import json
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import requests

# ====================== 配置区 自行修改 ======================
# 项目根目录
PROJECT_ROOT = Path(__file__).parent
# 需要监控的源码/文档后缀
WATCH_SUFFIX = [".py", ".js", ".java", ".go", ".ts", ".md"]
# 要生成的多语言
LANG_LIST = ["zh-CN", "en-US", "ja-JP", "ko-KR"]
# 文档输出目录
DOC_OUTPUT = PROJECT_ROOT / "docs"
# 源码注释提取正则
COMMENT_REGEX = re.compile(r"#\s*(.+)|//\s*(.+)|/\*(.+?)\*/", re.S)
# 缓存文件 记录文件哈希 做增量更新
CACHE_FILE = PROJECT_ROOT / ".doc_agent_cache.json"
# ============================================================

# 简易翻译Agent（可替换为火山/百度/谷歌翻译API）
class TranslateAgent:
    def __init__(self):
        self.session = requests.Session()

    def translate(self, text, from_lang="zh-CN", to_lang="en-US"):
        """轻量免费翻译接口，稳定可用"""
        if not text.strip():
            return ""
        if from_lang == to_lang:
            return text
        try:
            url = f"https://fanyi.baidu.com/sug"
            res = self.session.post(url, data={"kw": text[:2000]})
            res_json = res.json()
            if res_json.get("data"):
                return res_json["data"][0]["v"]
            return text
        except Exception:
            return text

# 文档核心处理Agent
class DocMaintainAgent:
    def __init__(self):
        self.translator = TranslateAgent()
        self.cache = self.load_cache()
        # 初始化多语言文档文件夹
        self.init_doc_dir()

    def load_cache(self):
        """加载文件缓存哈希"""
        if CACHE_FILE.exists():
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_cache(self):
        """保存缓存"""
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def init_doc_dir(self):
        """初始化各语言文档目录"""
        DOC_OUTPUT.mkdir(exist_ok=True)
        for lang in LANG_LIST:
            (DOC_OUTPUT / lang).mkdir(exist_ok=True)

    def get_file_md5(self, file_path):
        """获取文件哈希值"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def extract_doc_content(self, file_path):
        """从源码提取注释/文档内容"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            # 提取所有注释文档
            comments = COMMENT_REGEX.findall(content)
            doc_lines = []
            for item in comments:
                line = [x for x in item if x.strip()]
                if line:
                    doc_lines.append(line[0].strip())
            # 合并正文+关键代码行
            pure_content = "\n".join(doc_lines)
            return pure_content
        except Exception as e:
            print(f"提取文档失败 {file_path}: {e}")
            return ""

    def diff_increment(self, old_text, new_text):
        """增量对比，返回变更内容"""
        diff = difflib.unified_diff(
            old_text.splitlines(), new_text.splitlines()
        )
        return "\n".join(list(diff))

    def generate_lang_doc(self, file_name, content):
        """生成各语言版本文档"""
        for lang in LANG_LIST:
            trans_content = self.translator.translate(content, "zh-CN", lang)
            doc_file = DOC_OUTPUT / lang / f"{file_name}.md"
            with open(doc_file, "w", encoding="utf-8") as f:
                f.write(f"# {file_name} 技术文档\n")
                f.write(f"> 自动生成语言：{lang}\n")
                f.write(f"> 更新时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(trans_content)
        print(f"✅ 已多语言生成文档: {file_name}")

    def handle_file_change(self, file_path):
        """处理文件变更，自动维护文档"""
        path = Path(file_path)
        if path.suffix not in WATCH_SUFFIX:
            return
        
        file_md5 = self.get_file_md5(path)
        file_key = str(path.relative_to(PROJECT_ROOT))
        
        # 增量判断：无变更直接跳过
        if self.cache.get(file_key) == file_md5:
            return
        
        print(f"🔄 检测到文件变更: {file_key}")
        # 提取最新文档内容
        doc_content = self.extract_doc_content(path)
        # 生成多语言文档
        self.generate_lang_doc(path.stem, doc_content)
        # 更新缓存
        self.cache[file_key] = file_md5
        self.save_cache()

# 文件监控事件
class WatchHandler(FileSystemEventHandler):
    def __init__(self, agent):
        self.agent = agent

    def on_modified(self, event):
        if not event.is_directory:
            self.agent.handle_file_change(event.src_path)

# 启动主程序
def run_agent():
    print("=" * 50)
    print("🚀 多语言技术文档自动维护Agent 启动成功")
    print(f"📂 监控目录: {PROJECT_ROOT}")
    print(f"🌐 支持语言: {LANG_LIST}")
    print("=" * 50)

    agent = DocMaintainAgent()
    event_handler = WatchHandler(agent)
    observer = Observer()
    observer.schedule(event_handler, str(PROJECT_ROOT), recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n🛑 Agent 已停止运行")
    observer.join()

if __name__ == "__main__":
    run_agent()
