import os
import os.path as osp
import subprocess

from pydantic import BaseModel

INTERNAL_REGULATION_SUMMARY_FILE_NAME = "internal_regulation_summary.txt"


class InternalRegulationSummary(BaseModel):
    file_name: str
    content: str


def create_internal_regulation_summary_file(
    base_dir: str, file_name: str
) -> InternalRegulationSummary:
    """
    Function to retrieve a list of file names within base_dir 
    and create a file containing the list of internal regulation files.
    """
    data_dir = os.path.join(base_dir, "data")
    if not os.path.exists(data_dir):
        raise ValueError(f"{data_dir} does not exist.")
    try:
        # For Unix/Linux and macOS
        result = subprocess.check_output(["tree", data_dir], text=True)
    except FileNotFoundError:
        # Error handling when the 'tree' command is not available
        raise RuntimeError(
            "The 'tree' command was not found. Please check if it is installed."
        )
    output_file_path = os.path.join(base_dir, file_name)
    with open(output_file_path, "w") as file:
        file.write(result)

    return InternalRegulationSummary(
        file_name=file_name,
        content=result,
    )


def retrieve_internal_regulation_summary(
    base_dir: str, skip_summary_file_creation: bool
) -> InternalRegulationSummary:
    summary_file_name = INTERNAL_REGULATION_SUMMARY_FILE_NAME
    if not skip_summary_file_creation:
        print("[[CREATE INTERNAL REGULATION SUMMARY FILE]]")
        internal_regulation_summary = create_internal_regulation_summary_file(
            base_dir, file_name=summary_file_name
        )
        print("[[SUMMARY FILE CREATION COMPLETED]]")
    else:
        with open(osp.join(base_dir, summary_file_name), "r") as f:
            internal_regulation_summary = InternalRegulationSummary(
                file_name=summary_file_name,
                content=f.read(),
            )
    return internal_regulation_summary
