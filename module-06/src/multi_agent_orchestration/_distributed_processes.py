"""Private bounded pipe transport and cancellation-safe ownership of two children."""

import asyncio
import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from .distributed import decode_packet, encode_packet, validate_response
from .distributed_contracts import (
    MAX_PACKET_BYTES,
    WorkerAssignment,
    WorkerFailure,
    WorkerReady,
    WorkerRelease,
    WorkerResponse,
    WorkerStarted,
)
from .errors import ExecutionFailureError, InvalidRuntimeOutputError


@dataclass(frozen=True)
class Connection:
    assignment: WorkerAssignment
    process: asyncio.subprocess.Process


def worker_environment(directory: str) -> dict:
    environment = {
        key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR") if key in os.environ
    }
    environment.update(
        TEMP=directory,
        TMP=directory,
        HOME=directory,
        USERPROFILE=directory,
        LOCALAPPDATA=str(Path(directory, "AppData", "Local")),
        APPDATA=str(Path(directory, "AppData", "Roaming")),
        ADK_TELEMETRY_IGNORE_RUN_CONFIG="false",
        ADK_EXPERIMENTAL_TELEMETRY="false",
        OTEL_SDK_DISABLED="true",
        DO_NOT_TRACK="1",
        LANGSMITH_TRACING="false",
        LANGCHAIN_TRACING_V2="false",
    )
    return environment


async def spawn_worker(assignment: WorkerAssignment, directory: str):
    """Launch with identity/digest; task fragments travel only in private pipes."""
    for name in ("Local", "Roaming"):
        Path(directory, "AppData", name).mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        # Windows venv redirectors introduce a second, unowned interpreter PID.
        # Launch the actual interpreter and activate only this installed venv's
        # site directory; editable package ownership remains unchanged.
        command = (
            sys._base_executable,
            "-I",
            "-c",
            "import runpy,site,sys;site.addsitedir(sys.argv.pop(1));"
            "runpy.run_module('multi_agent_orchestration._distributed_worker',"
            "run_name='__main__')",
            str(Path(sys.prefix, "Lib", "site-packages")),
        )
    else:
        command = (
            sys.executable,
            "-I",
            "-m",
            "multi_agent_orchestration._distributed_worker",
        )
    return await asyncio.create_subprocess_exec(
        *command,
        assignment.worker.value,
        hashlib.sha256(encode_packet(assignment)).hexdigest(),
        str(assignment.coordinator_pid),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        limit=MAX_PACKET_BYTES + 1,
        env=worker_environment(directory),
        cwd=directory,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


async def read_packet(connection: Connection, schema):
    try:
        data = await connection.process.stdout.readuntil(b"\n")
    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError) as exc:
        raise InvalidRuntimeOutputError(
            "Worker violated bounded packet framing."
        ) from exc
    try:
        return decode_packet(data, schema)
    except InvalidRuntimeOutputError as original:
        try:
            failure = decode_packet(data, WorkerFailure)
        except InvalidRuntimeOutputError:
            raise original from original.__cause__
        error = (
            InvalidRuntimeOutputError
            if failure.category in ("invalid_assignment", "invalid_output")
            else ExecutionFailureError
        )
        raise error("Distributed worker failed its authorized operation.") from (
            RuntimeError(f"Worker failure: {failure.category}/{failure.cause_type}")
        )


async def send_packet(connection: Connection, packet):
    connection.process.stdin.write(encode_packet(packet))
    await connection.process.stdin.drain()


async def receive_ready(connection: Connection):
    ready = await read_packet(connection, WorkerReady)
    if (
        ready.worker != connection.assignment.worker
        or ready.pid != connection.process.pid
        or ready.coordinator_pid != connection.assignment.coordinator_pid
        or ready.pid == ready.coordinator_pid
    ):
        raise InvalidRuntimeOutputError("Worker startup identity is invalid.")


async def receive_started(connection: Connection):
    started = await read_packet(connection, WorkerStarted)
    assignment = connection.assignment
    if started != WorkerStarted(
        workflow_id=assignment.workflow_id,
        task_id=assignment.task_id,
        assignment_id=assignment.assignment_id,
        worker=assignment.worker,
        role=assignment.role,
        pid=connection.process.pid,
    ):
        raise InvalidRuntimeOutputError("Worker execution identity is invalid.")


async def release_worker(connection: Connection):
    assignment = connection.assignment
    await send_packet(
        connection,
        WorkerRelease(
            assignment_id=assignment.assignment_id,
            worker=assignment.worker,
            coordinator_pid=assignment.coordinator_pid,
        ),
    )
    connection.process.stdin.close()
    await connection.process.stdin.wait_closed()


async def collect_worker(connection: Connection):
    candidate = await read_packet(connection, WorkerResponse)
    response = validate_response(
        candidate, connection.assignment, connection.process.pid
    )
    if await connection.process.stdout.read(1):
        raise InvalidRuntimeOutputError(
            "Duplicate or extra worker output is forbidden."
        ) from RuntimeError(
            f"Worker {connection.assignment.worker.value} emitted post-result data."
        )
    await connection.process.wait()
    if connection.process.returncode != 0:
        raise ExecutionFailureError("Distributed worker exited unsuccessfully.") from (
            RuntimeError(f"Worker exit code: {connection.process.returncode}")
        )
    return response


async def cleanup_workers(spawning: list, operations: list):
    """Acquire even interrupted spawns, kill all living children, drain and reap."""
    outcomes = await asyncio.gather(*spawning, return_exceptions=True)
    processes = [item for item in outcomes if not isinstance(item, BaseException)]
    for process in processes:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        if process.stdin is not None:
            process.stdin.close()
    for operation in operations:
        if not operation.done():
            operation.cancel()
    await asyncio.gather(*operations, return_exceptions=True)

    async def drain_and_reap(process):
        while await process.stdout.read(4096):
            pass  # Discard bounded transport tail; never retain/log task data.
        await process.wait()

    await asyncio.gather(*(drain_and_reap(process) for process in processes))


async def dispatch_workers(assignments: tuple):
    """Both native ADK agents reach a live barrier before either is released."""
    if len(assignments) != 2:
        raise InvalidRuntimeOutputError("Exactly two worker assignments are required.")
    spawning, operations = [], []

    async def together(coroutines):
        tasks = [asyncio.create_task(item) for item in coroutines]
        operations.extend(tasks)
        return await asyncio.gather(*tasks)

    with TemporaryDirectory(prefix="module06-distributed-") as directory:
        try:
            for assignment in assignments:
                worker_dir = Path(directory, assignment.worker.value)
                worker_dir.mkdir()
                spawning.append(
                    asyncio.create_task(spawn_worker(assignment, str(worker_dir)))
                )
            processes = await asyncio.gather(
                *(asyncio.shield(task) for task in spawning)
            )
            if len({process.pid for process in processes}) != 2:
                raise InvalidRuntimeOutputError("Independent worker PIDs are required.")
            connections = tuple(
                Connection(assignment, process)
                for assignment, process in zip(assignments, processes, strict=True)
            )
            await together(receive_ready(item) for item in connections)
            await together(send_packet(item, item.assignment) for item in connections)
            await together(receive_started(item) for item in connections)
            # Fixed two-worker barrier proves simultaneous native executions in
            # separate processes. Release is coordinator-owned, not task-controlled.
            await together(release_worker(item) for item in connections)
            collectors = [asyncio.create_task(collect_worker(c)) for c in connections]
            operations.extend(collectors)
            completed = []
            for task in asyncio.as_completed(collectors):
                completed.append(await task)
            return tuple(completed), tuple(process.pid for process in processes)
        finally:
            cleanup = asyncio.create_task(cleanup_workers(spawning, operations))
            interrupted = False
            while not cleanup.done():
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    interrupted = True
            cleanup.result()
            if interrupted:
                raise asyncio.CancelledError
