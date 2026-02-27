/**
 * Client-side filtering for browse pages.
 * Reads dropdown selections and filters dataset rows by data attributes.
 * Shows active filter chips and updates result count live.
 */
(function () {
  "use strict";

  var formatSelect = document.getElementById("filter-format");
  var publisherSelect = document.getElementById("filter-publisher");
  var tagSelect = document.getElementById("filter-tag");
  var jurisdictionSelect = document.getElementById("filter-jurisdiction");
  var clearBtn = document.getElementById("clear-filters");
  var resultCount = document.getElementById("result-count");
  var chipsContainer = document.getElementById("filter-chips");
  var rows = document.querySelectorAll(".dataset-row");

  if (!formatSelect || !rows.length) return;

  /**
   * Apply all active filters to dataset rows.
   * Hides rows that do not match and updates the result count.
   */
  function applyFilters() {
    var formatVal = formatSelect.value.toLowerCase();
    var publisherVal = publisherSelect.value.toLowerCase();
    var tagVal = tagSelect.value.toLowerCase();
    var jurisdictionVal = jurisdictionSelect ? jurisdictionSelect.value.toLowerCase() : "";
    var visibleCount = 0;

    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      var rowFormat = row.getAttribute("data-format") || "";
      var rowPublisher = row.getAttribute("data-publisher") || "";
      var rowTags = row.getAttribute("data-tags") || "";
      var rowJurisdiction = row.getAttribute("data-jurisdiction") || "";

      var matchFormat = !formatVal || rowFormat === formatVal;
      var matchPublisher = !publisherVal || rowPublisher === publisherVal;
      var matchTag = !tagVal || rowTags.indexOf(tagVal) !== -1;
      var matchJurisdiction = !jurisdictionVal || rowJurisdiction === jurisdictionVal;

      if (matchFormat && matchPublisher && matchTag && matchJurisdiction) {
        row.style.display = "";
        visibleCount++;
      } else {
        row.style.display = "none";
      }
    }

    resultCount.textContent = visibleCount + " dataset" + (visibleCount !== 1 ? "s" : "");
    renderChips(formatVal, publisherVal, tagVal, jurisdictionVal);
  }

  /**
   * Render active filter chips below the filter bar.
   * Each chip shows the filter type and value with a remove button.
   */
  function renderChips(formatVal, publisherVal, tagVal, jurisdictionVal) {
    chipsContainer.innerHTML = "";

    if (formatVal) {
      chipsContainer.appendChild(createChip("Format", formatVal, function () {
        formatSelect.value = "";
        applyFilters();
      }));
    }
    if (publisherVal) {
      chipsContainer.appendChild(createChip("Publisher", publisherVal, function () {
        publisherSelect.value = "";
        applyFilters();
      }));
    }
    if (tagVal) {
      chipsContainer.appendChild(createChip("Tag", tagVal, function () {
        tagSelect.value = "";
        applyFilters();
      }));
    }
    if (jurisdictionVal) {
      chipsContainer.appendChild(createChip("Jurisdiction", jurisdictionVal, function () {
        if (jurisdictionSelect) jurisdictionSelect.value = "";
        applyFilters();
      }));
    }
  }

  /**
   * Create a filter chip DOM element.
   * @param {string} label - The filter type label (e.g., "Format").
   * @param {string} value - The active filter value.
   * @param {function} onRemove - Callback when chip is removed.
   * @returns {HTMLElement} The chip element.
   */
  function createChip(label, value, onRemove) {
    var chip = document.createElement("span");
    chip.className = "filter-chip";
    chip.textContent = label + ": " + value + " ";

    var removeBtn = document.createElement("span");
    removeBtn.className = "filter-chip-remove";
    removeBtn.textContent = "\u00d7";
    removeBtn.setAttribute("role", "button");
    removeBtn.setAttribute("aria-label", "Remove " + label + " filter");
    removeBtn.addEventListener("click", onRemove);

    chip.appendChild(removeBtn);
    return chip;
  }

  // Event listeners
  formatSelect.addEventListener("change", applyFilters);
  publisherSelect.addEventListener("change", applyFilters);
  tagSelect.addEventListener("change", applyFilters);
  if (jurisdictionSelect) jurisdictionSelect.addEventListener("change", applyFilters);

  clearBtn.addEventListener("click", function () {
    formatSelect.value = "";
    publisherSelect.value = "";
    tagSelect.value = "";
    if (jurisdictionSelect) jurisdictionSelect.value = "";
    applyFilters();
  });
})();
