# 🚀 快速上手

## 安装

确保你的环境中有 Python 3.8+ 和 Git。

```bash
# 安装依赖
pip install -r requirements.txt
```

*(注意：正式发布后将支持 `pip install axon-dev`)*

## 第一个 Axon 脚本

创建一个名为 `hello.md` 的文件，写入以下内容：

````markdown
# 我的第一个脚本

我要创建一个 Python 文件。

```act
write_file
```
```path
hello.py
```
```python
print("Hello Axon!")
```
````

## 运行脚本

在终端中执行：

```bash
# 运行脚本（默认交互模式，会询问确认）
python main.py run hello.md

# 使用 YOLO 模式（跳过确认，直接执行）
python main.py run hello.md -y
```

执行后，你会发现当前目录下多了一个 `hello.py` 文件。

## 查看历史

Axon 会自动记录你的操作历史。

```bash
python main.py log
```

你将看到刚才的操作记录。如果需要，你可以随时使用 `checkout` 命令回滚到操作之前的状态。