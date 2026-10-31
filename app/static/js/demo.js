(function () {
  const page = document.querySelector("[data-demo-page]");
  if (!page) return;

  const stages = [
    {label:"Registration", status:"Registration open", description:"Participant records are validated and ready for team formation.", calloutTitle:"Registration is ready", callout:"HACKOS keeps participant records clean before the event begins.", log:"248 participant records confirmed.", metrics:{teams:62,checkedIn:0,submissions:0,evaluations:"0%"}, details:{teams:"synthetic teams",checkedIn:"event day ahead",submissions:"not open yet",evaluations:"judging not started"}},
    {label:"Teams", status:"Teams formed", description:"Participants become accountable teams with clear rosters and ownership.", calloutTitle:"Teams have a shape", callout:"Rosters and membership history stay together as teams take form.", log:"62 teams formed from the confirmed registrations.", metrics:{teams:62,checkedIn:0,submissions:0,evaluations:"0%"}, details:{teams:"active teams",checkedIn:"event day ahead",submissions:"not open yet",evaluations:"judging not started"}},
    {label:"Check-in", status:"Event day live", description:"The room is opening. QR and manual check-in create one attendance record per participant.", calloutTitle:"The doors are open", callout:"Successful scans are recorded once; duplicate and invalid scans receive clear simulated statuses.", log:"196 successful check-ins; duplicate and invalid scans handled.", metrics:{teams:62,checkedIn:196,submissions:0,evaluations:"0%"}, details:{teams:"active teams",checkedIn:"79% present",submissions:"not open yet",evaluations:"judging not started"}},
    {label:"Submissions", status:"Submissions received", description:"Teams send their work through a deadline-aware submission flow.", calloutTitle:"Work is in", callout:"Project links and server-recorded timestamps give every submission a reliable trail.", log:"48 project submissions received from 62 teams.", metrics:{teams:62,checkedIn:196,submissions:48,evaluations:"0%"}, details:{teams:"active teams",checkedIn:"79% present",submissions:"all teams submitted",evaluations:"judging not started"}},
    {label:"Judging", status:"Judging in progress", description:"Assigned judges score only their projects against weighted rubric criteria.", calloutTitle:"Scores are accountable", callout:"Assignments, weighted criteria and private evaluations keep judging focused and fair.", log:"All judge assignments active; evaluations are 100% submitted.", metrics:{teams:62,checkedIn:196,submissions:48,evaluations:"100%"}, details:{teams:"active teams",checkedIn:"79% present",submissions:"48 submitted",evaluations:"complete"}},
    {label:"Results", status:"Ready to publish", description:"Submitted evaluations become a deterministic, organizer-controlled leaderboard.", calloutTitle:"Results are ready", callout:"HACKOS keeps results private until the organizer explicitly publishes them.", log:"Leaderboard calculated from submitted evaluations.", metrics:{teams:62,checkedIn:196,submissions:48,evaluations:"100%"}, details:{teams:"active teams",checkedIn:"79% present",submissions:"48 submitted",evaluations:"submitted judges"}},
  ];
  const leaderboard = [["01","Byte Me","HealthTech","92.4","3 / 3"],["02","Null Pointers","FinTech","89.1","3 / 3"],["03","Kernel Panic","EdTech","86.7","3 / 3"],["04","Stack Smash","Open Innovation","81.3","2 / 3"]];
  let current = 0, timer = null, running = false;
  const $ = (selector) => page.querySelector(selector);
  const metric = (name) => $(`[data-demo-metric="${name}"]`);
  function render(index, logEntry) {
    const stage = stages[index];
    current = index;
    $("[data-demo-stage-label]").textContent = stage.label;
    $("[data-demo-stage-index]").textContent = String(index + 1).padStart(2, "0");
    $("[data-demo-status]").textContent = stage.status;
    $("[data-demo-stage-description]").textContent = stage.description;
    $("[data-demo-callout-title]").textContent = stage.calloutTitle;
    $("[data-demo-callout]").textContent = stage.callout;
    $("[data-demo-callout-icon]").textContent = String(index + 1).padStart(2, "0");
    Object.entries(stage.metrics).forEach(([name, value]) => { metric(name).textContent = value; });
    Object.entries(stage.details).forEach(([name, value]) => { $(`[data-demo-detail="${name}"]`).textContent = value; });
    $("[data-demo-progress]").style.width = `${((index + 1) / stages.length) * 100}%`;
    page.querySelectorAll("[data-demo-step]").forEach((step) => {
      const stepIndex = Number(step.dataset.demoStep);
      step.classList.toggle("is-active", stepIndex === index);
      step.classList.toggle("is-complete", stepIndex < index);
    });
    if (logEntry) {
      const log = $("[data-demo-log]");
      log.querySelectorAll(".is-current").forEach((item) => item.classList.remove("is-current"));
      const item = document.createElement("li");
      item.className = "is-current";
      item.innerHTML = `<time>${String(9 + index).padStart(2, "0")}:0${index}</time><span>${logEntry}</span>`;
      log.appendChild(item);
      item.scrollIntoView({block:"nearest", behavior:"smooth"});
    }
    if (index === stages.length - 1) {
      $("[data-demo-leaderboard]").innerHTML = `<div class="demo-leaderboard-heading"><span>Final leaderboard</span><small>synthetic scores · submitted evaluations</small></div>${leaderboard.map(row => `<div class="demo-rank-row"><b>${row[0]}</b><span><strong>${row[1]}</strong><small>${row[2]}</small></span><em>${row[3]}</em><small>${row[4]} judges</small></div>`).join("")}`;
    } else if (index === 0) {
      $("[data-demo-leaderboard]").innerHTML = '<div class="demo-leaderboard-empty"><span>06</span><strong>Complete the walkthrough</strong><p>The leaderboard appears when evaluations are submitted.</p></div>';
    }
    updateControls();
  }
  function updateControls() {
    const finished = current === stages.length - 1;
    $("[data-demo-action=start]").disabled = running || current > 0;
    $("[data-demo-action=pause]").disabled = !running;
    $("[data-demo-action=resume]").disabled = running || current === 0 || finished;
    $("[data-demo-action=previous]").disabled = current === 0 || running;
    $("[data-demo-action=next]").disabled = running || finished;
    $("[data-demo-hint]").textContent = running ? "Playing the synthetic event timeline…" : finished ? "Walkthrough complete. Reset to run it again." : "Start the walkthrough or move one step at a time.";
  }
  function stop() { if (timer) window.clearInterval(timer); timer = null; running = false; updateControls(); }
  function advance() { if (current >= stages.length - 1) return stop(); render(current + 1, stages[current + 1].log); }
  function start() { if (current !== 0) return; running = true; render(0, "Walkthrough started: registration is the single source of truth."); timer = window.setInterval(advance, 2600); updateControls(); }
  function reset() { stop(); $("[data-demo-log]").innerHTML = '<li class="is-current"><time>09:00</time><span>Demo ready — waiting to start</span></li>'; render(0); }
  page.querySelectorAll("[data-demo-action]").forEach((button) => button.addEventListener("click", () => {
    const action = button.dataset.demoAction;
    if (action === "start") start();
    if (action === "pause") stop();
    if (action === "resume") { running = true; timer = window.setInterval(advance, 2600); updateControls(); }
    if (action === "next") render(Math.min(current + 1, stages.length - 1), stages[Math.min(current + 1, stages.length - 1)].log);
    if (action === "previous") render(Math.max(current - 1, 0));
    if (action === "reset") reset();
  }));
  page.querySelectorAll("[data-demo-step]").forEach((button) => button.addEventListener("click", () => {
    if (!running) render(Number(button.dataset.demoStep), stages[Number(button.dataset.demoStep)].log);
  }));
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    page.classList.add("demo-reduced-motion");
  }
  render(0);
}());
