# SPDX-License-Identifier: GPL-2.0-only
"""Original owned diagnostic helpers; no launch or ownership bypass."""
import hashlib
import importlib.util
import struct

def load_transport(path, digest):
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError("transport source hash mismatch")
    spec = importlib.util.spec_from_file_location("owned_trace_transport", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Rsp


def caller_frames(rsp, ebp, entry_esp):
    """Optional bounded frame-pointer evidence, explicitly incomplete."""
    frames, seen, reason = [], set(), "depth-limit"
    for _ in range(8):
        if ebp in seen or ebp & 3 or not entry_esp <= ebp < entry_esp + 65536:
            reason = "invalid-or-nonmonotonic-frame"
            break
        seen.add(ebp)
        try:
            following, caller = struct.unpack("<II", rsp.read(ebp, 8))
        except (ValueError, struct.error) as exc:
            reason = "unreadable-frame: " + str(exc)
            break
        frames.append(dict(frame_pointer=ebp, caller_pc=caller))
        if not following:
            reason = "zero-frame-link"
            break
        if following <= ebp:
            reason = "nonmonotonic-frame"
            break
        ebp = following
    return dict(frames=frames, complete=False, termination=reason,
                scope="heuristic frame-pointer evidence; optimized/interrupt frames may be omitted")
