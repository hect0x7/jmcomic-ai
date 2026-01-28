import os
import shutil
from pathlib import Path


class SkillManager:
    def __init__(self):
        # Locate the directory where this package's built-in skills are stored
        # Assumption: this file is at src/jmcomic_ai/skills/manager.py
        # and resources are at src/jmcomic_ai/skills/jmcomic/
        self.skills_source_dir = Path(__file__).parent / "jmcomic"
        self.skill_name: str = self.skills_source_dir.name

    def _get_skill_target_dir(self, target_dir: Path) -> Path:
        return target_dir / self.skill_name

    def _iter_relative_paths(self) -> list[Path]:
        """Iterate through all valid file paths relative to skills_source_dir"""
        results = []
        for root, _, files in os.walk(self.skills_source_dir):
            rel_root = Path(root).relative_to(self.skills_source_dir)
            for file in files:
                if file.startswith("__") or file.endswith(".pyc"):
                    continue
                results.append(rel_root / file)
        return results

    def _list_relative_files(self, base_dir: Path) -> list[str]:
        """List all files in base_dir relative to its parent"""
        parent_name = base_dir.name
        # Note: SkillManager always assumes traversal is relative to skills_source_dir or equivalent structure
        return sorted([str(Path(parent_name) / rel_path) for rel_path in self._iter_relative_paths()])

    def get_install_preview(self, target_dir: Path) -> dict:
        """Return preview info for installation"""
        return {
            "target_dir": target_dir,
            "skill_target_dir": self._get_skill_target_dir(target_dir),
            "files": self._list_relative_files(self.skills_source_dir)
        }

    def get_uninstall_preview(self, target_dir: Path) -> dict:
        """Return preview info for uninstallation"""
        skill_target_dir = self._get_skill_target_dir(target_dir)
        return {
            "target_dir": target_dir,
            "skill_target_dir": skill_target_dir,
            "exists": skill_target_dir.exists(),
            "files": self._list_removable_files(skill_target_dir) if skill_target_dir.exists() else []
        }

    def _list_removable_files(self, skill_target_dir: Path) -> list[str]:
        """List files in skill_target_dir that also exist in skills_source_dir"""
        parent_name = skill_target_dir.name
        results = []
        for rel_path in self._iter_relative_paths():
            if (skill_target_dir / rel_path).exists():
                results.append(str(Path(parent_name) / rel_path))
        return sorted(results)

    def has_conflicts(self, target_dir: Path) -> bool:
        """Check if any files in source exist in target"""
        skill_target_dir = self._get_skill_target_dir(target_dir)
        if not skill_target_dir.exists():
            return False

        for root, _, files in os.walk(self.skills_source_dir):
            rel_root = Path(root).relative_to(self.skills_source_dir)
            target_root = skill_target_dir / rel_root

            for file in files:
                if file.startswith("__") or file.endswith(".pyc"):
                    continue
                if (target_root / file).exists():
                    return True
        return False

    def install(self, target_dir: Path, overwrite: bool = False):
        """Install skills to target directory"""
        if not self.skills_source_dir.exists():
            raise FileNotFoundError(f"Source skills directory not found: {self.skills_source_dir}")

        skill_target_dir = self._get_skill_target_dir(target_dir)
        if not skill_target_dir.exists():
            skill_target_dir.mkdir(parents=True, exist_ok=True)

        for root, dirs, files in os.walk(self.skills_source_dir):
            rel_root = Path(root).relative_to(self.skills_source_dir)
            target_root = skill_target_dir / rel_root

            if not target_root.exists():
                target_root.mkdir(parents=True, exist_ok=True)

            for file in files:
                if file.startswith("__") or file.endswith(".pyc"):
                    continue

                src_file = Path(root) / file
                dst_file = target_root / file

                if dst_file.exists() and not overwrite:
                    print(f"Skipping {dst_file} (exists)")
                    continue

                shutil.copy2(src_file, dst_file)

    def uninstall(self, target_dir: Path) -> bool:
        """Uninstall skills from target directory. Returns True if subdirectory was found and processed."""
        skill_target_dir = self._get_skill_target_dir(target_dir)
        if not skill_target_dir.exists():
            return False

        for root, dirs, files in os.walk(self.skills_source_dir, topdown=False):
            rel_root = Path(root).relative_to(self.skills_source_dir)
            target_root = skill_target_dir / rel_root

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

        # Finally try to remove the skill_target_dir itself if empty
        if skill_target_dir.exists() and not any(skill_target_dir.iterdir()):
            try:
                os.rmdir(skill_target_dir)
                print(f"Removed empty skill dir: {skill_target_dir}")
            except OSError:
                pass
        
        return True
