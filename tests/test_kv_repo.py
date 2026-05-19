from sqlmodel import Session

from atlas20.api.repositories import KvRepo


def test_kv_repo_get_set_roundtrip(db_session: Session):
    repo = KvRepo(db_session)

    assert repo.get("theme") is None

    repo.set("theme", "dark")
    assert repo.get("theme") == "dark"

    repo.set("theme", "light")
    assert repo.get("theme") == "light"
