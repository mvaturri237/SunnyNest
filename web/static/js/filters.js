/**
 * SunnyNest Filter Bar — Dropdown Panel Logic
 *
 * Handles:
 * - Pill click → open/close panels
 * - Click outside → close without applying
 * - Escape key → close without applying
 * - Focus trap inside open panels
 * - Price quick-range ↔ min/max sync
 * - Segmented button groups (Beds & Baths)
 * - "More" panel checkboxes + sqft + m² preview
 * - Apply button → update hidden inputs + pill text + active state
 * - Reset all filters
 * - Source multi-select checkboxes
 * - Days Listed radio presets + custom input
 */

(function () {
  "use strict";

  // ── State: snapshot of values before panel opens (for revert on cancel) ──
  let _snapshot = {};

  // ── Helpers ──

  /** Format a price number to compact display: 4000 → "$4K", 6500 → "$6.5K" */
  function fmtPrice(n) {
    if (!n && n !== 0) return "";
    const k = n / 1000;
    // Show one decimal only if needed (e.g. 6.5K but not 5.0K)
    return "$" + (k % 1 === 0 ? k.toFixed(0) : k.toFixed(1)) + "K";
  }

  /** Convert sqft to m² */
  function sqftToM2(sqft) {
    return Math.round(sqft * 0.0929);
  }

  /** Get all focusable elements inside a container */
  function getFocusable(container) {
    return Array.from(
      container.querySelectorAll(
        'button, [href], input:not([type="hidden"]), select, textarea, [tabindex]:not([tabindex="-1"])'
      )
    );
  }

  // ── Panel open / close ──

  function openPanel(dropdown) {
    const pill = dropdown.querySelector(".filter-pill");
    const panel = dropdown.querySelector(".filter-panel");
    if (!panel || !pill) return;

    // Close any other open panels first
    closeAllPanels();

    // Snapshot current hidden input values for revert
    _snapshot = snapshotValues(dropdown.dataset.filter);

    pill.setAttribute("aria-expanded", "true");
    panel.classList.add("open");

    // Focus first input inside panel
    requestAnimationFrame(() => {
      const first = panel.querySelector(
        'input:not([type="hidden"]):not([type="radio"]):not([type="checkbox"]), button.segment-btn.selected, button.filter-apply-btn'
      );
      if (first) first.focus();
    });

    // Add click-outside listener (delayed to avoid catching the opening click)
    requestAnimationFrame(() => {
      document.addEventListener("click", onClickOutside, true);
    });
  }

  function closePanel(dropdown, revert) {
    const pill = dropdown.querySelector(".filter-pill");
    const panel = dropdown.querySelector(".filter-panel");
    if (!panel || !pill) return;

    pill.setAttribute("aria-expanded", "false");
    panel.classList.remove("open");

    if (revert && _snapshot._filterName) {
      revertValues(_snapshot);
    }
    _snapshot = {};

    // Return focus to pill
    pill.focus();

    document.removeEventListener("click", onClickOutside, true);
  }

  function closeAllPanels(revert) {
    document.querySelectorAll(".filter-dropdown").forEach((dd) => {
      const panel = dd.querySelector(".filter-panel");
      if (panel && panel.classList.contains("open")) {
        closePanel(dd, revert);
      }
    });
  }

  // ── Snapshot / Revert (for cancel-on-click-outside) ──

  function snapshotValues(filterName) {
    const snap = { _filterName: filterName };
    if (filterName === "price") {
      snap.min = document.getElementById("filter_price_min").value;
      snap.max = document.getElementById("filter_price_max").value;
    } else if (filterName === "bedsbaths") {
      snap.beds = document.getElementById("filter_beds").value;
      snap.baths = document.getElementById("filter_baths").value;
    } else if (filterName === "source") {
      snap.sourceValue = document.getElementById("filter_source").value;
      snap.zillow = document.getElementById("source-zillow").checked;
      snap.craigslist = document.getElementById("source-craigslist").checked;
      snap.realtor = document.getElementById("source-realtor").checked;
    } else if (filterName === "days") {
      snap.maxDays = document.getElementById("filter-max-days").value;
      snap.daysCustom = document.getElementById("days-custom").value;
      // Snapshot which radio is selected
      var radios = document.querySelectorAll('input[name="days_preset"]');
      snap.daysPreset = "any";
      radios.forEach(function (r) {
        if (r.checked) snap.daysPreset = r.value;
      });
    } else if (filterName === "more") {
      snap.sqftMin = document.getElementById("filter_sqft_min").value;
      snap.sqftMax = document.getElementById("filter_sqft_max").value;
      snap.pet = document.getElementById("filter_pet").value;
      snap.ac = document.getElementById("filter_ac").value;
      snap.furnished = document.getElementById("filter_furnished").value;
      snap.favorites = document.getElementById("filter_favorites").value;
    }
    return snap;
  }

  function revertValues(snap) {
    if (snap._filterName === "price") {
      document.getElementById("filter_price_min").value = snap.min;
      document.getElementById("filter_price_max").value = snap.max;
      // Also revert the panel inputs
      document.getElementById("price-min-input").value = snap.min;
      document.getElementById("price-max-input").value = snap.max;
      syncPriceQuickRange();
    } else if (snap._filterName === "bedsbaths") {
      document.getElementById("filter_beds").value = snap.beds;
      document.getElementById("filter_baths").value = snap.baths;
      // Revert segment buttons
      syncSegmentButtons();
    } else if (snap._filterName === "source") {
      document.getElementById("filter_source").value = snap.sourceValue;
      document.getElementById("source-zillow").checked = snap.zillow;
      document.getElementById("source-craigslist").checked = snap.craigslist;
      document.getElementById("source-realtor").checked = snap.realtor;
      updateSourcePill();
    } else if (snap._filterName === "days") {
      document.getElementById("filter-max-days").value = snap.maxDays;
      document.getElementById("days-custom").value = snap.daysCustom;
      // Revert radio selection
      var radios = document.querySelectorAll('input[name="days_preset"]');
      radios.forEach(function (r) {
        r.checked = r.value === snap.daysPreset;
      });
    } else if (snap._filterName === "more") {
      document.getElementById("filter_sqft_min").value = snap.sqftMin;
      document.getElementById("filter_sqft_max").value = snap.sqftMax;
      document.getElementById("filter_pet").value = snap.pet;
      document.getElementById("filter_ac").value = snap.ac;
      document.getElementById("filter_furnished").value = snap.furnished;
      document.getElementById("filter_favorites").value = snap.favorites;
      // Revert panel inputs
      document.getElementById("sqft-min-input").value = snap.sqftMin;
      document.getElementById("sqft-max-input").value = snap.sqftMax;
      document.getElementById("more-pet").checked = snap.pet === "1";
      document.getElementById("more-ac").checked = snap.ac === "1";
      document.getElementById("more-furnished").checked = snap.furnished === "1";
      document.getElementById("more-favorites").checked = snap.favorites === "1";
      updateSqftPreview();
    }
  }

  // ── Click outside handler ──

  function onClickOutside(e) {
    const openDropdown = document.querySelector(
      ".filter-dropdown .filter-panel.open"
    );
    if (!openDropdown) {
      document.removeEventListener("click", onClickOutside, true);
      return;
    }
    const dropdown = openDropdown.closest(".filter-dropdown");
    if (!dropdown.contains(e.target)) {
      closePanel(dropdown, true);
    }
  }

  // ── Price panel logic ──

  /** Sync quick-range radio selection based on current min/max input values */
  function syncPriceQuickRange() {
    const min = document.getElementById("price-min-input").value.trim();
    const max = document.getElementById("price-max-input").value.trim();
    const radios = document.querySelectorAll('input[name="price_quick"]');

    radios.forEach((r) => {
      const val = r.value;
      let match = false;
      if (val.endsWith("+")) {
        const rMin = val.replace("+", "");
        match = min === rMin && max === "";
      } else {
        const parts = val.split("-");
        if (parts[0] === "0") {
          match = min === "" && max === parts[1];
        } else {
          match = min === parts[0] && max === parts[1];
        }
      }
      r.checked = match;
    });
  }

  function onPriceQuickRangeClick(e) {
    const val = e.target.value;
    const minInput = document.getElementById("price-min-input");
    const maxInput = document.getElementById("price-max-input");

    if (val.endsWith("+")) {
      minInput.value = val.replace("+", "");
      maxInput.value = "";
    } else {
      const parts = val.split("-");
      minInput.value = parts[0] === "0" ? "" : parts[0];
      maxInput.value = parts[1];
    }
  }

  function onPriceInputChange() {
    // Deselect quick range when user types
    syncPriceQuickRange();
  }

  // ── Segmented button groups (Beds & Baths) ──

  function syncSegmentButtons() {
    document.querySelectorAll(".segment-group").forEach((group) => {
      const target = group.dataset.target;
      const currentVal = document.getElementById(target).value;
      group.querySelectorAll(".segment-btn").forEach((btn) => {
        const isSelected = btn.dataset.value === currentVal;
        btn.classList.toggle("selected", isSelected);
        btn.setAttribute("aria-checked", isSelected ? "true" : "false");
        btn.setAttribute("tabindex", isSelected ? "0" : "-1");
      });
    });
  }

  function onSegmentClick(e) {
    const btn = e.target.closest(".segment-btn");
    if (!btn) return;
    const group = btn.closest(".segment-group");
    if (!group) return;

    // Update visual state
    group.querySelectorAll(".segment-btn").forEach((b) => {
      b.classList.remove("selected");
      b.setAttribute("aria-checked", "false");
      b.setAttribute("tabindex", "-1");
    });
    btn.classList.add("selected");
    btn.setAttribute("aria-checked", "true");
    btn.setAttribute("tabindex", "0");
  }

  /** Arrow key navigation within segment groups */
  function onSegmentKeydown(e) {
    const btn = e.target.closest(".segment-btn");
    if (!btn) return;
    const group = btn.closest(".segment-group");
    if (!group) return;

    const buttons = Array.from(group.querySelectorAll(".segment-btn"));
    const idx = buttons.indexOf(btn);
    let next = -1;

    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      next = (idx + 1) % buttons.length;
    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      next = (idx - 1 + buttons.length) % buttons.length;
    }

    if (next >= 0) {
      // Select the new button
      buttons.forEach((b) => {
        b.classList.remove("selected");
        b.setAttribute("aria-checked", "false");
        b.setAttribute("tabindex", "-1");
      });
      buttons[next].classList.add("selected");
      buttons[next].setAttribute("aria-checked", "true");
      buttons[next].setAttribute("tabindex", "0");
      buttons[next].focus();
    }
  }

  // ── More panel: sqft m² preview ──

  function updateSqftPreview() {
    const minVal = document.getElementById("sqft-min-input").value.trim();
    const maxVal = document.getElementById("sqft-max-input").value.trim();
    const preview = document.getElementById("sqft-preview");
    if (!preview) return;

    const minNum = parseInt(minVal, 10);
    const maxNum = parseInt(maxVal, 10);

    if (!isNaN(minNum) && !isNaN(maxNum)) {
      preview.textContent =
        minNum.toLocaleString() +
        "–" +
        maxNum.toLocaleString() +
        " sqft (" +
        sqftToM2(minNum) +
        "–" +
        sqftToM2(maxNum) +
        " m²)";
    } else if (!isNaN(minNum)) {
      preview.textContent =
        minNum.toLocaleString() + "+ sqft (" + sqftToM2(minNum) + "+ m²)";
    } else if (!isNaN(maxNum)) {
      preview.textContent =
        "Up to " +
        maxNum.toLocaleString() +
        " sqft (" +
        sqftToM2(maxNum) +
        " m²)";
    } else {
      preview.textContent = "";
    }
  }

  // ── Apply button handler ──

  function applyFilter(filterName) {
    if (filterName === "price") {
      const min = document.getElementById("price-min-input").value.trim();
      const max = document.getElementById("price-max-input").value.trim();
      document.getElementById("filter_price_min").value = min;
      document.getElementById("filter_price_max").value = max;
      updatePricePill(min, max);
    } else if (filterName === "bedsbaths") {
      // Read selected segment values
      const bedsGroup = document.querySelector(
        '.segment-group[data-target="filter_beds"]'
      );
      const bathsGroup = document.querySelector(
        '.segment-group[data-target="filter_baths"]'
      );
      const bedsVal =
        bedsGroup.querySelector(".segment-btn.selected").dataset.value;
      const bathsVal =
        bathsGroup.querySelector(".segment-btn.selected").dataset.value;
      document.getElementById("filter_beds").value = bedsVal;
      document.getElementById("filter_baths").value = bathsVal;
      updateBedsBathsPill(bedsVal, bathsVal);
    } else if (filterName === "source") {
      // Read checked source checkboxes
      const allSources = ["zillow", "craigslist", "realtor"];
      const checked = allSources.filter(
        (s) => document.getElementById("source-" + s).checked
      );
      // If all checked or none checked, treat as "all" (no filter)
      const value =
        checked.length === allSources.length || checked.length === 0
          ? "all"
          : checked.join(",");
      document.getElementById("filter_source").value = value;
      updateSourcePill();
    } else if (filterName === "days") {
      // Read custom input first (overrides preset)
      var customVal = document.getElementById("days-custom").value.trim();
      if (customVal && parseInt(customVal, 10) > 0) {
        document.getElementById("filter-max-days").value = customVal;
      } else {
        // Read radio preset
        var selectedPreset = "any";
        document.querySelectorAll('input[name="days_preset"]').forEach(function (r) {
          if (r.checked) selectedPreset = r.value;
        });
        document.getElementById("filter-max-days").value =
          selectedPreset === "any" ? "" : selectedPreset;
      }
      updateDaysPill();
    } else if (filterName === "more") {
      const sqftMin = document.getElementById("sqft-min-input").value.trim();
      const sqftMax = document.getElementById("sqft-max-input").value.trim();
      document.getElementById("filter_sqft_min").value = sqftMin;
      document.getElementById("filter_sqft_max").value = sqftMax;
      document.getElementById("filter_pet").value = document.getElementById(
        "more-pet"
      ).checked
        ? "1"
        : "";
      document.getElementById("filter_ac").value = document.getElementById(
        "more-ac"
      ).checked
        ? "1"
        : "";
      document.getElementById("filter_furnished").value =
        document.getElementById("more-furnished").checked ? "1" : "";
      document.getElementById("filter_favorites").value =
        document.getElementById("more-favorites").checked ? "1" : "";
      updateMorePill();
    }

    // Close the panel (no revert — values are committed)
    const dropdown = document.querySelector(
      '.filter-dropdown[data-filter="' + filterName + '"]'
    );
    if (dropdown) {
      _snapshot = {}; // Clear snapshot so close doesn't revert
      closePanel(dropdown, false);

      // Dispatch custom "apply" event on the Apply button to trigger HTMX
      // (hidden inputs are already updated, so HTMX reads correct values)
      const applyBtn = dropdown.querySelector(".filter-apply-btn");
      if (applyBtn) {
        applyBtn.dispatchEvent(new CustomEvent("apply"));
      }
    }
  }

  // ── Pill text updaters ──

  function updatePricePill(min, max) {
    const pill = document.getElementById("pill-price");
    const textEl = pill.querySelector(".filter-pill-text");
    const minNum = parseInt(min, 10);
    const maxNum = parseInt(max, 10);

    if (!isNaN(minNum) && !isNaN(maxNum)) {
      textEl.textContent = fmtPrice(minNum) + "–" + fmtPrice(maxNum);
      pill.classList.add("active");
    } else if (!isNaN(minNum)) {
      textEl.textContent = fmtPrice(minNum) + "+";
      pill.classList.add("active");
    } else if (!isNaN(maxNum)) {
      textEl.textContent = "Under " + fmtPrice(maxNum);
      pill.classList.add("active");
    } else {
      textEl.textContent = textEl.dataset.default;
      pill.classList.remove("active");
    }
  }

  function updateBedsBathsPill(beds, baths) {
    const pill = document.getElementById("pill-bedsbaths");
    const textEl = pill.querySelector(".filter-pill-text");

    const hasBeds = beds && beds !== "any";
    const hasBaths = baths && baths !== "any";

    if (hasBeds && hasBaths) {
      textEl.textContent = beds + "+ bd, " + baths + "+ ba";
      pill.classList.add("active");
    } else if (hasBeds) {
      textEl.textContent = beds + "+ bd";
      pill.classList.add("active");
    } else if (hasBaths) {
      textEl.textContent = baths + "+ ba";
      pill.classList.add("active");
    } else {
      textEl.textContent = textEl.dataset.default;
      pill.classList.remove("active");
    }
  }

  function updateMorePill() {
    const pill = document.getElementById("pill-more");
    const textEl = pill.querySelector(".filter-pill-text");

    // Count active "More" filters
    let count = 0;
    if (document.getElementById("filter_sqft_min").value) count++;
    if (document.getElementById("filter_sqft_max").value) count++;
    if (document.getElementById("filter_pet").value === "1") count++;
    if (document.getElementById("filter_ac").value === "1") count++;
    if (document.getElementById("filter_furnished").value === "1") count++;
    if (document.getElementById("filter_favorites").value === "1") count++;

    if (count > 0) {
      textEl.textContent = "⚙️ More (" + count + ")";
      pill.classList.add("active");
    } else {
      textEl.textContent = textEl.dataset.default;
      pill.classList.remove("active");
    }
  }

  // ── Source multi-select pill updater ──

  /** Source name map for display */
  var _sourceLabels = {
    zillow: "Zillow",
    craigslist: "Craigslist",
    realtor: "Realtor.com",
  };

  function updateSourcePill() {
    var pill = document.getElementById("pill-source");
    if (!pill) return;
    var textEl = pill.querySelector(".filter-pill-text");
    var hiddenVal = document.getElementById("filter_source").value;

    if (!hiddenVal || hiddenVal === "all") {
      textEl.textContent = textEl.dataset.default;
      pill.classList.remove("active");
      return;
    }

    var selected = hiddenVal.split(",").filter(Boolean);
    var allSources = ["zillow", "craigslist", "realtor"];

    if (selected.length === allSources.length) {
      textEl.textContent = textEl.dataset.default;
      pill.classList.remove("active");
    } else if (selected.length === 1) {
      textEl.textContent = "📡 " + (_sourceLabels[selected[0]] || selected[0]);
      pill.classList.add("active");
    } else {
      textEl.textContent = "📡 " + selected.length + " sources";
      pill.classList.add("active");
    }
  }

  // ── Days Listed pill updater ──

  function updateDaysPill() {
    var pill = document.getElementById("pill-days");
    if (!pill) return;
    var textEl = pill.querySelector(".filter-pill-text");
    var val = document.getElementById("filter-max-days").value;

    if (val) {
      textEl.textContent = "📅 ≤ " + val + " days";
      pill.classList.add("active");
    } else {
      textEl.textContent = textEl.dataset.default;
      pill.classList.remove("active");
    }
  }

  // ── Reset all filters ──

  function resetAllFilters() {
    // Reset hidden inputs to defaults
    document.getElementById("filter_price_min").value = "";
    document.getElementById("filter_price_max").value = "";
    document.getElementById("filter_beds").value = "any";
    document.getElementById("filter_baths").value = "any";
    document.getElementById("filter_sqft_min").value = "";
    document.getElementById("filter_sqft_max").value = "";
    document.getElementById("filter_pet").value = "";
    document.getElementById("filter_ac").value = "";
    document.getElementById("filter_furnished").value = "";
    document.getElementById("filter_favorites").value = "";

    // Reset days listed
    var maxDaysInput = document.getElementById("filter-max-days");
    if (maxDaysInput) {
      maxDaysInput.value = "";
      var daysCustom = document.getElementById("days-custom");
      if (daysCustom) daysCustom.value = "";
      document.querySelectorAll('input[name="days_preset"]').forEach(function (r) {
        r.checked = r.value === "any";
      });
      updateDaysPill();
    }

    // Reset source multi-select to all checked
    document.getElementById("filter_source").value = "all";
    var sourceCheckboxes = ["source-zillow", "source-craigslist", "source-realtor"];
    sourceCheckboxes.forEach(function (id) {
      var cb = document.getElementById(id);
      if (cb) cb.checked = true;
    });
    updateSourcePill();

    // Reset sort to newest
    const sortSelect = document.querySelector('select[name="filter_sort"]');
    if (sortSelect) sortSelect.value = "newest";

    // Reset panel inputs
    document.getElementById("price-min-input").value = "";
    document.getElementById("price-max-input").value = "";
    document.getElementById("sqft-min-input").value = "";
    document.getElementById("sqft-max-input").value = "";
    document.getElementById("more-pet").checked = false;
    document.getElementById("more-ac").checked = false;
    document.getElementById("more-furnished").checked = false;
    document.getElementById("more-favorites").checked = false;

    // Deselect all quick ranges
    document
      .querySelectorAll('input[name="price_quick"]')
      .forEach((r) => (r.checked = false));

    // Reset segment buttons to "Any"
    document.querySelectorAll(".segment-group").forEach((group) => {
      group.querySelectorAll(".segment-btn").forEach((btn) => {
        const isAny = btn.dataset.value === "any";
        btn.classList.toggle("selected", isAny);
        btn.setAttribute("aria-checked", isAny ? "true" : "false");
        btn.setAttribute("tabindex", isAny ? "0" : "-1");
      });
    });

    // Reset pill text and active states
    updatePricePill("", "");
    updateBedsBathsPill("any", "any");
    updateMorePill();
    updateSqftPreview();

    // Close the More panel
    _snapshot = {};
    closeAllPanels(false);

    // Fire HTMX request to refresh listings with defaults
    // Dispatch custom "apply" event (matches hx-trigger="apply" on buttons)
    const applyBtn = document.querySelector(
      '.filter-dropdown[data-filter="more"] .filter-apply-btn'
    );
    if (applyBtn) {
      applyBtn.dispatchEvent(new CustomEvent("apply"));
    }
  }

  // ── Focus trap ──

  function trapFocus(e) {
    const openPanel = document.querySelector(".filter-panel.open");
    if (!openPanel) return;

    if (e.key === "Tab") {
      const focusable = getFocusable(openPanel);
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
  }

  // ── Keyboard: Escape to close ──

  function onKeydown(e) {
    if (e.key === "Escape") {
      const openPanel = document.querySelector(".filter-panel.open");
      if (openPanel) {
        const dropdown = openPanel.closest(".filter-dropdown");
        closePanel(dropdown, true);
        e.preventDefault();
      }
    }
    // Focus trap
    trapFocus(e);
  }

  // ── Enter key in price/sqft inputs → Apply ──

  function onInputEnter(e) {
    if (e.key === "Enter") {
      e.preventDefault();
      const panel = e.target.closest(".filter-panel");
      if (panel) {
        const applyBtn = panel.querySelector(".filter-apply-btn");
        if (applyBtn) applyBtn.click();
      }
    }
  }

  // ── Initialization ──

  function init() {
    // Pill click → toggle panel
    document.querySelectorAll(".filter-pill").forEach((pill) => {
      pill.addEventListener("click", (e) => {
        e.stopPropagation();
        const dropdown = pill.closest(".filter-dropdown");
        const panel = dropdown.querySelector(".filter-panel");
        if (panel.classList.contains("open")) {
          closePanel(dropdown, true);
        } else {
          openPanel(dropdown);
        }
      });
    });

    // Apply buttons
    document.querySelectorAll(".filter-apply-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const panelName = btn.dataset.panel;
        if (panelName) {
          applyFilter(panelName);
        }
      });
    });

    // Price quick-range radios
    document.querySelectorAll('input[name="price_quick"]').forEach((radio) => {
      radio.addEventListener("change", onPriceQuickRangeClick);
    });

    // Price min/max inputs — deselect quick range on typing
    const priceMinInput = document.getElementById("price-min-input");
    const priceMaxInput = document.getElementById("price-max-input");
    if (priceMinInput) {
      priceMinInput.addEventListener("input", onPriceInputChange);
      priceMinInput.addEventListener("keydown", onInputEnter);
    }
    if (priceMaxInput) {
      priceMaxInput.addEventListener("input", onPriceInputChange);
      priceMaxInput.addEventListener("keydown", onInputEnter);
    }

    // Segment button clicks
    document.querySelectorAll(".segment-group").forEach((group) => {
      group.addEventListener("click", onSegmentClick);
      group.addEventListener("keydown", onSegmentKeydown);
    });

    // Sqft inputs — update m² preview
    const sqftMinInput = document.getElementById("sqft-min-input");
    const sqftMaxInput = document.getElementById("sqft-max-input");
    if (sqftMinInput) {
      sqftMinInput.addEventListener("input", updateSqftPreview);
      sqftMinInput.addEventListener("keydown", onInputEnter);
    }
    if (sqftMaxInput) {
      sqftMaxInput.addEventListener("input", updateSqftPreview);
      sqftMaxInput.addEventListener("keydown", onInputEnter);
    }

    // Reset all filters
    const resetBtn = document.getElementById("reset-all-filters");
    if (resetBtn) {
      resetBtn.addEventListener("click", resetAllFilters);
    }

    // Days Listed: reset button + custom input Enter key
    var daysResetBtn = document.querySelector('[data-reset="days"]');
    if (daysResetBtn) {
      daysResetBtn.addEventListener("click", function () {
        document.getElementById("filter-max-days").value = "";
        document.getElementById("days-custom").value = "";
        document.querySelectorAll('input[name="days_preset"]').forEach(function (r) {
          r.checked = r.value === "any";
        });
        updateDaysPill();
        // Dispatch apply to refresh listings
        var applyBtn = document.querySelector('.filter-dropdown[data-filter="days"] .filter-apply-btn');
        if (applyBtn) {
          _snapshot = {};
          closePanel(document.querySelector('.filter-dropdown[data-filter="days"]'), false);
          applyBtn.dispatchEvent(new CustomEvent("apply"));
        }
      });
    }

    // Days custom input: clear radio preset when user types
    var daysCustomInput = document.getElementById("days-custom");
    if (daysCustomInput) {
      daysCustomInput.addEventListener("input", function () {
        if (this.value.trim()) {
          // Deselect all radio presets when custom value is entered
          document.querySelectorAll('input[name="days_preset"]').forEach(function (r) {
            r.checked = false;
          });
        }
      });
      daysCustomInput.addEventListener("keydown", onInputEnter);
    }

    // Days radio presets: clear custom input when a preset is selected
    document.querySelectorAll('input[name="days_preset"]').forEach(function (radio) {
      radio.addEventListener("change", function () {
        var customInput = document.getElementById("days-custom");
        if (customInput) customInput.value = "";
      });
    });

    // Source pill: sync initial state from hidden input
    updateSourcePill();

    // Global keyboard handler
    document.addEventListener("keydown", onKeydown);

    // Days Listed pill: sync initial state from hidden input
    updateDaysPill();

    // Initial sync: set quick range if price matches, update sqft preview
    syncPriceQuickRange();
    updateSqftPreview();
    updateMorePill();
  }

  // Run init when DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
