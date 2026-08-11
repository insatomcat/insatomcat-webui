# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""The inventory repository.

A git repository per node, holding the inventory and nothing else. The commit
hash is the version of the desired state, `git log` is the configuration audit
trail, and `git revert` is the rollback. There is no database anywhere in this
service, and this is why one is not needed.

The repository is exportable and clonable as is. A site that decides it wants a
conventional Ansible control machine clones this and loses nothing, which is
the escape hatch that makes the whole design safe to adopt.
"""

from __future__ import annotations

import io
import logging
import os
import subprocess
import tarfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

INVENTORY_FILENAME = "inventory.yaml"

_COMMITTER_NAME = "seapath-webui"
_LOG_FORMAT = "%H%x1f%an%x1f%ae%x1f%aI%x1f%s"


class RepositoryError(Exception):
    """A git operation failed. The message carries git's own words."""


class StaleWrite(Exception):
    """HEAD moved since the caller read it.

    Two operators editing the same inventory from two browsers is the ordinary
    case this prevents, and it prevents it by refusing rather than by merging:
    a silently merged desired state is one nobody reviewed.
    """


@dataclass(frozen=True)
class Commit:
    hash: str
    author: str
    email: str
    timestamp: datetime
    message: str


class InventoryRepository:
    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def inventory_file(self) -> Path:
        return self._path / INVENTORY_FILENAME

    # Lifecycle

    def exists(self) -> bool:
        return (self._path / ".git").is_dir()

    def initialise(self) -> None:
        """Create the repository if this is the first boot. Idempotent."""
        if self.exists():
            return
        self._path.mkdir(parents=True, exist_ok=True)
        self._git("init", "--initial-branch=main")
        logger.info("Initialised the inventory repository at %s", self._path)

    # Reading

    def head(self) -> str | None:
        """The current commit, or None on a repository with no commit yet."""
        try:
            return self._git("rev-parse", "HEAD").strip()
        except RepositoryError:
            return None

    def read(self) -> str:
        try:
            return self.inventory_file.read_text()
        except FileNotFoundError:
            return ""

    def read_at(self, commit: str) -> str:
        return self._git("show", f"{commit}:{INVENTORY_FILENAME}")

    def history(self, limit: int = 50) -> list[Commit]:
        try:
            output = self._git(
                "log", f"--max-count={limit}", f"--pretty=format:{_LOG_FORMAT}"
            )
        except RepositoryError:
            return []
        return [_parse_commit(line) for line in output.splitlines() if line]

    def diff(self, from_ref: str | None = None, to_ref: str | None = None) -> str:
        """A unified diff, defaulting to the working tree against HEAD."""
        if from_ref and to_ref:
            return self._git("diff", from_ref, to_ref, "--", INVENTORY_FILENAME)
        if from_ref:
            return self._git("diff", from_ref, "--", INVENTORY_FILENAME)
        return self._git("diff", "HEAD", "--", INVENTORY_FILENAME)

    def diff_against(self, candidate: str) -> str:
        """What committing this content would change, without writing it.

        The preview an operator sees before an apply. Produced with
        `git diff --no-index` against a temporary file, so the working tree is
        never touched by a question.
        """
        temporary = self._path / f".{INVENTORY_FILENAME}.candidate"
        temporary.write_text(candidate)
        try:
            # --no-index exits 1 when the files differ, which is not an error.
            result = self._run(
                [
                    "git",
                    "diff",
                    "--no-index",
                    "--",
                    INVENTORY_FILENAME if self.inventory_file.exists() else "/dev/null",
                    temporary.name,
                ],
                allowed_returncodes=(0, 1),
            )
            return result.replace(temporary.name, INVENTORY_FILENAME)
        finally:
            temporary.unlink(missing_ok=True)

    # Writing

    def commit(
        self,
        content: str,
        message: str,
        author: str,
        expected_head: str | None = None,
    ) -> Commit | None:
        """Write the inventory and commit it. Returns None when nothing changed.

        `expected_head` is the `If-Match` of the API: a caller that read the
        inventory at one commit and writes back at another is told rather than
        allowed to overwrite a change it never saw.
        """
        self.initialise()
        current = self.head()
        if expected_head is not None and current != expected_head:
            raise StaleWrite(
                f"The inventory changed since you read it. It is now at "
                f"{current or 'no commit'}, you sent {expected_head}."
            )

        if self.inventory_file.exists() and self.inventory_file.read_text() == content:
            return None

        self.inventory_file.write_text(content)
        self._git("add", INVENTORY_FILENAME)
        # The authenticated operator is the author, the service is the
        # committer. `git log` then answers "who changed the desired state"
        # without anyone having to trust a separate audit log.
        self._git(
            "commit",
            "--message",
            message,
            "--author",
            f"{author} <{author}@{_COMMITTER_NAME}>",
        )
        commit = self.history(limit=1)[0]
        logger.info("Inventory commit %s by %s: %s", commit.hash[:12], author, message)
        return commit

    def revert(self, commit: str, author: str) -> Commit:
        """Create a revert commit. It is not applied: that is a separate act."""
        self._git(
            "-c",
            f"user.name={author}",
            "-c",
            f"user.email={author}@{_COMMITTER_NAME}",
            "revert",
            "--no-edit",
            commit,
        )
        return self.history(limit=1)[0]

    def export(self) -> bytes:
        """The whole repository as a tarball, git directory included.

        Git directory included on purpose: what a site wants when it takes the
        inventory to a conventional control machine is the history, not just
        the current file.
        """
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            archive.add(self._path, arcname="seapath-inventory")
        return buffer.getvalue()

    # Plumbing

    def _git(self, *arguments: str) -> str:
        return self._run(["git", *arguments])

    def _run(self, argv: list[str], allowed_returncodes: tuple[int, ...] = (0,)) -> str:
        completed = subprocess.run(  # noqa: S603 - fixed argv, never a shell
            argv,
            cwd=self._path,
            capture_output=True,
            text=True,
            check=False,
            env=self._environment(),
        )
        if completed.returncode not in allowed_returncodes:
            raise RepositoryError(
                (completed.stderr or completed.stdout).strip()
                or f"{' '.join(argv)} failed with {completed.returncode}"
            )
        return completed.stdout

    def _environment(self) -> dict[str, str]:
        environment = dict(os.environ)
        environment.update(
            {
                "GIT_COMMITTER_NAME": _COMMITTER_NAME,
                "GIT_COMMITTER_EMAIL": f"{_COMMITTER_NAME}@localhost",
                # The repository is root owned inside the container and the
                # process is root, but a bind mount can still look dubious to
                # git. This is a repository the service owns outright.
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "safe.directory",
                "GIT_CONFIG_VALUE_0": str(self._path),
            }
        )
        return environment


def _parse_commit(line: str) -> Commit:
    commit_hash, author, email, timestamp, message = line.split("\x1f", 4)
    return Commit(
        hash=commit_hash,
        author=author,
        email=email,
        timestamp=datetime.fromisoformat(timestamp),
        message=message,
    )
