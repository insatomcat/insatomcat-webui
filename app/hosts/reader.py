# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""The read only host adapter, and the command runner it is built on."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Protocol

from app.hosts.models import (
    CpuReading,
    DisksReading,
    LogReading,
    NetworkReading,
    NodeIdentity,
    PtpClock,
    ServicesReading,
)


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


# The uid a reading runs under when running as root would change its meaning.
# `nobody` on every distribution this service targets, and passed as a number
# so that resolving it is not one more thing that can fail.
UNPRIVILEGED_UID = 65534


class CommandRunner(Protocol):
    """Runs a read only command against the host.

    Injected rather than called directly so that the tests can replay recorded
    output, and so that the set of commands the service is allowed to run stays
    a short, reviewable list in one place.
    """

    def run(
        self, argv: list[str], timeout: float = 5.0, user: int | None = None
    ) -> CommandResult: ...


class SubprocessRunner:
    def run(
        self, argv: list[str], timeout: float = 5.0, user: int | None = None
    ) -> CommandResult:
        try:
            completed = subprocess.run(  # noqa: S603 - fixed argv, never a shell
                argv,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                # None is subprocess's own default, meaning "stay as we are".
                user=user,
            )
        except FileNotFoundError:
            return CommandResult(127, "", f"{argv[0]}: not found in this image")
        except subprocess.TimeoutExpired:
            return CommandResult(124, "", f"{argv[0]}: timed out after {timeout}s")
        except OSError as error:  # pragma: no cover - defensive
            # Includes the case where this process is not root and therefore
            # cannot drop to another uid, which is a developer running the
            # service by hand rather than anything a node will do.
            return CommandResult(1, "", f"{argv[0]}: {error}")
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)


class HostReader(Protocol):
    """Everything the observation views need, and strictly nothing else.

    No method here changes anything. That is not a convention, it is the point:
    a machine is only ever changed by an Ansible run through the other adapter.
    """

    def node_identity(self) -> NodeIdentity: ...

    def cpu(self) -> CpuReading: ...

    def network(self) -> NetworkReading: ...

    def ptp_clocks(self) -> list[PtpClock]: ...

    def services(self, units: list[str]) -> ServicesReading: ...

    def disks(self) -> DisksReading: ...

    def logs(self, unit: str, lines: int) -> LogReading: ...
