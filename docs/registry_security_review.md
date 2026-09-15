# Registry Security Review

This document records the Comfy Registry findings and the data-flow review for the public node package. It does not contain raw scanner payloads, source snippets, credentials, or unpublished release details.

## Registry evidence

On 2026-09-15, `python tools/audit_comfy_registry_status.py` showed that `0.4.22` is active and every release from `0.4.23` through `0.4.37` is banned. Versions `0.4.31` through `0.4.34` identify an actual remote-code path in the LLM selector: workflow-controlled Hugging Face repository download plus `trust_remote_code`. The remediation removes those controls and locks Ollama to loopback.

The Registry's current `policy-v0.4: rce-remote-code` scan also reports static findings. They require an explicit decision or a manual review; they must not be obscured to alter scanner results.

## Finding inventory

| Finding | Location | Data origin | Current guard | Impact if guard fails | Decision | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| Remote model execution | `nodes/nodes_llm.py` (removed download and remote-code controls) | `/prompt` widget values | Previously none sufficient | Attacker-selected repository code could execute in the ComfyUI process | Removed | `.tests/test_llm_nodes.py`; registry audit after release |
| Arbitrary server-side request via Ollama URL | `nodes/nodes_llm.py` (removed URL widget) | `/prompt` widget value | Previously none | Server-side request to attacker-chosen service | Removed; endpoint is fixed to loopback | `.tests/test_llm_nodes.py` captures the request URL |
| FFmpeg preview subprocess | `nodes/nodes_enhanced_video_combine.py:80-111,171-175,345-404` | Request selects an output asset; node execution provides encoded frames and output path | `_preview_source_path()` rejects traversal and constrains the preview source to a ComfyUI asset root; FFmpeg commands use argument lists, not shells | An unchecked asset path or command construction regression could expose files or execute an unintended binary | Await owner decision: retain for manual review or remove/isolate from the registry package | Existing `.tests/test_enhanced_video_combine.py`; add route-level security tests before any change |
| Civitai by-hash request | `nodes/lora_info.py:179-191,203-266` | A selected local LoRA name resolves through `folder_paths`; SHA-256 becomes the Civitai request key | LoRA path resolution uses `folder_paths`; request destination is a module constant | Local file metadata is sent as a deterministic hash to a third party; a route can trigger outbound traffic | Await owner decision: retain with disclosure/manual review or remove remote lookup | `.tests/test_lora_info.py`; verify no remote request after removal if selected |
| Hardware telemetry subprocess | `nodes/nodes_system_monitor.py:67-73,76-138,179-205` | Fixed internal GPU probe lists | Executable is looked up by fixed name; arguments are constants; no shell | A future command interpolation regression could run unintended programs | Await owner decision: retain for manual review or remove/isolate the monitor | `.tests/test_system_monitor.py`; add command-list assertions before any change |
| Dynamic import | `nodes/nodes_rtx_upscaler_refiner.py:23-29` | Constant module name | The module name is not workflow input | Scanner treats dynamic import as import evasion; compatibility behavior is not yet covered | Replace with a normal guarded import after writing a focused compatibility test | New focused pytest before production change |
| Long Director log statement | `nodes/nodes_minimax_h3_director.py:236` | Internal model/timeline values | No code loading or process launch | None; scanner misclassifies semicolon density as minification | Reformat only after writing a behavior-preserving test or include in manual-review evidence | Existing Director tests plus log-output assertion |

## Required decision before the next registry publication

The confirmed remote-code and arbitrary-request paths can be removed without sacrificing local inference. The remaining FFmpeg, Civitai, telemetry, dynamic-import, and formatting findings have different product tradeoffs. Before publishing, choose one policy for each retained capability:

1. retain it and request Comfy Registry manual review with its data-flow evidence;
2. remove or isolate it from the public registry package; or
3. adopt a documented ComfyUI core replacement supplied by Registry maintainers.

Do not publish a cosmetic scanner-evasion change. The final release is accepted only when the Registry API reports the exact version as `NodeVersionStatusActive`.
