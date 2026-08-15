"""Resolve public examples separately from private runtime configuration."""

import shutil
from pathlib import Path


ROOT = Path(__file__).parent.parent
CONFIG_DIR = ROOT / "config"
RULES_DIR = ROOT / "rules"


def _runtime_or_example(directory: Path, filename: str) -> Path:
    runtime_path = directory / filename
    if runtime_path.exists():
        return runtime_path
    return directory / filename.replace(".", ".example.", 1)


def accounts_config_path() -> Path:
    return _runtime_or_example(CONFIG_DIR, "accounts.yaml")


def sheets_config_path() -> Path:
    return _runtime_or_example(CONFIG_DIR, "sheets_config.yaml")


def merchant_rules_path() -> Path:
    return _runtime_or_example(RULES_DIR, "merchant_rules.csv")


def transfer_rules_path() -> Path:
    return _runtime_or_example(RULES_DIR, "transfer_rules.csv")


def ensure_writable_merchant_rules() -> Path:
    """Create the private runtime rules file before appending corrections."""
    runtime_path = RULES_DIR / "merchant_rules.csv"
    if not runtime_path.exists():
        runtime_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(merchant_rules_path(), runtime_path)
    return runtime_path
