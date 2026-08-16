"""Clean POC SQLAlchemy schema; domain objects remain framework-free."""
from sqlalchemy import Column, ForeignKey, Integer, MetaData, String, Table

metadata = MetaData()
accounts = Table("accounts", metadata, Column("id", String(64), primary_key=True), Column("name", String(300), nullable=False), Column("relationship", String(32), nullable=False), Column("domain", String(300)))
facilities = Table("facilities", metadata, Column("id", String(64), primary_key=True), Column("account_id", ForeignKey("accounts.id"), nullable=False), Column("city", String(120), nullable=False), Column("region", String(64), nullable=False), Column("latitude", String(32), nullable=False), Column("longitude", String(32), nullable=False))
external_ranks = Table("external_industry_ranks", metadata, Column("account_id", ForeignKey("accounts.id"), primary_key=True), Column("industry", String(100), primary_key=True), Column("rank", Integer, nullable=False), Column("source", String(300), nullable=False))
identity_mappings = Table("identity_mappings", metadata, Column("source_key", String(300), primary_key=True), Column("account_id", ForeignKey("accounts.id"), nullable=False))
