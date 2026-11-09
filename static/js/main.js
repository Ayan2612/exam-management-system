/**
 * Exam Management System — Main JavaScript
 * Features: AJAX seat search, animations, sidebar toggle, 
 *           capacity calculator, toast notifications
 */

'use strict';

// ══════════════════════════════════════════════
// DOCUMENT READY
// ══════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', function () {
  initSidebar();
  initAjaxSearch();
  initSeatingCalculator();
  initToasts();
  initAnimations();
  initFormValidation();
  initTableSearch();
});

// ══════════════════════════════════════════════
// SIDEBAR TOGGLE (Mobile)
// ══════════════════════════════════════════════
function initSidebar() {
  const toggleBtn = document.getElementById('sidebarToggle');
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');

  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', () => {
      sidebar.classList.toggle('show');
      if (overlay) overlay.classList.toggle('show');
    });
  }

  if (overlay) {
    overlay.addEventListener('click', () => {
      sidebar?.classList.remove('show');
      overlay.classList.remove('show');
    });
  }

  // Active nav link
  const currentPath = window.location.pathname;
  document.querySelectorAll('.nav-link').forEach(link => {
    if (link.getAttribute('href') === currentPath) {
      link.classList.add('active');
    }
  });
}

// ══════════════════════════════════════════════
// AJAX SEAT SEARCH
// ══════════════════════════════════════════════
function initAjaxSearch() {
  const searchForm = document.getElementById('seatSearchForm');
  const rollInput = document.getElementById('roll_number_input');
  const examSelect = document.getElementById('exam_select');
  const resultDiv = document.getElementById('searchResult');
  const searchBtn = document.getElementById('searchBtn');

  if (!searchForm || !rollInput || !resultDiv) return;

  let searchTimeout = null;

  // Auto-search on roll number input (debounced)
  rollInput.addEventListener('input', function () {
    clearTimeout(searchTimeout);
    const val = this.value.trim();
    if (val.length >= 3) {
      searchTimeout = setTimeout(() => performSearch(val), 500);
    } else if (val.length === 0) {
      clearResult();
    }
  });

  // Form submit
  searchForm.addEventListener('submit', function (e) {
    e.preventDefault();
    const roll = rollInput.value.trim();
    if (!roll) {
      showError(resultDiv, 'Please enter your roll number.');
      return;
    }
    performSearch(roll);
  });

  function performSearch(roll) {
    const examId = examSelect ? examSelect.value : '';
    const url = `/ajax/search-seat/?roll_number=${encodeURIComponent(roll)}&exam_id=${examId}`;

    showLoading(resultDiv);
    if (searchBtn) {
      searchBtn.disabled = true;
      searchBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Searching...';
    }

    fetch(url, {
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCookie('csrftoken'),
      }
    })
      .then(r => r.json())
      .then(data => {
        if (data.found) {
          renderResults(resultDiv, data.allocations);
        } else {
          showError(resultDiv, data.error || 'No seat found.');
        }
      })
      .catch(() => showError(resultDiv, 'Network error. Please try again.'))
      .finally(() => {
        if (searchBtn) {
          searchBtn.disabled = false;
          searchBtn.innerHTML = '<i class="bi bi-search me-2"></i>Search Seat';
        }
      });
  }

  function showLoading(container) {
    container.innerHTML = `
      <div class="text-center py-4">
        <div class="spinner-ems"></div>
        <p class="text-secondary-ems mt-2">Searching for your seat...</p>
      </div>`;
  }

  function clearResult() {
    resultDiv.innerHTML = '';
  }

  function renderResults(container, allocations) {
    if (!allocations || !allocations.length) {
      showError(container, 'No allocation found.');
      return;
    }

    const html = allocations.map((a, idx) => `
      <div class="result-card mb-3" style="animation-delay: ${idx * 0.1}s">
        <div class="d-flex justify-content-between align-items-center mb-3">
          <div>
            <h5 class="mb-1" style="color: var(--text-primary)">${a.student_name}</h5>
            <span class="badge-pill badge-primary">${a.roll_number}</span>
            <span class="badge-pill badge-info ms-1">${a.course} · Sem ${a.semester}</span>
          </div>
          <div class="d-flex gap-2">
            <a href="/admit-card/${a.allocation_id}/view/" class="btn-primary-glow btn-sm" style="padding:6px 14px;font-size:0.8rem" target="_blank">
              <i class="bi bi-eye"></i> View & Print
            </a>
            <a href="/admit-card/${a.allocation_id}/" class="btn-success-glow btn-sm" style="padding:6px 14px;font-size:0.8rem" target="_blank">
              <i class="bi bi-download"></i> PDF
            </a>
          </div>
        </div>
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0">
          <div class="result-row"><span class="result-label">Exam</span><span class="result-value">${a.exam}</span></div>
          <div class="result-row"><span class="result-label">Date</span><span class="result-value">${a.exam_date}</span></div>
          <div class="result-row"><span class="result-label">Time</span><span class="result-value">${a.exam_time}</span></div>
          <div class="result-row"><span class="result-label">Building</span><span class="result-value">${a.building}</span></div>
          <div class="result-row"><span class="result-label">Room</span><span class="result-value" style="color: #1e3a8a; font-weight: 700">${a.room_number}</span></div>
          <div class="result-row"><span class="result-label">Seat</span><span class="result-value" style="color: #15803d; font-weight: 800; font-size: 1.3rem">Seat #${a.seat_number}</span></div>
        </div>
      </div>`).join('');

    container.innerHTML = `
      <div class="d-flex align-items-center gap-2 mb-3">
        <i class="bi bi-check-circle-fill" style="color: #15803d; font-size: 1.3rem"></i>
        <span style="color: #15803d; font-weight: 600">Verified Seat Allocation Confirmed</span>
      </div>
      ${html}`;
  }
}

function showError(container, msg) {
  container.innerHTML = `
    <div class="alert-ems alert-danger">
      <i class="bi bi-exclamation-triangle-fill"></i>
      <span>${msg}</span>
    </div>`;
}

// ══════════════════════════════════════════════
// SEATING CALCULATOR (Allocation Page)
// ══════════════════════════════════════════════
function initSeatingCalculator() {
  const roomCheckboxes = document.querySelectorAll('.room-checkbox');
  const studentCheckboxes = document.querySelectorAll('.student-checkbox');
  const capacityDisplay = document.getElementById('capacityDisplay');
  const studentDisplay = document.getElementById('studentDisplay');
  const capacityBar = document.getElementById('capacityBar');
  const alertDiv = document.getElementById('capacityAlert');
  const submitBtn = document.getElementById('allocateBtn');

  if (!roomCheckboxes.length) return;

  // Try to get rooms data from embedded JSON
  const roomsDataEl = document.getElementById('roomsData');
  let roomsData = {};
  if (roomsDataEl) {
    try {
      const arr = JSON.parse(roomsDataEl.textContent);
      arr.forEach(r => { roomsData[r.id] = r; });
    } catch (e) {}
  }

  function updateCapacity() {
    let totalCap = 0;
    let totalStudents = 0;

    roomCheckboxes.forEach(cb => {
      if (cb.checked) {
        const cap = parseInt(cb.dataset.capacity || 0);
        totalCap += cap;
        // Highlight selected cards
        const card = cb.closest('.room-checkbox-card');
        if (card) card.classList.add('selected');
      } else {
        const card = cb.closest('.room-checkbox-card');
        if (card) card.classList.remove('selected');
      }
    });

    studentCheckboxes.forEach(cb => {
      if (cb.checked) totalStudents++;
    });

    if (capacityDisplay) capacityDisplay.textContent = totalCap;
    if (studentDisplay) studentDisplay.textContent = totalStudents;

    if (capacityBar && totalCap > 0) {
      const pct = Math.min((totalStudents / totalCap) * 100, 100);
      capacityBar.style.width = pct + '%';
      capacityBar.className = 'capacity-fill' + (pct > 85 ? ' warning' : '');
    }

    if (alertDiv && submitBtn) {
      if (totalStudents > totalCap && totalCap > 0) {
        alertDiv.innerHTML = `<div class="alert-ems alert-danger mt-2">
          <i class="bi bi-exclamation-triangle"></i>
          <span>Insufficient capacity: ${totalStudents} students but only ${totalCap} seats!</span>
        </div>`;
        submitBtn.disabled = true;
      } else {
        alertDiv.innerHTML = '';
        submitBtn.disabled = false;
      }
    }
  }

  roomCheckboxes.forEach(cb => cb.addEventListener('change', updateCapacity));
  studentCheckboxes.forEach(cb => cb.addEventListener('change', updateCapacity));

  // Select all students button
  const selectAllBtn = document.getElementById('selectAllStudents');
  const deselectAllBtn = document.getElementById('deselectAllStudents');

  if (selectAllBtn) {
    selectAllBtn.addEventListener('click', () => {
      studentCheckboxes.forEach(cb => cb.checked = true);
      updateCapacity();
    });
  }

  if (deselectAllBtn) {
    deselectAllBtn.addEventListener('click', () => {
      studentCheckboxes.forEach(cb => cb.checked = false);
      updateCapacity();
    });
  }
}

// ══════════════════════════════════════════════
// TOAST NOTIFICATIONS (Auto-dismiss)
// ══════════════════════════════════════════════
function initToasts() {
  const alerts = document.querySelectorAll('.alert-ems[data-dismiss]');
  alerts.forEach(alert => {
    setTimeout(() => {
      alert.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
      alert.style.opacity = '0';
      alert.style.transform = 'translateX(20px)';
      setTimeout(() => alert.remove(), 500);
    }, 5000);
  });
}

// ══════════════════════════════════════════════
// SCROLL ANIMATIONS
// ══════════════════════════════════════════════
function initAnimations() {
  // Intersection Observer for card animations
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry, i) => {
      if (entry.isIntersecting) {
        setTimeout(() => {
          entry.target.style.opacity = '1';
          entry.target.style.transform = 'translateY(0)';
        }, i * 60);
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll('.glass-card, .feature-card, .stat-counter').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(24px)';
    el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
    observer.observe(el);
  });

  // Counter animation for stat numbers
  document.querySelectorAll('[data-count]').forEach(el => {
    const target = parseInt(el.dataset.count);
    let current = 0;
    const increment = target / 60;
    const timer = setInterval(() => {
      current = Math.min(current + increment, target);
      el.textContent = Math.floor(current).toLocaleString();
      if (current >= target) clearInterval(timer);
    }, 20);
  });
}

// ══════════════════════════════════════════════
// TABLE SEARCH (Client-side filter)
// ══════════════════════════════════════════════
function initTableSearch() {
  const inlineSearch = document.getElementById('inlineTableSearch');
  const tableBody = document.getElementById('mainTableBody');

  if (!inlineSearch || !tableBody) return;

  inlineSearch.addEventListener('input', function () {
    const q = this.value.toLowerCase();
    tableBody.querySelectorAll('tr').forEach(row => {
      const text = row.textContent.toLowerCase();
      row.style.display = text.includes(q) ? '' : 'none';
    });
  });
}

// ══════════════════════════════════════════════
// FORM VALIDATION FEEDBACK
// ══════════════════════════════════════════════
function initFormValidation() {
  const forms = document.querySelectorAll('.needs-validation');
  forms.forEach(form => {
    form.addEventListener('submit', event => {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
      }
      form.classList.add('was-validated');
    });
  });
}

// ══════════════════════════════════════════════
// UTILITY: Get CSRF Token from Cookie
// ══════════════════════════════════════════════
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
      cookie = cookie.trim();
      if (cookie.startsWith(name + '=')) {
        cookieValue = decodeURIComponent(cookie.slice(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

// ══════════════════════════════════════════════
// CONFIRM DELETE DIALOGS
// ══════════════════════════════════════════════
document.querySelectorAll('[data-confirm]').forEach(btn => {
  btn.addEventListener('click', function (e) {
    if (!confirm(this.dataset.confirm || 'Are you sure?')) {
      e.preventDefault();
    }
  });
});

// ══════════════════════════════════════════════
// BUTTON RIPPLE EFFECT
// ══════════════════════════════════════════════
document.querySelectorAll('.btn-primary-glow, .btn-danger-glow, .btn-success-glow').forEach(btn => {
  btn.addEventListener('click', function (e) {
    const rect = this.getBoundingClientRect();
    const ripple = document.createElement('span');
    ripple.style.cssText = `
      position: absolute;
      border-radius: 50%;
      background: rgba(255,255,255,0.3);
      width: 10px; height: 10px;
      left: ${e.clientX - rect.left - 5}px;
      top: ${e.clientY - rect.top - 5}px;
      animation: rippleEffect 0.6s ease forwards;
      pointer-events: none;
    `;
    this.style.position = 'relative';
    this.appendChild(ripple);
    setTimeout(() => ripple.remove(), 600);
  });
});

// Add ripple keyframes dynamically
const style = document.createElement('style');
style.textContent = `
  @keyframes rippleEffect {
    to { transform: scale(30); opacity: 0; }
  }
`;
document.head.appendChild(style);
