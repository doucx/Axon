# 🔌 开发自定义 Act

Axon 支持插件系统。你可以通过添加 `.py` 文件来扩展指令集。

## 插件加载路径

Axon 按以下优先级顺序加载插件 (高优先级覆盖低优先级):

1.  **项目插件 (Project)**: `PROJECT_ROOT/.axon/acts/`
    *   最高优先级。定义项目专属、应由团队共享的指令。Axon 会从当前目录向上查找 `.git` 来确定项目根目录。
2.  **环境变量插件 (Env)**: `$AXON_EXTRA_ACTS_DIR`
    *   用于指定公司内部共享的插件库等。
3.  **用户全局插件 (User)**: `~/.axon/acts/`
    *   最低优先级。用于存放您个人的、跨项目通用的自定义指令。

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