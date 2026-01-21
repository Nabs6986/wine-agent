"""Add canonical entity tables for wine catalog.

Revision ID: 0004
Revises: 0003
Create Date: 2025-01-22

This migration adds the canonical wine catalog schema:
- Core entities: producers, wines, vintages
- Reference entities: regions, grape_varieties
- Trade entities: importers, distributors
- Ingestion entities: sources, snapshots, listings, listing_matches
- Provenance: field_provenance

Also adds optional foreign keys to tasting_notes for linking to canonical vintages/wines.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # Reference Entities (created first due to FK dependencies)
    # =========================================================================

    # Create regions table (self-referential for hierarchy)
    op.create_table(
        "regions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("parent_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("aliases_json", sa.Text(), default="[]"),
        sa.Column("country", sa.String(100), default=""),
        sa.Column("wikidata_id", sa.String(20), nullable=True),
        sa.Column("hierarchy_level", sa.String(20), default="region"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_regions_name", "regions", ["name"])
    op.create_index("ix_regions_country", "regions", ["country"])
    op.create_index("ix_regions_parent_id", "regions", ["parent_id"])
    op.create_index("ix_regions_wikidata_id", "regions", ["wikidata_id"])
    # Add self-referential FK after table exists
    op.create_foreign_key(
        "fk_regions_parent_id", "regions", "regions", ["parent_id"], ["id"]
    )

    # Create grape_varieties table
    op.create_table(
        "grape_varieties",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("canonical_name", sa.String(255), nullable=False),
        sa.Column("aliases_json", sa.Text(), default="[]"),
        sa.Column("wikidata_id", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_grape_varieties_canonical_name", "grape_varieties", ["canonical_name"])
    op.create_index("ix_grape_varieties_wikidata_id", "grape_varieties", ["wikidata_id"])

    # =========================================================================
    # Core Wine Entities
    # =========================================================================

    # Create producers table
    op.create_table(
        "producers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("canonical_name", sa.String(255), nullable=False),
        sa.Column("aliases_json", sa.Text(), default="[]"),
        sa.Column("country", sa.String(100), default=""),
        sa.Column("region", sa.String(100), default=""),
        sa.Column("website", sa.String(500), default=""),
        sa.Column("wikidata_id", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_producers_canonical_name", "producers", ["canonical_name"])
    op.create_index("ix_producers_country", "producers", ["country"])
    op.create_index("ix_producers_region", "producers", ["region"])
    op.create_index("ix_producers_wikidata_id", "producers", ["wikidata_id"])

    # Create wines table
    op.create_table(
        "wines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("producer_id", sa.String(36), nullable=False),
        sa.Column("canonical_name", sa.String(255), nullable=False),
        sa.Column("aliases_json", sa.Text(), default="[]"),
        sa.Column("color", sa.String(20), nullable=True),
        sa.Column("style", sa.String(20), nullable=True),
        sa.Column("grapes_json", sa.Text(), default="[]"),
        sa.Column("appellation", sa.String(255), default=""),
        sa.Column("region_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_wines_producer_id", "wines", ["producer_id"])
    op.create_index("ix_wines_canonical_name", "wines", ["canonical_name"])
    op.create_index("ix_wines_appellation", "wines", ["appellation"])
    op.create_index("ix_wines_region_id", "wines", ["region_id"])
    op.create_foreign_key("fk_wines_producer_id", "wines", "producers", ["producer_id"], ["id"])
    op.create_foreign_key("fk_wines_region_id", "wines", "regions", ["region_id"], ["id"])

    # Create vintages table
    op.create_table(
        "vintages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("wine_id", sa.String(36), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("bottle_size_ml", sa.Integer(), default=750),
        sa.Column("abv", sa.Float(), nullable=True),
        sa.Column("tech_sheet_attrs_json", sa.Text(), default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_vintages_wine_id", "vintages", ["wine_id"])
    op.create_index("ix_vintages_year", "vintages", ["year"])
    op.create_foreign_key("fk_vintages_wine_id", "vintages", "wines", ["wine_id"], ["id"])

    # =========================================================================
    # Trade Entities
    # =========================================================================

    # Create importers table
    op.create_table(
        "importers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("canonical_name", sa.String(255), nullable=False),
        sa.Column("country", sa.String(100), default=""),
        sa.Column("website", sa.String(500), default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_importers_canonical_name", "importers", ["canonical_name"])
    op.create_index("ix_importers_country", "importers", ["country"])

    # Create distributors table
    op.create_table(
        "distributors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("canonical_name", sa.String(255), nullable=False),
        sa.Column("country", sa.String(100), default=""),
        sa.Column("website", sa.String(500), default=""),
        sa.Column("regions_served_json", sa.Text(), default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_distributors_canonical_name", "distributors", ["canonical_name"])
    op.create_index("ix_distributors_country", "distributors", ["country"])

    # =========================================================================
    # Ingestion Entities
    # =========================================================================

    # Create sources table
    op.create_table(
        "sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("domain", sa.String(255), nullable=False, unique=True),
        sa.Column("adapter_type", sa.String(50), nullable=False),
        sa.Column("rate_limit_config_json", sa.Text(), default='{"requests_per_second": 1.0, "burst_limit": 5}'),
        sa.Column("allowlist_json", sa.Text(), default="[]"),
        sa.Column("denylist_json", sa.Text(), default="[]"),
        sa.Column("enabled", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_sources_domain", "sources", ["domain"])

    # Create snapshots table
    op.create_table(
        "snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("mime_type", sa.String(100), default="text/html"),
        sa.Column("file_path", sa.Text(), default=""),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), default="pending"),
    )
    op.create_index("ix_snapshots_source_id", "snapshots", ["source_id"])
    op.create_index("ix_snapshots_content_hash", "snapshots", ["content_hash"])
    op.create_index("ix_snapshots_fetched_at", "snapshots", ["fetched_at"])
    op.create_foreign_key("fk_snapshots_source_id", "snapshots", "sources", ["source_id"], ["id"])

    # Create listings table
    op.create_table(
        "listings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("snapshot_id", sa.String(36), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(500), default=""),
        sa.Column("sku", sa.String(100), nullable=True),
        sa.Column("upc", sa.String(20), nullable=True),
        sa.Column("ean", sa.String(20), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(10), default="USD"),
        sa.Column("parsed_fields_json", sa.Text(), default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_listings_source_id", "listings", ["source_id"])
    op.create_index("ix_listings_snapshot_id", "listings", ["snapshot_id"])
    op.create_index("ix_listings_sku", "listings", ["sku"])
    op.create_index("ix_listings_upc", "listings", ["upc"])
    op.create_index("ix_listings_ean", "listings", ["ean"])
    op.create_index("ix_listings_created_at", "listings", ["created_at"])
    op.create_foreign_key("fk_listings_source_id", "listings", "sources", ["source_id"], ["id"])
    op.create_foreign_key("fk_listings_snapshot_id", "listings", "snapshots", ["snapshot_id"], ["id"])

    # Create listing_matches table
    op.create_table(
        "listing_matches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("listing_id", sa.String(36), nullable=False),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("decision", sa.String(20), default="auto"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_listing_matches_listing_id", "listing_matches", ["listing_id"])
    op.create_index("ix_listing_matches_entity_id", "listing_matches", ["entity_id"])
    op.create_foreign_key("fk_listing_matches_listing_id", "listing_matches", "listings", ["listing_id"], ["id"])

    # =========================================================================
    # Provenance Tracking
    # =========================================================================

    # Create field_provenance table
    op.create_table(
        "field_provenance",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("field_path", sa.String(100), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("extractor_version", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("snapshot_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_field_provenance_entity_type", "field_provenance", ["entity_type"])
    op.create_index("ix_field_provenance_entity_id", "field_provenance", ["entity_id"])
    op.create_index("ix_field_provenance_source_id", "field_provenance", ["source_id"])
    op.create_index("ix_field_provenance_snapshot_id", "field_provenance", ["snapshot_id"])
    op.create_foreign_key("fk_field_provenance_source_id", "field_provenance", "sources", ["source_id"], ["id"])
    op.create_foreign_key("fk_field_provenance_snapshot_id", "field_provenance", "snapshots", ["snapshot_id"], ["id"])

    # =========================================================================
    # Add FK columns to tasting_notes (optional links to canonical entities)
    # =========================================================================

    op.add_column("tasting_notes", sa.Column("vintage_id", sa.String(36), nullable=True))
    op.add_column("tasting_notes", sa.Column("wine_id", sa.String(36), nullable=True))
    op.create_index("ix_tasting_notes_vintage_id", "tasting_notes", ["vintage_id"])
    op.create_index("ix_tasting_notes_wine_id", "tasting_notes", ["wine_id"])
    op.create_foreign_key("fk_tasting_notes_vintage_id", "tasting_notes", "vintages", ["vintage_id"], ["id"])
    op.create_foreign_key("fk_tasting_notes_wine_id", "tasting_notes", "wines", ["wine_id"], ["id"])


def downgrade() -> None:
    # Remove FK columns from tasting_notes
    op.drop_constraint("fk_tasting_notes_wine_id", "tasting_notes", type_="foreignkey")
    op.drop_constraint("fk_tasting_notes_vintage_id", "tasting_notes", type_="foreignkey")
    op.drop_index("ix_tasting_notes_wine_id", table_name="tasting_notes")
    op.drop_index("ix_tasting_notes_vintage_id", table_name="tasting_notes")
    op.drop_column("tasting_notes", "wine_id")
    op.drop_column("tasting_notes", "vintage_id")

    # Drop field_provenance
    op.drop_constraint("fk_field_provenance_snapshot_id", "field_provenance", type_="foreignkey")
    op.drop_constraint("fk_field_provenance_source_id", "field_provenance", type_="foreignkey")
    op.drop_index("ix_field_provenance_snapshot_id", table_name="field_provenance")
    op.drop_index("ix_field_provenance_source_id", table_name="field_provenance")
    op.drop_index("ix_field_provenance_entity_id", table_name="field_provenance")
    op.drop_index("ix_field_provenance_entity_type", table_name="field_provenance")
    op.drop_table("field_provenance")

    # Drop listing_matches
    op.drop_constraint("fk_listing_matches_listing_id", "listing_matches", type_="foreignkey")
    op.drop_index("ix_listing_matches_entity_id", table_name="listing_matches")
    op.drop_index("ix_listing_matches_listing_id", table_name="listing_matches")
    op.drop_table("listing_matches")

    # Drop listings
    op.drop_constraint("fk_listings_snapshot_id", "listings", type_="foreignkey")
    op.drop_constraint("fk_listings_source_id", "listings", type_="foreignkey")
    op.drop_index("ix_listings_created_at", table_name="listings")
    op.drop_index("ix_listings_ean", table_name="listings")
    op.drop_index("ix_listings_upc", table_name="listings")
    op.drop_index("ix_listings_sku", table_name="listings")
    op.drop_index("ix_listings_snapshot_id", table_name="listings")
    op.drop_index("ix_listings_source_id", table_name="listings")
    op.drop_table("listings")

    # Drop snapshots
    op.drop_constraint("fk_snapshots_source_id", "snapshots", type_="foreignkey")
    op.drop_index("ix_snapshots_fetched_at", table_name="snapshots")
    op.drop_index("ix_snapshots_content_hash", table_name="snapshots")
    op.drop_index("ix_snapshots_source_id", table_name="snapshots")
    op.drop_table("snapshots")

    # Drop sources
    op.drop_index("ix_sources_domain", table_name="sources")
    op.drop_table("sources")

    # Drop distributors
    op.drop_index("ix_distributors_country", table_name="distributors")
    op.drop_index("ix_distributors_canonical_name", table_name="distributors")
    op.drop_table("distributors")

    # Drop importers
    op.drop_index("ix_importers_country", table_name="importers")
    op.drop_index("ix_importers_canonical_name", table_name="importers")
    op.drop_table("importers")

    # Drop vintages
    op.drop_constraint("fk_vintages_wine_id", "vintages", type_="foreignkey")
    op.drop_index("ix_vintages_year", table_name="vintages")
    op.drop_index("ix_vintages_wine_id", table_name="vintages")
    op.drop_table("vintages")

    # Drop wines
    op.drop_constraint("fk_wines_region_id", "wines", type_="foreignkey")
    op.drop_constraint("fk_wines_producer_id", "wines", type_="foreignkey")
    op.drop_index("ix_wines_region_id", table_name="wines")
    op.drop_index("ix_wines_appellation", table_name="wines")
    op.drop_index("ix_wines_canonical_name", table_name="wines")
    op.drop_index("ix_wines_producer_id", table_name="wines")
    op.drop_table("wines")

    # Drop producers
    op.drop_index("ix_producers_wikidata_id", table_name="producers")
    op.drop_index("ix_producers_region", table_name="producers")
    op.drop_index("ix_producers_country", table_name="producers")
    op.drop_index("ix_producers_canonical_name", table_name="producers")
    op.drop_table("producers")

    # Drop grape_varieties
    op.drop_index("ix_grape_varieties_wikidata_id", table_name="grape_varieties")
    op.drop_index("ix_grape_varieties_canonical_name", table_name="grape_varieties")
    op.drop_table("grape_varieties")

    # Drop regions
    op.drop_constraint("fk_regions_parent_id", "regions", type_="foreignkey")
    op.drop_index("ix_regions_wikidata_id", table_name="regions")
    op.drop_index("ix_regions_parent_id", table_name="regions")
    op.drop_index("ix_regions_country", table_name="regions")
    op.drop_index("ix_regions_name", table_name="regions")
    op.drop_table("regions")
