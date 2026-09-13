const $ = (selector) => document.querySelector(selector);

const source = $("#source");
const highlight = $("#highlight");
const stdin = $("#stdin");
const inputPanel = $("#input-panel");
const examplesSelect = $("#examples");
const sendButton = $("#send");
const shareButton = $("#share");
const emlInput = $("#eml-file");
const attachmentBox = $("#attachment");
const attachmentName = $("#attachment-name");
const editor = $("#editor");
const dropzone = $("#dropzone");
const reply = $("#reply");
const replyBody = $("#reply-body");
const replyFoot = $("#reply-foot");
const replySubject = $("#reply-subject");
const stamp = $("#stamp");

const exampleInfo = new Map();
let attached = null; // a File, when sending a saved .eml instead of the draft

const isMac = /Mac|iPhone|iPad/.test(navigator.userAgent);
document.querySelectorAll("kbd").forEach((key) => { key.textContent = isMac ? "⌘↵" : "Ctrl ↵"; });

// ------------------------------------------------------------ highlighting

const SIGN_OFFS = new Set(["best", "regards", "thanks", "cheers", "warm regards", "kind regards",
  "best regards", "many thanks", "sincerely"]);

function escapeHtml(text) {
  return text.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function inlineCode(text) {
  return escapeHtml(text).replace(/`([^`]+)`/g, "<code>$1</code>");
}

function paintLine(line) {
  const quote = line.match(/^(\s*>(?:\s*>)*\s?)/);
  const prefix = quote ? quote[1] : "";
  const rest = line.slice(prefix.length);
  const text = rest.trim();
  let kind = "";
  if (/^(subject|cc):/i.test(text)) kind = "hdr";
  else if (/^(hi|hello|hey|dear)\b.*,$/i.test(text)) kind = "greet";
  else if (text.endsWith(",") && SIGN_OFFS.has(text.slice(0, -1).toLowerCase())) kind = "signoff";
  else if (/^on .*wrote:$/i.test(text) || /^(from|sent):/i.test(text)) kind = "thread";
  else if (/^(fyi\b|(p\.?\s?)+s\b)/i.test(text)) kind = "comment";
  else if (/^sent from my iphone$/i.test(text)) kind = "pragma";
  let body = escapeHtml(rest).replace(/&quot;(.*?)&quot;/g, '<span class="str">&quot;$1&quot;</span>');
  if (kind) body = `<span class="${kind}">${body}</span>`;
  if (!prefix) return body;
  const depth = Math.min((prefix.match(/>/g) || []).length, 4);
  return `<span class="q q${depth}">${escapeHtml(prefix)}</span>${body}`;
}

function paint() {
  highlight.innerHTML = source.value.split("\n").map(paintLine).join("\n") + "\n ";
  syncScroll();
}

function syncScroll() {
  highlight.parentElement.scrollTop = source.scrollTop;
  highlight.parentElement.scrollLeft = source.scrollLeft;
}

source.addEventListener("input", () => { paint(); saveDraft(); });
source.addEventListener("scroll", syncScroll);
source.addEventListener("keydown", (event) => {
  if (event.key !== "Tab" || event.shiftKey || event.metaKey || event.ctrlKey || event.altKey) return;
  event.preventDefault();
  if (!document.execCommand("insertText", false, "> ")) {
    source.setRangeText("> ", source.selectionStart, source.selectionEnd, "end");
    paint();
  }
});

// ------------------------------------------------------------ drafts and share links

function saveDraft() {
  try { localStorage.setItem("regards-draft", JSON.stringify({ s: source.value, i: stdin.value })); } catch {}
}

function readDraft() {
  try { return JSON.parse(localStorage.getItem("regards-draft") || "null"); } catch { return null; }
}

stdin.addEventListener("input", saveDraft);

function toBase64Url(bytes) {
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromBase64Url(text) {
  return Uint8Array.from(atob(text.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
}

async function pack(data) {
  const bytes = new TextEncoder().encode(JSON.stringify(data));
  if (!("CompressionStream" in window)) return "u" + toBase64Url(bytes);
  const stream = new Blob([bytes]).stream().pipeThrough(new CompressionStream("deflate-raw"));
  return "z" + toBase64Url(new Uint8Array(await new Response(stream).arrayBuffer()));
}

async function unpack(text) {
  const bytes = fromBase64Url(text.slice(1));
  if (text[0] === "u") return JSON.parse(new TextDecoder().decode(bytes));
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
  return JSON.parse(await new Response(stream).text());
}

function flash(button, text) {
  button.dataset.label ||= button.textContent;
  button.textContent = text;
  clearTimeout(button.flashTimer);
  button.flashTimer = setTimeout(() => { button.textContent = button.dataset.label; }, 1800);
}

shareButton.addEventListener("click", async () => {
  if (attached) return flash(shareButton, "Attachments can't go in a link");
  history.replaceState(null, "", "#m=" + await pack({ s: source.value, i: stdin.value }));
  try {
    await navigator.clipboard.writeText(location.href);
    flash(shareButton, "Link copied");
  } catch {
    flash(shareButton, "Link is in the address bar");
  }
});

// ------------------------------------------------------------ attachments

function formatSize(bytes) {
  return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`;
}

function attach(file) {
  attached = file;
  attachmentName.textContent = `${file.name} · ${formatSize(file.size)}`;
  attachmentBox.hidden = false;
  editor.classList.add("covered");
}

function detach() {
  attached = null;
  attachmentBox.hidden = true;
  editor.classList.remove("covered");
  emlInput.value = "";
}

$("#detach").addEventListener("click", detach);
emlInput.addEventListener("change", () => { if (emlInput.files[0]) attach(emlInput.files[0]); });

["dragenter", "dragover"].forEach((type) => editor.addEventListener(type, (event) => {
  event.preventDefault();
  dropzone.hidden = false;
}));
editor.addEventListener("dragleave", (event) => {
  if (!editor.contains(event.relatedTarget)) dropzone.hidden = true;
});
editor.addEventListener("drop", async (event) => {
  event.preventDefault();
  dropzone.hidden = true;
  const file = event.dataTransfer.files[0];
  if (!file) return;
  if (/\.eml$/i.test(file.name) || file.type === "message/rfc822") return attach(file);
  detach();
  source.value = await file.text();
  paint();
  saveDraft();
});

// ------------------------------------------------------------ examples

async function loadExamples() {
  const list = await (await fetch("/api/examples")).json();
  for (const example of list) {
    exampleInfo.set(example.name, example);
    const option = document.createElement("option");
    option.value = example.name;
    option.textContent = example.subject ? `${example.subject}  (${example.name})` : example.name;
    examplesSelect.append(option);
  }
}

async function openExample(name) {
  const example = exampleInfo.get(name);
  if (!example) return;
  const response = await fetch(`/api/examples/${encodeURIComponent(name)}`);
  if (example.kind === "eml") {
    attach(new File([await response.blob()], name, { type: "message/rfc822" }));
  } else {
    detach();
    source.value = await response.text();
    paint();
  }
  stdin.value = example.stdin || "";
  inputPanel.open = Boolean(example.stdin);
  saveDraft();
}

examplesSelect.addEventListener("change", () => openExample(examplesSelect.value));

// ------------------------------------------------------------ sending

const TONE = {
  sent: { stamp: "Sent", signOff: "Best,", ink: "blue" },
  regards: { stamp: "Noted.", signOff: "Regards,", ink: "red" },
  error: { stamp: "Please advise", signOff: "Per my last email,", ink: "red" },
  timeout: { stamp: "Over time", signOff: "Let's continue next week,", ink: "ochre" },
  output_limit: { stamp: "TL;DR", signOff: "Too long, didn't read,", ink: "ochre" },
  too_long: { stamp: "TL;DR", signOff: "Too long, didn't read,", ink: "ochre" },
  internal: { stamp: "IT ticket", signOff: "Apologies,", ink: "grey" },
};

function subjectLine() {
  if (attached) return `Re: ${attached.name}`;
  const match = source.value.match(/^\s*subject:\s*(.+)$/im);
  return match ? `Re: ${match[1].trim()}` : "Re: (no subject)";
}

function showReply(result) {
  const tone = TONE[result.status] || TONE.internal;
  const lines = (result.stderr || "").split("\n").filter((line) => line.trim());
  const warnings = lines.filter((line) => line.startsWith("warning:")).map((line) => line.replace(/^warning:\s*/, ""));
  let problems = lines.filter((line) => !line.startsWith("warning:")).map((line) => line.replace(/^error:\s*/, "").trim());
  if (result.status === "internal" && problems.length > 1) problems = [problems.at(-1)];

  const parts = ['<p class="salutation">Hi,</p>'];
  if (result.status === "timeout") {
    parts.push('<p class="complaint">Your email ran past the time I had blocked for it, so I stopped reading.</p>');
  }
  if (result.status === "output_limit") {
    parts.push('<p class="complaint">That was a lot of output. I stopped after the first 100,000 characters.</p>');
  }
  if (result.stdout) {
    parts.push(`<pre class="output">${escapeHtml(result.stdout)}</pre>`);
  } else if (result.status === "sent" || result.status === "regards") {
    parts.push('<p class="quiet">Nothing to report.</p>');
  }
  if (problems.length) {
    parts.push(`<div class="complaint">${problems.map((line) => `<p>${inlineCode(line)}</p>`).join("")}</div>`);
  }
  if (result.status === "internal") {
    parts.push('<p class="quiet">This is a bug in the interpreter, not in your email.</p>');
  }
  if (warnings.length) {
    parts.push(`<ul class="ps">${warnings.map((w) => `<li><span>P.S.</span> ${inlineCode(w)}</li>`).join("")}</ul>`);
  }
  parts.push(`<p class="closing">${escapeHtml(tone.signOff)}<br>regards.py</p>`);

  replyBody.innerHTML = parts.join("");
  replySubject.textContent = subjectLine();
  const exit = result.exit_code == null ? "no exit code" : `exit code ${result.exit_code}`;
  replyFoot.textContent = `${exit} · replied in ${result.duration_ms} ms`;

  stamp.textContent = tone.stamp;
  stamp.dataset.ink = tone.ink;
  stamp.hidden = false;
  for (const element of [stamp, reply]) element.classList.remove("slam", "arrived");
  void reply.offsetWidth; // restart the animations
  stamp.classList.add("slam");
  reply.classList.add("arrived");
}

async function send() {
  if (sendButton.disabled) return;
  sendButton.disabled = true;
  sendButton.classList.add("sending");
  try {
    let response;
    if (attached) {
      const form = new FormData();
      form.append("eml", attached);
      form.append("stdin", stdin.value);
      response = await fetch("/api/run", { method: "POST", body: form });
    } else {
      response = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: source.value, stdin: stdin.value }),
      });
    }
    if (response.status === 413) {
      showReply({ status: "too_long", stdout: "", exit_code: null, duration_ms: 0,
        stderr: "error: this email is too long to read. Can you send a summary?" });
    } else if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    } else {
      showReply(await response.json());
    }
  } catch (error) {
    showReply({ status: "internal", stdout: "", exit_code: null, duration_ms: 0,
      stderr: `error: the mail server is down (${error.message}). Please try again later.` });
  } finally {
    sendButton.disabled = false;
    sendButton.classList.remove("sending");
  }
}

sendButton.addEventListener("click", send);
document.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    event.preventDefault();
    send();
  }
});

// ------------------------------------------------------------ start

async function start() {
  await loadExamples().catch(() => {});
  const shared = location.hash.match(/^#m=(.+)$/);
  const draft = readDraft();
  if (shared) {
    try {
      const data = await unpack(shared[1]);
      source.value = data.s || "";
      stdin.value = data.i || "";
      inputPanel.open = Boolean(data.i);
    } catch {
      source.value = "";
    }
  } else if (draft && draft.s) {
    source.value = draft.s;
    stdin.value = draft.i || "";
    inputPanel.open = Boolean(draft.i);
  } else if (exampleInfo.has("countdown.rgrd")) {
    examplesSelect.value = "countdown.rgrd";
    await openExample("countdown.rgrd");
  }
  paint();
}

start();
