"""Read-only access to saved MiniMax H3 RefMod safetensors files."""
import json
import os
from urllib.parse import unquote
from typing import Dict, List, Optional, Tuple

from safetensors import safe_open
from safetensors.torch import load_file

META_KEYS = ("refmod_meta", "audio_refmod_meta")
SKIP_DIRS = {"graph_presets", ".git", "__pycache__"}
MOD_KINDS = {"image", "video", "audio"}


def refmods_roots() -> List[str]:
    """Return RefMod folders for every model root configured in ComfyUI.

    Follows the same resolution ComfyUI itself uses for its models folder, so
    this respects --models-directory / --base-directory / extra_model_paths
    without hard-coding a path or deriving it from the plugin's location:
    the configured models root (folder_paths.models_dir) plus a ``refmods``
    subfolder, and any explicitly registered ``refmods`` category.
    """
    import folder_paths

    candidates = []
    try:
        candidates.extend(folder_paths.get_folder_paths("refmods"))
    except Exception:
        pass
    candidates.append(os.path.join(folder_paths.models_dir, "refmods"))

    roots = []
    seen = set()
    for candidate in candidates:
        normalized = os.path.abspath(os.path.expanduser(candidate))
        identity = os.path.normcase(os.path.realpath(normalized))
        if identity not in seen:
            seen.add(identity)
            roots.append(normalized)
    return roots


def iter_refmod_files(root: str):
    """Yield files below a configured RefMod root, following safe model links."""
    seen_directories = set()
    for directory, dirnames, filenames in os.walk(root, topdown=True, followlinks=True):
        identity = os.path.normcase(os.path.realpath(directory))
        if identity in seen_directories:
            dirnames[:] = []
            continue
        seen_directories.add(identity)
        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_DIRS)
        for filename in filenames:
            yield os.path.join(directory, filename)


def read_refmod_meta(path_no_ext: str) -> Optional[Dict]:
    try:
        with safe_open(path_no_ext + ".safetensors", framework="pt") as handle:
            header = handle.metadata()
        for key in META_KEYS:
            if header and key in header:
                return json.loads(header[key])
    except Exception:
        pass
    sidecar = path_no_ext + ".json"
    if os.path.isfile(sidecar):
        try:
            with open(sidecar, encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            pass
    return None


def list_refmods() -> List[str]:
    names = []
    for root in refmods_roots():
        if not os.path.isdir(root):
            continue
        for path in iter_refmod_files(root):
            filename = os.path.basename(path)
            if filename.startswith(".") or not filename.endswith(".safetensors"):
                continue
            meta = read_refmod_meta(path[:-len(".safetensors")])
            if isinstance(meta, dict) and meta.get("kind") in MOD_KINDS:
                names.append(os.path.splitext(os.path.relpath(path, root))[0].replace(os.sep, "/"))
    return sorted(set(names))


def _validate_name(name: str) -> list[str]:
    decoded = unquote(name) if isinstance(name, str) else name
    if (not isinstance(decoded, str) or not decoded or decoded in {"None", "(none)"} or
            decoded.startswith(("/", "\\")) or "//" in decoded or "\\" in decoded or
            any(part in {"", ".", ".."} for part in decoded.split("/"))):
        raise ValueError(f"Invalid RefMod name: {name!r}")
    return decoded.split("/")


def find_mod_path(name: str) -> str:
    parts = _validate_name(name)
    for root in refmods_roots():
        root_path = os.path.abspath(root)
        target = os.path.abspath(os.path.join(root_path, *parts) + ".safetensors")
        try:
            inside_root = os.path.commonpath((root_path, target)) == root_path
        except ValueError:
            inside_root = False
        if inside_root and os.path.isfile(target):
            return target[:-len(".safetensors")]
    raise ValueError(f"RefMod '{name}' not found in refmods folders.")


def refmod_mtime(name: str) -> float:
    return os.path.getmtime(find_mod_path(name) + ".safetensors")


def refmod_fingerprint(name: str) -> tuple[int, int]:
    stat = os.stat(find_mod_path(name) + ".safetensors")
    return stat.st_mtime_ns, stat.st_size


def load_refmod(name: str) -> Tuple["object", Dict]:
    path = find_mod_path(name)
    meta = read_refmod_meta(path)
    if not isinstance(meta, dict):
        raise ValueError(f"{path}.safetensors has no RefMod metadata.")
    if meta.get("kind") not in MOD_KINDS:
        raise ValueError(f"RefMod '{name}' kind {meta.get('kind')!r} not usable here (bundles need the upstream pack).")
    tensors = load_file(path + ".safetensors", device="cpu")
    if "latent" not in tensors:
        raise ValueError(f"RefMod '{name}' has no 'latent' tensor.")
    return tensors["latent"].clone(), meta
