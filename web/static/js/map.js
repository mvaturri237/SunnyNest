/**
 * SunnyNest — Leaflet Map Initialization
 * Sprint 1: Marker clustering, selected state, layer control,
 *           rich popups, card-map bidirectional sync.
 * Sprint 2: POI markers, per-category layer groups, loadPOIs().
 * Sprint 3: Satellite toggle.
 */

/**
 * POI category configuration — colors, icons, and labels.
 */
var POI_CATEGORIES = {
    work:     { color: '#6366f1', icon: '🏢', label: 'Work' },
    school:   { color: '#f59e0b', icon: '🏫', label: 'Schools' },
    park:     { color: '#16a34a', icon: '🌳', label: 'Parks' },
    transit:  { color: '#8b5cf6', icon: '🚉', label: 'Transit' },
    shopping: { color: '#ec4899', icon: '🛒', label: 'Shopping' },
    custom:   { color: '#64748b', icon: '📍', label: 'Custom' }
};

/**
 * Escape a string for safe insertion into HTML.
 * Prevents XSS when building popup content from data attributes.
 */
function escapeHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

/**
 * Format a raw price number into a compact label for map pills.
 * e.g. 5500 → "$5.5K", 6000 → "$6K", null → "N/A"
 */
function formatPriceLabel(price) {
    if (!price || price === 'None') return 'N/A';
    var num = parseFloat(price);
    if (isNaN(num)) return 'N/A';
    var k = num / 1000;
    if (k === Math.floor(k)) return '$' + Math.floor(k) + 'K';
    return '$' + k.toFixed(1) + 'K';
}

document.addEventListener('DOMContentLoaded', function () {
    var mapContainer = document.getElementById('map-container');
    if (!mapContainer) return;

    // Initialize map centered on Sunnyvale, CA
    var map = L.map('map-container', { scrollWheelZoom: false }).setView([37.3688, -122.0363], 12);

    // ----------------------------------------------------------------
    // Base Layers (3.1 — Street + Satellite toggle)
    // ----------------------------------------------------------------
    var osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://openstreetmap.org">OpenStreetMap</a> contributors',
        maxZoom: 19
    }).addTo(map);

    var satelliteLayer = L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        {
            attribution: '&copy; Esri, Maxar, Earthstar Geographics',
            maxZoom: 18
        }
    );

    // ----------------------------------------------------------------
    // Marker Cluster Group (1.1)
    // ----------------------------------------------------------------
    var clusterGroup = L.layerGroup();
    map.addLayer(clusterGroup);

    // ----------------------------------------------------------------
    // Sunnyvale City Boundary Overlay (wrapped in layerGroup for control)
    // ----------------------------------------------------------------
    var boundaryLayer = L.layerGroup().addTo(map);

    fetch('/api/boundary')
        .then(function (r) { return r.json(); })
        .then(function (geojson) {
            L.geoJSON(geojson, {
                style: {
                    color: '#2563eb',
                    weight: 2,
                    opacity: 0.6,
                    fillOpacity: 0.03,
                    dashArray: '6, 4'
                }
            }).addTo(boundaryLayer);
        })
        .catch(function (err) {
            console.warn('Could not load city boundary:', err);
        });

    // ----------------------------------------------------------------
    // POI Layer Groups (2.3) — one per category
    // ----------------------------------------------------------------
    var poiLayerGroups = {};
    Object.keys(POI_CATEGORIES).forEach(function (cat) {
        poiLayerGroups[cat] = L.layerGroup().addTo(map);
    });

    // ----------------------------------------------------------------
    // Layer Control (1.3 + 2.3 POI overlays + 3.1 Satellite)
    // ----------------------------------------------------------------
    var baseLayers = { 'Street': osmLayer, 'Satellite': satelliteLayer };
    var overlays = {
        'Listings': clusterGroup,
        'City Boundary': boundaryLayer
    };
    // Add POI category overlays
    Object.keys(POI_CATEGORIES).forEach(function (cat) {
        var cfg = POI_CATEGORIES[cat];
        overlays[cfg.icon + ' ' + cfg.label] = poiLayerGroups[cat];
    });
    L.control.layers(baseLayers, overlays, { collapsed: true, position: 'topright' }).addTo(map);

    // ----------------------------------------------------------------
    // Marker lookup for card-map sync
    // ----------------------------------------------------------------
    var markersByListingId = {};

    /**
     * Build rich popup HTML from card data attributes (1.4).
     * Gracefully handles missing data (no image, no sqft, etc.).
     */
    function buildPopupHtml(card, label) {
        var address = card.dataset.address || '';
        var beds = card.dataset.beds || '';
        var baths = card.dataset.baths || '';
        var sqft = card.dataset.sqft || '';
        var sqm = card.dataset.sqm || '';
        var imgUrl = card.dataset.img || '';
        var sourceUrl = card.dataset.url || '';
        var sourceName = card.dataset.source || '';

        var specsArr = [];
        if (beds) specsArr.push(beds + ' bd');
        if (baths) specsArr.push(baths + ' ba');
        if (sqft) {
            var sqftFormatted = Number(sqft).toLocaleString();
            specsArr.push(sqftFormatted + ' sqft' + (sqm ? ' (' + sqm + ' m²)' : ''));
        }

        var html = '<div class="map-popup">';
        if (imgUrl && /^https?:\/\//.test(imgUrl)) {
            html += '<img src="' + escapeHtml(imgUrl) + '" class="popup-thumb" alt="" loading="lazy"'
                + ' onerror="this.style.display=\'none\'">';
        }
        html += '<div class="popup-content">';
        html += '<div class="popup-price">' + escapeHtml(label) + '</div>';
        if (address) html += '<div class="popup-address">' + escapeHtml(address) + '</div>';
        if (specsArr.length) html += '<div class="popup-specs">' + escapeHtml(specsArr.join(' · ')) + '</div>';
        if (sourceUrl && /^https?:\/\//.test(sourceUrl)) {
            html += '<a href="' + escapeHtml(sourceUrl) + '" target="_blank" rel="noopener" class="popup-source">'
                + escapeHtml(sourceName ? sourceName.charAt(0).toUpperCase() + sourceName.slice(1) : 'View') + ' ↗</a>';
        }
        html += '</div></div>';
        return html;
    }

    // ----------------------------------------------------------------
    // Deselect all price pills (1.2)
    // ----------------------------------------------------------------
    function deselectAllPills() {
        document.querySelectorAll('.price-pill.selected').forEach(function (p) {
            p.classList.remove('selected');
        });
    }

    // Click empty map area → deselect (1.2)
    // Use setTimeout to let marker click handler fire first and set the flag
    map.on('click', function (e) {
        if (!e.originalEvent._markerClicked) {
            deselectAllPills();
        }
    });

    // ----------------------------------------------------------------
    // Add price pill markers for listings with lat/lng data attributes
    // ----------------------------------------------------------------
    function addMarkers() {
        var cards = document.querySelectorAll('.listing-card[data-lat][data-lng]');
        cards.forEach(function (card) {
            var lat = parseFloat(card.dataset.lat);
            var lng = parseFloat(card.dataset.lng);
            var listingId = card.getAttribute('data-id');
            if (!isNaN(lat) && !isNaN(lng)) {
                var priceEl = card.querySelector('.card-price');
                var priceText = priceEl ? priceEl.textContent.trim() : '';

                // Extract raw price number from formatted text like "$5,500/mo"
                var rawPrice = priceText.replace(/[^0-9.]/g, '');
                var label = formatPriceLabel(rawPrice);

                var icon = L.divIcon({
                    className: 'price-pill-marker',
                    html: '<span class="price-pill">' + label + '</span>',
                    iconSize: [50, 24],
                    iconAnchor: [25, 12]
                });

                var marker = L.marker([lat, lng], { icon: icon });

                // Rich popup (1.4)
                var popupHtml = buildPopupHtml(card, label);
                marker.bindPopup(popupHtml, { maxWidth: 300, className: 'custom-popup' });

                // Add to cluster group instead of directly to map (1.1)
                clusterGroup.addLayer(marker);

                // Store marker for bidirectional sync
                if (listingId) {
                    markersByListingId[listingId] = marker;
                }

                // Click marker → select pill + scroll to card (1.2)
                marker.on('click', function (e) {
                    // Flag to prevent map.on('click') from deselecting
                    if (e.originalEvent) e.originalEvent._markerClicked = true;

                    // Selected state (1.2)
                    deselectAllPills();
                    var el = marker.getElement();
                    if (el) {
                        var pill = el.querySelector('.price-pill');
                        if (pill) pill.classList.add('selected');
                    }

                    // Scroll to card and highlight
                    var targetCard = document.querySelector('.listing-card[data-id="' + listingId + '"]');
                    if (targetCard) {
                        targetCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        targetCard.classList.add('highlighted');
                        setTimeout(function () {
                            targetCard.classList.remove('highlighted');
                        }, 2000);
                    }
                });
            }
        });

        // Fit bounds if we have markers
        if (cards.length > 0) {
            var bounds = [];
            cards.forEach(function (card) {
                var lat = parseFloat(card.dataset.lat);
                var lng = parseFloat(card.dataset.lng);
                if (!isNaN(lat) && !isNaN(lng)) {
                    bounds.push([lat, lng]);
                }
            });
            if (bounds.length > 0) {
                map.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });
            }
        }
    }

    // ----------------------------------------------------------------
    // Card hover → highlight marker
    // ----------------------------------------------------------------
    function bindCardHoverEvents() {
        document.querySelectorAll('.listing-card').forEach(function (card) {
            card.addEventListener('mouseenter', function () {
                var id = this.getAttribute('data-id');
                var marker = markersByListingId[id];
                if (marker) {
                    var el = marker.getElement();
                    if (el) {
                        var pill = el.querySelector('.price-pill');
                        if (pill) pill.classList.add('highlighted');
                    }
                }
            });
            card.addEventListener('mouseleave', function () {
                var id = this.getAttribute('data-id');
                var marker = markersByListingId[id];
                if (marker) {
                    var el = marker.getElement();
                    if (el) {
                        var pill = el.querySelector('.price-pill');
                        if (pill) pill.classList.remove('highlighted');
                    }
                }
            });
        });
    }

    // ----------------------------------------------------------------
    // POI Marker creation (2.3)
    // ----------------------------------------------------------------

    /**
     * Create a Leaflet marker for a single POI.
     */
    function createPOIMarker(poi) {
        var cfg = POI_CATEGORIES[poi.category] || POI_CATEGORIES.custom;
        var icon = L.divIcon({
            className: 'poi-marker',
            html: '<div class="poi-circle" style="background:' + cfg.color + ';"'
                + ' aria-label="' + escapeHtml(cfg.label + ': ' + poi.name) + '">'
                + cfg.icon + '</div>',
            iconSize: [24, 24],
            iconAnchor: [12, 12]
        });

        var marker = L.marker([poi.latitude, poi.longitude], { icon: icon });
        marker.bindTooltip(escapeHtml(poi.name), { direction: 'top', offset: [0, -14] });
        return marker;
    }

    /**
     * Fetch POIs from the API and render them on the map.
     */
    function loadPOIs() {
        fetch('/api/poi')
            .then(function (r) { return r.json(); })
            .then(function (pois) {
                // Clear existing POI markers from all category layers
                Object.keys(poiLayerGroups).forEach(function (cat) {
                    poiLayerGroups[cat].clearLayers();
                });

                // Add markers to per-category layer groups
                pois.forEach(function (poi) {
                    var cat = poi.category || 'custom';
                    var layerGroup = poiLayerGroups[cat] || poiLayerGroups.custom;
                    var marker = createPOIMarker(poi);
                    layerGroup.addLayer(marker);
                });
            })
            .catch(function (err) {
                console.warn('Could not load POIs:', err);
            });
    }

    // ----------------------------------------------------------------
    // Initialise markers
    // ----------------------------------------------------------------
    addMarkers();
    bindCardHoverEvents();
    loadPOIs();

    // Re-add markers after HTMX swaps (when filters change)
    document.body.addEventListener('htmx:afterSwap', function (event) {
        if (event.detail.target && event.detail.target.id === 'listing-cards') {
            // Clear cluster group and marker lookup
            clusterGroup.clearLayers();
            markersByListingId = {};
            deselectAllPills();
            addMarkers();
            bindCardHoverEvents();
        }
        // Refresh POI markers when the POI list is updated (add/delete)
        if (event.detail.target && event.detail.target.id === 'poi-list') {
            loadPOIs();
        }
    });
});
