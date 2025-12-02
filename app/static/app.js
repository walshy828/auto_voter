let socket = null;
let socketConnected = false;
let loginModalShown = false;
let queueFilter = 'all';
let pollsLast7Days = false;
let pollsSortOrder = 'desc';

// Helper to format EST timestamps consistently
function formatESTTime(isoString) {
  if (!isoString) return '-';
  const date = new Date(isoString);
  return date.toLocaleString('en-US', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true
  });
}

async function fetchPolls() {
  // Add timestamp to prevent caching
  const res = await authedFetch(`/polls?_t=${Date.now()}`);
  return res.json();
}

async function fetchQueue() {
  // Add timestamp to prevent caching
  const res = await authedFetch(`/queue?_t=${Date.now()}`);
  return res.json();
}

async function fetchSchedulerStatus() {
  const res = await authedFetch('/scheduler/status');
  return res.json();
}

async function fetchPollSchedulerConfig() {
  const res = await authedFetch('/poll-scheduler/config');
  return res.json();
}

function el(tag, attrs = {}, text = '') {
  const e = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v));
  if (text) e.textContent = text;
  return e;
}

async function refreshPolls() {
  let polls = await fetchPolls();

  // Filter by date if checkbox is checked
  if (pollsLast7Days) {
    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
    polls = polls.filter(p => new Date(p.created_at) >= sevenDaysAgo);
  }

  // Sort by date
  polls.sort((a, b) => {
    const dateA = new Date(a.created_at);
    const dateB = new Date(b.created_at);
    return pollsSortOrder === 'desc' ? dateB - dateA : dateA - dateB;
  });

  const sel = document.getElementById('pollSelect');
  const tbody = document.querySelector('#pollsTable tbody');
  sel.innerHTML = '<option value="">-- choose existing poll or enter manually --</option>';
  tbody.innerHTML = '';

  // For dropdown, only show polls from last 7 days
  const sevenDaysAgo = new Date();
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
  const recentPolls = polls.filter(p => new Date(p.created_at) >= sevenDaysAgo);

  polls.forEach(p => {
    // table row
    const tr = document.createElement('tr');
    const stats = p.total_votes && p.total_poll_votes
      ? `<div class="small">
           <strong>${p.total_votes.toLocaleString()}</strong> / ${p.total_poll_votes.toLocaleString()}
         </div>
         <div class="small ${p.current_place === 1 ? 'text-success fw-bold' : 'text-danger'}">
           [${p.current_place || '?'}:${p.votes_behind_first || 0}]
         </div>`
      : '<span class="text-muted">-</span>';

    const lastUpdate = formatESTTime(p.last_snapshot_at);

    const statusBadge = p.status === 'closed'
      ? '<span class="badge bg-danger">Closed</span>'
      : '<span class="badge bg-success">Active</span>';

    tr.innerHTML = `
      <td data-label="">${escapeHtml(p.entryname)}</td>
      <td data-label="Poll ID:">${escapeHtml(p.pollid)}</td>
      <td data-label="Answer ID:">${escapeHtml(p.answerid)}</td>
      <td data-label="Status:">${statusBadge}</td>
      <td data-label="Tor:">${p.use_tor ? '<span class="badge bg-warning text-dark">Yes</span>' : '<span class="badge bg-secondary">No</span>'}</td>
      <td data-label="Stats:">${stats}</td>
      <td data-label="Last Updated:" class="small">${lastUpdate}</td>
      <td data-label="Actions:">
        <div class="dropdown poll-actions-dropdown">
          <button class="btn btn-sm btn-outline-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-expanded="false">
            <i class="bi bi-three-dots-vertical"></i><span class="d-none d-md-inline ms-1">Actions</span>
          </button>
          <ul class="dropdown-menu dropdown-menu-end">
            <li><a class="dropdown-item btn-add-to-queue" href="#" data-id="${p.id}" data-pollid="${escapeHtml(p.pollid)}" data-answerid="${escapeHtml(p.answerid)}" data-name="${escapeHtml(p.entryname)}" data-use-tor="${p.use_tor}">
              <i class="bi bi-plus-circle text-success"></i>Add to Queue
            </a></li>
            <li><a class="dropdown-item" href="https://poll.fm/${escapeHtml(p.pollid)}/results/" target="_blank" rel="noopener noreferrer">
              <i class="bi bi-box-arrow-up-right text-primary"></i>Go To Poll
            </a></li>
            <li><hr class="dropdown-divider"></li>
            <li><a class="dropdown-item btn-view-snapshot" href="#" data-id="${p.id}">
              <i class="bi bi-eye text-info"></i>View Snapshot
            </a></li>
            <li><a class="dropdown-item btn-refresh-results" href="#" data-id="${p.id}">
              <i class="bi bi-arrow-clockwise text-primary"></i>Refresh Results
            </a></li>
            <li><a class="dropdown-item btn-edit-poll" href="#" data-id="${p.id}">
              <i class="bi bi-pencil text-secondary"></i>Edit
            </a></li>
            <li><hr class="dropdown-divider"></li>
            <li><a class="dropdown-item btn-delete-poll" href="#" data-id="${p.id}">
              <i class="bi bi-trash text-danger"></i>Delete
            </a></li>
          </ul>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });

  // Attach listeners
  document.querySelectorAll('.btn-add-to-queue').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      console.log('[Add to Queue] Button clicked');

      try {
        const pollId = e.currentTarget.dataset.id;
        const pollid = e.currentTarget.dataset.pollid;
        const answerid = e.currentTarget.dataset.answerid;
        const name = e.currentTarget.dataset.name;
        const useTor = e.currentTarget.dataset.useTor === '1' || e.currentTarget.dataset.useTor === 'true';

        console.log('[Add to Queue] Poll data:', { pollId, pollid, answerid, name, useTor });

        // Switch to Queue tab using the correct selector
        document.querySelectorAll('.nav-link').forEach(link => link.classList.remove('active'));
        document.querySelectorAll('.content-section').forEach(section => section.classList.add('d-none'));

        // Find and activate the Queue tab button
        const queueTabButton = document.querySelector('[data-target="section-queue"]');
        const queueSection = document.getElementById('section-queue');

        console.log('[Add to Queue] Queue elements:', { queueTabButton, queueSection });

        if (queueTabButton) {
          queueTabButton.classList.add('active');
          console.log('[Add to Queue] Queue tab activated');
        }
        if (queueSection) {
          queueSection.classList.remove('d-none');
          console.log('[Add to Queue] Queue section shown');
        }

        // Pre-populate the queue modal form
        const pollIdInput = document.getElementById('q_poll_id');
        const pollidInput = document.getElementById('q_pollid');
        const answeridInput = document.getElementById('q_answerid');
        const nameInput = document.getElementById('q_name');
        const torCheckbox = document.getElementById('q_use_tor');

        console.log('[Add to Queue] Form elements:', { pollIdInput, pollidInput, answeridInput, nameInput, torCheckbox });

        if (pollIdInput) pollIdInput.value = pollId;
        if (pollidInput) pollidInput.value = pollid;
        if (answeridInput) answeridInput.value = answerid;
        if (nameInput) nameInput.value = name;
        if (torCheckbox) torCheckbox.checked = useTor;

        // Clear the poll select dropdown
        const pollSelect = document.getElementById('pollSelect');
        if (pollSelect) pollSelect.value = '';

        // Wait a moment for the tab to switch, then open the modal
        setTimeout(() => {
          const modalElement = document.getElementById('addQueueModal');
          console.log('[Add to Queue] Modal element:', modalElement);

          if (modalElement) {
            const addQueueModal = new bootstrap.Modal(modalElement);
            addQueueModal.show();
            console.log('[Add to Queue] Modal opened');

            // Focus on votes input for quick entry
            setTimeout(() => {
              const votesInput = document.getElementById('q_votes');
              if (votesInput) {
                votesInput.focus();
                console.log('[Add to Queue] Votes input focused');
              }
            }, 300);
          } else {
            console.error('[Add to Queue] Modal element not found!');
          }
        }, 100);

        showToast(`Pre-filled queue form with "${name}"`, 'info');
      } catch (error) {
        console.error('[Add to Queue] Error:', error);
        showToast('Error opening queue form: ' + error.message, 'danger');
      }
    });
  });

  document.querySelectorAll('.btn-delete-poll').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      if (!confirm('Delete this poll?')) return;
      const id = e.currentTarget.dataset.id;
      try {
        await authedFetch(`/polls/${id}`, { method: 'DELETE' });
        refreshPolls();
      } catch (err) {
        showToast(err.message, 'danger');
      }
    });
  });

  document.querySelectorAll('.btn-refresh-results').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const id = e.currentTarget.dataset.id;
      const button = e.currentTarget;
      const icon = button.querySelector('i');

      if (icon) icon.classList.add('spin-anim');
      button.disabled = true;

      try {
        await authedFetch(`/polls/${id}/refresh`, { method: 'POST' });
        showToast('Results refreshed', 'success');
        refreshPolls();
      } catch (err) {
        showToast('Failed to refresh: ' + err.message, 'danger');
        // Only re-enable if button still exists in DOM
        if (document.body.contains(button)) {
          button.disabled = false;
          if (icon) icon.classList.remove('spin-anim');
        }
      }
    });
  });

  document.querySelectorAll('.btn-view-snapshot').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const id = e.currentTarget.dataset.id;
      await showPollSnapshot(id);
    });
  });

  document.querySelectorAll('.btn-edit-poll').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const id = e.currentTarget.dataset.id;
      await openEditPollModal(id);
    });
  });

  recentPolls.forEach(p => {
    const opt = el('option', { value: p.id }, `${p.entryname} — ${p.pollid}`);
    opt.dataset.pollid = p.pollid;
    opt.dataset.answerid = p.answerid;
    opt.dataset.name = p.entryname;
    opt.dataset.use_tor = p.use_tor;
    sel.appendChild(opt);
  });
}

// Auto-fill poll fields when poll is selected
document.getElementById('pollSelect').addEventListener('change', (e) => {
  const selectedOption = e.target.options[e.target.selectedIndex];
  if (selectedOption.value) {
    document.getElementById('q_pollid').value = selectedOption.dataset.pollid || '';
    document.getElementById('q_answerid').value = selectedOption.dataset.answerid || '';
    document.getElementById('q_name').value = selectedOption.dataset.name || '';
    document.getElementById('q_use_tor').checked = (selectedOption.dataset.use_tor == '1');
  } else {
    document.getElementById('q_pollid').value = '';
    document.getElementById('q_answerid').value = '';
    document.getElementById('q_name').value = '';
    document.getElementById('q_use_tor').checked = false;
  }
});

let queuePage = 1;
const queuePageSize = 10;
let queueLast7Days = false;

async function refreshQueue() {
  let items = await fetchQueue();

  // Filter by last 7 days if enabled
  if (queueLast7Days) {
    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
    items = items.filter(it => new Date(it.created_at) >= sevenDaysAgo);
  }

  // Filter items based on selected status
  if (queueFilter !== 'all') {
    items = items.filter(it => it.status === queueFilter);
  }

  // Sort by started_at descending (running/completed), then created_at descending (queued)
  items.sort((a, b) => {
    // Prioritize running items
    if (a.status === 'running' && b.status !== 'running') return -1;
    if (b.status === 'running' && a.status !== 'running') return 1;

    // Then sort by start time (newest first)
    const dateA = a.started_at ? new Date(a.started_at) : new Date(a.created_at);
    const dateB = b.started_at ? new Date(b.started_at) : new Date(b.created_at);
    return dateB - dateA;
  });

  // Pagination
  const totalItems = items.length;
  const totalPages = Math.ceil(totalItems / queuePageSize);
  if (queuePage > totalPages && totalPages > 0) queuePage = totalPages;
  if (queuePage < 1) queuePage = 1;

  const startIdx = (queuePage - 1) * queuePageSize;
  const endIdx = startIdx + queuePageSize;
  const pageItems = items.slice(startIdx, endIdx);

  // Update pagination controls
  updatePaginationControls(totalItems, totalPages);

  const tbody = document.querySelector('#queueTable tbody');
  tbody.innerHTML = '';

  // Responsive view: Table rows for desktop, Cards for mobile (handled via CSS classes)
  pageItems.forEach(it => {
    const tr = document.createElement('tr');
    tr.dataset.itemId = it.id;
    tr.dataset.votesTotal = it.votes; // Store for updates

    // Render row content
    tr.innerHTML = renderQueueItemContent(it);

    // Add event listeners to buttons
    attachQueueItemListeners(tr, it);

    tbody.appendChild(tr);
  });
}

function renderQueueItemContent(it) {
  const statusBadge = statusToBadge(it.status);
  const startTime = formatESTTime(it.started_at);
  const endTime = formatESTTime(it.completed_at);

  // Poll results link
  const pollLink = `<a href="https://poll.fm/${it.pollid}/results" target="_blank" class="text-decoration-none">${escapeHtml(it.pollid)}</a>`;

  // Progress display - redesigned for better visibility
  const votesCast = it.votes_cast || 0;
  const votesTotal = it.votes || 1;
  const progress = Math.round((votesCast / votesTotal) * 100);

  // Determine progress bar color based on status and progress
  let progressBarClass = 'bg-primary';
  if (it.status === 'completed') {
    progressBarClass = 'bg-success';
  } else if (it.status === 'canceled') {
    progressBarClass = 'bg-danger';
  } else if (it.status === 'paused') {
    progressBarClass = 'bg-warning';
  }

  const progressBar = `
    <div class="d-flex align-items-center gap-2">
      <div class="progress flex-grow-1" style="height: 24px; min-width: 100px;">
        <div class="progress-bar ${progressBarClass} ${it.status === 'running' ? 'progress-bar-striped progress-bar-animated' : ''}" 
             role="progressbar" style="width: ${progress}%" 
             aria-valuenow="${progress}" aria-valuemin="0" aria-valuemax="100">
        </div>
      </div>
      <div class="text-nowrap small fw-bold" style="min-width: 80px;">
        <span class="text-primary">${votesCast.toLocaleString()}</span>
        <span class="text-muted">/</span>
        <span class="text-dark">${votesTotal.toLocaleString()}</span>
        <div class="text-muted" style="font-size: 0.75rem;">${progress}%</div>
      </div>
    </div>
  `;

  // Success rate badge
  const votesSuccess = it.votes_success || 0;
  const successRate = it.success_rate || 0;
  const badgeClass = successRate >= 80 ? 'bg-success' : (successRate >= 60 ? 'bg-warning text-dark' : 'bg-danger');
  const successBadge = votesCast > 0
    ? `<span class="badge ${badgeClass}">${votesSuccess}/${votesCast} (${successRate.toFixed(1)}%)</span>`
    : '<span class="badge bg-secondary">-</span>';

  // Current status text (only for running items)
  let statusText = '';
  if (it.status === 'running') {
    const currentStatus = it.current_status || '-';
    const lastUpdate = it.last_update ? new Date(it.last_update).toLocaleTimeString() : '';
    statusText = lastUpdate
      ? `<div class="small mt-1">${escapeHtml(currentStatus)}</div><div class="small text-muted">Updated: ${lastUpdate}</div>`
      : `<div class="small mt-1">${escapeHtml(currentStatus)}</div>`;
  }

  // Mobile card view structure (hidden on desktop via CSS)
  const mobileCard = `
    <td class="d-md-none p-0" colspan="9">
      <div class="p-2">
        <div class="d-flex justify-content-between mb-2">
          <strong>#${it.id} ${escapeHtml(it.queue_name || 'Queue Item')}</strong>
          ${statusBadge}
        </div>
        <div class="mb-2 small text-muted">Poll: ${pollLink} / ${escapeHtml(it.answerid)}</div>
        <div class="mb-2">${progressBar}</div>
        <div class="d-flex justify-content-between mb-2 small">
          <span>Success: ${successBadge}</span>
          <span>${it.status === 'running' ? statusText : ''}</span>
        </div>
        <div class="d-flex justify-content-end gap-2 action-buttons">
          <!-- Buttons injected via JS -->
        </div>
      </div>
    </td>
  `;

  // Desktop table view (hidden on mobile via CSS)
  const desktopRow = `
    <td class="d-none d-md-table-cell">${it.id}</td>
    <td class="d-none d-md-table-cell">${escapeHtml(it.queue_name || '-')}</td>
    <td class="d-none d-md-table-cell">${pollLink} / ${escapeHtml(it.answerid)}</td>
    <td class="d-none d-md-table-cell" style="min-width: 200px">${progressBar}</td>
    <td class="d-none d-md-table-cell">${successBadge}</td>
    <td class="d-none d-md-table-cell small">${startTime}</td>
    <td class="d-none d-md-table-cell small">${endTime}</td>
    <td class="d-none d-md-table-cell">${statusBadge}${statusText}</td>
    <td class="d-none d-md-table-cell action-buttons"></td>
  `;

  return mobileCard + desktopRow;
}

function attachQueueItemListeners(tr, it) {
  // Helper to add buttons to both mobile and desktop containers
  const addBtn = (btn) => {
    tr.querySelectorAll('.action-buttons').forEach(container => {
      const clone = btn.cloneNode(true);
      container.appendChild(clone);
      // Re-attach listener to the clone
      clone.addEventListener('click', btn.onclick);
      // Initialize tooltip
      new bootstrap.Tooltip(clone);
    });
  };

  // View Details button (for all items)
  const btnDetails = el('button', {
    class: 'btn btn-sm btn-outline-info me-1',
    'data-bs-toggle': 'tooltip',
    'title': 'View Details'
  });
  btnDetails.innerHTML = '<i class="bi bi-eye"></i>';
  btnDetails.onclick = () => showQueueDetails(it.id);
  addBtn(btnDetails);

  // Start button
  if (it.status === 'queued') {
    const btn = el('button', {
      class: 'btn btn-sm btn-primary me-1',
      'data-bs-toggle': 'tooltip',
      'title': 'Start Job'
    });
    btn.innerHTML = '<i class="bi bi-play-fill"></i>';
    btn.onclick = async () => {
      await authedFetch(`/queue/${it.id}/start`, { method: 'POST' });
      showToast('Started job #' + it.id, 'success');
      refreshQueue();
    };
    addBtn(btn);
  }

  // View Logs button
  if (it.status === 'running' && it.worker_id) {
    const btn = el('button', {
      class: 'btn btn-sm btn-info me-1',
      'data-bs-toggle': 'tooltip',
      'title': 'View Logs'
    });
    btn.innerHTML = '<i class="bi bi-file-text"></i>';
    btn.onclick = () => {
      showLogModal(it.worker_id, 'Connecting to log stream...');
      openLogStream(it.worker_id);
    };
    addBtn(btn);
  }

  // Pause button (for running items)
  if (it.status === 'running') {
    const btn = el('button', {
      class: 'btn btn-sm btn-warning me-1',
      'data-bs-toggle': 'tooltip',
      'title': 'Pause Job'
    });
    btn.innerHTML = '<i class="bi bi-pause-fill"></i>';
    btn.onclick = async () => {
      await authedFetch(`/queue/${it.id}/pause`, { method: 'POST' });
      showToast('Paused job #' + it.id, 'warning');
      refreshQueue();
    };
    addBtn(btn);
  }

  // Resume button (for paused items)
  if (it.status === 'paused') {
    const btn = el('button', {
      class: 'btn btn-sm btn-success me-1',
      'data-bs-toggle': 'tooltip',
      'title': 'Resume Job'
    });
    btn.innerHTML = '<i class="bi bi-play-fill"></i>';
    btn.onclick = async () => {
      await authedFetch(`/queue/${it.id}/resume`, { method: 'POST' });
      showToast('Resumed job #' + it.id, 'success');
      refreshQueue();
    };
    addBtn(btn);
  }

  // Cancel button
  if (it.status === 'queued' || it.status === 'running' || it.status === 'paused') {
    const btn = el('button', {
      class: 'btn btn-sm btn-danger',
      'data-bs-toggle': 'tooltip',
      'title': 'Cancel Job'
    });
    btn.innerHTML = '<i class="bi bi-x-lg"></i>';
    btn.onclick = async () => {
      await authedFetch(`/queue/${it.id}/cancel`, { method: 'POST' });
      showToast('Canceled job #' + it.id, 'warning');
      refreshQueue();
    };
    addBtn(btn);
  }

  // Run Again button
  if (it.status === 'completed' || it.status === 'canceled') {
    const btn = el('button', {
      class: 'btn btn-sm btn-secondary',
      'data-bs-toggle': 'tooltip',
      'title': 'Run Again'
    });
    btn.innerHTML = '<i class="bi bi-arrow-repeat"></i>';
    btn.onclick = async () => {
      if (confirm(`Run job #${it.id} again?`)) {
        await authedFetch(`/queue/${it.id}/retry`, { method: 'POST' });
        showToast('Job queued again', 'success');
        refreshQueue();
      }
    };
    addBtn(btn);
  }
}

function updatePaginationControls(totalItems, totalPages) {
  const container = document.getElementById('queuePagination');
  if (!container) return; // Need to add this element to HTML

  if (totalPages <= 1) {
    container.innerHTML = '';
    return;
  }

  let html = `
    <nav aria-label="Queue pagination">
      <ul class="pagination pagination-sm justify-content-center mb-0">
        <li class="page-item ${queuePage === 1 ? 'disabled' : ''}">
          <button class="page-link" onclick="changeQueuePage(${queuePage - 1})">Previous</button>
        </li>
        <li class="page-item disabled">
          <span class="page-link">Page ${queuePage} of ${totalPages} (${totalItems} items)</span>
        </li>
        <li class="page-item ${queuePage === totalPages ? 'disabled' : ''}">
          <button class="page-link" onclick="changeQueuePage(${queuePage + 1})">Next</button>
        </li>
      </ul>
    </nav>
  `;
  container.innerHTML = html;
}

window.changeQueuePage = function (newPage) {
  queuePage = newPage;
  refreshQueue();
};

function updateQueueItemProgress(data) {
  const tr = document.querySelector(`tr[data-item-id="${data.item_id}"]`);
  if (!tr) return;

  // Re-render the entire content to update both mobile and desktop views
  // We need to fetch the full item data or merge the update
  // Since we don't have full item data here, we'll just update the specific fields we know about
  // But wait, renderQueueItemContent needs the full object.
  // Simpler approach: Just trigger a refresh if it's a running item, or manually update DOM elements

  // Let's manually update for performance
  const votesCast = data.votes_cast || 0;
  const votesTotal = parseInt(tr.dataset.votesTotal) || 100;
  const progress = Math.round((votesCast / votesTotal) * 100);

  // Update progress bars (mobile and desktop)
  tr.querySelectorAll('.progress-bar').forEach(bar => {
    bar.style.width = `${progress}%`;
    bar.setAttribute('aria-valuenow', progress);
    bar.textContent = `${votesCast}/${votesTotal}`;
  });

  // Update success badges
  const votesSuccess = data.votes_success || 0;
  const successRate = data.success_rate || 0;
  const badgeClass = successRate >= 80 ? 'bg-success' : (successRate >= 60 ? 'bg-warning text-dark' : 'bg-danger');
  const successBadgeHtml = `<span class="badge ${badgeClass}">${votesSuccess}/${votesCast} (${successRate.toFixed(1)}%)</span>`;

  // This is tricky because we have multiple places. 
  // Let's just re-fetch the queue for simplicity and correctness since we're polling anyway
  // refreshQueue(); // Actually, we don't want to re-fetch everything on every socket event

  // Let's just rely on the 2s polling interval for now, as it calls refreshQueue()
  // which re-renders everything correctly.
}

function statusToBadge(s) {
  const map = {
    queued: '<span class="badge bg-secondary">queued</span>',
    running: '<span class="badge bg-primary">running</span>',
    paused: '<span class="badge bg-warning text-dark">paused</span>',
    completed: '<span class="badge bg-success">completed</span>',
    canceled: '<span class="badge bg-danger">canceled</span>'
  };
  return map[s] || `<span class="badge bg-light text-dark">${escapeHtml(s)}</span>`;
}

function escapeHtml(s) {
  if (!s) return '';
  return String(s).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
}

async function refreshWorkers() {
  const res = await authedFetch('/workers');
  const data = await res.json();
  const list = document.getElementById('workerList');
  list.innerHTML = '';
  data.forEach(w => {
    const li = document.createElement('li');
    li.className = 'list-group-item d-flex justify-content-between align-items-start';
    const left = document.createElement('div');
    left.innerHTML = `<strong>#${w.id}</strong> PID: ${w.pid || 'N/A'} — Item: ${w.item_id} <br><small>${w.start_time || ''} — ${w.end_time || ''}</small>`;
    const btns = document.createElement('div');
    const view = document.createElement('button');
    view.className = 'btn btn-sm btn-outline-primary me-2';
    view.innerHTML = '<i class="bi bi-file-earmark-text"></i> Log';
    view.addEventListener('click', async () => {
      // open modal and start SSE stream for live logs
      showLogModal(w.id, 'Loading live log...');
      openLogStream(w.id);
    });
    btns.appendChild(view);
    li.appendChild(left);
    li.appendChild(btns);
    list.appendChild(li);
  });
}

document.getElementById('pollForm').addEventListener('submit', async function addPoll(e) {
  e.preventDefault();
  const entryname = document.getElementById('entryname').value;
  const pollid = document.getElementById('pollid').value;
  const answerid = document.getElementById('answerid').value;
  const use_tor = document.getElementById('use_tor').checked ? 1 : 0;
  if (!entryname || !pollid || !answerid) return showToast('All fields required', 'warning');
  await authedFetch('/polls', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ entryname, pollid, answerid, use_tor }) });
  showToast('Poll added', 'success');
  document.getElementById('pollForm').reset();
  bootstrap.Modal.getInstance(document.getElementById('createPollModal')).hide();
  refreshPolls();
});

// Modal handlers
document.getElementById('btnNewPoll').addEventListener('click', () => {
  const modal = new bootstrap.Modal(document.getElementById('createPollModal'));
  modal.show();
});

document.getElementById('btnAddQueue').addEventListener('click', () => {
  const modal = new bootstrap.Modal(document.getElementById('addQueueModal'));
  modal.show();
});

document.getElementById('queueForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const pollSelect = document.getElementById('pollSelect').value;
  const q_name = document.getElementById('q_name').value;
  const q_pollid = document.getElementById('q_pollid').value;
  const q_answerid = document.getElementById('q_answerid').value;
  const votes = document.getElementById('q_votes').value;
  const threads = document.getElementById('q_threads').value;
  const per_run = document.getElementById('q_per_run').value;
  const pause = document.getElementById('q_pause').value;
  const use_vpn = document.getElementById('q_use_vpn').checked ? 1 : 0;
  const use_tor = document.getElementById('q_use_tor').checked ? 1 : 0;

  const payload = {};
  if (pollSelect) payload.poll_db_id = pollSelect;
  if (q_name) payload.queue_name = q_name;
  if (q_pollid) payload.pollid = q_pollid;
  if (q_answerid) payload.answerid = q_answerid;
  payload.votes = votes; payload.threads = threads; payload.per_run = per_run; payload.pause = pause;
  payload.use_vpn = use_vpn;
  payload.use_tor = use_tor;

  await authedFetch('/queue', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });

  // Success - close modal and refresh
  showToast('Added to queue', 'success');
  document.getElementById('queueForm').reset();
  document.getElementById('q_use_vpn').checked = true;
  document.getElementById('q_use_tor').checked = false;

  const modalEl = document.getElementById('addQueueModal');
  const modal = bootstrap.Modal.getInstance(modalEl);
  if (modal) {
    modal.hide();
  }

  refreshQueue();
});

// wrapper to include token if present and handle 401 (redirect to login)
async function authedFetch(url, opts = {}) {
  opts.headers = opts.headers || {};
  const token = sessionStorage.getItem('AUTO_VOTER_TOKEN');
  if (token) { opts.headers['Authorization'] = 'Bearer ' + token; }
  // ensure cookies are sent for session-based auth (same-origin)
  if (!opts.credentials) opts.credentials = 'same-origin';
  const res = await fetch(url, opts);
  if (res.status === 401) {
    // redirect to login
    showLoginModal();
    throw new Error('Unauthorized: please log in');
  }
  return res;
}

function showLoginModal() {
  if (loginModalShown) return; // avoid multiple modals
  loginModalShown = true;
  const modal = new bootstrap.Modal(document.getElementById('loginModal'), { backdrop: 'static', keyboard: false });
  modal.show();
}

// initial load (show login if protected endpoints fail)
initializeSocketIO(); // start Socket.IO client

// Wrap in async IIFE to properly handle authentication errors
(async () => {
  try {
    await refreshPolls();
    await refreshQueue();
    await refreshWorkers();
    await refreshSchedulerStatus();
    await refreshPollSchedulerStatus();

    // Load settings (non-critical, don't fail if not authenticated)
    try {
      await loadDaysToPurge();
    } catch (e) {
      console.log('Could not load days_to_purge (not critical):', e.message);
    }
  } catch (e) {
    // If any fetch fails with 401, the login modal will already be shown by authedFetch
    console.log('Initial data fetch failed, login required');
  }
})();

// poll for updates every 5s
setInterval(refreshQueue, 2000);  // Refresh every 2 seconds to show progress updates
setInterval(refreshWorkers, 5000);
setInterval(refreshSchedulerStatus, 5000);
setInterval(refreshPollSchedulerStatus, 5000);
document.getElementById('refreshAll').addEventListener('click', () => { refreshPolls(); refreshQueue(); refreshWorkers(); refreshSchedulerStatus(); refreshPollSchedulerStatus(); showToast('Refreshed'); });

async function refreshSchedulerStatus() {
  try {
    const data = await fetchSchedulerStatus();
    const badge = document.getElementById('schedulerStatusBadge');
    const btn = document.getElementById('btnToggleScheduler');

    if (data.running) {
      badge.className = 'badge bg-success me-2';
      badge.textContent = 'Workers Running';
      btn.textContent = 'Pause Workers';
      btn.className = 'btn btn-primary';
      btn.onclick = async () => {
        await authedFetch('/scheduler/pause', { method: 'POST' });
        refreshSchedulerStatus();
        showToast('Workers paused', 'warning');
      };
    } else {
      badge.className = 'badge bg-warning text-dark me-2';
      badge.textContent = 'Workers Paused';
      btn.textContent = 'Resume Workers';
      btn.className = 'btn btn-success';
      btn.onclick = async () => {
        try {
          await authedFetch('/scheduler/resume', { method: 'POST' });
          refreshSchedulerStatus();
          showToast('Workers resumed', 'success');
        } catch (e) { showToast(e.message, 'danger'); }
      };
    }
    btn.disabled = false;
  } catch (e) {
    console.log('Scheduler status fetch failed', e);
  }
}

// Manual trigger button handler
document.getElementById('btnTriggerScheduler').addEventListener('click', async () => {
  const btn = document.getElementById('btnTriggerScheduler');
  const icon = btn.querySelector('i');

  btn.disabled = true;
  if (icon) icon.classList.add('spin-anim');

  try {
    await authedFetch('/scheduler/trigger', { method: 'POST' });
    showToast('Scheduler triggered! Checking for queued items...', 'success');
    // Refresh queue to show any status changes
    setTimeout(() => refreshQueue(), 1000);
  } catch (e) {
    showToast('Failed to trigger scheduler: ' + e.message, 'danger');
  } finally {
    btn.disabled = false;
    if (icon) icon.classList.remove('spin-anim');
  }
});

async function refreshPollSchedulerStatus() {
  try {
    const data = await fetchPollSchedulerConfig();
    const badge = document.getElementById('pollSchedulerStatusBadge');
    const btn = document.getElementById('btnTogglePollScheduler');

    // Format last run time
    let lastRunText = '';
    if (data.last_run) {
      const lastRun = new Date(data.last_run);
      const now = new Date();
      const diffMs = now - lastRun;
      const diffMins = Math.floor(diffMs / 60000);

      if (diffMins < 1) {
        lastRunText = ' (just now)';
      } else if (diffMins < 60) {
        lastRunText = ` (${diffMins}m ago)`;
      } else {
        const diffHours = Math.floor(diffMins / 60);
        lastRunText = ` (${diffHours}h ago)`;
      }
    }

    if (data.enabled) {
      badge.className = 'badge bg-success me-2';
      badge.textContent = `Poll Results Enabled${lastRunText}`;
      badge.title = data.last_run ? `Last run: ${formatESTTime(data.last_run)}` : 'Never run';
      btn.textContent = 'Disable Poll Results';
      btn.className = 'btn btn-sm btn-outline-danger';
      btn.onclick = async () => {
        await authedFetch('/poll-scheduler/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: false })
        });
        refreshPollSchedulerStatus();
        showToast('Poll results scheduler disabled', 'warning');
      };
    } else {
      badge.className = 'badge bg-secondary me-2';
      badge.textContent = `Poll Results Disabled${lastRunText}`;
      badge.title = data.last_run ? `Last run: ${formatESTTime(data.last_run)}` : 'Never run';
      btn.textContent = 'Enable Poll Results';
      btn.className = 'btn btn-sm btn-outline-info';
      btn.onclick = async () => {
        await authedFetch('/poll-scheduler/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: true })
        });
        refreshPollSchedulerStatus();
        showToast('Poll results scheduler enabled', 'success');
      };
    }
    btn.disabled = false;

    // Update inline config fields
    const intervalInput = document.getElementById('pollSchedulerIntervalInput');
    if (intervalInput && document.activeElement !== intervalInput) {
      intervalInput.value = data.interval_minutes;
    }

    const lastRunInline = document.getElementById('pollSchedulerLastRunInline');
    if (lastRunInline) {
      lastRunInline.textContent = data.last_run ? formatESTTime(data.last_run) : 'Never';
    }
  } catch (e) {
    console.log('Poll scheduler status fetch failed', e);
  }
}

// Edit poll modal functions


// Queue filter event listeners
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[name="queueFilter"]').forEach(radio => {
    radio.addEventListener('change', (e) => {
      queueFilter = e.target.value;
      refreshQueue();
    });
  });

  // Poll filter event listeners
  const pollsLast7DaysCheckbox = document.getElementById('pollsLast7Days');
  if (pollsLast7DaysCheckbox) {
    pollsLast7DaysCheckbox.addEventListener('change', (e) => {
      pollsLast7Days = e.target.checked;
      refreshPolls();
    });
  }

  const pollsSortOrderSelect = document.getElementById('pollsSortOrder');
  if (pollsSortOrderSelect) {
    pollsSortOrderSelect.addEventListener('change', (e) => {
      pollsSortOrder = e.target.value;
      refreshPolls();
    });
  }

  // Queue Last 7 Days filter
  const queueLast7DaysCheckbox = document.getElementById('queueLast7Days');
  if (queueLast7DaysCheckbox) {
    queueLast7DaysCheckbox.addEventListener('change', (e) => {
      queueLast7Days = e.target.checked;
      queuePage = 1; // Reset to first page
      refreshQueue();
    });
  }
});

// Logout
const btnLogout = document.getElementById('btnLogout');
if (btnLogout) {
  btnLogout.addEventListener('click', async () => {
    try {
      await authedFetch('/logout', { method: 'POST' });
      window.location.reload();
    } catch (err) {
      showToast('Logout failed: ' + err.message, 'danger');
    }
  });
}

// Login modal behavior
const btnLogin = document.getElementById('btnLogin');
if (btnLogin) {
  btnLogin.addEventListener('click', () => {
    loginModalShown = false;
    showLoginModal();
  });
}

document.getElementById('saveCredentials').addEventListener('click', async () => {
  const username = document.getElementById('loginUsername').value.trim();
  const password = document.getElementById('loginPassword').value.trim();
  if (!username || !password) return showToast('Username and password required', 'warning');
  try {
    const r = await fetch('/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin', body: JSON.stringify({ username, password }) });
    if (r.ok) {
      showToast('Logged in', 'success');
      loginModalShown = false;
      const m = bootstrap.Modal.getInstance(document.getElementById('loginModal'));
      m.hide();
      // clear inputs and refresh data
      document.getElementById('loginUsername').value = '';
      document.getElementById('loginPassword').value = '';

      // Reload to update UI (show logout button)
      window.location.reload();
      refreshQueue();
      refreshWorkers();
    } else {
      const txt = await r.text();
      showToast('Login failed: ' + txt, 'danger');
    }
  } catch (e) { showToast('Login error: ' + e.message, 'danger'); }
});


// Save Poll Scheduler Interval
const btnSavePollSchedulerInterval = document.getElementById('btnSavePollSchedulerInterval');
if (btnSavePollSchedulerInterval) {
  btnSavePollSchedulerInterval.addEventListener('click', async () => {
    const interval = parseInt(document.getElementById('pollSchedulerIntervalInput').value);
    if (interval < 1) {
      return showToast('Interval must be at least 1 minute', 'warning');
    }

    try {
      await authedFetch('/poll-scheduler/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ interval_minutes: interval })
      });
      showToast('Interval saved', 'success');
      refreshPollSchedulerStatus();
    } catch (e) {
      showToast('Failed to save interval: ' + e.message, 'danger');
    }
  });
}

// Days to purge setting
const btnSaveDaysToPurge = document.getElementById('btnSaveDaysToPurge');
if (btnSaveDaysToPurge) {
  btnSaveDaysToPurge.addEventListener('click', async () => {
    const days = document.getElementById('daysToPurgeInput').value;
    try {
      await authedFetch('/settings/days_to_purge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value: days })
      });
      showToast(`Data retention set to ${days} days`, 'success');
    } catch (e) {
      showToast('Failed to update retention: ' + e.message, 'danger');
    }
  });
}

// Load days_to_purge on page load
async function loadDaysToPurge() {
  try {
    // Only load if we have a session (check if other endpoints worked)
    // This prevents showing login modal on initial page load
    const token = sessionStorage.getItem('AUTO_VOTER_TOKEN');
    if (!token) {
      console.log('Skipping days_to_purge load - not authenticated yet');
      return;
    }

    const response = await authedFetch('/settings/days_to_purge');
    const data = await response.json();
    const input = document.getElementById('daysToPurgeInput');
    if (input && data.value) {
      input.value = data.value;
    }
  } catch (e) {
    console.log('Failed to load days_to_purge setting:', e);
  }
}

// Refresh Poll Results Now
const btnRefreshPollResults = document.getElementById('btnRefreshPollResults');
if (btnRefreshPollResults) {
  btnRefreshPollResults.addEventListener('click', async () => {
    try {
      btnRefreshPollResults.disabled = true;
      btnRefreshPollResults.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Refreshing...';

      await authedFetch('/poll-scheduler/run-now', { method: 'POST' });
      showToast('Poll results refresh started', 'success');

      // Re-enable button after a delay
      setTimeout(() => {
        btnRefreshPollResults.disabled = false;
        btnRefreshPollResults.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Refresh Now';
        refreshPollSchedulerStatus();
      }, 2000);
    } catch (e) {
      showToast('Failed to start refresh: ' + e.message, 'danger');
      btnRefreshPollResults.disabled = false;
      btnRefreshPollResults.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Refresh Now';
    }
  });
}


// Socket.IO client for live log streaming (socket and socketConnected declared at top)
function initializeSocketIO() {
  if (socket) return; // already initialized
  socket = io({ reconnection: true, reconnectionDelay: 1000 });

  socket.on('connect', () => {
    socketConnected = true;
    console.log('Socket.IO connected');
  });

  socket.on('disconnect', () => {
    socketConnected = false;
    console.log('Socket.IO disconnected');
  });

  socket.on('error', (err) => {
    console.error('Socket.IO error:', err);
  });

  // Helper function to optimistically update queue item status in the DOM
  function updateQueueItemStatus(itemId, newStatus) {
    const tbody = document.querySelector('#queueTable tbody');
    if (!tbody) return;

    // Find the row for this item
    const rows = tbody.querySelectorAll('tr');
    for (const row of rows) {
      const itemIdCell = row.querySelector('td:first-child');
      if (itemIdCell && itemIdCell.textContent.trim() == itemId) {
        // Find the status badge cell (usually 3rd or 4th column)
        const statusCell = row.querySelector('.badge');
        if (statusCell) {
          // Update the badge
          statusCell.className = 'badge ' + getStatusBadgeClass(newStatus);
          statusCell.textContent = newStatus.charAt(0).toUpperCase() + newStatus.slice(1);
          console.log(`Updated item ${itemId} status to ${newStatus} in DOM`);
        }
        break;
      }
    }
  }

  // Helper to get Bootstrap badge class for status
  function getStatusBadgeClass(status) {
    switch (status) {
      case 'queued': return 'bg-secondary';
      case 'running': return 'bg-primary';
      case 'completed': return 'bg-success';
      case 'canceled': return 'bg-danger';
      default: return 'bg-secondary';
    }
  }

  socket.on('queue_update', (data) => {
    console.log('Queue update received:', data);

    // Optimistically update the UI immediately for status changes
    if (data.type === 'status' && data.item_id) {
      updateQueueItemStatus(data.item_id, data.status);
    }

    // Then refresh the full queue (non-blocking)
    refreshQueue().catch(err => {
      console.error('Failed to refresh queue:', err);
    });

    refreshWorkers().catch(err => {
      console.error('Failed to refresh workers:', err);
    });

    if (data.type === 'complete' || data.type === 'cancel') {
      showToast(`Job #${data.item_id} ${data.status || 'updated'}`, 'info');
    }
  });

  socket.on('queue_progress', (data) => {
    console.log('Queue progress update:', data);
    updateQueueItemProgress(data);
  });
}

// Modal and toast helpers (Bootstrap 5)
function showLogModal(workerId, log) {
  let modal = document.getElementById('logModal');
  if (!modal) return;
  modal.querySelector('.modal-title').textContent = `Worker ${workerId} Log`;
  modal.querySelector('.modal-body pre').textContent = log;
  const bsModal = new bootstrap.Modal(modal);
  bsModal.show();
}

// Open live-tail log stream using Socket.IO (preferred) or fall back to SSE
function openLogStream(workerId) {
  const modal = document.getElementById('logModal');
  if (!modal) return;
  const pre = modal.querySelector('.modal-body pre');
  pre.textContent = 'Connecting to worker ' + workerId + '...';

  // Try Socket.IO first
  if (socketConnected) {
    console.log(`[openLogStream] Setting up log_line listener FIRST for worker ${workerId}`);

    // Set up listener BEFORE subscribing (so we don't miss messages)
    const logLineHandler = (data) => {
      console.log(`[openLogStream] Received log_line:`, data);
      if (data && data.line) {
        // Only replace "Connecting..." on first line
        if (pre.textContent.includes('Connecting')) {
          pre.textContent = '';
        }
        pre.textContent += data.line + '\n';
        pre.scrollTop = pre.scrollHeight;
      }
    };

    socket.off('log_line'); // remove previous listener
    socket.on('log_line', logLineHandler);

    console.log(`[openLogStream] NOW subscribing to log stream for worker ${workerId}`);
    socket.emit('subscribe_log', { worker_id: workerId });

    // when modal closes, unsubscribe
    let closeHandler = () => {
      console.log(`[openLogStream] Modal closed for worker ${workerId}, unsubscribing`);
      socket.emit('unsubscribe_log', { worker_id: workerId });
      socket.off('log_line');
      modal.removeEventListener('hidden.bs.modal', closeHandler);
    };
    modal.addEventListener('hidden.bs.modal', closeHandler);
  } else {
    // Fall back to SSE
    console.log(`[openLogStream] Socket.IO not connected, falling back to SSE for worker ${workerId}`);
    const url = `/workers/${workerId}/stream`;
    const es = new EventSource(url);
    es.onmessage = function (e) {
      console.log(`[openLogStream] SSE message:`, e.data);
      pre.textContent += e.data + '\n';
      pre.scrollTop = pre.scrollHeight;
    };
    es.onerror = function () {
      console.error(`[openLogStream] SSE error`);
      try { es.close(); } catch (e) { }
    };
    // when modal closes, close the eventsource
    let closeHandler = () => {
      console.log(`[openLogStream] Modal closed for worker ${workerId}, closing SSE`);
      try { es.close(); } catch (e) { }
      modal.removeEventListener('hidden.bs.modal', closeHandler);
    };
    modal.addEventListener('hidden.bs.modal', closeHandler);
  }
}

function showToast(message, level = 'info') {
  const container = document.getElementById('toastContainer');
  const toastEl = document.createElement('div');
  toastEl.className = 'toast align-items-center text-bg-light border-0';
  toastEl.role = 'status';
  toastEl.ariaLive = 'polite';
  toastEl.ariaAtomic = 'true';
  toastEl.innerHTML = `<div class="d-flex"><div class="toast-body">${escapeHtml(message)}</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button></div>`;
  container.appendChild(toastEl);
  const bs = new bootstrap.Toast(toastEl, { delay: 3000 });
  bs.show();
  toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
}

// Tab switching logic
document.addEventListener('DOMContentLoaded', () => {
  // Tab navigation handlers
  document.querySelectorAll('.navbar.fixed-bottom .nav-link').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const targetId = e.currentTarget.dataset.target;
      switchTab(targetId);
    });
  });

  // Initial tab load (default to Polls)
  switchTab('section-polls');
});

function switchTab(targetId) {
  // Hide all sections
  document.querySelectorAll('.content-section').forEach(el => el.classList.add('d-none'));

  // Show target section
  const target = document.getElementById(targetId);
  if (target) target.classList.remove('d-none');

  // Update nav active state
  document.querySelectorAll('.navbar.fixed-bottom .nav-link').forEach(btn => {
    btn.classList.remove('active');
    btn.classList.remove('text-primary'); // Bootstrap primary color for active
    if (btn.dataset.target === targetId) {
      btn.classList.add('active');
      btn.classList.add('text-primary');
    }
  });

  // Refresh data for the new tab
  if (targetId === 'section-polls') refreshPolls();
  if (targetId === 'section-queue') refreshQueue();
  if (targetId === 'section-workers') refreshWorkers();
  if (targetId === 'section-settings') {
    refreshSchedulerStatus();
    refreshPollSchedulerStatus();
    refreshSettings();
  }
}

async function refreshSettings() {
  try {
    const res = await authedFetch('/settings/concurrency');
    const data = await res.json();

    const inputWorkers = document.getElementById('settingMaxWorkers');
    if (inputWorkers) inputWorkers.value = data.max_concurrent_workers;

    const inputInterval = document.getElementById('settingSchedulerInterval');
    if (inputInterval) inputInterval.value = data.scheduler_interval;
  } catch (e) {
    console.error('Failed to fetch settings:', e);
  }
}

// Save Concurrency Settings
const btnSaveConcurrencySettings = document.getElementById('btnSaveConcurrencySettings');
if (btnSaveConcurrencySettings) {
  btnSaveConcurrencySettings.addEventListener('click', async () => {
    const valWorkers = document.getElementById('settingMaxWorkers').value;
    const valInterval = document.getElementById('settingSchedulerInterval').value;

    try {
      await authedFetch('/settings/concurrency', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          max_concurrent_workers: valWorkers,
          scheduler_interval: valInterval
        })
      });
      showToast('Settings saved', 'success');
    } catch (e) {
      showToast('Failed to save settings: ' + e.message, 'danger');
    }
  });
}

// InfluxDB Settings
const btnSaveInfluxSettings = document.getElementById('btnSaveInfluxSettings');
if (btnSaveInfluxSettings) {
  btnSaveInfluxSettings.addEventListener('click', async () => {
    const influxUrl = document.getElementById('settingInfluxUrl').value;
    const influxOrg = document.getElementById('settingInfluxOrg').value;
    const influxBucket = document.getElementById('settingInfluxBucket').value;
    const influxToken = document.getElementById('settingInfluxToken').value;

    try {
      await authedFetch('/settings/influxdb', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          influx_url: influxUrl,
          influx_org: influxOrg,
          influx_bucket: influxBucket,
          influx_token: influxToken
        })
      });
      showToast('InfluxDB settings saved', 'success');
      // Clear token field for security
      document.getElementById('settingInfluxToken').value = '';
    } catch (e) {
      showToast('Failed to save InfluxDB settings: ' + e.message, 'danger');
    }
  });
}

// Voting Behavior Settings
const btnSaveVotingSettings = document.getElementById('btnSaveVotingSettings');
if (btnSaveVotingSettings) {
  btnSaveVotingSettings.addEventListener('click', async () => {
    const vpnMode = document.getElementById('settingVpnMode').value;
    const cooldownCount = document.getElementById('settingCooldownCount').value;
    const cooldown = document.getElementById('settingCooldown').value;
    const cntToPause = document.getElementById('settingCntToPause').value;
    const longPause = document.getElementById('settingLongPause').value;

    try {
      await authedFetch('/settings/voting', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          vpnmode: vpnMode,
          cooldown_count: cooldownCount,
          cooldown: cooldown,
          cnt_to_pause: cntToPause,
          long_pause_seconds: longPause
        })
      });
      showToast('Voting settings saved', 'success');
    } catch (e) {
      showToast('Failed to save voting settings: ' + e.message, 'danger');
    }
  });
}

// Presets
const btnPresetTiger = document.getElementById('btnPresetTiger');
if (btnPresetTiger) {
  btnPresetTiger.addEventListener('click', () => applyPreset('tiger'));
}

const btnPresetLazy = document.getElementById('btnPresetLazy');
if (btnPresetLazy) {
  btnPresetLazy.addEventListener('click', () => applyPreset('lazy'));
}

async function applyPreset(preset) {
  try {
    const res = await authedFetch('/settings/presets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preset })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Applied ${preset === 'tiger' ? 'Tiger 🐯' : 'Lazy 🦥'} Mode`, 'success');
      // Update UI fields
      const schedInput = document.getElementById('settingSchedulerInterval');
      if (schedInput) schedInput.value = data.scheduler_interval;

      const pollInput = document.getElementById('pollSchedulerIntervalInput');
      if (pollInput) pollInput.value = data.poll_interval;

      // Refresh status badges
      refreshPollSchedulerStatus();
    }
  } catch (e) {
    showToast('Failed to apply preset: ' + e.message, 'danger');
  }
}

// Auto-Switch
const settingAutoSwitch = document.getElementById('settingAutoSwitch');
if (settingAutoSwitch) {
  settingAutoSwitch.addEventListener('change', async () => {
    try {
      const enabled = settingAutoSwitch.checked;
      await authedFetch('/settings/auto-switch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
      });
      showToast(`Auto-switch ${enabled ? 'enabled' : 'disabled'}`, 'success');
    } catch (e) {
      showToast('Failed to update auto-switch: ' + e.message, 'danger');
      settingAutoSwitch.checked = !settingAutoSwitch.checked; // Revert
    }
  });
}

// Load settings when settings section is shown
async function loadAllSettings() {
  try {
    // Load InfluxDB settings
    const influxRes = await authedFetch('/settings/influxdb');
    const influxData = await influxRes.json();
    document.getElementById('settingInfluxUrl').value = influxData.influx_url || '';
    document.getElementById('settingInfluxOrg').value = influxData.influx_org || '';
    document.getElementById('settingInfluxBucket').value = influxData.influx_bucket || '';

    // Load voting settings
    const votingRes = await authedFetch('/settings/voting');
    const votingData = await votingRes.json();
    document.getElementById('settingVpnMode').value = votingData.vpnmode || 2;
    document.getElementById('settingCooldownCount').value = votingData.cooldown_count || 3;
    document.getElementById('settingCooldown').value = votingData.cooldown || 92;
    document.getElementById('settingCntToPause').value = votingData.cnt_to_pause || 1;
    document.getElementById('settingLongPause').value = votingData.long_pause_seconds || 90;

    // Load Auto-Switch
    const autoSwitchRes = await authedFetch('/settings/auto-switch');
    const autoSwitchData = await autoSwitchRes.json();
    const switchEl = document.getElementById('settingAutoSwitch');
    if (switchEl) switchEl.checked = autoSwitchData.enabled;

  } catch (e) {
    console.error('Failed to load settings:', e);
  }
}

// Call loadAllSettings when navigating to settings
document.querySelectorAll('[data-section="settings"]').forEach(btn => {
  btn.addEventListener('click', () => {
    loadAllSettings();
    // Initialize tooltips after a short delay to ensure DOM is ready
    setTimeout(() => {
      const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
      const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
    }, 100);
  });
});

// Initialize tooltips on page load
// Initialize tooltips and settings on page load
document.addEventListener('DOMContentLoaded', () => {
  const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

  // Load saved settings (including auto-switch toggle)
  loadAllSettings();
});

async function showPollSnapshot(pollId) {
  try {
    const res = await authedFetch(`/polls/${pollId}/snapshot`);
    const data = await res.json();

    // Update poll summary
    document.getElementById('snapshotPollTitle').textContent = data.poll.poll_title || data.poll.entryname;
    document.getElementById('snapshotPollId').textContent = data.poll.pollid;

    const statusBadge = data.poll.status === 'closed'
      ? '<span class="badge bg-danger">Closed</span>'
      : '<span class="badge bg-success">Active</span>';
    document.getElementById('snapshotStatus').innerHTML = statusBadge;

    document.getElementById('snapshotTime').textContent = formatESTTime(data.poll.last_snapshot_at);
    document.getElementById('snapshotTimeSince').textContent = data.poll.time_since || '-';
    document.getElementById('snapshotTotalVotes').textContent = (data.poll.total_poll_votes || 0).toLocaleString();

    // Update results table
    const tbody = document.getElementById('snapshotTableBody');
    tbody.innerHTML = '';

    if (data.snapshots && data.snapshots.length > 0) {
      data.snapshots.forEach(s => {
        const row = document.createElement('tr');
        const placeClass = s.place === 1 ? 'text-success fw-bold' : '';
        row.innerHTML = `
          <td class="${placeClass}">${s.place}</td>
          <td>${escapeHtml(s.answer_text)}</td>
          <td class="d-none d-md-table-cell small text-muted">${escapeHtml(s.answerid)}</td>
          <td class="${placeClass}">${s.votes.toLocaleString()}</td>
          <td>${escapeHtml(s.percent)}</td>
          <td class="text-danger">${s.gap > 0 ? '-' + s.gap.toLocaleString() : '-'}</td>
        `;
        tbody.appendChild(row);
      });
    } else {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No snapshot data available</td></tr>';
    }

    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('pollSnapshotModal'));
    modal.show();
  } catch (err) {
    showToast('Failed to load snapshot: ' + err.message, 'danger');
  }
}

async function openEditPollModal(pollId) {
  try {
    const res = await authedFetch(`/polls`);
    const polls = await res.json();
    const poll = polls.find(p => p.id === parseInt(pollId));

    if (!poll) {
      showToast('Poll not found', 'danger');
      return;
    }

    console.log('Editing poll:', poll);

    // Get form elements
    const editPollId = document.getElementById('editPollId');
    const editPollName = document.getElementById('editPollName');
    const editPollPollId = document.getElementById('editPollPollId');
    const editPollAnswerId = document.getElementById('editPollAnswerId');
    const editPollStatus = document.getElementById('editPollStatus');
    const editPollUseTor = document.getElementById('editPollUseTor');

    if (!editPollId || !editPollName || !editPollPollId || !editPollAnswerId) {
      console.error('Edit form elements not found');
      showToast('Form elements not found', 'danger');
      return;
    }

    // Clear form first
    document.getElementById('editPollForm').reset();

    // Populate form immediately
    editPollId.value = poll.id;
    editPollName.value = poll.entryname;
    editPollPollId.value = poll.pollid;
    editPollAnswerId.value = poll.answerid;
    editPollStatus.value = poll.status || 'active';
    editPollUseTor.checked = poll.use_tor === 1;

    console.log('Form populated with:', {
      id: editPollId.value,
      name: editPollName.value,
      pollid: editPollPollId.value,
      answerid: editPollAnswerId.value,
      status: editPollStatus.value,
      tor: editPollUseTor.checked
    });

    // Show modal
    const modalEl = document.getElementById('editPollModal');
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  } catch (err) {
    console.error('Error in openEditPollModal:', err);
    showToast('Failed to load poll: ' + err.message, 'danger');
  }
}

// Save Edit Poll
const btnSaveEditPoll = document.getElementById('btnSaveEditPoll');
if (btnSaveEditPoll) {
  console.log('Save Edit Poll button found, attaching listener');
  btnSaveEditPoll.addEventListener('click', async () => {
    console.log('Save Edit Poll clicked');
    const pollId = document.getElementById('editPollId').value;
    const entryname = document.getElementById('editPollName').value;
    const pollid = document.getElementById('editPollPollId').value;
    const answerid = document.getElementById('editPollAnswerId').value;
    const status = document.getElementById('editPollStatus').value;
    const use_tor = document.getElementById('editPollUseTor').checked ? 1 : 0;

    if (!entryname || !pollid || !answerid) {
      showToast('Please fill in all required fields', 'warning');
      return;
    }

    try {
      await authedFetch(`/polls/${pollId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          entryname,
          pollid,
          answerid,
          status,
          use_tor
        })
      });

      showToast('Poll updated successfully', 'success');
      bootstrap.Modal.getInstance(document.getElementById('editPollModal')).hide();
      refreshPolls();
    } catch (err) {
      showToast('Failed to update poll: ' + err.message, 'danger');
    }
  });
}


// ===== Queue Details Modal =====

async function showQueueDetails(itemId) {
  console.log('[showQueueDetails] Opening details for item:', itemId);
  try {
    const response = await authedFetch(`/queue/${itemId}/details`);
    console.log('[showQueueDetails] Response status:', response.status);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    console.log('[showQueueDetails] Data received:', data);

    // Populate basic info
    document.getElementById('detailsItemId').textContent = `#${data.id}`;
    document.getElementById('detailsName').textContent = data.queue_name || '-';
    document.getElementById('detailsStatus').innerHTML = statusToBadge(data.status);
    document.getElementById('detailsPollId').textContent = data.pollid;
    document.getElementById('detailsPollLink').href = `https://poll.fm/${data.pollid}`;
    document.getElementById('detailsAnswerId').textContent = data.answerid;

    // Populate settings
    document.getElementById('detailsVotes').value = data.votes;
    document.getElementById('detailsThreads').value = data.threads;
    document.getElementById('detailsPerRun').value = data.per_run;
    document.getElementById('detailsPause').value = data.pause;
    document.getElementById('detailsUseVpn').checked = data.use_vpn;
    document.getElementById('detailsUseTor').checked = data.use_tor;

    // Reset to read-only mode
    document.getElementById('detailsVotes').readOnly = true;
    document.getElementById('detailsThreads').readOnly = true;
    document.getElementById('detailsPerRun').readOnly = true;
    document.getElementById('detailsPause').readOnly = true;
    document.getElementById('detailsUseVpn').disabled = true;
    document.getElementById('detailsUseTor').disabled = true;
    document.getElementById('editButtons').style.display = 'none';

    // Show edit button only for queued items
    const btnEdit = document.getElementById('btnEditSettings');
    if (data.status === 'queued') {
      btnEdit.style.display = 'block';
    } else {
      btnEdit.style.display = 'none';
    }

    // Populate progress
    document.getElementById('detailsVotesCast').textContent = (data.votes_cast || 0).toLocaleString();
    document.getElementById('detailsVotesSuccess').textContent = (data.votes_success || 0).toLocaleString();
    document.getElementById('detailsSuccessRate').textContent =
      data.success_rate ? `${data.success_rate.toFixed(1)}%` : '0%';
    document.getElementById('detailsCurrentStatus').textContent = data.current_status || '-';

    // Populate timing
    document.getElementById('detailsCreatedAt').textContent =
      data.created_at ? new Date(data.created_at).toLocaleString() : '-';
    document.getElementById('detailsStartedAt').textContent =
      data.started_at ? new Date(data.started_at).toLocaleString() : '-';
    document.getElementById('detailsCompletedAt').textContent =
      data.completed_at ? new Date(data.completed_at).toLocaleString() : '-';

    if (data.duration_seconds) {
      const hours = Math.floor(data.duration_seconds / 3600);
      const mins = Math.floor((data.duration_seconds % 3600) / 60);
      const secs = Math.floor(data.duration_seconds % 60);
      if (hours > 0) {
        document.getElementById('detailsDuration').textContent = `${hours}h ${mins}m ${secs}s`;
      } else {
        document.getElementById('detailsDuration').textContent = `${mins}m ${secs}s`;
      }
    } else {
      document.getElementById('detailsDuration').textContent = '-';
    }

    // Store item ID for editing
    document.getElementById('queueDetailsModal').dataset.itemId = itemId;

    // Show modal
    new bootstrap.Modal(document.getElementById('queueDetailsModal')).show();
  } catch (e) {
    showToast('Failed to load details: ' + e.message, 'danger');
  }
}

// Edit mode toggle
document.getElementById('btnEditSettings').addEventListener('click', () => {
  document.getElementById('detailsVotes').readOnly = false;
  document.getElementById('detailsThreads').readOnly = false;
  document.getElementById('detailsPerRun').readOnly = false;
  document.getElementById('detailsPause').readOnly = false;
  document.getElementById('detailsUseVpn').disabled = false;
  document.getElementById('detailsUseTor').disabled = false;

  document.getElementById('btnEditSettings').style.display = 'none';
  document.getElementById('editButtons').style.display = 'block';
});

// Cancel edit
document.getElementById('btnCancelEdit').addEventListener('click', () => {
  const itemId = document.getElementById('queueDetailsModal').dataset.itemId;
  showQueueDetails(itemId); // Reload original data
});

// Save changes
document.getElementById('btnSaveSettings').addEventListener('click', async () => {
  const itemId = document.getElementById('queueDetailsModal').dataset.itemId;

  try {
    await authedFetch(`/queue/${itemId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        votes: parseInt(document.getElementById('detailsVotes').value),
        threads: parseInt(document.getElementById('detailsThreads').value),
        per_run: parseInt(document.getElementById('detailsPerRun').value),
        pause: parseInt(document.getElementById('detailsPause').value),
        use_vpn: document.getElementById('detailsUseVpn').checked,
        use_tor: document.getElementById('detailsUseTor').checked
      })
    });

    showToast('Settings updated successfully', 'success');
    bootstrap.Modal.getInstance(document.getElementById('queueDetailsModal')).hide();
    refreshQueue();
  } catch (e) {
    showToast('Failed to save: ' + e.message, 'danger');
  }
});
