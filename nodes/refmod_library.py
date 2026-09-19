"""Metadata-only RefMod library route."""
import os

from .helper_refmod_format import (
    _safetensors_path, find_mod_path, iter_refmod_files, list_refmods, read_refmod_meta, refmods_roots,
)

_entries_cache = {"sig": None, "entries": []}


def _signature():
    parts = []
    for root in refmods_roots():
        files = []
        if os.path.isdir(root):
            for path in iter_refmod_files(root):
                filename = os.path.basename(path)
                if not filename.casefold().endswith((".safetensors", ".json")):
                    continue
                stat = os.stat(path)
                files.append((os.path.relpath(path, root), stat.st_mtime_ns, stat.st_size))
        parts.append((os.path.realpath(root), tuple(sorted(files))))
    return tuple(parts)


def library_entries():
    signature = _signature()
    if signature != _entries_cache["sig"]:
        entries = []
        for name in list_refmods():
            path = find_mod_path(name)
            meta = read_refmod_meta(path) or {}
            kind = meta.get("kind")
            t = int(meta.get("latent_t", 0) or 0)
            h = int(meta.get("latent_h", 0) or 0)
            w = int(meta.get("latent_w", 0) or 0)
            tokens = t * 2 if kind == "audio" else t * (h // 2) * (w // 2)
            entries.append({"name": name, "kind": kind, "concept": meta.get("concept_type", "generic"),
                            "description": meta.get("description", ""), "tokens": tokens or None,
                            "mtime": os.path.getmtime(_safetensors_path(path))})
        _entries_cache.update(sig=signature, entries=entries)
    return _entries_cache["entries"]


def register_routes(server):
    from aiohttp import web

    @server.routes.get("/dasiwa/refmods")
    async def refmods_route(_request):
        try:
            return web.json_response(library_entries())
        except (OSError, ValueError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
