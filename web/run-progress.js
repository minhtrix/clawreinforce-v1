function duration(milliseconds) {
  const seconds = Math.max(0, Math.round(milliseconds / 1000));
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, "0")}s`;
}


export function createRunProgress({ phase, bar, count, elapsed, eta }) {
  let runStarted = null;
  let phaseStarted = null;
  let completed = 0;
  let total = 0;
  let timer = null;

  function paintTime() {
    if (!runStarted) return;
    elapsed.textContent = `elapsed ${duration(Date.now() - runStarted)}`;
    if (completed > 0 && total > completed && phaseStarted) {
      const remaining = ((Date.now() - phaseStarted) / completed) * (total - completed);
      eta.textContent = `ETA ~${duration(remaining)} · observed this phase`;
    } else if (total > 0 && completed >= total) {
      eta.textContent = "phase complete";
    } else {
      eta.textContent = "ETA waits for the first completed unit";
    }
  }

  function ensureTimer() {
    if (timer) clearInterval(timer);
    timer = setInterval(paintTime, 250);
  }

  return {
    start(label = "Run accepted") {
      runStarted = Date.now();
      phaseStarted = runStarted;
      completed = 0;
      total = 0;
      phase.textContent = label;
      count.textContent = "waiting for work units";
      bar.removeAttribute("value");
      ensureTimer();
      paintTime();
    },
    beginPhase(label, nextTotal) {
      phaseStarted = Date.now();
      completed = 0;
      total = Number(nextTotal) || 0;
      phase.textContent = label;
      count.textContent = total ? `0 / ${total}` : "in progress";
      bar.max = Math.max(total, 1);
      bar.value = 0;
      paintTime();
    },
    update(nextCompleted, nextTotal, label = "") {
      completed = Number(nextCompleted) || 0;
      total = Number(nextTotal) || total;
      if (label) phase.textContent = label;
      count.textContent = total ? `${completed} / ${total}` : `${completed} completed`;
      bar.max = Math.max(total, 1);
      bar.value = Math.min(completed, bar.max);
      paintTime();
    },
    finish(label = "Complete") {
      if (timer) clearInterval(timer);
      timer = null;
      phase.textContent = label;
      if (total) {
        completed = total;
        bar.max = total;
        bar.value = total;
        count.textContent = `${total} / ${total}`;
      }
      paintTime();
      eta.textContent = "complete";
    },
    fail(label = "Failed") {
      if (timer) clearInterval(timer);
      timer = null;
      phase.textContent = label;
      eta.textContent = "no estimate";
      paintTime();
    },
  };
}
