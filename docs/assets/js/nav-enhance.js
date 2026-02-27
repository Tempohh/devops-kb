(function () {
  var activeTop = null;
  var hideTimer = null;

  // ── Timer helpers ────────────────────────────────────────────────────────────
  // A short grace period lets the mouse travel from the tab bar to the dropdown
  // without the menu disappearing. This is the only timer in the system — there
  // is no second flyout level, so there are no cross-element timing races.

  function scheduleHide() {
    clearTimeout(hideTimer);
    hideTimer = setTimeout(hideAll, 250);
  }

  function cancelHide() {
    clearTimeout(hideTimer);
  }

  // ── Hide ─────────────────────────────────────────────────────────────────────

  function hideAll() {
    cancelHide();
    if (activeTop) {
      activeTop.classList.remove('kbdrop--visible');
      activeTop = null;
    }
  }

  // ── Measure element width without a visible flash ────────────────────────────

  function measureWidth(el) {
    el.style.visibility = 'hidden';
    el.style.display    = 'block';
    var w = el.offsetWidth;
    el.style.display    = '';   // '' → CSS class controls display again
    el.style.visibility = '';
    return w;
  }

  // ── Show dropdown centered under the tab ─────────────────────────────────────
  // Uses -1px top overlap so there is never a sub-pixel gap between the tab bar
  // bottom edge and the dropdown top edge.

  function showTop(drop, anchorRect) {
    cancelHide();
    if (activeTop === drop) return;
    if (activeTop) activeTop.classList.remove('kbdrop--visible');

    var dw   = measureWidth(drop);
    var left = anchorRect.left + anchorRect.width / 2 - dw / 2;
    left = Math.max(8, Math.min(left, window.innerWidth - dw - 8));

    drop.style.top       = (anchorRect.bottom - 1) + 'px';
    drop.style.left      = left + 'px';
    drop.style.maxHeight = (window.innerHeight - anchorRect.bottom - 12) + 'px';
    drop.classList.add('kbdrop--visible');
    activeTop = drop;
  }

  // ── Normalize a URL for prefix-based matching ─────────────────────────────────

  function normHref(href) {
    return href
      .replace(/_index\/?$/, '')
      .replace(/index\.html$/, '')
      .replace(/\/?$/, '/');
  }

  // ── Find direct children (one depth level only) ──────────────────────────────
  // Scans a.md-nav__link in the full DOM (includes the hidden drawer nav that
  // MkDocs always renders). A "direct child" of base/ has exactly one path
  // segment relative to base.

  function findDirectChildren(sectionHref) {
    var base     = normHref(sectionHref);
    var children = [];
    var seen     = {};

    document.querySelectorAll('a.md-nav__link').forEach(function (a) {
      var href = a.href;
      if (!href) return;
      var norm = normHref(href);
      if (seen[norm]) return;
      if (!norm.startsWith(base)) return;
      if (norm === base) return;

      var rel   = norm.slice(base.length).replace(/\/?$/, '/');
      var parts = rel.split('/').filter(Boolean);
      if (parts.length !== 1) return;

      seen[norm] = true;
      var textEl = a.querySelector('.md-ellipsis');
      var text   = (textEl ? textEl.textContent : a.textContent).trim();
      if (text) children.push({ text: text, href: href });
    });

    return children;
  }

  // ── Build the dropdown element ────────────────────────────────────────────────
  //
  // MEGA-MENU mode  (when at least one child itself has children):
  //   Each top-level child becomes a section header.
  //   Its children are listed in a responsive CSS grid below the header.
  //   Everything is visible at once — no second flyout level needed.
  //
  // FLAT-LIST mode  (all children are leaf nodes):
  //   Classic single-column dropdown list.

  function buildMenu(children) {
    // Pre-resolve sub-children for every top-level child in one pass.
    var sections = children.map(function (c) {
      return { text: c.text, href: c.href, subs: findDirectChildren(c.href) };
    });

    // Always use mega-menu layout for consistency across all categories.
    // Items with sub-children show a header + grid; leaf items show header only.
    // This guarantees identical chrome regardless of how deep the content tree is.
    var drop = document.createElement('div');
    drop.className = 'kbdrop kbdrop--mega';
    drop.setAttribute('data-kb-drop', '');

    sections.forEach(function (s) {
      var section = document.createElement('div');
      section.className = 'kbdrop__section';

      // Section header — links to the section index page
      var header        = document.createElement('a');
      header.className  = 'kbdrop__section-header';
      header.href       = s.href;
      header.textContent = s.text;
      section.appendChild(header);

      if (s.subs.length) {
        var grid = document.createElement('ul');
        grid.className = 'kbdrop__section-items';
        s.subs.forEach(function (sub) {
          var li = document.createElement('li');
          var a  = document.createElement('a');
          a.href        = sub.href;
          a.textContent = sub.text;
          li.appendChild(a);
          grid.appendChild(li);
        });
        section.appendChild(grid);
      }

      drop.appendChild(section);
    });

    return drop;
  }

  // ── Build / rebuild dropdowns on every navigation ────────────────────────────

  function buildDropdowns() {
    document.querySelectorAll('[data-kb-drop]').forEach(function (d) { d.remove(); });
    hideAll();

    var tabsList = document.querySelector('.md-tabs__list');
    if (!tabsList) return;

    var tabItems        = Array.from(tabsList.querySelectorAll(':scope > .md-tabs__item'));
    var rootNames       = ['home', 'tags'];
    var categoryStarted = false;

    tabItems.forEach(function (item) {
      item.classList.remove('md-tabs__item--category-start');
      if (item._kbEnter) item.removeEventListener('mouseenter', item._kbEnter);
      if (item._kbLeave) item.removeEventListener('mouseleave', item._kbLeave);
      item._kbDrop = null;
    });

    tabItems.forEach(function (tabItem) {
      var link = tabItem.querySelector('.md-tabs__link');
      if (!link) return;

      var name   = link.textContent.trim().toLowerCase();
      var isRoot = rootNames.indexOf(name) !== -1;

      if (!isRoot && !categoryStarted) {
        tabItem.classList.add('md-tabs__item--category-start');
        categoryStarted = true;
      }
      if (isRoot) return;

      var children = findDirectChildren(link.href);
      if (!children.length) return;

      var drop = buildMenu(children);
      document.body.appendChild(drop);
      tabItem._kbDrop = drop;

      drop.addEventListener('mouseenter', function () { cancelHide(); activeTop = drop; });
      drop.addEventListener('mouseleave', scheduleHide);

      tabItem._kbEnter = function () {
        cancelHide();
        showTop(drop, tabItem.getBoundingClientRect());
      };
      tabItem._kbLeave = scheduleHide;

      tabItem.addEventListener('mouseenter', tabItem._kbEnter);
      tabItem.addEventListener('mouseleave', tabItem._kbLeave);
    });
  }

  // ── Global listeners ──────────────────────────────────────────────────────────

  window.addEventListener('scroll', hideAll, { passive: true });
  document.addEventListener('click', function (e) {
    if (!activeTop || !activeTop.contains(e.target)) hideAll();
  });

  if (typeof document$ !== 'undefined') {
    document$.subscribe(buildDropdowns);
  } else {
    window.addEventListener('DOMContentLoaded', buildDropdowns);
  }
})();
