/* MDC Data Encyclopedia - Full Search Module */
/* Loads pre-built Lunr.js index and provides instant dropdown results. */

(function () {
  'use strict';

  var searchIndex = null;
  var searchData = null;
  var searchReady = false;

  /**
   * Initialize search by loading index and data JSON files.
   * Disables search input until both files are loaded.
   */
  function initSearch() {
    var searchInput = document.getElementById('search-input');
    var navSearchInput = document.getElementById('nav-search-input');

    /* Disable inputs until index loads */
    if (searchInput) {
      searchInput.disabled = true;
      searchInput.placeholder = 'Loading search...';
    }
    if (navSearchInput) {
      navSearchInput.disabled = true;
      navSearchInput.placeholder = 'Loading...';
    }

    Promise.all([
      fetch('/search-index.json').then(function (r) { return r.json(); }),
      fetch('/search-data.json').then(function (r) { return r.json(); })
    ])
      .then(function (results) {
        var indexData = results[0];
        var dataPayload = results[1];

        /* Load the serialized index into Lunr */
        if (indexData && Object.keys(indexData).length > 0) {
          searchIndex = lunr.Index.load(indexData);
        }
        searchData = dataPayload || {};
        searchReady = true;

        /* Enable inputs */
        if (searchInput) {
          searchInput.disabled = false;
          searchInput.placeholder = 'Search datasets by name, topic, or department...';
        }
        if (navSearchInput) {
          navSearchInput.disabled = false;
          navSearchInput.placeholder = 'Search datasets...';
        }
      })
      .catch(function (err) {
        console.warn('Search index load failed:', err);
        if (searchInput) {
          searchInput.placeholder = 'Search unavailable';
        }
      });
  }

  /**
   * Handle search input keyup events.
   * Runs Lunr query and renders dropdown with top 8 results.
   */
  function onSearchInput(event) {
    var query = event.target.value.trim();
    var container = event.target.closest('.search-container') || event.target.parentElement;

    if (!searchReady || !searchIndex || query.length < 2) {
      hideDropdown(container);
      return;
    }

    var results;
    try {
      /* Wildcard suffix for as-you-type matching */
      results = searchIndex.search(query + '*');
    } catch (e) {
      /* Lunr throws on syntax errors; fall back to simple search */
      try {
        results = searchIndex.search(query);
      } catch (e2) {
        results = [];
      }
    }

    var items = [];
    var limit = 8;
    for (var i = 0; i < results.length && i < limit; i++) {
      var ref = results[i].ref;
      if (searchData[ref]) {
        items.push(searchData[ref]);
      }
    }

    renderDropdown(items, container);
  }

  /**
   * Render dropdown with search result items below the search input.
   * Each item shows title, snippet, and department chip.
   */
  function renderDropdown(items, container) {
    /* Remove existing dropdown */
    var existing = container.querySelector('.search-dropdown');
    if (existing) {
      existing.remove();
    }

    var dropdown = document.createElement('div');
    dropdown.className = 'search-dropdown';

    if (items.length === 0) {
      var noResults = document.createElement('div');
      noResults.className = 'search-dropdown-empty';
      noResults.textContent = 'No datasets found';
      dropdown.appendChild(noResults);
    } else {
      for (var i = 0; i < items.length; i++) {
        var item = items[i];
        var link = document.createElement('a');
        link.href = item.url;
        link.className = 'search-dropdown-item';

        var titleEl = document.createElement('div');
        titleEl.className = 'search-dropdown-title';
        titleEl.textContent = item.title;

        var snippetEl = document.createElement('div');
        snippetEl.className = 'search-dropdown-snippet';
        snippetEl.textContent = item.snippet;

        link.appendChild(titleEl);
        link.appendChild(snippetEl);

        if (item.department) {
          var deptEl = document.createElement('span');
          deptEl.className = 'chip search-dropdown-dept';
          deptEl.textContent = item.department;
          link.appendChild(deptEl);
        }

        dropdown.appendChild(link);
      }
    }

    container.appendChild(dropdown);
  }

  /**
   * Hide/remove the search dropdown from a container.
   */
  function hideDropdown(container) {
    if (!container) return;
    var dropdown = container.querySelector('.search-dropdown');
    if (dropdown) {
      dropdown.remove();
    }
  }

  /**
   * Set up event listeners after DOM is ready.
   */
  document.addEventListener('DOMContentLoaded', function () {
    initSearch();

    /* Hero search input */
    var searchInput = document.getElementById('search-input');
    if (searchInput) {
      searchInput.addEventListener('keyup', onSearchInput);
    }

    /* Nav search input */
    var navSearchInput = document.getElementById('nav-search-input');
    if (navSearchInput) {
      navSearchInput.addEventListener('keyup', onSearchInput);
    }

    /* Click-outside handler to close dropdowns */
    document.addEventListener('click', function (e) {
      var containers = document.querySelectorAll('.search-container, .nav-search');
      for (var i = 0; i < containers.length; i++) {
        if (!containers[i].contains(e.target)) {
          hideDropdown(containers[i]);
        }
      }
    });
  });
})();
