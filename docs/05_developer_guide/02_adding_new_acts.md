# 🔌 开发自定义 Act

Axon 支持插件系统。你可以通过添加 `.py` 文件来扩展指令集。

## 插件加载路径

Axon 会按顺序扫描以下路径加载插件：
1.  用户主目录: `~/.axon/acts/`
2.  环境变量: `AXON_EXTRA_ACTS_DIR`
3.  项目目录: `.axon/acts/` (当前工作区)

## 编写规范

创建一个 Python 文件（例如 `my_plugin.py`），并实现 `register` 函数。

```python
from typing import List
from core.executor import Executor, ExecutionError

def register(executor: Executor):
    """注册插件入口"""
    # 参数模式可选: "hybrid", "exclusive", "block_only"
    executor.register("my_hello", _my_hello, arg_mode="hybrid")

def _my_hello(executor: Executor, args: List[str]):
    """
    Act: my_hello
    Args: [name]
    """
    if not args:
        name = "World"
    else:
        name = args[0]
        
    print(f"Hello, {name}!")
```

## 测试插件

在 Markdown 中即可直接调用：

````markdown
~~~act
my_hello AxonUser
~~~
````