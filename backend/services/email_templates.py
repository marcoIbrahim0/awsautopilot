"""Shared branded email layout and section helpers."""
from __future__ import annotations

from html import escape
from typing import Iterable, Sequence

DEFAULT_EMAIL_APP_NAME = "AWS Security Autopilot"


def escape_html(value: object | None) -> str:
    return escape("" if value is None else str(value), quote=True)


def render_html_paragraphs(paragraphs: Sequence[str]) -> str:
    items = [f'<p style="margin:0 0 14px;color:#526277;line-height:1.7;">{escape_html(item)}</p>' for item in paragraphs if str(item).strip()]
    return "".join(items)


def render_html_rich_list(items: Sequence[str]) -> str:
    rows = [f'<li style="margin:0 0 10px;color:#17324d;line-height:1.65;">{item}</li>' for item in items if str(item).strip()]
    if not rows:
        return ""
    return f'<ul style="margin:0;padding-left:20px;">{"".join(rows)}</ul>'


def render_html_stat_grid(rows: Sequence[tuple[str, object]]) -> str:
    cards = []
    for label, value in rows:
        cards.append(
            '<div style="display:inline-block;vertical-align:top;width:calc(50% - 8px);min-width:220px;'
            'margin:0 8px 8px 0;padding:16px 18px;border:1px solid #d8e4f0;border-radius:14px;'
            'background:#f5f9fc;">'
            f'<div style="font-size:12px;letter-spacing:0.04em;text-transform:uppercase;color:#6a7a8f;margin:0 0 8px;">{escape_html(label)}</div>'
            f'<div style="font-size:28px;line-height:1.1;font-weight:700;color:#10253d;">{escape_html(value)}</div>'
            "</div>"
        )
    if not cards:
        return ""
    return "".join(cards)


def render_html_fact_table(rows: Sequence[tuple[str, object]]) -> str:
    cells = []
    for label, value in rows:
        cells.append(
            "<tr>"
            f'<td style="padding:8px 14px 8px 0;color:#6a7a8f;vertical-align:top;">{escape_html(label)}</td>'
            f'<td style="padding:8px 0;color:#17324d;font-weight:600;vertical-align:top;">{escape_html(value)}</td>'
            "</tr>"
        )
    if not cells:
        return ""
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;">'
        f'{"".join(cells)}'
        "</table>"
    )


def render_html_notice(message: str) -> str:
    text = escape_html(message)
    if not text.strip():
        return ""
    return (
        '<div style="margin:0;padding:14px 16px;border-radius:12px;'
        'background:#eef5fb;border:1px solid #d5e4f2;color:#41586f;line-height:1.65;">'
        f"{text}"
        "</div>"
    )


def render_html_link_box(url: str) -> str:
    safe_url = escape_html(url)
    if not safe_url.strip():
        return ""
    return (
        '<div style="margin:0;padding:12px 14px;border-radius:12px;'
        'background:#f8fbfd;border:1px dashed #c7d7e6;word-break:break-all;'
        'font-size:13px;line-height:1.6;color:#36506e;">'
        f"{safe_url}"
        "</div>"
    )


def render_html_code_block(code: str, label: str | None = None) -> str:
    safe_code = escape_html(code)
    if not safe_code.strip():
        return ""
    label_html = (
        f'<div style="font-size:12px;letter-spacing:0.04em;text-transform:uppercase;color:#6a7a8f;margin:0 0 8px;">{escape_html(label)}</div>'
        if label
        else ""
    )
    return (
        '<div style="margin:0;padding:18px;border-radius:16px;border:1px solid #d6e3f0;'
        'background:#f4f8fb;text-align:center;">'
        f"{label_html}"
        f'<div style="font-size:34px;line-height:1.1;letter-spacing:0.32em;font-weight:700;color:#10253d;">{safe_code}</div>'
        "</div>"
    )


def render_html_section(title: str, content_html: str) -> str:
    if not content_html.strip():
        return ""
    return (
        '<div style="margin:0 0 20px;padding:18px 20px;border:1px solid #e2ebf3;'
        'border-radius:18px;background:#ffffff;">'
        f'<div style="font-size:14px;font-weight:700;color:#17324d;margin:0 0 12px;">{escape_html(title)}</div>'
        f"{content_html}"
        "</div>"
    )


def render_text_fact_block(title: str, rows: Sequence[tuple[str, object]]) -> str:
    lines = [title, "-" * len(title)]
    lines.extend(
        f"{label}: {value}"
        for label, value in rows
        if str(label).strip() and str(value).strip()
    )
    return "\n".join(lines).strip()


def render_text_list_block(title: str, items: Sequence[str]) -> str:
    rows = [f"• {item}" for item in items if str(item).strip()]
    if not rows:
        return ""
    return "\n".join([title, "-" * len(title), *rows]).strip()


def build_email_html_document(
    *,
    title: str,
    intro_html: str,
    sections_html: Sequence[str] | None = None,
    cta_label: str | None = None,
    cta_url: str | None = None,
    footer_html: str | None = None,
    eyebrow: str | None = DEFAULT_EMAIL_APP_NAME,
    preheader: str | None = None,
) -> str:
    section_html = "".join(item for item in (sections_html or []) if item.strip())
    button_html = ""
    if cta_label and cta_url:
        button_html = (
            '<div style="margin:0 0 22px;">'
            f'<a href="{escape_html(cta_url)}" style="display:inline-block;padding:14px 22px;'
            'background:#0d63c8;border-radius:12px;color:#ffffff;text-decoration:none;'
            'font-weight:700;font-size:14px;">'
            f"{escape_html(cta_label)}</a>"
            "</div>"
        )
    footer_block = footer_html or (
        f'<p style="margin:0;color:#6a7a8f;line-height:1.6;">Sent by {escape_html(DEFAULT_EMAIL_APP_NAME)}.</p>'
    )
    preheader_html = (
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{escape_html(preheader)}</div>'
        if preheader
        else ""
    )
    eyebrow_html = (
        '<div style="display:inline-block;margin:0 0 14px;padding:6px 10px;border-radius:999px;'
        'background:#e8f1fb;color:#0d63c8;font-size:11px;font-weight:700;letter-spacing:0.08em;'
        'text-transform:uppercase;">'
        f"{escape_html(eyebrow)}"
        "</div>"
        if eyebrow
        else ""
    )
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{escape_html(title)}</title>
</head>
<body style="margin:0;padding:24px 12px;background:#eef3f8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#17324d;">
  {preheader_html}
  <div style="max-width:640px;margin:0 auto;">
    <div style="padding:18px 10px 14px;text-align:center;color:#6a7a8f;font-size:12px;letter-spacing:0.08em;text-transform:uppercase;">
      {escape_html(DEFAULT_EMAIL_APP_NAME)}
    </div>
    <div style="background:#ffffff;border:1px solid #dbe6f0;border-radius:24px;padding:32px 28px;box-shadow:0 12px 40px rgba(16,37,61,0.08);">
      {eyebrow_html}
      <h1 style="margin:0 0 14px;font-size:30px;line-height:1.18;color:#10253d;">{escape_html(title)}</h1>
      <div style="margin:0 0 22px;">{intro_html}</div>
      {button_html}
      {section_html}
      <div style="margin-top:28px;padding-top:18px;border-top:1px solid #e4edf5;font-size:12px;">
        {footer_block}
      </div>
    </div>
  </div>
</body>
</html>"""


def build_email_text_document(
    *,
    title: str,
    intro_lines: Sequence[str],
    section_blocks: Sequence[str] | None = None,
    cta_label: str | None = None,
    cta_url: str | None = None,
    footer_lines: Sequence[str] | None = None,
) -> str:
    lines: list[str] = [title, "=" * len(title), ""]
    lines.extend([line for line in intro_lines if str(line).strip()])
    if lines[-1] != "":
        lines.append("")
    for block in section_blocks or []:
        if block.strip():
            lines.append(block.strip())
            lines.append("")
    if cta_label and cta_url:
        lines.extend([cta_label + ":", cta_url, ""])
    for line in footer_lines or []:
        if str(line).strip():
            lines.append(str(line))
    return "\n".join(lines).strip()


def join_text_blocks(blocks: Iterable[str]) -> list[str]:
    return [block.strip() for block in blocks if block and block.strip()]
