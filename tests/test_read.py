import pytest
import shutil
import logging
from pathlib import Path
from core.executor import Executor, ExecutionError
from acts.read import register_read_acts

class TestReadActs:
    @pytest.fixture(autouse=True)
    def setup_executor(self, executor: Executor):
        """自动为每个测试注册 read acts"""
        register_read_acts(executor)

    def test_search_python_fallback(self, executor: Executor, isolated_vault: Path, caplog, capsys, monkeypatch):
        """
        测试场景: 强制禁用 rg，验证 Python 原生搜索逻辑。
        """
        # 1. Mock shutil.which 返回 None，欺骗 Axon 认为系统没装 rg
        monkeypatch.setattr(shutil, "which", lambda x: None)

        # 2. 准备测试文件
        target_file = isolated_vault / "config.py"
        target_file.write_text('SECRET_KEY = "123456"', encoding='utf-8')
        
        # 干扰文件
        (isolated_vault / "readme.md").write_text("Nothing here", encoding='utf-8')

        # 3. 执行搜索
        caplog.set_level(logging.INFO)
        search_func, _ = executor._acts['search_files']
        search_func(executor, ["SECRET_KEY"])

        # 4. 断言
        # 日志中断言执行路径
        assert "Using Python native search" in caplog.text
        
        # STDOUT 中断言结果内容
        captured = capsys.readouterr()
        assert "config.py" in captured.out
        assert 'SECRET_KEY = "123456"' in captured.out

    @pytest.mark.skipif(not shutil.which("rg"), reason="Ripgrep (rg) 未安装，跳过集成测试")
    def test_search_with_ripgrep(self, executor: Executor, isolated_vault: Path, caplog, capsys):
        """
        测试场景: 系统存在 rg 时，验证 ripgrep 调用路径。
        """
        # 1. 准备测试文件
        (isolated_vault / "main.rs").write_text('fn main() { println!("Hello Axon"); }', encoding='utf-8')

        # 2. 执行搜索
        caplog.set_level(logging.INFO)
        search_func, _ = executor._acts['search_files']
        search_func(executor, ['println!'])

        # 3. 断言
        assert "Using 'rg' (ripgrep)" in caplog.text
        
        # 结果应在 STDOUT
        captured = capsys.readouterr()
        assert "main.rs" in captured.out
        assert 'println!("Hello Axon")' in captured.out

    def test_search_scoped_path(self, executor: Executor, isolated_vault: Path, caplog, capsys, monkeypatch):
        """
        测试场景: 指定搜索特定子目录 (CLI参数风格 --path)。
        """
        monkeypatch.setattr(shutil, "which", lambda x: None) # 保持一致性使用 Python 搜索

        # 1. 准备目录结构
        # root/target.txt (不应被搜到)
        # root/src/target.txt (应该被搜到)
        (isolated_vault / "target.txt").write_text("target_function", encoding='utf-8')
        
        src_dir = isolated_vault / "src"
        src_dir.mkdir()
        (src_dir / "inner.txt").write_text("target_function", encoding='utf-8')

        # 2. 执行搜索：限制在 src 目录下 (使用 --path 参数)
        caplog.set_level(logging.INFO)
        search_func, _ = executor._acts['search_files']
        search_func(executor, ["target_function", "--path", "src"])

        # 3. 断言
        captured = capsys.readouterr()
        stdout = captured.out
        
        assert "src/inner.txt" in stdout or str(Path("src/inner.txt")) in stdout
        
        # 验证根目录下的文件路径不应该出现在结果中
        root_target = isolated_vault / "target.txt"
        assert str(root_target) not in stdout

    def test_search_no_match(self, executor: Executor, isolated_vault: Path, caplog, monkeypatch):
        """
        测试场景: 搜索不存在的内容。
        """
        monkeypatch.setattr(shutil, "which", lambda x: None)

        (isolated_vault / "file.txt").write_text("some content", encoding='utf-8')

        caplog.set_level(logging.INFO)
        search_func, _ = executor._acts['search_files']
        search_func(executor, ["non_existent_pattern"])

        assert "No matches found" in caplog.text

    def test_search_binary_file_resilience(self, executor: Executor, isolated_vault: Path, caplog, monkeypatch):
        """
        测试场景: Python 搜索应当忽略二进制文件读取错误。
        """
        monkeypatch.setattr(shutil, "which", lambda x: None)

        # 创建一个伪二进制文件 (包含非法 UTF-8 字节)
        binary_file = isolated_vault / "data.bin"
        with open(binary_file, "wb") as f:
            f.write(b'\x80\x81\xff')

        caplog.set_level(logging.INFO)
        search_func, _ = executor._acts['search_files']
        
        # 搜索任意内容，只要不抛出异常 Crash 就算通过
        try:
            search_func(executor, ["pattern"])
        except Exception as e:
            pytest.fail(f"搜索过程因二进制文件崩溃: {e}")
    def test_search_args_error(self, executor: Executor):
        """测试非法参数应抛出 ExecutionError 而非 SystemExit"""
        search_func, _ = executor._acts['search_files']
        
        with pytest.raises(ExecutionError) as exc:
            search_func(executor, ["pattern", "--unknown-flag"])
        
        assert "参数解析错误" in str(exc.value)