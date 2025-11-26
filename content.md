# feat: 集成 ruff 用于代码格式化

## 用户需求
为了确保项目代码风格的统一性和高质量，需要引入一个现代化的代码格式化与检查工具。`ruff` 是一个优秀的选择，因为它集成了格式化和 linting 功能，并且性能极高。同时，根据开发要求，需要将测试用例中的 `~~~` 语法的指令块统一为 ```` ```` 语法，以提高可读性和一致性。

## 评论
这是一个标准的工程实践，有助于提升开发者体验 (DX) 和项目的长期可维护性。将 `ruff` 集成到开发环境中可以自动化格式问题，让开发者专注于逻辑实现。

## 目标
1.  在项目根目录的 `pyproject.toml` 中添加 `ruff` 的配置。
2.  将 `ruff` 添加到 `dev` 环境的依赖中，通过修改 `bootstrap.py` 实现。
3.  修改所有使用 `~~~` 语法的测试文件，将其统一为 ```` ````。
4.  提供清晰的指令，指导用户如何使用新工具格式化整个代码库。

## 基本原理
通过在 `pyproject.toml` 中定义共享的 `ruff` 规则，我们确保了所有开发者都遵循同一套标准。将 `ruff` 添加到 `bootstrap.py` 的开发环境安装列表中，可以保证 `qd` 环境中始终包含 `ruff` 命令。最后，通过 `replace` 指令批量更新测试文件，完成代码库的风格统一。

此计划修改了项目的构建和测试工具链，但不会直接运行格式化命令。用户在执行此计划后，需要重新生成开发环境，然后手动运行一次格式化，以应用新的代码风格。

## 标签
#comp/build #comp/tests #scope/dx

---

## Script

### Acts 1: 配置 Ruff 并集成到开发环境

首先，我们在根 `pyproject.toml` 文件中定义 `ruff` 的规则，然后修改 `bootstrap.py` 脚本，在创建开发环境时自动安装 `ruff`。

~~~~~act
replace pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 120
target-version = "py38"
select = ["E", "F", "I"] # Pycodestyle Errors, Pyflakes, isort

[tool.ruff.format]
quote-style = "double"
docstring-code-format = true
~~~~~

~~~~~act
replace bootstrap.py
~~~~~
~~~~~python
        pip_cmd = ["uv", "pip", "install", "-p", str(env_path), "pytest", "pytest-cov"]
~~~~~
~~~~~python
        pip_cmd = ["uv", "pip", "install", "-p", str(env_path), "pytest", "pytest-cov", "ruff"]
~~~~~

### Acts 2: 统一测试文件中的指令语法

接下来，我们将几个关键的集成测试文件中的 `~~~` 指令块全部替换为 ```` ````，以保证一致性。

~~~~~act
replace tests/test_idempotent_node.py
~~~~~
~~~~~python
        # 2. 先执行一个会产生变更的操作 (State A)
        plan_1 = "~~~act\nwrite_file a.txt\n~~~\n~~~content\nA\n~~~"
        run_quipu(plan_1, workspace, yolo=True)
        
        # 使用正确的 Engine 设置来验证
        from quipu.cli.factory import create_engine
        engine1 = create_engine(workspace)
        nodes1 = engine1.reader.load_all_nodes()
        assert len(nodes1) >= 1
        
        # 3. 执行一个无变更的操作 (State A -> State A)
        plan_2 = "~~~act\nread_file a.txt\n~~~"
        result = run_quipu(plan_2, workspace, yolo=True)
~~~~~
~~~~~python
        # 2. 先执行一个会产生变更的操作 (State A)
        plan_1 = "```act\nwrite_file a.txt\n```\n```content\nA\n```"
        run_quipu(plan_1, workspace, yolo=True)
        
        # 使用正确的 Engine 设置来验证
        from quipu.cli.factory import create_engine
        engine1 = create_engine(workspace)
        nodes1 = engine1.reader.load_all_nodes()
        assert len(nodes1) >= 1
        
        # 3. 执行一个无变更的操作 (State A -> State A)
        plan_2 = "```act\nread_file a.txt\n```"
        result = run_quipu(plan_2, workspace, yolo=True)
~~~~~

~~~~~act
replace tests/test_integration_v2.py
~~~~~
~~~~~python
        plan = """
~~~act
write_file
~~~
~~~path
hello.txt
~~~
~~~content
Hello Quipu
~~~
"""
        result = run_quipu(content=plan, work_dir=workspace, yolo=True)
~~~~~
~~~~~python
        plan = """
```act
write_file
```
```path
hello.txt
```
```content
Hello Quipu
```
"""
        result = run_quipu(content=plan, work_dir=workspace, yolo=True)
~~~~~

~~~~~act
replace tests/test_integration_v2.py
~~~~~
~~~~~python
        # 试图追加到一个不存在的文件
        plan = """
~~~act
append_file
~~~
~~~path
ghost.txt
~~~
~~~content
boo
~~~
"""
        result = run_quipu(content=plan, work_dir=workspace, yolo=True)
~~~~~
~~~~~python
        # 试图追加到一个不存在的文件
        plan = """
```act
append_file
```
```path
ghost.txt
```
```content
boo
```
"""
        result = run_quipu(content=plan, work_dir=workspace, yolo=True)
~~~~~

~~~~~act
replace tests/test_integration_v2.py
~~~~~
~~~~~python
        plan_file = tmp_path / "plan.md"
        plan_file.write_text("~~~act\nend\n~~~", encoding="utf-8")
~~~~~
~~~~~python
        plan_file = tmp_path / "plan.md"
        plan_file.write_text("```act\nend\n```", encoding="utf-8")
~~~~~

~~~~~act
replace tests/test_integration_v2.py
~~~~~
~~~~~python
        # State A: Create a.txt
        plan_a = "~~~act\nwrite_file a.txt\n~~~\n~~~content\nState A\n~~~"
        run_quipu(content=plan_a, work_dir=workspace, yolo=True)
        
        engine_after_a = create_engine(workspace)
        nodes_after_a = sorted(engine_after_a.reader.load_all_nodes(), key=lambda n: n.timestamp)
        node_a = nodes_after_a[-1]
        hash_a = node_a.output_tree

        # Manually create State B by removing a.txt and adding b.txt
        (workspace / "a.txt").unlink()
        plan_b = "~~~act\nwrite_file b.txt\n~~~\n~~~content\nState B\n~~~"
        run_quipu(content=plan_b, work_dir=workspace, yolo=True)
~~~~~
~~~~~python
        # State A: Create a.txt
        plan_a = "```act\nwrite_file a.txt\n```\n```content\nState A\n```"
        run_quipu(content=plan_a, work_dir=workspace, yolo=True)
        
        engine_after_a = create_engine(workspace)
        nodes_after_a = sorted(engine_after_a.reader.load_all_nodes(), key=lambda n: n.timestamp)
        node_a = nodes_after_a[-1]
        hash_a = node_a.output_tree

        # Manually create State B by removing a.txt and adding b.txt
        (workspace / "a.txt").unlink()
        plan_b = "```act\nwrite_file b.txt\n```\n```content\nState B\n```"
        run_quipu(content=plan_b, work_dir=workspace, yolo=True)
~~~~~

~~~~~act
replace tests/test_storage_integration.py
~~~~~
~~~~~python
# A simple plan that creates one file
PLAN_A = """
~~~act
write_file a.txt
~~~
~~~content
File A content
~~~
"""

# A simple plan that creates a different file
PLAN_B = """
~~~act
write_file b.txt
~~~
~~~content
File B content
~~~
"""
~~~~~
~~~~~python
# A simple plan that creates one file
PLAN_A = """
```act
write_file a.txt
```
```content
File A content
```
"""

# A simple plan that creates a different file
PLAN_B = """
```act
write_file b.txt
```
```content
File B content
```
"""
~~~~~

### Acts 3: 后续步骤说明

此计划已完成对工具链的修改。请按以下步骤应用格式化：

1.  **更新开发环境**:
    运行 `python bootstrap.py promote` 来重建你的 `dev` 和 `stable` 环境。这将会安装 `ruff`。

2.  **激活别名**:
    运行 `source dev_setup.sh` (或 `dev_setup.fish`) 来更新别名。

3.  **格式化代码库**:
    在项目根目录运行 `qd format .`。`ruff` 会自动格式化所有文件。

4.  **检查代码**:
    运行 `qd check .` 来查看是否有 `ruff` 无法自动修复的问题。
