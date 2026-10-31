// Renders the site from data/index.json and data/sports/{slug}.json.
// Routes: #/{sport}/{view}[/{division}]

const VIEWS = [
  { id: "results", label: "Results" },
  { id: "upcoming", label: "Upcoming" },
  { id: "rankings", label: "Rankings" },
  { id: "divisions", label: "Divisions" },
];
const DEFAULT_VIEW = "results";
const OTHER_DIVISION = "other";
const RANKING_PREVIEW = 25;
const SITE_NAME = "MA High School Elo";

const state = { index: null, sports: new Map(), expanded: new Set() };

const $ = (id) => document.getElementById(id);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === undefined || child === null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

const srOnly = (text) => el("span", { class: "sr-only" }, text);
const message = (text) => el("p", { class: "message" }, text);

// Routing

function routeHref(sport, view, division) {
  const parts = [sport, view];
  if (division) parts.push(division);
  return "#/" + parts.map(encodeURIComponent).join("/");
}

function parseHash() {
  const [sport, view, division] = location.hash
    .replace(/^#\/?/, "")
    .split("/")
    .map((part) => {
      try {
        return decodeURIComponent(part);
      } catch {
        return "";
      }
    });
  return { sport, view, division };
}

function resolveRoute() {
  const sports = state.index.sports;
  const requested = parseHash();
  const sport = sports.find((s) => s.slug === requested.sport) || sports[0];
  const view = VIEWS.some((v) => v.id === requested.view) ? requested.view : DEFAULT_VIEW;
  return { sport, view, division: requested.division };
}

// Data

async function fetchJson(path) {
  const response = await fetch(path, { cache: "no-cache" });
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.json();
}

function loadSport(slug) {
  if (!state.sports.has(slug)) {
    const request = fetchJson(`data/sports/${encodeURIComponent(slug)}.json`).catch((error) => {
      state.sports.delete(slug);
      throw error;
    });
    state.sports.set(slug, request);
  }
  return state.sports.get(slug);
}

// Formatting

function parseDate(iso) {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day));
}

function formatDay(iso) {
  const days = Math.round((parseDate(iso) - parseDate(state.index.date)) / 86400000);
  const label = parseDate(iso).toLocaleDateString("en-US", {
    weekday: "short", month: "short", day: "numeric", timeZone: "UTC",
  });
  const relative = { "-1": "Yesterday", 0: "Today", 1: "Tomorrow" }[days];
  return relative ? `${relative}, ${label}` : label;
}

function formatUpdated(iso) {
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return "";
  return "Updated " + when.toLocaleString("en-US", {
    weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
    timeZone: "America/New_York",
  });
}

function divisionLabel(division) {
  if (division === OTHER_DIVISION) return "Other teams";
  const [section, number] = division.includes(" ") ? division.split(" ") : [null, division];
  return section ? `${section} Division ${number}` : `Division ${number}`;
}

function tourneyTag(game) {
  if (!game.tourney && !game.level) return null;
  const name = (game.tourney || "").replace(/^MIAA Division (\S+)$/, "D$1");
  const text = [name, game.level].filter(Boolean).join(" · ");
  const full = [game.tourney, game.level].filter(Boolean).join(", ");
  return el("span", { class: "tag", title: full }, el("span", { "aria-hidden": "true" }, text), srOnly(full));
}

function record(team) {
  return team.t ? `${team.w}-${team.l}-${team.t}` : `${team.w}-${team.l}`;
}

function groupByDate(games) {
  const groups = [];
  for (const game of games) {
    const last = groups[groups.length - 1];
    if (last && last.date === game.date) last.games.push(game);
    else groups.push({ date: game.date, games: [game] });
  }
  return groups;
}

// Current-season record by team name, built once per sport from its rankings
const recordCache = new WeakMap();

function recordsFor(data) {
  if (!recordCache.has(data)) {
    recordCache.set(data, new Map(data.teams.map((team) => [team.team, record(team)])));
  }
  return recordCache.get(data);
}

function teamName(name, isHome, records) {
  const teamRecord = records.get(name);
  return el("span", { class: "team-name" },
    isHome ? el("span", { class: "at" }, el("span", { "aria-hidden": "true" }, "@"), srOnly("at ")) : null,
    name,
    teamRecord ? el("span", { class: "team-record" }, ` (${teamRecord})`) : null);
}

function dayList(games, renderGame) {
  return groupByDate(games).map((group) =>
    el("section", { class: "day" },
      el("h2", { class: "day-heading" }, formatDay(group.date)),
      el("ul", { class: "games" }, group.games.map(renderGame))));
}

// Views

// Compare a result with its predicted spread, from the predicted favorite's side.
// Returns null for even predictions and games without scores (forfeits).
function spreadVerdict(game) {
  if (game.spread === undefined || Math.abs(game.spread) < 0.05) return null;
  if (game.hs === undefined || game.vs === undefined) return null;
  const homeFavored = game.spread > 0;
  const predicted = Math.abs(game.spread);
  // Orient the score difference by the recorded winner, since in some sports
  // (cross country) the lower score wins: ho 1 home won, 0 visitor won, 2 tie
  const gap = Math.abs(game.hs - game.vs);
  const homeMargin = game.ho === 1 ? gap : game.ho === 0 ? -gap : game.ho === 2 ? 0 : game.hs - game.vs;
  const actual = homeFavored ? homeMargin : -homeMargin;
  const margin = predicted.toFixed(1);
  let label;
  let detail;
  if (actual < 0) {
    label = "Upset";
    detail = `Favorite lost; predicted to win by ${margin}`;
  } else if (actual === 0) {
    label = "Closer than expected";
    detail = `Favorite tied; predicted to win by ${margin}`;
  } else if (actual > predicted) {
    label = "As expected";
    detail = `Favorite won by ${actual}, more than the predicted ${margin}`;
  } else {
    label = "Closer than expected";
    detail = `Favorite won by ${actual}, less than the predicted ${margin}`;
  }
  return { homeFavored, margin, label, detail };
}

function verdictTag(verdict) {
  if (!verdict) return null;
  const cls = "tag tag-verdict" + (verdict.label === "Upset" ? " tag-upset" : "");
  return el("span", { class: cls, title: verdict.detail },
    el("span", { "aria-hidden": "true" }, verdict.label), srOnly(`${verdict.label}: ${verdict.detail}`));
}

function tagRow(...tags) {
  const present = tags.filter(Boolean);
  return present.length ? el("div", { class: "tags" }, present) : null;
}

function resultGame(game, records) {
  // home outcome: 1 home won, 0 visitor won, 2 tie
  const forfeit = game.status && game.status.startsWith("FORFEIT");
  const verdict = forfeit ? null : spreadVerdict(game);
  const line = (name, score, isHome) => {
    const won = game.ho === (isHome ? 1 : 0);
    const lost = game.ho === (isHome ? 0 : 1);
    const favored = verdict && verdict.homeFavored === isHome;
    return el("div", { class: "team-line" + (won ? " won" : lost ? " lost" : "") },
      teamName(name, isHome, records),
      el("span", { class: "team-figures" },
        favored
          ? el("span", { class: "spread" }, el("span", { "aria-hidden": "true" }, `\u2212${verdict.margin}`), srOnly(`, favored by ${verdict.margin},`))
          : null,
        el("span", { class: "score" }, score ?? (won ? "W" : "L")),
        won ? srOnly(", won") : null));
  };
  return el("li", { class: "game result" },
    el("div", {},
      line(game.visitor, game.vs, false),
      line(game.home, game.hs, true)),
    tagRow(forfeit ? el("span", { class: "tag" }, "Forfeit") : tourneyTag(game), verdictTag(verdict)));
}

function upcomingGame(game, records) {
  const homeFavored = game.homeProb === undefined || game.homeProb >= 0.5;
  const prob = game.homeProb === undefined ? null : Math.round(100 * (homeFavored ? game.homeProb : 1 - game.homeProb));
  const favoredSpread = game.spread === undefined ? null : homeFavored ? game.spread : -game.spread;
  // Probabilities and spreads use separately fitted home edges; show a margin only when they agree
  const margin = favoredSpread !== null && favoredSpread >= 0.05 ? favoredSpread.toFixed(1) : null;

  const line = (name, isHome) => {
    const favored = prob !== null && isHome === homeFavored;
    return el("div", { class: "team-line" },
      teamName(name, isHome, records),
      favored
        ? el("span", { class: "team-figures" },
          margin ? el("span", { class: "spread" }, el("span", { "aria-hidden": "true" }, `−${margin}`), srOnly(`, favored by ${margin}`)) : srOnly(", favored"),
          el("span", { class: "prob" }, `${prob}%`, srOnly(" win probability")))
        : null);
  };
  return el("li", { class: "game has-time" },
    el("span", { class: "game-time" }, game.time || "TBD"),
    el("div", {}, line(game.visitor, false), line(game.home, true)),
    tagRow(tourneyTag(game)));
}

function headerCell(visible, spoken, cls) {
  return el("th", { scope: "col", class: cls },
    spoken ? [el("span", { "aria-hidden": "true" }, visible), srOnly(spoken)] : visible);
}

function rankingTable(caption, teams, { rankKey, showDivision }) {
  return el("div", { class: "table-wrap" },
    el("table", {},
      el("caption", { class: "sr-only" }, caption),
      el("thead", {}, el("tr", {},
        headerCell("#", "Rank", "col-rank"),
        headerCell("Team"),
        headerCell("Elo", null, "col-num"),
        headerCell("Record", null, "col-record"),
        showDivision ? headerCell("Div", "Division", "col-div") : null)),
      el("tbody", {}, teams.map((team) => el("tr", {},
        el("td", { class: "col-rank" }, team[rankKey] ?? ""),
        el("td", {}, team.team),
        el("td", { class: "col-num" }, team.elo),
        el("td", { class: "col-record" }, record(team)),
        showDivision ? el("td", { class: "col-div" }, team.div ?? "") : null)))));
}

function renderRankings(data, rerender) {
  if (!data.teams.length) return [message("No rankings yet this season.")];
  const expanded = state.expanded.has(data.slug);
  const shown = expanded ? data.teams : data.teams.slice(0, RANKING_PREVIEW);
  const nodes = [rankingTable(`${data.name} Elo rankings`, shown, { rankKey: "rank", showDivision: data.hasDivisions })];
  if (!expanded && data.teams.length > RANKING_PREVIEW) {
    nodes.push(el("button", {
      type: "button",
      class: "show-all",
      onclick: () => {
        state.expanded.add(data.slug);
        rerender();
        // Keep keyboard users near where they were: the first newly revealed row
        const row = document.querySelectorAll("#content tbody tr")[RANKING_PREVIEW];
        if (row) {
          row.setAttribute("tabindex", "-1");
          row.focus();
        }
      },
    }, `Show all ${data.teams.length}`));
  }
  return nodes;
}

function renderDivisions(data, route) {
  if (!data.hasDivisions) return [message("Division data isn't available for this sport.")];
  const choices = [...data.divisions];
  if (data.teams.some((team) => !team.div)) choices.push(OTHER_DIVISION);
  const division = choices.includes(route.division) ? route.division : choices[0];
  if (division !== route.division) {
    history.replaceState(null, "", routeHref(data.slug, route.view, division));
  }

  const teams = division === OTHER_DIVISION
    ? data.teams.filter((team) => !team.div)
    : data.teams.filter((team) => team.div === division).sort((a, b) => a.divRank - b.divRank);

  const select = el("select", {
    id: "division-select",
    onchange: (event) => { location.hash = routeHref(data.slug, route.view, event.target.value); },
  }, choices.map((choice) => el("option", { value: choice, selected: choice === division }, divisionLabel(choice))));

  return [
    el("div", { class: "division-picker" }, el("label", { for: "division-select" }, "Division"), select),
    teams.length
      ? rankingTable(`${data.name} ${divisionLabel(division)} Elo rankings`, teams, {
        rankKey: division === OTHER_DIVISION ? null : "divRank",
        showDivision: false,
      })
      : message("No teams in this division have played yet."),
  ];
}

function renderView(data, route) {
  switch (route.view) {
    case "upcoming":
      return data.upcoming.length ? dayList(data.upcoming, (game) => upcomingGame(game, recordsFor(data))) : [message("No games scheduled.")];
    case "rankings":
      return renderRankings(data, () => $("content").replaceChildren(...renderView(data, route)));
    case "divisions":
      return renderDivisions(data, route);
    default:
      return data.recent.length ? dayList(data.recent, (game) => resultGame(game, recordsFor(data))) : [message("No results yet this season.")];
  }
}

// Page chrome. Nav links are built once and updated in place so keyboard focus survives navigation.

function buildNav() {
  const sportLink = (sport) => el("li", {}, el("a", { "data-sport": sport.slug }, sport.name));
  const sports = state.index.sports;
  const inSeason = sports.filter((s) => s.inSeason);
  const primary = inSeason.length ? inSeason : sports;
  const others = inSeason.length ? sports.filter((s) => !s.inSeason) : [];

  $("sports-primary").replaceChildren(...primary.map(sportLink));
  const details = $("sports-other");
  details.hidden = others.length === 0;
  details.querySelector("ul").replaceChildren(...others.map(sportLink));
  $("views").replaceChildren(...VIEWS.map((view) => el("a", { "data-view": view.id }, view.label)));
}

function setCurrent(link, isCurrent) {
  if (isCurrent) link.setAttribute("aria-current", "page");
  else link.removeAttribute("aria-current");
}

function updateNav(route) {
  for (const link of document.querySelectorAll("a[data-sport]")) {
    link.href = routeHref(link.dataset.sport, route.view);
    setCurrent(link, link.dataset.sport === route.sport.slug);
  }
  if (document.querySelector("#sports-other a[aria-current]")) $("sports-other").open = true;
  for (const link of document.querySelectorAll("a[data-view]")) {
    link.href = routeHref(route.sport.slug, link.dataset.view);
    setCurrent(link, link.dataset.view === route.view);
  }
}

let renderToken = 0;

async function render() {
  const requested = parseHash();
  const route = resolveRoute();
  if (requested.sport !== route.sport.slug || requested.view !== route.view) {
    // Replace unknown or missing parts with the defaults actually shown
    const division = route.view === "divisions" ? route.division : undefined;
    history.replaceState(null, "", routeHref(route.sport.slug, route.view, division));
  }

  const viewLabel = VIEWS.find((v) => v.id === route.view).label;
  document.title = `${route.sport.name} ${viewLabel} - ${SITE_NAME}`;
  $("sport-name").textContent = route.sport.name;
  $("sport-season").textContent = route.sport.season;
  updateNav(route);

  const content = $("content");
  const token = ++renderToken;
  content.setAttribute("aria-busy", "true");
  try {
    const data = await loadSport(route.sport.slug);
    if (token !== renderToken) return;
    content.replaceChildren(...renderView(data, route));
  } catch (error) {
    if (token !== renderToken) return;
    console.error(error);
    content.replaceChildren(message(`Couldn't load ${route.sport.name}. Try again later.`));
  } finally {
    if (token === renderToken) content.removeAttribute("aria-busy");
  }
}

async function start() {
  // The skip link targets #main, which would otherwise be read as a route
  document.querySelector(".skip-link").addEventListener("click", (event) => {
    event.preventDefault();
    $("main").focus();
  });
  try {
    state.index = await fetchJson("data/index.json");
  } catch (error) {
    console.error(error);
    $("content").replaceChildren(message("Couldn't load sports data. Try again later."));
    return;
  }
  if (!state.index.sports.length) {
    $("content").replaceChildren(message("No sports data yet."));
    return;
  }
  $("updated").textContent = formatUpdated(state.index.generated);
  buildNav();
  window.addEventListener("hashchange", render);
  render();
}

start();
