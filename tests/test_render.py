from slopmeter.render import TextNode, resolve_text_draw_origin


def test_resolve_text_draw_origin_uses_bbox_edges_for_end_alignment():
    node = TextNode(
        x=500,
        y=100,
        text="640M",
        fill="#000000",
        font_size=14,
        anchor="end",
    )

    draw_x, draw_y = resolve_text_draw_origin(
        node,
        scale=1.0,
        bbox=(4, 10, 104, 40),
    )

    assert draw_x == 396
    assert draw_y == 90


def test_resolve_text_draw_origin_uses_bbox_center_for_middle_alignment():
    node = TextNode(
        x=500,
        y=100,
        text="640M",
        fill="#000000",
        font_size=14,
        anchor="middle",
        baseline="middle",
    )

    draw_x, draw_y = resolve_text_draw_origin(
        node,
        scale=2.0,
        bbox=(4, 10, 104, 40),
    )

    assert draw_x == 946
    assert draw_y == 175
