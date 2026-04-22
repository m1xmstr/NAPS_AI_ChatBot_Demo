#!/usr/bin/env python3
"""Build a small branded EDU chatbot artifact from public website content."""

from __future__ import annotations

import argparse
import base64
import html
import json
import mimetypes
import os
import re
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


DEFAULT_QUESTIONS = [
    "When is open enrollment?",
    "When can I register for classes?",
    "How much is tuition going up?",
    "How do I apply for financial assistance?",
    "Where are the closest bookstores to campus?",
    "How many students find job placement after graduation?",
]

KEYWORDS = {
    "admission",
    "admissions",
    "apply",
    "application",
    "registrar",
    "register",
    "registration",
    "enrollment",
    "calendar",
    "tuition",
    "fees",
    "financial",
    "aid",
    "scholarship",
    "bookstore",
    "campus-store",
    "career",
    "outcomes",
    "placement",
    "students",
}

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "after",
    "before",
    "be",
    "by",
    "can",
    "closest",
    "do",
    "find",
    "for",
    "from",
    "going",
    "how",
    "i",
    "in",
    "is",
    "it",
    "many",
    "me",
    "much",
    "nearest",
    "of",
    "on",
    "or",
    "student",
    "students",
    "the",
    "to",
    "up",
    "what",
    "when",
    "where",
    "with",
}


def clean_space(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def tokenize(value: str) -> list[str]:
    values: list[str] = []
    for token in re.findall(r"[a-z0-9][a-z0-9-]{2,}", value.lower()):
        if token in STOP_WORDS:
            continue
        values.append(token)
        if token.endswith("ies") and len(token) > 4:
            values.append(token[:-3] + "y")
        elif token.endswith("s") and len(token) > 4:
            values.append(token[:-1])
    return sorted(set(values))


def required_terms(question: str) -> list[str]:
    lowered = question.lower()
    if "bookstore" in lowered or "book store" in lowered:
        return ["bookstore", "book store", "campus store"]
    if "job placement" in lowered or "placement" in lowered:
        return ["placement", "outcome", "career outcome", "employment outcome", "graduate outcome"]
    if "tuition" in lowered:
        return ["tuition"]
    if "financial" in lowered or "assistance" in lowered:
        return ["financial", "aid", "scholarship"]
    if "register" in lowered:
        return ["register", "registrar", "registration"]
    if "enrollment" in lowered:
        return ["enrollment", "admission", "apply"]
    return []


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "edu-demo"


def fetch_text(url: str, timeout: int = 12) -> tuple[str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "EDU_AI_DEMO/0.1 (+https://github.com/m1xmstr/NAPS_AI_ChatBot_Demo)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("content-type", "")
        charset_match = re.search(r"charset=([\w.-]+)", content_type)
        charset = charset_match.group(1) if charset_match else "utf-8"
        body = response.read(2_000_000)
    return body.decode(charset, errors="replace"), content_type


def normalize_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url if "://" in url else f"https://{url}")
    path = parsed.path or "/"
    return urllib.parse.urlunparse((parsed.scheme or "https", parsed.netloc.lower(), path, "", "", ""))


def site_root(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    return host


def same_site(url: str, root_host: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    return host == root_host or host.endswith("." + root_host)


class PageParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title = ""
        self.meta_description = ""
        self.links: list[str] = []
        self.images: list[dict[str, str]] = []
        self.text_chunks: list[str] = []
        self._tag_stack: list[str] = []
        self._skip_depth = 0
        self._capture_tag = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k.lower(): v or "" for k, v in attrs}
        tag = tag.lower()
        self._tag_stack.append(tag)
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag == "title":
            self._capture_tag = "title"
        if tag in {"h1", "h2", "h3", "p", "li", "a"}:
            self._capture_tag = tag
        if tag == "meta":
            name = (attrs_dict.get("name") or attrs_dict.get("property") or "").lower()
            content = attrs_dict.get("content", "")
            if name in {"description", "og:description"} and content and not self.meta_description:
                self.meta_description = clean_space(content)
            if name in {"og:image", "twitter:image"} and content:
                self.images.append({"src": urllib.parse.urljoin(self.base_url, content), "alt": name})
        if tag == "a" and attrs_dict.get("href"):
            self.links.append(urllib.parse.urljoin(self.base_url, attrs_dict["href"]))
        if tag == "link":
            rel = attrs_dict.get("rel", "").lower()
            if "icon" in rel and attrs_dict.get("href"):
                self.images.append({"src": urllib.parse.urljoin(self.base_url, attrs_dict["href"]), "alt": rel})
        if tag == "img" and attrs_dict.get("src"):
            alt = " ".join(
                [
                    attrs_dict.get("alt", ""),
                    attrs_dict.get("class", ""),
                    attrs_dict.get("id", ""),
                    attrs_dict.get("src", ""),
                ]
            )
            self.images.append({"src": urllib.parse.urljoin(self.base_url, attrs_dict["src"]), "alt": alt})

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if self._tag_stack:
            self._tag_stack.pop()
        self._capture_tag = self._tag_stack[-1] if self._tag_stack else ""

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = clean_space(data)
        if not text:
            return
        if self._capture_tag == "title" and not self.title:
            self.title = text
        if self._capture_tag in {"title", "h1", "h2", "h3", "p", "li", "a"}:
            if len(text) > 2:
                self.text_chunks.append(text)


@dataclass
class Page:
    url: str
    title: str
    description: str
    text: str
    score_hint: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "url": self.url,
            "title": self.title or self.url,
            "description": self.description,
            "text": self.text[:7000],
            "score_hint": self.score_hint,
        }


@dataclass
class CrawlResult:
    pages: list[Page] = field(default_factory=list)
    logo_url: str = ""
    errors: list[str] = field(default_factory=list)


def discover_sitemap_urls(start_url: str, root_host: str) -> list[str]:
    parsed = urllib.parse.urlparse(start_url)
    sitemap = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "/sitemap.xml", "", "", ""))
    try:
        body, _ = fetch_text(sitemap, timeout=8)
    except Exception:
        return []
    urls = re.findall(r"<loc>\s*([^<]+)\s*</loc>", body, flags=re.I)
    normalized = []
    for url in urls:
        url = normalize_url(url)
        if same_site(url, root_host):
            normalized.append(url)
    return normalized[:200]


def link_priority(url: str) -> int:
    lowered = url.lower()
    score = sum(3 for keyword in KEYWORDS if keyword in lowered)
    if any(part in lowered for part in ["/news", "/event", "/story", "/tag"]):
        score -= 2
    if any(part in lowered for part in [".pdf", ".jpg", ".png", ".zip", "mailto:", "#"]):
        score -= 20
    return score


def pick_logo(images: list[dict[str, str]]) -> str:
    if not images:
        return ""
    ranked = sorted(
        images,
        key=lambda item: (
            5 if "logo" in (item.get("alt", "") + item.get("src", "")).lower() else 0,
            3 if "og:image" in item.get("alt", "").lower() else 0,
            -len(item.get("src", "")),
        ),
        reverse=True,
    )
    return ranked[0].get("src", "")


def crawl_site(start_url: str, seed_urls: Iterable[str], max_pages: int) -> CrawlResult:
    start_url = normalize_url(start_url)
    root_host = site_root(start_url)
    queue: list[str] = [start_url]
    queue.extend(normalize_url(url) for url in seed_urls if url)
    queue.extend(sorted(discover_sitemap_urls(start_url, root_host), key=link_priority, reverse=True))
    seen: set[str] = set()
    result = CrawlResult()
    discovered_images: list[dict[str, str]] = []

    while queue and len(result.pages) < max_pages:
        url = queue.pop(0)
        if url in seen or not same_site(url, root_host) or link_priority(url) < -5:
            continue
        seen.add(url)
        try:
            body, content_type = fetch_text(url)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            result.errors.append(f"{url}: {exc}")
            continue
        if "html" not in content_type.lower() and "<html" not in body[:500].lower():
            continue
        parser = PageParser(url)
        try:
            parser.feed(body)
        except Exception as exc:
            result.errors.append(f"{url}: parser error {exc}")
            continue
        text = clean_space(" ".join(parser.text_chunks))
        if len(text) < 120:
            continue
        discovered_images.extend(parser.images)
        page = Page(
            url=url,
            title=parser.title or urllib.parse.urlparse(url).path.strip("/").replace("-", " ").title(),
            description=parser.meta_description,
            text=text,
            score_hint=link_priority(url),
        )
        result.pages.append(page)
        next_links = []
        for link in parser.links:
            normalized = normalize_url(link)
            if normalized not in seen and same_site(normalized, root_host) and link_priority(normalized) > -5:
                next_links.append(normalized)
        queue.extend(sorted(set(next_links), key=link_priority, reverse=True))
        time.sleep(0.15)

    result.logo_url = pick_logo(discovered_images)
    return result


def file_to_data_uri(path: str) -> str:
    if not path:
        return ""
    file_path = Path(path).expanduser()
    if not file_path.exists():
        raise FileNotFoundError(f"Logo file not found: {file_path}")
    mime = mimetypes.guess_type(str(file_path))[0] or "image/png"
    encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def score_pages(question: str, pages: list[dict[str, object]], limit: int = 4) -> list[dict[str, object]]:
    tokens = tokenize(question)
    required = required_terms(question)
    scored: list[tuple[int, dict[str, object]]] = []
    for page in pages:
        haystack = f"{page.get('title', '')} {page.get('description', '')} {page.get('text', '')}".lower()
        if required and not any(term in haystack for term in required):
            continue
        token_hits = 0
        score = 0
        for token in tokens:
            count = haystack.count(token)
            token_hits += count
            score += count * 5
            if token in str(page.get("title", "")).lower():
                score += 3
        score += int(page.get("score_hint", 0))
        if token_hits > 0 and score > 3:
            scored.append((score, page))
    return [page for _, page in sorted(scored, key=lambda item: item[0], reverse=True)[:limit]]


def make_snippet(question: str, text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", clean_space(text))
    tokens = tokenize(question)
    best = ""
    best_score = -1
    for sentence in sentences:
        score = sum(sentence.lower().count(token) for token in tokens)
        if score > best_score and 40 <= len(sentence) <= 360:
            best = sentence
            best_score = score
    return best or clean_space(text)[:280]


def answer_question(question: str, pages: list[dict[str, object]], customer_name: str) -> dict[str, object]:
    matches = score_pages(question, pages)
    if not matches:
        return {
            "question": question,
            "answer": (
                f"I could not verify this from the pages crawled for {customer_name}. "
                "For a live demo, add a seed URL for registrar, tuition, financial aid, bookstore, or outcomes pages."
            ),
            "confidence": "not_found",
            "sources": [],
        }
    snippets = [make_snippet(question, str(page.get("text", ""))) for page in matches[:2]]
    answer = (
        f"Based on the public {customer_name} pages I crawled, the most relevant official information is: "
        + " ".join(snippets)
    )
    return {
        "question": question,
        "answer": answer,
        "confidence": "evidence_found",
        "sources": [{"title": page.get("title", ""), "url": page.get("url", "")} for page in matches],
    }


APP_PY = r'''#!/usr/bin/env python3
import json
import os
import re
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROFILE = json.loads((ROOT / "profile.json").read_text())
KNOWLEDGE = json.loads((ROOT / "knowledge.json").read_text())
STOP_WORDS = {"a","an","and","are","as","at","after","before","be","by","can","closest","do","find","for","from","going","how","i","in","is","it","many","me","much","nearest","of","on","or","student","students","the","to","up","what","when","where","with"}


def clean_space(value):
    return re.sub(r"\s+", " ", value or "").strip()


def tokens(value):
    result = []
    for token in re.findall(r"[a-z0-9][a-z0-9-]{2,}", value.lower()):
        if token in STOP_WORDS:
            continue
        result.append(token)
        if token.endswith("ies") and len(token) > 4:
            result.append(token[:-3] + "y")
        elif token.endswith("s") and len(token) > 4:
            result.append(token[:-1])
    return sorted(set(result))


def required_terms(question):
    lowered = question.lower()
    if "bookstore" in lowered or "book store" in lowered:
        return ["bookstore", "book store", "campus store"]
    if "job placement" in lowered or "placement" in lowered:
        return ["placement", "outcome", "career outcome", "employment outcome", "graduate outcome"]
    if "tuition" in lowered:
        return ["tuition"]
    if "financial" in lowered or "assistance" in lowered:
        return ["financial", "aid", "scholarship"]
    if "register" in lowered:
        return ["register", "registrar", "registration"]
    if "enrollment" in lowered:
        return ["enrollment", "admission", "apply"]
    return []


def score_pages(question, limit=4):
    q_tokens = tokens(question)
    required = required_terms(question)
    scored = []
    for page in KNOWLEDGE["pages"]:
        haystack = f"{page.get('title','')} {page.get('description','')} {page.get('text','')}".lower()
        if required and not any(term in haystack for term in required):
            continue
        token_hits = 0
        score = 0
        for token in q_tokens:
            count = haystack.count(token)
            token_hits += count
            score += count * 5
            if token in str(page.get("title", "")).lower():
                score += 3
        score += int(page.get("score_hint", 0))
        if token_hits > 0 and score > 3:
            scored.append((score, page))
    return [page for _, page in sorted(scored, key=lambda item: item[0], reverse=True)[:limit]]


def snippet(question, text):
    parts = re.split(r"(?<=[.!?])\s+", clean_space(text))
    q_tokens = tokens(question)
    best = ""
    best_score = -1
    for part in parts:
        score = sum(part.lower().count(token) for token in q_tokens)
        if score > best_score and 40 <= len(part) <= 360:
            best = part
            best_score = score
    return best or clean_space(text)[:280]


def evidence_answer(question):
    matches = score_pages(question)
    if not matches:
        return {
            "answer": f"I could not verify this from the pages crawled for {PROFILE['customer_name']}. Add a more specific official URL and re-run EDU_AI_DEMO.",
            "confidence": "not_found",
            "sources": [],
            "provider": "evidence",
        }
    snippets = [snippet(question, page.get("text", "")) for page in matches[:2]]
    return {
        "answer": f"Based on public {PROFILE['customer_name']} pages, I found: " + " ".join(snippets),
        "confidence": "evidence_found",
        "sources": [{"title": page.get("title", ""), "url": page.get("url", "")} for page in matches],
        "provider": "evidence",
    }


def llm_answer(question, base):
    endpoint = os.environ.get("DEMO_LLM_ENDPOINT", "").strip()
    if not endpoint:
        return base
    api_key_env = os.environ.get("DEMO_LLM_API_KEY_ENV", "DEMO_LLM_API_KEY")
    api_key = os.environ.get(api_key_env, "")
    context = "\n\n".join([f"{src['title']}: {src['url']}" for src in base.get("sources", [])])
    prompt = (
        "Answer as a careful EDU assistant. Use only the provided context. "
        "If the answer is not in the context, say you cannot verify it.\n\n"
        f"Customer: {PROFILE['customer_name']}\nQuestion: {question}\nContext:\n{context}\nEvidence answer: {base['answer']}"
    )
    payload = json.dumps({
        "model": os.environ.get("DEMO_LLM_MODEL", "demo-model"),
        "messages": [
            {"role": "system", "content": "You are a careful assistant for an education technology demo."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        request = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=25) as response:
            data = json.loads(response.read().decode("utf-8"))
        base["answer"] = data["choices"][0]["message"]["content"]
        base["provider"] = os.environ.get("DEMO_AI_PROVIDER", "llm")
        return base
    except Exception as exc:
        base["provider"] = "evidence_fallback"
        base["llm_error"] = str(exc)
        return base


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, content_type="application/json"):
        raw = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/healthz":
            self._send(200, b"ok", "text/plain")
        elif self.path == "/api/profile":
            profile = dict(PROFILE)
            profile["provider"] = os.environ.get("DEMO_AI_PROVIDER", profile.get("provider", "artifact"))
            self._send(200, json.dumps(profile))
        elif self.path == "/static/styles.css":
            self._send(200, (ROOT / "static" / "styles.css").read_bytes(), "text/css")
        else:
            self._send(200, (ROOT / "static" / "index.html").read_bytes(), "text/html")

    def do_POST(self):
        if self.path != "/api/chat":
            self._send(404, json.dumps({"error": "not found"}))
            return
        length = int(self.headers.get("Content-Length", "0"))
        data = json.loads(self.rfile.read(length) or b"{}")
        question = clean_space(data.get("question", ""))
        if not question:
            self._send(400, json.dumps({"error": "question is required"}))
            return
        result = llm_answer(question, evidence_answer(question))
        self._send(200, json.dumps(result))

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
'''


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>EDU AI Demo</title>
  <link rel="stylesheet" href="/static/styles.css" />
</head>
<body>
  <main class="shell">
    <section class="brand-panel">
      <img id="logo" class="logo" alt="" />
      <p class="eyebrow">AAP-built customer demo</p>
      <h1 id="customer">EDU AI Demo</h1>
      <p id="website" class="site"></p>
      <div class="badges">
        <span>Ansible Automation Platform</span>
        <span>RHEL</span>
        <span>Podman</span>
        <span>OpenShift</span>
        <span>OpenShift AI</span>
        <span>RHEL AI</span>
      </div>
    </section>
    <section class="chat-panel">
      <div id="messages" class="messages"></div>
      <div id="suggestions" class="suggestions"></div>
      <form id="chat-form" class="composer">
        <input id="question" autocomplete="off" placeholder="Ask about enrollment, tuition, financial aid, bookstores, or career outcomes" />
        <button type="submit">Ask</button>
      </form>
    </section>
  </main>
  <script>
    let profile = {};
    const messages = document.querySelector("#messages");
    const suggestions = document.querySelector("#suggestions");
    const form = document.querySelector("#chat-form");
    const question = document.querySelector("#question");

    function addMessage(role, text, sources) {
      const item = document.createElement("article");
      item.className = `message ${role}`;
      item.innerHTML = `<p>${text}</p>`;
      if (sources && sources.length) {
        const list = document.createElement("div");
        list.className = "sources";
        sources.slice(0, 4).forEach((src) => {
          const a = document.createElement("a");
          a.href = src.url;
          a.target = "_blank";
          a.rel = "noreferrer";
          a.textContent = src.title || src.url;
          list.appendChild(a);
        });
        item.appendChild(list);
      }
      messages.appendChild(item);
      messages.scrollTop = messages.scrollHeight;
    }

    async function ask(text) {
      addMessage("user", text);
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({question: text})
      });
      const data = await response.json();
      addMessage("assistant", data.answer || data.error, data.sources || []);
    }

    async function boot() {
      profile = await (await fetch("/api/profile")).json();
      document.title = `${profile.customer_name} AI Demo`;
      document.querySelector("#customer").textContent = `${profile.customer_name} AI Assistant`;
      document.querySelector("#website").textContent = profile.customer_website;
      if (profile.logo_url) {
        document.querySelector("#logo").src = profile.logo_url;
      } else {
        document.querySelector("#logo").style.display = "none";
      }
      addMessage("assistant", `I am a temporary ${profile.customer_name} demo assistant built by Ansible Automation Platform from public website content.`);
      (profile.questions || []).forEach((q) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = q;
        button.onclick = () => ask(q);
        suggestions.appendChild(button);
      });
    }

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const text = question.value.trim();
      if (!text) return;
      question.value = "";
      ask(text);
    });

    boot();
  </script>
</body>
</html>
"""


STYLES_CSS = """
:root {
  color-scheme: dark;
  --bg: #08111f;
  --panel: #101c2d;
  --line: #27415f;
  --text: #eaf3ff;
  --muted: #aebfd3;
  --accent: #35d0a2;
  --accent-2: #7cc8ff;
}

* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: radial-gradient(circle at 25% 20%, rgba(53, 208, 162, .16), transparent 28%), var(--bg);
  color: var(--text);
}
.shell {
  display: grid;
  grid-template-columns: minmax(280px, 380px) 1fr;
  gap: 24px;
  width: min(1180px, calc(100vw - 32px));
  min-height: calc(100vh - 32px);
  margin: 16px auto;
}
.brand-panel, .chat-panel {
  border: 1px solid var(--line);
  background: rgba(16, 28, 45, .92);
  border-radius: 8px;
}
.brand-panel {
  padding: 28px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.logo {
  display: block;
  max-width: 220px;
  max-height: 120px;
  object-fit: contain;
  background: #fff;
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 28px;
}
.eyebrow {
  margin: 0 0 10px;
  color: var(--accent);
  font-weight: 800;
  letter-spacing: 0;
  text-transform: uppercase;
  font-size: 12px;
}
h1 {
  margin: 0;
  font-size: 42px;
  line-height: 1.02;
}
.site {
  color: var(--muted);
  margin: 16px 0 26px;
  word-break: break-word;
}
.badges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.badges span, .suggestions button {
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--text);
  background: #0b1728;
  padding: 8px 10px;
  font-weight: 700;
  font-size: 13px;
}
.chat-panel {
  display: grid;
  grid-template-rows: 1fr auto auto;
  min-height: 620px;
}
.messages {
  padding: 24px;
  overflow: auto;
}
.message {
  max-width: 820px;
  padding: 16px 18px;
  margin: 0 0 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
}
.message p {
  margin: 0;
  line-height: 1.55;
}
.message.user {
  margin-left: auto;
  background: #173b53;
}
.message.assistant {
  background: #0b1728;
}
.sources {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}
.sources a {
  color: var(--accent-2);
  overflow-wrap: anywhere;
}
.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 0 24px 16px;
}
.suggestions button {
  cursor: pointer;
}
.composer {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
  padding: 16px;
  border-top: 1px solid var(--line);
}
.composer input, .composer button {
  min-height: 48px;
  border-radius: 6px;
  border: 1px solid var(--line);
  font: inherit;
}
.composer input {
  width: 100%;
  background: #07101d;
  color: var(--text);
  padding: 0 14px;
}
.composer button {
  background: var(--accent);
  color: #03150f;
  font-weight: 900;
  padding: 0 22px;
  cursor: pointer;
}
@media (max-width: 800px) {
  .shell {
    grid-template-columns: 1fr;
  }
  h1 {
    font-size: 34px;
  }
  .chat-panel {
    min-height: 560px;
  }
}
"""


CONTAINERFILE = """FROM registry.access.redhat.com/ubi9/python-311:latest
WORKDIR /opt/app
COPY . /opt/app
EXPOSE 8080
ENV PORT=8080
CMD ["python", "/opt/app/app.py"]
"""


def write_app(output_dir: Path, profile: dict[str, object], knowledge: dict[str, object]) -> None:
    app_dir = output_dir / "app"
    static_dir = app_dir / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "app.py").write_text(APP_PY, encoding="utf-8")
    (app_dir / "profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")
    (app_dir / "knowledge.json").write_text(json.dumps(knowledge, indent=2), encoding="utf-8")
    (static_dir / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (static_dir / "styles.css").write_text(STYLES_CSS, encoding="utf-8")
    (app_dir / "Containerfile").write_text(CONTAINERFILE, encoding="utf-8")


def write_report(output_dir: Path, profile: dict[str, object], knowledge: dict[str, object], answers: list[dict[str, object]], errors: list[str]) -> None:
    lines = [
        f"# {profile['customer_name']} EDU AI Demo Report",
        "",
        f"- Website: {profile['customer_website']}",
        f"- Pages crawled: {len(knowledge['pages'])}",
        f"- Logo: {profile.get('logo_url') or 'not found'}",
        "",
        "## Preview Answers",
        "",
    ]
    for answer in answers:
        lines.extend(
            [
                f"### {answer['question']}",
                "",
                textwrap.shorten(str(answer["answer"]), width=700, placeholder=" ..."),
                "",
            ]
        )
        for source in answer.get("sources", [])[:4]:
            lines.append(f"- [{source.get('title') or source.get('url')}]({source.get('url')})")
        lines.append("")
    if errors:
        lines.extend(["## Crawl Notes", ""])
        for error in errors[:20]:
            lines.append(f"- {error}")
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def read_questions(path: str) -> list[str]:
    if not path:
        return DEFAULT_QUESTIONS
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [str(item) for item in data]
    raise ValueError("questions file must contain a JSON list")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--customer-name", required=True)
    parser.add_argument("--customer-website", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--logo-url", default="")
    parser.add_argument("--logo-file", default="")
    parser.add_argument("--max-pages", type=int, default=24)
    parser.add_argument("--questions-file", default="")
    parser.add_argument("--seed-url", nargs="*", default=[])
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    questions = read_questions(args.questions_file)
    crawl = crawl_site(args.customer_website, args.seed_url, args.max_pages)
    pages = [page.as_dict() for page in crawl.pages]
    logo_url = args.logo_url or (file_to_data_uri(args.logo_file) if args.logo_file else crawl.logo_url)
    profile = {
        "customer_name": args.customer_name,
        "customer_slug": slugify(args.customer_name),
        "customer_website": normalize_url(args.customer_website),
        "logo_url": logo_url,
        "questions": questions,
        "provider": os.environ.get("DEMO_AI_PROVIDER", "artifact"),
        "generated_by": "EDU_AI_DEMO",
    }
    knowledge = {
        "customer_name": args.customer_name,
        "source_website": normalize_url(args.customer_website),
        "pages": pages,
    }
    answers = [answer_question(question, pages, args.customer_name) for question in questions]

    (output_dir / "profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")
    (output_dir / "knowledge.json").write_text(json.dumps(knowledge, indent=2), encoding="utf-8")
    (output_dir / "answers_preview.json").write_text(json.dumps(answers, indent=2), encoding="utf-8")
    write_app(output_dir, profile, knowledge)
    write_report(output_dir, profile, knowledge, answers, crawl.errors)
    print(json.dumps({"output_dir": str(output_dir), "pages": len(pages), "logo_url": logo_url}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
