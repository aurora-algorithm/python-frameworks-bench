"""Checks every server gives the same answers before anything is timed: the same 50 users, the same accepted and
rejected POST inputs (unknown fields dropped, UUID ids), and 50 rows from Postgres. Prints each server's headers.

usage (inside the rig): python3 verify.py [--table] [server ...]
--table prints one row per POST input and one column per server, with the status code each server answered.
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

VALID = {"name": "Ada", "email": "ada@example.com", "age": 36}
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
CASES = [
    ("valid", VALID, True),
    ("unknown field dropped", {**VALID, "admin": True}, True),
    # Every framework's default (lax) mode turns "36" and 36.0 into 36; the reply must say 36.
    ("age as a string", {**VALID, "age": "36"}, True),
    ("age as 36.0", {**VALID, "age": 36.0}, True),
    ("age not whole", {**VALID, "age": 36.5}, False),
    ("age negative", {**VALID, "age": -1}, False),
    ("age too big", {**VALID, "age": 151}, False),
    ("empty name", {**VALID, "name": ""}, False),
    ("name too long", {**VALID, "name": "x" * 51}, False),
    ("not an email", {**VALID, "email": "ada"}, False),
    ("missing age", {"name": "Ada", "email": "ada@example.com"}, False),
]
EXPECTED_USERS = [
    {"id": i, "name": "User", "email": "user@example.com", "active": i % 2 == 0, "tags": ["a", "b"]} for i in range(50)
]
SERVERS = ["flask", "django", "fastapi", "fastapi-typed", "litestar"]


def server(name: str) -> tuple[int, str]:
    script = f'source servers.sh; echo "$(port_of {name})"; server_cmd {name} users-db'
    port, cmd = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True).stdout.split("\n", 1)
    return int(port), cmd.strip()


def request(port: int, method: str, path: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"content-type": "application/json"} if data else {}
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), err.read()


def check(name: str, quiet: bool) -> tuple[list[str], list[int]]:
    port, cmd = server(name)
    env = {**os.environ, "DATABASE_URL": os.environ.get("DATABASE_URL", "postgres://dev:dev@127.0.0.1/bench")}
    proc = subprocess.Popen(
        ["bash", "-c", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=env, start_new_session=True
    )
    try:
        for _ in range(150):
            try:
                request(port, "GET", "/users")
                break
            except OSError:
                time.sleep(0.1)
        problems, statuses = [], []
        status, headers, body = request(port, "GET", "/users")
        if status != 200 or json.loads(body) != EXPECTED_USERS:
            problems.append(f"GET /users: {status} {body[:80]!r}")
        for label, payload, ok in CASES:
            status, _, reply = request(port, "POST", "/users", payload)
            statuses.append(status)
            if ok:
                created = json.loads(reply) if status == 201 else {}
                new_id = created.pop("id", "")
                expected = VALID
                if status != 201 or created != expected or not UUID.match(str(new_id)):
                    problems.append(f"{label}: expected 201 with a UUID id and {expected}, got {status} {reply[:90]!r}")
            elif not 400 <= status < 500:
                problems.append(f"{label}: expected a 4xx, got {status} {reply[:90]!r}")
        status, _, rows = request(port, "GET", "/users-db")
        if status != 200 or len(json.loads(rows)) != 50:
            problems.append(f"GET /users-db: {status} {rows[:80]!r}")
        if not quiet:
            shown = {k: v for k, v in headers.items() if k.lower() not in ("date",)}
            print(f"{name:22} {len(body):5} B  {shown}")
        return problems, statuses
    finally:
        os.killpg(proc.pid, 15)
        proc.wait()


def main() -> None:
    args = sys.argv[1:]
    as_table = "--table" in args
    names = [a for a in args if a != "--table"] or SERVERS
    failed = False
    columns = {}
    for name in names:
        problems, columns[name] = check(name, quiet=as_table)
        for problem in problems:
            failed = True
            print(f"  FAIL {name}: {problem}")
    if as_table:
        width = max(len(label) for label, _, _ in CASES) + 4
        shown = [n for n in names if columns[n]]
        print("input".ljust(width) + "".join(n.ljust(15) for n in shown))
        for i, (label, _, _) in enumerate(CASES):
            print(label.ljust(width) + "".join(str(columns[n][i]).ljust(15) for n in shown))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
