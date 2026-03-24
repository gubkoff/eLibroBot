"""Блоки верстки PDF-накладной."""

from report.pdf_blocks.header_block import build_header_table, resolve_doc_header
from report.pdf_blocks.items_block import build_items_table
from report.pdf_blocks.parties_block import build_parties_story
from report.pdf_blocks.totals_block import build_totals_story

__all__ = [
    "build_header_table",
    "resolve_doc_header",
    "build_items_table",
    "build_parties_story",
    "build_totals_story",
]

