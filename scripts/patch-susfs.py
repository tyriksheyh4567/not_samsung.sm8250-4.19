#!/usr/bin/env python3

from pathlib import Path
from datetime import datetime
import shutil
import sys


# ============================================================
# SUSFS configuration
# ============================================================

SUSFS_CONFIG = {
    "CONFIG_KSU_SUSFS": "y",
    "CONFIG_KSU_SUSFS_SUS_PATH": "y",
    "CONFIG_KSU_SUSFS_SUS_MOUNT": "y",
    "CONFIG_KSU_SUSFS_SUS_KSTAT": "y",
    "CONFIG_KSU_SUSFS_SPOOF_UNAME": "y",
    "CONFIG_KSU_SUSFS_ENABLE_LOG": "y",
    "CONFIG_KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS": "y",
    "CONFIG_KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG": "y",
    "CONFIG_KSU_SUSFS_OPEN_REDIRECT": "y",
    "CONFIG_KSU_SUSFS_SUS_MAP": "y",
}

# KSU_HACK_ARM64_BRANCH_LINK depends on KALLSYMS.
# You already have KALLSYMS, so we make sure it stays enabled.
EXTRA_CONFIG = {
    "CONFIG_KALLSYMS": "y",
}


# ============================================================
# Paths
# ============================================================

ROOT = Path(__file__).resolve().parent.parent

KSU_KCONFIG = ROOT / "KernelSU" / "kernel" / "Kconfig"

KSU_CONFIG = (
    ROOT
    / "arch"
    / "arm64"
    / "configs"
    / "vendor"
    / "not"
    / "ksu.config"
)

OLD_DEFCONFIG = (
    ROOT
    / "arch"
    / "arm64"
    / "configs"
    / "defconfig"
)


# ============================================================
# Pretty output
# ============================================================

def info(text):
    print(f"\033[36m[*]\033[0m {text}")


def success(text):
    print(f"\033[32m[+]\033[0m {text}")


def warning(text):
    print(f"\033[33m[!]\033[0m {text}")


def error(text):
    print(f"\033[31m[-]\033[0m {text}")


def die(text):
    error(text)
    sys.exit(1)


# ============================================================
# Backup
# ============================================================

def backup(path):
    if not path.exists():
        return

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    backup_path = path.with_name(
        path.name + f".bak.{timestamp}"
    )

    shutil.copy2(path, backup_path)

    info(f"Backup: {backup_path.relative_to(ROOT)}")


# ============================================================
# Config manipulation
# ============================================================

def clean_symbol(text, symbol):
    """
    Remove both:

        CONFIG_FOO=y
        CONFIG_FOO=n
        # CONFIG_FOO is not set

    for the requested symbol.
    """

    result = []

    for line in text.splitlines():

        stripped = line.strip()

        if stripped.startswith(symbol + "="):
            continue

        if stripped == f"# {symbol} is not set":
            continue

        result.append(line)

    return "\n".join(result)


def set_symbol(text, symbol, value):
    """
    Remove existing definition and append exactly one
    canonical definition.
    """

    text = clean_symbol(text, symbol)

    text = text.rstrip()

    if text:
        text += "\n"

    text += f"{symbol}={value}\n"

    return text


# ============================================================
# Checks
# ============================================================

def check_repository():

    info(f"Kernel root: {ROOT}")

    if not (ROOT / "Makefile").exists():
        die(
            "Это не похоже на корень kernel tree.\n"
            "Запускай скрипт внутри not_samsung.sm8250-4.19."
        )

    if not KSU_KCONFIG.exists():
        die(
            "Не найден:\n"
            "KernelSU/kernel/Kconfig\n\n"
            "Проверь, что KernelSU submodule инициализирован."
        )

    if not KSU_CONFIG.exists():
        die(
            "Не найден:\n"
            "arch/arm64/configs/vendor/not/ksu.config"
        )

    success("Структура репозитория OK.")


def check_susfs():

    text = KSU_KCONFIG.read_text(
        encoding="utf-8",
        errors="replace",
    )

    required = [
        "config KSU_SUSFS",
        "config KSU_SUSFS_SUS_PATH",
        "config KSU_SUSFS_SUS_MOUNT",
        "config KSU_SUSFS_SUS_KSTAT",
        "config KSU_SUSFS_SPOOF_UNAME",
        "config KSU_SUSFS_SUS_MAP",
    ]

    missing = [
        symbol
        for symbol in required
        if symbol not in text
    ]

    if missing:
        die(
            "В KernelSU не найден полный SUSFS Kconfig.\n\n"
            + "\n".join("  " + x for x in missing)
        )

    success("SUSFS найден в KernelSU.")


# ============================================================
# Patch ksu.config
# ============================================================

def patch_ksu_config():

    info("Патчу vendor/not/ksu.config")

    backup(KSU_CONFIG)

    text = KSU_CONFIG.read_text(
        encoding="utf-8",
        errors="replace",
    )

    # --------------------------------------------------------
    # Fix old typo:
    #
    # CONFIG_KSU_SUS_PATH=y
    #
    # This symbol DOES NOT exist.
    # --------------------------------------------------------

    if "CONFIG_KSU_SUS_PATH=" in text:
        warning(
            "Найден старый неправильный CONFIG_KSU_SUS_PATH"
        )

    text = clean_symbol(
        text,
        "CONFIG_KSU_SUS_PATH",
    )

    # --------------------------------------------------------
    # Add SUSFS
    # --------------------------------------------------------

    for symbol, value in SUSFS_CONFIG.items():

        text = set_symbol(
            text,
            symbol,
            value,
        )

    # --------------------------------------------------------
    # Required for KSU branch-link mode
    # --------------------------------------------------------

    for symbol, value in EXTRA_CONFIG.items():

        text = set_symbol(
            text,
            symbol,
            value,
        )

    KSU_CONFIG.write_text(
        text,
        encoding="utf-8",
    )

    success(
        "vendor/not/ksu.config обновлён."
    )


# ============================================================
# Clean old SUSFS entries from wrong defconfig
# ============================================================

def clean_old_defconfig():

    if not OLD_DEFCONFIG.exists():
        return

    text = OLD_DEFCONFIG.read_text(
        encoding="utf-8",
        errors="replace",
    )

    susfs_symbols = [
        "CONFIG_KSU_SUSFS",
        "CONFIG_KSU_SUS_PATH",
        "CONFIG_KSU_SUSFS_SUS_PATH",
        "CONFIG_KSU_SUSFS_SUS_MOUNT",
        "CONFIG_KSU_SUSFS_SUS_KSTAT",
        "CONFIG_KSU_SUSFS_SPOOF_UNAME",
        "CONFIG_KSU_SUSFS_ENABLE_LOG",
        "CONFIG_KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS",
        "CONFIG_KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG",
        "CONFIG_KSU_SUSFS_OPEN_REDIRECT",
        "CONFIG_KSU_SUSFS_SUS_MAP",
    ]

    original = text

    for symbol in susfs_symbols:
        text = clean_symbol(text, symbol)

    if text != original:

        backup(OLD_DEFCONFIG)

        OLD_DEFCONFIG.write_text(
            text,
            encoding="utf-8",
        )

        success(
            "Удалены SUSFS-настройки из старого "
            "arch/arm64/configs/defconfig"
        )

    else:
        info(
            "SUSFS в arch/arm64/configs/defconfig "
            "не найден — ничего удалять не пришлось."
        )


# ============================================================
# Print result
# ============================================================

def show_result():

    print()
    print("=" * 60)
    print("SUSFS CONFIG")
    print("=" * 60)

    text = KSU_CONFIG.read_text(
        encoding="utf-8",
        errors="replace",
    )

    for line in text.splitlines():

        if (
            line.startswith("CONFIG_KSU_SUSFS")
            or line.startswith("CONFIG_KALLSYMS")
        ):
            print(line)

    print("=" * 60)
    print()


# ============================================================
# Main
# ============================================================

def main():

    print()
    print("==========================================")
    print("   not_kernel SUSFS patcher")
    print("==========================================")
    print()

    check_repository()

    check_susfs()

    patch_ksu_config()

    clean_old_defconfig()

    show_result()

    success("Ready!")


if __name__ == "__main__":
    main()
