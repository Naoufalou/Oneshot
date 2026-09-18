// Global State
let allJobs = [];
let allResumes = [];
let activeResumeFilename = "";
let viewedResumeFilename = "";
let userProfile = null;
let currentPeekJob = null;

let selectedPlatform = "";
let selectedLoc = "";
let searchQuery = "";
let option1ClickEnabled = true;
let filterOnly1Click = false; // Show all fresh offers by default!
let selectedStatus = "";

function formatRelativeTime(dateStr) {
  if (!dateStr) return "Récent";
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diffSec = Math.max(0, Math.floor((now - d) / 1000));
    if (diffSec < 60) return "À l'instant";
    if (diffSec < 3600) return `Il y a ${Math.max(1, Math.floor(diffSec / 60))} min`;
    if (diffSec < 86400) return `Il y a ${Math.floor(diffSec / 3600)}h`;
    const days = Math.floor(diffSec / 86400);
    if (days === 1) return "Hier";
    if (days < 30) return `Il y a ${days} jours`;
    return `Il y a ${Math.floor(days / 30)} mois`;
  } catch (e) {
    return "Récent";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  init3DMotionBanner();
  setupThemeEngine();
  setupBannerCustomizer();
  setupTabs();
  setupFilters();
  setupResumeManager();
  setupSidePeek();
  setupBatchApply();
  setupSettings();
  setupPlatformsManager();
  setupPlatformCatalogAndSearch();
  setupArovaExperience();
  initGameAudio();

  // Initial load
  loadResumes();
  loadJobs();
  loadConfig();
  loadPlatformsStatus();
  loadCustomPlatforms();

  // Periodic background refresh
  setInterval(() => {
    loadJobs(false);
  }, 20000);
});

/* ==========================================================
   LUDIQUE 1-CLICK PROGRESS HERO ENGINE
   Large, playful, gamified progress bar on the main dashboard
   with flying rocket mascot, stars particle stream, live counters & victory fireworks.
========================================================== */
function initLudiqueProgress() {
  const hero = document.getElementById("ludique-progress-hero");
  const canvas = document.getElementById("ludique-stars-canvas");
  const gaugeStroke = document.getElementById("ludique-gauge-stroke");
  const rocketRotator = document.getElementById("ludique-rocket-rotator");
  const giantPct = document.getElementById("ludique-giant-pct");
  const gaugeLabel = document.getElementById("ludique-gauge-label");
  const stepText = document.getElementById("ludique-step-text");
  const titleElem = document.getElementById("ludique-main-title");
  const subElem = document.getElementById("ludique-subtitle");
  const mascotIcon = document.getElementById("ludique-mascot-icon");
  const xpBadge = document.getElementById("ludique-xp-badge");
  const currPlatform = document.getElementById("ludique-curr-platform");
  const currPlatBadge = document.getElementById("ludique-curr-plat-badge");
  const resumeNameElem = document.getElementById("ludique-resume-name");
  const consoleFeed = document.getElementById("ludique-console-feed");
  const victoryRow = document.getElementById("ludique-victory-row");
  const victoryMsg = document.getElementById("ludique-victory-msg");
  const countSuccess = document.getElementById("ludique-count-success");
  const countRemaining = document.getElementById("ludique-count-remaining");
  const countSkipped = document.getElementById("ludique-count-skipped");
  const btnStop = document.getElementById("btn-ludique-stop");
  const btnClose = document.getElementById("btn-ludique-close");
  const btnViewApplied = document.getElementById("btn-ludique-view-applied");

  const CIRCUMFERENCE = 716.28; // 2 * PI * 114 (viewBox 280x280)

  let animFrameId = null;
  let particles = [];
  let currentPct = 0;
  let isRunning = false;
  let lastLoggedMsg = "";

  function addConsoleLog(msg, type = "info") {
    if (!consoleFeed || !msg || msg === lastLoggedMsg) return;
    lastLoggedMsg = msg;

    const now = new Date();
    const timeStr = now.toTimeString().split(" ")[0];

    const line = document.createElement("div");
    line.className = `ludique-log-line ${type}`;
    line.innerHTML = `
      <span class="ludique-log-time">${timeStr}</span>
      <span class="ludique-log-msg">${escapeHtml(msg)}</span>
    `;

    consoleFeed.appendChild(line);
    // Keep max 20 logs in feed
    while (consoleFeed.children.length > 20) {
      consoleFeed.removeChild(consoleFeed.firstChild);
    }
    consoleFeed.scrollTop = consoleFeed.scrollHeight;
  }

  function updateChecklist(pct, isFinished = false) {
    // Checklist panel removed per user request
  }

  function initCanvas() {
    if (!canvas || !canvas.parentElement) return;
    const ctx = canvas.getContext("2d");
    let w = (canvas.width = canvas.parentElement.offsetWidth || 900);
    let h = (canvas.height = canvas.parentElement.offsetHeight || 280);

    const resize = () => {
      if (canvas.parentElement) {
        w = canvas.width = canvas.parentElement.offsetWidth || 900;
        h = canvas.height = canvas.parentElement.offsetHeight || 280;
      }
    };
    window.removeEventListener("resize", resize);
    window.addEventListener("resize", resize);

    particles = [];
    const colors = ["#38bdf8", "#818cf8", "#c084fc", "#10b981", "#fbbf24"];
    for (let i = 0; i < 50; i++) {
      particles.push({
        x: Math.random() * w,
        y: Math.random() * h,
        radius: Math.random() * 2.2 + 0.8,
        vx: Math.random() * 1.8 + 0.6,
        color: colors[Math.floor(Math.random() * colors.length)],
        alpha: Math.random() * 0.75 + 0.25,
      });
    }

    function loop() {
      if (!ctx) return;
      ctx.clearRect(0, 0, w, h);
      const speedMult = 1 + currentPct / 20;

      particles.forEach((p) => {
        p.x += p.vx * speedMult;
        if (p.x > w) {
          p.x = 0;
          p.y = Math.random() * h;
        }
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.globalAlpha = p.alpha;
        ctx.fill();
      });

      ctx.globalAlpha = 1;
      if (isRunning) {
        animFrameId = requestAnimationFrame(loop);
      }
    }

    if (animFrameId) cancelAnimationFrame(animFrameId);
    animFrameId = requestAnimationFrame(loop);
  }

  // Buttons
  if (btnStop) {
    btnStop.addEventListener("click", async () => {
      btnStop.disabled = true;
      btnStop.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Arrêt...';
      addConsoleLog("Arrêt d'urgence demandé par l'utilisateur...", "warning");
      try {
        await fetch("/api/jobs/stop-batch", { method: "POST" });
        showToast("Arrêt des candidatures demandé.", "info");
      } catch (err) {
        showToast("Erreur arrêt : " + err.message, "error");
      } finally {
        setTimeout(() => {
          btnStop.disabled = false;
          btnStop.innerHTML = '<i class="fa-solid fa-hand"></i> <span>Arrêter</span>';
        }, 1200);
      }
    });
  }

  if (btnClose) {
    btnClose.addEventListener("click", () => {
      if (hero) hero.style.display = "none";
    });
  }

  if (btnViewApplied) {
    btnViewApplied.addEventListener("click", () => {
      if (typeof window.openZenTable === "function") {
        window.openZenTable("", "applied");
      }
    });
  }

  window.LudiqueProgress = {
    open: function (options = {}) {
      isRunning = true;
      currentPct = 0;
      lastLoggedMsg = "";

      if (hero) {
        hero.style.display = "block";
        setTimeout(() => {
          hero.scrollIntoView({ behavior: "smooth", block: "center" });
        }, 60);
      }

      initCanvas();

      if (consoleFeed) {
        consoleFeed.innerHTML = "";
      }
      addConsoleLog("🚀 Initialisation du propulseur Playwright furtif...", "info");

      if (titleElem) {
        titleElem.innerText = options.title || "Turbo-Postulation en 1 Clic";
      }
      if (subElem) {
        if (options.company) {
          subElem.innerHTML = `Mission en direct vers <strong style="color:#38bdf8;">${escapeHtml(options.company)}</strong> via l'agent IA biométrique.`;
        } else {
          subElem.innerText = "L'agent IA pilote Playwright en navigation biométrique pour postuler sans blocage.";
        }
      }

      // Target platform badge
      if (currPlatform) {
        const pName = (options.platform || "1-Clic").toUpperCase();
        currPlatform.innerText = pName;
      }
      if (currPlatBadge) {
        const p = (options.platform || "").toLowerCase();
        if (p.includes("linkedin")) {
          currPlatBadge.style.color = "#38bdf8";
          currPlatBadge.style.borderColor = "rgba(56, 189, 248, 0.4)";
        } else if (p.includes("france") || p.includes("ft")) {
          currPlatBadge.style.color = "#ef4444";
          currPlatBadge.style.borderColor = "rgba(239, 68, 68, 0.4)";
        } else if (p.includes("indeed")) {
          currPlatBadge.style.color = "#22c55e";
          currPlatBadge.style.borderColor = "rgba(34, 197, 94, 0.4)";
        }
      }

      // Resume name
      if (resumeNameElem) {
        resumeNameElem.innerText = options.resume || activeResumeFilename || "CV Actif";
      }

      if (mascotIcon) {
        mascotIcon.style.display = "none";
        mascotIcon.innerText = "🚀";
      }
      if (victoryRow) victoryRow.style.display = "none";

      // Reset circular SVG gauge & rocket
      if (gaugeStroke) gaugeStroke.style.strokeDashoffset = `${CIRCUMFERENCE}`;
      if (rocketRotator) rocketRotator.style.transform = `rotate(0deg)`;
      if (giantPct) giantPct.innerText = "0%";
      if (gaugeLabel) gaugeLabel.innerText = "PROPULSION";

      if (stepText) stepText.innerText = "Initialisation furtive des propulseurs Playwright...";
      if (xpBadge) xpBadge.innerHTML = '<i class="fa-solid fa-bolt"></i> +50 XP';

      if (countSuccess) countSuccess.innerText = "0";
      if (countRemaining) countRemaining.innerText = options.totalCount || "-";
      if (countSkipped) countSkipped.innerText = "0";

      updateChecklist(0, false);
    },

    setProgress: function (pct, stepMsg, stats = null) {
      currentPct = Math.min(100, Math.max(0, Math.round(pct)));

      if (hero && hero.style.display === "none") {
        hero.style.display = "block";
      }

      // Update Circular Progress Ring (Dashoffset)
      if (gaugeStroke) {
        const offset = CIRCUMFERENCE * (1 - currentPct / 100);
        gaugeStroke.style.strokeDashoffset = `${offset}`;
      }

      // Update Orbiting Rocket Rotator (360 deg)
      if (rocketRotator) {
        const rotDeg = currentPct * 3.6;
        rocketRotator.style.transform = `rotate(${rotDeg}deg)`;
      }

      // Update Giant Percentage
      if (giantPct) giantPct.innerText = `${currentPct}%`;

      // Update Dynamic Gauge Label
      if (gaugeLabel) {
        if (currentPct >= 100) gaugeLabel.innerText = "TERMINÉ !";
        else if (currentPct >= 85) gaugeLabel.innerText = "VALIDATION";
        else if (currentPct >= 60) gaugeLabel.innerText = "RÉPONSES IA";
        else if (currentPct >= 35) gaugeLabel.innerText = "INJECTION CV";
        else if (currentPct >= 15) gaugeLabel.innerText = "ANALYSE RH";
        else gaugeLabel.innerText = "PROPULSION";
      }

      // Update Step Description
      if (stepMsg && stepText) {
        stepText.innerText = stepMsg;
        addConsoleLog(stepMsg, "info");
      }

      // Update Checklist Status
      updateChecklist(currentPct, false);

      // Update XP
      if (xpBadge) {
        const gainedXp = Math.max(50, Math.round(currentPct * 5));
        xpBadge.innerHTML = `<i class="fa-solid fa-bolt"></i> +${gainedXp} XP`;
      }

      // Update Stats & Target if provided
      if (stats) {
        if (countSuccess && stats.success_count !== undefined) {
          countSuccess.innerText = stats.success_count;
        }
        if (countRemaining) {
          if (stats.remaining !== undefined) {
            countRemaining.innerText = stats.remaining;
          } else if (stats.total !== undefined && stats.current_index !== undefined) {
            countRemaining.innerText = Math.max(0, stats.total - stats.current_index);
          }
        }
        if (countSkipped && stats.skipped_count !== undefined) {
          countSkipped.innerText = stats.skipped_count;
        }

        if (stats.title && titleElem) {
          titleElem.innerText = stats.title;
        }
        if (stats.company && subElem) {
          subElem.innerHTML = `Mission en direct vers <strong style="color:#38bdf8;">${escapeHtml(stats.company)}</strong> via l'agent IA biométrique.`;
        }
        if (stats.platform && currPlatform) {
          currPlatform.innerText = stats.platform.toUpperCase();
        }
      }
    },

    complete: function (isSuccess, finalMsg) {
      currentPct = 100;

      if (gaugeStroke) gaugeStroke.style.strokeDashoffset = "0";
      if (rocketRotator) rocketRotator.style.transform = "rotate(360deg)";
      if (giantPct) giantPct.innerText = "100%";
      if (gaugeLabel) gaugeLabel.innerText = isSuccess ? "VICTOIRE !" : "ARRÊT";
      if (mascotIcon) {
        mascotIcon.innerText = isSuccess ? "🎉" : "⚠️";
        mascotIcon.style.display = "block";
      }

      const msg = finalMsg || (isSuccess ? "Session terminée avec succès !" : "Session interrompue");
      if (stepText) stepText.innerText = msg;
      addConsoleLog(msg, isSuccess ? "success" : "warning");

      updateChecklist(100, isSuccess);

      if (isSuccess && victoryRow) {
        victoryRow.style.display = "flex";
        if (victoryMsg && finalMsg) victoryMsg.innerText = finalMsg;
      }

      if (xpBadge) {
        xpBadge.innerHTML = '<i class="fa-solid fa-trophy"></i> +500 XP MAX';
      }

      if (typeof loadJobs === "function") loadJobs();
      if (typeof updateBatchCounts === "function") updateBatchCounts();
    },

    close: function () {
      isRunning = false;
      if (animFrameId) cancelAnimationFrame(animFrameId);
      if (hero) hero.style.display = "none";
    },
  };

  // Backward-compatible hook alias for existing calls
  window.ParticleProgress3D = window.LudiqueProgress;
}

function init3DMotionBanner() {
  initLudiqueProgress();
}

/* ==========================================================
   TOAST NOTIFICATIONS
========================================================== */
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = "toast";

  let icon = 'ℹ️';
  if (type === "success") icon = '✅';
  if (type === "error") icon = '⚠️';

  toast.innerHTML = `<span style="font-size:15px;">${icon}</span> <span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

/* ==========================================================
   TABS NAVIGATION
========================================================== */
function setupTabs() {
  const viewButtons = document.querySelectorAll(".view-tab-btn[data-tab]");
  viewButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      const tabId = btn.getAttribute("data-tab");
      switchViewTab(tabId);
    });
  });

  // Steady Invoicing Brand Home Button
  const btnBrandHome = document.getElementById("btn-brand-home");
  if (btnBrandHome) {
    btnBrandHome.addEventListener("click", () => {
      if (typeof window.closeSecondarySheet === "function") window.closeSecondarySheet();
      window.scrollTo({ top: 0, behavior: "smooth" });
      document.querySelectorAll(".steady-nav-btn").forEach(b => b.classList.remove("active"));
      const btnDash = document.getElementById("btn-nav-dashboard");
      if (btnDash) btnDash.classList.add("active");
    });
  }

  // Steady Invoicing Top Nav Buttons
  document.querySelectorAll(".steady-nav-btn[data-steady-view]").forEach(btn => {
    btn.addEventListener("click", () => {
      const view = btn.getAttribute("data-steady-view");
      document.querySelectorAll(".steady-nav-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      if (view === "dashboard") {
        if (typeof window.closeSecondarySheet === "function") window.closeSecondarySheet();
        const workbench = document.getElementById("steady-workbench");
        if (workbench) workbench.scrollIntoView({ behavior: "smooth" });
      } else if (view === "cv") {
        if (typeof window.openSecondarySheet === "function") window.openSecondarySheet("tab-cv");
      } else if (view === "platforms") {
        if (typeof window.openSecondarySheet === "function") window.openSecondarySheet("tab-platforms");
      } else if (view === "criteria") {
        if (typeof window.openSecondarySheet === "function") window.openSecondarySheet("tab-settings");
      }
    });
  });

  // Header direct scan trigger
  const btnHeaderScan = document.getElementById("btn-header-scan");
  if (btnHeaderScan) {
    btnHeaderScan.addEventListener("click", () => {
      const btnScan = document.getElementById("btn-scan-now");
      if (btnScan) btnScan.click();
    });
  }

  const btnGotoViewer = document.getElementById("btn-goto-viewer");
  if (btnGotoViewer) {
    btnGotoViewer.addEventListener("click", () => switchViewTab("tab-cv"));
  }

  const btnModalGoto = document.getElementById("btn-modal-goto-viewer");
  if (btnModalGoto) {
    btnModalGoto.addEventListener("click", () => {
      closeQuickSwitchModal();
      switchViewTab("tab-cv");
    });
  }

  const btnEditProfileJump = document.getElementById("btn-edit-profile-jump");
  if (btnEditProfileJump) {
    btnEditProfileJump.addEventListener("click", () => switchViewTab("tab-settings"));
  }
}

function switchViewTab(tabId) {
  if (tabId === "tab-table") {
    if (typeof window.openCandidaturesSheet === "function") {
      window.openCandidaturesSheet("");
    }
    return;
  }
  if (tabId === "tab-cv" || tabId === "tab-platforms" || tabId === "tab-settings") {
    if (typeof window.openSecondarySheet === "function") {
      window.openSecondarySheet(tabId);
    }
    return;
  }

  document.querySelectorAll(".view-tab-btn").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".notion-view-page").forEach(p => p.classList.remove("active"));

  const activeBtn = document.querySelector(`.view-tab-btn[data-tab='${tabId}']`);
  const activePage = document.getElementById(tabId);

  if (activeBtn) activeBtn.classList.add("active");
  if (activePage) activePage.classList.add("active");
}

/* ==========================================================
   RESUME MANAGER & VIEWER
========================================================== */
function setupResumeManager() {
  const topbarPill = document.getElementById("header-cv-pill");
  const triggerBtn = document.getElementById("btn-quick-switch-trigger");
  const modal = document.getElementById("quick-switch-modal");
  const btnClose = document.getElementById("btn-close-modal");

  if (topbarPill) topbarPill.addEventListener("click", openQuickSwitchModal);
  const drawerPill = document.getElementById("drawer-cv-pill");
  if (drawerPill) drawerPill.addEventListener("click", openQuickSwitchModal);
  if (triggerBtn) triggerBtn.addEventListener("click", openQuickSwitchModal);
  if (btnClose) btnClose.addEventListener("click", closeQuickSwitchModal);

  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeQuickSwitchModal();
    });
  }

  // Dropzone
  const dropzone = document.getElementById("cv-dropzone");
  const fileInput = document.getElementById("cv-file-input");

  if (dropzone && fileInput) {
    dropzone.addEventListener("click", () => fileInput.click());

    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });

    dropzone.addEventListener("dragleave", () => {
      dropzone.classList.remove("dragover");
    });

    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleUploadFile(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleUploadFile(e.target.files[0]);
      }
    });
  }

  const btnModalUpload = document.getElementById("btn-modal-upload");
  if (btnModalUpload && fileInput) {
    btnModalUpload.addEventListener("click", () => {
      closeQuickSwitchModal();
      switchViewTab("tab-cv");
      fileInput.click();
    });
  }

  const btnSetViewedActive = document.getElementById("btn-set-viewed-active");
  if (btnSetViewedActive) {
    btnSetViewedActive.addEventListener("click", async () => {
      if (!viewedResumeFilename) return;
      await setActiveResume(viewedResumeFilename);
    });
  }
}

async function loadResumes() {
  try {
    const res = await fetch("/api/resumes");
    const data = await res.json();

    allResumes = data.resumes || [];
    activeResumeFilename = data.active_filename || "";
    userProfile = data.profile || {};

    if (!viewedResumeFilename && activeResumeFilename) {
      viewedResumeFilename = activeResumeFilename;
    } else if (!viewedResumeFilename && allResumes.length > 0) {
      viewedResumeFilename = allResumes[0].filename;
    }

    renderResumeElements();
  } catch (e) {
    console.error("Error loading resumes:", e);
  }
}

function renderResumeElements() {
  const topbarName = document.getElementById("topbar-active-cv-name");
  const reminderName = document.getElementById("reminder-cv-name");
  const viewerActiveName = document.getElementById("viewer-active-filename");
  const countBadge = document.getElementById("resumes-count-badge");
  const peekActiveCV = document.getElementById("peek-active-cv-name");
  const settingsActiveCV = document.getElementById("settings-active-cv-label");

  const displayName = activeResumeFilename || "Aucun CV actif";
  if (topbarName) topbarName.innerText = displayName;
  const drawerName = document.getElementById("drawer-active-cv-name");
  if (drawerName) drawerName.innerText = displayName;
  if (reminderName) reminderName.innerText = displayName;
  if (viewerActiveName) viewerActiveName.innerText = displayName;
  if (countBadge) countBadge.innerText = allResumes.length;
  if (peekActiveCV) peekActiveCV.innerText = displayName;
  if (settingsActiveCV) settingsActiveCV.innerText = displayName;

  const listContainer = document.getElementById("resumes-list-container");
  if (listContainer) {
    if (allResumes.length === 0) {
      listContainer.innerHTML = `
        <div style="text-align:center; padding: 14px; color: var(--text-muted); font-size: 12px;">
          Aucun document. Glissez un PDF ci-dessus.
        </div>
      `;
    } else {
      listContainer.innerHTML = allResumes.map(r => {
        const isActive = (r.filename === activeResumeFilename);
        const isViewed = (r.filename === viewedResumeFilename);
        return `
          <div class="cv-list-entry ${isActive ? 'is-active' : ''} ${isViewed ? 'is-viewed' : ''}">
            <div style="display:flex; align-items:center; gap:8px; min-width:0; flex:1; cursor:pointer;" onclick="viewResume('${r.filename}')">
              <i class="fa-regular fa-file-pdf" style="color:#ef4444; font-size:14px;"></i>
              <div style="min-width:0;">
                <div style="font-size:12.5px; font-weight:500; color:#fff; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${r.filename}">
                  ${r.filename}
                </div>
                <div style="font-size:11px; color:var(--text-muted); display:flex; align-items:center; gap:6px;">
                  <span>${r.size_kb} Ko</span>
                  ${isActive ? '<span style="color:#34d399; font-weight:600;">• Actif</span>' : ''}
                </div>
              </div>
            </div>
            <div style="display:flex; align-items:center; gap:4px;">
              ${!isActive ? `
                <button class="btn-xs-link" title="Définir comme CV actif" onclick="setActiveResume('${r.filename}')">
                  Activer
                </button>
              ` : `
                <span style="color:#34d399; font-size:13px; padding:0 4px;"><i class="fa-solid fa-circle-check"></i></span>
              `}
              <button class="table-icon-link" title="Supprimer ce CV" onclick="deleteResume('${r.filename}')">
                <i class="fa-solid fa-trash-can"></i>
              </button>
            </div>
          </div>
        `;
      }).join("");
    }
  }

  renderDocumentViewer();
  renderModalList();
  renderProfileProperties();
}

function renderDocumentViewer() {
  const titleElem = document.getElementById("viewer-display-title");
  const activeBadge = document.getElementById("viewer-is-active-badge");
  const btnSetActive = document.getElementById("btn-set-viewed-active");
  const downloadLink = document.getElementById("btn-download-pdf");
  const fullscreenLink = document.getElementById("btn-fullscreen-pdf");
  const frame = document.getElementById("pdf-viewer-frame");
  const placeholder = document.getElementById("viewer-empty-state");

  if (!viewedResumeFilename) {
    if (titleElem) titleElem.innerText = "Aucun document sélectionné";
    if (activeBadge) activeBadge.style.display = "none";
    if (btnSetActive) btnSetActive.style.display = "none";
    if (frame) frame.style.display = "none";
    if (placeholder) placeholder.style.display = "flex";
    return;
  }

  if (titleElem) titleElem.innerText = viewedResumeFilename;

  const isActive = (viewedResumeFilename === activeResumeFilename);
  if (activeBadge) activeBadge.style.display = isActive ? "inline-flex" : "none";
  if (btnSetActive) btnSetActive.style.display = isActive ? "none" : "inline-flex";

  const previewUrl = `/api/resumes/preview/${encodeURIComponent(viewedResumeFilename)}`;
  const downloadUrl = `/api/resumes/download/${encodeURIComponent(viewedResumeFilename)}`;

  if (downloadLink) downloadLink.href = downloadUrl;
  if (fullscreenLink) fullscreenLink.href = previewUrl;

  if (frame) {
    frame.style.display = "block";
    if (frame.src !== window.location.origin + previewUrl) {
      frame.src = previewUrl;
    }
  }
  if (placeholder) placeholder.style.display = "none";
}

function renderProfileProperties() {
  const container = document.getElementById("profile-summary-content");
  if (!container || !userProfile) return;

  const skillsList = (userProfile.skills || []).slice(0, 5).join(", ");

  container.innerHTML = `
    <div class="prop-row-clean">
      <span class="prop-name-clean">Candidat</span>
      <span class="prop-val-clean">${userProfile.first_name || ""} ${userProfile.last_name || ""}</span>
    </div>
    <div class="prop-row-clean">
      <span class="prop-name-clean">Poste visé</span>
      <span class="prop-val-clean">${userProfile.current_title || "Développeur Full Stack"}</span>
    </div>
    <div class="prop-row-clean">
      <span class="prop-name-clean">Email</span>
      <span class="prop-val-clean">${userProfile.email || "-"}</span>
    </div>
    <div class="prop-row-clean">
      <span class="prop-name-clean">Téléphone</span>
      <span class="prop-val-clean">${userProfile.phone_number ? '+33 ' + userProfile.phone_number : "01 88 33 97 16"}</span>
    </div>
    <div class="prop-row-clean">
      <span class="prop-name-clean">Compétences</span>
      <span class="prop-val-clean">${skillsList}</span>
    </div>
    <div class="prop-row-clean">
      <span class="prop-name-clean">Prétentions</span>
      <span class="prop-val-clean">${userProfile.salary_expectation_annual_eur ? userProfile.salary_expectation_annual_eur + ' €/an' : "50 000 €/an"}</span>
    </div>
  `;
}

function viewResume(filename) {
  viewedResumeFilename = filename;
  renderResumeElements();
}

async function setActiveResume(filename) {
  try {
    const res = await fetch("/api/resumes/set-active", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename }),
    });

    if (!res.ok) throw new Error("Erreur de mise à jour");

    activeResumeFilename = filename;
    viewedResumeFilename = filename;
    showToast(`CV Actif mis à jour : ${filename}`, "success");
    closeQuickSwitchModal();
    await loadResumes();
  } catch (e) {
    showToast("Erreur : " + e.message, "error");
  }
}

async function deleteResume(filename) {
  if (!confirm(`Supprimer définitivement le CV "${filename}" ?`)) return;

  try {
    const res = await fetch(`/api/resumes/${encodeURIComponent(filename)}`, {
      method: "DELETE",
    });
    if (!res.ok) throw new Error("Erreur de suppression");

    showToast(`CV "${filename}" supprimé`, "info");
    if (viewedResumeFilename === filename) viewedResumeFilename = "";
    await loadResumes();
  } catch (e) {
    showToast("Erreur : " + e.message, "error");
  }
}

async function handleUploadFile(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    showToast("Veuillez sélectionner un fichier PDF (.pdf)", "error");
    return;
  }

  const setActive = document.getElementById("upload-set-active")?.checked ?? true;
  const formData = new FormData();
  formData.append("file", file);

  showToast(`Importation de "${file.name}"...`);

  try {
    const res = await fetch(`/api/resumes/upload?set_active=${setActive}`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) throw new Error("Échec de l'import");

    const data = await res.json();
    showToast(data.message || "CV importé avec succès !", "success");
    viewedResumeFilename = data.filename;
    await loadResumes();
  } catch (e) {
    showToast("Erreur : " + e.message, "error");
  }
}

function openQuickSwitchModal() {
  const modal = document.getElementById("quick-switch-modal");
  if (modal) {
    renderModalList();
    modal.style.display = "flex";
  }
}

function closeQuickSwitchModal() {
  const modal = document.getElementById("quick-switch-modal");
  if (modal) modal.style.display = "none";
}

function renderModalList() {
  const container = document.getElementById("modal-resumes-list");
  if (!container) return;

  if (allResumes.length === 0) {
    container.innerHTML = `
      <div style="text-align:center; padding: 18px; color: var(--text-muted);">
        Aucun document disponible.
      </div>
    `;
    return;
  }

  container.innerHTML = allResumes.map(r => {
    const isActive = (r.filename === activeResumeFilename);
    return `
      <div class="modal-cv-entry ${isActive ? 'is-active' : ''}" onclick="setActiveResume('${r.filename}')">
        <div style="display:flex; align-items:center; gap:10px;">
          <i class="fa-regular fa-file-pdf" style="color:#ef4444; font-size:16px;"></i>
          <div>
            <div style="font-weight:600; font-size:13px; color:#fff;">${r.filename}</div>
            <div style="font-size:11px; color:var(--text-muted);">
              ${r.size_kb} Ko ${isActive ? '• <span style="color:#34d399; font-weight:600;">Actif pour postuler</span>' : ''}
            </div>
          </div>
        </div>
        <div>
          ${isActive ? `
            <span style="color:#34d399; font-size:16px;"><i class="fa-solid fa-circle-check"></i></span>
          ` : `
            <button class="btn-xs-link">Choisir</button>
          `}
        </div>
      </div>
    `;
  }).join("");
}

/* ==========================================================
   SIDE-PEEK DRAWER (1-CLICK APPLY IN DETAIL)
========================================================== */
function setupSidePeek() {
  const sidePeek = document.getElementById("notion-side-peek");
  const btnClose = document.getElementById("btn-close-side-peek");
  const btnApplyNow = document.getElementById("btn-peek-apply-now");
  const btnChangeCv = document.getElementById("btn-peek-change-cv");

  if (btnClose) {
    btnClose.addEventListener("click", () => {
      if (sidePeek) sidePeek.style.display = "none";
    });
  }

  if (btnChangeCv) {
    btnChangeCv.addEventListener("click", openQuickSwitchModal);
  }

  if (btnApplyNow) {
    btnApplyNow.addEventListener("click", async () => {
      if (!currentPeekJob) return;
      await handleApply(currentPeekJob.id, btnApplyNow);
      // update sidepeek status
      const peekStatus = document.getElementById("peek-status-pill");
      if (peekStatus) {
        peekStatus.className = "notion-status-pill applied";
        peekStatus.innerHTML = `<span class="status-dot"></span> Postulé`;
      }
    });
  }
}

function openSidePeek(job) {
  currentPeekJob = job;
  const sidePeek = document.getElementById("notion-side-peek");
  if (!sidePeek) return;

  const titleElem = document.getElementById("peek-job-title");
  const compElem = document.getElementById("peek-company");
  const locElem = document.getElementById("peek-location");
  const platElem = document.getElementById("peek-platform");
  const scoreElem = document.getElementById("peek-score");
  const reasonElem = document.getElementById("peek-match-reason");
  const linkElem = document.getElementById("peek-external-link");
  const cvElem = document.getElementById("peek-active-cv-name");
  const statusElem = document.getElementById("peek-status-pill");
  const btnApply = document.getElementById("btn-peek-apply-now");
  const auditBox = document.getElementById("peek-audit-box");
  const auditTitle = document.getElementById("peek-audit-title");
  const auditDetail = document.getElementById("peek-audit-detail");

  if (titleElem) titleElem.innerText = job.job_title;
  if (compElem) compElem.innerText = job.company;
  if (locElem) locElem.innerText = job.location || "Paris";
  if (platElem) platElem.innerText = (job.platform || "").toUpperCase();
  if (scoreElem) scoreElem.innerText = `${job.match_score || 75}%`;
  if (reasonElem) reasonElem.innerText = job.match_reason || "Adéquation confirmée avec votre profil candidat.";
  if (linkElem) linkElem.href = job.job_url;
  const postedElem = document.getElementById("peek-posted-time");
  if (postedElem) {
    const rel = job.posted_relative || (job.created_at ? formatRelativeTime(job.created_at) : "Récent");
    postedElem.innerText = rel;
  }

  // Status Pill
  if (statusElem) {
    if (job.status === "applied") {
      statusElem.className = "notion-status-pill applied";
      statusElem.innerHTML = `<span class="status-dot"></span> Postulé`;
    } else if (job.status === "applying") {
      statusElem.className = "notion-status-pill contacted";
      statusElem.innerHTML = `<span class="status-dot"></span> En cours...`;
    } else if (job.status === "skipped") {
      statusElem.className = "notion-status-pill skipped";
      statusElem.innerHTML = `<span class="status-dot"></span> Redirection`;
    } else if (job.status === "failed") {
      statusElem.className = "notion-status-pill failed";
      statusElem.innerHTML = `<span class="status-dot"></span> Échec d'envoi`;
    } else if (job.status === "requires_review") {
      statusElem.className = "notion-status-pill requires-review";
      statusElem.innerHTML = `<span class="status-dot"></span> À vérifier`;
    } else {
      statusElem.className = "notion-status-pill to-contact";
      statusElem.innerHTML = `<span class="status-dot"></span> À contacter`;
    }
  }

  // Preuve & Audit Box
  if (auditBox && auditDetail) {
    auditBox.style.display = "block";
    if (job.status === "applied") {
      auditBox.className = "peek-audit-box success";
      auditTitle.innerHTML = `<i class="fa-solid fa-circle-check"></i> Candidature transmise avec succès`;
      const dt = job.applied_at ? new Date(job.applied_at).toLocaleString('fr-FR') : "Confirmée";
      auditDetail.innerHTML = `Votre dossier a été validé et envoyé à <strong>${escapeHtml(job.company)}</strong> via ${job.platform}.<br><span style="opacity:0.8; font-size:11.5px;">Horodatage : ${dt}</span>`;
    } else if (job.status === "skipped") {
      auditBox.className = "peek-audit-box warning";
      auditTitle.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Candidature externe requise (Non 1-Clic direct)`;
      auditDetail.innerHTML = `Cette offre ne supporte pas l'envoi automatique direct (<em>${escapeHtml(job.error_message || 'Redirection vers portail employeur')}</em>). Cliquez sur "Postuler sur le site externe" ci-dessous pour remplir leur formulaire officiel.`;
    } else if (job.status === "failed") {
      auditBox.className = "peek-audit-box error";
      auditTitle.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> Échec lors de la transmission Playwright`;
      auditDetail.innerHTML = `Raison : <strong>${escapeHtml(job.error_message || 'Erreur inconnue')}</strong>.<br><span style="opacity:0.85; font-size:11.5px;">Astuce : Vérifiez votre connexion sur <em>${job.platform}</em> dans l'onglet <strong>🔑 Connexions Plateformes</strong>.</span>`;
    } else if (job.status === "applying") {
      auditBox.className = "peek-audit-box info";
      auditTitle.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Traitement Playwright en arrière-plan...`;
      auditDetail.innerHTML = `Le robot invisible navigue et remplit la candidature en tâche de fond.`;
    } else {
      auditBox.style.display = "none";
    }
  }

  // Action Button
  if (btnApply) {
    if (job.status === "applied") {
      btnApply.innerHTML = '<i class="fa-solid fa-check"></i> Déjà postulé avec succès';
      btnApply.style.background = "rgba(16, 185, 129, 0.35)";
      btnApply.style.color = "#34d399";
      btnApply.disabled = true;
    } else if (job.status === "applying") {
      btnApply.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> En cours de traitement...';
      btnApply.style.background = "rgba(59, 130, 246, 0.25)";
      btnApply.style.color = "#93c5fd";
      btnApply.disabled = true;
    } else if (job.status === "skipped") {
      btnApply.innerHTML = '<i class="fa-solid fa-arrow-up-right-from-square"></i> Postuler sur le site externe';
      btnApply.style.background = "#334155";
      btnApply.style.color = "#f8fafc";
      btnApply.disabled = false;
      btnApply.onclick = () => window.open(job.job_url, '_blank');
    } else if (job.status === "failed") {
      btnApply.innerHTML = '<i class="fa-solid fa-rotate-right"></i> Réessayer en 1 Clic';
      btnApply.style.background = "#ef4444";
      btnApply.style.color = "#ffffff";
      btnApply.disabled = false;
      btnApply.onclick = async () => { await handleApply(job.id, btnApply); };
    } else {
      btnApply.innerHTML = '<i class="fa-solid fa-bolt"></i> POSTULER EN 1 CLIC MAINTENANT';
      btnApply.style.background = "#10b981";
      btnApply.style.color = "#ffffff";
      btnApply.disabled = false;
      btnApply.onclick = async () => { await handleApply(job.id, btnApply); };
    }
  }

  sidePeek.style.display = "flex";
}

/* ==========================================================
   BATCH 1-CLICK APPLY
========================================================== */
function setupBatchApply() {
  const btnHeaderBatch = document.getElementById("btn-header-batch-apply");
  const btnStripBatch = document.getElementById("btn-strip-apply-all");

  const runBatch = async () => {
    const unappliedJobs = allJobs.filter(j => j.status !== "applied" && j.status !== "skipped");
    if (unappliedJobs.length === 0) {
      showToast("Toutes les offres affichées ont déjà été postulées !", "info");
      return;
    }

    const jobIds = unappliedJobs.slice(0, 10).map(j => j.id);
    const resumeName = activeResumeFilename || "votre CV actif";

    if (!confirm(`⚡ Lancer la postulation automatique (mode humain indétectable) pour ${jobIds.length} offre(s) avec ${resumeName} ?`)) {
      return;
    }

    showToast(`⚡ Postulation automatique (mode humain indétectable) lancée pour ${jobIds.length} offre(s)...`, "info");

    if (window.ParticleProgress3D) {
      window.ParticleProgress3D.open({
        title: "Candidatures Groupées 1 Clic",
        company: `${jobIds.length} opportunités ciblées`,
        platform: "Multi",
        mode: "batch"
      });
    }

    try {
      const res = await fetch("/api/jobs/apply-batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_ids: jobIds })
      });
      const data = await res.json();
      showToast(data.message || "Candidatures en cours de traitement !", "success");

      // Mark rows visually
      jobIds.forEach(id => {
        const row = document.getElementById(`job-row-${id}`);
        if (row) {
          const cell = row.cells[3];
          if (cell) {
            cell.innerHTML = `
              <span class="notion-status-pill contacted">
                <span class="status-dot"></span> En cours...
              </span>
            `;
          }
        }
      });

      setTimeout(() => {
        loadJobs();
      }, 4000);
    } catch (e) {
      showToast("Erreur : " + e.message, "error");
    }
  };

  if (btnHeaderBatch) {
    btnHeaderBatch.addEventListener("click", () => {
      if (typeof window.openBatchApplyModal === "function") {
        window.openBatchApplyModal(selectedPlatform || "");
      } else {
        runBatch();
      }
    });
  }
  if (btnStripBatch) {
    btnStripBatch.addEventListener("click", () => {
      if (typeof window.openBatchApplyModal === "function") {
        window.openBatchApplyModal(selectedPlatform || "");
      } else {
        runBatch();
      }
    });
  }
}

function updateBatchCounts() {
  const unappliedTotal = allJobs.filter(j => j.status !== "applied" && j.status !== "skipped").length;
  const appliedTotal = allJobs.filter(j => j.status === "applied").length;

  // By platform unapplied counts
  const ftUnapplied = allJobs.filter(j => (j.platform || "").toLowerCase() === "francetravail" && j.status !== "applied" && j.status !== "skipped").length;
  const liUnapplied = allJobs.filter(j => (j.platform || "").toLowerCase() === "linkedin" && j.status !== "applied" && j.status !== "skipped").length;
  const indUnapplied = allJobs.filter(j => (j.platform || "").toLowerCase() === "indeed" && j.status !== "applied" && j.status !== "skipped").length;

  const headerCount = document.getElementById("header-batch-count");
  const stripCount = document.getElementById("strip-batch-count");
  const drawerCount = document.getElementById("drawer-count-all-unapplied");
  const footCount = document.getElementById("arova-foot-unapplied-count");
  const footBtn = document.getElementById("btn-arova-foot-apply-all");
  const dockAppliedCount = document.getElementById("dock-count-applied");
  const drawerAppliedCount = document.getElementById("drawer-count-applied-badge");
  const tabCountApplied = document.getElementById("arova-tab-count-applied");

  // Pills inside batch modal
  const pillAll = document.getElementById("batch-pill-count-all");
  const pillFt = document.getElementById("batch-pill-count-ft");
  const pillLi = document.getElementById("batch-pill-count-li");
  const pillInd = document.getElementById("batch-pill-count-ind");

  const workbenchCount = document.getElementById("workbench-count-unapplied");
  if (headerCount) headerCount.innerText = unappliedTotal;
  if (stripCount) stripCount.innerText = unappliedTotal;
  if (drawerCount) drawerCount.innerText = unappliedTotal;
  if (workbenchCount) workbenchCount.innerText = unappliedTotal;
  if (dockAppliedCount) dockAppliedCount.innerText = appliedTotal;
  if (drawerAppliedCount) drawerAppliedCount.innerText = appliedTotal;

  // Steady Invoicing KPI Updates
  const steadyKpiTotal = document.getElementById("steady-kpi-total");
  const steadyKpiApplied = document.getElementById("steady-kpi-applied");
  const steadyKpi1Click = document.getElementById("steady-kpi-1click");
  const count1Click = allJobs.filter(j => j.is_easy_apply !== 0 && j.is_easy_apply !== false).length;

  if (steadyKpiTotal) steadyKpiTotal.innerText = allJobs.length;
  if (steadyKpiApplied) steadyKpiApplied.innerText = appliedTotal;
  if (steadyKpi1Click) steadyKpi1Click.innerText = count1Click;

  // Status Filter Chips (All, Applied, Unapplied, Skipped)
  const countChipAll = document.getElementById("count-chip-all");
  const countChipApplied = document.getElementById("count-chip-applied");
  const countChipUnapplied = document.getElementById("count-chip-unapplied");
  const countChipSkipped = document.getElementById("count-chip-skipped");
  const skippedTotal = allJobs.filter(j => j.status === "skipped").length;

  if (countChipAll) countChipAll.innerText = allJobs.length;
  if (countChipApplied) countChipApplied.innerText = appliedTotal;
  if (countChipUnapplied) countChipUnapplied.innerText = unappliedTotal;
  if (countChipSkipped) countChipSkipped.innerText = skippedTotal;

  if (pillAll) pillAll.innerText = unappliedTotal;
  if (pillFt) pillFt.innerText = ftUnapplied;
  if (pillLi) pillLi.innerText = liUnapplied;
  if (pillInd) pillInd.innerText = indUnapplied;

  // Zen Platform Hub pill badge counters (Total count per platform)
  const ftTotal = allJobs.filter(j => (j.platform || "").toLowerCase() === "francetravail").length;
  const liTotal = allJobs.filter(j => (j.platform || "").toLowerCase() === "linkedin").length;
  const indTotal = allJobs.filter(j => (j.platform || "").toLowerCase() === "indeed").length;

  const pCountAll = document.getElementById("plat-count-all");
  const pCountFt = document.getElementById("plat-count-ft");
  const pCountLi = document.getElementById("plat-count-li");
  const pCountInd = document.getElementById("plat-count-ind");
  const pCountApplied = document.getElementById("plat-count-applied");

  if (pCountAll) pCountAll.innerText = allJobs.length;
  if (pCountFt) pCountFt.innerText = ftTotal;
  if (pCountLi) pCountLi.innerText = liTotal;
  if (pCountInd) pCountInd.innerText = indTotal;
  if (pCountApplied) pCountApplied.innerText = appliedTotal;

  // For the active platform in the card
  let activeUnapplied = unappliedTotal;
  let activeApplied = appliedTotal;
  if (selectedPlatform) {
    activeUnapplied = allJobs.filter(j => (j.platform || "").toLowerCase() === selectedPlatform.toLowerCase() && j.status !== "applied" && j.status !== "skipped").length;
    activeApplied = allJobs.filter(j => (j.platform || "").toLowerCase() === selectedPlatform.toLowerCase() && j.status === "applied").length;
  }

  if (footCount) footCount.innerText = activeUnapplied;
  if (tabCountApplied) tabCountApplied.innerText = activeApplied;

  // New prominent 1-Click buttons & simplified menu badges
  const mainQuickApplyCount = document.getElementById("main-quick-apply-count");
  const dockQuickApplyCount = document.getElementById("dock-apply-count-badge");
  const menuBadgeJobsCount = document.getElementById("menu-badge-jobs-count");
  if (mainQuickApplyCount) mainQuickApplyCount.innerText = activeUnapplied;
  if (dockQuickApplyCount) dockQuickApplyCount.innerText = unappliedTotal;
  if (menuBadgeJobsCount) menuBadgeJobsCount.innerText = `${allJobs.length} offres`;

  if (footBtn) {
    const meta = getPlatformMeta(selectedPlatform);
    if (selectedPlatform && meta) {
      footBtn.innerHTML = `<i class="fa-solid fa-bolt"></i> Tout postuler sur ${meta.name} (<span id="arova-foot-unapplied-count">${activeUnapplied}</span>)`;
    } else {
      footBtn.innerHTML = `<i class="fa-solid fa-bolt"></i> Tout postuler (<span id="arova-foot-unapplied-count">${unappliedTotal}</span>)`;
    }
  }
}

/* ==========================================================
   DATABASE TABLE (CANDIDATURES AGENCE PARIS)
========================================================== */
function setupFilters() {
  const searchInput = document.getElementById("search-query");
  const clearBtn = document.getElementById("btn-clear-search");

  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      searchQuery = e.target.value.toLowerCase().trim();
      if (clearBtn) clearBtn.style.display = searchQuery ? "block" : "none";
      renderJobsTable();
    });
  }

  if (clearBtn && searchInput) {
    clearBtn.addEventListener("click", () => {
      searchInput.value = "";
      searchQuery = "";
      clearBtn.style.display = "none";
      renderJobsTable();
    });
  }

  // Header 1-Click Apply Toggle Switch
  const headerToggle = document.getElementById("header-toggle-1click");
  const settingsToggle = document.getElementById("settings-toggle-easy-apply");
  if (headerToggle) {
    headerToggle.addEventListener("change", async (e) => {
      const isChecked = e.target.checked;
      option1ClickEnabled = isChecked;
      if (settingsToggle) settingsToggle.checked = isChecked;
      update1ClickUI(isChecked);
      await saveOption1Click(isChecked);
    });
  }

  if (settingsToggle) {
    settingsToggle.addEventListener("change", async (e) => {
      const isChecked = e.target.checked;
      option1ClickEnabled = isChecked;
      if (headerToggle) headerToggle.checked = isChecked;
      update1ClickUI(isChecked);
      await saveOption1Click(isChecked);
    });
  }

  // 1-Click Fast Toggle Button
  const chip1Click = document.getElementById("filter-chip-1click");
  if (chip1Click) {
    chip1Click.addEventListener("click", () => {
      filterOnly1Click = !filterOnly1Click;
      chip1Click.classList.toggle("active", filterOnly1Click);
      renderJobsTable();
      showToast(filterOnly1Click ? "Filtre activé : Offres '1 Clic' uniquement" : "Toutes les offres affichées", "info");
    });
  }

  // Steady Status Segmented Chips (Toutes / Postulées / À postuler / Externes)
  document.querySelectorAll(".steady-status-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const targetStatus = chip.getAttribute("data-status-tab") || "";
      selectedStatus = targetStatus;

      // When selecting 'applied', reset platform constraint so all applied jobs across platforms are shown
      if (selectedStatus === "applied") {
        selectedPlatform = "";
        filterOnly1Click = false;
        if (chip1Click) chip1Click.classList.remove("active");
      }

      document.querySelectorAll(".steady-status-chip").forEach(c => c.classList.remove("active"));
      chip.classList.add("active");

      // Synchronize Zen platform pills
      document.querySelectorAll(".zen-plat-pill").forEach(pill => {
        const isApplied = pill.getAttribute("data-status-filter") === "applied" || pill.id === "btn-plat-applied";
        if (selectedStatus === "applied") {
          pill.classList.toggle("active", isApplied);
        } else if (isApplied) {
          pill.classList.remove("active");
        }
      });

      renderJobsTable();
    });
  });

  // Zen Platform Hub Pills (Toggle Table on click)
  document.querySelectorAll(".zen-plat-pill").forEach(pill => {
    pill.addEventListener("click", (e) => {
      e.stopPropagation();
      const isApplied = pill.getAttribute("data-status-filter") === "applied" || pill.id === "btn-plat-applied";
      const targetPlat = isApplied ? "" : (pill.getAttribute("data-platform") || "");
      const targetStatus = isApplied ? "applied" : "";

      const workbench = document.getElementById("steady-workbench");
      const isTableOpen = workbench && workbench.style.display !== "none";

      // If already open on the exact same platform/status, toggle closed (zen calm mode)
      if (isTableOpen && selectedPlatform === targetPlat && selectedStatus === targetStatus) {
        closeZenTable();
        return;
      }

      openZenTable(targetPlat, targetStatus);
    });
  });

  // Workbench Close Button
  const btnCloseWorkbench = document.getElementById("btn-close-table-workbench");
  if (btnCloseWorkbench) {
    btnCloseWorkbench.addEventListener("click", () => {
      closeZenTable();
    });
  }

  // Make KPI cards interactive to open candidatures directly
  const kpiTotalCard = document.getElementById("steady-kpi-card-total");
  if (kpiTotalCard) {
    kpiTotalCard.style.cursor = "pointer";
    kpiTotalCard.addEventListener("click", () => {
      openZenTable("", "");
    });
  }

  const kpiAppliedCard = document.getElementById("steady-kpi-card-applied");
  if (kpiAppliedCard) {
    kpiAppliedCard.style.cursor = "pointer";
    kpiAppliedCard.addEventListener("click", () => {
      openZenTable("", "applied");
    });
  }

  const kpi1ClickCard = document.getElementById("steady-kpi-card-1click");
  if (kpi1ClickCard) {
    kpi1ClickCard.style.cursor = "pointer";
    kpi1ClickCard.addEventListener("click", () => {
      filterOnly1Click = true;
      if (chip1Click) chip1Click.classList.add("active");
      openZenTable("", "");
    });
  }

  // Card 4: Plateformes Actives -> Open Connexions & Sessions des Plateformes
  const kpiPlatformsCard = document.getElementById("steady-kpi-card-platforms");
  if (kpiPlatformsCard) {
    kpiPlatformsCard.style.cursor = "pointer";
    kpiPlatformsCard.addEventListener("click", () => {
      if (typeof window.openSecondarySheet === "function") {
        window.openSecondarySheet("tab-platforms");
      }
    });
  }

  // KPI platform chip indicators (France Travail, LinkedIn, Indeed) inside Card 4
  document.querySelectorAll(".steady-plat-chip").forEach(chip => {
    chip.style.cursor = "pointer";
    chip.addEventListener("click", (e) => {
      e.stopPropagation();
      if (typeof window.openSecondarySheet === "function") {
        window.openSecondarySheet("tab-platforms");
      }
    });
  });

  // Location Picker Dropdown Logic (Choix et personnalisation du lieu)
  const btnLocationPicker = document.getElementById("btn-location-picker");
  const locationPopover = document.getElementById("location-dropdown-popover");
  const btnCloseLocPopover = document.getElementById("btn-close-location-popover");
  const inputCustomLoc = document.getElementById("input-custom-location");
  const btnApplyCustomLoc = document.getElementById("btn-apply-custom-loc");
  const labelSelectedLoc = document.getElementById("current-selected-location-label");
  const locationPills = document.querySelectorAll(".location-option-pill");

  function closeLocationPopover() {
    if (locationPopover) locationPopover.style.display = "none";
  }

  function openLocationPopover() {
    if (locationPopover) {
      locationPopover.style.display = "flex";
      if (inputCustomLoc) {
        setTimeout(() => inputCustomLoc.focus(), 80);
      }
    }
  }

  if (btnLocationPicker && locationPopover) {
    btnLocationPicker.addEventListener("click", (e) => {
      e.stopPropagation();
      const isVisible = locationPopover.style.display === "flex" || locationPopover.style.display === "block";
      if (isVisible) {
        closeLocationPopover();
      } else {
        openLocationPopover();
      }
    });

    if (btnCloseLocPopover) {
      btnCloseLocPopover.addEventListener("click", (e) => {
        e.stopPropagation();
        closeLocationPopover();
      });
    }

    // Close when clicking outside
    document.addEventListener("click", (e) => {
      const pickerContainer = document.getElementById("location-picker-container");
      if (pickerContainer && !pickerContainer.contains(e.target)) {
        closeLocationPopover();
      }
    });

    // Option pills
    locationPills.forEach(pill => {
      pill.addEventListener("click", (e) => {
        e.stopPropagation();
        locationPills.forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        selectedLoc = pill.getAttribute("data-loc-value") || "";
        const labelText = pill.innerText.trim();
        if (labelSelectedLoc) labelSelectedLoc.innerText = labelText;
        if (inputCustomLoc) inputCustomLoc.value = "";
        localStorage.setItem("user_selected_job_location", selectedLoc);
        localStorage.setItem("user_selected_job_location_label", labelText);
        closeLocationPopover();
        renderJobsTable();
        showToast(`📍 Lieu sélectionné : ${labelText}`, "info");
      });
    });

    // Custom Location apply
    const applyCustomLocation = () => {
      if (!inputCustomLoc) return;
      const customVal = inputCustomLoc.value.trim();
      if (!customVal) {
        // Reset to default
        selectedLoc = "";
        locationPills.forEach(p => p.classList.toggle("active", p.getAttribute("data-loc-value") === ""));
        if (labelSelectedLoc) labelSelectedLoc.innerText = "Tout Paris & IDF";
      } else {
        selectedLoc = customVal.toLowerCase();
        locationPills.forEach(p => p.classList.remove("active"));
        if (labelSelectedLoc) labelSelectedLoc.innerText = `📍 ${customVal}`;
      }
      localStorage.setItem("user_selected_job_location", selectedLoc);
      localStorage.setItem("user_selected_job_location_label", labelSelectedLoc ? labelSelectedLoc.innerText : selectedLoc);
      closeLocationPopover();
      renderJobsTable();
      showToast(`📍 Candidatures filtrées sur : ${customVal || "Toutes"}`, "success");
    };

    if (btnApplyCustomLoc) {
      btnApplyCustomLoc.addEventListener("click", (e) => {
        e.stopPropagation();
        applyCustomLocation();
      });
    }

    if (inputCustomLoc) {
      inputCustomLoc.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          applyCustomLocation();
        } else if (e.key === "Escape") {
          closeLocationPopover();
        }
      });
    }

    // Restore saved location preference
    const savedLoc = localStorage.getItem("user_selected_job_location");
    const savedLabel = localStorage.getItem("user_selected_job_location_label");
    if (savedLoc !== null) {
      selectedLoc = savedLoc;
      if (savedLabel && labelSelectedLoc) {
        labelSelectedLoc.innerText = savedLabel;
      }
      let foundPill = false;
      locationPills.forEach(p => {
        if (p.getAttribute("data-loc-value") === savedLoc) {
          p.classList.add("active");
          foundPill = true;
        } else {
          p.classList.remove("active");
        }
      });
      if (!foundPill && savedLoc && inputCustomLoc) {
        inputCustomLoc.value = savedLoc;
      }
    }
  }

  // Legacy location chips if present
  document.querySelectorAll("[data-loc]").forEach(chip => {
    chip.addEventListener("click", () => {
      document.querySelectorAll("[data-loc]").forEach(p => p.classList.remove("active"));
      chip.classList.add("active");
      selectedLoc = chip.getAttribute("data-loc");
      renderJobsTable();
    });
  });

  // Status chips (Tous, Postulés, Redirection, Échecs) - only for toolbar chips if present
  document.querySelectorAll(".toolbar-status-filter:not(.zen-plat-pill)").forEach(chip => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".toolbar-status-filter").forEach(p => p.classList.remove("active"));
      chip.classList.add("active");
      selectedStatus = chip.getAttribute("data-status-filter") || "";
      renderJobsTable();
    });
  });


  // Refresh
  const btnRefresh = document.getElementById("btn-refresh");
  if (btnRefresh) {
    btnRefresh.addEventListener("click", () => {
      loadJobs();
      loadResumes();
      showToast("Données synchronisées");
    });
  }

  // Scan temps réel multi-plateformes
  const btnScan = document.getElementById("btn-scan-now");
  if (btnScan) {
    btnScan.addEventListener("click", async () => {
      btnScan.disabled = true;
      btnScan.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Scan temps réel...';

      try {
        showToast("⚡ Récupération des offres en direct (France Travail, LinkedIn, Indeed)...", "info");
        const res = await fetch("/api/jobs/sync-realtime", { method: "POST" });
        const data = await res.json();
        await loadJobs();
        showToast(`✓ ${data.new_count || 0} offres en direct synchronisées avec horodatage exact !`, "success");
      } catch (e) {
        showToast("Erreur lors du scan : " + e.message, "error");
      } finally {
        btnScan.disabled = false;
        btnScan.innerHTML = '<i class="fa-solid fa-bolt"></i> Scanner en Direct';
      }
    });
  }

  // Bouton Purger immédiatement les offres fermées / expirées
  const btnClean = document.getElementById("btn-clean-inactive");
  if (btnClean) {
    btnClean.addEventListener("click", async () => {
      btnClean.disabled = true;
      btnClean.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Vérification...';

      try {
        showToast("🧹 Audit en direct : test de validité des annonces sur Indeed, LinkedIn & France Travail...", "info");
        const res = await fetch("/api/jobs/clean-inactive", { method: "POST" });
        const data = await res.json();

        if (data.deleted_count > 0) {
          showToast(`🧹 ${data.deleted_count} offre(s) fermée(s) ou expirée(s) supprimée(s) automatiquement !`, "success");
        } else {
          showToast("✓ Parfait : toutes les offres affichées sont actuellement actives et ouvertes !", "success");
        }
        loadJobs();
      } catch (e) {
        showToast("Erreur lors de la vérification : " + e.message, "error");
      } finally {
        btnClean.disabled = false;
        btnClean.innerHTML = '<i class="fa-solid fa-broom"></i> Purger expirées';
      }
    });
  }
}

function update1ClickUI(enabled) {
  const badge = document.getElementById("header-toggle-badge");
  const stripStatus = document.getElementById("strip-option-status");

  if (badge) {
    badge.className = `toggle-option-badge ${enabled ? "active" : "inactive"}`;
    badge.innerText = enabled ? "ACTIVE" : "DESACTIVE";
  }

  if (stripStatus) {
    stripStatus.className = `badge-emerald ${enabled ? "" : "inactive"}`;
    stripStatus.innerHTML = enabled 
      ? `<i class="fa-solid fa-check"></i> ACTIVÉE` 
      : `<i class="fa-solid fa-power-off"></i> DÉSACTIVÉE`;
  }
}

async function saveOption1Click(enabled) {
  try {
    const res = await fetch("/api/config/toggle-easy-apply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled })
    });
    const data = await res.json();
    showToast(data.message || `Option 1 Clic ${enabled ? 'activée' : 'désactivée'}`, "success");
  } catch (e) {
    showToast("Erreur d'enregistrement : " + e.message, "error");
  }
}

async function loadJobs(showLoading = true) {
  try {
    const sortParam = (typeof arovaSortMode !== "undefined") ? arovaSortMode : "relevance";
    const res = await fetch(`/api/applications?limit=1000&sort_by=${sortParam}`);
    allJobs = await res.json();
    renderJobsTable();
    updateBatchCounts();
    if (typeof renderArovaCardRows === "function") {
      renderArovaCardRows();
    }
  } catch (e) {
    console.error("Error loading jobs:", e);
  }
}

function renderJobsTable() {
  const tbody = document.getElementById("notion-table-body");
  const countText = document.getElementById("jobs-count-text");
  const tabCount = document.getElementById("tab-jobs-count");
  const badge1ClickCount = document.getElementById("count-1click-jobs");

  if (!tbody) return;

  // Total 1-Click compatible jobs count & total count
  const count1Click = allJobs.filter(j => j.is_easy_apply !== 0 && j.is_easy_apply !== false).length;
  if (badge1ClickCount) badge1ClickCount.innerText = count1Click;
  const badgeTotalJobs = document.getElementById("count-total-jobs-badge");
  if (badgeTotalJobs) badgeTotalJobs.innerText = allJobs.length;

  // Steady Invoicing KPI Cards Updates
  const steadyKpiTotal = document.getElementById("steady-kpi-total");
  const steadyKpiApplied = document.getElementById("steady-kpi-applied");
  const steadyKpi1Click = document.getElementById("steady-kpi-1click");
  const countApplied = allJobs.filter(j => j.status === "applied").length;

  if (steadyKpiTotal) steadyKpiTotal.innerText = allJobs.length;
  if (steadyKpiApplied) steadyKpiApplied.innerText = countApplied;
  if (steadyKpi1Click) steadyKpi1Click.innerText = count1Click;

  // Dynamic counts on Dock CTAs and Top Brand
  const countAll = allJobs.length;
  const elDockAll = document.getElementById("dock-count-all");
  if (elDockAll) elDockAll.innerText = countAll;

  // Update counts on all dock CTA buttons dynamically
  document.querySelectorAll(".arova-cta-btn[data-dock-platform]").forEach(btn => {
    const platId = btn.getAttribute("data-dock-platform");
    const badge = btn.querySelector(".arova-cta-badge");
    if (!badge) return;
    if (!platId) {
      badge.innerText = allJobs.length;
    } else {
      const c = allJobs.filter(j => (j.platform || "").toLowerCase() === platId.toLowerCase()).length;
      badge.innerText = c;
    }
  });

  const elTopBadge = document.getElementById("arova-top-jobs-badge");
  if (elTopBadge) elTopBadge.innerText = `${countAll} offres`;

  if (typeof renderArovaCardRows === "function") {
    renderArovaCardRows();
  }

  const filtered = allJobs.filter(job => {
    // When inspecting applied candidatures, show all applied jobs without strict 1-click or location restrictions
    if (selectedStatus === "applied") {
      if (job.status !== "applied") return false;
      if (selectedPlatform && (job.platform || "").toLowerCase() !== selectedPlatform.toLowerCase()) return false;
      if (searchQuery) {
        const matchText = `${job.job_title} ${job.company} ${job.location || ""} ${job.match_reason || ""}`.toLowerCase();
        if (!matchText.includes(searchQuery)) return false;
      }
      return true;
    }

    if (selectedStatus === "unapplied") {
      if (job.status === "applied" || job.status === "skipped") return false;
    } else if (selectedStatus === "skipped") {
      if (job.status !== "skipped") return false;
    }

    // 1-Click only filter
    if (filterOnly1Click && (job.is_easy_apply === 0 || job.is_easy_apply === false)) {
      return false;
    }

    if (selectedPlatform && (job.platform || "").toLowerCase() !== selectedPlatform.toLowerCase()) {
      return false;
    }

    const loc = (job.location || "").toLowerCase();
    if (selectedLoc) {
      const locTarget = selectedLoc.toLowerCase().trim();
      if (locTarget === "intra") {
        if (!loc.includes("75") && !loc.includes("paris")) return false;
      } else if (locTarget === "idf") {
        const idfKeywords = ["paris", "75", "île-de-france", "ile-de-france", "idf", "92", "93", "94", "78", "91", "95", "77"];
        if (!idfKeywords.some(k => loc.includes(k))) return false;
      } else if (locTarget === "remote") {
        const remoteKeywords = ["remote", "télétravail", "teletravail", "hybride", "france entière", "full remote"];
        if (!remoteKeywords.some(k => loc.includes(k))) return false;
      } else if (locTarget === "france") {
        // France entière : match all
      } else {
        // Custom location string (e.g. Lyon, Bordeaux, 75001, Nantes...)
        if (!loc.includes(locTarget)) return false;
      }
    }

    if (searchQuery) {
      const matchText = `${job.job_title} ${job.company} ${job.location || ""} ${job.match_reason || ""}`.toLowerCase();
      if (!matchText.includes(searchQuery)) return false;
    }

    return true;
  });

  // Synchronize status segmented chips active state
  document.querySelectorAll(".steady-status-chip").forEach(chip => {
    const tabStatus = chip.getAttribute("data-status-tab") || "";
    chip.classList.toggle("active", tabStatus === selectedStatus);
  });

  const activeTitle = document.getElementById("workbench-active-title");
  if (activeTitle) {
    if (selectedStatus === "applied") {
      activeTitle.innerHTML = `<i class="fa-solid fa-circle-check" style="color:#10b981;margin-right:8px;"></i> Candidatures postulées avec succès (${filtered.length})`;
    } else if (selectedStatus === "unapplied") {
      activeTitle.innerHTML = `<i class="fa-solid fa-paper-plane" style="color:#6366f1;margin-right:8px;"></i> Opportunités à postuler (${filtered.length})`;
    } else if (selectedStatus === "skipped") {
      activeTitle.innerHTML = `<i class="fa-solid fa-arrow-up-right-from-square" style="color:#f59e0b;margin-right:8px;"></i> Redirections externes (${filtered.length})`;
    } else if (selectedPlatform === "francetravail") {
      activeTitle.innerHTML = `<span class="steady-dot ft" style="display:inline-block;margin-right:8px;"></span> France Travail (${filtered.length})`;
    } else if (selectedPlatform === "linkedin") {
      activeTitle.innerHTML = `<span class="steady-dot li" style="display:inline-block;margin-right:8px;"></span> LinkedIn (${filtered.length})`;
    } else if (selectedPlatform === "indeed") {
      activeTitle.innerHTML = `<span class="steady-dot ind" style="display:inline-block;margin-right:8px;"></span> Indeed (${filtered.length})`;
    } else {
      activeTitle.innerHTML = `<i class="fa-solid fa-layer-group" style="color:#0f172a;margin-right:8px;"></i> Toutes les opportunités (${filtered.length})`;
    }
  }

  if (tabCount) tabCount.innerText = filtered.length;
  const elSheetCount = document.getElementById("sheet-current-count");
  if (elSheetCount) {
    elSheetCount.innerText = (selectedStatus === "applied") ? `${filtered.length} candidatures postulées` : `${filtered.length} offres`;
  }
  if (countText) {
    if (selectedStatus === "applied") {
      countText.innerText = `Candidatures transmises : ${filtered.length}`;
    } else {
      const modeLabel = filterOnly1Click ? " • Filtre 1 Clic actif" : " • Affichage de toutes les offres";
      countText.innerText = `Nombre d'offres : ${filtered.length}${modeLabel}`;
    }
  }

  if (filtered.length === 0) {
    const emptyMsg = (selectedStatus === "applied")
      ? "Aucune candidature postulée pour l'instant. Choisissez des offres et cliquez sur 'Postuler en 1 Clic' !"
      : 'Aucune offre ne correspond à cette recherche. Cliquez sur "Toutes" ou lancez "Scanner en Direct".';
    tbody.innerHTML = `
      <tr>
        <td colspan="9" style="text-align:center; padding: 40px 12px; color: var(--text-muted);">
          ${emptyMsg}
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filtered.map(renderTableRow).join("");

  // Bind direct apply buttons
  tbody.querySelectorAll(".btn-apply-action").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const id = btn.getAttribute("data-id");
      await handleApply(id, btn);
    });
  });

  // Bind ignore buttons
  tbody.querySelectorAll(".btn-ignore-row").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const id = btn.getAttribute("data-id");
      await handleIgnore(id);
    });
  });

  // Bind row click to open side-peek
  tbody.querySelectorAll("tr").forEach(row => {
    row.addEventListener("click", (e) => {
      if (e.target.closest("button") || e.target.closest("a")) return;
      const jobId = row.getAttribute("data-id");
      const job = allJobs.find(j => String(j.id) === String(jobId));
      if (job) openSidePeek(job);
    });
  });

  updateBatchCounts();
}

function renderTableRow(job) {
  const companyClean = escapeHtml(job.company || "Studio Paris");
  const loc = escapeHtml(job.location || "Paris (75)");

  let statusHtml = '';
  let actionBtnHtml = '';

  const resumeHint = activeResumeFilename ? `avec ${activeResumeFilename}` : 'sans CV';
  const is1Click = (job.is_easy_apply !== 0 && job.is_easy_apply !== false);

  if (job.status === "applied") {
    const appliedDate = job.applied_at ? `Postulé le ${new Date(job.applied_at).toLocaleDateString('fr-FR', {hour:'2-digit', minute:'2-digit'})}` : 'Postulé';
    statusHtml = `
      <span class="notion-status-pill applied" title="${appliedDate}">
        <span class="status-dot"></span> Postulé
      </span>
    `;
    actionBtnHtml = `
      <button class="btn-apply-action applied" disabled title="Candidature réellement transmise avec succès">
        <i class="fa-solid fa-check"></i> Postulé
      </button>
    `;
  } else if (job.status === "applying") {
    statusHtml = `
      <span class="notion-status-pill contacted">
        <span class="status-dot"></span> En cours
      </span>
    `;
    actionBtnHtml = `
      <button class="btn-apply-action applying" disabled>
        <i class="fa-solid fa-spinner fa-spin"></i> En cours
      </button>
    `;
  } else if (job.status === "skipped") {
    const reason = job.error_message || "Candidature externe requise";
    statusHtml = `
      <span class="notion-status-pill skipped" title="${escapeHtml(reason)}">
        <span class="status-dot"></span> Externe
      </span>
    `;
    actionBtnHtml = `
      <a href="${job.job_url}" target="_blank" class="btn-apply-action external" title="${escapeHtml(reason)} : Cliquez pour ouvrir le site externe">
        <i class="fa-solid fa-arrow-up-right-from-square"></i> Site
      </a>
    `;
  } else if (job.status === "failed") {
    const errorMsg = job.error_message || "Échec de postulation";
    statusHtml = `
      <span class="notion-status-pill failed" title="${escapeHtml(errorMsg)}">
        <span class="status-dot"></span> Échec
      </span>
    `;
    actionBtnHtml = `
      <button class="btn-apply-action failed" data-id="${job.id}" title="Échec : ${escapeHtml(errorMsg)}. Cliquez pour réessayer">
        <i class="fa-solid fa-rotate-right"></i> Réessayer
      </button>
    `;
  } else if (job.status === "requires_review") {
    statusHtml = `
      <span class="notion-status-pill requires-review" title="Formulaire nécessitant une révision">
        <span class="status-dot"></span> À vérifier
      </span>
    `;
    actionBtnHtml = `
      <a href="${job.job_url}" target="_blank" class="btn-apply-action review">
        <i class="fa-solid fa-eye"></i> Vérifier
      </a>
    `;
  } else {
    // Default / detected
    statusHtml = `
      <span class="notion-status-pill to-contact">
        <span class="status-dot"></span> À contacter
      </span>
    `;
    actionBtnHtml = `
      <button class="btn-apply-action primary" data-id="${job.id}" title="Postuler immédiatement en 1 Clic (${resumeHint})">
        <i class="fa-solid fa-bolt"></i> Postuler
      </button>
    `;
  }

  const score = job.match_score || 75;
  const scoreBadge = score >= 80 
    ? `<span class="table-score-badge high">${score}%</span>` 
    : `<span class="table-score-badge normal">${score}%</span>`;

  const easyApplyTag = is1Click 
    ? `<span class="badge-table-1click" title="Option Postuler en 1 Clic disponible">1 Clic</span>` 
    : '';

  // Real-time publication badge
  const relativeText = job.posted_relative || (job.created_at ? formatRelativeTime(job.created_at) : "Récent");
  const relLower = relativeText.toLowerCase();
  const isFresh = relLower.includes("aujourd") || 
                  relLower.includes("min") || 
                  relLower.includes("instant") || 
                  relLower.includes("h") ||
                  relLower.includes("direct");
  const isYesterday = relLower.includes("hier");

  const pubHtml = (isFresh && !isYesterday) ? `
    <span class="badge-live-fresh" title="Offre temps réel • ${escapeHtml(job.posted_at || relativeText)}">
      <span class="live-pulse-dot"></span> ${escapeHtml(relativeText)}
    </span>
  ` : `
    <span class="badge-live-standard" title="Horodatage : ${escapeHtml(job.posted_at || relativeText)}">
      <i class="fa-regular fa-clock" style="font-size:11px; margin-right:4px;"></i> ${escapeHtml(relativeText)}
    </span>
  `;

  const platKey = (job.platform || "francetravail").toLowerCase();
  const platBadge = platKey === "francetravail"
    ? `<span class="steady-table-plat-badge ft" title="Plateforme : France Travail"><span class="steady-dot ft"></span> FT</span>`
    : platKey === "linkedin"
    ? `<span class="steady-table-plat-badge li" title="Plateforme : LinkedIn"><span class="steady-dot li"></span> LI</span>`
    : `<span class="steady-table-plat-badge ind" title="Plateforme : Indeed"><span class="steady-dot ind"></span> Indeed</span>`;

  return `
    <tr id="job-row-${job.id}" data-id="${job.id}" style="cursor:pointer;" title="Cliquez pour ouvrir la fiche détaillée ou le bouton d'action">
      <td>
        <div class="studio-row-cell">
          <i class="fa-regular fa-file-lines" style="color:var(--text-muted); font-size:13px;"></i>
          <span title="${escapeHtml(job.job_title)}">${escapeHtml(job.job_title)}</span>
          ${easyApplyTag}
        </div>
      </td>
      <td class="row-dim-text">
        <div style="display:inline-flex; align-items:center; gap:6px;">
          ${platBadge}
          <span title="${companyClean}">${companyClean}</span>
        </div>
      </td>
      <td class="row-dim-text">
        <span title="${loc}">${loc}</span>
      </td>
      <td>
        ${pubHtml}
      </td>
      <td>
        ${statusHtml}
      </td>
      <td>
        ${scoreBadge}
      </td>
      <td>
        ${actionBtnHtml}
      </td>
      <td class="row-dim-text" style="max-width:180px; overflow:hidden; text-overflow:ellipsis;" title="${escapeHtml(job.match_reason || '')}">
        ${escapeHtml(job.match_reason || "Adéquation profil")}
      </td>
      <td>
        <a href="${job.job_url}" target="_blank" class="table-icon-link" title="Ouvrir l'offre originale">
          <i class="fa-solid fa-arrow-up-right-from-square"></i>
        </a>
        <button class="table-icon-link btn-ignore-row" data-id="${job.id}" title="Archiver la ligne">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </td>
    </tr>
  `;
}

async function handleApply(jobId, buttonElem) {
  buttonElem.disabled = true;
  buttonElem.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Traitement Playwright...';
  buttonElem.style.background = "rgba(59, 130, 246, 0.25)";
  buttonElem.style.color = "#93c5fd";

  const targetJob = allJobs.find(j => String(j.id) === String(jobId));
  const jobTitle = targetJob ? targetJob.job_title : "l'offre";

  // Trigger 3D Particle Progress Bar on the main screen
  if (window.ParticleProgress3D) {
    window.ParticleProgress3D.open({
      title: targetJob ? targetJob.job_title : "Candidature 1-Clic",
      company: targetJob ? targetJob.company : "Entreprise",
      platform: targetJob ? targetJob.platform : "1-Clic",
      mode: "single",
      totalCount: 1,
      resume: activeResumeFilename || "CV Actif"
    });
  }

  // Update table row visual status immediately to "En cours..."
  const row = document.getElementById(`job-row-${jobId}`);
  if (row && row.cells[3]) {
    row.cells[3].innerHTML = `
      <span class="notion-status-pill contacted">
        <span class="status-dot"></span> En cours...
      </span>
    `;
  }

  showToast(`⚡ Postulation automatique (mode humain indétectable) lancée pour ${jobTitle}...`, "info");

  try {
    const res = await fetch(`/api/jobs/${jobId}/apply`, { method: "POST" });
    if (!res.ok) throw new Error("Erreur serveur lors du déclenchement");
    
    // Real-time polling until background Playwright finishes (no fake timeout!)
    let attempts = 0;
    const maxAttempts = 25; // up to ~30-35s
    const pollInterval = setInterval(async () => {
      attempts++;

      // Update 3D particle progress bar in real time
      const estPct = Math.min(88, 12 + attempts * 8);
      let stepMsg = "1. Initialisation de la session furtive Playwright...";
      if (estPct >= 25 && estPct < 55) {
        stepMsg = "2. Navigation biométrique vers l'offre & bypass anti-bot...";
      } else if (estPct >= 55 && estPct < 75) {
        stepMsg = `3. Injection du CV (${activeResumeFilename || 'CV Eliot'}) et des coordonnées...`;
      } else if (estPct >= 75 && estPct < 88) {
        stepMsg = "4. Traitement intelligent des questions employeur...";
      } else if (estPct >= 88) {
        stepMsg = "5. Finalisation & validation de la candidature...";
      }

      if (window.ParticleProgress3D) {
        window.ParticleProgress3D.setProgress(estPct, stepMsg, {
          success_count: 0,
          remaining: 1,
          skipped_count: 0,
          title: targetJob ? targetJob.job_title : null,
          company: targetJob ? targetJob.company : null,
          platform: targetJob ? targetJob.platform : null
        });
      }
      if (window.__updateNeuralProgress) {
        window.__updateNeuralProgress(estPct, stepMsg);
      }

      try {
        const sRes = await fetch(`/api/jobs/${jobId}/status`);
        if (!sRes.ok) return;
        const jobStatus = await sRes.json();

        if (jobStatus.status !== "applying" || attempts >= maxAttempts) {
          clearInterval(pollInterval);

          // Update memory state
          if (targetJob) {
            targetJob.status = jobStatus.status;
            targetJob.applied_at = jobStatus.applied_at;
            targetJob.error_message = jobStatus.error_message;
          }

          if (jobStatus.status === "applied") {
            const comp = jobStatus.company || (targetJob ? targetJob.company : "l'employeur");
            if (window.ParticleProgress3D) {
              window.ParticleProgress3D.setProgress(100, "Candidature transmise et confirmée !", {
                success_count: 1,
                remaining: 0,
                skipped_count: 0
              });
              window.ParticleProgress3D.complete(true, `Candidature réellement transmise avec succès à ${comp} !`);
            }
            if (window.__completeNeuralProgress) {
              window.__completeNeuralProgress(true, `Candidature réellement transmise avec succès à ${comp} !`);
            }
            showToast(`✓ Candidature réellement transmise avec succès à ${comp} !`, "success");
          } else if (jobStatus.status === "skipped") {
            if (window.ParticleProgress3D) {
              window.ParticleProgress3D.complete(false, `Redirection requise : ${jobStatus.error_message || 'Site employeur externe'}`);
            }
            if (window.__completeNeuralProgress) {
              window.__completeNeuralProgress(false, `Redirection requise : ${jobStatus.error_message || 'Site employeur externe'}`);
            }
            showToast(`ℹ️ Non éligible au 1 Clic : ${jobStatus.error_message || 'Redirection externe requise'}`, "warning");
          } else if (jobStatus.status === "failed") {
            if (window.ParticleProgress3D) {
              window.ParticleProgress3D.complete(false, `Échec : ${jobStatus.error_message || 'Erreur lors de la postulation'}`);
            }
            if (window.__completeNeuralProgress) {
              window.__completeNeuralProgress(false, `Échec : ${jobStatus.error_message || 'Erreur lors de la postulation'}`);
            }
            showToast(`❌ Échec : ${jobStatus.error_message || 'Erreur lors de la postulation'}`, "error");
          } else if (attempts >= maxAttempts) {
            if (window.ParticleProgress3D) {
              window.ParticleProgress3D.complete(true, "Processus en cours en tâche de fond...");
            }
            if (window.__completeNeuralProgress) {
              window.__completeNeuralProgress(true, "Processus en cours en tâche de fond...");
            }
            showToast(`⏳ Le processus continue en tâche de fond. Rafraîchissez dans quelques instants.`, "info");
          }

          renderJobsTable();
          if (currentPeekJob && String(currentPeekJob.id) === String(jobId)) {
            openSidePeek(targetJob || jobStatus);
          }
        }
      } catch (pollErr) {
        console.warn("Polling error:", pollErr);
      }
    }, 1300);

  } catch (e) {
    if (window.ParticleProgress3D) {
      window.ParticleProgress3D.complete(false, "Erreur : " + e.message);
    }
    showToast("Erreur lors de l'initialisation : " + e.message, "error");
    buttonElem.disabled = false;
    buttonElem.innerHTML = '<i class="fa-solid fa-bolt"></i> Postuler (1 Clic)';
  }
}


async function handleIgnore(jobId) {
  try {
    await fetch(`/api/jobs/${jobId}/ignore`, { method: "POST" });
    showToast("Ligne archivée");
    const row = document.getElementById(`job-row-${jobId}`);
    if (row) {
      row.style.opacity = "0.2";
      setTimeout(() => {
        row.remove();
        updateBatchCounts();
      }, 200);
    }
  } catch (e) {
    showToast("Erreur : " + e.message, "error");
  }
}

/* ==========================================================
   CONFIG & SETTINGS
========================================================== */
function setupSettings() {
  const formCriteria = document.getElementById("form-criteria");
  if (formCriteria) {
    formCriteria.addEventListener("submit", async (e) => {
      e.preventDefault();
      const keywords = document.getElementById("input-keywords").value.split(",").map(k => k.trim()).filter(Boolean);
      const locations = document.getElementById("input-locations").value.split(",").map(l => l.trim()).filter(Boolean);
      const minScore = parseInt(document.getElementById("input-min-score").value) || 60;
      const maxDaily = parseInt(document.getElementById("input-max-daily").value) || 25;

      try {
        const res = await fetch("/api/config/criteria", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            keywords,
            locations,
            min_match_score: minScore,
            max_applications_per_day: maxDaily,
          }),
        });
        if (!res.ok) throw new Error("Erreur de sauvegarde");
        showToast("Paramètres de recherche enregistrés !", "success");
      } catch (err) {
        showToast("Erreur : " + err.message, "error");
      }
    });
  }

  const formNotif = document.getElementById("form-notifications");
  if (formNotif) {
    formNotif.addEventListener("submit", async (e) => {
      e.preventDefault();
      const enableTg = document.getElementById("notif-telegram-enable").checked;
      const tokenTg = document.getElementById("input-telegram-token").value.trim();
      const chatIdTg = document.getElementById("input-telegram-chatid").value.trim();
      const enableDisc = document.getElementById("notif-discord-enable").checked;
      const webhookDisc = document.getElementById("input-discord-webhook").value.trim();

      try {
        const res = await fetch("/api/config/notifications", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            enable_telegram: enableTg,
            telegram_bot_token: tokenTg || null,
            telegram_chat_id: chatIdTg || null,
            enable_discord: enableDisc,
            discord_webhook_url: webhookDisc || null,
            enable_in_app: true,
          }),
        });
        if (!res.ok) throw new Error("Erreur de sauvegarde");
        showToast("Alertes enregistrées !", "success");
      } catch (err) {
        showToast("Erreur : " + err.message, "error");
      }
    });
  }

  const btnTestNotif = document.getElementById("btn-test-notif");
  if (btnTestNotif) {
    btnTestNotif.addEventListener("click", async () => {
      try {
        btnTestNotif.disabled = true;
        const res = await fetch("/api/notifications/test", { method: "POST" });
        const data = await res.json();
        showToast(data.message || "Notification de test transmise !", "success");
      } catch (err) {
        showToast("Erreur : " + err.message, "error");
      } finally {
        btnTestNotif.disabled = false;
      }
    });
  }

  const btnSettingsChangeCV = document.getElementById("btn-settings-change-cv");
  if (btnSettingsChangeCV) {
    btnSettingsChangeCV.addEventListener("click", openQuickSwitchModal);
  }
}

async function loadConfig() {
  try {
    const res = await fetch("/api/config");
    const data = await res.json();

    if (data.criteria) {
      const kw = document.getElementById("input-keywords");
      const loc = document.getElementById("input-locations");
      const minS = document.getElementById("input-min-score");
      const maxD = document.getElementById("input-max-daily");
      const easyApplyCheck = document.getElementById("settings-toggle-easy-apply");
      const headerToggle = document.getElementById("header-toggle-1click");

      if (kw) kw.value = (data.criteria.keywords || []).join(", ");
      if (loc) loc.value = (data.criteria.locations || []).join(", ");
      if (minS) minS.value = data.criteria.min_match_score || 65;
      if (maxD) maxD.value = data.criteria.max_applications_per_day || 25;

      const isEasy = (data.criteria.easy_apply_only !== false);
      option1ClickEnabled = isEasy;
      if (easyApplyCheck) easyApplyCheck.checked = isEasy;
      if (headerToggle) headerToggle.checked = isEasy;
      update1ClickUI(isEasy);
    }

    if (data.notifications) {
      const tgEn = document.getElementById("notif-telegram-enable");
      const tgTok = document.getElementById("input-telegram-token");
      const tgChat = document.getElementById("input-telegram-chatid");
      const discEn = document.getElementById("notif-discord-enable");
      const discWeb = document.getElementById("input-discord-webhook");

      if (tgEn) tgEn.checked = !!data.notifications.enable_telegram;
      if (tgTok) tgTok.value = data.notifications.telegram_bot_token || "";
      if (tgChat) tgChat.value = data.notifications.telegram_chat_id || "";
      if (discEn) discEn.checked = !!data.notifications.enable_discord;
      if (discWeb) discWeb.value = data.notifications.discord_webhook_url || "";
    }
  } catch (e) {
    console.error("Error loading config:", e);
  }
}


function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/* ==========================================================
   PLATFORMS & SESSIONS MANAGER
========================================================== */
function bindPlatformActionButtons(scope = document) {
  // Open Chromium login window buttons
  scope.querySelectorAll(".btn-open-browser-win").forEach(btn => {
    if (btn._hasOpenListener) return;
    btn._hasOpenListener = true;

    btn.addEventListener("click", async () => {
      const plat = btn.getAttribute("data-plat");
      const targetUrl = btn.getAttribute("data-target-url");
      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Ouverture du navigateur...';

      try {
        const bodyPayload = targetUrl ? { target_url: targetUrl } : {};
        const res = await fetch(`/api/platforms/${plat}/login-window`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(bodyPayload)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Échec de l'ouverture");
        showToast(data.message || `Fenêtre Chromium ouverte pour ${plat.toUpperCase()}`, "info");
        btn.innerHTML = '<i class="fa-solid fa-window-restore"></i> Navigateur ouvert (Actif)';
      } catch (e) {
        showToast("Erreur d'ouverture : " + e.message, "error");
        btn.innerHTML = '<i class="fa-solid fa-window-restore"></i> Ouvrir Chromium';
      } finally {
        btn.disabled = false;
      }
    });
  });

  // Verify session buttons
  scope.querySelectorAll(".btn-verify-session-plat").forEach(btn => {
    if (btn._hasVerifyListener) return;
    btn._hasVerifyListener = true;

    btn.addEventListener("click", async () => {
      const plat = btn.getAttribute("data-plat");
      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Vérification...';

      try {
        const res = await fetch(`/api/platforms/${plat}/verify-session`, { method: "POST" });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Erreur de validation");

        if (data.logged_in) {
          showToast(`✓ Session ${plat.toUpperCase()} enregistrée avec succès !`, "success");
          loadPinnedPlatforms();
          if (!pinnedPlatforms.includes(plat)) {
            pinnedPlatforms.push(plat);
            savePinnedPlatforms();
          }
        } else {
          showToast(data.message || "Connexion non détectée. Veuillez vous connecter dans Chromium avant de valider.", "warning");
        }
        await loadPlatformsStatus();
        if (typeof renderDynamicDockPlatforms === "function") {
          renderDynamicDockPlatforms();
        }
      } catch (e) {
        showToast("Erreur de vérification : " + e.message, "error");
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-check"></i> Valider ma connexion';
        const openBtn = document.querySelector(`.btn-open-browser-win[data-plat="${plat}"]`);
        if (openBtn) openBtn.innerHTML = '<i class="fa-solid fa-window-restore"></i> Ouvrir Chromium';
      }
    });
  });

  // Close single platform browser button
  scope.querySelectorAll(".btn-close-browser-win").forEach(btn => {
    if (btn._hasCloseListener) return;
    btn._hasCloseListener = true;

    btn.addEventListener("click", async () => {
      const plat = btn.getAttribute("data-plat");
      try {
        const res = await fetch(`/api/platforms/${plat}/close-browser`, { method: "POST" });
        const data = await res.json();
        showToast(data.message || `Fenêtre ${plat.toUpperCase()} fermée`, "info");
        const openBtn = document.querySelector(`.btn-open-browser-win[data-plat="${plat}"]`);
        if (openBtn) openBtn.innerHTML = '<i class="fa-solid fa-window-restore"></i> Ouvrir Chromium';
      } catch (e) {
        showToast("Erreur : " + e.message, "error");
      }
    });
  });

  // Disconnect platform button
  scope.querySelectorAll(".btn-disconnect-plat").forEach(btn => {
    if (btn._hasDisconnectListener) return;
    btn._hasDisconnectListener = true;

    btn.addEventListener("click", async () => {
      const plat = btn.getAttribute("data-plat");
      if (!confirm(`Voulez-vous déconnecter votre session ${plat.toUpperCase()} ?`)) return;
      try {
        const res = await fetch(`/api/platforms/${plat}/disconnect`, { method: "POST" });
        const data = await res.json();
        showToast(data.message || `Session ${plat.toUpperCase()} déconnectée`, "info");
        await loadPlatformsStatus();
      } catch (e) {
        showToast("Erreur de déconnexion : " + e.message, "error");
      }
    });
  });
}

function setupPlatformsManager() {
  bindPlatformActionButtons(document);

  // Emergency Kill All Browsers button
  const btnKillAll = document.getElementById("btn-kill-all-browsers");
  if (btnKillAll) {
    btnKillAll.addEventListener("click", async () => {
      try {
        btnKillAll.disabled = true;
        btnKillAll.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Fermeture en cours...';
        await fetch("/api/platforms/kill-all-browsers", { method: "POST" });
        showToast("✓ Toutes les fenêtres de navigateur ont été fermées !", "success");
        document.querySelectorAll(".btn-open-browser-win").forEach(btn => {
          btn.innerHTML = '<i class="fa-solid fa-window-restore"></i> Ouvrir Chromium';
        });
      } catch (e) {
        showToast("Erreur : " + e.message, "error");
      } finally {
        btnKillAll.disabled = false;
        btnKillAll.innerHTML = '<i class="fa-solid fa-power-off"></i> Fermer tous les navigateurs';
      }
    });
  }

  // LinkedIn li_at cookie injection
  const btnSubmitLiAt = document.getElementById("btn-submit-li-at");
  const inputLiAt = document.getElementById("input-li-at-cookie");

  if (btnSubmitLiAt && inputLiAt) {
    btnSubmitLiAt.addEventListener("click", async () => {
      const cookieVal = inputLiAt.value.trim();
      if (!cookieVal) {
        showToast("Veuillez coller votre cookie li_at", "error");
        return;
      }

      btnSubmitLiAt.disabled = true;
      btnSubmitLiAt.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Test du cookie...';

      try {
        const res = await fetch("/api/platforms/linkedin/set-cookie", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ li_at: cookieVal })
        });
        const data = await res.json();

        if (data.logged_in) {
          showToast("✓ Cookie li_at validé ! Connecté à LinkedIn.", "success");
          inputLiAt.value = "";
        } else {
          showToast(data.message || "Cookie invalide ou refusé par LinkedIn.", "error");
        }
        await loadPlatformsStatus();
      } catch (e) {
        showToast("Erreur : " + e.message, "error");
      } finally {
        btnSubmitLiAt.disabled = false;
        btnSubmitLiAt.innerHTML = '<i class="fa-solid fa-bolt"></i> Injecter';
      }
    });
  }

  // Header platforms pill shortcut
  const btnHeaderPlatforms = document.getElementById("btn-header-platforms");
  if (btnHeaderPlatforms) {
    btnHeaderPlatforms.addEventListener("click", () => {
      switchViewTab("tab-platforms");
    });
  }
}

let lastPlatformsStatus = {};

async function loadPlatformsStatus() {
  try {
    const res = await fetch("/api/platforms/status");
    const data = await res.json();
    window.lastPlatformsStatus = data;
    lastPlatformsStatus = data;

    let countConnected = 0;

    Object.entries(data).forEach(([platId, info]) => {
      const isLogged = info ? Boolean(info.logged_in) : false;
      if (isLogged) countConnected++;

      const badge = document.getElementById(`badge-${platId}`);
      if (badge) {
        badge.className = `platform-status-badge ${isLogged ? "connected" : "disconnected"}`;
        badge.innerHTML = `
          <span class="dot"></span>
          <span class="txt">${isLogged ? "Connecté" : (info.isBuiltinCatalog || info.is_custom ? "Disponible" : "Déconnecté")}</span>
        `;
      }

      // Toggle disconnect buttons visibility
      document.querySelectorAll(`.btn-disconnect-plat[data-plat="${platId}"]`).forEach(btn => {
        btn.style.display = isLogged ? "inline-flex" : "none";
      });
    });

    const topbarCount = document.getElementById("topbar-platforms-count");
    const tabBadge = document.getElementById("tab-platforms-badge");

    if (topbarCount) topbarCount.innerText = `${countConnected} connectée(s)`;
    if (tabBadge) {
      tabBadge.innerText = `${countConnected}`;
      if (countConnected > 0) {
        tabBadge.style.background = "rgba(16, 185, 129, 0.25)";
        tabBadge.style.color = "#34d399";
      } else {
        tabBadge.style.background = "rgba(255, 255, 255, 0.08)";
        tabBadge.style.color = "#999999";
      }
    }

    const countConnectedEl = document.getElementById("count-platforms-connected");
    if (countConnectedEl) countConnectedEl.innerText = countConnected;

    // Steady Invoicing Platform KPI Updates (Plateformes Actives: FT, LinkedIn, Indeed)
    const steadyPlatCount = document.getElementById("steady-kpi-platforms-count");
    const corePlatforms = ["francetravail", "linkedin", "indeed"];
    const activeCore = corePlatforms.filter(id => Boolean(data[id]?.logged_in)).length;
    if (steadyPlatCount) steadyPlatCount.innerText = `${activeCore} / 3`;

    const ftChip = document.querySelector(".steady-dot.ft")?.closest(".steady-plat-chip");
    const liChip = document.querySelector(".steady-dot.li")?.closest(".steady-plat-chip");
    const indChip = document.querySelector(".steady-dot.ind")?.closest(".steady-plat-chip");
    if (ftChip) ftChip.className = `steady-plat-chip ${data.francetravail?.logged_in ? 'online' : 'offline'}`;
    if (liChip) liChip.className = `steady-plat-chip ${data.linkedin?.logged_in ? 'online' : 'offline'}`;
    if (indChip) indChip.className = `steady-plat-chip ${data.indeed?.logged_in ? 'online' : 'offline'}`;

    // Mini status dots in Drawer
    const dotFT = document.getElementById("drawer-dot-ft");
    if (dotFT) dotFT.className = `mini-status-dot ${data.francetravail?.logged_in ? "" : "disconnected"}`;
    const dotLI = document.getElementById("drawer-dot-li");
    if (dotLI) dotLI.className = `mini-status-dot ${data.linkedin?.logged_in ? "" : "disconnected"}`;
    const dotInd = document.getElementById("drawer-dot-ind");
    if (dotInd) dotInd.className = `mini-status-dot ${data.indeed?.logged_in ? "" : "disconnected"}`;

    // Sync dock platform buttons whenever status updates
    renderDynamicDockPlatforms();
  } catch (e) {
    console.error("Error loading platforms status:", e);
  }
}

/* ==========================================================
   PLATFORMS CATALOG, SEARCH & CUSTOM ADD MANAGEMENT
========================================================== */
const POPULAR_PLATFORMS_CATALOG = [
  {
    id: "wttj",
    name: "Welcome to the Jungle",
    shortName: "WTTJ",
    category: "Tech & Startups",
    role: "Offres Tech, Design & Culture d'entreprise",
    url: "https://www.welcometothejungle.com",
    login_url: "https://www.welcometothejungle.com/fr/signin",
    search_url: "https://www.welcometothejungle.com/fr/jobs?query=Paris",
    icon: "fa-solid fa-tree",
    color: "#eab308",
    isBuiltinCatalog: true
  },
  {
    id: "apec",
    name: "Apec",
    shortName: "Apec",
    category: "Cadres & Dirigeants",
    role: "Offres cadres, ingénieurs et managers Paris & IDF",
    url: "https://www.apec.fr",
    login_url: "https://www.apec.fr/mon-espace/connexion.html",
    search_url: "https://www.apec.fr/candidat/recherche-emploi.html",
    icon: "fa-solid fa-user-tie",
    color: "#0284c7",
    isBuiltinCatalog: true
  },
  {
    id: "hellowork",
    name: "HelloWork",
    shortName: "HelloWork",
    category: "Généraliste",
    role: "Portail d'emploi leader en France (ex-RegionsJob)",
    url: "https://www.hellowork.com",
    login_url: "https://www.hellowork.com/fr-fr/mon-compte/connexion.html",
    search_url: "https://www.hellowork.com/fr-fr/emploi.html",
    icon: "fa-solid fa-handshake",
    color: "#ef4444",
    isBuiltinCatalog: true
  },
  {
    id: "glassdoor",
    name: "Glassdoor",
    shortName: "Glassdoor",
    category: "Avis & Salaires",
    role: "Offres d'emploi avec transparence des salaires",
    url: "https://www.glassdoor.fr",
    login_url: "https://www.glassdoor.fr/profile/login_input.htm",
    search_url: "https://www.glassdoor.fr/Emploi/paris-emplois-SRCH_IL.0,5_IC2881970.htm",
    icon: "fa-solid fa-door-open",
    color: "#10b981",
    isBuiltinCatalog: true
  },
  {
    id: "lesjeunestalents",
    name: "Les Jeunes Talents",
    shortName: "Jeunes Talents",
    category: "Stages & Juniors",
    role: "Premiers emplois, alternances & diplômés",
    url: "https://www.lesjeunestalents.fr",
    login_url: "https://www.lesjeunestalents.fr/login",
    search_url: "https://www.lesjeunestalents.fr/offres",
    icon: "fa-solid fa-graduation-cap",
    color: "#ec4899",
    isBuiltinCatalog: true
  }
];

let pinnedPlatforms = [];

function loadPinnedPlatforms() {
  try {
    const saved = localStorage.getItem("arova_dock_pinned_platforms");
    pinnedPlatforms = saved ? JSON.parse(saved) : [];
    if (Array.isArray(pinnedPlatforms)) {
      pinnedPlatforms = pinnedPlatforms.filter(id => id !== "monster" && id !== "meteojob");
      localStorage.setItem("arova_dock_pinned_platforms", JSON.stringify(pinnedPlatforms));
    } else {
      pinnedPlatforms = [];
    }
  } catch (e) {
    pinnedPlatforms = [];
  }
}

function savePinnedPlatforms() {
  try {
    localStorage.setItem("arova_dock_pinned_platforms", JSON.stringify(pinnedPlatforms));
  } catch (e) {}
}

const VIBRANT_PALETTE = [
  "#a855f7", "#ec4899", "#06b6d4", "#f97316",
  "#6366f1", "#14b8a6", "#e11d48", "#8b5cf6", "#3b82f6"
];

function getCustomPlatformColor(platId) {
  let hash = 0;
  const str = String(platId || "custom");
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = Math.abs(hash) % VIBRANT_PALETTE.length;
  return VIBRANT_PALETTE[index];
}

function getPlatformMeta(platformKey) {
  const key = (platformKey || "").toLowerCase();
  if (!key) {
    return {
      id: "",
      name: "Toutes les candidatures",
      shortName: "Toutes",
      color: "#0f1015",
      textColor: "#ffffff",
      themeClass: "arova-theme-black",
      icon: "fa-solid fa-layer-group"
    };
  }
  if (key === "francetravail" || key === "france travail") {
    return {
      id: "francetravail",
      name: "France Travail",
      shortName: "France Travail",
      color: "#dc2626",
      textColor: "#ffffff",
      themeClass: "arova-theme-red",
      icon: "fa-solid fa-building-columns"
    };
  }
  if (key === "linkedin") {
    return {
      id: "linkedin",
      name: "LinkedIn",
      shortName: "LinkedIn",
      color: "#0284c7",
      textColor: "#ffffff",
      themeClass: "arova-theme-blue",
      icon: "fa-brands fa-linkedin-in"
    };
  }
  if (key === "indeed") {
    return {
      id: "indeed",
      name: "Indeed",
      shortName: "Indeed",
      color: "#16a34a",
      textColor: "#ffffff",
      themeClass: "arova-theme-green",
      icon: "fa-solid fa-briefcase"
    };
  }

  // Check popular catalog
  const cat = POPULAR_PLATFORMS_CATALOG.find(p => p.id === key);
  if (cat) {
    return {
      id: cat.id,
      name: cat.name,
      shortName: cat.shortName || cat.name,
      color: cat.color || "#8b5cf6",
      textColor: "#ffffff",
      themeClass: "arova-theme-colored",
      icon: cat.icon || "fa-solid fa-globe"
    };
  }

  // Check custom platforms
  const cust = customPlatformsList.find(p => p.id === key || `custom_${p.id}` === key);
  if (cust) {
    return {
      id: cust.id,
      name: cust.name,
      shortName: cust.name,
      color: cust.color || getCustomPlatformColor(cust.id),
      textColor: "#ffffff",
      themeClass: "arova-theme-colored",
      icon: cust.icon || "fa-solid fa-globe"
    };
  }

  // Generic fallback
  return {
    id: key,
    name: platformKey.charAt(0).toUpperCase() + platformKey.slice(1),
    shortName: platformKey.charAt(0).toUpperCase() + platformKey.slice(1),
    color: getCustomPlatformColor(key),
    textColor: "#ffffff",
    themeClass: "arova-theme-colored",
    icon: "fa-solid fa-globe"
  };
}

function renderDynamicDockPlatforms() {
  const ctasContainer = document.getElementById("arova-dock-ctas");
  const sheetTabsContainer = document.getElementById("sheet-platform-switch");
  const dockPill = document.querySelector(".arova-dock-pill");
  if (!ctasContainer) return;

  if (dockPill) {
    dockPill.style.display = "inline-flex";
    dockPill.style.alignItems = "center";
    dockPill.style.gap = "7px";
    dockPill.style.flexWrap = "nowrap";
    dockPill.style.whiteSpace = "nowrap";
    dockPill.style.overflowX = "auto";
    dockPill.style.overflowY = "hidden";
    if (!dockPill._wheelBound) {
      dockPill._wheelBound = true;
      dockPill.addEventListener("wheel", (e) => {
        if (e.deltaY !== 0) {
          e.preventDefault();
          dockPill.scrollLeft += e.deltaY;
        }
      }, { passive: false });
    }
  }

  ctasContainer.style.display = "inline-flex";
  ctasContainer.style.alignItems = "center";
  ctasContainer.style.gap = "7px";
  ctasContainer.style.flexWrap = "nowrap";
  ctasContainer.style.whiteSpace = "nowrap";
  ctasContainer.style.flexShrink = "0";

  loadPinnedPlatforms();

  // 1. Built-in base platforms
  const platformsToDisplay = [
    { id: "", name: "Toutes les candidatures", shortName: "Toutes", color: "#0f1015", textColor: "#ffffff", isBlack: true },
    { id: "francetravail", name: "France Travail", shortName: "France Travail", color: "#dc2626", textColor: "#ffffff" },
    { id: "linkedin", name: "LinkedIn", shortName: "LinkedIn", color: "#0284c7", textColor: "#ffffff" },
    { id: "indeed", name: "Indeed", shortName: "Indeed", color: "#16a34a", textColor: "#ffffff" }
  ];

  // 2. Add all custom platforms created by user (always included on dock)
  customPlatformsList.forEach(cp => {
    if (!platformsToDisplay.some(p => p.id.toLowerCase() === cp.id.toLowerCase())) {
      platformsToDisplay.push({
        id: cp.id,
        name: cp.name,
        shortName: cp.name,
        color: cp.color || getCustomPlatformColor(cp.id),
        textColor: "#ffffff",
        isCustom: true
      });
    }
  });

  // 3. Add any catalog platform that is connected (logged_in) or pinned
  POPULAR_PLATFORMS_CATALOG.forEach(cat => {
    const isConnected = Boolean(window.lastPlatformsStatus && window.lastPlatformsStatus[cat.id]?.logged_in);
    const isPinned = pinnedPlatforms.includes(cat.id);
    if ((isConnected || isPinned) && !platformsToDisplay.some(p => p.id.toLowerCase() === cat.id.toLowerCase())) {
      platformsToDisplay.push({
        id: cat.id,
        name: cat.name,
        shortName: cat.shortName || cat.name,
        color: cat.color || "#8b5cf6",
        textColor: "#ffffff",
        isCatalog: true
      });
    }
  });

  // Render CTA buttons in Dock (Zen Frosted Glass with Micro-Dots)
  ctasContainer.innerHTML = "";
  platformsToDisplay.forEach(plat => {
    const btn = document.createElement("button");
    const isActive = (typeof selectedPlatform !== "undefined" && selectedPlatform === plat.id && typeof arovaStatusFilter !== "undefined" && arovaStatusFilter === "");
    btn.className = `arova-cta-btn ${isActive ? 'active' : ''}`;
    btn.id = `btn-dock-${plat.id || 'all'}`;
    btn.setAttribute("data-dock-platform", plat.id);
    btn.setAttribute("title", `Candidatures • ${plat.name}`);
    btn.style.flexShrink = "0";
    btn.style.whiteSpace = "nowrap";

    const count = plat.id === ""
      ? allJobs.length
      : allJobs.filter(j => (j.platform || "").toLowerCase() === plat.id.toLowerCase()).length;

    let dotClass = "custom-dot";
    const pid = (plat.id || "").toLowerCase();
    if (pid === "francetravail") dotClass = "ft-dot";
    else if (pid === "linkedin") dotClass = "li-dot";
    else if (pid === "indeed") dotClass = "ind-dot";
    else if (pid === "wttj") dotClass = "wttj-dot";

    const dotHtml = plat.id === ""
      ? `<span class="platform-dot" style="background:#94a3b8;"></span>`
      : `<span class="platform-dot ${dotClass}" ${plat.color && dotClass === 'custom-dot' ? `style="background:${plat.color};"` : ''}></span>`;

    btn.innerHTML = `
      ${dotHtml}
      <span>${escapeHtml(plat.shortName || plat.name)}</span>
      <span class="arova-cta-badge" id="dock-count-${plat.id || 'all'}">${count}</span>
    `;

    btn.addEventListener("click", () => {
      const floatingCard = document.getElementById("arova-floating-card");
      if (floatingCard && floatingCard.classList.contains("open") && selectedPlatform === plat.id && arovaStatusFilter === "") {
        closeArovaCard();
      } else {
        openArovaCard(plat.id, "");
      }
    });

    ctasContainer.appendChild(btn);
  });

  // Dedicated "Postulées" CTA button on Dock
  const appliedCount = allJobs.filter(j => j.status === "applied").length;
  const appliedBtn = document.createElement("button");
  const isAppliedActive = typeof arovaStatusFilter !== "undefined" && arovaStatusFilter === "applied";
  appliedBtn.className = `arova-cta-btn ${isAppliedActive ? 'active' : ''}`;
  appliedBtn.id = "btn-dock-applied";
  appliedBtn.setAttribute("title", "Consulter les candidatures déjà envoyées avec succès");
  appliedBtn.style.flexShrink = "0";
  appliedBtn.style.whiteSpace = "nowrap";
  appliedBtn.innerHTML = `
    <span class="platform-dot" style="background:#10b981; box-shadow:0 0 6px rgba(16,185,129,0.4);"></span>
    <span>Postulées</span>
    <span class="arova-cta-badge" id="dock-count-applied">${appliedCount}</span>
  `;
  appliedBtn.addEventListener("click", () => {
    const floatingCard = document.getElementById("arova-floating-card");
    if (floatingCard && floatingCard.classList.contains("open") && arovaStatusFilter === "applied") {
      closeArovaCard();
    } else {
      openArovaCard("", "applied");
    }
  });
  ctasContainer.appendChild(appliedBtn);

  // Also sync Sheet platform switcher tabs
  if (sheetTabsContainer) {
    sheetTabsContainer.innerHTML = "";
    platformsToDisplay.forEach(plat => {
      const tabBtn = document.createElement("button");
      tabBtn.className = `sheet-plat-btn ${selectedPlatform === plat.id ? 'active' : ''}`;
      tabBtn.setAttribute("data-sheet-platform", plat.id);
      tabBtn.id = `sheet-tab-${plat.id || 'all'}`;
      tabBtn.innerText = plat.shortName || plat.name;

      tabBtn.addEventListener("click", () => {
        openCandidaturesSheet(plat.id);
      });

      sheetTabsContainer.appendChild(tabBtn);
    });
  }
}

let customPlatformsList = [];
let activePlatformFilter = "all";
let platformSearchTerm = "";

function setupPlatformCatalogAndSearch() {
  const searchInput = document.getElementById("input-search-platforms");
  const clearBtn = document.getElementById("btn-clear-platforms-search");

  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      platformSearchTerm = e.target.value.trim().toLowerCase();
      if (clearBtn) {
        clearBtn.style.display = platformSearchTerm ? "block" : "none";
      }
      filterPlatformCards();
    });
  }

  if (clearBtn && searchInput) {
    clearBtn.addEventListener("click", () => {
      searchInput.value = "";
      platformSearchTerm = "";
      clearBtn.style.display = "none";
      searchInput.focus();
      filterPlatformCards();
    });
  }

  // Filter chips (all, connected, builtin, popular, custom)
  document.querySelectorAll(".platforms-filter-chips .notion-chip[data-platform-filter]").forEach(chip => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".platforms-filter-chips .notion-chip").forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      activePlatformFilter = chip.getAttribute("data-platform-filter") || "all";
      filterPlatformCards();
    });
  });

  // Modal open/close handlers
  const modalAdd = document.getElementById("modal-add-platform");
  const btnOpenModal = document.getElementById("btn-open-add-platform-modal");
  const btnCloseModal = document.getElementById("btn-close-add-platform");
  const btnCancelModal = document.getElementById("btn-cancel-add-platform");
  const btnEmptyAdd = document.getElementById("btn-empty-add-platform");

  function openAddModal(prefillName = "") {
    if (!modalAdd) return;
    modalAdd.style.display = "flex";
    const nameInput = document.getElementById("custom-platform-name");
    if (nameInput) {
      if (prefillName) nameInput.value = prefillName;
      nameInput.focus();
    }
  }

  function closeAddModal() {
    if (!modalAdd) return;
    modalAdd.style.display = "none";
    const form = document.getElementById("form-add-custom-platform");
    if (form) form.reset();
  }

  if (btnOpenModal) {
    btnOpenModal.addEventListener("click", () => openAddModal());
  }
  if (btnEmptyAdd) {
    btnEmptyAdd.addEventListener("click", () => {
      openAddModal(platformSearchTerm);
    });
  }
  if (btnCloseModal) {
    btnCloseModal.addEventListener("click", closeAddModal);
  }
  if (btnCancelModal) {
    btnCancelModal.addEventListener("click", closeAddModal);
  }

  // Close modal when clicking on backdrop
  if (modalAdd) {
    modalAdd.addEventListener("click", (e) => {
      if (e.target === modalAdd) closeAddModal();
    });
  }

  // Submit custom platform
  const formAdd = document.getElementById("form-add-custom-platform");
  if (formAdd) {
    formAdd.addEventListener("submit", async (e) => {
      e.preventDefault();
      const submitBtn = document.getElementById("btn-save-custom-platform");
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Enregistrement...';
      }

      const name = document.getElementById("custom-platform-name").value.trim();
      const url = document.getElementById("custom-platform-url").value.trim();
      const category = document.getElementById("custom-platform-category").value;
      const loginUrl = document.getElementById("custom-platform-login-url").value.trim();
      const searchUrl = document.getElementById("custom-platform-search-url").value.trim();
      const notes = document.getElementById("custom-platform-notes").value.trim();

      try {
        const res = await fetch("/api/platforms/custom", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: name,
            url: url,
            category: category,
            login_url: loginUrl,
            search_url: searchUrl,
            notes: notes
          })
        });

        const data = await res.json();
        if (res.ok && data.platform) {
          showToast(`✓ Plateforme "${name}" ajoutée avec succès !`, "success");
          closeAddModal();
          await loadCustomPlatforms();
        } else {
          showToast(data.message || "Erreur lors de l'enregistrement", "error");
        }
      } catch (err) {
        showToast("Erreur réseau : " + err.message, "error");
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Enregistrer la plateforme';
        }
      }
    });
  }

  // Render initial catalog
  renderPlatformsCatalog();
}

async function loadCustomPlatforms() {
  try {
    const res = await fetch("/api/platforms/custom");
    if (res.ok) {
      const data = await res.json();
      customPlatformsList = Array.isArray(data) ? data : [];
    } else {
      customPlatformsList = [];
    }
  } catch (e) {
    console.warn("Could not load custom platforms:", e);
    customPlatformsList = [];
  }

  const countCustomEl = document.getElementById("count-platforms-custom");
  if (countCustomEl) {
    countCustomEl.innerText = customPlatformsList.length;
  }

  renderPlatformsCatalog();
  renderDynamicDockPlatforms();
}

function renderPlatformsCatalog() {
  const container = document.getElementById("platforms-extra-grid");
  if (!container) return;

  container.innerHTML = "";

  // Combine popular catalog + custom platforms
  const allExtra = [
    ...POPULAR_PLATFORMS_CATALOG.map(p => ({ ...p, isCustom: false })),
    ...customPlatformsList.map(p => ({
      ...p,
      isCustom: true,
      icon: "fa-solid fa-globe",
      color: "#a855f7"
    }))
  ];

  allExtra.forEach(plat => {
    const card = document.createElement("div");
    card.className = "notion-card platform-box platform-catalog-card";
    card.id = `card-plat-${plat.id}`;
    card.setAttribute("data-platform-id", plat.id);
    card.setAttribute("data-platform-name", plat.name.toLowerCase());
    card.setAttribute("data-platform-category", plat.category ? plat.category.toLowerCase() : "");
    card.setAttribute("data-is-custom", plat.isCustom ? "true" : "false");
    card.setAttribute("data-is-popular", plat.isBuiltinCatalog ? "true" : "false");

    const badgeHtml = plat.isCustom
      ? '<span class="platform-tag-badge custom">Personnalisée</span>'
      : '<span class="platform-tag-badge">Jobboard</span>';

    const loginUrl = plat.login_url || plat.url;
    const searchUrl = plat.search_url || plat.url;
    const isConnected = Boolean(window.lastPlatformsStatus && window.lastPlatformsStatus[plat.id]?.logged_in);
    loadPinnedPlatforms();
    const isPinned = pinnedPlatforms.includes(plat.id) || isConnected || plat.isCustom;

    card.innerHTML = `
      <div class="plat-box-head">
        <div class="plat-info">
          <div class="plat-icon-circle" style="background:${plat.color}; color:#ffffff;">
            <i class="${plat.icon || 'fa-solid fa-globe'}"></i>
          </div>
          <div>
            <div style="display:flex; align-items:center; gap:4px;">
              <h3 class="plat-name">${escapeHtml(plat.name)}</h3>
              ${badgeHtml}
            </div>
            <div class="plat-role">${escapeHtml(plat.role || plat.category || "Plateforme d'offres")}</div>
          </div>
        </div>
        <span class="platform-status-badge disconnected" id="badge-${plat.id}">
          <span class="dot"></span> <span class="txt">Disponible</span>
        </span>
      </div>

      <div class="plat-box-content">
        <div class="platform-links-row">
          <a href="${plat.url}" target="_blank" class="platform-link-item">
            <i class="fa-solid fa-arrow-up-right-from-square"></i> Visiter le site
          </a>
          ${plat.search_url ? `
          <a href="${plat.search_url}" target="_blank" class="platform-link-item">
            <i class="fa-solid fa-magnifying-glass"></i> Voir les offres
          </a>` : ''}
        </div>

        <div class="method-card">
          <div class="method-card-head">
            <span class="method-num"><i class="fa-solid fa-window-restore"></i></span>
            <strong>Navigation & Connexion directe</strong>
          </div>
          <p class="method-desc-text">
            Ouvre Chromium directement sur ${escapeHtml(plat.name)} pour vous connecter, consulter les offres et synchroniser vos candidatures.
          </p>
          <div class="method-actions-row">
            <button class="btn-notion primary btn-open-browser-win" data-plat="${plat.id}" data-target-url="${loginUrl}">
              <i class="fa-solid fa-window-restore"></i> Ouvrir Chromium
            </button>
            <button class="btn-notion btn-verify-session-plat" data-plat="${plat.id}">
              <i class="fa-solid fa-check"></i> Valider ma connexion
            </button>
            <button class="btn-notion btn-close-browser-win" data-plat="${plat.id}" title="Fermer le navigateur">
              <i class="fa-solid fa-xmark"></i> Fermer
            </button>
            <button class="btn-notion btn-toggle-dock-pin ${isPinned ? 'pinned' : ''}" data-plat="${plat.id}" title="${isPinned ? 'Présente sur le dock (cliquer pour retirer)' : 'Épingler cette plateforme sur le dock'}">
              <i class="fa-solid ${isPinned ? 'fa-thumbtack' : 'fa-plus'}"></i> ${isPinned ? 'Sur le dock' : 'Ajouter au dock'}
            </button>
            <button class="btn-notion btn-disconnect-plat" data-plat="${plat.id}" title="Déconnecter cette session" style="display: none;">
              <i class="fa-solid fa-arrow-right-from-bracket"></i> Déconnecter
            </button>
            ${plat.isCustom ? `
            <button class="btn-notion btn-delete-custom-plat" data-delete-id="${plat.id}" title="Supprimer cette plateforme">
              <i class="fa-solid fa-trash-can"></i>
            </button>` : ''}
          </div>
        </div>
      </div>
    `;

    container.appendChild(card);
  });

  // Bind all action buttons inside container
  bindPlatformActionButtons(container);

  // Bind toggle pin buttons
  container.querySelectorAll(".btn-toggle-dock-pin").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const platId = btn.getAttribute("data-plat");
      loadPinnedPlatforms();
      if (pinnedPlatforms.includes(platId)) {
        pinnedPlatforms = pinnedPlatforms.filter(id => id !== platId);
        showToast("Plateforme retirée du dock", "info");
      } else {
        pinnedPlatforms.push(platId);
        showToast("✓ Plateforme épinglée sur le dock !", "success");
      }
      savePinnedPlatforms();
      renderPlatformsCatalog();
      renderDynamicDockPlatforms();
    });
  });

  // Sync statuses for all newly rendered cards
  loadPlatformsStatus();

  // Bind delete custom platform buttons
  container.querySelectorAll(".btn-delete-custom-plat").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const deleteId = btn.getAttribute("data-delete-id");
      if (!confirm("Voulez-vous vraiment supprimer cette plateforme personnalisée ?")) return;

      try {
        const res = await fetch(`/api/platforms/custom/${deleteId}`, { method: "DELETE" });
        const data = await res.json();
        showToast(data.message || "Plateforme supprimée", "info");
        await loadCustomPlatforms();
      } catch (err) {
        showToast("Erreur : " + err.message, "error");
      }
    });
  });

  filterPlatformCards();
}

function filterPlatformCards() {
  const query = platformSearchTerm;
  const filter = activePlatformFilter;

  const builtinCards = [
    { el: document.getElementById("card-plat-linkedin"), name: "linkedin", cat: "linkedin", isBuiltin: true, id: "linkedin" },
    { el: document.getElementById("card-plat-indeed"), name: "indeed", cat: "indeed", isBuiltin: true, id: "indeed" },
    { el: document.getElementById("card-plat-francetravail"), name: "france travail francetravail pole emploi", cat: "francetravail", isBuiltin: true, id: "francetravail" }
  ];

  let visibleCount = 0;

  // Filter builtin cards
  builtinCards.forEach(item => {
    if (!item.el) return;
    let matchQuery = true;
    if (query) {
      matchQuery = item.name.includes(query);
    }

    let matchFilter = true;
    if (filter === "popular") matchFilter = false;
    if (filter === "custom") matchFilter = false;
    if (filter === "connected") {
      const badge = item.el.querySelector(".platform-status-badge");
      matchFilter = badge && badge.classList.contains("connected");
    }

    if (matchQuery && matchFilter) {
      item.el.style.display = "";
      visibleCount++;
    } else {
      item.el.style.display = "none";
    }
  });

  // Filter extra cards (popular & custom)
  const extraCards = document.querySelectorAll(".platform-catalog-card");
  extraCards.forEach(card => {
    const name = card.getAttribute("data-platform-name") || "";
    const cat = card.getAttribute("data-platform-category") || "";
    const isCustom = card.getAttribute("data-is-custom") === "true";
    const isPopular = card.getAttribute("data-is-popular") === "true";

    let matchQuery = true;
    if (query) {
      matchQuery = name.includes(query) || cat.includes(query);
    }

    let matchFilter = true;
    if (filter === "builtin") matchFilter = false;
    if (filter === "custom") matchFilter = isCustom;
    if (filter === "popular") matchFilter = isPopular;
    if (filter === "connected") {
      const badge = card.querySelector(".platform-status-badge");
      matchFilter = badge && badge.classList.contains("connected");
    }

    if (matchQuery && matchFilter) {
      card.style.display = "";
      visibleCount++;
    } else {
      card.style.display = "none";
    }
  });

  // Empty state
  const emptyState = document.getElementById("platforms-empty-state");
  if (emptyState) {
    emptyState.style.display = visibleCount === 0 ? "block" : "none";
  }
}

/* ==========================================================
   AROVA INTERACTIVE EXPERIENCE ENGINE
   Floating Editorial Card, Colored Themes (Black for Toutes, Red for FT,
   Blue for LinkedIn, Green for Indeed), Drawer & Theme Switch
========================================================== */
let arovaCardLimit = 8;
let arovaCardSearch = "";
let arovaSortMode = "relevance"; // 'relevance' or 'date'
let arovaStatusFilter = ""; // '' (all), 'unapplied', 'applied'

function renderArovaCardRows() {
  const rowsContainer = document.getElementById("arova-card-rows");
  const countBadge = document.getElementById("arova-card-count");
  const nameBadge = document.getElementById("arova-card-name");
  const loadMoreBtn = document.getElementById("btn-arova-load-more");
  const tabCountApplied = document.getElementById("arova-tab-count-applied");
  if (!rowsContainer) return;

  const meta = getPlatformMeta(selectedPlatform);
  if (nameBadge) {
    if (arovaStatusFilter === "applied") {
      nameBadge.innerText = (meta ? meta.name + " • " : "") + "Candidatures Postulées";
    } else if (arovaStatusFilter === "unapplied") {
      nameBadge.innerText = (meta ? meta.name + " • " : "") + "Offres À Postuler";
    } else {
      nameBadge.innerText = meta ? meta.name : (selectedPlatform || "Toutes les candidatures");
    }
  }

  // Count applied jobs for the current platform
  const appliedForScope = allJobs.filter(j => (!selectedPlatform || (j.platform || "").toLowerCase() === selectedPlatform.toLowerCase()) && j.status === "applied").length;
  if (tabCountApplied) tabCountApplied.innerText = appliedForScope;

  // Filter jobs based on selectedPlatform, arovaStatusFilter, and arovaCardSearch
  const filtered = allJobs.filter(job => {
    if (selectedPlatform && (job.platform || "").toLowerCase() !== selectedPlatform.toLowerCase()) {
      return false;
    }
    if (arovaStatusFilter === "applied" && job.status !== "applied") {
      return false;
    }
    if (arovaStatusFilter === "unapplied" && job.status === "applied") {
      return false;
    }
    if (arovaCardSearch) {
      const matchText = `${job.job_title} ${job.company} ${job.location || ""}`.toLowerCase();
      if (!matchText.includes(arovaCardSearch)) return false;
    }
    return true;
  });

  // Sort according to arovaSortMode
  const sorted = [...filtered].sort((a, b) => {
    if (arovaSortMode === "relevance") {
      const scoreDiff = (b.match_score || 0) - (a.match_score || 0);
      if (scoreDiff !== 0) return scoreDiff;
      const dateA = new Date(a.posted_at || a.created_at || 0).getTime();
      const dateB = new Date(b.posted_at || b.created_at || 0).getTime();
      return dateB - dateA;
    } else {
      const dateA = new Date(a.posted_at || a.created_at || 0).getTime();
      const dateB = new Date(b.posted_at || b.created_at || 0).getTime();
      return dateB - dateA;
    }
  });

  if (countBadge) {
    countBadge.innerText = `- ${sorted.length}`;
  }

  const visibleJobs = sorted.slice(0, arovaCardLimit);

  if (visibleJobs.length === 0) {
    const emptyMsg = arovaStatusFilter === "applied" 
      ? "Aucune candidature n'a encore été envoyée pour cette sélection."
      : "Aucune offre trouvée pour cette sélection.";
    rowsContainer.innerHTML = `
      <div style="text-align:center; padding: 36px 12px; font-size:14px; font-weight:600; opacity:0.75;">
        ${emptyMsg}
      </div>
    `;
    if (loadMoreBtn) loadMoreBtn.style.display = "none";
    return;
  }

  rowsContainer.innerHTML = visibleJobs.map(job => {
    const isApplied = job.status === "applied";
    let timeLabel = formatRelativeTime(job.posted_at || job.created_at);
    if (isApplied && job.applied_at) {
      timeLabel = `<span style="color:#34d399; font-weight:600;"><i class="fa-solid fa-check"></i> Envoyée ${formatRelativeTime(job.applied_at)}</span>`;
    }

    const locClean = (job.location || "France").replace(/,/g, "").trim();
    const isEasy = (job.is_easy_apply !== 0 && job.is_easy_apply !== false);
    
    // Match score pill
    const score = job.match_score || 60;
    let pillClass = "normal";
    if (score >= 95) pillClass = "exceptional";
    else if (score >= 85) pillClass = "high";
    else if (score >= 70) pillClass = "medium";
    const scorePill = `<span class="arova-match-pill ${pillClass}">${score}% MATCH</span>`;
    const appliedPill = isApplied ? `<span class="arova-badge-applied"><i class="fa-solid fa-circle-check"></i> Postulée</span>` : "";

    // Extract skill tags from match_reason if available
    let skillChipsHtml = "";
    if (job.match_reason && job.match_reason.includes("(") && job.match_reason.includes(")")) {
      const inside = job.match_reason.split("(")[1].split(")")[0];
      const tags = inside.split(",").map(t => t.trim()).filter(Boolean);
      skillChipsHtml = tags.slice(0, 3).map(t => `<span class="arova-skill-chip">${escapeHtml(t)}</span>`).join("");
    }

    const scopeParts = [
      job.company,
      locClean,
      isEasy ? "1 CLIC" : "DIRECT"
    ].filter(Boolean);

    return `
      <div class="arova-row-item ${isApplied ? 'row-is-applied' : ''}" data-job-id="${job.id}" title="${escapeHtml(job.match_reason || 'Cliquer pour voir le détail et postuler')}">
        <div class="arova-row-left">
          <div class="arova-row-jobtitle">${escapeHtml(job.job_title)}</div>
          <div class="arova-row-scope">
            ${scorePill}
            ${appliedPill}
            <span>${escapeHtml(scopeParts.join(" • ").toUpperCase())}</span>
            ${skillChipsHtml}
          </div>
        </div>
        <div class="arova-row-right">
          <span class="arova-row-year">${timeLabel}</span>
          ${isApplied 
            ? `<span class="arova-row-quick-apply-btn applied"><i class="fa-solid fa-check"></i> Postulé</span>` 
            : `<button type="button" class="arova-row-quick-apply-btn" data-apply-id="${job.id}" title="Postuler immédiatement en 1 Clic à cette offre"><i class="fa-solid fa-bolt"></i> 1 Clic</button>`
          }
          <span class="arova-row-arrow">→</span>
        </div>
      </div>
    `;
  }).join("");

  // Direct 1-Click apply on row button
  rowsContainer.querySelectorAll(".arova-row-quick-apply-btn[data-apply-id]").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const jobId = parseInt(btn.getAttribute("data-apply-id"), 10);
      btn.classList.add("loading");
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Envoi...';
      btn.disabled = true;
      try {
        await handleApply(jobId, btn);
      } finally {
        renderArovaCardRows();
        updateBatchCounts();
      }
    });
  });

  // Clicking an item opens the side peek drawer with 1-Click apply!
  rowsContainer.querySelectorAll(".arova-row-item").forEach(item => {
    item.addEventListener("click", () => {
      const jId = parseInt(item.getAttribute("data-job-id"), 10);
      const targetJob = allJobs.find(j => j.id === jId);
      if (targetJob) {
        openSidePeek(targetJob);
      }
    });
  });

  if (loadMoreBtn) {
    if (sorted.length > arovaCardLimit) {
      loadMoreBtn.style.display = "block";
      loadMoreBtn.innerText = `Load more ••• (${sorted.length - arovaCardLimit} de plus)`;
    } else {
      loadMoreBtn.style.display = "none";
    }
  }
}

function setupArovaExperience() {
  const floatingCard = document.getElementById("arova-floating-card");
  const cardWidget = document.getElementById("arova-card-widget");
  const btnCloseCard = document.getElementById("btn-close-arova-card");
  const btnToggleSearch = document.getElementById("btn-toggle-arova-search");
  const searchRow = document.getElementById("arova-card-search-row");
  const searchInput = document.getElementById("arova-card-search-input");
  const btnClearSearch = document.getElementById("btn-clear-arova-search");
  const btnToggleTable = document.getElementById("btn-toggle-table-mode");
  const loadMoreBtn = document.getElementById("btn-arova-load-more");

  const sheetOverlay = document.getElementById("candidatures-sheet-overlay");
  const btnCloseSheet = document.getElementById("btn-close-candidatures-sheet");
  const sheetPlatformDot = document.getElementById("sheet-platform-dot");
  const sheetPlatformTitle = document.getElementById("sheet-platform-title");

  const drawerBackdrop = document.getElementById("studio-drawer-backdrop");
  const drawerEl = document.getElementById("studio-menu-drawer");
  const btnCloseDrawer = document.getElementById("btn-close-menu-drawer");
  const btnTopMenu = document.getElementById("btn-top-menu");
  const btnDockMenu = document.getElementById("btn-dock-menu");

  const secondaryOverlay = document.getElementById("secondary-sheet-overlay");
  const btnCloseSecondary = document.getElementById("btn-close-secondary-sheet");
  const secondaryTitle = document.getElementById("secondary-sheet-title");

  // Helper: Open Arova Editorial Card with distinct platform color theme & optional status filter
  window.openArovaCard = function(platformKey, statusFilter) {
    selectedPlatform = platformKey !== undefined ? platformKey : "";
    arovaStatusFilter = statusFilter !== undefined ? statusFilter : "";
    arovaCardLimit = 8; // Reset display count on platform switch
    arovaCardSearch = "";
    if (searchInput) searchInput.value = "";
    if (searchRow) searchRow.style.display = "none";

    // Sync status filter tabs in card header
    document.querySelectorAll(".arova-status-tab-btn").forEach(b => {
      b.classList.toggle("active", (b.getAttribute("data-arova-status") || "") === arovaStatusFilter);
    });

    const meta = getPlatformMeta(selectedPlatform);

    if (cardWidget) {
      // Keep card serene obsidian dark glass across all platform views
      cardWidget.classList.remove("arova-theme-red", "arova-theme-blue", "arova-theme-green", "arova-theme-colored", "arova-theme-emerald");
      cardWidget.classList.add("arova-theme-black");
      cardWidget.style.backgroundColor = "";
      cardWidget.style.color = "";
      cardWidget.style.borderColor = "";
    }

    // Sync dock button active state
    document.querySelectorAll(".arova-cta-btn").forEach(btn => {
      const btnPlat = btn.getAttribute("data-dock-platform");
      if (btn.id === "btn-dock-applied") {
        btn.classList.toggle("active", arovaStatusFilter === "applied");
      } else if (btnPlat !== null) {
        btn.classList.toggle("active", btnPlat === selectedPlatform && arovaStatusFilter === "");
      }
    });

    renderArovaCardRows();
    updateBatchCounts();

    // Close full table sheet and menu if open
    if (sheetOverlay) sheetOverlay.classList.remove("open");
    closeStudioDrawer();

    if (floatingCard) {
      floatingCard.classList.add("open");
    }
  };

  // Inline card status filter tabs
  document.querySelectorAll(".arova-status-tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".arova-status-tab-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      arovaStatusFilter = btn.getAttribute("data-arova-status") || "";
      arovaCardLimit = 8;
      renderArovaCardRows();
    });
  });

  // Bottom dock Applied CTA
  const btnDockApplied = document.getElementById("btn-dock-applied");
  if (btnDockApplied) {
    btnDockApplied.addEventListener("click", () => {
      openZenTable("", "applied");
    });
  }

  // Drawer View Applied Button
  const btnDrawerViewApplied = document.getElementById("btn-drawer-view-applied");
  if (btnDrawerViewApplied) {
    btnDrawerViewApplied.addEventListener("click", () => {
      closeStudioDrawer();
      openZenTable("", "applied");
    });
  }

  window.closeArovaCard = function() {
    if (floatingCard) floatingCard.classList.remove("open");
    document.querySelectorAll(".arova-cta-btn").forEach(btn => btn.classList.remove("active"));
  };

  // Helper: Open / close Zen table workbench
  window.openZenTable = async function(platformKey, statusFilter) {
    selectedPlatform = platformKey !== undefined ? platformKey : "";
    selectedStatus = statusFilter !== undefined ? statusFilter : "";

    // When viewing applied candidatures, ensure clean display without conflicting 1-click or search filters
    if (selectedStatus === "applied") {
      selectedPlatform = platformKey || "";
      filterOnly1Click = false;
      const chip1Click = document.getElementById("filter-chip-1click");
      if (chip1Click) chip1Click.classList.remove("active");

      // Verify all applied jobs are in memory; fetch if missing
      const inMemApplied = allJobs.filter(j => j.status === "applied");
      if (inMemApplied.length === 0) {
        try {
          const r = await fetch('/api/applications?status=applied&limit=500');
          const data = await r.json();
          if (data && data.length > 0) {
            data.forEach(aj => {
              const idx = allJobs.findIndex(j => j.id === aj.id);
              if (idx >= 0) allJobs[idx] = aj;
              else allJobs.push(aj);
            });
          }
        } catch (err) {
          console.warn("Could not fetch applied applications:", err);
        }
      }
    }

    const workbench = document.getElementById("steady-workbench");
    const calmState = document.getElementById("zen-calm-state");
    const activeTitle = document.getElementById("workbench-active-title");

    // Close cards and drawers
    closeArovaCard();
    closeStudioDrawer();

    // Show workbench with smooth appearance and platform-specific color theme
    if (workbench) {
      workbench.style.display = "flex";
      workbench.classList.remove("zen-appear", "theme-ft", "theme-li", "theme-ind", "theme-applied", "theme-all");
      if (selectedStatus === "applied") {
        workbench.classList.add("theme-applied");
      } else if (selectedPlatform === "francetravail") {
        workbench.classList.add("theme-ft");
      } else if (selectedPlatform === "linkedin") {
        workbench.classList.add("theme-li");
      } else if (selectedPlatform === "indeed") {
        workbench.classList.add("theme-ind");
      } else {
        workbench.classList.add("theme-all");
      }
      void workbench.offsetWidth;
      workbench.classList.add("zen-appear");
    }
    if (calmState) {
      calmState.style.display = "none";
    }

    // Update active pill styling
    document.querySelectorAll(".zen-plat-pill").forEach(pill => {
      const pillPlat = pill.getAttribute("data-platform");
      const pillStatus = pill.getAttribute("data-status-filter");

      if (pillStatus === "applied" || pill.id === "btn-plat-applied") {
        pill.classList.toggle("active", selectedStatus === "applied");
      } else if (pillPlat !== null) {
        pill.classList.toggle("active", pillPlat === selectedPlatform && selectedStatus === "");
      }
    });

    // Update active status chips
    document.querySelectorAll(".steady-status-chip").forEach(chip => {
      const chipStatus = chip.getAttribute("data-status-tab") || "";
      chip.classList.toggle("active", chipStatus === selectedStatus);
    });

    // Set friendly dynamic title
    if (activeTitle) {
      if (selectedStatus === "applied") {
        const countApplied = allJobs.filter(j => j.status === "applied").length;
        activeTitle.innerHTML = `<i class="fa-solid fa-circle-check" style="color:#059669;margin-right:8px;"></i> Candidatures postulées (${countApplied})`;
      } else if (selectedPlatform === "francetravail") {
        activeTitle.innerHTML = `<span class="steady-dot ft" style="display:inline-block;margin-right:8px;"></span> France Travail`;
      } else if (selectedPlatform === "linkedin") {
        activeTitle.innerHTML = `<span class="steady-dot li" style="display:inline-block;margin-right:8px;"></span> LinkedIn`;
      } else if (selectedPlatform === "indeed") {
        activeTitle.innerHTML = `<span class="steady-dot ind" style="display:inline-block;margin-right:8px;"></span> Indeed`;
      } else {
        activeTitle.innerHTML = `<i class="fa-solid fa-layer-group" style="color:#0f172a;margin-right:8px;"></i> Toutes les opportunités`;
      }
    }

    renderJobsTable();

    // Scroll smoothly down to the workbench
    if (workbench) {
      setTimeout(() => {
        workbench.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 40);
    }
  };

  window.closeZenTable = function() {
    const workbench = document.getElementById("steady-workbench");
    const calmState = document.getElementById("zen-calm-state");

    if (workbench) {
      workbench.style.display = "none";
      workbench.classList.remove("theme-ft", "theme-li", "theme-ind", "theme-applied", "theme-all");
    }
    if (calmState) {
      calmState.style.display = "flex";
    }

    // Reset active platform/status selection
    selectedPlatform = "";
    selectedStatus = "";

    // Deactivate all pills
    document.querySelectorAll(".zen-plat-pill").forEach(pill => {
      pill.classList.remove("active");
    });

    // Smooth scroll back up to platform tabs
    const hub = document.getElementById("zen-platform-hub");
    if (hub) {
      hub.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };

  // Helper: Open full table / focus Steady workbench
  window.openCandidaturesSheet = function(platformKey) {
    openZenTable(platformKey, "");
  };

  window.closeCandidaturesSheet = function() {
    closeZenTable();
    if (sheetOverlay) sheetOverlay.classList.remove("open");
  };

  // Render dynamic dock platform buttons & sheet tabs
  renderDynamicDockPlatforms();

  // Card Controls
  if (btnCloseCard) btnCloseCard.addEventListener("click", closeArovaCard);

  if (btnToggleSearch && searchRow && searchInput) {
    btnToggleSearch.addEventListener("click", () => {
      const isVisible = searchRow.style.display !== "none";
      searchRow.style.display = isVisible ? "none" : "flex";
      if (!isVisible) searchInput.focus();
    });
  }

  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      arovaCardSearch = e.target.value.toLowerCase().trim();
      renderArovaCardRows();
    });
  }

  if (btnClearSearch && searchInput) {
    btnClearSearch.addEventListener("click", () => {
      searchInput.value = "";
      arovaCardSearch = "";
      renderArovaCardRows();
    });
  }

  // Toggle Table Mode button inside Card Header -> opens full table sheet
  if (btnToggleTable) {
    btnToggleTable.addEventListener("click", () => {
      openCandidaturesSheet(selectedPlatform);
    });
  }

  // Load more button inside card
  if (loadMoreBtn) {
    loadMoreBtn.addEventListener("click", () => {
      arovaCardLimit += 8;
      renderArovaCardRows();
    });
  }

  // Sheet Header Tabs switch
  document.querySelectorAll(".sheet-plat-btn[data-sheet-platform]").forEach(btn => {
    btn.addEventListener("click", () => {
      const plat = btn.getAttribute("data-sheet-platform") || "";
      openCandidaturesSheet(plat);
    });
  });

  // Close sheet events
  if (btnCloseSheet) btnCloseSheet.addEventListener("click", closeCandidaturesSheet);
  if (sheetOverlay) {
    sheetOverlay.addEventListener("click", (e) => {
      if (e.target === sheetOverlay) closeCandidaturesSheet();
    });
  }

  // Helper: Open / Close Studio Menu Drawer
  window.openStudioDrawer = function() {
    closeArovaCard();
    closeCandidaturesSheet();
    if (drawerBackdrop) drawerBackdrop.classList.add("open");
    if (drawerEl) drawerEl.classList.add("open");
    if (btnTopMenu) btnTopMenu.classList.add("active");
  };

  window.closeStudioDrawer = function() {
    if (drawerBackdrop) drawerBackdrop.classList.remove("open");
    if (drawerEl) drawerEl.classList.remove("open");
    if (btnTopMenu) btnTopMenu.classList.remove("active");
  };

  if (btnTopMenu) {
    btnTopMenu.addEventListener("click", (e) => {
      e.stopPropagation();
      if (drawerEl && drawerEl.classList.contains("open")) {
        closeStudioDrawer();
      } else {
        openStudioDrawer();
      }
    });
  }
  if (btnDockMenu) btnDockMenu.addEventListener("click", openStudioDrawer);
  if (btnCloseDrawer) btnCloseDrawer.addEventListener("click", closeStudioDrawer);
  if (drawerBackdrop) drawerBackdrop.addEventListener("click", closeStudioDrawer);

  // Helper: Secondary Sheet (CV Viewer, Plateformes, Critères)
  window.openSecondarySheet = function(tabId) {
    closeStudioDrawer();
    closeCandidaturesSheet();
    closeArovaCard();

    document.querySelectorAll(".notion-view-page").forEach(p => p.classList.remove("active"));
    const targetPage = document.getElementById(tabId);
    if (targetPage) targetPage.classList.add("active");

    // Sync Steady Top Nav buttons
    document.querySelectorAll(".steady-nav-btn").forEach(b => b.classList.remove("active"));
    if (tabId === "tab-cv") {
      const btn = document.getElementById("btn-nav-cv");
      if (btn) btn.classList.add("active");
    } else if (tabId === "tab-platforms") {
      const btn = document.getElementById("btn-nav-platforms");
      if (btn) btn.classList.add("active");
    } else if (tabId === "tab-settings") {
      const btn = document.getElementById("btn-nav-criteria");
      if (btn) btn.classList.add("active");
    }

    const titles = {
      "tab-cv": '<i class="fa-solid fa-file-pdf" style="color:#ef4444;"></i> <span>Visualisateur & Bibliothèque de CV</span>',
      "tab-platforms": '<i class="fa-solid fa-key" style="color:#38bdf8;"></i> <span>Connexions & Sessions des Plateformes</span>',
      "tab-settings": '<i class="fa-solid fa-sliders" style="color:#a855f7;"></i> <span>Paramètres de Recherche & Veille</span>'
    };

    if (secondaryTitle && titles[tabId]) {
      secondaryTitle.innerHTML = titles[tabId];
    }

    if (secondaryOverlay) secondaryOverlay.classList.add("open");
  };

  window.closeSecondarySheet = function() {
    if (secondaryOverlay) secondaryOverlay.classList.remove("open");
    // Restore Dashboard nav tab as active
    document.querySelectorAll(".steady-nav-btn").forEach(b => b.classList.remove("active"));
    const btnDash = document.getElementById("btn-nav-dashboard");
    if (btnDash) btnDash.classList.add("active");
  };

  if (btnCloseSecondary) btnCloseSecondary.addEventListener("click", closeSecondarySheet);
  if (secondaryOverlay) {
    secondaryOverlay.addEventListener("click", (e) => {
      if (e.target === secondaryOverlay) closeSecondarySheet();
    });
  }

  // Drawer Action Triggers
  const btnDrawerCV = document.getElementById("btn-drawer-open-cv");
  if (btnDrawerCV) btnDrawerCV.addEventListener("click", () => openSecondarySheet("tab-cv"));

  const btnDrawerPlat = document.getElementById("btn-drawer-open-platforms");
  if (btnDrawerPlat) btnDrawerPlat.addEventListener("click", () => openSecondarySheet("tab-platforms"));

  const btnDrawerCrit = document.getElementById("btn-drawer-open-criteria");
  if (btnDrawerCrit) btnDrawerCrit.addEventListener("click", () => openSecondarySheet("tab-settings"));

  // Simplified Navigation Tiles inside Studio Drawer
  const tileTable = document.getElementById("menu-tile-table");
  if (tileTable) tileTable.addEventListener("click", () => {
    closeStudioDrawer();
    openCandidaturesSheet(selectedPlatform);
  });

  const tileCV = document.getElementById("menu-tile-cv");
  if (tileCV) tileCV.addEventListener("click", () => openSecondarySheet("tab-cv"));

  const tilePlat = document.getElementById("menu-tile-platforms");
  if (tilePlat) tilePlat.addEventListener("click", () => openSecondarySheet("tab-platforms"));

  const tileCrit = document.getElementById("menu-tile-criteria");
  if (tileCrit) tileCrit.addEventListener("click", () => openSecondarySheet("tab-settings"));

  const tileProfile = document.getElementById("menu-tile-profile");
  if (tileProfile) tileProfile.addEventListener("click", () => {
    closeStudioDrawer();
    const modalProfile = document.getElementById("profile-analyze-modal");
    if (modalProfile) modalProfile.style.display = "flex";
  });

  const tileApplied = document.getElementById("menu-tile-applied");
  if (tileApplied) tileApplied.addEventListener("click", () => {
    closeStudioDrawer();
    openZenTable("", "applied");
  });

  const btnKillDrawer = document.getElementById("btn-kill-all-browsers-drawer");
  const btnKillMain = document.getElementById("btn-kill-all-browsers");
  if (btnKillDrawer && btnKillMain) {
    btnKillDrawer.addEventListener("click", () => btnKillMain.click());
  }

  // Drawer & Dock Scan Action
  const btnDockScan = document.getElementById("btn-dock-scan");
  if (btnDockScan) {
    btnDockScan.addEventListener("click", async () => {
      btnDockScan.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> <span>Scan...</span>';
      btnDockScan.disabled = true;
      try {
        const res = await fetch("/api/jobs/sync-realtime", { method: "POST" });
        const data = await res.json();
        showToast(`🎉 Scan terminé : ${data.new_jobs_detected || 0} nouvelles offres trouvées en direct !`, "success");
        await loadJobs();
      } catch (err) {
        showToast("Erreur lors du scan : " + err.message, "error");
      } finally {
        btnDockScan.innerHTML = '<i class="fa-solid fa-bolt"></i> <span>Scanner</span>';
        btnDockScan.disabled = false;
      }
    });
  }

  // Drawer banner triggers
  const btnDrawerUpload = document.getElementById("btn-drawer-upload-banner");
  if (btnDrawerUpload) {
    btnDrawerUpload.addEventListener("click", () => {
      if (typeof window.closeStudioDrawer === "function") window.closeStudioDrawer();
      if (typeof window.openBannerModal === "function") window.openBannerModal();
    });
  }

  const btnDrawerReset = document.getElementById("btn-drawer-reset-banner");
  if (btnDrawerReset) {
    btnDrawerReset.addEventListener("click", () => {
      const btnReset = document.getElementById("btn-reset-banner-default");
      if (btnReset) btnReset.click();
    });
  }

  // Brand click in top bar returns home (closes all sheets/drawers)
  const brandHome = document.getElementById("btn-brand-home");
  if (brandHome) {
    brandHome.addEventListener("click", () => {
      closeArovaCard();
      closeCandidaturesSheet();
      closeStudioDrawer();
      closeSecondarySheet();
    });
  }

  // Keyboard shortcut: Escape closes all open modals / sheets
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      const modalAdd = document.getElementById("modal-add-platform");
      if (modalAdd && modalAdd.style.display !== "none") {
        modalAdd.style.display = "none";
      }
      closeArovaCard();
      closeCandidaturesSheet();
      closeStudioDrawer();
      closeSecondarySheet();
    }
  });

  // Visual Theme Toggle (Dark Studio vs Arova Cream Gallery)
  const themeToggle = document.getElementById("btn-arova-theme-toggle");
  const savedTheme = localStorage.getItem("arova_theme");
  if (savedTheme === "cream") {
    document.body.classList.add("arova-gallery-theme");
  }

  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      document.body.classList.toggle("arova-gallery-theme");
      const isCream = document.body.classList.contains("arova-gallery-theme");
      localStorage.setItem("arova_theme", isCream ? "cream" : "dark");
      if (typeof window.__updateThreeTheme === "function") {
        window.__updateThreeTheme(isCream);
      }
      showToast(isCream ? "🎨 Thème Arova Gallery (Crème) activé" : "🌙 Thème Dark Studio activé", "info");
    });
  }

  // Setup Profile & IA Matching Engine
  setupProfileAndMatchingExperience();
  setupBatchApplyExperience();
}

/* ==========================================================
   PROFILE SHOWCASE & IA MATCHING INTERACTION ENGINE
========================================================== */
function setupProfileAndMatchingExperience() {
  const btnSortRel = document.getElementById("btn-arova-sort-relevance");
  const btnSortDate = document.getElementById("btn-arova-sort-date");

  function updateSortButtons() {
    if (btnSortRel) btnSortRel.classList.toggle("active", arovaSortMode === "relevance");
    if (btnSortDate) btnSortDate.classList.toggle("active", arovaSortMode === "date");
  }

  if (btnSortRel) {
    btnSortRel.addEventListener("click", () => {
      arovaSortMode = "relevance";
      updateSortButtons();
      renderArovaCardRows();
      renderJobsTable();
      showToast("🎯 Tri par pertinence profil (Score %)", "info");
    });
  }

  if (btnSortDate) {
    btnSortDate.addEventListener("click", () => {
      arovaSortMode = "date";
      updateSortButtons();
      renderArovaCardRows();
      renderJobsTable();
      showToast("⏱️ Tri par date la plus récente", "info");
    });
  }

  // Profile Drawer elements
  const profileModal = document.getElementById("profile-analyze-modal");
  const btnOpenAnalyze = document.getElementById("btn-open-analyze-profile-modal");
  const btnCloseAnalyze = document.getElementById("btn-close-profile-modal");
  const btnCancelAnalyze = document.getElementById("btn-cancel-profile-modal");
  const formAnalyze = document.getElementById("form-profile-analyzer");
  const btnRescore = document.getElementById("btn-drawer-rescore-jobs");

  async function loadProfileShowcase() {
    try {
      const res = await fetch("/api/profile/current");
      if (!res.ok) return;
      const data = await res.json();
      const p = data.profile || {};

      const elName = document.getElementById("drawer-profile-fullname");
      const elTitle = document.getElementById("drawer-profile-title");
      const elInitials = document.getElementById("drawer-profile-initials");
      const elLinkPort = document.getElementById("drawer-link-portfolio");
      const elLinkLi = document.getElementById("drawer-link-linkedin");
      const elLinkGh = document.getElementById("drawer-link-github");
      const elTags = document.getElementById("drawer-profile-skills-tags");

      if (elName) elName.innerText = `${p.first_name || ""} ${p.last_name || ""}`.trim() || "Eliot Hantute";
      if (elTitle) elTitle.innerText = p.current_title || "Creative Front-End Developer & UI Designer";
      if (elInitials) {
        const i1 = (p.first_name || "E")[0];
        const i2 = (p.last_name || "H")[0];
        elInitials.innerText = `${i1}${i2}`.toUpperCase();
      }

      if (elLinkPort && p.portfolio_url) {
        elLinkPort.href = p.portfolio_url;
        elLinkPort.innerHTML = `<i class="fa-solid fa-globe"></i> ${p.portfolio_url.replace(/^https?:\/\//, "").replace(/\/$/, "")}`;
      }
      if (elLinkLi && p.linkedin_url) {
        elLinkLi.href = p.linkedin_url;
      }
      if (elLinkGh && p.github_url) {
        elLinkGh.href = p.github_url;
      }

      if (elTags && Array.isArray(p.skills)) {
        const highlights = ["Three.js", "WebGL", "React 19", "React", "TypeScript", "Tailwind CSS", "Figma", "UI/UX Design", "Next.js", "GSAP"];
        elTags.innerHTML = p.skills.slice(0, 12).map(sk => {
          const isHigh = highlights.some(h => sk.toLowerCase().includes(h.toLowerCase()));
          return `<span class="skill-tag ${isHigh ? 'highlight' : ''}">${escapeHtml(sk)}</span>`;
        }).join("");
      }
    } catch (err) {
      console.warn("Could not load profile showcase:", err);
    }
  }

  // Open modal
  if (btnOpenAnalyze) {
    btnOpenAnalyze.addEventListener("click", () => {
      if (profileModal) {
        profileModal.style.display = "flex";
        const prog = document.getElementById("analyze-progress-box");
        if (prog) prog.style.display = "none";
      }
    });
  }

  function closeProfileModal() {
    if (profileModal) profileModal.style.display = "none";
  }

  if (btnCloseAnalyze) btnCloseAnalyze.addEventListener("click", closeProfileModal);
  if (btnCancelAnalyze) btnCancelAnalyze.addEventListener("click", closeProfileModal);
  if (profileModal) {
    profileModal.addEventListener("click", (e) => {
      if (e.target === profileModal) closeProfileModal();
    });
  }

  // Form submit: analyze profile
  if (formAnalyze) {
    formAnalyze.addEventListener("submit", async (e) => {
      e.preventDefault();
      const portfolioUrl = document.getElementById("input-profile-portfolio")?.value || "";
      const linkedinUrl = document.getElementById("input-profile-linkedin")?.value || "";
      const resumeSelect = document.getElementById("select-profile-resume")?.value || "";
      const notes = document.getElementById("input-profile-notes")?.value || "";

      const progBox = document.getElementById("analyze-progress-box");
      const submitBtn = document.getElementById("btn-run-profile-analysis");
      const step1 = document.getElementById("prog-step-1");
      const step2 = document.getElementById("prog-step-2");
      const step3 = document.getElementById("prog-step-3");
      const step4 = document.getElementById("prog-step-4");

      if (progBox) progBox.style.display = "flex";
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Analyse en cours...';
      }

      function setStep(stepEl, state) {
        if (!stepEl) return;
        stepEl.classList.remove("active", "done");
        if (state === "active") {
          stepEl.classList.add("active");
          const ico = stepEl.querySelector("i");
          if (ico) ico.className = "fa-solid fa-circle-notch fa-spin";
        } else if (state === "done") {
          stepEl.classList.add("done");
          const ico = stepEl.querySelector("i");
          if (ico) ico.className = "fa-solid fa-circle-check";
        }
      }

      setStep(step1, "active");

      try {
        setTimeout(() => { setStep(step1, "done"); setStep(step2, "active"); }, 500);
        setTimeout(() => { setStep(step2, "done"); setStep(step3, "active"); }, 1200);

        const res = await fetch("/api/profile/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            portfolio_url: portfolioUrl,
            linkedin_url: linkedinUrl,
            resume_filename: resumeSelect,
            additional_notes: notes,
          })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.message || "Erreur lors de l'analyse");

        setStep(step3, "done");
        setStep(step4, "active");
        setTimeout(() => setStep(step4, "done"), 400);

        setTimeout(async () => {
          showToast(`⚡ Profil analysé avec succès ! ${data.rescore_stats?.high_matches || 0} offres recommandées.`, "success");
          closeProfileModal();
          await loadProfileShowcase();
          await loadJobs();
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fa-solid fa-bolt"></i> Lancer l\'analyse & calibrer les offres';
          }
        }, 800);

      } catch (err) {
        showToast("Erreur analyse de profil : " + err.message, "error");
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = '<i class="fa-solid fa-bolt"></i> Lancer l\'analyse & calibrer les offres';
        }
      }
    });
  }

  // Rescore button in drawer
  if (btnRescore) {
    btnRescore.addEventListener("click", async () => {
      btnRescore.disabled = true;
      btnRescore.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Recalcul...';
      try {
        const res = await fetch("/api/jobs/rescore", { method: "POST" });
        const data = await res.json();
        showToast(data.message || "Recalcul de pertinence terminé !", "success");
        await loadJobs();
      } catch (err) {
        showToast("Erreur recalcul : " + err.message, "error");
      } finally {
        btnRescore.disabled = false;
        btnRescore.innerHTML = '<i class="fa-solid fa-crosshairs"></i> Recalculer la pertinence';
      }
    });
  }

  // Initial load
  loadProfileShowcase();
}

/* ==========================================================
   BATCH APPLY TO ALL JOBS EXPERIENCE
========================================================== */
function setupBatchApplyExperience() {
  const modal = document.getElementById("modal-batch-apply");
  const btnClose = document.getElementById("btn-close-batch-modal");
  const btnCancel = document.getElementById("btn-cancel-batch");
  const btnStart = document.getElementById("btn-start-batch-action");
  const btnStop = document.getElementById("btn-stop-batch-action");

  const btnArovaHead = document.getElementById("btn-arova-head-apply-all");
  const btnArovaFoot = document.getElementById("btn-arova-foot-apply-all");
  const btnDrawerMaster = document.getElementById("btn-drawer-apply-all-master");

  let batchPollInterval = null;
  let currentBatchPlatform = "";

  function closeModal() {
    if (modal) modal.style.display = "none";
  }

  if (btnClose) btnClose.addEventListener("click", closeModal);
  if (btnCancel) btnCancel.addEventListener("click", closeModal);
  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeModal();
    });
  }

  async function refreshBatchModalStats(plat) {
    currentBatchPlatform = (plat !== undefined && plat !== null) ? plat : "";
    try {
      const url = currentBatchPlatform ? `/api/jobs/unapplied-stats?platform=${encodeURIComponent(currentBatchPlatform)}` : "/api/jobs/unapplied-stats";
      const res = await fetch(url);
      const stats = await res.json();

      const elTotal = document.getElementById("batch-stat-total");
      const elHigh = document.getElementById("batch-stat-high");
      const elPlat = document.getElementById("batch-stat-platform");
      const elScopeAll = document.getElementById("batch-scope-count-all");
      const elScopeHigh = document.getElementById("batch-scope-count-high");

      const meta = getPlatformMeta(currentBatchPlatform);
      const platLabel = currentBatchPlatform ? (meta ? meta.name : currentBatchPlatform) : "Tout le catalogue";

      if (elTotal) elTotal.innerText = stats.total_unapplied || 0;
      if (elHigh) elHigh.innerText = stats.high_match_unapplied || 0;
      if (elPlat) elPlat.innerText = platLabel;
      if (elScopeAll) elScopeAll.innerText = stats.total_unapplied || 0;
      if (elScopeHigh) elScopeHigh.innerText = stats.high_match_unapplied || 0;

      // Update active pill button
      document.querySelectorAll(".batch-plat-pill").forEach(p => {
        p.classList.toggle("active", (p.getAttribute("data-batch-plat") || "") === currentBatchPlatform);
      });

      // Show/hide execution mode selector depending on platform selection
      const modeField = document.getElementById("batch-execution-mode-field");
      if (modeField) {
        modeField.style.display = (!currentBatchPlatform || currentBatchPlatform === "all") ? "block" : "none";
      }

      // Update start button text with specific platform name and mode
      if (btnStart) {
        if (!currentBatchPlatform || currentBatchPlatform === "all") {
          btnStart.innerHTML = `<i class="fa-solid fa-bolt"></i> Lancer en simultané (Toutes plateformes : ${stats.total_unapplied || 0})`;
        } else {
          btnStart.innerHTML = `<i class="fa-solid fa-paper-plane"></i> Lancer les candidatures ${meta ? meta.name : currentBatchPlatform} (${stats.total_unapplied || 0})`;
        }
      }

      // Update pill badge counts from breakdown if available
      if (stats.breakdown) {
        const pAll = document.getElementById("batch-pill-count-all");
        const pFt = document.getElementById("batch-pill-count-ft");
        const pLi = document.getElementById("batch-pill-count-li");
        const pInd = document.getElementById("batch-pill-count-ind");
        if (pAll && stats.breakdown.all) pAll.innerText = stats.breakdown.all.unapplied || 0;
        if (pFt && stats.breakdown.francetravail) pFt.innerText = stats.breakdown.francetravail.unapplied || 0;
        if (pLi && stats.breakdown.linkedin) pLi.innerText = stats.breakdown.linkedin.unapplied || 0;
        if (pInd && stats.breakdown.indeed) pInd.innerText = stats.breakdown.indeed.unapplied || 0;
      }
      await checkLinkedInSessionNotice();
    } catch (e) {
      console.warn("Error refreshing batch modal stats:", e);
    }
  }

  // Wire execution mode cards
  document.querySelectorAll(".batch-mode-card").forEach(card => {
    card.addEventListener("click", () => {
      document.querySelectorAll(".batch-mode-card").forEach(c => c.classList.remove("active"));
      card.classList.add("active");
      const radio = card.querySelector("input[name='batch-execution-mode']");
      if (radio) radio.checked = true;
    });
  });

  // Wire platform selector pills in batch modal
  document.querySelectorAll(".batch-plat-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      const targetPlat = pill.getAttribute("data-batch-plat") || "";
      refreshBatchModalStats(targetPlat);
    });
  });

  window.openBatchApplyModal = async function(platformScope) {
    const plat = (platformScope !== undefined && platformScope !== null) ? platformScope : (selectedPlatform || "");
    await refreshBatchModalStats(plat);

    const elResumeName = document.getElementById("batch-modal-resume-name");
    if (elResumeName && activeResumeFilename) {
      elResumeName.innerText = activeResumeFilename;
    }

    await checkCurrentBatchStatus();
    if (modal) modal.style.display = "flex";
  };

  if (btnArovaHead) {
    btnArovaHead.addEventListener("click", (e) => {
      e.stopPropagation();
      openBatchApplyModal(selectedPlatform);
    });
  }

  // Main Screen Header 1-Click Apply Button
  const btnMainQuick = document.getElementById("btn-main-quick-apply");
  if (btnMainQuick) {
    btnMainQuick.addEventListener("click", (e) => {
      e.stopPropagation();
      openBatchApplyModal(selectedPlatform);
    });
  }

  // Floating Bottom Dock 1-Click Apply Button
  const btnDockQuick = document.getElementById("btn-dock-quick-apply");
  if (btnDockQuick) {
    btnDockQuick.addEventListener("click", (e) => {
      e.stopPropagation();
      openBatchApplyModal(selectedPlatform || "");
    });
  }

  if (btnArovaFoot) {
    btnArovaFoot.addEventListener("click", (e) => {
      e.stopPropagation();
      openBatchApplyModal(selectedPlatform);
    });
  }

  document.querySelectorAll(".arova-btn-apply-all-master").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      closeStudioDrawer();
      openBatchApplyModal(selectedPlatform || "");
    });
  });

  async function checkCurrentBatchStatus() {
    try {
      const res = await fetch("/api/jobs/batch-status");
      const status = await res.json();
      updateBatchUIState(status);

      if (status.is_running && !batchPollInterval) {
        batchPollInterval = setInterval(pollBatchStatus, 1500);
      }
    } catch (e) {
      console.warn("Could not check batch status:", e);
    }
  }

  function renderPlatformWorkersProgress(platformsData) {
    const container = document.getElementById("batch-platform-workers-list");
    if (!container || !platformsData) return;

    const platformKeys = ["francetravail", "linkedin", "indeed"];
    let html = "";

    platformKeys.forEach(plat => {
      const w = platformsData[plat];
      if (!w || (w.total === 0 && !w.is_running)) return;

      const meta = getPlatformMeta(plat);
      const platName = meta ? meta.name : plat.toUpperCase();
      const tagClass = (plat === "francetravail") ? "worker-tag-ft" : (plat === "linkedin" ? "worker-tag-li" : "worker-tag-ind");
      const barClass = (plat === "francetravail") ? "bar-ft" : (plat === "linkedin" ? "bar-li" : "bar-ind");
      const p = w.percent || 0;
      const isRunning = w.is_running;
      const isFinished = !isRunning && w.total > 0 && w.current_index >= w.total;

      let statusBadge = "";
      if (isRunning) {
        statusBadge = `<span style="font-size:10.5px; color:#38bdf8; font-weight:700;"><i class="fa-solid fa-circle-notch fa-spin"></i> Actif (${p}%)</span>`;
      } else if (isFinished) {
        statusBadge = `<span style="font-size:10.5px; color:#34d399; font-weight:700;"><i class="fa-solid fa-circle-check"></i> Terminé</span>`;
      } else {
        statusBadge = `<span style="font-size:10.5px; color:#94a3b8;">${p}%</span>`;
      }

      const currentTask = w.current_task || (isRunning ? "Traitement..." : "En attente");
      const successCount = w.success_count || 0;
      const skippedCount = w.skipped_count || 0;
      const failedCount = w.failed_count || 0;

      html += `
        <div class="batch-worker-card ${isRunning ? 'worker-active' : (isFinished ? 'worker-finished' : '')}" data-worker-platform="${plat}">
          <div class="batch-worker-head">
            <div class="batch-worker-plat-title">
              <span class="batch-worker-pill-tag ${tagClass}">${platName}</span>
              <span style="font-size:11px; color:#94a3b8;">${w.current_index || 0}/${w.total || 0} offres</span>
            </div>
            <div style="display:flex; align-items:center; gap:8px;">
              ${statusBadge}
              ${isRunning ? `<button type="button" class="btn-worker-stop" data-stop-platform="${plat}" title="Interrompre ce worker"><i class="fa-solid fa-stop"></i> Arrêter</button>` : ''}
            </div>
          </div>
          <div class="batch-worker-bar-wrap">
            <div class="batch-worker-bar-fill ${barClass}" style="width: ${p}%;"></div>
          </div>
          <div class="batch-worker-details">
            <span class="batch-worker-task-text" title="${currentTask}">${currentTask}</span>
            <div class="batch-worker-stats-row">
              <span style="color:#34d399;" title="Succès"><i class="fa-solid fa-check"></i> ${successCount}</span>
              <span style="color:#fbbf24;" title="Ignorées"><i class="fa-solid fa-forward"></i> ${skippedCount}</span>
              <span style="color:#f87171;" title="Erreurs"><i class="fa-solid fa-xmark"></i> ${failedCount}</span>
            </div>
          </div>
        </div>
      `;
    });

    container.innerHTML = html;

    // Wire per-platform stop buttons
    container.querySelectorAll(".btn-worker-stop").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const p = btn.getAttribute("data-stop-platform");
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
        try {
          await fetch("/api/jobs/stop-batch", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ platform: p })
          });
          showToast(`Arrêt demandé pour ${p.toUpperCase()}`, "info");
        } catch (err) {
          showToast("Erreur arrêt worker: " + err.message, "error");
        }
      });
    });
  }

  function updateBatchUIState(status) {
    const liveSection = document.getElementById("batch-live-progress");
    const bar = document.getElementById("batch-progress-bar");
    const title = document.getElementById("batch-progress-title");
    const pct = document.getElementById("batch-progress-pct");
    const currJob = document.getElementById("batch-progress-curr-job");
    const statSuccess = document.getElementById("batch-stat-success");
    const statSkipped = document.getElementById("batch-stat-skipped");
    const statFailed = document.getElementById("batch-stat-failed");
    const statRemaining = document.getElementById("batch-stat-remaining");
    const statTip = document.getElementById("batch-stat-tip");
    const statTipText = document.getElementById("batch-stat-tip-text");

    // Render per-platform workers
    if (status.platforms) {
      renderPlatformWorkersProgress(status.platforms);
    }

    if (status.is_running) {
      if (liveSection) liveSection.style.display = "flex";
      if (btnStart) btnStart.style.display = "none";
      if (btnStop) btnStop.style.display = "inline-flex";

      const p = status.percent || 0;
      if (bar) bar.style.width = `${p}%`;
      if (pct) pct.innerText = `${p}%`;
      if (title) title.innerText = status.current_task || "Candidatures simultanées en cours...";
      if (currJob) {
        if (status.active_platforms && status.active_platforms.length > 1) {
          currJob.innerText = `⚡ ${status.active_platforms.length} plateformes actives (${status.active_platforms.join(', ')})`;
        } else if (status.current_job_title) {
          currJob.innerText = `${status.current_job_title} chez ${status.current_company} (${(status.current_platform || '').toUpperCase()})`;
        } else {
          currJob.innerText = "Initialisation des workers...";
        }
      }

      // Sync with 3D Particle Progress Bar on the main screen
      if (window.ParticleProgress3D) {
        window.ParticleProgress3D.setProgress(p, status.current_task || "Postulation simultanée en cours...", {
          success_count: status.success_count || 0,
          remaining: Math.max(0, (status.total || 0) - (status.current_index || 0)),
          skipped_count: status.skipped_count || 0,
          total: status.total || 0,
          current_index: status.current_index || 0,
          title: status.current_job_title || null,
          company: status.current_company || null,
          platform: status.current_platform || null
        });
      }

      if (statSuccess) statSuccess.innerText = status.success_count || 0;
      if (statSkipped) statSkipped.innerText = status.skipped_count || 0;
      if (statFailed) statFailed.innerText = status.failed_count || 0;
      const remaining = Math.max(0, (status.total || 0) - (status.current_index || 0));
      if (statRemaining) statRemaining.innerText = remaining;

      if (statTip && statTipText) {
        const reason = status.last_reason || "";
        if (reason.includes("Session") || reason.includes("Authwall")) {
          statTip.style.display = "block";
          statTipText.innerHTML = "<strong>Session requise :</strong> Connectez-vous dans le tiroir <em>Menu &gt; Plateformes &amp; Sessions</em> pour débloquer l'envoi direct.";
        } else if (reason.includes("externe")) {
          statTip.style.display = "block";
          statTipText.innerHTML = "<strong>Redirection externe détectée :</strong> Cette offre redirige vers le portail RH de l'entreprise (non éligible au 1 Clic direct).";
        } else if (reason) {
          statTip.style.display = "block";
          statTipText.innerText = `Note : ${reason}`;
        }
      }
    } else {
      if (btnStart) {
        btnStart.style.display = "inline-flex";
        btnStart.disabled = false;
        const meta = getPlatformMeta(currentBatchPlatform);
        if (!currentBatchPlatform || currentBatchPlatform === "all") {
          btnStart.innerHTML = `<i class="fa-solid fa-bolt"></i> Lancer en simultané (Toutes plateformes)`;
        } else {
          btnStart.innerHTML = `<i class="fa-solid fa-paper-plane"></i> Lancer les candidatures ${meta ? meta.name : currentBatchPlatform}`;
        }
      }
      if (btnStop) btnStop.style.display = "none";

      if (status.total > 0 && status.current_index >= status.total) {
        if (title) title.innerText = status.current_task || "Session terminée avec succès !";
        if (bar) bar.style.width = "100%";
        if (pct) pct.innerText = "100%";
        if (window.ParticleProgress3D) {
          window.ParticleProgress3D.complete(true, `Session terminée : ${status.success_count || 0} candidature(s) validée(s) !`);
        }
      } else if (!status.is_running && status.total === 0) {
        if (liveSection) liveSection.style.display = "none";
      }
    }
  }

  async function pollBatchStatus() {
    try {
      const res = await fetch("/api/jobs/batch-status");
      const status = await res.json();
      updateBatchUIState(status);

      if (!status.is_running) {
        if (batchPollInterval) {
          clearInterval(batchPollInterval);
          batchPollInterval = null;
        }
        if (window.ParticleProgress3D) {
          window.ParticleProgress3D.complete(true, `🎉 Session terminée : ${status.success_count || 0} offre(s) postulée(s) avec succès !`);
        }
        showToast(`🎉 Session terminée : ${status.success_count || 0} offre(s) postulée(s) avec succès !`, "success");
        await loadJobs();
      }
    } catch (e) {
      console.warn("Poll batch status failed:", e);
    }
  }

  // Start Batch Apply Action
  if (btnStart) {
    btnStart.addEventListener("click", async () => {
      const scopeRadio = document.querySelector("input[name='batch-scope']:checked");
      const scopeVal = scopeRadio ? scopeRadio.value : "all";
      const isHighOnly = scopeVal === "high";

      const modeRadio = document.querySelector("input[name='batch-execution-mode']:checked");
      const execMode = modeRadio ? modeRadio.value : "parallel";

      btnStart.disabled = true;
      btnStart.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Initialisation des workers...';

      if (window.ParticleProgress3D) {
        window.ParticleProgress3D.open({
          title: "Candidatures Simultanées par Plateforme",
          company: currentBatchPlatform ? `Plateforme ${currentBatchPlatform}` : "Workers Parallèles Multi-Plateformes",
          platform: currentBatchPlatform || "Simultané",
          mode: "batch"
        });
      }

      try {
        const payload = {
          platform: currentBatchPlatform || null,
          min_score: isHighOnly ? 80 : null,
          mode: execMode,
        };

        const res = await fetch("/api/jobs/apply-all", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.message || "Erreur au lancement");

        showToast(data.message || "Candidatures simultanées par plateforme lancées !", "success");
        closeModal();

        // Start polling
        await checkCurrentBatchStatus();
        if (!batchPollInterval) {
          batchPollInterval = setInterval(pollBatchStatus, 1200);
        }

      } catch (err) {
        showToast("Erreur lancement candidatures : " + err.message, "error");
        btnStart.disabled = false;
        btnStart.innerHTML = '<i class="fa-solid fa-bolt"></i> Lancer les candidatures';
      }
    });
  }

  // Stop Batch Apply Action
  if (btnStop) {
    btnStop.addEventListener("click", async () => {
      btnStop.disabled = true;
      btnStop.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Arrêt...';
      try {
        const res = await fetch("/api/jobs/stop-batch", { method: "POST" });
        const data = await res.json();
        showToast("Arrêt de tous les workers demandé.", "info");
      } catch (err) {
        showToast("Erreur arrêt : " + err.message, "error");
      } finally {
        btnStop.disabled = false;
        btnStop.innerHTML = '<i class="fa-solid fa-hand"></i> Interrompre tout';
      }
    });
  }

  // LinkedIn session notice check
  const authWarning = document.getElementById("batch-auth-warning-linkedin");
  const btnSaveLiAt = document.getElementById("btn-batch-save-li-at");
  const inputQuickLiAt = document.getElementById("input-batch-quick-li-at");
  const btnResetSkipped = document.getElementById("btn-reset-skipped-jobs");

  async function checkLinkedInSessionNotice() {
    if (!authWarning) return;
    try {
      const res = await fetch("/api/platforms/status");
      const data = await res.json();
      const isLiLogged = data.linkedin && data.linkedin.logged_in;
      if (!isLiLogged && (currentBatchPlatform === "linkedin" || !currentBatchPlatform)) {
        authWarning.style.display = "block";
      } else {
        authWarning.style.display = "none";
      }
    } catch (e) {
      authWarning.style.display = "none";
    }
  }

  if (btnSaveLiAt && inputQuickLiAt) {
    btnSaveLiAt.addEventListener("click", async () => {
      const val = inputQuickLiAt.value.trim();
      if (!val) {
        showToast("Veuillez coller votre cookie li_at", "error");
        return;
      }
      btnSaveLiAt.disabled = true;
      btnSaveLiAt.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
      try {
        const res = await fetch("/api/platforms/linkedin/set-cookie", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ li_at: val })
        });
        const data = await res.json();
        if (data.status === "connected") {
          showToast("✓ Connecté à LinkedIn avec succès !", "success");
          if (authWarning) authWarning.style.display = "none";
          inputQuickLiAt.value = "";
        } else {
          showToast(data.message || "Erreur de connexion", "error");
        }
      } catch (err) {
        showToast("Erreur injection cookie : " + err.message, "error");
      } finally {
        btnSaveLiAt.disabled = false;
        btnSaveLiAt.innerHTML = '<i class="fa-solid fa-key"></i> Connecter';
      }
    });
  }

  if (btnResetSkipped) {
    btnResetSkipped.addEventListener("click", async () => {
      btnResetSkipped.disabled = true;
      btnResetSkipped.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Réinitialisation...';
      try {
        const res = await fetch("/api/jobs/reset-skipped", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ platform: currentBatchPlatform || null })
        });
        const data = await res.json();
        showToast(data.message || "Offres réinitialisées avec succès !", "success");
        await refreshBatchModalStats(currentBatchPlatform);
        await loadJobs();
      } catch (err) {
        showToast("Erreur réinitialisation : " + err.message, "error");
      } finally {
        btnResetSkipped.disabled = false;
        btnResetSkipped.innerHTML = '<i class="fa-solid fa-rotate-left"></i> Réinitialiser ignorées';
      }
    });
  }
}

/* ==========================================================
   ONESHOT DAY / NIGHT DUAL THEME ENGINE
========================================================== */
function setupThemeEngine() {
  const btnThemeToggle = document.getElementById("btn-theme-toggle");
  const themeIcon = document.getElementById("theme-toggle-icon");
  const themeText = document.getElementById("theme-toggle-text");

  const drawerToggleTheme = document.getElementById("drawer-toggle-theme");
  const drawerThemeIcon = document.getElementById("drawer-theme-icon");
  const drawerThemeTitle = document.getElementById("drawer-theme-title-text");
  const drawerThemeSub = document.getElementById("drawer-theme-sub-text");

  // Default to Dark Gaming HUD mode unless explicitly saved as light
  const savedTheme = localStorage.getItem("oneshot_theme");
  const initialTheme = savedTheme || "dark";

  applyTheme(initialTheme);

  function applyTheme(theme) {
    if (theme === "dark") {
      document.body.classList.remove("theme-light");
      document.body.classList.add("theme-dark");
      document.documentElement.setAttribute("data-theme", "dark");
      if (themeIcon) {
        themeIcon.className = "fa-solid fa-sun";
        themeIcon.style.color = "#38bdf8";
      }
      if (themeText) themeText.innerText = "Jour";
      if (btnThemeToggle) btnThemeToggle.title = "Passer en Mode Jour (Clarté)";

      if (drawerToggleTheme) drawerToggleTheme.checked = true;
      if (drawerThemeIcon) {
        drawerThemeIcon.className = "fa-solid fa-sun";
        drawerThemeIcon.style.color = "#38bdf8";
      }
      if (drawerThemeTitle) drawerThemeTitle.innerText = "Mode Nuit Actif (Zen)";
      if (drawerThemeSub) drawerThemeSub.innerText = "Cliquer pour passer en Mode Jour (Clarté)";
    } else {
      document.body.classList.remove("theme-dark");
      document.body.classList.add("theme-light");
      document.documentElement.setAttribute("data-theme", "light");
      if (themeIcon) {
        themeIcon.className = "fa-solid fa-moon";
        themeIcon.style.color = "#f59e0b";
      }
      if (themeText) themeText.innerText = "Nuit";
      if (btnThemeToggle) btnThemeToggle.title = "Passer en Mode Nuit (Obsidian Zen)";

      if (drawerToggleTheme) drawerToggleTheme.checked = false;
      if (drawerThemeIcon) {
        drawerThemeIcon.className = "fa-solid fa-moon";
        drawerThemeIcon.style.color = "#f59e0b";
      }
      if (drawerThemeTitle) drawerThemeTitle.innerText = "Mode Jour Actif (Clarté)";
      if (drawerThemeSub) drawerThemeSub.innerText = "Cliquer pour passer en Mode Nuit (Obsidian Zen)";
    }
    localStorage.setItem("oneshot_theme", theme);
  }

  window.toggleOneShotTheme = function() {
    const isDark = document.body.classList.contains("theme-dark");
    const nextTheme = isDark ? "light" : "dark";
    applyTheme(nextTheme);
    showToast(nextTheme === "dark" ? "Mode Nuit activé (Obsidian Zen)" : "Mode Jour activé (Clarté)", "info");
  };

  if (btnThemeToggle) {
    btnThemeToggle.addEventListener("click", () => {
      window.toggleOneShotTheme();
    });
  }

  if (drawerToggleTheme) {
    drawerToggleTheme.addEventListener("change", () => {
      window.toggleOneShotTheme();
    });
  }
}

/* ==========================================================
   ONESHOT WORKSPACE BANNER CUSTOMIZER
========================================================== */
/* ==========================================================
   ONESHOT WORKSPACE BANNER & WALLPAPER CUSTOMIZER
========================================================== */
function setupBannerCustomizer() {
  const bannerWrapper = document.getElementById("oneshot-banner-wrapper");
  const bannerImage = document.getElementById("oneshot-banner-image");
  const wallpaperLayer = document.getElementById("oneshot-wallpaper-layer");
  const wallpaperOverlay = document.getElementById("oneshot-wallpaper-overlay");

  const modal = document.getElementById("modal-banner-customizer");
  const btnCloseModal = document.getElementById("btn-close-banner-modal");
  const btnCloseModalFoot = document.getElementById("btn-close-banner-modal-foot");
  const btnSaveModal = document.getElementById("btn-save-banner-modal");

  const btnHeaderBanner = document.getElementById("btn-header-banner");
  const btnBannerEdit = document.getElementById("btn-banner-edit");
  const btnBannerToggleVis = document.getElementById("btn-banner-toggle-vis");
  const menuTileBanner = document.getElementById("menu-tile-banner");

  const inputCustomUrl = document.getElementById("input-banner-custom-url");
  const btnApplyCustomUrl = document.getElementById("btn-apply-banner-custom-url");
  const inputUpload = document.getElementById("input-banner-file-upload");
  const dropzone = document.getElementById("banner-dropzone");
  const btnBrowse = document.getElementById("btn-banner-browse");
  const uploadProgress = document.getElementById("banner-upload-progress");

  const btnToggleVisModal = document.getElementById("btn-modal-toggle-banner-vis");
  const btnResetDefault = document.getElementById("btn-reset-banner-default");

  const activeThumb = document.getElementById("banner-active-thumb");
  const activeName = document.getElementById("banner-active-name");
  const activeModeTag = document.getElementById("banner-active-mode-tag");

  // Default state: banner mode, Cyber Obsidian gradient
  const defaultBanner = {
    type: "gradient",
    value: "linear-gradient(135deg, #090d16 0%, #1e1b4b 50%, #312e81 100%)",
    name: "Cyber Obsidian",
    height: 160,
    visible: true,
    mode: "banner" // "banner" | "wallpaper" | "both"
  };

  let bannerConfig = { ...defaultBanner };
  try {
    const saved = localStorage.getItem("oneshot_banner_config");
    if (saved) {
      const parsed = JSON.parse(saved);
      bannerConfig = { ...defaultBanner, ...parsed };
    }
  } catch (e) {
    console.warn("Could not load banner config from localStorage:", e);
    bannerConfig = { ...defaultBanner };
  }

  // Safe localStorage saving
  function saveConfig() {
    try {
      localStorage.setItem("oneshot_banner_config", JSON.stringify(bannerConfig));
    } catch (e) {
      console.warn("localStorage quota exceeded, storing lightweight reference only:", e);
      if (bannerConfig.value && bannerConfig.value.length > 500) {
        // If it's a huge base64, don't store it in localStorage to prevent crashing
        const safeConfig = { ...bannerConfig, value: "" };
        try {
          localStorage.setItem("oneshot_banner_config", JSON.stringify(safeConfig));
        } catch (_) {}
      }
    }
    renderBanner();
  }

  function renderBanner() {
    const isVisible = !!bannerConfig.visible;
    const mode = bannerConfig.mode || "banner";
    const isWallpaper = mode === "wallpaper" || mode === "both";
    const isBanner = mode === "banner" || mode === "both";

    // 1. Wallpaper Layer & Overlay
    if (wallpaperLayer && wallpaperOverlay) {
      if (isVisible && isWallpaper && bannerConfig.value) {
        wallpaperLayer.classList.add("active");
        wallpaperOverlay.classList.add("active");
        document.body.classList.add("has-custom-wallpaper");

        if (bannerConfig.type === "gradient") {
          wallpaperLayer.style.background = bannerConfig.value;
          wallpaperLayer.style.backgroundImage = bannerConfig.value;
        } else {
          wallpaperLayer.style.background = "";
          wallpaperLayer.style.backgroundImage = `url("${bannerConfig.value}")`;
        }
      } else {
        wallpaperLayer.classList.remove("active");
        wallpaperOverlay.classList.remove("active");
        wallpaperLayer.style.backgroundImage = "none";
        wallpaperLayer.style.background = "none";
        document.body.classList.remove("has-custom-wallpaper");
      }
    }

    // 2. Banner Wrapper (Top Notion-style cover)
    if (bannerWrapper && bannerImage) {
      if (isVisible && isBanner && bannerConfig.value) {
        bannerWrapper.classList.remove("hidden");
        bannerWrapper.style.height = `${bannerConfig.height || 160}px`;

        if (bannerConfig.type === "gradient") {
          bannerImage.style.background = bannerConfig.value;
          bannerImage.style.backgroundImage = bannerConfig.value;
        } else {
          bannerImage.style.background = "";
          bannerImage.style.backgroundImage = `url("${bannerConfig.value}")`;
        }
      } else {
        bannerWrapper.classList.add("hidden");
      }
    }

    // 3. Quick Toggle button on banner
    if (btnBannerToggleVis) {
      btnBannerToggleVis.innerHTML = isVisible
        ? '<i class="fa-solid fa-eye-slash"></i> <span>Masquer</span>'
        : '<i class="fa-solid fa-eye"></i> <span>Afficher</span>';
    }

    // 4. Modal Controls Sync
    if (btnToggleVisModal) {
      btnToggleVisModal.classList.toggle("active", isVisible);
      btnToggleVisModal.innerHTML = isVisible
        ? '<i class="fa-solid fa-eye"></i> <span>Bannière Visible</span>'
        : '<i class="fa-solid fa-eye-slash"></i> <span>Bannière Masquée</span>';
    }

    // Mode chips (Banner / Wallpaper / Both)
    document.querySelectorAll(".banner-mode-chip").forEach(chip => {
      const chipMode = chip.getAttribute("data-mode");
      chip.classList.toggle("active", chipMode === mode);
    });

    // Height chips
    document.querySelectorAll(".banner-size-chip").forEach(chip => {
      const h = parseInt(chip.getAttribute("data-size"), 10);
      chip.classList.toggle("active", h === bannerConfig.height);
    });

    // Preset cards
    document.querySelectorAll(".banner-preset-card").forEach(card => {
      const val = card.getAttribute("data-banner-val");
      card.classList.toggle("active", val === bannerConfig.value);
    });

    // Active visual preview bar
    if (activeThumb) {
      if (bannerConfig.type === "gradient") {
        activeThumb.style.background = bannerConfig.value;
        activeThumb.style.backgroundImage = bannerConfig.value;
      } else {
        activeThumb.style.background = "";
        activeThumb.style.backgroundImage = `url("${bannerConfig.value}")`;
      }
    }
    if (activeName) {
      let displayName = bannerConfig.name || "Visuel personnalisé";
      if (bannerConfig.type === "image" && !bannerConfig.name) {
        displayName = bannerConfig.value.includes("/custom_banner") ? "Image importée" : "Image personnalisée";
      }
      activeName.textContent = displayName;
    }
    if (activeModeTag) {
      let modeText = "Bannière (Haut)";
      if (mode === "wallpaper") modeText = "Fond d'écran";
      else if (mode === "both") modeText = "Bannière & Fond";
      activeModeTag.textContent = modeText;
    }
  }

  // Upload handler with API and Canvas compression fallback
  async function handleBannerFileUpload(file) {
    if (!file) return;

    // Robust image check: MIME type OR file extension
    const isImageMime = file.type && file.type.startsWith("image/");
    const isImageExt = /\.(jpe?g|png|webp|gif|bmp|svg|avif|heic|jfif|ico)$/i.test(file.name || "");
    if (!isImageMime && !isImageExt) {
      showToast("Veuillez sélectionner un fichier image valide (JPG, PNG, WebP, GIF, etc.)", "error");
      return;
    }

    // Ensure banner is visible and active when user imports an image
    bannerConfig.visible = true;
    if (bannerConfig.mode === "wallpaper") {
      bannerConfig.mode = "both";
    }

    // Instant immediate visual preview for zero-latency feedback
    try {
      const tempBlobUrl = URL.createObjectURL(file);
      bannerConfig.type = "image";
      bannerConfig.value = tempBlobUrl;
      bannerConfig.name = file.name || "Image importée";
      renderBanner();
      showToast("Application immédiate de votre image...", "info");
    } catch (_) {}

    if (uploadProgress) uploadProgress.style.display = "flex";

    try {
      // 1. Direct server upload via FormData
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch("/api/banner/upload", {
        method: "POST",
        body: formData
      });

      if (response.ok) {
        const data = await response.json();
        if (data.status === "success" && data.url) {
          bannerConfig.type = "image";
          bannerConfig.value = data.url;
          bannerConfig.name = file.name || "Image importée";
          bannerConfig.visible = true;
          saveConfig();
          showToast("✓ Image importée et appliquée avec succès !", "success");
          return;
        }
      }
      throw new Error("API upload returned non-success");
    } catch (err) {
      console.warn("Direct upload to /api/banner/upload failed, using compressed canvas fallback:", err);

      // 2. Client-side fallback: compress image on canvas to avoid quota errors
      try {
        const compressedDataUrl = await compressImageFile(file, 1920, 0.82);
        bannerConfig.type = "image";
        bannerConfig.value = compressedDataUrl;
        bannerConfig.name = file.name || "Image importée (local)";
        bannerConfig.visible = true;
        saveConfig();
        showToast("✓ Image optimisée et appliquée avec succès !", "success");
      } catch (compressionErr) {
        console.error("Compression failed:", compressionErr);
        saveConfig();
        showToast("Image appliquée localement !", "info");
      }
    } finally {
      if (uploadProgress) uploadProgress.style.display = "none";
    }
  }

  // Helper: compress image file using canvas
  function compressImageFile(file, maxDimension, quality) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = function(e) {
        const img = new Image();
        img.onload = function() {
          let width = img.width;
          let height = img.height;

          if (width > maxDimension || height > maxDimension) {
            if (width > height) {
              height = Math.round((height * maxDimension) / width);
              width = maxDimension;
            } else {
              width = Math.round((width * maxDimension) / height);
              height = maxDimension;
            }
          }

          const canvas = document.createElement("canvas");
          canvas.width = width;
          canvas.height = height;
          const ctx = canvas.getContext("2d");
          ctx.drawImage(img, 0, 0, width, height);

          resolve(canvas.toDataURL("image/jpeg", quality));
        };
        img.onerror = reject;
        img.src = e.target.result;
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  // Initial apply
  renderBanner();

  // Check if server already has a custom banner previously uploaded
  fetch("/api/banner")
    .then(res => res.json())
    .then(data => {
      if (data && data.has_custom && data.url) {
        // If current config is default or points to a custom banner, update url
        if (!bannerConfig.value || bannerConfig.value.includes("custom_banner")) {
          bannerConfig.type = "image";
          bannerConfig.value = data.url;
          bannerConfig.name = "Image importée";
          renderBanner();
        }
      } else if (data && !data.has_custom) {
        // If server was reset and localStorage points to an old missing file, revert to default
        if (bannerConfig.value && bannerConfig.value.includes("custom_banner")) {
          bannerConfig = { ...defaultBanner };
          saveConfig();
        }
      }
    })
    .catch(() => {});

  function openBannerModal() {
    const modalEl = document.getElementById("modal-banner-customizer") || modal;
    if (modalEl) {
      modalEl.style.setProperty("display", "flex", "important");
      renderBanner();
    }
  }

  function closeBannerModal() {
    const modalEl = document.getElementById("modal-banner-customizer") || modal;
    if (modalEl) modalEl.style.display = "none";
  }

  // Expose globally on window for 100% reliable invocation from any menu or drawer
  window.openBannerModal = openBannerModal;
  window.closeBannerModal = closeBannerModal;
  window.handleBannerFileUpload = handleBannerFileUpload;

  // Open modal triggers
  if (btnHeaderBanner) btnHeaderBanner.addEventListener("click", openBannerModal);
  if (btnBannerEdit) btnBannerEdit.addEventListener("click", openBannerModal);

  const btnDrawerBanner = document.getElementById("btn-drawer-upload-banner");
  if (btnDrawerBanner) {
    btnDrawerBanner.addEventListener("click", () => {
      if (typeof window.closeStudioDrawer === "function") window.closeStudioDrawer();
      openBannerModal();
    });
  }

  if (menuTileBanner) {
    menuTileBanner.addEventListener("click", () => {
      if (typeof window.closeStudioDrawer === "function") window.closeStudioDrawer();
      openBannerModal();
    });
  }

  // Attach all file input elements (global, modal, legacy) to handleBannerFileUpload
  function bindFileInput(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener("change", (e) => {
      const file = e.target.files && e.target.files[0];
      if (file) {
        handleBannerFileUpload(file);
      }
      el.value = "";
    });
  }

  bindFileInput("global-banner-file-input");
  bindFileInput("input-banner-file-upload");
  bindFileInput("banner-file-input");

  // Quick toggle on banner
  if (btnBannerToggleVis) {
    btnBannerToggleVis.addEventListener("click", (e) => {
      e.stopPropagation();
      bannerConfig.visible = !bannerConfig.visible;
      saveConfig();
      showToast(bannerConfig.visible ? "Bannière affichée" : "Bannière masquée (Mode zen)", "info");
    });
  }

  // Close triggers
  if (btnCloseModal) btnCloseModal.addEventListener("click", closeBannerModal);
  if (btnCloseModalFoot) btnCloseModalFoot.addEventListener("click", closeBannerModal);
  if (btnSaveModal) {
    btnSaveModal.addEventListener("click", () => {
      saveConfig();
      closeBannerModal();
      showToast("✓ Thème et affichage enregistrés !", "success");
    });
  }

  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeBannerModal();
    });
  }

  // Mode Selection (Bannière / Fond d'écran / Les deux)
  document.querySelectorAll(".banner-mode-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const selectedMode = chip.getAttribute("data-mode");
      if (selectedMode) {
        bannerConfig.mode = selectedMode;
        bannerConfig.visible = true;
        saveConfig();
        const modeLabels = {
          banner: "Bannière seule (Haut de page)",
          wallpaper: "Fond d'écran plein écran",
          both: "Bannière et Fond d'écran"
        };
        showToast(`✓ Mode actif : ${modeLabels[selectedMode] || selectedMode}`, "info");
      }
    });
  });

  // Preset click handlers (Gradients & Photos)
  document.querySelectorAll(".banner-preset-card").forEach(card => {
    card.addEventListener("click", () => {
      const type = card.getAttribute("data-banner-type") || "gradient";
      const val = card.getAttribute("data-banner-val") || "";
      const name = card.querySelector("span") ? card.querySelector("span").textContent.trim() : "Préréglage";

      bannerConfig.type = type;
      bannerConfig.value = val;
      bannerConfig.name = name;
      bannerConfig.visible = true;
      saveConfig();
      showToast(`✓ Thème appliqué : ${name}`, "info");
    });
  });

  // Custom Web URL handler
  if (btnApplyCustomUrl && inputCustomUrl) {
    btnApplyCustomUrl.addEventListener("click", () => {
      const url = inputCustomUrl.value.trim();
      if (!url) {
        showToast("Veuillez saisir une URL d'image valide", "error");
        return;
      }
      bannerConfig.type = "image";
      bannerConfig.value = url;
      bannerConfig.name = "Image Web personnalisée";
      bannerConfig.visible = true;
      saveConfig();
      showToast("✓ Image web appliquée !", "success");
    });
  }

  // Drag & Drop helper for any drop target
  function setupDropEvents(element) {
    if (!element) return;
    element.addEventListener("dragover", (e) => {
      e.preventDefault();
      e.stopPropagation();
      element.classList.add("dragover");
    });
    element.addEventListener("dragleave", (e) => {
      e.preventDefault();
      e.stopPropagation();
      element.classList.remove("dragover");
    });
    element.addEventListener("drop", (e) => {
      e.preventDefault();
      e.stopPropagation();
      element.classList.remove("dragover");
      const dt = e.dataTransfer;
      if (dt && dt.files && dt.files.length > 0) {
        handleBannerFileUpload(dt.files[0]);
      }
    });
  }

  setupDropEvents(document.getElementById("banner-dropzone"));
  setupDropEvents(document.getElementById("oneshot-banner-wrapper"));

  // Dropzone click handler: only trigger file picker if user didn't click directly on a label or button
  if (dropzone) {
    dropzone.addEventListener("click", (e) => {
      if (e.target.closest("label") || e.target.closest("button") || e.target.closest("input")) {
        return;
      }
      const globalInput = document.getElementById("global-banner-file-input") || inputUpload;
      if (globalInput) globalInput.click();
    });
  }

  // Reset to default button
  if (btnResetDefault) {
    btnResetDefault.addEventListener("click", async () => {
      try {
        await fetch("/api/banner/reset", { method: "POST" });
      } catch (_) {}

      bannerConfig = { ...defaultBanner };
      saveConfig();
      showToast("✓ Thème par défaut rétabli !", "info");
    });
  }

  // Modal Visibility toggle
  if (btnToggleVisModal) {
    btnToggleVisModal.addEventListener("click", () => {
      bannerConfig.visible = !bannerConfig.visible;
      saveConfig();
      showToast(bannerConfig.visible ? "Visuel activé" : "Visuel masqué", "info");
    });
  }

  // Height chips
  document.querySelectorAll(".banner-size-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const h = parseInt(chip.getAttribute("data-size"), 10);
      if (h) {
        bannerConfig.height = h;
        saveConfig();
      }
    });
  });
}

/* ==========================================================
   NINTENDO & POKÉMON PROCEDURAL AUDIO SYNTH (WEB AUDIO API)
   Iconic Nintendo Switch two-tone menu ping & Zelda chime
========================================================== */
function initGameAudio() {
  let audioCtx = null;
  const isMuted = localStorage.getItem("oneshot_audio_mute") === "true";

  function playNintendoChirp(type = "select") {
    if (isMuted) return;
    try {
      if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      }
      if (audioCtx.state === "suspended") {
        audioCtx.resume();
      }

      const now = audioCtx.currentTime;

      if (type === "confirm") {
        // Joy-Con Confirm / Zelda Item Ding (Arpeggio: E5 -> G#5 -> B5 -> E6)
        const notes = [659.25, 830.61, 987.77, 1318.51];
        notes.forEach((freq, idx) => {
          const osc = audioCtx.createOscillator();
          const gain = audioCtx.createGain();
          osc.type = "sine";
          osc.frequency.setValueAtTime(freq, now + idx * 0.04);
          gain.gain.setValueAtTime(0.04, now + idx * 0.04);
          gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.04 + 0.08);
          osc.connect(gain);
          gain.connect(audioCtx.destination);
          osc.start(now + idx * 0.04);
          osc.stop(now + idx * 0.04 + 0.08);
        });
      } else {
        // Classic Switch / Pokémon Menu Ding: crisp two-tone B5 -> E6
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(987.77, now);
        osc.frequency.setValueAtTime(1318.51, now + 0.025);
        gain.gain.setValueAtTime(0.035, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.065);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start(now);
        osc.stop(now + 0.065);
      }
    } catch (_) {}
  }

  document.addEventListener("click", (e) => {
    const btn = e.target.closest("button, .steady-action-btn, .zen-plat-pill, .steady-status-chip, .ludique-btn-action, .steady-cv-pill, .oneshot-banner-btn");
    if (btn) {
      if (btn.id === "btn-header-batch-apply" || btn.classList.contains("steady-btn-primary")) {
        playNintendoChirp("confirm");
      } else {
        playNintendoChirp("select");
      }
      btn.classList.remove("nintendo-press");
      void btn.offsetWidth; // trigger reflow
      btn.classList.add("nintendo-press");
    }
  });

  window.playNintendoChirp = playNintendoChirp;
  window.playCyberChirp = playNintendoChirp;
}



