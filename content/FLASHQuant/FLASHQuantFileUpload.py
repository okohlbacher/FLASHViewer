import pandas as pd
import streamlit as st

from pathlib import Path

from src.Workflow import QuantWorkflow
from src.parse.quant import parseQuant
from src.common.common import page_setup, desktop_file_picker
from src.workflow.StreamlitUI import DESKTOP
from src import confirm


# page initialization
params = page_setup()

wf = QuantWorkflow()

st.title("Add data")

# Wizard banner. Mounted ABOVE st.tabs deliberately: it must not sit inside a
# tab body, because st.tabs renders every body on load and execution() depends
# on that. State is derived in src/tools.py; nothing here constructs a
# FileManager for another tool.
from src import wizard
from src.tools import TOOLS
_spec = TOOLS["FLASHQuant"]
_files_dir = Path(wf.workflow_dir, "input-files", "mzML-files")
_selected = wizard.selected_names(wf.params, "mzML-files")
wizard.banner(wizard.build_steps(_spec, wf, wf.params, _files_dir, _selected))

def process_uploaded_files(uploaded_files):
        
        # Store all uploaded files
        for file in uploaded_files:
            
            if file.name.endswith("tsv"):
                if file.name.endswith('.mts.tsv'):
                    wf.file_manager.store_file(
                        file.name.split('.mts.tsv')[0], 'trace_tsv', file
                    )
                elif file.name.endswith('_shared.tsv'):
                    wf.file_manager.store_file(
                        file.name.split('_shared.tsv')[0], 'conflict_tsv', file
                    )
                elif file.name.endswith('.tsv'):
                    wf.file_manager.store_file(
                        file.name.split('.tsv')[0], 'quant_tsv', file
                    )
                else:
                    st.warning(f'Invalid file : {file.name}')
            else:
                st.warning(f'Invalid file : {file.name}')
        
        # Get the unparsed files
        input_files = set(wf.file_manager.get_results_list(['quant_tsv', 'trace_tsv']))
        parsed_files = set(wf.file_manager.get_results_list(['quant_dfs']))
        unparsed_files = input_files - parsed_files

        # Get the unpared conflict resolution files
        tsv_files = set(wf.file_manager.get_results_list(['conflict_tsv']))
        parsed_tsv_files = set(wf.file_manager.get_results_list(['conflict_resolution_dfs']))
        unparsed_tsv_files = (tsv_files - parsed_tsv_files) & input_files

        # Process unparsed datasets. Parsing is a phase of the work, not a
        # silent gap after it: on real data this runs for minutes. FLASHQuant
        # never got this when the other two did — the cost of three copies.
        pending = sorted(unparsed_files | unparsed_tsv_files)
        if pending:
            _status = st.status(f"Parsing {len(pending)} dataset(s)…", expanded=True)
            _progress = _status.progress(0.0)
        for _i, unparsed_dataset in enumerate(pending):
            _status.write(f"Parsing {unparsed_dataset} ({_i + 1}/{len(pending)})")
            results = wf.file_manager.get_results(
                unparsed_dataset, ['quant_tsv', 'trace_tsv']
            )

            # FLASHQuant needs both; a lone quant or trace file would otherwise
            # raise a bare KeyError, as FLASHTnT did.
            missing = [t for t in ('quant_tsv', 'trace_tsv') if t not in results]
            if missing:
                _status.write(
                    f":orange[Skipped {unparsed_dataset} — needs both files; "
                    f"missing: {', '.join(missing)}]"
                )
                _progress.progress((_i + 1) / len(pending))
                continue

            conflict_results = None
            if wf.file_manager.result_exists(unparsed_dataset, 'conflict_tsv'):
                conflict_results = wf.file_manager.get_results(
                    unparsed_dataset, ['conflict_tsv']
                )['conflict_tsv']
            
            parsed_data = parseQuant(
                results['quant_tsv'], results['trace_tsv'], conflict_results
            )

            for k, v in parsed_data.items():
                wf.file_manager.store_data(unparsed_dataset, k, v)
            _progress.progress((_i + 1) / len(pending))

        if pending:
            _status.update(label=f"Parsed {len(pending)} dataset(s)", state="complete",
                           expanded=False)


tabs = st.tabs(["File Upload", "Example Data"])

# Load Example Data
with tabs[1]:
    st.markdown("An example truncated file from the E. coli & ThermoFisher Pierce Intact Protein Standard Mix dataset.")
    _, c2, _ = st.columns(3)
    if c2.button("Load Example Data", type="primary"):
        # loading and copying example files into default workspace
        for filename_postfix, name_tag in zip(
            ['*.fq.tsv', '*.fq.mts.tsv', '*.fq_shared.tsv'],
            ['quant_tsv', 'trace_tsv', 'conflict_tsv']
        ):
            for file in Path("example-data/flashquant").glob(filename_postfix):
                wf.file_manager.store_file(
                    file.name.replace(filename_postfix[1:], ''), 
                    name_tag, file, remove=False
                )
        process_uploaded_files([])
        st.success("Example files loaded!")

# Upload files via upload widget
with tabs[0]:
    # Upload files via upload widget
    st.subheader("**Upload FLASHQuant output files**")

    # Display info how to upload files
    st.info(
        """
    **How to upload files**
    
    1. Browse files on your computer or drag and drops files
    2. Click the **Add the uploaded quant files** button to use them in the workflows
    
    Select data for analysis from the uploaded files shown below.
    
    **Make sure that the same number of FLASHQuant result files (\*fq.tsv and \*fq.mts.tsv) are uploaded!**
    
    **To visualize conflict resolution, \*fq_shared.tsv files should be uploaded**
    """
    )
    if DESKTOP:
        # No upload step: reference the files where they already are.
        picked = desktop_file_picker(
            "Add FLASHQuant output files", ["tsv"], key="fq_pick"
        )
        if picked:
            process_uploaded_files(picked)
            st.success(f"Added {len(picked)} file(s).")
            st.rerun()
    else:
      with st.form('files_uploader_form', clear_on_submit=True):
        uploaded_files = st.file_uploader(
            "FLASHQuant output files", accept_multiple_files=True
        )
        _, c2, _ = st.columns(3)
        # User needs to click button to upload selected files
        if c2.form_submit_button("Add files to workspace", type="primary"):
                if uploaded_files:
                    # A list of files is required, since online allows only single upload, create a list
                    if type(uploaded_files) != list:
                        uploaded_files = [uploaded_files]

                    # opening file dialog and closing without choosing a file results in None upload
                    process_uploaded_files(uploaded_files)
                    st.success("Successfully added uploaded files!")
                else:
                    st.warning("Upload some files before adding them.")

# File Upload Table
experiments = (
    set(wf.file_manager.get_results_list(['quant_tsv']))
    | set(wf.file_manager.get_results_list(['trace_tsv']))
    | set(wf.file_manager.get_results_list(['conflict_tsv']))
)
table = {
    'Experiment Name' : [],
    'Quant Result Files' : [],
    'Mass Trace Files' : [],
    '(Conflict resolution Files)' : [],
}
for experiment in experiments:
    table['Experiment Name'].append(experiment)

    if wf.file_manager.result_exists(experiment, 'quant_tsv'):
        table['Quant Result Files'].append(True)
    else:
        table['Quant Result Files'].append(False)

    if wf.file_manager.result_exists(experiment, 'trace_tsv'):
        table['Mass Trace Files'].append(True)
    else:
        table['Mass Trace Files'].append(False)

    if wf.file_manager.result_exists(experiment, 'conflict_tsv'):
        table['(Conflict resolution Files)'].append(True)
    else:
        table['(Conflict resolution Files)'].append(False)

st.markdown('**Uploaded experiments in current workspace**')
st.dataframe(pd.DataFrame(table))

# Remove files
with st.expander("Remove datasets"):
    to_remove = st.multiselect(
        "select files", options=experiments
    )
    c1, c2 = st.columns(2)
    if c2.button(
            "Remove **selected**", type="primary", disabled=not any(to_remove)
    ):
        for dataset_id in to_remove:
            wf.file_manager.remove_results(dataset_id)
        st.rerun()

    # Unbounded and unrecoverable: clear_cache() drops both SQLite tables and
    # rmtree's <cache>/files. It had no confirmation at all.
    if c1.button("Remove **all**", icon=":material/delete_forever:"):
        st.session_state["armed_clear_FLASHQuant"] = True
    if st.session_state.get("armed_clear_FLASHQuant"):
        def _clear_FLASHQuant():
            wf.file_manager.clear_cache()
            st.session_state.pop("armed_clear_FLASHQuant", None)
            st.rerun()
        confirm.confirm_typed(
            title="Remove every FLASHQuant dataset",
            body="This deletes every dataset in this workspace for FLASHQuant, "
                 "including parsed results. It cannot be undone.",
            phrase="FLASHQuant",
            confirm_label="Remove all FLASHQuant datasets",
            on_confirm=_clear_FLASHQuant,
        )
