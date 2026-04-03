from slopmeter_py.output_path import (
    ProviderSelectionValues,
    get_default_output_path,
    get_default_output_suffix,
)


def create_values(**overrides):
    return ProviderSelectionValues(**overrides)


def test_default_output_path_stays_unsuffixed_when_no_provider_flags_are_set():
    assert get_default_output_path(create_values(), "png") == "./heatmap-last-year.png"


def test_default_output_path_adds_cursor_for_cursor_flag():
    assert (
        get_default_output_path(create_values(cursor=True), "png")
        == "./heatmap-last-year_cursor.png"
    )


def test_default_output_path_adds_all_for_all_flag():
    assert (
        get_default_output_path(create_values(all=True, cursor=True), "json")
        == "./heatmap-last-year_all.json"
    )


def test_default_output_path_reflects_multiple_explicit_provider_flags():
    assert (
        get_default_output_path(
            create_values(codex=True, cursor=True, pi=True),
            "svg",
        )
        == "./heatmap-last-year_codex_cursor_pi.svg"
    )


def test_default_output_suffix_follows_provider_flag_order():
    assert (
        get_default_output_suffix(
            create_values(pi=True, gemini=True, amp=True, opencode=True)
        )
        == "_amp_gemini_opencode_pi"
    )

