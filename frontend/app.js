/* ============================================================
   FordTracker — frontend app
   Talks to the local FastAPI server on the same origin.
   ============================================================ */

// ---- Tab switching ----
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const target = btn.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(s => s.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`tab-${target}`).classList.add('active');
    if (target === 'map') initMainMap();
    if (target === 'trips') loadTrips();
  });
});

// ---- Status dot ----
const statusDot = document.getElementById('statusDot');
function setStatus(state) { // 'ok' | 'err' | 'poll'
  statusDot.className = 'status-dot ' + state;
  statusDot.title = { ok: 'Connected', err: 'Connection error', poll: 'Polling…' }[state] || '';
}

// ============================================================
//  DASHBOARD
// ============================================================
let miniMap = null;
let miniMarker = null;
let fuelChart = null;

async function loadDashboard() {
  setStatus('poll');
  try {
    const [statusRes, statsRes, fuelRes] = await Promise.all([
      fetch('/api/status').then(r => r.json()),
      fetch('/api/stats').then(r => r.json()),
      fetch('/api/fuel-history?limit=30').then(r => r.json()),
    ]);
    renderDashboard(statusRes, statsRes, fuelRes);
    setStatus('ok');
  } catch (e) {
    setStatus('err');
    console.error('Dashboard fetch failed', e);
  }
}

function renderDashboard(status, stats, fuelHistory) {
  const snap = status.snapshot;

  // Fuel
  const pct = snap?.fuel_level ?? null;
  document.getElementById('fuelPct').textContent = pct !== null ? `${pct.toFixed(1)}%` : '—';
  const range = snap?.fuel_range_km;
  document.getElementById('fuelRange').textContent = range !== null && range !== undefined
    ? `~${Math.round(range)} km range` : '';
  const bar = document.getElementById('fuelBar');
  if (pct !== null) {
    bar.style.width = `${Math.min(100, pct)}%`;
    bar.className = 'gauge-fill' + (pct < 15 ? ' crit' : pct < 30 ? ' warn' : '');
  }

  // Engine
  const oil = snap?.oil_life;
  document.getElementById('oilLife').textContent = oil !== null && oil !== undefined
    ? `${oil.toFixed(0)}%` : '—';
  const odo = snap?.odometer_km;
  document.getElementById('odometer').textContent = odo !== null && odo !== undefined
    ? `${Math.round(odo).toLocaleString()} mi` : '—';
  const bat = snap?.battery_voltage;
  document.getElementById('battery').textContent = bat !== null && bat !== undefined
    ? `${bat.toFixed(1)} V` : '—';

  // Tires
  const t = snap;
  document.getElementById('tireFL').textContent = fmt_psi(t?.tire_fl);
  document.getElementById('tireFR').textContent = fmt_psi(t?.tire_fr);
  document.getElementById('tireRL').textContent = fmt_psi(t?.tire_rl);
  document.getElementById('tireRR').textContent = fmt_psi(t?.tire_rr);

  // Location & last seen
  const loc = status.latest_location;
  if (loc) {
    const d = new Date(loc.ts + 'Z');
    document.getElementById('lastSeen').textContent = 'Last seen ' + relativeTime(d);
    renderMiniMap(loc.lat, loc.lng);
  } else {
    document.getElementById('lastSeen').textContent = 'No GPS fix yet';
  }

  // Pill badges
  const lockPill = document.getElementById('lockPill');
  const alarmPill = document.getElementById('alarmPill');
  const tripPill = document.getElementById('tripPill');

  if (status.locked === true) {
    lockPill.textContent = 'Locked'; lockPill.className = 'pill green';
  } else if (status.locked === false) {
    lockPill.textContent = 'Unlocked'; lockPill.className = 'pill red';
  } else {
    lockPill.textContent = '—'; lockPill.className = 'pill';
  }

  if (status.alarm_set === true) {
    alarmPill.textContent = 'Alarm On'; alarmPill.className = 'pill green';
  } else if (status.alarm_set === false) {
    alarmPill.textContent = 'Alarm Off'; alarmPill.className = 'pill yellow';
  } else {
    alarmPill.textContent = '—'; alarmPill.className = 'pill';
  }

  if (status.active_trip_id !== null) {
    tripPill.style.display = '';
    tripPill.textContent = `Trip active — ${(status.trip_distance_km || 0).toFixed(2)} km`;
    tripPill.className = 'pill blue';
  } else {
    tripPill.style.display = 'none';
  }

  // Stats
  document.getElementById('weekTrips').textContent  = stats.week_trips;
  document.getElementById('weekDist').textContent   = `${stats.week_distance_km.toFixed(1)} km`;
  document.getElementById('monthTrips').textContent = stats.month_trips;
  document.getElementById('monthDist').textContent  = `${stats.month_distance_km.toFixed(1)} km`;
  document.getElementById('totalTrips').textContent = stats.total_trips;
  document.getElementById('totalDist').textContent  = `${stats.total_distance_km.toFixed(1)} km`;

  // Fuel sparkline
  renderFuelChart(fuelHistory);
}

function fmt_psi(val) {
  return val !== null && val !== undefined ? `${val.toFixed(0)} PSI` : '—';
}

function relativeTime(date) {
  const diff = Math.floor((Date.now() - date.getTime()) / 1000);
  if (diff < 60)   return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return date.toLocaleDateString();
}

function renderMiniMap(lat, lng) {
  if (!miniMap) {
    miniMap = L.map('miniMap', { zoomControl: false, attributionControl: false, dragging: false, scrollWheelZoom: false });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18 }).addTo(miniMap);
    miniMarker = L.circleMarker([lat, lng], { radius: 8, color: '#0066cc', fillColor: '#3b82f6', fillOpacity: 1 }).addTo(miniMap);
  } else {
    miniMarker.setLatLng([lat, lng]);
  }
  miniMap.setView([lat, lng], 15);
}

function renderFuelChart(history) {
  const canvas = document.getElementById('fuelChart');
  const labels = history.map(h => {
    const d = new Date(h.ts + 'Z');
    return d.toLocaleDateString('en', { month: 'short', day: 'numeric' });
  }).reverse();
  const data = history.map(h => h.fuel_level).reverse();

  if (fuelChart) { fuelChart.destroy(); fuelChart = null; }
  if (!data.length) return;

  fuelChart = new Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data,
        borderColor: '#0066cc',
        borderWidth: 1.5,
        pointRadius: 0,
        fill: true,
        backgroundColor: 'rgba(0,102,204,0.12)',
        tension: 0.3,
      }]
    },
    options: {
      responsive: true,
      animation: false,
      plugins: { legend: { display: false }, tooltip: {
        callbacks: { label: ctx => `${ctx.parsed.y.toFixed(1)}%` }
      }},
      scales: {
        x: { display: false },
        y: { display: false, min: 0, max: 100 }
      }
    }
  });
}

// ============================================================
//  MAP TAB
// ============================================================
let mainMap = null;
let allPolylines = [];
let selectedPolyline = null;
let allTripsData = [];
let startMarker = null;
let endMarker = null;

async function initMainMap() {
  if (mainMap) return;
  mainMap = L.map('mainMap').setView([39.5, -98.35], 5);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://openstreetmap.org">OpenStreetMap</a>',
  }).addTo(mainMap);

  await loadTripsForMap();
}

async function loadTripsForMap() {
  try {
    const trips = await fetch('/api/trips?limit=200').then(r => r.json());
    allTripsData = trips;

    const sel = document.getElementById('tripSelect');
    sel.innerHTML = '<option value="">— select a trip —</option>';
    trips.forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.id;
      const d = new Date(t.start_time + 'Z');
      const dist = t.distance_km ? `${t.distance_km.toFixed(1)} km` : 'in progress';
      opt.textContent = `${fmtDate(d)} — ${dist}`;
      sel.appendChild(opt);
    });
  } catch (e) {
    console.error('Failed to load trips for map', e);
  }
}

document.getElementById('tripSelect').addEventListener('change', async e => {
  const id = parseInt(e.target.value);
  if (!id) return;
  await showTrip(id);
});

document.getElementById('showAllTripsBtn').addEventListener('click', async () => {
  clearMapLayers();
  document.getElementById('tripInfo').textContent = '';
  if (!allTripsData.length) return;

  const bounds = [];
  for (const trip of allTripsData) {
    const pts = await fetch(`/api/trips/${trip.id}/points`).then(r => r.json());
    if (!pts.length) continue;
    const coords = pts.map(p => [p.lat, p.lng]);
    const pl = L.polyline(coords, { color: '#2e3147', weight: 2, opacity: .7 }).addTo(mainMap);
    allPolylines.push(pl);
    coords.forEach(c => bounds.push(c));
  }
  if (bounds.length) mainMap.fitBounds(bounds, { padding: [30, 30] });
});

async function showTrip(id) {
  clearMapLayers();
  const [trip, pts] = await Promise.all([
    fetch(`/api/trips/${id}`).then(r => r.json()),
    fetch(`/api/trips/${id}/points`).then(r => r.json()),
  ]);
  if (!pts.length) {
    document.getElementById('tripInfo').textContent = 'No GPS points for this trip.';
    return;
  }

  const coords = pts.map(p => [p.lat, p.lng]);
  selectedPolyline = L.polyline(coords, { color: '#0066cc', weight: 4, opacity: .9 }).addTo(mainMap);

  const greenIcon = L.circleMarker(coords[0], { radius: 7, color: '#22c55e', fillColor: '#22c55e', fillOpacity: 1 });
  greenIcon.bindPopup('Start').addTo(mainMap);
  startMarker = greenIcon;

  if (trip.end_time) {
    const redIcon = L.circleMarker(coords[coords.length - 1], { radius: 7, color: '#ef4444', fillColor: '#ef4444', fillOpacity: 1 });
    redIcon.bindPopup('End').addTo(mainMap);
    endMarker = redIcon;
  }

  mainMap.fitBounds(selectedPolyline.getBounds(), { padding: [30, 30] });

  const d = new Date(trip.start_time + 'Z');
  const dur = trip.end_time ? duration(new Date(trip.start_time + 'Z'), new Date(trip.end_time + 'Z')) : 'in progress';
  document.getElementById('tripInfo').textContent =
    `${fmtDate(d)} · ${trip.distance_km.toFixed(2)} km · ${dur}`;
}

function clearMapLayers() {
  allPolylines.forEach(p => mainMap.removeLayer(p));
  allPolylines = [];
  if (selectedPolyline) { mainMap.removeLayer(selectedPolyline); selectedPolyline = null; }
  if (startMarker) { mainMap.removeLayer(startMarker); startMarker = null; }
  if (endMarker) { mainMap.removeLayer(endMarker); endMarker = null; }
}

// ============================================================
//  TRIPS TAB
// ============================================================
async function loadTrips() {
  try {
    const trips = await fetch('/api/trips?limit=200').then(r => r.json());
    const tbody = document.getElementById('tripsBody');
    const empty = document.getElementById('tripsEmpty');
    document.getElementById('tripsCount').textContent = `${trips.length} trip${trips.length !== 1 ? 's' : ''}`;

    if (!trips.length) {
      tbody.innerHTML = '';
      empty.style.display = '';
      return;
    }
    empty.style.display = 'none';

    tbody.innerHTML = trips.map(t => {
      const start = new Date(t.start_time + 'Z');
      const end   = t.end_time ? new Date(t.end_time + 'Z') : null;
      const active = !t.end_time;
      return `<tr data-id="${t.id}" class="${active ? 'active-trip' : ''}">
        <td>${fmtDate(start)}</td>
        <td>${fmtTime(start)}</td>
        <td>${end ? fmtTime(end) : '<span class="badge-active">Active</span>'}</td>
        <td>${end ? duration(start, end) : '—'}</td>
        <td>${t.distance_km.toFixed(2)} km</td>
      </tr>`;
    }).join('');

    tbody.querySelectorAll('tr').forEach(row => {
      row.addEventListener('click', () => {
        const id = parseInt(row.dataset.id);
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(s => s.classList.remove('active'));
        document.querySelector('[data-tab="map"]').classList.add('active');
        document.getElementById('tab-map').classList.add('active');
        initMainMap().then(() => {
          document.getElementById('tripSelect').value = id;
          showTrip(id);
        });
      });
    });
  } catch (e) {
    console.error('Failed to load trips', e);
  }
}

// ============================================================
//  Utilities
// ============================================================
function fmtDate(d) {
  return d.toLocaleDateString('en', { month: 'short', day: 'numeric', year: 'numeric' });
}
function fmtTime(d) {
  return d.toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' });
}
function duration(start, end) {
  const s = Math.floor((end - start) / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h ? `${h}h ${m}m` : `${m}m`;
}

// ============================================================
//  Init + auto-refresh
// ============================================================
async function init() {
  try {
    const cfg = await fetch('/api/config').then(r => r.json());
    if (cfg.demo_mode) {
      document.getElementById('demoBadge').style.display = '';
      document.title = 'FordTracker (Demo)';
    }
  } catch (_) {}
  loadDashboard();
  setInterval(loadDashboard, 60_000);
}

init();
