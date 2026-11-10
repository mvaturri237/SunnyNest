"""SQLAlchemy data models for the Sunnyvale Rental Finder."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


class ListingSource(Base):
    """Maps a listing to one or more external source records.

    A single physical property (Listing) can have multiple source
    records — one from Zillow, one from Craigslist, etc.

    Attributes:
        id: Auto-increment primary key.
        listing_id: Foreign key to the listings table.
        source: Origin site — ``"zillow"``, ``"craigslist"``, or ``"realtor"``.
        external_id: Source-specific listing identifier.
        url: Direct link to the listing on the source website.
        first_seen: Timestamp when this source record was first discovered.
        last_seen: Timestamp when this source record was last confirmed.
        is_active: Whether this source record is still active.
    """

    __tablename__ = "listing_sources"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    listing_id: int = Column(Integer, ForeignKey("listings.id"), nullable=False, index=True)
    source: str = Column(Text, nullable=False)        # "zillow" | "craigslist"
    external_id: str = Column(Text, nullable=False)    # source-specific ID
    url: str = Column(Text, nullable=False)            # direct link to source listing
    first_seen: datetime = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_seen: datetime = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    is_active: bool = Column(Boolean, nullable=False, default=True)

    listing = relationship("Listing", back_populates="sources")

    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_ls_source_external_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ListingSource(id={self.id}, listing_id={self.listing_id}, "
            f"source={self.source!r}, external_id={self.external_id!r})>"
        )


class Listing(Base):
    """A single rental listing scraped from Zillow or Craigslist.

    Attributes:
        id: Auto-increment primary key.
        external_id: Unique identifier from the source website (DEPRECATED — use ``sources``).
        source: Origin site — ``"zillow"`` or ``"craigslist"`` (DEPRECATED — use ``sources``).
        url: Direct link to the listing page (DEPRECATED — use ``sources``).
        title: Listing headline / title.
        address: Full street address.
        neighborhood: Neighbourhood name (nullable).
        city: City name.
        zip_code: ZIP / postal code.
        price: Monthly rent in USD.
        bedrooms: Number of bedrooms.
        bathrooms: Number of bathrooms (supports halves, e.g. 2.5).
        sqft: Area in square feet (nullable).
        sqm: Area in square metres — auto-calculated from *sqft* (nullable).
        property_type: One of ``house``, ``apartment``, ``condo``, ``townhouse``.
        pet_friendly: Whether pets are allowed (nullable).
        parking: Parking information, e.g. ``"garage"``, ``"street"`` (nullable).
        laundry: Laundry information, e.g. ``"in-unit"``, ``"shared"`` (nullable).
        ac: Whether air conditioning is available (nullable).
        furnished: Whether the unit is furnished (nullable).
        school_district: Linked school-district name (nullable).
        description: Full listing description text (nullable).
        image_urls: JSON-encoded array of image URLs (nullable).
        latitude: Latitude for map pin (nullable).
        longitude: Longitude for map pin (nullable).
        available_date: Move-in availability date (nullable).
        listed_date: Date the listing was posted (nullable).
        first_seen: Timestamp when the scraper first discovered this listing.
        last_seen: Timestamp when the scraper last confirmed this listing.
        days_on_market: Computed days since listed_date (or first_seen). Recalculated each scrape.
        is_active: Whether the listing is still available.
        notified: Whether an email notification has been sent.
    """

    __tablename__ = "listings"

    # --- Primary key ---
    id: int = Column(Integer, primary_key=True, autoincrement=True)

    # --- Identification ---
    external_id: str = Column(Text, nullable=False)
    source: str = Column(Text, nullable=False)  # "zillow" | "craigslist"
    url: str = Column(Text, nullable=False)

    # --- Core details ---
    title: str = Column(Text, nullable=False)
    address: str = Column(Text, nullable=False)
    neighborhood: str | None = Column(Text, nullable=True)
    city: str = Column(Text, nullable=False)
    zip_code: str = Column(Text, nullable=False)

    # --- Pricing & size ---
    price: float = Column(Float, nullable=False)
    bedrooms: int = Column(Integer, nullable=False)
    bathrooms: float = Column(Float, nullable=False)
    sqft: int | None = Column(Integer, nullable=True)
    sqm: float | None = Column(Float, nullable=True)

    # --- Property classification ---
    property_type: str = Column(Text, nullable=False)  # house | apartment | condo | townhouse

    # --- Amenities (all nullable) ---
    pet_friendly: bool | None = Column(Boolean, nullable=True)
    parking: str | None = Column(Text, nullable=True)
    laundry: str | None = Column(Text, nullable=True)
    ac: bool | None = Column(Boolean, nullable=True)
    furnished: bool | None = Column(Boolean, nullable=True)

    # --- Extra info ---
    school_district: str | None = Column(Text, nullable=True)
    school_elementary: str | None = Column(Text, nullable=True)
    school_middle: str | None = Column(Text, nullable=True)
    school_high: str | None = Column(Text, nullable=True)
    description: str | None = Column(Text, nullable=True)
    image_urls: str | None = Column(Text, nullable=True)  # JSON array

    # --- Geolocation ---
    latitude: float | None = Column(Float, nullable=True)
    longitude: float | None = Column(Float, nullable=True)

    # --- Dates ---
    available_date: date | None = Column(Date, nullable=True)
    listed_date: date | None = Column(Date, nullable=True)
    first_seen: datetime = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_seen: datetime = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # --- Analytics ---
    days_on_market: int | None = Column(Integer, nullable=True)
    deactivated_at: datetime | None = Column(DateTime, nullable=True)

    # --- Lifecycle hysteresis (Bug B fix, 2026-06-04) ---
    # ``consecutive_misses`` counts how many scrapes in a row this
    # listing was absent from the source's results. Incremented by
    # :func:`src.database.mark_inactive` when absent, reset to 0 when
    # present. When the counter reaches
    # ``src.database.MARK_INACTIVE_MISS_THRESHOLD`` (= 3 by default,
    # ≈ 3 daily scrapes since the scraper runs once per day), the
    # listing is flipped to ``is_active=False`` and ``deactivated_at``
    # is set. This guards against the non-deterministic RapidAPI Zillow
    # index that was observed dropping zpids on individual scrapes
    # (see [`docs/memory/wiki/entities/zillow-scraper.md`](docs/memory/wiki/entities/zillow-scraper.md)).
    consecutive_misses: int = Column(Integer, nullable=False, default=0, server_default="0")

    # --- Status flags ---
    is_active: bool = Column(Boolean, nullable=False, default=True)
    notified: bool = Column(Boolean, nullable=False, default=False)

    # --- User preferences ---
    is_favorite: bool = Column(Boolean, nullable=False, default=False)
    is_disliked: bool = Column(Boolean, nullable=False, default=False)

    # --- Relationships ---
    price_history = relationship("PriceHistory", back_populates="listing", order_by="PriceHistory.snapshot_date", cascade="all, delete-orphan")
    sources = relationship("ListingSource", back_populates="listing", cascade="all, delete-orphan", order_by="ListingSource.source")

    # --- Constraints ---
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_source_external_id"),
        Index("ix_listings_dedup_candidates", "zip_code", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<Listing(id={self.id}, source={self.source!r}, "
            f"external_id={self.external_id!r}, price={self.price}, "
            f"bedrooms={self.bedrooms}, city={self.city!r})>"
        )


class PriceHistory(Base):
    """Daily price snapshot for a listing.

    One row per listing per day — captures the listing price at each sync
    so we can track price changes over time.

    Attributes:
        id: Auto-increment primary key.
        listing_id: Foreign key to the listings table.
        snapshot_date: The date this price was recorded.
        price: The listing price on this date.
        created_at: Timestamp when this record was created.
    """

    __tablename__ = "price_history"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    listing_id: int = Column(Integer, ForeignKey("listings.id"), nullable=False, index=True)
    snapshot_date: date = Column(Date, nullable=False)
    price: float = Column(Float, nullable=False)
    created_at: datetime = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationship back to Listing
    listing = relationship("Listing", back_populates="price_history")

    __table_args__ = (
        UniqueConstraint("listing_id", "snapshot_date", name="uq_listing_snapshot_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<PriceHistory(id={self.id}, listing_id={self.listing_id}, "
            f"date={self.snapshot_date}, price={self.price})>"
        )


class ApiCallLog(Base):
    """Tracks API calls for rate limiting and usage monitoring.

    Attributes:
        id: Auto-increment primary key.
        service: The API service name (e.g. "zillow").
        called_at: Timestamp of the API call.
        endpoint: The API endpoint called (nullable).
        status_code: HTTP response status code (nullable).
    """

    __tablename__ = "api_call_log"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    service: str = Column(Text, nullable=False, index=True)
    called_at: datetime = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    endpoint: str | None = Column(Text, nullable=True)
    status_code: int | None = Column(Integer, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<ApiCallLog(id={self.id}, service={self.service!r}, "
            f"called_at={self.called_at}, status={self.status_code})>"
        )


class NotificationLog(Base):
    """Tracks notification sends for anti-spam enforcement and auditing.

    Each row represents a single notification dispatch (regardless of
    channel).  The ``success`` flag indicates whether the send succeeded.
    When ``success`` is ``False``, ``error_category`` and
    ``error_message`` provide structured diagnostics so the admin UI can
    surface specific failures (e.g. expired WhatsApp OAuth tokens).

    Attributes:
        id: Auto-increment primary key.
        channel: Notification channel name (e.g. ``"email"``, ``"whatsapp"``).
        sent_at: Timestamp when the notification was sent.
        listing_count: Number of listings included in this notification.
        recipient: The recipient identifier (email address, phone, etc.).
        success: Whether the send was successful.
        error_category: Short machine-readable failure tag (nullable).
            Known values: ``"token_expired"``, ``"auth"``, ``"rate_limited"``,
            ``"network"``, ``"api_error"``, ``"missing_credentials"``,
            ``"unexpected"``.
        error_message: Human-readable failure description (nullable).
    """

    __tablename__ = "notification_log"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    channel: str = Column(Text, nullable=False)
    sent_at: datetime = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    listing_count: int = Column(Integer, nullable=False)
    recipient: str = Column(Text, nullable=False)
    success: bool = Column(Boolean, nullable=False, default=True)
    error_category: str | None = Column(Text, nullable=True)
    error_message: str | None = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<NotificationLog(id={self.id}, channel={self.channel!r}, "
            f"sent_at={self.sent_at}, count={self.listing_count}, "
            f"success={self.success})>"
        )


# ---------------------------------------------------------------------------
# Auto-calculate sqm whenever sqft is set
# ---------------------------------------------------------------------------

@event.listens_for(Listing.sqft, "set")
def _calculate_sqm(target: Listing, value: int | None, _oldvalue: int | None, _initiator: object) -> None:
    """Automatically compute *sqm* from *sqft* using the conversion factor 0.092903."""
    if value is not None:
        target.sqm = round(float(value) * 0.092903, 2)
    else:
        target.sqm = None
