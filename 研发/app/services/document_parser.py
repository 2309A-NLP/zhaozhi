"""解析上传文档并提取纯文本内容。"""  # 说明当前模块或代码块的用途。
from __future__ import annotations  # 从 __future__ 中导入所需对象。

from io import BytesIO  # 从 io 中导入所需对象。
from pathlib import Path  # 从 pathlib 中导入所需对象。
from typing import List  # 从 typing 中导入所需对象。

import numpy as np  # 导入所需的模块或对象：numpy。

try:  # 开始尝试执行可能出错的代码。
    from docx import Document as DocxDocument  # 从 docx 中导入所需对象。
except Exception:  # 捕获并处理前面代码抛出的异常。
    DocxDocument = None  # 设置 DocxDocument 的值，供后续逻辑使用。

try:  # 开始尝试执行可能出错的代码。
    import fitz  # fitz 就是 PyMuPDF，只不过在 PyMuPDF v1.24.3 之后，官方就推荐使用 pymupdf 作为主要的导入名
except Exception:  # 捕获并处理前面代码抛出的异常。
    fitz = None  # 设置 fitz 的值，供后续逻辑使用。

try:  # 开始尝试执行可能出错的代码。
    from paddleocr import PaddleOCR  # 从 paddleocr 中导入所需对象。
except Exception:  # 捕获并处理前面代码抛出的异常。
    PaddleOCR = None  # 设置 PaddleOCR 的值，供后续逻辑使用。

try:  # 开始尝试执行可能出错的代码。
    from pypdf import PdfReader  # 从 pypdf 中导入所需对象。
except Exception:  # 捕获并处理前面代码抛出的异常。
    PdfReader = None  # 设置 PdfReader 的值，供后续逻辑使用。


_ocr_engine = None  # 设置 _ocr_engine 的值，供后续逻辑使用。


def _require_dependency(value, message: str):  # 定义函数 _require_dependency，用于封装可复用的逻辑。

    if value is None:  # 根据条件决定是否执行下面的代码块。
        raise ValueError(message)  # 抛出异常以中断当前流程。
    return value  # 返回当前函数计算出的结果。


def _get_ocr_engine():  # 定义函数 _get_ocr_engine，用于封装可复用的逻辑。

    global _ocr_engine  # 执行这一行代码，完成当前逻辑。
    if _ocr_engine is None and PaddleOCR is not None:  # 根据条件决定是否执行下面的代码块。
        _ocr_engine = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)  # 调用 PaddleOCR 并把结果保存到 _ocr_engine 中。
    return _ocr_engine  # 返回当前函数计算出的结果。


def _extract_pdf_text(content: bytes) -> str:

    reader_cls = _require_dependency(PdfReader, "当前环境未安装 PDF 解析依赖 pypdf")  # 调用 _require_dependency 并把结果保存到 reader_cls 中。
    reader = reader_cls(BytesIO(content))  # 调用 reader_cls 并把结果保存到 reader 中。
    extracted = "\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()  # 设置 extracted 的值，供后续逻辑使用。
    return extracted or _extract_pdf_text_by_ocr(content)  # 返回当前函数计算出的结果。


def _extract_pdf_text_by_ocr(content: bytes) -> str:  # 定义函数 _extract_pdf_text_by_ocr，用于封装可复用的逻辑。
    fitz_module = _require_dependency(fitz, "当前环境未安装 PDF 图像解析依赖 PyMuPDF")  # 调用 _require_dependency 并把结果保存到 fitz_module 中。
    ocr = _require_dependency(_get_ocr_engine(), "当前环境未安装 OCR 依赖 paddleocr / paddlepaddle")  # 调用 _require_dependency 并把结果保存到 ocr 中。

    pdf = fitz_module.open(stream=content, filetype="pdf")  # 调用 fitz_module.open 并把结果保存到 pdf 中。
    page_texts: List[str] = []  # 执行这一行代码，完成当前逻辑。
    for page in pdf:  # 遍历目标数据中的每一项。
        pix = page.get_pixmap(matrix=fitz_module.Matrix(2, 2), alpha=False)  # 调用 page.get_pixmap 并把结果保存到 pix 中。
        image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)  # 调用 np.frombuffer 并把结果保存到 image 中。
        lines: List[str] = []  # 执行这一行代码，完成当前逻辑。
        for block in ocr.ocr(image, cls=True) or []:  # 遍历目标数据中的每一项。
            if not block:  # 根据条件决定是否执行下面的代码块。
                continue  # 跳过本次循环的剩余逻辑。
            for item in block:  # 遍历目标数据中的每一项。
                if not item or len(item) < 2:  # 根据条件决定是否执行下面的代码块。
                    continue  # 跳过本次循环的剩余逻辑。
                text_info = item[1]  # 设置 text_info 的值，供后续逻辑使用。
                if isinstance(text_info, (list, tuple)) and text_info:  # 根据条件决定是否执行下面的代码块。
                    line_text = str(text_info[0]).strip()  # 调用 str 并把结果保存到 line_text 中。
                    if line_text:  # 根据条件决定是否执行下面的代码块。
                        lines.append(line_text)  # 调用 lines.append 处理当前这一步逻辑。
        if lines:  # 根据条件决定是否执行下面的代码块。
            page_texts.append("\n".join(lines).strip())  # 调用 page_texts.append 处理当前这一步逻辑。
    return "\n\n".join(page_texts).strip()  # 返回当前函数计算出的结果。


def _extract_docx_text(content: bytes) -> str:  # 定义函数 _extract_docx_text，用于封装可复用的逻辑。
    document_cls = _require_dependency(DocxDocument, "当前环境未安装 Word 解析依赖 python-docx")  # 调用 _require_dependency 并把结果保存到 document_cls 中。
    document = document_cls(BytesIO(content))  # 调用 document_cls 并把结果保存到 document 中。
    return "\n".join(paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip())  # 返回当前函数计算出的结果。


def extract_text(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md", ".csv", ".json", ".log"}:
        return content.decode("utf-8", errors="ignore").strip()
    if suffix == ".pdf":
        return _extract_pdf_text(content)
    if suffix == ".docx":
        return _extract_docx_text(content)
    raise ValueError(f"暂不支持的文件类型：{suffix or 'unknown'}")
