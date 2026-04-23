from __future__ import annotations

from datetime import datetime
from pathlib import Path

from nova_scout_app.constants import APP_TITLE, MAX_REPORT_COPY_LINES
from nova_scout_app.services.text_processing import format_similarity


def build_match_report(
    *,
    source_dir: str,
    destination_dir: str,
    total_source_images: int,
    queries: list[str],
    reference_images: list[str],
    copied_files: list[str],
    missing_queries: list[str],
    unmatched_references: list[str],
    matched_by_name: dict[str, list[str]],
    matched_by_visual: dict[str, list[tuple[str, float]]],
    vision_engine: str,
    warnings: list[str],
) -> str:
    report_lines = [
        APP_TITLE,
        "=" * len(APP_TITLE),
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "Folders",
        f"Source: {source_dir}",
        f"Destination: {destination_dir}",
        "",
        "Summary",
        f"Total source images: {total_source_images}",
        f"Text queries provided: {len(queries)}",
        f"Reference images provided: {len(reference_images)}",
        f"Copied images: {len(copied_files)}",
        f"Missing text queries: {len(missing_queries)}",
        f"Unmatched references: {len(unmatched_references)}",
        f"Vision engine: {vision_engine}",
    ]

    if warnings:
        report_lines.extend(["", "Warnings"])
        report_lines.extend(f"- {warning}" for warning in warnings)

    if matched_by_name:
        report_lines.extend(["", "Name Matches"])
        for query, hits in matched_by_name.items():
            report_lines.append(f"- {query}: {len(hits)} match(es)")
            for path in hits[:5]:
                report_lines.append(f"  - {Path(path).name}")
            if len(hits) > 5:
                report_lines.append(f"  - ... {len(hits) - 5} more")

    if matched_by_visual:
        report_lines.extend(["", "Visual Best Matches"])
        for reference_name, matches in matched_by_visual.items():
            best_path, best_score = matches[0]
            report_lines.append(
                f"- {reference_name}: {Path(best_path).name}  "
                f"(similarity {format_similarity(best_score)})"
            )

    if copied_files:
        report_lines.extend(["", "Copied Files"])
        for path in copied_files[:MAX_REPORT_COPY_LINES]:
            report_lines.append(f"- {path}")
        overflow = len(copied_files) - MAX_REPORT_COPY_LINES
        if overflow > 0:
            report_lines.append(f"- ... {overflow} additional file(s) omitted from the on-screen report")

    if missing_queries:
        report_lines.extend(["", "Not Found"])
        report_lines.extend(f"- {query}" for query in missing_queries)

    if unmatched_references:
        report_lines.extend(["", "Reference Images Without Confident Matches"])
        report_lines.extend(f"- {reference}" for reference in unmatched_references)

    return "\n".join(report_lines)
