// Styled confirm dialog (DESIGN.md) for hx-confirm and bulk actions; Review keys: j/k move, a approve, r reject.
const dlg = () => document.getElementById("confirm");
document.addEventListener("htmx:confirm", (e) => {
  const elt = e.detail.elt;
  const verb = elt.dataset.verb;
  let msg = e.detail.question;
  if (verb) {
    const n = elt.closest("form")?.querySelectorAll("input[name=ids]:checked").length || 0;
    if (!n) return e.preventDefault();
    msg = `${verb} ${n} item${n === 1 ? "" : "s"}?`;
  }
  if (!msg) return;
  e.preventDefault();
  const d = dlg();
  d.querySelector("p").textContent = msg;
  const ok = d.querySelector("[data-ok]");
  ok.textContent = verb || elt.textContent.trim();
  ok.className = "btn " + (elt.classList.contains("danger") ? "danger" : "primary");
  d.returnValue = "";
  d.addEventListener("close", () => d.returnValue === "ok" && e.detail.issueRequest(true), { once: true });
  d.showModal();
});
document.addEventListener("keydown", (e) => {
  if (e.target.closest("input, select, textarea") || e.metaKey || e.ctrlKey) return;
  const rows = [...document.querySelectorAll("[data-review-row]")];
  if (!rows.length) return;
  const i = rows.findIndex((r) => r.contains(document.activeElement));
  if (e.key === "j" || e.key === "k") {
    const next = rows[Math.max(0, Math.min(rows.length - 1, i + (e.key === "j" ? 1 : -1)))];
    next.querySelector("input[type=checkbox]").focus();
  } else if ((e.key === "a" || e.key === "r") && i >= 0) {
    rows[i].querySelector(e.key === "a" ? "[data-act=approve]" : "[data-act=reject]").click();
  }
});
