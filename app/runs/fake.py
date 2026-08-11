# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""A fake Ansible run.

The events below are the real shapes `ansible-runner` emits, trimmed to the
fields this service reads. The whole test suite runs against this, and so does
the development switch, which is what lets the run view be built without a
machine to converge.
"""

from __future__ import annotations

from app.runs.adapter import (
    CancelCheck,
    EventHandler,
    OutputHandler,
    RunOutcome,
    RunRequest,
    prepare,
)


def play_start(play: str = "Detect Seapath distribution") -> dict:
    return {"event": "playbook_on_play_start", "event_data": {"play": play}}


def task_start(task: str, play: str = "Detect Seapath distribution") -> dict:
    return {
        "event": "playbook_on_task_start",
        "event_data": {"task": task, "play": play},
    }


def ok(host: str, task: str, changed: bool = False) -> dict:
    return {
        "event": "runner_on_ok",
        "event_data": {"host": host, "task": task, "res": {"changed": changed}},
    }


def failed(host: str, task: str, message: str) -> dict:
    return {
        "event": "runner_on_failed",
        "event_data": {"host": host, "task": task, "res": {"msg": message}},
    }


def unreachable(host: str, task: str) -> dict:
    return {
        "event": "runner_on_unreachable",
        "event_data": {
            "host": host,
            "task": task,
            "res": {"msg": "Failed to connect to the host via ssh"},
        },
    }


def stats(host: str, ok_count: int = 2, changed: int = 1, failures: int = 0) -> dict:
    return {
        "event": "playbook_on_stats",
        "event_data": {
            "ok": {host: ok_count},
            "changed": {host: changed},
            "failures": {host: failures} if failures else {},
            "dark": {},
            "skipped": {},
            "rescued": {},
        },
    }


def successful_run(host: str = "seapath-machine") -> list[dict]:
    return [
        play_start(),
        task_start("Gather the distribution"),
        ok(host, "Gather the distribution"),
        play_start("Import seapath_setup_network playbook"),
        task_start("Apply the network configuration"),
        ok(host, "Apply the network configuration", changed=True),
        stats(host),
    ]


def failed_run(host: str = "seapath-machine") -> list[dict]:
    return [
        play_start(),
        task_start("Apply the network configuration"),
        failed(host, "Apply the network configuration", "eno1 does not exist"),
        stats(host, ok_count=0, changed=0, failures=1),
    ]


def interrupted_run(host: str = "seapath-machine") -> list[dict]:
    """A run that stops without a recap.

    What happens when the playbook reboots the machine it is running from,
    which `seapath_setup_hardening.yaml` does on every host by design. There is
    no `playbook_on_stats`, and that absence is the signal.
    """
    return [
        play_start(),
        task_start("Restart to configure SEAPATH"),
        ok(host, "Restart to configure SEAPATH", changed=True),
    ]


class FakeRunAdapter:
    """Replays a scripted event stream instead of converging anything."""

    def __init__(
        self,
        events: list[dict] | None = None,
        return_code: int = 0,
        output: str = "PLAY RECAP\n",
    ) -> None:
        self.events = events if events is not None else successful_run()
        self.return_code = return_code
        self.output = output
        self.requests: list[RunRequest] = []

    def execute(
        self,
        request: RunRequest,
        on_event: EventHandler,
        on_output: OutputHandler,
        should_cancel: CancelCheck,
    ) -> RunOutcome:
        self.requests.append(request)
        # Prepared for real, so the configuration a test inspects is the
        # configuration a machine would have been converged with.
        preparation = prepare(request)

        for event in self.events:
            if should_cancel():
                return RunOutcome(
                    return_code=None, command=preparation.command, cancelled=True
                )
            on_event(event)

        on_output(self.output)
        return RunOutcome(return_code=self.return_code, command=preparation.command)
