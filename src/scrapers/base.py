"""Abstract base class for all rental listing scrapers."""

import logging
import ssl
from abc import ABC, abstractmethod
from pathlib import Path

import certifi

logger = logging.getLogger("rental_finder.scrapers.base")

# Path to the Palo Alto Networks Enterprise Root CA, exported from the
# macOS System Keychain.  When present, it is loaded into the SSL context
# so that connections through a GlobalProtect TLS-decryption proxy succeed.
_PANW_CA_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "certs" / "panw-root-ca.pem"
)


class BaseScraper(ABC):
    """Base interface that every scraper must implement.

    Subclasses are responsible for fetching raw listing data from a
    specific source and normalizing it into a dict that matches the
    :class:`~src.models.Listing` model fields.
    """

    # ------------------------------------------------------------------
    # Shared SSL helper
    # ------------------------------------------------------------------

    @staticmethod
    def _build_ssl_context() -> ssl.SSLContext:
        """Build an SSL context suitable for RapidAPI requests.

        The context:
        * Uses certifi's CA bundle as the trust base.
        * Loads the PANW Enterprise Root CA on top (if the PEM file
          exists) so that connections through a Palo Alto Networks
          GlobalProtect TLS-decryption proxy are trusted.
        * Clears the ``VERIFY_X509_STRICT`` flag — the decrypt proxy
          generates leaf certificates that lack the Authority Key
          Identifier (AKI) extension, which OpenSSL ≥ 3.6 rejects
          under strict mode.
        * Preserves ``verify_mode=CERT_REQUIRED`` and
          ``check_hostname=True`` — full chain validation is still
          enforced.

        Returns:
            A configured :class:`ssl.SSLContext`.
        """
        ctx = ssl.create_default_context(cafile=certifi.where())

        if _PANW_CA_PATH.exists():
            ctx.load_verify_locations(cafile=str(_PANW_CA_PATH))
            logger.info(
                "Loaded PANW Enterprise Root CA for TLS decryption proxy (%s)",
                _PANW_CA_PATH,
            )

        # OpenSSL 3.6+ rejects leaf certs missing AKI under strict mode.
        # Clear the flag while keeping all other security properties.
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT

        return ctx

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def scrape(self) -> list[dict]:
        """Scrape listings and return raw data dicts.

        Returns:
            A list of raw dictionaries, each representing a single
            listing as returned by the source website.
        """
        pass

    @abstractmethod
    def normalize(self, raw: dict) -> dict | None:
        """Normalize a raw data dict to match Listing model fields.

        Args:
            raw: A single raw listing dictionary produced by
                :meth:`scrape`.

        Returns:
            A dictionary whose keys correspond to
            :class:`~src.models.Listing` column names, OR ``None`` to
            signal the orchestrator to skip this raw item entirely
            (e.g. status validation failed — see Zillow Bug A,
            2026-06-04). Callers MUST check for ``None`` before
            dereferencing.
        """
        pass
