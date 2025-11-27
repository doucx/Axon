好的。现在为 `ConfigManager` 的读写功能添加单元测试。

这是一个很好的步骤，可以确保配置层的健壮性，为后续依赖它的 `sync` 功能打下坚实的基础。

## test: 为 ConfigManager 增加单元测试

### 用户需求
为了确保 `ConfigManager` 的写入能力 (`set` 和 `save` 方法) 的正确性和可靠性，需要为其编写一套完整的单元测试。

### 评论
对 `ConfigManager` 进行单元测试是保障系统稳定性的关键步骤，尤其是在它现在负责文件 I/O 的情况下。通过使用 `pytest` 的 `tmp_path` 夹具，我们可以在一个隔离的环境中精确地验证其加载、修改和保存配置的全部逻辑，有效防止未来的代码变更引入回归错误。

### 目标
1.  在 `tests/engine/test_config.py` 文件中增加针对配置读写功能的测试用例。
2.  验证 `ConfigManager` 在配置文件不存在时能否正确返回默认值。
3.  验证 `set` 和 `save` 方法能否成功创建并写入新的配置值。
4.  验证嵌套键 (例如 `sync.user_id`) 的设置和保存功能。
5.  验证配置的“往返”一致性：保存的配置可以被一个新的 `ConfigManager` 实例正确加载。

### 基本原理
我们将使用 `pytest` 内置的 `tmp_path` 夹具。该夹具为每个测试函数提供一个唯一的临时目录。我们将在这个临时目录中模拟一个项目工作区，动态地创建、写入和读取 `.quipu/config.yml` 文件，从而在一个完全隔离和可控的环境中测试 `ConfigManager` 的所有文件操作和内存操作。

### 标签
#intent/tooling #flow/ready #priority/high 
#comp/engine #comp/tests 
#concept/config 
#scope/dx 
#ai/instruct
#task/domain/sync #task/object/user-identity #task/action/configuration #task/state/continue

---

### Script

#### Acts 1: 编写 ConfigManager 的单元测试

我们将使用 `write_file` 覆盖现有的 `test_config.py` 文件，以确保测试的完整性和一致性。

~~~~~act
write_file
tests/engine/test_config.py
~~~~~
~~~~~python
import yaml
from pathlib import Path
import pytest
from quipu.core.config import ConfigManager

# A pytest fixture to provide a clean work directory for each test
@pytest.fixture
def work_dir(tmp_path: Path) -> Path:
    """Creates a temporary directory to act as a project root."""
    return tmp_path


def test_config_get_defaults(work_dir: Path):
    """Test that default values are returned when no config file exists."""
    config = ConfigManager(work_dir)

    # Test accessing a nested default value
    assert config.get("storage.type") == "git_object"
    # Test a non-existent key with a fallback
    assert config.get("nonexistent.key", "fallback") == "fallback"
    # Test a default that is None
    assert config.get("sync.user_id") is None


def test_config_load_from_file(work_dir: Path):
    """Test loading configuration from an existing config.yml file."""
    config_dir = work_dir / ".quipu"
    config_dir.mkdir()
    config_file = config_dir / "config.yml"
    
    # Create a dummy config file
    dummy_config = {
        "storage": {"type": "sqlite"},
        "sync": {"user_id": "test-user-from-file"}
    }
    with open(config_file, "w") as f:
        yaml.dump(dummy_config, f)

    config = ConfigManager(work_dir)

    # User-defined value should override default
    assert config.get("storage.type") == "sqlite"
    # Value defined in file should be loaded
    assert config.get("sync.user_id") == "test-user-from-file"
    # Default value should still be accessible if not overridden
    assert config.get("sync.remote_name") == "origin"


def test_config_set_and_save(work_dir: Path):
    """Test setting a simple value and saving it to a new file."""
    config = ConfigManager(work_dir)
    
    # Pre-check: value should be default (None)
    assert config.get("sync.user_id") is None

    # Set a new value in memory
    config.set("sync.user_id", "test-user-new")
    assert config.get("sync.user_id") == "test-user-new"

    # Save the configuration to disk
    config.save()

    config_file = work_dir / ".quipu" / "config.yml"
    assert config_file.exists()

    # Verify the content of the saved file
    with open(config_file, "r") as f:
        saved_data = yaml.safe_load(f)
    
    assert saved_data == {"sync": {"user_id": "test-user-new"}}


def test_config_nested_set_and_save(work_dir: Path):
    """Test that setting a nested key creates the necessary dictionaries."""
    config = ConfigManager(work_dir)
    
    config.set("a.b.c", 123)
    config.save()

    # Verify by loading with a new instance
    new_config = ConfigManager(work_dir)
    assert new_config.get("a.b.c") == 123


def test_config_round_trip_consistency(work_dir: Path):
    """
    Test the full cycle: create, set, save, then create a new instance and load.
    """
    # --- Phase 1: Create and save ---
    config1 = ConfigManager(work_dir)
    config1.set("storage.type", "sqlite")
    config1.set("sync.user_id", "round-trip-user")
    config1.set("sync.subscriptions", ["user-a", "user-b"])
    config1.save()

    # --- Phase 2: Load in a new instance and verify ---
    config2 = ConfigManager(work_dir)
    assert config2.get("storage.type") == "sqlite"
    assert config2.get("sync.user_id") == "round-trip-user"
    assert config2.get("sync.subscriptions") == ["user-a", "user-b"]
    # Verify a default value is still accessible
    assert config2.get("sync.remote_name") == "origin"
~~~~~

### 下一步建议
`ConfigManager` 的读写功能现已得到充分测试，我们可以放心地在此基础上继续推进 `sync` 功能的开发。

下一步，我们将执行任务列表中的 **2.2** 和 **2.3**，重构 `HistoryWriter` 和 `HistoryReader`，使其适应 v1.1 架构中新的 Git 引用命名空间。
