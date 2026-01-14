import os
import shutil
from pathlib import Path


class SkillManager:
    def __init__(self):
        # Locate the directory where this package's built-in skills are stored
        # Assumption: this file is at src/jmcomic_ai/skills/manager.py
        # and resources are at src/jmcomic_ai/skills/jmcomic/
        self.skills_source_dir = Path(__file__).parent / "jmcomic"

    def has_conflicts(self, target_dir: Path) -> bool:
        """Check if any files in source exist in target"""
        if not target_dir.exists():
            return False

        for root, _, files in os.walk(self.skills_source_dir):
            rel_root = Path(root).relative_to(self.skills_source_dir)
            target_root = target_dir / rel_root

            for file in files:
                if (target_root / file).exists():
                    return True
        return False

    def install(self, target_dir: Path, overwrite: bool = False):
        """Install skills to target directory"""
        if not self.skills_source_dir.exists():
            raise FileNotFoundError(f"Source skills directory not found: {self.skills_source_dir}")

        if not target_dir.exists():
            target_dir.mkdir(parents=True, exist_ok=True)

        for root, dirs, files in os.walk(self.skills_source_dir):
            rel_root = Path(root).relative_to(self.skills_source_dir)
            target_root = target_dir / rel_root

            if not target_root.exists():
                target_root.mkdir(parents=True, exist_ok=True)

            for file in files:
                # Skip __pycache__ etc if necessary, though explicit ignore is better
                if file.startswith("__") or file.endswith(".pyc"):
                    continue

                src_file = Path(root) / file
                dst_file = target_root / file

                if dst_file.exists() and not overwrite:
                    print(f"Skipping {dst_file} (exists)")
                    continue

                shutil.copy2(src_file, dst_file)

    def uninstall(self, target_dir: Path):
        """Uninstall skills from target directory"""
        if not target_dir.exists():
            print(f"Directory not found: {target_dir}")
            return

        for root, dirs, files in os.walk(self.skills_source_dir, topdown=False):
            rel_root = Path(root).relative_to(self.skills_source_dir)
            target_root = target_dir / rel_root

            # Delete files
            for file in files:
                if file.startswith("__") or file.endswith(".pyc"):
                    continue

                dst_file = target_root / file
                if dst_file.exists():
                    os.remove(dst_file)
                    print(f"Removed: {dst_file}")

            # Try to remove empty dirs
            if target_root.exists() and not any(target_root.iterdir()):
                try:
                    os.rmdir(target_root)
                    print(f"Removed empty dir: {target_root}")
                except OSError:
                    pass

        # Finally try to remove the target_dir itself if empty
        if target_dir.exists() and not any(target_dir.iterdir()):
            try:
                os.rmdir(target_dir)
                print(f"Removed empty skill dir: {target_dir}")
            except OSError:
                pass
