from sqlalchemy import inspect
from sqlmodel import SQLModel, create_engine

from atlas20.api.db.models import IdempotencyKey, KvSetting, ReportFile, Run


def test_db_models_create_expected_tables_in_memory():
    engine = create_engine("sqlite:///:memory:")

    SQLModel.metadata.create_all(engine)

    tables = set(inspect(engine).get_table_names())
    assert {"runs", "report_files", "kv_settings", "idempotency_keys"}.issubset(tables)
    assert Run.__tablename__ == "runs"
    assert ReportFile.__tablename__ == "report_files"
    assert KvSetting.__tablename__ == "kv_settings"
    assert IdempotencyKey.__tablename__ == "idempotency_keys"
