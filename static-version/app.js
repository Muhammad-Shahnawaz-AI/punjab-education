const pageTitle = document.querySelector('#page-title');
const pageContent = document.querySelector('#page-content');
const navigationLinks = [...document.querySelectorAll('[data-route]')];

const sampleItems = [
  'Sample curriculum',
  'Sample subject',
  'Sample book',
  'Sample chapter',
  'Sample topic',
];

const emptyState = (title, message) => `
  <article class="empty-state">
    <h2>${title}</h2>
    <p>${message}</p>
  </article>`;

const pages = {
  overview: {
    title: 'Overview',
    content: `
      <div class="hero">
        <section class="hero-panel">
          <span class="eyebrow">Static demonstration</span>
          <h2>Education insights, in one workspace.</h2>
          <p>This preview demonstrates the platform layout and navigation. Live curriculum, account access, AI generation, and student analytics require the separate application services.</p>
        </section>
        <section class="panel">
          <span class="eyebrow">Illustrative only</span>
          <div class="metrics" style="margin-top:14px">
            <div class="metric"><span>Student mastery</span><strong>--</strong></div>
            <div class="metric"><span>Active students</span><strong>--</strong></div>
            <div class="metric"><span>Assessments</span><strong>--</strong></div>
            <div class="metric"><span>Approved questions</span><strong>--</strong></div>
          </div>
          <p>Live figures are intentionally not shown in this offline preview.</p>
        </section>
      </div>
      <div class="section-heading"><div><h2>Curriculum browser</h2><p>Search only the generic placeholder catalog in this static preview.</p></div></div>
      <form class="search-form" id="catalog-search"><input id="catalog-query" type="search" aria-label="Search placeholder catalog" placeholder="Search sample catalog"><button type="submit">Search</button></form>
      <ul class="result-list" id="catalog-results" aria-live="polite"><li class="muted">Search results will appear here.</li></ul>`,
  },
  curriculum: {
    title: 'Curriculum',
    content: `
      <div class="section-heading"><div><h2>Sample catalog</h2><p>Placeholder structure only. No official curriculum content is included.</p></div></div>
      <form class="search-form" id="catalog-search"><input id="catalog-query" type="search" aria-label="Search placeholder catalog" placeholder="Search sample catalog"><button type="submit">Search</button></form>
      <ul class="result-list" id="catalog-results"><li class="muted">Search the generic sample labels; this preview has no official catalog data.</li></ul>`,
  },
  generator: {
    title: 'AI Generator',
    content: `${emptyState('Generation is unavailable in this preview', 'The platform must have approved source material and a connected backend before it can generate questions. No curriculum content is invented or generated here.')}`,
  },
  assessments: {
    title: 'Assessments',
    content: `${emptyState('No live assessments', 'Assessment creation, publishing, student attempts, and grading require the application backend.')}`,
  },
  students: {
    title: 'Students',
    content: `${emptyState('Student records are not available', 'This static preview contains no accounts or personal data. Student management requires the application backend.')}`,
  },
  analytics: {
    title: 'Analytics',
    content: `${emptyState('Analytics are not connected', 'Mastery trends and class comparisons require real assessment attempts. No sample student analytics are presented as live data.')}`,
  },
  settings: {
    title: 'Settings',
    content: `${emptyState('Static preview settings', 'There are no accounts or saved preferences in this standalone preview. Account and profile settings are part of the full application.')}`,
  },
};

function attachCatalogSearch() {
  const form = document.querySelector('#catalog-search');
  if (!form) return;
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const query = document.querySelector('#catalog-query').value.trim().toLowerCase();
    const results = document.querySelector('#catalog-results');
    const matches = sampleItems.filter((item) => item.toLowerCase().includes(query));
    results.replaceChildren();
    if (matches.length === 0) {
      const item = document.createElement('li');
      item.className = 'muted';
      item.textContent = 'No placeholder labels matched that search.';
      results.append(item);
      return;
    }
    for (const match of matches) {
      const item = document.createElement('li');
      item.textContent = match;
      results.append(item);
    }
  });
}

function renderPage() {
  const route = window.location.hash.slice(1) || 'overview';
  const page = pages[route] || pages.overview;
  pageTitle.textContent = page.title;
  pageContent.innerHTML = page.content;
  navigationLinks.forEach((link) => {
    if (link.dataset.route === route) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
  attachCatalogSearch();
}

window.addEventListener('hashchange', renderPage);
renderPage();
