# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""The inventory repository, which is the configuration audit trail."""

from __future__ import annotations

import tarfile
from io import BytesIO
from pathlib import Path

import pytest

from app.inventory.repository import InventoryRepository, StaleWrite


@pytest.fixture
def repository(tmp_path: Path) -> InventoryRepository:
    repository = InventoryRepository(tmp_path / "inventory")
    repository.initialise()
    return repository


def test_initialising_twice_is_harmless(tmp_path: Path) -> None:
    repository = InventoryRepository(tmp_path / "inventory")
    repository.initialise()
    repository.initialise()

    assert repository.exists()
    assert repository.head() is None


def test_a_commit_records_the_operator_who_made_it(
    repository: InventoryRepository,
) -> None:
    commit = repository.commit(
        content="all: {}\n",
        message="network: set gateway_addr on node1",
        author="alice",
    )

    assert commit is not None
    # `git log` answers "who changed the desired state" without anyone having
    # to trust a separate audit log.
    assert commit.author == "alice"
    assert commit.message == "network: set gateway_addr on node1"
    assert repository.head() == commit.hash


def test_committing_the_same_content_twice_creates_no_commit(
    repository: InventoryRepository,
) -> None:
    repository.commit(content="all: {}\n", message="first", author="alice")

    # An empty commit would be noise in the audit trail.
    assert (
        repository.commit(content="all: {}\n", message="again", author="alice") is None
    )


def test_a_write_from_a_stale_read_is_refused(
    repository: InventoryRepository,
) -> None:
    first = repository.commit(content="one\n", message="first", author="alice")
    assert first is not None
    repository.commit(content="two\n", message="second", author="bob")

    # Two operators on two browsers. Refusing beats merging: a silently merged
    # desired state is one nobody reviewed.
    with pytest.raises(StaleWrite, match="changed since you read it"):
        repository.commit(
            content="three\n",
            message="third",
            author="alice",
            expected_head=first.hash,
        )


def test_the_history_is_most_recent_first(repository: InventoryRepository) -> None:
    repository.commit(content="one\n", message="first", author="alice")
    repository.commit(content="two\n", message="second", author="bob")

    history = repository.history()

    assert [commit.message for commit in history] == ["second", "first"]
    assert [commit.author for commit in history] == ["bob", "alice"]


def test_reverting_produces_a_commit_and_does_not_apply_anything(
    repository: InventoryRepository,
) -> None:
    first = repository.commit(content="one\n", message="first", author="alice")
    assert first is not None
    repository.commit(content="two\n", message="second", author="bob")

    reverted = repository.revert(repository.head(), author="alice")

    assert repository.read() == "one\n"
    assert reverted.author == "alice"
    # Rollback is a new commit, never a rewritten history.
    assert len(repository.history()) == 3


def test_reading_an_older_version(repository: InventoryRepository) -> None:
    first = repository.commit(content="one\n", message="first", author="alice")
    assert first is not None
    repository.commit(content="two\n", message="second", author="bob")

    assert repository.read_at(first.hash) == "one\n"


def test_a_candidate_can_be_diffed_without_touching_the_working_tree(
    repository: InventoryRepository,
) -> None:
    repository.commit(content="one\n", message="first", author="alice")

    diff = repository.diff_against("two\n")

    assert "-one" in diff
    assert "+two" in diff
    # The preview is a question, and a question must not change the answer.
    assert repository.read() == "one\n"
    assert not list(repository.path.glob(".*candidate"))


def test_the_export_carries_the_history_a_control_machine_would_want(
    repository: InventoryRepository,
) -> None:
    repository.commit(content="one\n", message="first", author="alice")

    archive = tarfile.open(fileobj=BytesIO(repository.export()), mode="r:gz")
    names = archive.getnames()

    assert "seapath-inventory/inventory.yaml" in names
    # The git directory too: a site taking the inventory to a conventional
    # control machine wants the audit trail, not just the current file.
    assert any(name.startswith("seapath-inventory/.git/") for name in names)
