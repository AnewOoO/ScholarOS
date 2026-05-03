(function () {
  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function escapeAttr(value) {
    return escapeHtml(value).replaceAll("`", "&#096;");
  }

  function normalizeNewlines(value) {
    return String(value ?? "").replace(/\r\n?/g, "\n");
  }

  function renderInlineMarkdown(value) {
    const codeTokens = [];
    let text = String(value ?? "").replace(/`([^`\n]+)`/g, (_, code) => {
      const token = `@@INLINE_CODE_${codeTokens.length}@@`;
      codeTokens.push(`<code>${escapeHtml(code)}</code>`);
      return token;
    });

    text = escapeHtml(text)
      .replace(
        /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
        (_, label, url) => `<a href="${escapeAttr(url)}" target="_blank" rel="noreferrer">${label}</a>`,
      )
      .replace(/~~([^~]+)~~/g, "<del>$1</del>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/__([^_]+)__/g, "<strong>$1</strong>")
      .replace(/(^|[\s(])\*([^*\n]+)\*/g, "$1<em>$2</em>")
      .replace(/(^|[\s(])_([^_\n]+)_/g, "$1<em>$2</em>");

    return text.replace(/@@INLINE_CODE_(\d+)@@/g, (_, index) => codeTokens[Number(index)] || "");
  }

  function countIndent(line) {
    const match = String(line ?? "")
      .replace(/\t/g, "  ")
      .match(/^ */);
    return match ? match[0].length : 0;
  }

  function matchFence(line) {
    return line.trim().match(/^(```|~~~)\s*([\w.+-]*)\s*$/);
  }

  function matchHeading(line) {
    return line.trim().match(/^(#{1,4})\s+(.+)$/);
  }

  function matchListItem(line) {
    const expanded = String(line ?? "").replace(/\t/g, "  ");
    const match = expanded.match(/^(\s*)([-*+]|\d+[.)])\s+(.+)$/);
    if (!match) return null;
    return {
      indent: match[1].length,
      type: /^\d/.test(match[2]) ? "ol" : "ul",
      content: match[3],
    };
  }

  function splitTableRow(line) {
    let text = String(line ?? "").trim();
    if (text.startsWith("|")) text = text.slice(1);
    if (text.endsWith("|")) text = text.slice(0, -1);

    const cells = [];
    let cell = "";
    let escaping = false;

    for (const char of text) {
      if (escaping) {
        cell += char === "|" ? "|" : `\\${char}`;
        escaping = false;
        continue;
      }
      if (char === "\\") {
        escaping = true;
        continue;
      }
      if (char === "|") {
        cells.push(cell.trim());
        cell = "";
        continue;
      }
      cell += char;
    }

    if (escaping) cell += "\\";
    cells.push(cell.trim());
    return cells;
  }

  function parseTableDelimiter(line) {
    const cells = splitTableRow(line);
    if (!cells.length) return null;

    const alignments = [];
    for (const cell of cells) {
      const value = cell.replace(/\s+/g, "");
      if (!/^:?-{3,}:?$/.test(value)) return null;
      if (value.startsWith(":") && value.endsWith(":")) {
        alignments.push("center");
      } else if (value.endsWith(":")) {
        alignments.push("right");
      } else if (value.startsWith(":")) {
        alignments.push("left");
      } else {
        alignments.push("");
      }
    }
    return alignments;
  }

  function isTableStart(lines, index) {
    if (index + 1 >= lines.length) return false;
    if (!lines[index].includes("|")) return false;
    const delimiter = parseTableDelimiter(lines[index + 1]);
    return Boolean(delimiter && splitTableRow(lines[index]).length >= delimiter.length);
  }

  function isHorizontalRule(line) {
    return /^(-{3,}|\*{3,}|_{3,})$/.test(line.trim());
  }

  function isBlockStart(lines, index) {
    const trimmed = lines[index].trim();
    if (!trimmed) return true;
    return Boolean(
      matchFence(trimmed) ||
        matchHeading(trimmed) ||
        isHorizontalRule(trimmed) ||
        trimmed.startsWith(">") ||
        matchListItem(lines[index]) ||
        isTableStart(lines, index),
    );
  }

  function renderParagraph(lines) {
    const content = lines.map((line) => renderInlineMarkdown(line.trim())).join("<br>");
    return content ? `<p>${content}</p>` : "";
  }

  function renderCodeBlock(lines, startIndex) {
    const opener = matchFence(lines[startIndex]);
    const fence = opener[1];
    const language = opener[2] || "";
    const codeLines = [];
    let index = startIndex + 1;

    while (index < lines.length) {
      const trimmed = lines[index].trim();
      if (trimmed.startsWith(fence)) {
        index += 1;
        break;
      }
      codeLines.push(lines[index]);
      index += 1;
    }

    const className = language ? ` class="language-${escapeAttr(language)}"` : "";
    return {
      html: `<pre><code${className}>${escapeHtml(codeLines.join("\n"))}</code></pre>`,
      nextIndex: index,
    };
  }

  function renderTable(lines, startIndex) {
    const headers = splitTableRow(lines[startIndex]);
    const alignments = parseTableDelimiter(lines[startIndex + 1]) || [];
    const rows = [];
    let index = startIndex + 2;

    while (index < lines.length) {
      const trimmed = lines[index].trim();
      if (!trimmed || !trimmed.includes("|")) break;
      rows.push(splitTableRow(lines[index]));
      index += 1;
    }

    const columnCount = Math.max(headers.length, alignments.length, ...rows.map((row) => row.length));
    const alignClass = (columnIndex) => {
      const alignment = alignments[columnIndex];
      return alignment ? ` class="align-${alignment}"` : "";
    };
    const renderCell = (tag, cells, columnIndex) =>
      `<${tag}${alignClass(columnIndex)}>${renderInlineMarkdown(cells[columnIndex] || "")}</${tag}>`;

    const head = Array.from({ length: columnCount }, (_, index) => renderCell("th", headers, index)).join("");
    const body = rows
      .map((row) => `<tr>${Array.from({ length: columnCount }, (_, index) => renderCell("td", row, index)).join("")}</tr>`)
      .join("");

    return {
      html: `<div class="markdown-table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`,
      nextIndex: index,
    };
  }

  function renderQuote(lines, startIndex) {
    const quoteLines = [];
    let index = startIndex;

    while (index < lines.length) {
      const match = lines[index].trim().match(/^>\s?(.*)$/);
      if (!match) break;
      quoteLines.push(match[1]);
      index += 1;
    }

    return {
      html: `<blockquote>${renderMarkdown(quoteLines.join("\n"))}</blockquote>`,
      nextIndex: index,
    };
  }

  function renderListItemContent(lines) {
    if (!lines.length) return "";
    const task = lines[0].match(/^\[([ xX])\]\s+(.+)$/);
    if (!task) return renderParagraph(lines);

    const checked = task[1].toLowerCase() === "x" ? " checked" : "";
    const firstLine = `<input type="checkbox" disabled${checked}> ${renderInlineMarkdown(task[2])}`;
    const rest = lines.slice(1).map((line) => renderInlineMarkdown(line.trim()));
    return `<p class="task-list-item">${[firstLine, ...rest].join("<br>")}</p>`;
  }

  function renderListItem(lines, startIndex, baseIndent) {
    const item = matchListItem(lines[startIndex]);
    const parts = [];
    let paragraphLines = item.content ? [item.content] : [];
    let index = startIndex + 1;

    const flushParagraph = () => {
      if (!paragraphLines.length) return;
      parts.push(renderListItemContent(paragraphLines));
      paragraphLines = [];
    };

    while (index < lines.length) {
      const trimmed = lines[index].trim();

      if (!trimmed) {
        flushParagraph();
        index += 1;
        if (index >= lines.length) break;

        const nextItem = matchListItem(lines[index]);
        if (nextItem && nextItem.indent <= baseIndent) break;
        if (!nextItem && countIndent(lines[index]) <= baseIndent) break;
        continue;
      }

      const nextItem = matchListItem(lines[index]);
      if (nextItem) {
        if (nextItem.indent <= baseIndent) break;
        flushParagraph();
        const nested = renderList(lines, index, nextItem.indent);
        parts.push(nested.html);
        index = nested.nextIndex;
        continue;
      }

      if (countIndent(lines[index]) <= baseIndent || isBlockStart(lines, index)) break;
      paragraphLines.push(trimmed);
      index += 1;
    }

    flushParagraph();
    return {
      html: `<li>${parts.join("")}</li>`,
      nextIndex: index,
    };
  }

  function renderList(lines, startIndex, baseIndent) {
    const first = matchListItem(lines[startIndex]);
    const type = first.type;
    const items = [];
    let index = startIndex;

    while (index < lines.length) {
      const item = matchListItem(lines[index]);
      if (!item || item.indent !== baseIndent || item.type !== type) break;
      const rendered = renderListItem(lines, index, baseIndent);
      items.push(rendered.html);
      index = rendered.nextIndex;
    }

    return {
      html: `<${type}>${items.join("")}</${type}>`,
      nextIndex: index,
    };
  }

  function renderMarkdown(value) {
    const lines = normalizeNewlines(value).split("\n");
    const html = [];
    let index = 0;

    while (index < lines.length) {
      const trimmed = lines[index].trim();

      if (!trimmed) {
        index += 1;
        continue;
      }

      if (matchFence(trimmed)) {
        const codeBlock = renderCodeBlock(lines, index);
        html.push(codeBlock.html);
        index = codeBlock.nextIndex;
        continue;
      }

      if (isHorizontalRule(trimmed)) {
        html.push("<hr>");
        index += 1;
        continue;
      }

      const heading = matchHeading(trimmed);
      if (heading) {
        const level = Math.min(heading[1].length + 1, 4);
        html.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
        index += 1;
        continue;
      }

      if (trimmed.startsWith(">")) {
        const quote = renderQuote(lines, index);
        html.push(quote.html);
        index = quote.nextIndex;
        continue;
      }

      if (isTableStart(lines, index)) {
        const table = renderTable(lines, index);
        html.push(table.html);
        index = table.nextIndex;
        continue;
      }

      const listItem = matchListItem(lines[index]);
      if (listItem) {
        const list = renderList(lines, index, listItem.indent);
        html.push(list.html);
        index = list.nextIndex;
        continue;
      }

      const paragraphLines = [];
      while (index < lines.length) {
        const line = lines[index];
        if (!line.trim()) break;
        if (paragraphLines.length && isBlockStart(lines, index)) break;
        paragraphLines.push(line);
        index += 1;
      }
      html.push(renderParagraph(paragraphLines));
    }

    return html.join("");
  }

  window.ScholarOSMarkdown = {
    render: renderMarkdown,
    renderInline: renderInlineMarkdown,
  };
})();
