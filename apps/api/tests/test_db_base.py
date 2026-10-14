from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Parent(Base):
    __tablename__ = "parent"
    id: Mapped[int] = mapped_column(primary_key=True)


class Child(Base, TimestampMixin):
    __tablename__ = "child"
    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("parent.id"))
    name: Mapped[str] = mapped_column(index=True)
    __table_args__ = (UniqueConstraint("parent_id", "name"),)


def test_timestamp_mixin_columns_exist():
    cols = Base.metadata.tables["child"].columns
    assert "created_at" in cols and not cols["created_at"].nullable
    assert "updated_at" in cols and not cols["updated_at"].nullable


def test_constraint_naming_convention_is_applied():
    table = Base.metadata.tables["child"]
    assert any(c.name.startswith("fk_") for c in table.foreign_key_constraints)
    assert any(c.name.startswith("uq_") for c in table.constraints)
    assert any(i.name.startswith("ix_") for i in table.indexes)
