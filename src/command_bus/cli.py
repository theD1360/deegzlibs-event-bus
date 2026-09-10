"""Run CommandBus.work() from a user module with one OS process per worker."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import logging
import multiprocessing
import signal
import sys
import time
from typing import Any, List, Optional, Sequence, Tuple, Union

from .adapters.queue.in_memory import InMemoryQueueAdapter
from .bus import CommandBus
from .command_bus_group import BusGroup, CommandBusGroup, resolve_bus_attr_on_module
from .event_bus import EventBus
from .worker_app import WorkerApp

logger = logging.getLogger(__name__)

_DEFAULT_BUS_ATTR = "bus"
_BUS_TYPES = (CommandBus, EventBus)
_WORKER_TARGET_TYPES = (CommandBus, EventBus, WorkerApp)


def _parse_target(spec: str) -> Tuple[str, str]:
    """
    Parse ``dotted.module`` or ``dotted.module:attribute``.

    If ``:attribute`` is omitted, the attribute defaults to ``bus``.
    """
    spec = spec.strip()
    if not spec:
        raise SystemExit("Target must be a non-empty module path or module:attribute")
    if ":" in spec:
        mod_part, _, attr = spec.rpartition(":")
        mod_part = mod_part.strip()
        attr = attr.strip()
        if not mod_part or not attr:
            raise SystemExit(
                f"Invalid target {spec!r}; use dotted.module:attribute "
                f"(e.g. myapp.worker:bus or myapp.worker:command_bus_group)"
            )
        return mod_part, attr
    return spec, _DEFAULT_BUS_ATTR


def _resolve_single_bus(module: object, bus_attr: str) -> Tuple[str, Any]:
    """Validate ``module.bus_attr`` is a CommandBus or EventBus; return (attr, instance)."""
    obj = getattr(module, bus_attr, None)
    if obj is None:
        raise SystemExit(f"Module has no attribute {bus_attr!r}")
    if not isinstance(obj, _BUS_TYPES):
        raise SystemExit(
            f"Attribute {bus_attr!r} is not a CommandBus or EventBus "
            f"(got {type(obj).__name__})"
        )
    return bus_attr, obj


def _worker_jobs(bus_attr: str, workers: int) -> List[Tuple[str, int]]:
    """One forked process per (bus attribute, worker index)."""
    return [(bus_attr, w) for w in range(1, workers + 1)]


def _is_benign_worker_exit(exitcode: Optional[int]) -> bool:
    """Treat clean exit and typical terminate/kill signals as non-fatal."""
    if exitcode is None or exitcode == 0:
        return True
    if sys.platform != "win32" and exitcode < 0:
        sig = -exitcode
        if sig in (signal.SIGTERM, signal.SIGINT):
            return True
    return False


def _get_multiprocessing_context() -> multiprocessing.context.BaseContext:
    """POSIX uses fork (separate interpreters, no shared GIL); Windows uses spawn."""
    if sys.platform == "win32":
        return multiprocessing.get_context("spawn")
    return multiprocessing.get_context("fork")


def _queue_name_for_target(target: Union[CommandBus, EventBus, WorkerApp], attr: str) -> str:
    if isinstance(target, WorkerApp):
        return getattr(target.queue_adapter, "queue_name", attr)
    return getattr(target.queue_adapter, "queue_name", attr)


async def _do_work(
    target: Union[CommandBus, EventBus, WorkerApp],
    concurrency: int,
) -> int:
    if isinstance(target, WorkerApp):
        return await target.work(concurrency=concurrency)
    return await target.work(concurrency=concurrency)


def _process_worker_main(
    module_name: str,
    bus_attr: str,
    worker_num: int,
    poll_interval: float,
    log_level: int,
    concurrency: int,
) -> None:
    """Entry point for each worker process (import module, run work loop)."""
    # Foreground process group delivers SIGINT to all workers; parent coordinates shutdown.
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except (ValueError, OSError):
        pass

    stop = False

    def _on_term(signum: int, frame: Any) -> None:
        nonlocal stop
        stop = True

    try:
        signal.signal(signal.SIGTERM, _on_term)
    except (ValueError, OSError):
        pass

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    wlog = logging.getLogger("command_bus.cli.worker")

    try:
        mod = importlib.import_module(module_name)
    except ImportError as e:
        wlog.error("Failed to import %r: %s", module_name, e)
        sys.exit(1)

    target = getattr(mod, bus_attr, None)
    if not isinstance(target, _WORKER_TARGET_TYPES):
        wlog.error(
            "Attribute %r is not a CommandBus, EventBus, or WorkerApp",
            bus_attr,
        )
        sys.exit(1)

    name = f"{bus_attr}:{worker_num}"
    qn = _queue_name_for_target(target, bus_attr)
    wlog.info(
        "Worker started for %r (queue_name=%s, concurrency=%d)",
        bus_attr,
        qn,
        concurrency,
    )

    async def _loop() -> None:
        while not stop:
            try:
                await _do_work(target, concurrency)
            except asyncio.CancelledError:
                raise
            except Exception:
                wlog.exception("%s: work() failed", name)
            if stop:
                break
            if poll_interval > 0:
                deadline = time.monotonic() + poll_interval
                while time.monotonic() < deadline and not stop:
                    await asyncio.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
            else:
                await asyncio.sleep(0)

    try:
        asyncio.run(_loop())
    finally:
        wlog.info("Worker %s exiting", name)


def _supervise_worker_processes(processes: List[multiprocessing.Process]) -> None:
    """Block until all workers finish; on SIGINT/SIGTERM terminate children."""
    shutting_down = False

    def _request_shutdown(signum: int, frame: Any) -> None:
        # Keep minimal work here (no join/logging) to avoid deadlocks in the handler.
        nonlocal shutting_down
        shutting_down = True

    old: List[Tuple[int, Any]] = []
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            old.append((sig, signal.signal(sig, _request_shutdown)))
        except ValueError:
            pass

    try:
        while True:
            if shutting_down:
                logger.info("Terminating workers...")
                for p in processes:
                    if p.is_alive():
                        p.terminate()
                for p in processes:
                    p.join(timeout=30)
                break

            alive = [p for p in processes if p.is_alive()]
            if not alive:
                break
            for p in alive:
                p.join(timeout=0.5)

            for p in processes:
                if p.is_alive():
                    continue
                code = p.exitcode
                if not _is_benign_worker_exit(code):
                    logger.error(
                        "Worker name=%r pid=%s exited with code %s",
                        p.name,
                        p.pid,
                        code,
                    )
                    shutting_down = True
                    for q in processes:
                        if q.is_alive():
                            q.terminate()
                    for q in processes:
                        q.join(timeout=30)
                    raise SystemExit(int(code) if code and code > 0 else 1)
    finally:
        for p in processes:
            if p.is_alive():
                p.terminate()
                p.join(timeout=15)
        for sig, handler in old:
            try:
                signal.signal(sig, handler)
            except ValueError:
                pass


def _run_worker_processes(
    module_name: str,
    jobs: List[Tuple[str, int]],
    poll_interval: float,
    log_level: int,
    concurrency: int,
) -> None:
    ctx = _get_multiprocessing_context()
    method = ctx.get_start_method()
    logger.info("Multiprocessing start method: %s (%d worker process(es))", method, len(jobs))

    processes: List[multiprocessing.Process] = []
    for bus_attr, worker_num in jobs:
        proc = ctx.Process(
            target=_process_worker_main,
            args=(module_name, bus_attr, worker_num, poll_interval, log_level, concurrency),
            name=f"command-bus-{bus_attr}-{worker_num}",
        )
        proc.start()
        processes.append(proc)

    _supervise_worker_processes(processes)


def main(argv: Optional[Sequence[str]] = None) -> None:
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(
        description=(
            "Run CommandBus/EventBus/WorkerApp.work() in worker processes "
            "(fork on POSIX, spawn on Windows). "
            "Target is module:attribute like uvicorn — e.g. myapp.worker:app, "
            "myapp.worker:bus, or myapp.worker:command_bus_group. "
            "If :attribute is omitted, :bus is assumed."
        )
    )
    parser.add_argument(
        "target",
        metavar="TARGET",
        help=(
            "Import path and object: dotted.module:attribute. "
            "Attribute must be a CommandBus, EventBus, WorkerApp, or BusGroup. "
            "Omit :attribute to use attribute name 'bus' (e.g. myapp.worker is myapp.worker:bus)."
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        metavar="N",
        help=(
            "Process count for a single CommandBus, EventBus, or WorkerApp. "
            "For BusGroup, default count when WorkerConfig.workers is omitted (default: 1)"
        ),
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        metavar="N",
        help=(
            "In-process parallel message dispatch per worker process. "
            "For WorkerApp, defaults to the app's concurrency when omitted (default: 1 otherwise)"
        ),
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.05,
        metavar="SECONDS",
        help="Sleep after each work() tick when idle (reduces CPU spin); 0 disables (default: 0.05)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase logging (repeat for DEBUG)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    log_level = logging.WARNING
    if args.verbose == 1:
        log_level = logging.INFO
    elif args.verbose >= 2:
        log_level = logging.DEBUG
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if args.workers < 1:
        parser.error("--workers must be >= 1")
    if args.concurrency is not None and args.concurrency < 1:
        parser.error("--concurrency must be >= 1")

    module_name, attr_name = _parse_target(args.target)

    try:
        mod = importlib.import_module(module_name)
    except ImportError as e:
        raise SystemExit(f"Failed to import {module_name!r}: {e}") from e

    obj = getattr(mod, attr_name, None)
    if obj is None:
        raise SystemExit(f"Module {module_name!r} has no attribute {attr_name!r}")

    if isinstance(obj, WorkerApp):
        concurrency = args.concurrency if args.concurrency is not None else obj.concurrency
        if isinstance(obj.queue_adapter, InMemoryQueueAdapter) and args.workers > 1:
            logger.warning(
                "InMemoryQueueAdapter is process-local; each of %d worker processes "
                "will have its own queue. Use a shared backend (SQS, Redis, RabbitMQ) "
                "for multi-process workers, or run with --workers 1.",
                args.workers,
            )
    elif args.concurrency is not None:
        concurrency = args.concurrency
    else:
        concurrency = 1

    if isinstance(obj, (BusGroup, CommandBusGroup)):
        obj.validate(mod)
        jobs = obj.iter_jobs(mod, args.workers)
        for cfg in obj.configs:
            n = cfg.workers if cfg.workers is not None else args.workers
            bus = cfg.bus
            attr = resolve_bus_attr_on_module(mod, bus)
            qn = getattr(bus.queue_adapter, "queue_name", attr)
            logger.info(
                "Launching %d process(es) for %s (queue_name=%s)",
                n,
                attr,
                qn,
            )
    elif isinstance(obj, _WORKER_TARGET_TYPES):
        jobs = _worker_jobs(attr_name, args.workers)
        qn = _queue_name_for_target(obj, attr_name)
        logger.info(
            "Launching %d process(es) for %s:%s (queue_name=%s, concurrency=%d)",
            args.workers,
            module_name,
            attr_name,
            qn,
            concurrency,
        )
    else:
        raise SystemExit(
            f"Attribute {attr_name!r} must be a CommandBus, EventBus, WorkerApp, or BusGroup "
            f"(got {type(obj).__name__})"
        )

    try:
        _run_worker_processes(
            module_name,
            jobs,
            max(0.0, args.poll_interval),
            log_level,
            concurrency,
        )
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
