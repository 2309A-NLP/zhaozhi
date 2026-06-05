"""Robust PDF parsing with layout cleanup, table reconstruction, and optional OCR fallback."""

from __future__ import annotations

import io
import json
import logging
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from PIL import Image, ImageOps

from rag_qa_system.backend.models.llm_client import PdfTextCleanupClient, PdfVisionChartClient
from rag_qa_system.backend.utils.text_utils import normalize_text


LOGGER = logging.getLogger("rag.pdf_parser")
_MIN_REPEAT_LENGTH = 6


@dataclass
class PdfParser:
    mode: str = "local"
    cleanup_client: PdfTextCleanupClient | None = None
    vision_client: PdfVisionChartClient | None = None
    header_ratio: float = 0.1
    footer_ratio: float = 0.08
    repeated_line_threshold: float = 0.6
    remove_page_number_lines: bool = True
    min_text_density_for_ocr: int = 80
    ocr_min_image_edge: int = 900
    ocr_lang: str = "chi_sim+eng"
    max_ocr_images_per_page: int = 3
    llm_cleanup_min_chars: int = 600
    vision_max_pages: int = 12
    vision_render_scale: float = 2.0
    vision_target_pages: str = ""
    auto_hybrid_max_pages: int = 80
    auto_hybrid_max_chars: int = 120000
    vision_chart_keywords: tuple[str, ...] = (
        "图",
        "结构",
        "结构图",
        "组织结构",
        "组织架构",
        "架构图",
        "部门",
        "销售部",
        "销售处",
        "增长",
        "占比",
        "比例",
        "市场",
        "亿元",
        "%",
        "％",
        "收入",
        "构成",
        "分布",
        "饼图",
        "柱状图",
        "直方图",
    )
    _tesseract_cmd: str | None = field(default=None, init=False, repr=False)

    def parse(self, pdf_path: str) -> str:
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")

        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("pypdf is required to parse PDF files") from exc

        logging.getLogger("pypdf").setLevel(logging.ERROR)
        reader = PdfReader(str(path))
        page_texts = [self._extract_page_text(page) for page in reader.pages]
        parser_mode = (self.mode or "local").strip().lower()
        effective_mode = self._choose_auto_parse_mode(path, page_texts) if parser_mode == "auto" else parser_mode
        text = self._remove_repeated_page_lines(page_texts)
        text = self._append_page_ocr_fallback(text, path)
        text = self._cleanup_document_text(text)
        if effective_mode == "vision_hybrid":
            text = self._append_vision_chart_descriptions(text, path, page_texts)
        else:
            text = self._refine_with_llm(text, path.name, effective_mode=effective_mode)
        if not normalize_text(text):
            raise ValueError(f"No text extracted from PDF: {path.name}")
        return text

    def _extract_page_text(self, page) -> str:
        fragments = self._collect_text_fragments(page)
        lines = self._build_lines(fragments)
        table_lines = self._extract_table_lines(page)
        image_ocr_lines = self._extract_page_image_ocr(page)

        if table_lines:
            lines.extend(table_lines)
        if image_ocr_lines:
            lines.extend(image_ocr_lines)

        if not lines:
            fallback = normalize_text(page.extract_text() or "")
            return self._remove_inline_page_noise(fallback)
        return self._remove_inline_page_noise("\n".join(lines))

    def _extract_compact_department_names(self, text: str) -> List[str]:
        first_office = text.find("销售处")
        scoped_text = text[:first_office] if first_office >= 0 else text
        names: List[str] = []
        for name in self._split_compact_names_by_suffix(scoped_text, ("销售部", "贸易部")):
            cleaned = self._trim_department_prefix(name)
            if cleaned.endswith(("销售部", "贸易部")) and cleaned not in names:
                names.append(cleaned)
        return names

    def _trim_department_prefix(self, text: str) -> str:
        compact = re.sub(r"\s+", "", text)
        for boundary in ("市场开发部", "信息系统部", "行政人事部", "物流部", "研发中心", "财务部", "内部审计部", "证券部"):
            hit = compact.rfind(boundary)
            if hit >= 0:
                compact = compact[hit + len(boundary) :]
        return compact

    def _split_compact_names_by_suffix(self, text: str, suffixes: tuple[str, ...]) -> List[str]:
        compact = re.sub(r"\s+", "", text)
        names: List[str] = []
        start = 0
        index = 0
        while index < len(compact):
            matched_suffix = next((suffix for suffix in suffixes if compact.startswith(suffix, index)), "")
            if not matched_suffix:
                index += 1
                continue
            end = index + len(matched_suffix)
            candidate = compact[start:end]
            if 2 <= len(candidate) <= 20 and candidate not in names:
                names.append(candidate)
            start = end
            index = end
        return names

    def _extract_names_ending_with_suffix(self, text: str, suffix: str) -> List[str]:
        compact = re.sub(r"\s+", "", text)
        names: List[str] = []
        index = 0
        boundaries = ("销售部", "贸易部", "销售处", "。", "，", ",", "、", "：", ":")
        while True:
            hit = compact.find(suffix, index)
            if hit < 0:
                break
            end = hit + len(suffix)
            start = 0
            for boundary in boundaries:
                boundary_hit = compact.rfind(boundary, 0, hit)
                if boundary_hit >= 0:
                    start = max(start, boundary_hit + len(boundary))
            candidate = compact[start:end]
            if 2 <= len(candidate) <= 12 and candidate not in names:
                names.append(candidate)
            index = end
        return names

    def _collect_text_fragments(self, page) -> List[Dict[str, object]]:
        page_height = float(page.mediabox.height or 0.0)
        header_limit = page_height * (1.0 - self.header_ratio)
        footer_limit = page_height * self.footer_ratio
        fragments: List[Dict[str, object]] = []

        def visitor_text(text: str, cm, tm, font_dict, font_size) -> None:
            candidate = normalize_text(text)
            if not candidate:
                return

            x = self._resolve_x_position(cm, tm)
            y = self._resolve_y_position(cm, tm)
            if page_height > 0:
                if y >= header_limit or y <= footer_limit:
                    return

            if self.remove_page_number_lines and self._looks_like_page_number(candidate):
                return

            fragments.append(
                {
                    "x": x,
                    "y": y,
                    "font_size": float(font_size or 0.0),
                    "text": candidate,
                }
            )

        try:
            page.extract_text(visitor_text=visitor_text, extraction_mode="layout")
        except TypeError:
            page.extract_text(visitor_text=visitor_text)
        return fragments

    def _build_lines(self, fragments: List[Dict[str, object]]) -> List[str]:
        if not fragments:
            return []

        sorted_fragments = sorted(
            fragments,
            key=lambda item: (-float(item["y"]), float(item["x"])),
        )
        grouped_rows: List[List[Dict[str, object]]] = []

        for fragment in sorted_fragments:
            if not grouped_rows:
                grouped_rows.append([fragment])
                continue
            previous_row = grouped_rows[-1]
            previous_y = float(previous_row[0]["y"])
            current_y = float(fragment["y"])
            tolerance = max(float(fragment["font_size"]) * 0.55, 2.5)
            if abs(previous_y - current_y) <= tolerance:
                previous_row.append(fragment)
            else:
                grouped_rows.append([fragment])

        lines: List[str] = []
        for row in grouped_rows:
            row.sort(key=lambda item: float(item["x"]))
            line_parts: List[str] = []
            previous_right = None
            for fragment in row:
                current_x = float(fragment["x"])
                text = str(fragment["text"])
                if previous_right is not None:
                    gap = current_x - previous_right
                    if gap > 45:
                        line_parts.append(" | ")
                    elif gap > 10 and line_parts:
                        line_parts.append(" ")
                line_parts.append(text)
                previous_right = current_x + max(len(text), 1) * max(float(fragment["font_size"]), 7.0) * 0.5

            line = normalize_text("".join(line_parts))
            if line:
                lines.append(line)
        return self._deduplicate_adjacent_lines(lines)

    def _extract_table_lines(self, page) -> List[str]:
        table_lines: List[str] = []
        try:
            tables = page.extract_tables() or []
        except Exception:
            tables = []

        for table in tables:
            for row in table or []:
                normalized_cells = [normalize_text(str(cell or "")) for cell in row]
                normalized_cells = [cell for cell in normalized_cells if cell]
                if len(normalized_cells) >= 2:
                    table_lines.append(" | ".join(normalized_cells))
        return self._deduplicate_adjacent_lines(table_lines)

    def _extract_page_image_ocr(self, page) -> List[str]:
        if not self._ocr_available():
            return []

        lines: List[str] = []
        images = self._iter_page_images(page)
        for index, image in enumerate(images):
            if index >= self.max_ocr_images_per_page:
                break
            ocr_text = self._ocr_image(image)
            if ocr_text:
                lines.extend(
                    line
                    for line in self._split_to_lines(ocr_text)
                    if len(line) >= 2 and not self._looks_like_page_number(line)
                )
        return self._deduplicate_adjacent_lines(lines)

    def _append_page_ocr_fallback(self, text: str, pdf_path: Path) -> str:
        cleaned = normalize_text(text)
        if len(cleaned) >= self.min_text_density_for_ocr:
            return text
        if not self._ocr_available():
            return text

        fallback_pages: List[str] = []
        for rendered in self._render_pdf_pages_to_images(pdf_path):
            ocr_text = self._ocr_image(rendered)
            if ocr_text:
                fallback_pages.append(ocr_text)

        if not fallback_pages:
            return text
        merged = "\n\n".join(part for part in [text, *fallback_pages] if normalize_text(part))
        return merged

    def _append_rendered_growth_chart_ocr(self, text: str, pdf_path: Path, page_texts: List[str]) -> str:
        return text

    def _looks_like_growth_chart_page(self, page_text: str) -> bool:
        return False

    def _extract_rendered_growth_chart_text(self, pdf_path: Path, page_index: int) -> str:
        try:
            import fitz
        except ImportError:
            return ""

        try:
            document = fitz.open(str(pdf_path))
        except Exception:
            LOGGER.exception("pdf_growth_chart_open_failed | source_name=%s", pdf_path.name)
            return ""

        try:
            if page_index < 0 or page_index >= len(document):
                return ""
            page = document[page_index]
            pixmap = page.get_pixmap(matrix=fitz.Matrix(max(self.vision_render_scale, 3.0), max(self.vision_render_scale, 3.0)), alpha=False)
            image = Image.open(io.BytesIO(pixmap.tobytes("png")))
            image.load()
        except Exception:
            LOGGER.exception("pdf_growth_chart_render_failed | source_name=%s | page=%s", pdf_path.name, page_index + 1)
            return ""
        finally:
            document.close()

        rates = self._extract_growth_rates_from_rendered_image(image)
        if not rates:
            return ""
        return self._format_rendered_growth_chart_text(page_index + 1, rates)

    def _extract_growth_rates_from_rendered_image(self, image: Image.Image) -> Dict[str, float]:
        width, height = image.size
        crop = image.crop((int(width * 0.43), int(height * 0.06), int(width * 0.92), int(height * 0.45)))
        tsv_text = self._ocr_image_tsv(crop, psm="6")
        rates = self._parse_growth_chart_tsv(tsv_text)
        if len(rates) < 2:
            tsv_text = self._ocr_image_tsv(crop, psm="11")
            rates = self._parse_growth_chart_tsv(tsv_text)
        return rates

    def _ocr_image_tsv(self, image: Image.Image, psm: str = "6") -> str:
        if not self._ocr_available():
            return ""

        processed = self._prepare_image_for_ocr_tsv(image)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            processed.save(temp_path)

        try:
            command = [
                self._tesseract_cmd or "tesseract",
                str(temp_path),
                "stdout",
                "-l",
                self.ocr_lang,
                "--psm",
                psm,
                "tsv",
            ]
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                check=False,
            )
            if completed.returncode != 0:
                LOGGER.warning("tesseract_tsv_failed | detail=%s", normalize_text(completed.stderr) or completed.returncode)
                return ""
            return completed.stdout
        finally:
            temp_path.unlink(missing_ok=True)

    def _prepare_image_for_ocr_tsv(self, image: Image.Image) -> Image.Image:
        grayscale = ImageOps.grayscale(image)
        grayscale = ImageOps.autocontrast(grayscale)
        width, height = grayscale.size
        scale = 2
        resized = grayscale.resize((max(1, width * scale), max(1, height * scale)), Image.Resampling.LANCZOS)
        return resized.point(lambda px: 0 if px < 170 else 255, mode="1")

    def _parse_growth_chart_tsv(self, tsv_text: str) -> Dict[str, float]:
        words: List[Dict[str, object]] = []
        for line in tsv_text.splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) < 12:
                continue
            raw_text = normalize_text(parts[11])
            if not raw_text:
                continue
            try:
                words.append(
                    {
                        "left": int(parts[6]),
                        "top": int(parts[7]),
                        "width": int(parts[8]),
                        "height": int(parts[9]),
                        "text": raw_text,
                    }
                )
            except ValueError:
                continue

        value_words = [word for word in words if self._extract_percent(str(word["text"])) is not None]
        label_words = [word for word in words if self._normalize_growth_label(str(word["text"]))]
        if not value_words or not label_words:
            return {}

        rates: Dict[str, float] = {}
        for value_word in value_words:
            value = self._extract_percent(str(value_word["text"]))
            if value is None:
                continue
            label = self._nearest_growth_label(value_word, label_words)
            if not label:
                continue
            if label in rates:
                continue
            if value_word["left"] < 360 and value > 0:
                value = -value
            rates[label] = value
        return rates

    def _nearest_growth_label(self, value_word: Dict[str, object], label_words: List[Dict[str, object]]) -> str:
        value_y = int(value_word["top"]) + int(value_word["height"]) // 2
        candidates: List[tuple[int, int, str]] = []
        for label_word in label_words:
            label = self._normalize_growth_label(str(label_word["text"]))
            if not label:
                continue
            label_y = int(label_word["top"]) + int(label_word["height"]) // 2
            delta_y = abs(value_y - label_y)
            if delta_y > 95:
                continue
            left_penalty = 0 if int(label_word["left"]) <= int(value_word["left"]) else 40
            candidates.append((delta_y + left_penalty, int(label_word["left"]), label))
        if not candidates:
            return ""
        candidates.sort(key=lambda item: (item[0], item[1]))
        return candidates[0][2]

    def _normalize_growth_label(self, text: str) -> str:
        return normalize_text(text).replace(" ", "")

    def _format_rendered_growth_chart_text(self, page_number: int, rates: Dict[str, float]) -> str:
        lines = [
            "[PDF图表OCR解析]",
            f"页码：{page_number}",
            "图表类型：mixed",
            "柱状图/直方图数据：",
        ]
        for name, value in rates.items():
            lines.append(f"- {name}: 系列=增长率，数值={self._format_percent(value)}")
        return "\n".join(lines)

    def _cleanup_document_text(self, text: str) -> str:
        lines: List[str] = []
        for raw_line in text.splitlines():
            line = self._strip_inline_page_artifacts(raw_line)
            line = normalize_text(line)
            if not line:
                continue
            lines.append(line)
        return "\n".join(self._deduplicate_adjacent_lines(lines))

    def _choose_auto_parse_mode(self, pdf_path: Path, page_texts: List[str]) -> str:
        page_count = len(page_texts)
        total_chars = sum(len(normalize_text(page_text)) for page_text in page_texts)
        chart_page_count = self._count_vision_candidate_pages(pdf_path, page_texts) if self.vision_client else 0

        if chart_page_count > 0:
            LOGGER.info(
                "pdf_auto_mode_selected | mode=vision_hybrid | source_name=%s | pages=%s | chars=%s | chart_pages=%s",
                pdf_path.name,
                page_count,
                total_chars,
                chart_page_count,
            )
            return "vision_hybrid"

        if (
            self.cleanup_client is not None
            and page_count <= self.auto_hybrid_max_pages
            and total_chars <= self.auto_hybrid_max_chars
            and self._looks_like_text_cleanup_needed(page_texts)
        ):
            LOGGER.info(
                "pdf_auto_mode_selected | mode=hybrid | source_name=%s | pages=%s | chars=%s",
                pdf_path.name,
                page_count,
                total_chars,
            )
            return "hybrid"

        LOGGER.info(
            "pdf_auto_mode_selected | mode=local | source_name=%s | pages=%s | chars=%s | chart_pages=%s",
            pdf_path.name,
            page_count,
            total_chars,
            chart_page_count,
        )
        return "local"

    def _count_vision_candidate_pages(self, pdf_path: Path, page_texts: List[str]) -> int:
        try:
            import fitz
        except ImportError:
            return 0

        try:
            document = fitz.open(str(pdf_path))
        except Exception:
            LOGGER.exception("pdf_auto_vision_scan_failed | source_name=%s", pdf_path.name)
            return 0

        try:
            count = 0
            for page_index in range(len(document)):
                try:
                    image_count = len(document[page_index].get_images(full=True))
                except Exception:
                    image_count = 0
                if image_count <= 0:
                    continue
                page_text = page_texts[page_index] if page_index < len(page_texts) else ""
                if self._chart_context_score(normalize_text(page_text)) > 0:
                    count += 1
            return count
        finally:
            document.close()

    def _looks_like_text_cleanup_needed(self, page_texts: List[str]) -> bool:
        text = "\n".join(page_texts[: min(len(page_texts), 20)])
        normalized = normalize_text(text)
        if not normalized:
            return False

        suspicious_chars = sum(1 for char in normalized if char in "�ÃÂâ€æçé鎷绗")
        suspicious_ratio = suspicious_chars / max(len(normalized), 1)
        lines = [line.strip() for line in normalized.splitlines() if line.strip()]
        short_line_ratio = sum(1 for line in lines if len(line) <= 8) / max(len(lines), 1)
        return suspicious_ratio >= 0.08 or (len(lines) >= 20 and short_line_ratio >= 0.45)

    def _refine_with_llm(self, text: str, source_name: str, effective_mode: str | None = None) -> str:
        parser_mode = (effective_mode or self.mode or "local").strip().lower()
        if parser_mode == "local":
            return text
        if parser_mode == "vision_hybrid":
            return text
        if parser_mode != "llm" and len(normalize_text(text)) < self.llm_cleanup_min_chars:
            return text
        if self.cleanup_client is None:
            LOGGER.warning("pdf_llm_cleanup_skipped | reason=no_client | source_name=%s | mode=%s", source_name, parser_mode)
            return text

        try:
            cleaned = self.cleanup_client.cleanup_text(text, source_name=source_name)
        except Exception:
            LOGGER.exception("pdf_llm_cleanup_failed | source_name=%s | mode=%s", source_name, parser_mode)
            return text

        if not normalize_text(cleaned):
            LOGGER.warning("pdf_llm_cleanup_empty | source_name=%s | mode=%s", source_name, parser_mode)
            return text
        return cleaned

    def _append_vision_chart_descriptions(self, text: str, pdf_path: Path, page_texts: List[str]) -> str:
        if self.vision_max_pages <= 0:
            return text
        if self.vision_client is None:
            LOGGER.warning("pdf_vision_skipped | reason=no_client | source_name=%s", pdf_path.name)
            return text

        try:
            import fitz
        except ImportError:
            LOGGER.warning("pdf_vision_skipped | reason=pymupdf_not_found | source_name=%s", pdf_path.name)
            return text

        try:
            document = fitz.open(str(pdf_path))
        except Exception:
            LOGGER.exception("pdf_vision_open_failed | source_name=%s", pdf_path.name)
            return text

        vision_parts: List[str] = []
        try:
            candidate_indexes = self._select_vision_candidate_pages(document, page_texts)
            for page_index in candidate_indexes[: self.vision_max_pages]:
                page_number = page_index + 1
                page_text = page_texts[page_index] if page_index < len(page_texts) else ""
                try:
                    page = document[page_index]
                    matrix = fitz.Matrix(self.vision_render_scale, self.vision_render_scale)
                    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                    image = Image.open(io.BytesIO(pixmap.tobytes("png")))
                    image.load()
                    image_png = self._prepare_vision_image_png(image)
                    description = self.vision_client.describe_page_image(
                        image_png=image_png,
                        page_number=page_number,
                        surrounding_text=page_text,
                        source_name=pdf_path.name,
                    )
                except RuntimeError as exc:
                    detail = str(exc)
                    LOGGER.error(
                        "pdf_vision_page_failed | source_name=%s | page=%s | detail=%s",
                        pdf_path.name,
                        page_number,
                        detail,
                    )
                    if "HTTP 403" in detail or "Model disabled" in detail or "Model does not exist" in detail:
                        LOGGER.error("pdf_vision_disabled_for_document | reason=model_unavailable | source_name=%s", pdf_path.name)
                        break
                    continue
                except Exception:
                    LOGGER.exception("pdf_vision_page_failed | source_name=%s | page=%s", pdf_path.name, page_number)
                    continue

                cleaned = self._cleanup_vision_description(description)
                if not cleaned or cleaned == "未发现可解析图表。":
                    continue
                LOGGER.info("pdf_vision_page_parsed | source_name=%s | page=%s", pdf_path.name, page_number)
                vision_parts.append(
                    "\n".join(
                        [
                            "[PDF图表视觉解析]",
                            f"文件：{pdf_path.name}",
                            f"页码：{page_number}",
                            cleaned,
                        ]
                    )
                )
        finally:
            document.close()

        if not vision_parts:
            return text
        return "\n\n".join(part for part in [text, *vision_parts] if normalize_text(part))

    def _select_vision_candidate_pages(self, document, page_texts: List[str]) -> List[int]:
        explicit_pages = self._parse_vision_target_pages(len(document))
        if explicit_pages:
            LOGGER.info("pdf_vision_candidates | explicit=%s", len(explicit_pages))
            return explicit_pages

        keyword_candidates: List[tuple[int, int]] = []
        fallback_candidates: List[int] = []
        for page_index in range(len(document)):
            try:
                image_count = len(document[page_index].get_images(full=True))
            except Exception:
                image_count = 0
            if image_count <= 0:
                continue

            page_text = page_texts[page_index] if page_index < len(page_texts) else ""
            normalized = normalize_text(page_text)
            chart_score = self._chart_context_score(normalized)
            if chart_score > 0:
                keyword_candidates.append((page_index, chart_score))
            elif len(normalized) < self.min_text_density_for_ocr:
                fallback_candidates.append(page_index)

        keyword_candidates.sort(key=lambda item: (-item[1], item[0]))
        keyword_indexes = [page_index for page_index, _score in keyword_candidates]
        selected = keyword_indexes + [index for index in fallback_candidates if index not in set(keyword_indexes)]
        LOGGER.info("pdf_vision_candidates | keyword=%s | fallback=%s | selected=%s", len(keyword_candidates), len(fallback_candidates), len(selected))
        return selected

    def _parse_vision_target_pages(self, page_count: int) -> List[int]:
        raw_value = (self.vision_target_pages or "").strip()
        if not raw_value:
            return []

        selected: List[int] = []
        for part in re.split(r"[,，\s]+", raw_value):
            if not part:
                continue
            range_match = re.fullmatch(r"(\d+)\s*[-~]\s*(\d+)", part)
            if range_match:
                start = int(range_match.group(1))
                end = int(range_match.group(2))
                if start > end:
                    start, end = end, start
                selected.extend(range(start - 1, end))
                continue
            if part.isdigit():
                selected.append(int(part) - 1)

        deduped: List[int] = []
        seen: set[int] = set()
        for page_index in selected:
            if page_index < 0 or page_index >= page_count or page_index in seen:
                continue
            deduped.append(page_index)
            seen.add(page_index)
        return deduped

    def _chart_context_score(self, text: str) -> int:
        if not text:
            return 0
        keyword_hits = sum(1 for keyword in self.vision_chart_keywords if keyword in text)
        has_number_signal = bool(re.search(r"\d+(\.\d+)?\s*(%|％|亿元|万元|元)", text))
        strong_hits = sum(
            1
            for keyword in (
                "资料来源",
                "增长率",
                "图表",
                "饼图",
                "柱状图",
                "直方图",
                "结构与增长",
                "组织结构",
                "组织架构",
                "销售组织",
                "大客户销售部",
            )
            if keyword in text
        )
        score = keyword_hits + (2 if has_number_signal else 0) + strong_hits * 3
        if score >= 4:
            return score
        return 0

    def _cleanup_vision_description(self, text: str) -> str:
        stripped = (text or "").strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            lines = stripped.splitlines()
            stripped = "\n".join(lines[1:-1]).strip()

        parsed = self._parse_vision_json(stripped)
        if parsed is not None:
            return self._format_vision_json_description(parsed)

        cleaned_lines: List[str] = []
        for raw_line in stripped.splitlines():
            line = normalize_text(raw_line)
            if line:
                cleaned_lines.append(line)
        return "\n".join(self._deduplicate_adjacent_lines(cleaned_lines))

    def _prepare_vision_image_png(self, image: Image.Image) -> bytes:
        cropped = self._crop_non_white_content(image)
        output = io.BytesIO()
        cropped.save(output, format="PNG")
        return output.getvalue()

    def _crop_chart_region(self, image: Image.Image) -> Image.Image:
        try:
            import cv2
            import numpy as np
        except ImportError:
            return self._crop_non_white_content(image)

        rgb = image.convert("RGB")
        array = np.array(rgb)
        height, width = array.shape[:2]
        gray = cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 60, 160)
        contours, _hierarchy = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidates: List[tuple[int, int, int, int, float]] = []
        page_area = width * height
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            if area < page_area * 0.025:
                continue
            if w < width * 0.25 or h < height * 0.08:
                continue
            if y > height * 0.85:
                continue
            score = area * (1.2 if y < height * 0.6 else 1.0)
            candidates.append((x, y, w, h, score))

        if not candidates:
            return self._crop_non_white_content(image)

        x, y, w, h, _score = max(candidates, key=lambda item: item[4])
        pad = max(16, int(min(width, height) * 0.015))
        left = max(0, x - pad)
        top = max(0, y - pad)
        right = min(width, x + w + pad)
        bottom = min(height, y + h + pad)

        if (right - left) * (bottom - top) < page_area * 0.05:
            return image
        return image.crop((left, top, right, bottom))

    def _crop_non_white_content(self, image: Image.Image) -> Image.Image:
        grayscale = ImageOps.grayscale(image)
        mask = grayscale.point(lambda px: 255 if px < 248 else 0, mode="L")
        bbox = mask.getbbox()
        if bbox is None:
            return image
        width, height = image.size
        left, top, right, bottom = bbox
        pad = max(16, int(min(width, height) * 0.015))
        return image.crop(
            (
                max(0, left - pad),
                max(0, top - pad),
                min(width, right + pad),
                min(height, bottom + pad),
            )
        )

    def _parse_vision_json(self, text: str) -> Dict[str, object] | None:
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if not match:
                return None
            try:
                parsed = json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, dict) else None

    def _format_vision_json_description(self, payload: Dict[str, object]) -> str:
        if payload.get("has_chart") is False:
            return "未发现可解析图表。"

        lines: List[str] = []
        title = normalize_text(str(payload.get("title", "")))
        chart_type = normalize_text(str(payload.get("chart_type", "")))
        confidence = payload.get("confidence", "")
        if title:
            lines.append(f"图表标题：{title}")
        if chart_type:
            lines.append(f"图表类型：{chart_type}")
        if confidence != "":
            lines.append(f"图表解析置信度：{confidence}")

        org_chart = payload.get("org_chart") or {}
        if isinstance(org_chart, dict):
            org_lines = self._format_org_chart(org_chart)
            if org_lines:
                lines.append("组织结构关系：")
                lines.extend(org_lines)

        pie_items = payload.get("pie") or []
        if isinstance(pie_items, list) and pie_items:
            lines.append("饼图数据：")
            for item in pie_items:
                if not isinstance(item, dict):
                    continue
                name = normalize_text(str(item.get("name", "")))
                amount = item.get("amount", "")
                unit = normalize_text(str(item.get("unit", "")))
                ratio = normalize_text(str(item.get("ratio", "")))
                values = []
                if amount not in ("", None):
                    values.append(f"金额/数值={amount}{unit}")
                if ratio:
                    values.append(f"占比={ratio}")
                lines.append(f"- {name}: {'，'.join(values) if values else '未识别数值'}")

            ratio_sum = self._sum_percentages(pie_items)
            if ratio_sum is not None:
                if abs(ratio_sum - 100.0) <= 2.0:
                    lines.append(f"校验：饼图占比合计约 {ratio_sum:.2f}%，接近 100%。")
                else:
                    lines.append(f"校验提示：饼图占比合计约 {ratio_sum:.2f}%，可能存在漏读或误读。")

        bar_items = payload.get("bar") or []
        if isinstance(bar_items, list) and bar_items:
            lines.append("柱状图/直方图数据：")
            lines.extend(self._format_series_values(bar_items))

        line_items = payload.get("line") or []
        if isinstance(line_items, list) and line_items:
            lines.append("折线图数据：")
            lines.extend(self._format_series_values(line_items))

        growth_items = payload.get("growth_rate") or []
        if isinstance(growth_items, list) and growth_items:
            lines.append("增长率数据：")
            for item in growth_items:
                if not isinstance(item, dict):
                    continue
                name = normalize_text(str(item.get("name", "")))
                rate = normalize_text(str(item.get("rate", "")))
                lines.append(f"- {name}: 增长率={rate or '未识别'}")

        other_values = payload.get("other_values") or []
        if isinstance(other_values, list) and other_values:
            lines.append("其他图表数值：")
            for item in other_values:
                if not isinstance(item, dict):
                    continue
                name = normalize_text(str(item.get("name", "")))
                value = normalize_text(str(item.get("value", "")))
                unit = normalize_text(str(item.get("unit", "")))
                lines.append(f"- {name}: {value}{unit}")

        source = normalize_text(str(payload.get("source", "")))
        notes = normalize_text(str(payload.get("notes", "")))
        if source:
            lines.append(f"资料来源：{source}")
        if notes:
            lines.append(f"备注：{notes}")

        return "\n".join(line for line in lines if line.strip())

    def _format_org_chart(self, org_chart: Dict[str, object]) -> List[str]:
        lines: List[str] = []
        hierarchy_text = org_chart.get("hierarchy_text") or []
        if isinstance(hierarchy_text, list):
            for item in hierarchy_text:
                line = normalize_text(str(item))
                if line:
                    lines.append(f"- {line}")

        edges = org_chart.get("edges") or []
        if isinstance(edges, list) and edges:
            lines.append("上下级边关系：")
            for item in edges:
                if not isinstance(item, dict):
                    continue
                parent = normalize_text(str(item.get("parent", "")))
                child = normalize_text(str(item.get("child", "")))
                if parent and child:
                    lines.append(f"- {parent} -> {child}")

        nodes = org_chart.get("nodes") or []
        if isinstance(nodes, list) and nodes:
            lines.append("节点层级：")
            for item in nodes:
                if not isinstance(item, dict):
                    continue
                name = normalize_text(str(item.get("name", "")))
                parent = normalize_text(str(item.get("parent", "")))
                level = item.get("level", "")
                if not name:
                    continue
                if parent:
                    lines.append(f"- level={level}，{name}，上级={parent}")
                else:
                    lines.append(f"- level={level}，{name}")

        return self._deduplicate_adjacent_lines(lines)

    def _format_series_values(self, items: List[object]) -> List[str]:
        lines: List[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = normalize_text(str(item.get("name", "")))
            value = normalize_text(str(item.get("value", "")))
            unit = normalize_text(str(item.get("unit", "")))
            series = normalize_text(str(item.get("series", "")))
            parts = []
            if series:
                parts.append(f"系列={series}")
            if value:
                parts.append(f"数值={value}{unit}")
            if name:
                lines.append(f"- {name}: {'，'.join(parts) if parts else '未识别数值'}")
        return lines

    def _format_growth_extrema(self, growth_items: List[object], bar_items: List[object]) -> List[str]:
        return []

    def _collect_growth_rates_from_growth_items(self, items: List[object]) -> List[tuple[str, float]]:
        rates: List[tuple[str, float]] = []
        if not isinstance(items, list):
            return rates
        for item in items:
            if not isinstance(item, dict):
                continue
            name = normalize_text(str(item.get("name", "")))
            value = self._extract_percent(str(item.get("rate", "")))
            if name and value is not None:
                rates.append((name, value))
        return rates

    def _collect_growth_rates_from_bar_items(self, items: List[object]) -> List[tuple[str, float]]:
        rates: List[tuple[str, float]] = []
        if not isinstance(items, list):
            return rates
        for item in items:
            if not isinstance(item, dict):
                continue
            name = normalize_text(str(item.get("name", "")))
            series = normalize_text(str(item.get("series", "")))
            unit = normalize_text(str(item.get("unit", "")))
            value_text = normalize_text(str(item.get("value", "")))
            combined = f"{name} {series} {value_text} {unit}"
            if "增长" not in combined and "%" not in combined and "％" not in combined:
                continue
            value = self._extract_percent(f"{value_text}{unit}")
            if name and value is not None:
                rates.append((name, value))
        return rates

    def _extract_percent(self, text: str) -> float | None:
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            return None
        return float(match.group(0))

    def _format_percent(self, value: float) -> str:
        formatted = f"{value:.2f}".rstrip("0").rstrip(".")
        return f"{formatted}%"

    def _sum_percentages(self, items: List[object]) -> float | None:
        values: List[float] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            raw_ratio = str(item.get("ratio", ""))
            match = re.search(r"-?\d+(?:\.\d+)?", raw_ratio)
            if match:
                values.append(float(match.group(0)))
        if not values:
            return None
        return sum(values)

    def _iter_page_images(self, page) -> List[Image.Image]:
        images: List[Image.Image] = []
        image_refs = getattr(page, "images", None) or []
        for image_ref in image_refs:
            try:
                image = Image.open(io.BytesIO(image_ref.data))
                image.load()
            except Exception:
                continue
            images.append(image)
        return images

    def _render_pdf_pages_to_images(self, pdf_path: Path) -> List[Image.Image]:
        try:
            import fitz
        except ImportError:
            LOGGER.debug("pymupdf_not_found | pdf=%s", pdf_path.name)
            return []

        images: List[Image.Image] = []
        try:
            document = fitz.open(str(pdf_path))
        except Exception:
            LOGGER.exception("pdf_render_open_failed | pdf=%s", pdf_path.name)
            return []

        try:
            matrix = fitz.Matrix(2, 2)
            for page in document:
                try:
                    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                    image = Image.open(io.BytesIO(pixmap.tobytes("png")))
                    image.load()
                    images.append(image)
                except Exception:
                    LOGGER.exception("pdf_render_page_failed | pdf=%s | page=%s", pdf_path.name, page.number + 1)
        finally:
            document.close()
        return images

    def _ocr_available(self) -> bool:
        if self._tesseract_cmd is not None:
            return bool(self._tesseract_cmd)
        self._tesseract_cmd = shutil.which("tesseract")
        if not self._tesseract_cmd:
            LOGGER.debug("tesseract_not_found")
        return bool(self._tesseract_cmd)

    def _ocr_image(self, image: Image.Image) -> str:
        if not self._ocr_available():
            return ""

        processed = self._prepare_image_for_ocr(image)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            processed.save(temp_path)

        try:
            command = [
                self._tesseract_cmd or "tesseract",
                str(temp_path),
                "stdout",
                "-l",
                self.ocr_lang,
                "--psm",
                "6",
            ]
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                check=False,
            )
            if completed.returncode != 0:
                stderr = normalize_text(completed.stderr)
                LOGGER.warning("tesseract_failed | detail=%s", stderr or completed.returncode)
                return ""
            return self._postprocess_ocr_text(completed.stdout)
        finally:
            temp_path.unlink(missing_ok=True)

    def _prepare_image_for_ocr(self, image: Image.Image) -> Image.Image:
        if image.mode not in ("L", "RGB"):
            image = image.convert("RGB")
        grayscale = ImageOps.grayscale(image)
        width, height = grayscale.size
        edge = max(width, height)
        if edge < self.ocr_min_image_edge and edge > 0:
            scale = self.ocr_min_image_edge / edge
            grayscale = grayscale.resize(
                (max(1, int(width * scale)), max(1, int(height * scale))),
                Image.Resampling.LANCZOS,
            )
        enhanced = ImageOps.autocontrast(grayscale)
        return enhanced.point(lambda px: 0 if px < 180 else 255, mode="1")

    def _postprocess_ocr_text(self, text: str) -> str:
        lines = self._split_to_lines(text)
        filtered = [line for line in lines if not self._looks_like_page_number(line)]
        return "\n".join(filtered)

    def _remove_repeated_page_lines(self, page_texts: List[str]) -> str:
        pages_lines: List[List[str]] = []
        counter: Counter[str] = Counter()

        for page_text in page_texts:
            unique_lines: List[str] = []
            seen: set[str] = set()
            for raw_line in page_text.splitlines():
                line = normalize_text(raw_line)
                if not line:
                    continue
                unique_lines.append(line)
                if len(line) >= _MIN_REPEAT_LENGTH and line not in seen:
                    line_key = self._repeat_detection_key(line)
                    counter[line_key] += 1
                    seen.add(line_key)
            pages_lines.append(unique_lines)

        page_count = max(len(pages_lines), 1)
        repeated_lines = {
            line
            for line, count in counter.items()
            if count / page_count >= self.repeated_line_threshold and not self._looks_like_meaningful_heading(line)
        }

        cleaned_pages: List[str] = []
        for lines in pages_lines:
            filtered = [line for line in lines if self._repeat_detection_key(line) not in repeated_lines]
            cleaned_pages.append("\n".join(self._deduplicate_adjacent_lines(filtered)))
        return "\n\n".join(page for page in cleaned_pages if page.strip())

    def _remove_inline_page_noise(self, text: str) -> str:
        cleaned_lines: List[str] = []
        for raw_line in text.splitlines():
            line = normalize_text(raw_line)
            if not line:
                continue
            if self.remove_page_number_lines and self._looks_like_page_number(line):
                continue
            if self._looks_like_watermark(line):
                continue
            cleaned_lines.append(line)
        return "\n".join(self._deduplicate_adjacent_lines(cleaned_lines))

    def _split_to_lines(self, text: str) -> List[str]:
        return [normalize_text(part) for part in re.split(r"[\r\n]+", text) if normalize_text(part)]

    def _deduplicate_adjacent_lines(self, lines: List[str]) -> List[str]:
        deduped: List[str] = []
        previous = ""
        for line in lines:
            if line == previous:
                continue
            deduped.append(line)
            previous = line
        return deduped

    def _resolve_x_position(self, cm, tm) -> float:
        for matrix in (tm, cm):
            try:
                if matrix and len(matrix) > 4 and matrix[4] is not None:
                    return float(matrix[4])
            except (TypeError, ValueError):
                continue
        return 0.0

    def _resolve_y_position(self, cm, tm) -> float:
        for matrix in (tm, cm):
            try:
                if matrix and len(matrix) > 5 and matrix[5] is not None:
                    return float(matrix[5])
            except (TypeError, ValueError):
                continue
        return 0.0

    def _looks_like_page_number(self, text: str) -> bool:
        compact = text.strip()
        if re.fullmatch(r"\d+\s*[-/]\s*\d+\s*[-/]\s*\d+", compact):
            return True
        if re.fullmatch(r"第?\s*\d+\s*页", compact):
            return True
        if re.fullmatch(r"page\s+\d+(\s+of\s+\d+)?", compact, flags=re.IGNORECASE):
            return True
        return bool(re.fullmatch(r"[0-9A-Za-z.\-_/]{1,12}", compact))

    def _looks_like_watermark(self, text: str) -> bool:
        compact = text.strip()
        if len(compact) < 4:
            return False
        if re.fullmatch(r"[A-Za-z0-9/\\_.:\- ]{6,}", compact):
            return True
        if "www." in compact.lower() or "http" in compact.lower():
            return True
        if compact.count(" ") >= 4 and len(set(compact.replace(" ", ""))) <= 6:
            return True
        return False

    def _strip_inline_page_artifacts(self, text: str) -> str:
        cleaned = text
        cleaned = re.sub(r"\b\d{1,4}\s*-\s*\d{1,4}\s*-\s*\d{1,4}\b", " ", cleaned)
        cleaned = re.sub(r"\b第\s*\d+\s*页\b", " ", cleaned)
        cleaned = re.sub(r"\bPage\s+\d+(\s+of\s+\d+)?\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        return cleaned.strip()

    def _repeat_detection_key(self, text: str) -> str:
        compact = self._strip_inline_page_artifacts(text)
        compact = re.sub(r"\[[^\]]*\]|\([^\)]*\)|【[^】]*】", " ", compact)
        compact = re.sub(r"\s+", " ", compact)
        return compact.strip()

    def _looks_like_meaningful_heading(self, text: str) -> bool:
        compact = text.strip()
        if len(compact) <= 4:
            return True
        if re.search(r"[一二三四五六七八九十]+[、.．]", compact):
            return True
        if "章" in compact or "节" in compact:
            return True
        return False
