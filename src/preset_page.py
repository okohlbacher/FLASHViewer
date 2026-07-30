"""The View presets page, shared by FLASHDeconv and FLASHTnT.

Replaces hand-building a grid for the common cases. A custom layout is still
reachable, but it is no longer the only way in.
"""
import json
from pathlib import Path

import streamlit as st

from src import presets as presets_mod
from src.workflow.FileManager import FileManager


def _param_key(tool):
    return f"view_preset_{tool}"


def selected_preset_id(tool):
    """The preset the user picked, falling back to the tool's default."""
    return st.session_state.get(_param_key(tool)) or presets_mod.default_id(tool)


def selected_rows(tool):
    """The grid rows for the current preset, prerequisites already satisfied.

    Returns None when the user has a custom layout saved, so the viewer keeps
    using that.
    """
    preset = presets_mod.get(tool, selected_preset_id(tool))
    if preset is None:
        return None
    rows, _ = presets_mod.expand_prerequisites(tool, preset["rows"])
    return rows


def _cache_dir(tool):
    return {"FLASHDeconv": "flashdeconv", "FLASHTnT": "flashtnt"}[tool]


def render(tool, required_tags):
    """Draw the page. `required_tags` are the fields a dataset needs to exist."""
    st.title("View presets")
    st.caption(
        "Pick the view that matches the question you are asking. "
        "Presets that need data this run does not have are shown greyed out, "
        "with the reason."
    )

    file_manager = FileManager(
        st.session_state["workspace"],
        Path(st.session_state["workspace"], _cache_dir(tool), "cache"),
    )
    datasets = file_manager.get_results_list(required_tags)

    if not datasets:
        st.info(
            "No datasets in this workspace yet. Run an analysis or upload "
            "FLASH\\* output, then come back to choose a view."
        )
        return

    dataset = st.selectbox("Dataset", datasets, key=f"preset_dataset_{tool}")
    has_sequence = bool(st.session_state.get("input_sequence"))
    current = selected_preset_id(tool)

    for preset, available, reason in presets_mod.for_dataset(
        tool, file_manager, dataset, has_sequence
    ):
        with st.container(border=True):
            head, action = st.columns([5, 1], vertical_alignment="center")
            is_current = preset["id"] == current
            head.markdown(f"**{preset['name']}**" + (" — current" if is_current else ""))
            head.caption(preset["description"])

            rows, _ = presets_mod.expand_prerequisites(tool, preset["rows"])
            head.caption(
                " · ".join(
                    " | ".join(presets_mod.label(c) for c in row) for row in rows
                )
            )

            if available:
                head.caption(":green[Available]")
            else:
                head.caption(f":orange[Not available — {reason}]")

            if action.button(
                "Use", key=f"use_{tool}_{preset['id']}",
                disabled=not available or is_current,
            ):
                st.session_state[_param_key(tool)] = preset["id"]
                # A preset and a hand-built layout cannot both be in charge.
                st.session_state.pop(_saved_key(tool), None)
                st.rerun()

    st.divider()
    _render_interchange(tool)


def _saved_key(tool):
    return "saved_layout_setting" if tool == "FLASHDeconv" else "saved_layout_setting_tagger"


def _render_interchange(tool):
    """Import/export, kept compatible with the old settings file plus a tool tag."""
    with st.expander("Import / export a layout"):
        st.caption(
            "Exported layouts now record which tool they belong to. Importing a "
            "layout built for the other tool is refused rather than crashing on "
            "an unknown component name."
        )

        rows = selected_rows(tool) or []
        st.download_button(
            "Export current view",
            data=json.dumps({"tool": tool, "layout": [rows]}, indent=2),
            file_name="FLASHViewer_layout_settings.json",
            mime="application/json",
            disabled=not rows,
        )

        uploaded = st.file_uploader("Import a layout", type="json", key=f"import_{tool}")
        if uploaded is not None:
            try:
                payload = json.load(uploaded)
            except json.JSONDecodeError as exc:
                st.error(f"Not valid JSON: {exc}")
                return

            # Old files are a bare list of experiments and carry no tool tag.
            if isinstance(payload, dict):
                if payload.get("tool") not in (None, tool):
                    st.error(
                        f"That layout was built for {payload['tool']}, not {tool}."
                    )
                    return
                layout = payload.get("layout") or []
            else:
                layout = payload

            if not layout or not layout[0]:
                st.error("That file contains no layout.")
                return

            known = set(presets_mod.PREREQUISITES[tool]) | set(
                presets_mod.PREREQUISITES[tool].values()
            )
            unknown = [
                c for row in layout[0] for c in row
                if c not in known and c not in _EXTRA_COMPONENTS[tool]
            ]
            if unknown:
                st.error(f"Unknown component(s) for {tool}: {', '.join(sorted(set(unknown)))}")
                return

            repaired, added = presets_mod.expand_prerequisites(tool, layout[0])
            st.session_state[_saved_key(tool)] = [repaired]
            st.session_state.pop(_param_key(tool), None)
            if added:
                st.toast(f"Added missing prerequisite(s): {', '.join(added)}")
            st.success("Layout imported.")


# Components with no prerequisite of their own, so absent from PREREQUISITES.
_EXTRA_COMPONENTS = {
    "FLASHDeconv": {"ms1_raw_heatmap", "ms1_deconv_heat_map", "scan_table", "fdr_plot"},
    "FLASHTnT": {"protein_table"},
}
