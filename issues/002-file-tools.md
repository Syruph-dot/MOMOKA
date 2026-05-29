# Issue #2: 文件读写工具

## 类型
AFK

## 阻塞
- #1 项目骨架

## 目标

实现文件读取、写入、列表、追加四个工具，注册到 Agent。

## 验收标准

- [ ] `tools/file_reader.py` — `read_file(path)` 读取文本文件内容
- [ ] `tools/file_writer.py` — `write_file(path, content)` 写入文本文件
- [ ] `tools/file_lister.py` — `list_files(directory)` 列出目录文件
- [ ] `tools/file_appender.py` — `append_file(path, content)` 追加内容到文件
- [ ] 所有工具注册到 Agent
- [ ] `python file_agent.py "读取 test.txt 并写入 copy.txt"` 正常工作

## 阻塞
- #1
