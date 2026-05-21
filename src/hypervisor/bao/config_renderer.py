"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
Render Bao C configuration files from YAML input using Jinja templates.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined


def _get_platform_name(platform) -> str:
    """Return the normalized platform name used for config lookup and output."""
    platform_name = getattr(platform, "platform_name", None)
    if platform_name:
        return platform_name
    return platform.__class__.__name__.replace("_", "-")


def _resolve_yaml_config_path(config_path: str, platform) -> str:
    """Resolve the YAML config path for the given platform."""
    platform_name = _get_platform_name(platform)
    candidates = [
        os.path.join(config_path, f"{platform_name}.yaml"),
        os.path.join(config_path, f"{platform_name}.yml"),
        os.path.join(config_path, platform_name, f"{platform_name}.yaml"),
        os.path.join(config_path, platform_name, f"{platform_name}.yml"),
    ]

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    raise FileNotFoundError(
        f"Could not find YAML config for platform '{platform_name}' in '{config_path}'."
    )


def _extract_vm_entries(config_file: dict[str, Any]) -> list[Any]:
    """Extract the VM list from the top-level or setup section."""
    if not isinstance(config_file, dict):
        return []

    vm_entries = config_file.get("vms")
    if vm_entries is None:
        setup_cfg = config_file.get("setup", {})
        if isinstance(setup_cfg, dict):
            vm_entries = setup_cfg.get("vms", [])

    return vm_entries if isinstance(vm_entries, list) else []


def _normalize_vm_entry(vm_entry: Any, vm_idx: int) -> tuple[str, dict[str, Any]]:
    """Normalize a VM entry into a VM key and configuration dictionary."""
    vm_key = f"vm{vm_idx + 1}"

    if not isinstance(vm_entry, dict):
        return vm_key, {}

    vm_named_keys = [
        key for key in vm_entry if isinstance(key, str) and key.startswith("vm")
    ]
    if vm_named_keys:
        vm_key = vm_named_keys[0]
        nested_cfg = vm_entry.get(vm_key)
        if isinstance(nested_cfg, dict):
            merged_cfg = dict(nested_cfg)
            for key, value in vm_entry.items():
                if key != vm_key:
                    merged_cfg.setdefault(key, value)
            return vm_key, merged_cfg

    return vm_key, vm_entry


def _to_c_literal(value: Any) -> str | None:
    """Convert a Python value into a C literal string."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return hex(value)
    return str(value)


def _to_c_initializer_literal(value: Any) -> str | None:
    """Convert a Python value into a C initializer literal."""
    if isinstance(value, list):
        values = []
        for item in value:
            item_literal = _to_c_initializer_literal(item)
            if item_literal is not None:
                values.append(item_literal)
        return "{" + ", ".join(values) + "}"
    return _to_c_literal(value)


def _flatten_c_designators(
    cfg: dict[str, Any], prefix: str = ""
) -> list[tuple[str, Any]]:
    """Flatten nested dictionaries into C designator paths."""
    designators: list[tuple[str, Any]] = []

    if not isinstance(cfg, dict):
        return designators

    for key, value in cfg.items():
        key_str = str(key).strip()
        if not key_str:
            continue

        next_prefix = f"{prefix}.{key_str}" if prefix else key_str
        if isinstance(value, dict):
            designators.extend(_flatten_c_designators(value, next_prefix))
        else:
            designators.append((next_prefix, value))

    return designators


def _image_mode(image_cfg: dict[str, Any]) -> str:
    """Determine how the VM image should be rendered."""
    has_base = "base_addr" in image_cfg
    has_load = "load_addr" in image_cfg
    has_phys = "phys_addr" in image_cfg
    has_size = "size" in image_cfg

    if has_load and has_phys and has_size:
        return "loaded"
    if has_base and not has_load and not has_size:
        return "macro_offset_size"
    return "explicit_fields"


def _normalize_image(vm_bin_name: str, image_cfg: dict[str, Any]) -> dict[str, Any]:
    """Normalize a VM image configuration into render-ready fields."""
    image_cfg = image_cfg if isinstance(image_cfg, dict) else {}
    image_symbol = re.sub(r"[^a-zA-Z0-9_]", "_", f"{vm_bin_name}_image")
    mode = _image_mode(image_cfg)

    if mode == "loaded":
        load_addr = _to_c_literal(image_cfg.get("load_addr"))
        phys_addr = _to_c_literal(image_cfg.get("phys_addr"))
        size = _to_c_literal(image_cfg.get("size"))
        expr = f"VM_IMAGE_LOADED({load_addr}, {phys_addr}, {size})"
        return {
            "mode": mode,
            "symbol": image_symbol,
            "bin_name": vm_bin_name,
            "expr": expr,
            "struct_fields": [],
            "declare_macro_image": False,
        }

    if mode == "macro_offset_size":
        load_addr = f"VM_IMAGE_OFFSET({image_symbol})"
        size = f"VM_IMAGE_SIZE({image_symbol})"
    else:
        load_addr = _to_c_literal(image_cfg.get("load_addr"))
        size = _to_c_literal(image_cfg.get("size"))

    if load_addr is None:
        load_addr = f"VM_IMAGE_OFFSET({image_symbol})"
    if size is None:
        size = f"VM_IMAGE_SIZE({image_symbol})"

    base_addr = _to_c_literal(image_cfg.get("base_addr"))
    if base_addr is None:
        base_addr = _to_c_literal(image_cfg.get("phys_addr"))
    if base_addr is None:
        base_addr = load_addr

    struct_fields = [
        ("base_addr", base_addr),
        ("load_addr", load_addr),
        ("size", size),
    ]

    return {
        "mode": mode,
        "symbol": image_symbol,
        "bin_name": vm_bin_name,
        "expr": None,
        "struct_fields": struct_fields,
        "declare_macro_image": mode == "macro_offset_size",
    }


def _normalize_regions(regions_cfg: Any) -> list[dict[str, Any]]:
    """Normalize VM memory region definitions."""
    regions_cfg = regions_cfg if isinstance(regions_cfg, list) else []
    regions = []

    for region in regions_cfg:
        region = region if isinstance(region, dict) else {}
        regions.append(
            {
                "fields": [
                    ("base", _to_c_literal(region.get("base"))),
                    ("size", _to_c_literal(region.get("size"))),
                ]
            }
        )
    return regions


def _normalize_devs(devs_cfg: Any, platform_name: str) -> list[dict[str, Any]]:
    """Normalize VM device region definitions."""
    devs_cfg = devs_cfg if isinstance(devs_cfg, list) else []
    devs = []

    for dev in devs_cfg:
        dev = dev if isinstance(dev, dict) else {}
        interrupts = dev.get("interrupts", [])
        interrupts = interrupts if isinstance(interrupts, list) else []

        interrupt_values = ", ".join(_to_c_literal(irq) for irq in interrupts)
        only_interrupts = (
            bool(interrupts)
            and "pa" not in dev
            and "va" not in dev
            and "size" not in dev
        )

        comment = None
        qemu_timer_special_case = False

        if platform_name == "qemu-aarch64-virt":
            if interrupts == ["33"] and not only_interrupts:
                comment = "PL011"
            elif interrupts == ["27"] and only_interrupts:
                comment = "Arch timer interrupt"
                qemu_timer_special_case = True

        devs.append(
            {
                "comment": comment,
                "qemu_timer_special_case": qemu_timer_special_case,
                "interrupt_num": len(interrupts),
                "interrupt_values": interrupt_values,
                "fields": [
                    ("pa", _to_c_literal(dev.get("pa"))),
                    ("va", _to_c_literal(dev.get("va"))),
                    ("size", _to_c_literal(dev.get("size"))),
                    ("interrupt_num", str(len(interrupts)) if interrupts else None),
                    (
                        "interrupts",
                        f"(irqid_t[]) {{{interrupt_values}}}" if interrupts else None,
                    ),
                ],
            }
        )

    return devs


def _normalize_arch(arch_cfg: Any, platform_name: str) -> dict[str, Any] | None:
    """Normalize architecture-specific configuration fields."""
    arch_cfg = arch_cfg if isinstance(arch_cfg, dict) else {}
    if not arch_cfg:
        return None

    generic_entries = []
    for arch_key, arch_value in _flatten_c_designators(
        {key: value for key, value in arch_cfg.items() if key != "gic"}
    ):
        normalized_key = "gpsr_groups" if arch_key == "gspr_groups" else arch_key
        arch_literal = _to_c_initializer_literal(arch_value)
        if arch_literal is None:
            continue

        if normalized_key == "gpsr_groups" and isinstance(arch_value, list):
            arch_literal = f"(unsigned long int[]){arch_literal}"

        if (
            platform_name == "qemu-aarch64-virt"
            and normalized_key in {"gic.gicd_addr", "gic.gicr_addr"}
        ):
            arch_literal = f"(paddr_t) {arch_literal}"

        generic_entries.append((normalized_key, arch_literal))

    gic_entries = []
    gic_cfg = arch_cfg.get("gic")
    if isinstance(gic_cfg, dict):
        for gic_key, gic_value in gic_cfg.items():
            gic_literal = _to_c_initializer_literal(gic_value)
            if gic_literal is None:
                continue

            if (
                platform_name == "qemu-aarch64-virt"
                and gic_key in {"gicd_addr", "gicr_addr"}
            ):
                gic_literal = f"(paddr_t) {gic_literal}"

            gic_entries.append((gic_key, gic_literal))

    return {
        "gic_entries": gic_entries,
        "generic_entries": generic_entries,
    }


def _normalize_vm(vm_entry: Any, vm_idx: int, platform_name: str) -> dict[str, Any]:
    """Normalize a VM configuration into the template render model."""
    vm_key, vm_cfg = _normalize_vm_entry(vm_entry, vm_idx)
    vm_cfg = vm_cfg if isinstance(vm_cfg, dict) else {}

    vm_runtime_cfg = vm_cfg.get("config", {})
    vm_runtime_cfg = vm_runtime_cfg if isinstance(vm_runtime_cfg, dict) else {}

    vm_image_cfg = vm_runtime_cfg.get("image", {})
    vm_platform_cfg = vm_runtime_cfg.get("platform", {})
    vm_platform_cfg = vm_platform_cfg if isinstance(vm_platform_cfg, dict) else {}

    vm_name = vm_cfg.get("name") or vm_key
    build_options = vm_cfg.get("build_options", {})
    build_options = build_options if isinstance(build_options, dict) else {}

    vm_bin_name = build_options.get("bin_name")
    if not isinstance(vm_bin_name, str) or not vm_bin_name.strip():
        vm_bin_name = vm_name
    vm_bin_name = vm_bin_name.strip()

    image = _normalize_image(vm_bin_name, vm_image_cfg)

    return {
        "name": vm_name,
        "bin_name": vm_bin_name,
        "entry": _to_c_literal(vm_runtime_cfg.get("entry")),
        "image": image,
        "platform": {
            "cpu_num": _to_c_literal(vm_platform_cfg.get("cpu_num")),
            "regions": _normalize_regions(vm_platform_cfg.get("regions", [])),
            "devs": _normalize_devs(vm_platform_cfg.get("devs", []), platform_name),
            "arch": _normalize_arch(vm_platform_cfg.get("arch", {}), platform_name),
        },
    }


def _build_render_model(config_file: dict[str, Any], platform_name: str) -> dict[str, Any]:
    """Build the complete template render model from the YAML config."""
    vm_entries = [
        _normalize_vm(vm_entry, vm_idx, platform_name)
        for vm_idx, vm_entry in enumerate(_extract_vm_entries(config_file))
    ]

    declared_images = [
        {
            "symbol": vm["image"]["symbol"],
            "bin_name": vm["image"]["bin_name"],
        }
        for vm in vm_entries
        if vm["image"]["declare_macro_image"]
    ]

    return {
        "platform_name": platform_name,
        "num_vms": len(vm_entries),
        "declared_images": declared_images,
        "vms": vm_entries,
    }


def _resolve_output_c_path(
    yaml_path: str, platform_name: str, output_dir: str | None
) -> str:
    """Resolve the final output path for the generated config.c file."""
    if output_dir is not None:
        output_dir = os.path.abspath(output_dir)
        output_dir = os.path.join(output_dir, platform_name)
        os.makedirs(output_dir, exist_ok=True)
        return os.path.join(output_dir, "config.c")

    if os.path.basename(os.path.dirname(yaml_path)) == platform_name:
        return os.path.join(os.path.dirname(yaml_path), "config.c")

    return os.path.join(os.path.dirname(yaml_path), platform_name, "config.c")


class BaoConfigRenderer:
    """Render Bao configuration files from a normalized model."""

    def __init__(self, template_dir: str | Path | None = None):
        """Initialize the Jinja environment and template directory."""
        if template_dir is None:
            template_dir = Path(__file__).resolve().parent / "templates"

        self.template_dir = Path(template_dir)
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

        self.env.filters["render_fields"] = self._render_fields

    @staticmethod
    def _render_fields(fields: list[tuple[str, str | None]], indent: str) -> str:
        """Render a list of C struct fields using the requested indentation."""
        valid_fields = [(name, value) for name, value in fields if value not in (None, "")]
        lines = []
        for idx, (name, value) in enumerate(valid_fields):
            suffix = "," if idx < len(valid_fields) - 1 else ""
            lines.append(f"{indent}.{name} = {value}{suffix}")
        return "\n".join(lines)

    def render_to_string(self, model: dict[str, Any]) -> str:
        """Render the config template into a string."""
        template = self.env.get_template("config.c")
        return template.render(**model)

    def render_to_file(self, model: dict[str, Any], output_path: str | Path) -> str:
        """Render the config template and write it to a file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.render_to_string(model), encoding="utf-8")
        return str(output_path)


def read_config(config_path: str, platform) -> list[dict[str, Any]]:
    """Read a YAML config and return the legacy VM list structure."""
    yaml_path = _resolve_yaml_config_path(config_path, platform)

    with open(yaml_path, "r", encoding="utf-8") as yaml_file:
        config_file = yaml.safe_load(yaml_file) or {}

    vm_list_config = []
    for vm_idx, vm_entry in enumerate(_extract_vm_entries(config_file)):
        vm_key, vm_cfg = _normalize_vm_entry(vm_entry, vm_idx)
        vm_cfg = vm_cfg if isinstance(vm_cfg, dict) else {}

        vm_runtime_cfg = vm_cfg.get("config", {})
        vm_runtime_cfg = vm_runtime_cfg if isinstance(vm_runtime_cfg, dict) else {}

        vm_list_config.append(
            {
                vm_key: {
                    "name": vm_cfg.get("name"),
                    "build_options": vm_cfg.get("build_options", {}),
                    "image": vm_runtime_cfg.get("image", {}),
                    "entry": vm_runtime_cfg.get("entry"),
                    "platform_cfg": vm_runtime_cfg.get("platform", {}),
                }
            }
        )

    return vm_list_config


def write_config(config_path: str, platform, output_dir: str | None = None) -> str:
    """Read a YAML config, render it, and write the generated config.c file."""
    yaml_path = _resolve_yaml_config_path(config_path, platform)
    platform_name = _get_platform_name(platform)

    with open(yaml_path, "r", encoding="utf-8") as yaml_file:
        config_file = yaml.load(yaml_file, Loader=yaml.BaseLoader) or {}

    model = _build_render_model(config_file, platform_name)
    output_c_path = _resolve_output_c_path(yaml_path, platform_name, output_dir)

    renderer = BaoConfigRenderer()
    return renderer.render_to_file(model, output_c_path)
