from __future__ import annotations

from paragraphs.types import (
    BLOCK_CONTENT_KIND,
    RENDER_CUSTOM_BLOCK,
    RENDER_DECORATED_TEXT,
    CommandTransitionSpec,
    DecorationSpec,
    ExportSpec,
    LayoutSpec,
    ParagraphTypeSpec,
)


def build_builtin_paragraph_type_specs() -> dict[str, ParagraphTypeSpec]:
    heading_tags = {
        "heading_1": ("Heading 1", 32, "heading_1"),
        "heading_2": ("Heading 2", 28, "heading_2"),
        "heading_3": ("Heading 3", 24, "heading_3"),
        "heading_4": ("Heading 4", 20, "heading_4"),
        "heading_5": ("Heading 5", 18, "heading_5"),
    }
    registry: dict[str, ParagraphTypeSpec] = {
        "empty": ParagraphTypeSpec(
            tag="empty",
            display_name="Empty",
            layout=LayoutSpec(rendered_font_size=16, line_height=24.0, bottom_margin=8.0),
            export=ExportSpec(markdown_role="empty"),
        ),
        "body": ParagraphTypeSpec(
            tag="body",
            display_name="Body",
            layout=LayoutSpec(rendered_font_size=16, line_height=24.0, bottom_margin=8.0),
            export=ExportSpec(markdown_role="body"),
        ),
        "body_small": ParagraphTypeSpec(
            tag="body_small",
            display_name="Body Small",
            layout=LayoutSpec(rendered_font_size=14, line_height=20.0, bottom_margin=8.0),
            export=ExportSpec(markdown_role="body"),
        ),
        "ordered_item": ParagraphTypeSpec(
            tag="ordered_item",
            display_name="Ordered List Item",
            render_kind=RENDER_DECORATED_TEXT,
            contagious=True,
            allows_empty_persistence=False,
            layout=LayoutSpec(
                rendered_font_size=12,
                line_height=20.0,
                top_margin=8.0,
                bottom_margin=8.0,
                left_margin=28.0,
                prefixed_item_gap=4.0,
                prefix_gap=6.0,
                ordered_prefix_min_digits=3,
                expand_text_start=True,
            ),
            decoration=DecorationSpec(prefix_kind="ordered_list"),
            commands=CommandTransitionSpec(
                create_command="/ord/",
                create_from_tag="*",
                clean_to_tag="empty",
            ),
            export=ExportSpec(markdown_role="ordered_item"),
        ),
        "unordered_item": ParagraphTypeSpec(
            tag="unordered_item",
            display_name="Unordered List Item",
            render_kind=RENDER_DECORATED_TEXT,
            contagious=True,
            allows_empty_persistence=False,
            layout=LayoutSpec(
                rendered_font_size=12,
                line_height=20.0,
                top_margin=8.0,
                bottom_margin=8.0,
                left_margin=28.0,
                prefixed_item_gap=4.0,
                prefix_gap=6.0,
            ),
            decoration=DecorationSpec(prefix_kind="unordered_list"),
            commands=CommandTransitionSpec(
                create_command="/unord/",
                create_from_tag="*",
                clean_to_tag="empty",
            ),
            export=ExportSpec(markdown_role="unordered_item"),
        ),
        "image": ParagraphTypeSpec(
            tag="image",
            display_name="Image",
            content_kind=BLOCK_CONTENT_KIND,
            render_kind=RENDER_CUSTOM_BLOCK,
            uses_runs=False,
            allows_text_input=False,
            decoration=DecorationSpec(custom_renderer="image_block"),
            export=ExportSpec(markdown_role="image"),
        ),
        "canvas": ParagraphTypeSpec(
            tag="canvas",
            display_name="Canvas",
            content_kind=BLOCK_CONTENT_KIND,
            render_kind=RENDER_CUSTOM_BLOCK,
            uses_runs=False,
            allows_text_input=False,
            decoration=DecorationSpec(custom_renderer="canvas_block"),
            export=ExportSpec(markdown_role="canvas"),
        ),
    }
    for tag, (display_name, font_size, markdown_role) in heading_tags.items():
        registry[tag] = ParagraphTypeSpec(
            tag=tag,
            display_name=display_name,
            layout=LayoutSpec(
                rendered_font_size=font_size,
                line_height={18: 26.0, 20: 28.0, 24: 32.0, 28: 36.0, 32: 40.0}[font_size],
                top_margin=0.0,
                bottom_margin=8.0,
            ),
            export=ExportSpec(markdown_role=markdown_role),
        )
    return registry
