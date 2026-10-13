"""Apply QMP latency to this isolated fixture drive, then start the VM."""
import json
import socket
import sys
import time

port, limit, output = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
deadline = time.monotonic() + 12
while True:
    try:
        connection = socket.create_connection(("127.0.0.1", port), timeout=2)
        break
    except OSError:
        if time.monotonic() >= deadline:
            raise
        time.sleep(0.1)
connection.settimeout(12)
stream = connection.makefile("rwb", buffering=0)
transcript = [json.loads(stream.readline())]


def command(name, arguments=None):
    request = {"execute": name}
    if arguments is not None:
        request["arguments"] = arguments
    stream.write(json.dumps(request).encode() + b"\n")
    while True:
        result = json.loads(stream.readline())
        transcript.append({"request": request, "response": result})
        if "error" in result:
            raise RuntimeError(result)
        if "return" in result:
            return result["return"]


try:
    command("qmp_capabilities")
    blocks = command("query-block")
    disks = [b for b in blocks if b.get("inserted", {}).get("file", "").lower().endswith("hdd.qcow2")]
    if len(disks) != 1:
        raise RuntimeError("Expected exactly one isolated hdd.qcow2")
    command("block_set_io_throttle", {
        "device": disks[0]["device"], "bps": 0, "bps_rd": limit,
        "bps_wr": 0, "iops": 0, "iops_rd": 0, "iops_wr": 0,
    })
    command("query-block")
    command("cont")
finally:
    with open(output, "w", encoding="utf-8") as target:
        json.dump(transcript, target, indent=2)
    connection.close()
