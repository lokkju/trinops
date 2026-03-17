---
template: home.html
---

<section class="hero">
  <div class="hero-content">
    <div class="trinops-brand">trino.ps</div>
    <p class="hero-tagline">Trino query monitoring from the terminal.</p>
    <img class="hero-image" src="assets/screenshots/hero.gif" alt="trinops demo" />
    <div class="installer-selector">
      <button data-installer="uvx" class="active">uvx</button>
      <button data-installer="pipx">pipx</button>
      <button data-installer="pip">pip</button>
    </div>
    <pre class="hero-install"><code data-install-command="install">uvx trinops install</code></pre>
    <div class="hero-buttons">
      <a href="docs/getting-started/" class="hero-btn hero-btn--primary">Get Started</a>
      <a href="https://github.com/lokkju/trinops" class="hero-btn hero-btn--secondary">GitHub</a>
    </div>
  </div>
</section>

<section class="feature-cards-section">
  <div class="feature-cards">
    <div class="feature-card">
      <h2>Command Line</h2>
      <p>List, inspect, and kill queries. Search schema metadata across catalogs. JSON output for scripting.</p>
      <pre><code class="language-shell">trinops query list
trinops query kill &lt;query-id&gt;
trinops schema search --catalog hive keyword
trinops query list --json | jq '.[] | select(.state=="RUNNING")'</code></pre>
    </div>
    <div class="feature-card">
      <h2>Live Dashboard</h2>
      <p>Like htop for Trino. Live-updating query table with tabbed detail view, kill support, and cluster stats.</p>
      <img src="assets/screenshots/query-list.svg" alt="Query list dashboard" class="feature-screenshot" />
    </div>
  </div>
</section>

<section class="screenshot-gallery-section">
  <h2>Screenshots</h2>
  <div class="screenshot-gallery">
    <figure>
      <img src="assets/screenshots/query-list.svg" alt="Query list with sort indicators" />
      <figcaption>Query list with sort indicators</figcaption>
    </figure>
    <figure>
      <img src="assets/screenshots/detail-overview.svg" alt="Detail pane: Overview tab" />
      <figcaption>Detail pane: Overview tab</figcaption>
    </figure>
    <figure>
      <img src="assets/screenshots/detail-stats.svg" alt="Detail pane: Stats tab" />
      <figcaption>Detail pane: Stats tab</figcaption>
    </figure>
    <figure>
      <img src="assets/screenshots/kill-confirm.svg" alt="Kill confirmation dialog" />
      <figcaption>Kill confirmation dialog</figcaption>
    </figure>
  </div>
</section>

<section class="quick-start">
  <h2>Quick Start</h2>
  <ol class="quick-start-steps">
    <li>
      <strong>Configure</strong>
      <pre><code data-install-command="config init --server trino.example.com --user myuser">uvx trinops config init --server trino.example.com --user myuser</code></pre>
    </li>
    <li>
      <strong>Authenticate</strong>
      <pre><code data-install-command="config set auth oauth2">uvx trinops config set auth oauth2</code></pre>
      <pre><code data-install-command="auth login">uvx trinops auth login</code></pre>
    </li>
    <li>
      <strong>Go</strong>
      <pre><code data-install-command="top">uvx trinops top</code></pre>
    </li>
  </ol>
</section>

<footer class="landing-footer">
  <div class="landing-footer-links">
    <a href="docs/getting-started/">Documentation</a>
    <a href="https://github.com/lokkju/trinops">GitHub</a>
    <a href="https://pypi.org/project/trinops/">PyPI</a>
    <a href="https://github.com/lokkju/trinops/issues">Issues</a>
  </div>
  <p class="landing-footer-attribution">Built by Loki Coyote &middot; A community tool for the <a href="https://trino.io">Trino</a> ecosystem &middot; PolyForm Shield 1.0.0</p>
</footer>
