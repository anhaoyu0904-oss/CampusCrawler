const state = { mode: "logo", items: [] };
const labels = {
  logo: ["学校标识结果", "查找 Logo、校徽和视觉识别素材。"],
  notice: ["校园通知结果", "查找公开通知、公告和公示。"],
  admission: ["招生信息结果", "查找招生简章、复试和调剂信息。"],
};

const $ = (selector) => document.querySelector(selector);
const results = $("#results");

function setStatus(text, kind = "") {
  $("#status").textContent = text;
  $("#status").className = `status ${kind}`;
}

function renderEmpty(text) {
  results.innerHTML = `<div class="empty">${text}</div>`;
}

function updateMetrics(data = {}) {
  $("#resultCount").textContent = (data.items || []).length;
  $("#pageCount").textContent = (data.visited_pages || []).length;
  $("#skipCount").textContent = (data.skipped || []).length;
  $("#errorCount").textContent = (data.errors || []).length;
}

function render(data) {
  state.items = data.items || [];
  updateMetrics(data);
  $("#exportButton").disabled = state.items.length === 0;
  results.innerHTML = "";
  if (!state.items.length) {
    renderEmpty("没有找到符合条件的结果。可以尝试输入更具体的栏目网址。");
    return;
  }

  for (const item of state.items) {
    const node = $("#resultTemplate").content.cloneNode(true);
    const preview = node.querySelector(".preview");
    node.querySelector("h3").textContent = item.title;
    node.querySelector(".score").textContent = `${item.score} 分`;
    node.querySelector(".meta").textContent = [item.date, item.file_type, labels[item.category][0].replace("结果", "")]
      .filter(Boolean).join(" · ");
    node.querySelector(".reason").textContent = item.reason;
    const source = node.querySelector(".source");
    source.textContent = item.url;
    source.href = item.url;
    node.querySelector(".open").href = item.url;

    if (item.preview_url) {
      const image = document.createElement("img");
      image.src = item.preview_url;
      image.alt = item.title;
      image.referrerPolicy = "no-referrer";
      image.onerror = () => { preview.textContent = "无法预览"; };
      preview.append(image);
    } else {
      preview.textContent = item.file_type || (item.category === "notice" ? "通知" : "网页");
    }

    const download = node.querySelector(".download");
    if (!item.file_type) {
      download.hidden = true;
    } else {
      download.addEventListener("click", () => downloadItem(item, download));
    }
    results.append(node);
  }
}

async function downloadItem(item, button) {
  button.disabled = true;
  button.textContent = "下载中";
  try {
    const response = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: item.url }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "下载失败");
    button.textContent = "已保存";
    window.open(data.download_url, "_blank");
  } catch (error) {
    button.disabled = false;
    button.textContent = "重试";
    alert(error.message);
  }
}

document.querySelectorAll(".mode").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".mode").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.mode = button.dataset.mode;
    $("#resultTitle").textContent = labels[state.mode][0];
    $("#resultHint").textContent = labels[state.mode][1];
    state.items = [];
    updateMetrics();
    $("#exportButton").disabled = true;
    renderEmpty("尚未开始采集");
    setStatus("等待任务");
  });
});

$("#collectForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("#collectButton");
  button.disabled = true;
  button.textContent = "采集中";
  setStatus("正在访问", "running");
  renderEmpty("正在读取公开网页，请稍候...");
  updateMetrics();
  try {
    const response = await fetch("/api/collect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: $("#siteUrl").value,
        mode: state.mode,
        max_pages: Number($("#maxPages").value),
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "采集失败");
    render(data);
    setStatus("任务完成", "done");
  } catch (error) {
    renderEmpty(error.message);
    setStatus("任务失败", "failed");
  } finally {
    button.disabled = false;
    button.textContent = "开始采集";
  }
});

$("#exportButton").addEventListener("click", async () => {
  const response = await fetch("/api/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items: state.items, format: $("#exportFormat").value }),
  });
  const data = await response.json();
  if (!response.ok) {
    alert(data.error || "导出失败");
    return;
  }
  window.open(data.download_url, "_blank");
});
