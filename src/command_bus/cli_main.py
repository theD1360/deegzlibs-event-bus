"""Unified command-bus CLI with worker and queue admin subcommands."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from . import cli as worker_cli
from .queue_admin import (
    QueueAdminError,
    UnsupportedQueueOperation,
    drain_queue,
    get_message_count,
    load_target,
    purge_queue,
    resolve_queues,
    select_queues,
)


def _add_target_parser(
    parser: argparse.ArgumentParser,
    *,
    help_text: str = "Import path: dotted.module:attribute (default attribute: bus)",
) -> None:
    parser.add_argument(
        "target",
        metavar="TARGET",
        help=help_text,
    )
    parser.add_argument(
        "--queue",
        metavar="NAME",
        default=None,
        help="For WorkerApp / BusGroup targets, operate on this queue label only",
    )


def _cmd_list(args: argparse.Namespace) -> int:
    module, attr_name, target = load_target(args.target)
    descriptors = resolve_queues(module, attr_name, target)
    selected = select_queues(descriptors, args.queue)
    for desc in selected:
        count = get_message_count(desc.adapter)
        count_text = str(count) if count is not None else "n/a"
        print(
            f"{desc.label}\t{desc.bus_kind}\t{desc.adapter_type}\t"
            f"{desc.adapter_queue_name}\t{count_text}"
        )
    return 0


def _cmd_count(args: argparse.Namespace) -> int:
    module, attr_name, target = load_target(args.target)
    descriptors = resolve_queues(module, attr_name, target)
    selected = select_queues(descriptors, args.queue)
    exit_code = 0
    for desc in selected:
        count = get_message_count(desc.adapter)
        if count is None:
            print(
                f"{desc.label}: count unavailable for {desc.adapter_type}",
                file=sys.stderr,
            )
            exit_code = 1
            continue
        print(f"{desc.label}: {count}")
    return exit_code


def _confirm(args: argparse.Namespace, action: str, labels: Sequence[str]) -> bool:
    if args.yes:
        return True
    joined = ", ".join(labels)
    answer = input(f"{action} queue(s) {joined}? [y/N] ").strip().lower()
    return answer in {"y", "yes"}


def _cmd_drain(args: argparse.Namespace) -> int:
    module, attr_name, target = load_target(args.target)
    descriptors = resolve_queues(module, attr_name, target)
    selected = select_queues(descriptors, args.queue)
    if not _confirm(args, "Drain", [d.label for d in selected]):
        print("Aborted.")
        return 1
    for desc in selected:
        removed = drain_queue(desc.adapter, batch_size=args.batch_size)
        print(f"{desc.label}: drained {removed} message(s)")
    return 0


def _cmd_purge(args: argparse.Namespace) -> int:
    module, attr_name, target = load_target(args.target)
    descriptors = resolve_queues(module, attr_name, target)
    selected = select_queues(descriptors, args.queue)
    if not _confirm(args, "Purge", [d.label for d in selected]):
        print("Aborted.")
        return 1
    exit_code = 0
    for desc in selected:
        try:
            removed = purge_queue(desc.adapter)
        except UnsupportedQueueOperation as e:
            print(f"{desc.label}: {e}", file=sys.stderr)
            exit_code = 1
            continue
        print(f"{desc.label}: purged {removed} message(s)")
    return exit_code


def _cmd_worker(args: argparse.Namespace) -> int:
    argv = [args.target]
    if args.queue is not None:
        argv.extend(["--queue", args.queue])
    argv.extend(["--workers", str(args.workers)])
    if args.concurrency is not None:
        argv.extend(["--concurrency", str(args.concurrency)])
    argv.extend(["--poll-interval", str(args.poll_interval)])
    if args.verbose:
        argv.extend(["-v"] * args.verbose)
    worker_cli.main(argv)
    return 0


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        prog="command-bus",
        description="Command-bus worker and queue administration CLI.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list", help="List queues exposed by a target")
    _add_target_parser(list_parser)
    list_parser.set_defaults(func=_cmd_list)

    count_parser = sub.add_parser("count", help="Show pending message counts")
    _add_target_parser(count_parser)
    count_parser.set_defaults(func=_cmd_count)

    drain_parser = sub.add_parser(
        "drain",
        help="Remove messages without dispatching handlers",
    )
    _add_target_parser(drain_parser)
    drain_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip confirmation prompt",
    )
    drain_parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        metavar="N",
        help="Messages fetched per drain iteration (default: 10)",
    )
    drain_parser.set_defaults(func=_cmd_drain)

    purge_parser = sub.add_parser(
        "purge",
        help="Clear a queue using native purge when available",
    )
    _add_target_parser(purge_parser)
    purge_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip confirmation prompt",
    )
    purge_parser.set_defaults(func=_cmd_purge)

    worker_parser = sub.add_parser(
        "worker",
        help="Run worker processes (same as command-bus-worker)",
    )
    _add_target_parser(
        worker_parser,
        help_text="Import path: dotted.module:attribute",
    )
    worker_parser.add_argument("--workers", type=int, default=1, metavar="N")
    worker_parser.add_argument("--concurrency", type=int, default=None, metavar="N")
    worker_parser.add_argument("--poll-interval", type=float, default=0.05, metavar="SECONDS")
    worker_parser.add_argument("-v", "--verbose", action="count", default=0)
    worker_parser.set_defaults(func=_cmd_worker)

    args = parser.parse_args(list(argv) if argv is not None else None)

    if getattr(args, "batch_size", 1) < 1:
        parser.error("--batch-size must be >= 1")
    if getattr(args, "workers", 1) < 1:
        parser.error("--workers must be >= 1")
    if getattr(args, "concurrency", None) is not None and args.concurrency < 1:
        parser.error("--concurrency must be >= 1")

    try:
        code = args.func(args)
    except QueueAdminError as e:
        raise SystemExit(str(e)) from e
    if code:
        raise SystemExit(code)


if __name__ == "__main__":
    main()
