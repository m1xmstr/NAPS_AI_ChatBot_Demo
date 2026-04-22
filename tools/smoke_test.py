#!/usr/bin/env python3
"""Offline smoke test for generated EDU_AI_DEMO app bundles."""

from __future__ import annotations

import argparse
import json
import re
import textwrap
from pathlib import Path


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
    return re.sub(r"\s+", " ", value or "").strip()


def tokens(value: str) -> list[str]:
    result: list[str] = []
    for token in re.findall(r"[a-z0-9][a-z0-9-]{2,}", value.lower()):
        if token in STOP_WORDS:
            continue
        result.append(token)
        if token.endswith("ies") and len(token) > 4:
            result.append(token[:-3] + "y")
        elif token.endswith("s") and len(token) > 4:
            result.append(token[:-1])
    return sorted(set(result))


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


def score(question: str, pages: list[dict[str, object]]) -> list[dict[str, object]]:
    q_tokens = tokens(question)
    required = required_terms(question)
    scored: list[tuple[int, dict[str, object]]] = []
    for page in pages:
        haystack = f"{page.get('title','')} {page.get('description','')} {page.get('text','')}".lower()
        if required and not any(term in haystack for term in required):
            continue
        token_hits = 0
        value = 0
        for token in q_tokens:
            count = haystack.count(token)
            token_hits += count
            value += count * 5
            if token in str(page.get("title", "")).lower():
                value += 3
        value += int(page.get("score_hint", 0))
        if token_hits > 0 and value > 3:
            scored.append((value, page))
    return [page for _, page in sorted(scored, key=lambda item: item[0], reverse=True)[:4]]


def snippet(question: str, text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", clean_space(text))
    q_tokens = tokens(question)
    best = ""
    best_score = -1
    for part in parts:
        value = sum(part.lower().count(token) for token in q_tokens)
        if value > best_score and 40 <= len(part) <= 360:
            best = part
            best_score = value
    return best or clean_space(text)[:280]


def answer(question: str, profile: dict[str, object], pages: list[dict[str, object]]) -> dict[str, object]:
    matches = score(question, pages)
    if not matches:
        return {
            "question": question,
            "answer": f"Not verified from the crawled pages for {profile['customer_name']}.",
            "confidence": "not_found",
            "sources": [],
        }
    return {
        "question": question,
        "answer": " ".join(snippet(question, str(page.get("text", ""))) for page in matches[:2]),
        "confidence": "evidence_found",
        "sources": [{"title": page.get("title", ""), "url": page.get("url", "")} for page in matches],
    }


def read_questions(path: str, profile: dict[str, object]) -> list[str]:
    if path:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return [str(item) for item in data]
    return [str(item) for item in profile.get("questions", [])]


def write_markdown(path: Path, profile: dict[str, object], results: list[dict[str, object]]) -> None:
    lines = [f"# Smoke Test: {profile['customer_name']}", ""]
    for result in results:
        lines.extend(
            [
                f"## {result['question']}",
                "",
                f"Confidence: `{result['confidence']}`",
                "",
                textwrap.shorten(str(result["answer"]), width=700, placeholder=" ..."),
                "",
            ]
        )
        for source in result.get("sources", [])[:4]:
            lines.append(f"- [{source.get('title') or source.get('url')}]({source.get('url')})")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-dir", required=True)
    parser.add_argument("--questions-file", default="")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    app_dir = Path(args.app_dir)
    profile = json.loads((app_dir / "profile.json").read_text(encoding="utf-8"))
    knowledge = json.loads((app_dir / "knowledge.json").read_text(encoding="utf-8"))
    questions = read_questions(args.questions_file, profile)
    results = [answer(question, profile, knowledge.get("pages", [])) for question in questions]
    Path(args.output_json).write_text(json.dumps(results, indent=2), encoding="utf-8")
    write_markdown(Path(args.output_md), profile, results)
    print(json.dumps({"questions": len(results), "verified": sum(1 for r in results if r["confidence"] == "evidence_found")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
