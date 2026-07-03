/* TripleMate — front-end controller
   Talks to POST /api/travel and renders the concierge response. */

(() => {
  "use strict";

  const form = document.getElementById("travelForm");
  const input = document.getElementById("query");
  const submitBtn = document.getElementById("submitBtn");
  const chips = document.getElementById("chips");

  const loading = document.getElementById("loading");
  const steps = document.getElementById("steps");
  const errorBox = document.getElementById("error");
  const errorMsg = document.getElementById("errorMsg");

  const results = document.getElementById("results");
  const tabs = document.getElementById("tabs");
  const meta = document.getElementById("meta");
  const statusText = document.getElementById("statusText");
  const newTrip = document.getElementById("newTrip");

  const paneItinerary = document.getElementById("paneItinerary");
  const paneFlights = document.getElementById("paneFlights");
  const paneHotels = document.getElementById("paneHotels");

  // Persist the conversation thread across follow-up queries.
  let threadId = null;
  let stepTimers = [];

  /* ---------- tiny, safe markdown renderer ---------- */
  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function renderInline(text) {
    return text
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(?!\s)(.+?)(?!\s)\*/g, "<em>$1</em>")
      .replace(
        /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
        '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
      )
      .replace(
        /(^|[\s(])(https?:\/\/[^\s)]+)/g,
        '$1<a href="$2" target="_blank" rel="noopener noreferrer">$2</a>'
      );
  }

  function renderMarkdown(md) {
    if (!md) return '<p class="muted">No details returned.</p>';
    const lines = escapeHtml(md).split(/\r?\n/);
    let html = "";
    let listType = null; // "ul" | "ol"

    const closeList = () => {
      if (listType) { html += `</${listType}>`; listType = null; }
    };

    for (const raw of lines) {
      const line = raw.trim();
      if (!line) { closeList(); continue; }

      let m;
      if ((m = line.match(/^#{3,}\s+(.*)$/))) {
        closeList();
        html += `<h3>${renderInline(m[1])}</h3>`;
      } else if ((m = line.match(/^#{1,2}\s+(.*)$/))) {
        closeList();
        html += `<h2>${renderInline(m[1])}</h2>`;
      } else if ((m = line.match(/^[-*+]\s+(.*)$/))) {
        if (listType !== "ul") { closeList(); html += "<ul>"; listType = "ul"; }
        html += `<li>${renderInline(m[1])}</li>`;
      } else if ((m = line.match(/^\d+[.)]\s+(.*)$/))) {
        if (listType !== "ol") { closeList(); html += "<ol>"; listType = "ol"; }
        html += `<li>${renderInline(m[1])}</li>`;
      } else {
        closeList();
        html += `<p>${renderInline(line)}</p>`;
      }
    }
    closeList();
    return html;
  }

  /* ---------- loading choreography ---------- */
  function startLoading() {
    const order = ["flights", "hotels", "itinerary"];
    const items = order.map((k) => steps.querySelector(`[data-step="${k}"]`));
    items.forEach((el) => el.classList.remove("is-active", "is-done"));
    stepTimers.forEach(clearTimeout);
    stepTimers = [];

    items[0].classList.add("is-active");
    // advance the visual steps on a gentle cadence while the request runs
    stepTimers.push(setTimeout(() => {
      items[0].classList.replace("is-active", "is-done");
      items[1].classList.add("is-active");
    }, 2600));
    stepTimers.push(setTimeout(() => {
      items[1].classList.replace("is-active", "is-done");
      items[2].classList.add("is-active");
    }, 6200));
  }

  function finishLoading() {
    stepTimers.forEach(clearTimeout);
    stepTimers = [];
    steps.querySelectorAll("li").forEach((el) => {
      el.classList.remove("is-active");
      el.classList.add("is-done");
    });
  }

  /* ---------- view helpers ---------- */
  function show(el) { el.hidden = false; }
  function hide(el) { el.hidden = true; }

  function setStatus(text) { if (statusText) statusText.textContent = text; }

  function showError(message) {
    errorMsg.textContent = message;
    show(errorBox);
    errorBox.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  /* ---------- submit ---------- */
  async function handleSubmit(event) {
    event.preventDefault();
    const query = input.value.trim();
    if (!query) { input.focus(); return; }

    hide(errorBox);
    hide(results);
    show(loading);
    startLoading();
    submitBtn.disabled = true;
    setStatus("PLOTTING YOUR ROUTE…");

    try {
      const res = await fetch("/api/travel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_query: query, thread_id: threadId }),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok || data.success === false) {
        throw new Error(data.error || `Request failed (${res.status}).`);
      }

      finishLoading();
      threadId = data.thread_id || threadId;
      renderResults(data);
    } catch (err) {
      hide(loading);
      setStatus("DELAYED");
      showError(err.message || "Unexpected error contacting the concierge.");
    } finally {
      submitBtn.disabled = false;
    }
  }

  function renderResults(data) {
    paneItinerary.innerHTML = renderMarkdown(data.answer || data.itinerary);
    paneFlights.innerHTML = renderMarkdown(data.flight_results);
    paneHotels.innerHTML = renderMarkdown(data.hotel_results);

    const bits = [];
    if (data.thread_id) bits.push(`THREAD <b>${escapeHtml(data.thread_id)}</b>`);
    if (data.llm_calls != null) bits.push(`AGENT CALLS <b>${data.llm_calls}</b>`);
    bits.push("STATUS <b>ARRIVED</b>");
    meta.innerHTML = bits.join("&nbsp;&nbsp;·&nbsp;&nbsp;");

    setActiveTab("itinerary");
    hide(loading);
    setStatus("ITINERARY READY");
    show(results);
    results.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  /* ---------- tabs ---------- */
  function setActiveTab(name) {
    tabs.querySelectorAll(".tab").forEach((t) =>
      t.classList.toggle("is-active", t.dataset.tab === name)
    );
    document.querySelectorAll(".pane").forEach((p) =>
      p.classList.toggle("is-active", p.dataset.pane === name)
    );
  }

  /* ---------- events ---------- */
  form.addEventListener("submit", handleSubmit);

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  chips.addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    input.value = chip.textContent.replace(/→/g, "to");
    input.focus();
    form.requestSubmit();
  });

  tabs.addEventListener("click", (e) => {
    const tab = e.target.closest(".tab");
    if (tab) setActiveTab(tab.dataset.tab);
  });

  newTrip.addEventListener("click", () => {
    threadId = null;
    input.value = "";
    hide(results);
    setStatus("READY FOR DEPARTURE");
    document.getElementById("searchPanel").scrollIntoView({ behavior: "smooth" });
    input.focus();
  });
})();
