# fix: 修正 pytest-cov 配置并恢复测试详细输出

## 用户需求
`pytest-cov` 由于配置错误而未能收集到任何覆盖率数据，同时 `pytest` 的输出因 `-q` 标志而过于简化。你希望修复这两个问题，以便能正确地生成覆盖率报告并看到详细的测试进度。

## 评论
这个问题是由于测试配置 (`pyproject.toml`) 与项目的实际目录结构和导入方式不匹配造成的。`--cov=src` 适用于标准的 `src-layout`，但我们的项目使用了命名空间包，并且 `pythonpath` 指向了更深的目录，因此需要将覆盖率目标明确指向 `quipu` 包。同时，移除 `-q` 标志将改善开发者体验 (DX)，在运行测试时提供更清晰的反馈。

## 目标
1.  修改 `pyproject.toml`，将 `pytest-cov` 的目标从 `--cov=src` 改为 `--cov=quipu`。
2.  从 `pytest` 的 `addopts` 配置中移除 `-q` 标志，以恢复默认的详细测试进度输出。

## 基本原理
通过使 `pytest-cov` 的配置与项目的命名空间包结构保持一致，我们可以确保覆盖率工具能够正确地挂钩 (hook) 到被测试的代码模块。移除 `-q` 标志则是一个简单的配置调整，用于恢复 `pytest` 的标准输出行为，提升开发过程中的透明度。

## 标签
#intent/fix #flow/ready #priority/high
#comp/build #comp/tests
#scope/dx
#ai/instruct
#task/domain/testing #task/object/coverage #task/action/fix
#task/state/continue #task/status/active

---

## Script

### Acts 1: 修正 `pyproject.toml` 中的 `pytest` 配置

我们将一次性更新 `[tool.pytest.ini_options]` 部分，同时修正覆盖率目标并移除 quiet 标志。

~~~~~act
replace pyproject.toml
~~~~~
~~~~~
[tool.pytest.ini_options]
addopts = "-ra -q --cov=src --cov-report=term-missing"
pythonpath = [
  "packages/quipu-interfaces/src",
  "packages/quipu-engine/src",
  "packages/quipu-runtime/src",
  "packages/quipu-cli/src",
]
~~~~~
~~~~~
[tool.pytest.ini_options]
addopts = "-ra --cov=quipu --cov-report=term-missing"
pythonpath = [
  "packages/quipu-interfaces/src",
  "packages/quipu-engine/src",
  "packages/quipu-runtime/src",
  "packages/quipu-cli/src",
]
~~~~~
