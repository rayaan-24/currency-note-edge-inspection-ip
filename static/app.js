/**
 * app.js - Frontend Logic for Currency Note Edge Quality Inspection
 * Manages dashboard state, API calls, real-time image updates, dataset browser, and batch evaluation.
 */

document.addEventListener('DOMContentLoaded', () => {
  // --- DOM Elements ---
  const engineStatusBadge = document.getElementById('engineStatusBadge');
  const engineStatusText = document.getElementById('engineStatusText');
  const sampleSelect = document.getElementById('sampleSelect');
  const fileInput = document.getElementById('fileInput');
  const dropZone = document.getElementById('dropZone');
  const fileSelectedBadge = document.getElementById('fileSelectedBadge');
  const selectedFileName = document.getElementById('selectedFileName');
  const btnClearFile = document.getElementById('btnClearFile');
  const btnAnalyze = document.getElementById('btnAnalyze');
  const btnAnalyzeText = document.getElementById('btnAnalyzeText');
  const btnReset = document.getElementById('btnReset');
  const toggleOverlayCheckbox = document.getElementById('toggleOverlayCheckbox');
  const btnExportOverlay = document.getElementById('btnExportOverlay');
  const btnExportReport = document.getElementById('btnExportReport');

  // Sidebar Dataset Selection Elements
  const datasetSelectPlaceholder = document.getElementById('datasetSelectPlaceholder');
  const datasetSelectedPreview = document.getElementById('datasetSelectedPreview');
  const imgSelectedDatasetThumb = document.getElementById('imgSelectedDatasetThumb');
  const lblDatasetPreviewName = document.getElementById('lblDatasetPreviewName');
  const lblDatasetPreviewCat = document.getElementById('lblDatasetPreviewCat');
  const lblDatasetPreviewDim = document.getElementById('lblDatasetPreviewDim');
  const btnClearDatasetSelection = document.getElementById('btnClearDatasetSelection');
  const btnLaunchBrowserSidebar = document.getElementById('btnLaunchBrowserSidebar');

  // System Banner
  const systemBanner = document.getElementById('systemBanner');
  const systemBannerText = document.getElementById('systemBannerText');
  const btnCloseBanner = document.getElementById('btnCloseBanner');

  // Metrics
  const badgeClassification = document.getElementById('badgeClassification');
  const classificationReason = document.getElementById('classificationReason');
  const metricDamagePct = document.getElementById('metricDamagePct');
  const damageProgressBar = document.getElementById('damageProgressBar');
  const lblDamagedPx = document.getElementById('lblDamagedPx');
  const lblTotalPerimPx = document.getElementById('lblTotalPerimPx');
  const metricConfidence = document.getElementById('metricConfidence');
  const confidenceProgressBar = document.getElementById('confidenceProgressBar');
  const lblSolidityAspect = document.getElementById('lblSolidityAspect');
  const metricExecTime = document.getElementById('metricExecTime');
  const lblEngineMode = document.getElementById('lblEngineMode');

  // Viewports & Tabs
  const imgOriginal = document.getElementById('imgOriginal');
  const imgGrayscale = document.getElementById('imgGrayscale');
  const imgBoundary = document.getElementById('imgBoundary');
  const imgOverlay = document.getElementById('imgOverlay');
  const imgSingleView = document.getElementById('imgSingleView');
  const quadViewContainer = document.getElementById('quadViewContainer');
  const singleViewContainer = document.getElementById('singleViewContainer');
  const loaderOriginal = document.getElementById('loaderOriginal');
  const loaderGrayscale = document.getElementById('loaderGrayscale');
  const loaderBoundary = document.getElementById('loaderBoundary');
  const loaderOverlay = document.getElementById('loaderOverlay');
  const canvasTabs = document.querySelectorAll('.canvas-tabs .tab-btn');

  // Granular Table
  const edgeTableBody = document.getElementById('edgeTableBody');

  // Dataset Browser Modal Elements
  const btnOpenBrowserModal = document.getElementById('btnOpenBrowserModal');
  const browserModal = document.getElementById('browserModal');
  const btnCloseBrowserModal = document.getElementById('btnCloseBrowserModal');
  const btnCloseBrowserFooter = document.getElementById('btnCloseBrowserFooter');
  const browserSearchInput = document.getElementById('browserSearchInput');
  const browserCategoryFilter = document.getElementById('browserCategoryFilter');
  const lblBrowserCurrentCount = document.getElementById('lblBrowserCurrentCount');
  const lblBrowserTotalCount = document.getElementById('lblBrowserTotalCount');
  const datasetGalleryGrid = document.getElementById('datasetGalleryGrid');
  const browserLoadingSpinner = document.getElementById('browserLoadingSpinner');
  const btnPrevPage = document.getElementById('btnPrevPage');
  const btnNextPage = document.getElementById('btnNextPage');
  const lblCurrentPage = document.getElementById('lblCurrentPage');
  const lblTotalPages = document.getElementById('lblTotalPages');
  const paginationPageNumbers = document.getElementById('paginationPageNumbers');

  // Batch Evaluation Modal Elements
  const btnOpenEvalModal = document.getElementById('btnOpenEvalModal');
  const evalModal = document.getElementById('evalModal');
  const btnCloseEvalModal = document.getElementById('btnCloseEvalModal');
  const btnCloseEvalFooter = document.getElementById('btnCloseEvalFooter');
  const evalCountSelect = document.getElementById('evalCountSelect');
  const evalCategorySelect = document.getElementById('evalCategorySelect');
  const btnRunEvaluation = document.getElementById('btnRunEvaluation');
  const evalProgressBox = document.getElementById('evalProgressBox');
  const evalProgressText = document.getElementById('evalProgressText');
  const evalResultsSummary = document.getElementById('evalResultsSummary');
  const statEvalTotal = document.getElementById('statEvalTotal');
  const statEvalSuccess = document.getElementById('statEvalSuccess');
  const statEvalAvgDamage = document.getElementById('statEvalAvgDamage');
  const statEvalAvgTime = document.getElementById('statEvalAvgTime');
  const evalClassDistribution = document.getElementById('evalClassDistribution');
  const btnDownloadEvalCsv = document.getElementById('btnDownloadEvalCsv');
  const evalTableBody = document.getElementById('evalTableBody');

  // Dataset Attribution Modal Elements
  const btnOpenDatasetModal = document.getElementById('btnOpenDatasetModal');
  const datasetModal = document.getElementById('datasetModal');
  const btnCloseDatasetModal = document.getElementById('btnCloseDatasetModal');
  const btnCloseModalFooter = document.getElementById('btnCloseModalFooter');
  const statRealCount = document.getElementById('statRealCount');
  const statCategoryCount = document.getElementById('statCategoryCount');
  const statTargetCount = document.getElementById('statTargetCount');
  const datasetCategoryList = document.getElementById('datasetCategoryList');

  // Application State
  const state = {
    selectedDatasetItem: null,
    selectedFile: null,
    selectedSample: null,
    latestResult: null,
    activeTab: 'quad',
    browserPage: 1,
    browserPageSize: 24,
    browserSearch: '',
    browserCategory: 'All',
    datasetInfo: null
  };

  // --- Initial Startup Sequence ---
  checkSystemHealth();
  loadSampleList();
  fetchDatasetInfo();

  // --- 1. System Health Check ---
  async function checkSystemHealth() {
    try {
      const resp = await fetch('/api/health');
      const data = await resp.json();

      engineStatusBadge.className = 'status-badge ready';
      engineStatusText.textContent = 'Python DIP Engine Ready (No MATLAB/Octave)';
      lblEngineMode.textContent = 'Python 3 Native (scikit-image + NumPy + Pillow)';
    } catch (err) {
      engineStatusBadge.className = 'status-badge missing';
      engineStatusText.textContent = 'Server Offline';
      showBanner('Unable to connect to the backend server. Verify that Uvicorn is active at http://127.0.0.1:8000.', 'error');
    }
  }

  // --- 2. Load Synthetic Unit Test Samples ---
  async function loadSampleList() {
    try {
      const resp = await fetch('/api/samples');
      const data = await resp.json();
      sampleSelect.innerHTML = '<option value="" selected>Select a synthetic test note...</option>';

      data.samples.forEach(sample => {
        const opt = document.createElement('option');
        opt.value = sample.filename;
        opt.textContent = `${sample.name} (${sample.expected_class})`;
        sampleSelect.appendChild(opt);
      });
    } catch (err) {
      console.warn('Failed to load sample list:', err);
    }
  }

  // --- 3. Fetch Dataset Attribution & Category Info ---
  async function fetchDatasetInfo() {
    try {
      const resp = await fetch('/api/dataset');
      const data = await resp.json();
      state.datasetInfo = data;

      // Populate attribution modal stats
      statRealCount.textContent = data.total_selected_images.toLocaleString();
      statCategoryCount.textContent = data.categories.length;
      statTargetCount.textContent = data.target_selection.toLocaleString();

      // Populate categories list
      datasetCategoryList.innerHTML = '';
      browserCategoryFilter.innerHTML = '<option value="All">All Categories (2,000)</option>';
      evalCategorySelect.innerHTML = '<option value="All">All 8 Denominations/Series</option>';

      data.categories.forEach(cat => {
        // Modal category list item
        const item = document.createElement('div');
        item.className = 'category-item';
        item.innerHTML = `<span class="category-name">${escapeHtml(cat.name)}</span><span class="category-count">${cat.count} samples</span>`;
        datasetCategoryList.appendChild(item);

        // Filter dropdowns
        const opt = document.createElement('option');
        opt.value = cat.name;
        opt.textContent = `${cat.name} (${cat.count})`;
        browserCategoryFilter.appendChild(opt);

        const evalOpt = document.createElement('option');
        evalOpt.value = cat.name;
        evalOpt.textContent = cat.name;
        evalCategorySelect.appendChild(evalOpt);
      });

    } catch (err) {
      console.warn('Failed to load dataset metadata:', err);
    }
  }

  // --- 4. Dataset Browser Logic ---
  let searchDebounceTimer = null;

  async function loadBrowserImages(page = 1) {
    state.browserPage = page;
    browserLoadingSpinner.classList.remove('hidden');
    datasetGalleryGrid.innerHTML = '';

    const params = new URLSearchParams({
      page: state.browserPage,
      page_size: state.browserPageSize,
      category: state.browserCategory,
      search: state.browserSearch
    });

    try {
      const resp = await fetch(`/api/dataset/images?${params.toString()}`);
      const data = await resp.json();

      browserLoadingSpinner.classList.add('hidden');
      lblBrowserCurrentCount.textContent = data.items.length;
      lblBrowserTotalCount.textContent = data.total.toLocaleString();
      lblCurrentPage.textContent = data.page;
      lblTotalPages.textContent = data.total_pages;

      btnPrevPage.disabled = (data.page <= 1);
      btnNextPage.disabled = (data.page >= data.total_pages);

      renderPaginationNumbers(data.page, data.total_pages);

      if (data.items.length === 0) {
        datasetGalleryGrid.innerHTML = '<div class="empty-state">No matching notes found in the 2,000-image dataset.</div>';
        return;
      }

      data.items.forEach(item => {
        const card = document.createElement('div');
        card.className = 'gallery-card';
        if (state.selectedDatasetItem && state.selectedDatasetItem.id === item.id) {
          card.classList.add('selected');
        }

        const thumbUrl = `/api/dataset/image/${item.id}?thumb=1`;

        card.innerHTML = `
          <div class="gallery-thumb-wrapper">
            <img src="${thumbUrl}" alt="${escapeHtml(item.filename)}" class="gallery-thumb" loading="lazy">
            <span class="gallery-id-badge">#${item.id}</span>
          </div>
          <div class="gallery-card-body">
            <span class="gallery-card-title" title="${escapeHtml(item.filename)}">${escapeHtml(item.filename)}</span>
            <span class="gallery-card-sub">${escapeHtml(item.denomination)} &bull; ${escapeHtml(item.series)}</span>
            <span class="gallery-card-dim">${item.width} &times; ${item.height} px</span>
            <button class="gallery-btn-select" data-id="${item.id}">Analyze Note &rarr;</button>
          </div>
        `;

        card.querySelector('.gallery-btn-select').addEventListener('click', () => {
          selectDatasetItemAndAnalyze(item);
        });

        datasetGalleryGrid.appendChild(card);
      });

    } catch (err) {
      browserLoadingSpinner.classList.add('hidden');
      datasetGalleryGrid.innerHTML = '<div class="empty-state error">Failed to load dataset images.</div>';
    }
  }

  function renderPaginationNumbers(currPage, totalPages) {
    paginationPageNumbers.innerHTML = '';
    const maxButtons = 5;
    let start = Math.max(1, currPage - 2);
    let end = Math.min(totalPages, start + maxButtons - 1);
    if (end - start < maxButtons - 1) {
      start = Math.max(1, end - maxButtons + 1);
    }

    for (let p = start; p <= end; p++) {
      const btn = document.createElement('button');
      btn.className = `page-pill ${p === currPage ? 'active' : ''}`;
      btn.textContent = p;
      btn.addEventListener('click', () => loadBrowserImages(p));
      paginationPageNumbers.appendChild(btn);
    }
  }

  function selectDatasetItemAndAnalyze(item) {
    state.selectedDatasetItem = item;
    state.selectedFile = null;
    state.selectedSample = null;

    // Reset upload UI
    fileInput.value = '';
    fileSelectedBadge.classList.add('hidden');
    dropZone.querySelector('.drop-zone-content').classList.remove('hidden');
    sampleSelect.value = '';

    // Update Sidebar Dataset Preview Box
    datasetSelectPlaceholder.classList.add('hidden');
    datasetSelectedPreview.classList.remove('hidden');
    imgSelectedDatasetThumb.src = `/api/dataset/image/${item.id}?thumb=1`;
    lblDatasetPreviewName.textContent = item.filename;
    lblDatasetPreviewCat.textContent = `${item.denomination} (${item.series} Series, #${item.id})`;
    lblDatasetPreviewDim.textContent = `${item.width} × ${item.height} px`;

    // Close browser modal
    browserModal.classList.add('hidden');

    // Trigger analysis immediately
    btnAnalyze.disabled = false;
    runInspection();
  }

  function clearDatasetSelection() {
    state.selectedDatasetItem = null;
    datasetSelectedPreview.classList.add('hidden');
    datasetSelectPlaceholder.classList.remove('hidden');
    updateAnalyzeButtonState();
  }

  // Browser Search & Filter Listeners
  browserSearchInput.addEventListener('input', (e) => {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
      state.browserSearch = e.target.value.trim();
      loadBrowserImages(1);
    }, 300);
  });

  browserCategoryFilter.addEventListener('change', (e) => {
    state.browserCategory = e.target.value;
    loadBrowserImages(1);
  });

  btnPrevPage.addEventListener('click', () => {
    if (state.browserPage > 1) loadBrowserImages(state.browserPage - 1);
  });

  btnNextPage.addEventListener('click', () => {
    loadBrowserImages(state.browserPage + 1);
  });

  // Open/Close Browser Modal
  btnOpenBrowserModal.addEventListener('click', () => {
    browserModal.classList.remove('hidden');
    loadBrowserImages(state.browserPage);
  });
  btnLaunchBrowserSidebar.addEventListener('click', () => {
    browserModal.classList.remove('hidden');
    loadBrowserImages(state.browserPage);
  });
  btnCloseBrowserModal.addEventListener('click', () => browserModal.classList.add('hidden'));
  btnCloseBrowserFooter.addEventListener('click', () => browserModal.classList.add('hidden'));

  btnClearDatasetSelection.addEventListener('click', clearDatasetSelection);

  // --- 5. Batch Evaluation Logic ---
  btnOpenEvalModal.addEventListener('click', () => evalModal.classList.remove('hidden'));
  btnCloseEvalModal.addEventListener('click', () => evalModal.classList.add('hidden'));
  btnCloseEvalFooter.addEventListener('click', () => evalModal.classList.add('hidden'));

  btnRunEvaluation.addEventListener('click', async () => {
    const count = parseInt(evalCountSelect.value, 10);
    const category = evalCategorySelect.value;

    btnRunEvaluation.disabled = true;
    evalProgressBox.classList.remove('hidden');
    evalResultsSummary.classList.add('hidden');
    evalProgressText.textContent = `Processing ${count} real notes through the Python DIP pipeline...`;

    const formData = new FormData();
    formData.append('count', count);
    formData.append('category', category);

    try {
      const resp = await fetch('/api/dataset/evaluate', {
        method: 'POST',
        body: formData
      });
      const data = await resp.json();

      evalProgressBox.classList.add('hidden');
      btnRunEvaluation.disabled = false;
      evalResultsSummary.classList.remove('hidden');

      statEvalTotal.textContent = data.total_evaluated;
      statEvalSuccess.textContent = `${data.success_count} (${((data.success_count/data.total_evaluated)*100).toFixed(0)}%)`;
      statEvalAvgDamage.textContent = `${data.average_damage_percentage.toFixed(2)}%`;
      statEvalAvgTime.textContent = `${data.average_execution_time_sec.toFixed(3)}s`;

      // Distribution pills
      evalClassDistribution.innerHTML = '';
      for (const [clsName, clsCount] of Object.entries(data.predicted_distribution)) {
        const pill = document.createElement('span');
        pill.className = 'dist-pill';
        pill.innerHTML = `${escapeHtml(clsName)}: <strong>${clsCount}</strong>`;
        evalClassDistribution.appendChild(pill);
      }

      // Download CSV Link
      btnDownloadEvalCsv.href = data.csv_export_url;

      // Table of evaluated notes
      evalTableBody.innerHTML = '';
      data.evaluated_items.forEach(item => {
        const row = document.createElement('tr');
        const badgeClass = getConditionBadgeClass(item.predicted_condition);
        row.innerHTML = `
          <td>#${item.id}</td>
          <td><strong>${escapeHtml(item.filename)}</strong></td>
          <td>${escapeHtml(item.source_category)}</td>
          <td><span class="status-pill ${item.status === 'SUCCESS' ? 'green' : 'amber'}">${item.status}</span></td>
          <td><span class="status-pill ${badgeClass}">${escapeHtml(item.predicted_condition)}</span></td>
          <td>${item.damage_percentage.toFixed(2)}%</td>
          <td>${item.execution_time_sec.toFixed(3)}s</td>
        `;
        evalTableBody.appendChild(row);
      });

    } catch (err) {
      evalProgressBox.classList.add('hidden');
      btnRunEvaluation.disabled = false;
      showBanner('Batch evaluation failed: ' + err.message, 'error');
    }
  });

  // --- 6. Dataset Attribution Modal ---
  btnOpenDatasetModal.addEventListener('click', () => datasetModal.classList.remove('hidden'));
  btnCloseDatasetModal.addEventListener('click', () => datasetModal.classList.add('hidden'));
  btnCloseModalFooter.addEventListener('click', () => datasetModal.classList.add('hidden'));

  // --- 7. Input File & Sample Handling ---
  dropZone.addEventListener('click', (e) => {
    if (e.target !== btnClearFile) fileInput.click();
  });

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });

  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelected(e.target.files[0]);
    }
  });

  btnClearFile.addEventListener('click', (e) => {
    e.stopPropagation();
    state.selectedFile = null;
    fileInput.value = '';
    fileSelectedBadge.classList.add('hidden');
    dropZone.querySelector('.drop-zone-content').classList.remove('hidden');
    updateAnalyzeButtonState();
  });

  sampleSelect.addEventListener('change', (e) => {
    const val = e.target.value;
    if (val) {
      state.selectedSample = val;
      state.selectedFile = null;
      state.selectedDatasetItem = null;
      fileInput.value = '';
      fileSelectedBadge.classList.add('hidden');
      dropZone.querySelector('.drop-zone-content').classList.remove('hidden');
      datasetSelectedPreview.classList.add('hidden');
      datasetSelectPlaceholder.classList.remove('hidden');
    } else {
      state.selectedSample = null;
    }
    updateAnalyzeButtonState();
  });

  function handleFileSelected(file) {
    state.selectedFile = file;
    state.selectedSample = null;
    state.selectedDatasetItem = null;
    sampleSelect.value = '';
    datasetSelectedPreview.classList.add('hidden');
    datasetSelectPlaceholder.classList.remove('hidden');

    selectedFileName.textContent = file.name;
    fileSelectedBadge.classList.remove('hidden');
    dropZone.querySelector('.drop-zone-content').classList.add('hidden');
    updateAnalyzeButtonState();
  }

  function updateAnalyzeButtonState() {
    btnAnalyze.disabled = !(state.selectedDatasetItem || state.selectedFile || state.selectedSample);
  }

  btnReset.addEventListener('click', () => {
    clearDatasetSelection();
    state.selectedFile = null;
    state.selectedSample = null;
    state.latestResult = null;
    fileInput.value = '';
    sampleSelect.value = '';
    fileSelectedBadge.classList.add('hidden');
    dropZone.querySelector('.drop-zone-content').classList.remove('hidden');
    updateAnalyzeButtonState();
    resetDashboardMetrics();
  });

  // --- 8. Analyze Action Execution ---
  btnAnalyze.addEventListener('click', runInspection);

  async function runInspection() {
    if (!(state.selectedDatasetItem || state.selectedFile || state.selectedSample)) return;

    btnAnalyze.disabled = true;
    btnAnalyzeText.textContent = 'Processing Edges...';
    setLoadersVisible(true);

    const formData = new FormData();
    if (state.selectedDatasetItem) {
      formData.append('dataset_image_id', state.selectedDatasetItem.id);
    } else if (state.selectedFile) {
      formData.append('file', state.selectedFile);
    } else if (state.selectedSample) {
      formData.append('sample_filename', state.selectedSample);
    }

    try {
      const resp = await fetch('/api/analyze', {
        method: 'POST',
        body: formData
      });

      if (!resp.ok) {
        const errJson = await resp.json().catch(() => ({}));
        throw new Error(errJson.detail || `Server returned error status ${resp.status}`);
      }

      const result = await resp.json();
      state.latestResult = result;
      renderAnalysisResults(result);

    } catch (err) {
      showBanner(`Analysis failed: ${err.message}`, 'error');
    } finally {
      btnAnalyze.disabled = false;
      btnAnalyzeText.textContent = 'Analyze Note Edges';
      setLoadersVisible(false);
    }
  }

  // --- 9. Render Analysis Results ---
  function renderAnalysisResults(res) {
    // 1. Classification Metric
    const cat = res.classification.category || 'Needs Manual Inspection';
    badgeClassification.textContent = cat.toUpperCase();
    badgeClassification.className = `classification-badge ${getConditionBadgeClass(cat)}`;
    classificationReason.textContent = res.classification.reason || 'Completed.';

    // 2. Damage Metric
    const isReliable = res.damage.is_reliable;
    const dmgPct = isReliable ? res.damage.damage_percentage : null;
    metricDamagePct.textContent = res.damage.display_text || '--';
    if (dmgPct !== null) {
      damageProgressBar.style.width = `${Math.min(dmgPct, 100)}%`;
      if (dmgPct > 3.0) damageProgressBar.style.background = '#ef4444';
      else if (dmgPct > 1.5) damageProgressBar.style.background = '#f59e0b';
      else damageProgressBar.style.background = '#10b981';
    } else {
      damageProgressBar.style.width = '0%';
    }
    lblDamagedPx.textContent = `${res.damage.damaged_edge_length_px.toFixed(1)} px`;
    lblTotalPerimPx.textContent = `${res.damage.total_perimeter_px.toFixed(1)} px`;

    // 3. Boundary Quality
    const bConf = res.boundary.confidence || 0.0;
    metricConfidence.textContent = `${(bConf * 100).toFixed(0)}%`;
    confidenceProgressBar.style.width = `${Math.min(bConf * 100, 100)}%`;
    lblSolidityAspect.textContent = `Solidity: ${res.boundary.solidity.toFixed(2)} • Aspect Ratio: ${res.boundary.aspect_ratio.toFixed(2)}`;

    // 4. Runtime
    metricExecTime.textContent = `${res.execution_time_sec.toFixed(3)}s`;

    // 5. Update Viewports
    const art = res.artifacts || {};
    const timestampQuery = `?t=${Date.now()}`;

    if (art.source_url) imgOriginal.src = art.source_url;
    if (art.quad_url) {
      // Extract grayscale from composite if needed or use quad
      imgGrayscale.src = art.quad_url + timestampQuery;
    }
    if (art.boundary_url) imgBoundary.src = art.boundary_url + timestampQuery;
    if (art.overlay_url) imgOverlay.src = art.overlay_url + timestampQuery;

    updateActiveTabContent();

    // 6. Granular 4-Edge Table
    renderEdgeTable(res.edges.edges || []);

    // 7. Enable Export Buttons
    btnExportOverlay.disabled = !art.overlay_url;
    btnExportReport.disabled = !art.report_url;

    btnExportOverlay.onclick = () => {
      if (art.overlay_url) window.open(art.overlay_url, '_blank');
    };
    btnExportReport.onclick = () => {
      if (art.report_url) window.open(art.report_url, '_blank');
    };

    if (res.status === 'WARNING') {
      showBanner(`Notice: ${res.error_message || 'Boundary detection operated under low confidence.'}`, 'warning');
    }
  }

  function renderEdgeTable(edges) {
    edgeTableBody.innerHTML = '';
    if (!edges || edges.length === 0) {
      edgeTableBody.innerHTML = `<tr><td colspan="6" class="text-center">No individual edge data available.</td></tr>`;
      return;
    }

    edges.forEach(e => {
      const row = document.createElement('tr');
      const isDamaged = e.status === 'DAMAGED';
      const statusPill = isDamaged ? `<span class="status-pill red">DAMAGED</span>` : `<span class="status-pill green">INTACT</span>`;
      const evalText = isDamaged
        ? `Defect detected (${e.defect_count} clusters, max depth ${e.max_defect_depth.toFixed(1)} px)`
        : 'Smooth edge within geometric tolerance';

      row.innerHTML = `
        <td><strong>${escapeHtml(e.name)} Edge</strong></td>
        <td>${statusPill}</td>
        <td>${e.damaged_length.toFixed(1)} px</td>
        <td>${e.max_defect_depth.toFixed(1)} px</td>
        <td>${e.defect_count}</td>
        <td>${evalText}</td>
      `;
      edgeTableBody.appendChild(row);
    });
  }

  function getConditionBadgeClass(cat) {
    const c = (cat || '').toLowerCase();
    if (c.includes('good')) return 'good';
    if (c.includes('torn')) return 'torn';
    if (c.includes('folded')) return 'folded';
    if (c.includes('worn') || c.includes('old')) return 'worn';
    return 'manual';
  }

  function setLoadersVisible(visible) {
    const list = [loaderOriginal, loaderGrayscale, loaderBoundary, loaderOverlay];
    list.forEach(l => {
      if (visible) l.classList.remove('hidden');
      else l.classList.add('hidden');
    });
  }

  function resetDashboardMetrics() {
    badgeClassification.textContent = 'NOT ANALYZED';
    badgeClassification.className = 'classification-badge pending';
    classificationReason.textContent = 'Awaiting input note for edge analysis';
    metricDamagePct.textContent = '--';
    damageProgressBar.style.width = '0%';
    lblDamagedPx.textContent = '0.0 px';
    lblTotalPerimPx.textContent = '0.0 px';
    metricConfidence.textContent = '--';
    confidenceProgressBar.style.width = '0%';
    lblSolidityAspect.textContent = 'Solidity: -- • Aspect Ratio: --';
    metricExecTime.textContent = '--';

    imgOriginal.src = '/static/placeholder.svg';
    imgGrayscale.src = '/static/placeholder.svg';
    imgBoundary.src = '/static/placeholder.svg';
    imgOverlay.src = '/static/placeholder.svg';
    imgSingleView.src = '/static/placeholder.svg';

    btnExportOverlay.disabled = true;
    btnExportReport.disabled = true;

    renderEdgeTable([
      { name: 'Top', status: '--', damaged_length: 0, max_defect_depth: 0, defect_count: 0 },
      { name: 'Right', status: '--', damaged_length: 0, max_defect_depth: 0, defect_count: 0 },
      { name: 'Bottom', status: '--', damaged_length: 0, max_defect_depth: 0, defect_count: 0 },
      { name: 'Left', status: '--', damaged_length: 0, max_defect_depth: 0, defect_count: 0 }
    ]);
  }

  // --- 10. Multi-View Tab Navigation ---
  canvasTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      canvasTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      state.activeTab = tab.dataset.tab;
      updateActiveTabContent();
    });
  });

  function updateActiveTabContent() {
    if (state.activeTab === 'quad') {
      quadViewContainer.classList.remove('hidden');
      singleViewContainer.classList.add('hidden');
    } else {
      quadViewContainer.classList.add('hidden');
      singleViewContainer.classList.remove('hidden');

      if (state.activeTab === 'overlay') {
        imgSingleView.src = imgOverlay.src;
      } else if (state.activeTab === 'boundary') {
        imgSingleView.src = imgBoundary.src;
      } else if (state.activeTab === 'grayscale') {
        imgSingleView.src = imgGrayscale.src;
      } else if (state.activeTab === 'original') {
        imgSingleView.src = imgOriginal.src;
      }
    }
  }

  // Toggle Overlay Highlight
  toggleOverlayCheckbox.addEventListener('change', (e) => {
    if (e.target.checked) {
      imgOverlay.classList.remove('hidden');
    } else {
      imgOverlay.src = imgOriginal.src;
    }
  });

  // --- 11. Notifications ---
  function showBanner(msg, type = 'info') {
    systemBannerText.textContent = msg;
    systemBanner.className = `system-banner ${type}`;
    systemBanner.classList.remove('hidden');
  }

  btnCloseBanner.addEventListener('click', () => systemBanner.classList.add('hidden'));

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
});
