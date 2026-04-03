from __future__ import annotations

from ui.app import create_app


def _has_elem_id(config: dict, elem_id: str) -> bool:
    return any((component.get("props") or {}).get("elem_id") == elem_id for component in config.get("components", []))


def test_create_app_uses_single_workspace_shell():
    config = create_app().get_config_file()

    assert not any(component.get("type") == "tabs" for component in config.get("components", []))
    assert _has_elem_id(config, "workspace_grid")
    assert _has_elem_id(config, "sidebar_shell")
    assert _has_elem_id(config, "workspace_shell")
    assert _has_elem_id(config, "chat_shell")
    assert _has_elem_id(config, "composer_shell")


def test_create_app_keeps_secondary_controls_nested_under_chat():
    config = create_app().get_config_file()

    accordion_labels = {
        (component.get("props") or {}).get("label")
        for component in config.get("components", [])
        if component.get("type") == "accordion"
    }

    assert "Model & Backend" in accordion_labels
    assert "Voice & Devices" in accordion_labels
    assert "Profile & Personalization" in accordion_labels
    assert "Diagnostics" in accordion_labels
