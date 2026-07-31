from numa.memory import InMemoryMemory


def test_in_memory_memory_crud() -> None:
    memory = InMemoryMemory()

    memory.set("answer", 42)

    assert memory.get("answer") == 42
    assert memory.delete("answer") is True
    assert memory.get("answer") is None
    assert memory.delete("answer") is False


def test_delete_reports_stored_none() -> None:
    memory = InMemoryMemory()
    memory.set("nullable", None)

    assert memory.delete("nullable") is True
