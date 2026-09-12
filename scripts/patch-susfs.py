#!/usr/bin/env python3

from pathlib import Path
import shutil
import subprocess
import sys


SUSFS_CONFIG = [
    "CONFIG_KSU_SUSFS=y",
    "CONFIG_KSU_SUSFS_SUS_PATH=y",
    "CONFIG_KSU_SUSFS_SUS_MOUNT=y",
    "CONFIG_KSU_SUSFS_SUS_KSTAT=y",
    "CONFIG_KSU_SUSFS_SPOOF_UNAME=y",
    "CONFIG_KSU_SUSFS_ENABLE_LOG=y",
    "CONFIG_KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS=y",
    "CONFIG_KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG=y",
    "CONFIG_KSU_SUSFS_OPEN_REDIRECT=y",
    "CONFIG_KSU_SUSFS_SUS_MAP=y",
    "CONFIG_KALLSYMS=y",
]


def fail(message):
    print(f"[SUSFS] ERROR: {message}")
    sys.exit(1)


def run(cmd, cwd):
    print(f"[SUSFS] $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        fail(f"Command failed with exit code {result.returncode}")


def main():
    # scripts/patch_susfs.py -> repository root
    root = Path(__file__).resolve().parent.parent

    print(f"[SUSFS] Kernel tree: {root}")

    # Basic sanity checks.
    required = [
        root / "Makefile",
        root / ".gitmodules",
        root / "KernelSU",
        root / "arch" / "arm64" / "configs" / "vendor" / "not" / "ksu.config",
    ]

    for path in required:
        if not path.exists():
            fail(f"Expected kernel-tree file/directory not found: {path}")

    ksukconfig = root / "KernelSU" / "kernel" / "Kconfig"

    if not ksukconfig.exists():
        fail(f"KernelSU Kconfig not found: {ksukconfig}")

    # Make absolutely sure the checked-out KernelSU actually contains SUSFS.
    kconfig_text = ksukconfig.read_text(errors="replace")

    required_symbols = [
        "config KSU_SUSFS",
        "config KSU_SUSFS_SUS_PATH",
        "config KSU_SUSFS_SUS_MOUNT",
        "config KSU_SUSFS_SUS_KSTAT",
        "config KSU_SUSFS_SPOOF_UNAME",
        "config KSU_SUSFS_ENABLE_LOG",
        "config KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS",
        "config KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG",
        "config KSU_SUSFS_OPEN_REDIRECT",
        "config KSU_SUSFS_SUS_MAP",
    ]

    missing = [x for x in required_symbols if x not in kconfig_text]

    if missing:
        fail(
            "The checked-out KernelSU does not contain all expected SUSFS "
            f"symbols:\n  " + "\n  ".join(missing)
        )

    print("[SUSFS] KernelSU SUSFS support detected.")

    config = root / "arch" / "arm64" / "configs" / "vendor" / "not" / "ksu.config"

    original = config.read_text()

    # Remove old/wrong SUSFS-related entries from previous attempts.
    bad_prefixes = (
        "CONFIG_KSU_SUS_PATH=",
        "CONFIG_KSU_SUSFS",
        "# CONFIG_KSU_SUSFS",
        "CONFIG_KALLSYMS=",
        "# CONFIG_KALLSYMS",
    )

    lines = original.splitlines()

    cleaned = [
        line
        for line in lines
        if not line.startswith(bad_prefixes)
    ]

    # Preserve normal formatting and append one clean SUSFS block.
    while cleaned and not cleaned[-1].strip():
        cleaned.pop()

    cleaned.append("")
    cleaned.append("# SUSFS")
    cleaned.extend(SUSFS_CONFIG)
    cleaned.append("")

    new_text = "\n".join(cleaned)

    # Backup only if something actually changes.
    if new_text != original:
        backup = config.with_suffix(config.suffix + ".bak")

        if not backup.exists():
            shutil.copy2(config, backup)
            print(f"[SUSFS] Backup created: {backup}")

        config.write_text(new_text)
        print(f"[SUSFS] Updated: {config}")
    else:
        print("[SUSFS] Config already up to date.")

    print()
    print("[SUSFS] SUSFS configuration:")
    for item in SUSFS_CONFIG:
        print(f"  {item}")

    print()
    print("[SUSFS] Running olddefconfig...")

    # Do NOT run make defconfig here.
    # build.sh has already selected the correct vendor config fragments.
    run(
        [
            "make",
            "O=out",
            "ARCH=arm64",
            "olddefconfig",
        ],
        root,
    )

    final_config = root / "out" / ".config"

    if not final_config.exists():
        fail(f"Expected generated config not found: {final_config}")

    final_text = final_config.read_text(errors="replace")

    print()
    print("[SUSFS] Checking resulting out/.config...")

    missing_final = []

    for item in SUSFS_CONFIG:
        if item not in final_text.splitlines():
            missing_final.append(item)

    if missing_final:
        print()
        print("[SUSFS] Resulting kernel configuration:")
        for line in final_text.splitlines():
            if (
                "KSU_SUSFS" in line
                or "KALLSYMS" in line
                or "THREAD_INFO_IN_TASK" in line
            ):
                print(f"  {line}")

        fail(
            "SUSFS configuration was not accepted by Kconfig.\n"
            "Missing from out/.config:\n  "
            + "\n  ".join(missing_final)
        )

    print()
    print("[SUSFS] SUCCESS!")
    print("[SUSFS] SUSFS is enabled in out/.config.")
    print()
    print("[SUSFS] Effective configuration:")

    for line in final_text.splitlines():
        if (
            "KSU_SUSFS" in line
            or "KALLSYMS" in line
            or "THREAD_INFO_IN_TASK" in line
        ):
            print(f"  {line}")


if __name__ == "__main__":
    main()
