document.addEventListener("DOMContentLoaded", () => {
  const $ = (id) => document.getElementById(id);

  const kpiTotalEarned = $("kpiTotalEarned");
  const kpiBalance = $("kpiBalance");
  const kpiWithdrawn = $("kpiWithdrawn");
  const kpiClients = $("kpiClients");
  const withdrawalsList = $("withdrawalsList");

  const affPromoCode = $("affPromoCode");
  const shareLinkInput = $("shareLinkInput");

  // Referrals elements
  const totalReferrals = $("totalReferrals");
  const activeReferrals = $("activeReferrals");
  const referralsList = $("referralsList");

  const copyCodeBtn = $("copyCodeBtn");
  const shareCodeBtn = $("shareCodeBtn");
  const copyLinkBtn = $("copyLinkBtn");
  const refreshBtn = $("refreshBtn");

  const openWithdrawModalBtn = $("openWithdrawModalBtn");
  const withdrawModal = $("withdrawModal");
  const withdrawModalBackdrop = $("withdrawModalBackdrop");
  const closeWithdrawModalBtn = $("closeWithdrawModalBtn");
  const withdrawAmountInput = $("withdrawAmountInput");
  const withdrawPaymentMethodInput = $("withdrawPaymentMethodInput");
  const submitWithdrawBtn = $("submitWithdrawBtn");

  let state = {
    promo_code: (affPromoCode?.textContent || "").trim(),
    share_link: "",
    balance: null,
  };

  function showToast(msg, type = "info") {
    const toast = document.createElement("div");
    toast.className = `toast toast--${type}`;
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.classList.add("show"), 10);
    setTimeout(() => {
      toast.classList.remove("show");
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  function fmtMoney(v) {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return "--";
    try {
      return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 }).format(Number(v));
    } catch {
      return String(v);
    }
  }

  function statusBadge(status) {
    const s = (status || "").toLowerCase();
    if (s === "paid") return { label: "Payé", cls: "text-emerald-700 dark:text-emerald-300" };
    if (s === "rejected") return { label: "Rejeté", cls: "text-rose-700 dark:text-rose-300" };
    if (s === "approved") return { label: "Approuvé", cls: "text-blue-700 dark:text-blue-300" };
    return { label: "En attente", cls: "text-amber-700 dark:text-amber-300" };
  }

  function isoToDate(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleString("fr-FR");
  }

  async function apiGet(url) {
    const res = await fetch(url, {
      method: "GET",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data?.success === false) {
      const msg = data?.error || `Erreur (${res.status})`;
      throw new Error(msg);
    }
    return data;
  }

  async function apiPost(url, body) {
    const res = await fetch(url, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data?.success === false) {
      const msg = data?.error || `Erreur (${res.status})`;
      throw new Error(msg);
    }
    return data;
  }

  function setSkeleton(on) {
    if (!withdrawalsList) return;
    if (on) {
      withdrawalsList.innerHTML = "";
      for (let i = 0; i < 3; i++) {
        const div = document.createElement("div");
        div.className = "gaboom-card p-3";
        div.innerHTML = `
          <div class="h-3 w-2/3 bg-white/10 rounded"></div>
          <div class="mt-2 h-3 w-1/3 bg-white/10 rounded"></div>
        `;
        withdrawalsList.appendChild(div);
      }
    }
  }

  function renderWithdrawals(withdrawals) {
    if (!withdrawalsList) return;
    const rows = withdrawals || [];
    if (!rows.length) {
      withdrawalsList.innerHTML = '<div class="empty-state">Aucun retrait</div>';
      return;
    }

    withdrawalsList.innerHTML = "";
    rows.forEach((w) => {
      const badge = statusBadge(w.status);
      const item = document.createElement("div");
      item.className = "gaboom-card p-3";
      item.innerHTML = `
        <div class="flex items-start justify-between gap-3">
          <div>
            <div class="text-sm font-semibold">${fmtMoney(w.amount)}</div>
            <div class="mt-1 text-xs text-slate-500 dark:text-slate-400">${isoToDate(w.created_at)}</div>
          </div>
          <div class="text-xs font-semibold ${badge.cls}">${badge.label}</div>
        </div>
      `;
      withdrawalsList.appendChild(item);
    });
  }

  function renderReferrals(referrals) {
    if (!referralsList) return;
    const rows = referrals || [];
    if (!rows.length) {
      referralsList.innerHTML = '<div class="empty-state">Aucun filleul</div>';
      return;
    }

    referralsList.innerHTML = "";
    rows.forEach((r) => {
      const item = document.createElement("div");
      item.className = "gaboom-card p-3";
      const isActive = r.has_borlette;
      const statusBadge = isActive 
        ? '<span class="text-xs font-semibold text-emerald-600 dark:text-emerald-300">Actif</span>'
        : '<span class="text-xs font-semibold text-slate-500 dark:text-slate-400">Inactif</span>';
      
      item.innerHTML = `
        <div class="flex items-start justify-between gap-3">
          <div>
            <div class="text-sm font-semibold">${r.username || r.email || 'Utilisateur'}</div>
            <div class="mt-1 text-xs text-slate-500 dark:text-slate-400">Rejoint: ${isoToDate(r.created_at)}</div>
          </div>
          ${statusBadge}
        </div>
      `;
      referralsList.appendChild(item);
    });
  }

  async function refreshAll() {
    setSkeleton(true);
    try {
      const bal = await apiGet("/api/affiliate/balance/");

      state.promo_code = bal.promo_code || state.promo_code;
      state.share_link = bal.share_link || (state.promo_code ? `http://site.com/?ref=${state.promo_code}` : "");
      state.balance = bal.balance;

      if (kpiTotalEarned) kpiTotalEarned.textContent = fmtMoney(bal.total_earned);
      if (kpiBalance) kpiBalance.textContent = fmtMoney(bal.balance);
      if (kpiWithdrawn) kpiWithdrawn.textContent = fmtMoney(bal.total_withdrawn);
      if (kpiClients) kpiClients.textContent = String(bal.clients_count ?? "--");

      if (affPromoCode) affPromoCode.textContent = state.promo_code || "";
      if (shareLinkInput) shareLinkInput.value = state.share_link || "";

      const w = await apiGet("/api/affiliate/withdrawals/");
      renderWithdrawals(w.withdrawals);

      // Load referrals
      try {
        const r = await apiGet("/api/affiliate/referrals/");
        if (totalReferrals) totalReferrals.textContent = String(r.total_count ?? "--");
        if (activeReferrals) activeReferrals.textContent = String(r.active_count ?? "--");
        renderReferrals(r.referrals);
      } catch (refErr) {
        // Referrals might not be implemented yet, don't break the whole page
        console.warn("Failed to load referrals:", refErr);
        if (referralsList) referralsList.innerHTML = '<div class="empty-state">Non disponible</div>';
      }
    } catch (e) {
      const msg = e?.message || "Erreur";
      if (msg.toLowerCase().includes("non autorisé") || msg.toLowerCase().includes("unauthorized")) {
        window.location.href = "/portal/login/";
        return;
      }
      showToast(msg, "error");
      if (withdrawalsList) withdrawalsList.innerHTML = '<div class="empty-state">Erreur de chargement</div>';
    }
  }

  async function copyToClipboard(text) {
    if (!text) return false;
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // Fallback for older browsers
      try {
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.left = "-999999px";
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand("copy");
        document.body.removeChild(textArea);
        return true;
      } catch {
        return false;
      }
    }
  }

  function openModal() {
    if (!withdrawModal) return;
    withdrawModal.style.display = "block";
    if (withdrawAmountInput) withdrawAmountInput.focus();
  }

  function closeModal() {
    if (!withdrawModal) return;
    withdrawModal.style.display = "none";
    if (withdrawAmountInput) withdrawAmountInput.value = "";
    if (withdrawPaymentMethodInput) withdrawPaymentMethodInput.value = "";
  }

  copyCodeBtn?.addEventListener("click", async () => {
    const ok = await copyToClipboard(state.promo_code);
    showToast(ok ? "Code copié" : "Impossible de copier", ok ? "success" : "error");
  });

  copyLinkBtn?.addEventListener("click", async () => {
    const ok = await copyToClipboard(state.share_link);
    showToast(ok ? "Lien copié" : "Impossible de copier", ok ? "success" : "error");
  });

  shareCodeBtn?.addEventListener("click", async () => {
    const text = state.share_link || state.promo_code;
    if (navigator.share) {
      try {
        await navigator.share({ title: "Mon code promo", text, url: state.share_link || undefined });
      } catch {
        // ignore cancel
      }
      return;
    }
    const ok = await copyToClipboard(text);
    showToast(ok ? "Copié (partage non supporté)" : "Impossible de copier", ok ? "success" : "error");
  });

  refreshBtn?.addEventListener("click", () => refreshAll());

  openWithdrawModalBtn?.addEventListener("click", () => openModal());
  closeWithdrawModalBtn?.addEventListener("click", () => closeModal());
  withdrawModalBackdrop?.addEventListener("click", () => closeModal());

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });

  submitWithdrawBtn?.addEventListener("click", async () => {
    const amount = Number(withdrawAmountInput?.value || 0);
    const payment_method = (withdrawPaymentMethodInput?.value || "").trim();

    if (!amount || amount <= 0) {
      showToast("Montant invalide", "error");
      return;
    }

    submitWithdrawBtn.disabled = true;
    const original = submitWithdrawBtn.textContent;
    submitWithdrawBtn.textContent = "Envoi...";

    try {
      await apiPost("/api/affiliate/withdraw/", { amount, payment_method });
      showToast("Demande envoyée", "success");
      closeModal();
      await refreshAll();
    } catch (e) {
      showToast(e?.message || "Erreur", "error");
    } finally {
      submitWithdrawBtn.disabled = false;
      submitWithdrawBtn.textContent = original;
    }
  });

  refreshAll();
});
