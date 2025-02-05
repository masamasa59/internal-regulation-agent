import os
import os.path as osp
from datetime import datetime
from typing import Any, List

from langchain_community.document_loaders import Docx2txtLoader
from pydantic import BaseModel, Field

from internal_regulation_agent.create_internal_regulatiom_summary import (
    InternalRegulationSummary, retrieve_internal_regulation_summary)
from internal_regulation_agent.generate_plan import Task, parse_json_to_tasks
from internal_regulation_agent.llm import (AVAILABLE_LLMS, create_client,
                                           extract_json_between_markers,
                                           get_response_from_llm)

execution_prompt = """
Please update the following internal regulation text if necessary to fulfill the user's request, based on the reason for reviewing the regulation.
If no update is needed, provide a reason for why it is unnecessary, and leave the updated text and the original text empty.
Ensure that the modified sections are clearly identifiable in the output.

User Request: {query}


Reason for Reviewing This Regulation: {current_task_check_reason}
Internal Regulation Text:
{current_task_file_name}
{regulation_text}

Respond in the following format:

JSON:
```json
<JSON>
```
In <JSON>, provide the new idea in JSON format with the following fields:
{output_schema}

This JSON will be automatically parsed, so ensure the format is precise.
"""

replanning_prompt = """
Checking for additional tasks.
Based on the information below, if there are any additional internal regulation files that should be reviewed, output them in JSON format.  
If no additional files need to be reviewed, output an empty list `[]`.  
Do not add tasks that overlap with tasks already in progress or regulations that have already been updated.  

In the <THOUGHT> section, consider related content within the observed regulations, such as linked references, dependencies, or cross-references with other regulations.  
Ensure that nothing is overlooked, and consider the impact of changes to the regulations.

User Request: {query}

The internal regulations updated so far are as follows:
{updated_regulations}
The list of regulations scheduled for review is as follows:
{tasks}

Here is the complete list of internal regulations:
{internal_regulation_summary}
The regulation currently under review is as follows:
{current_regulation}

Respond in the following format:
THOUGHT:
<THOUGHT>

JSON:
```json
<JSON>
```
In <JSON>, provide the new idea in JSON format with the following fields:
{output_schema}

This JSON will be automatically parsed, so ensure the format is precise.
"""


class Regulation(BaseModel):
    file_name: str = Field(title="Internal regulation file name (no path required)")
    original_text: str = Field(title="Original regulation text")
    updated_text: str = Field(title="Updated regulation text")
    is_updated: bool = Field(title="Whether the regulation has been updated")
    hypothesis: str = Field(title="The reason for reviewing this regulation (Japanese)")
    reason: str = Field(
        title="Reason for whether the regulation was updated (Japanese)"
    )


def retrieve_internal_regulation(base_dir: str, file_name: str) -> str:
    """
    Retrieve internal regulation from the given file path.

    Args:
        base_dir: str
        file_name: str (docx, pdf, txt,...)
    """
    data_dir = os.path.join(base_dir, "data/")
    if not os.path.exists(data_dir):
        raise ValueError(f"{data_dir} doesn't exist.")

    if file_name.endswith(".docx"):
        loader = Docx2txtLoader(data_dir + file_name)
        content = loader.load()
    else:
        # TODO: Implement other file types
        raise NotImplementedError("Only docx files are supported at the moment.")
    return content


def execute_plan(
    query: str,
    tasks: List[Task],
    base_dir: str,
    client: Any,
    client_model: str,
    internal_regulation_summary: InternalRegulationSummary,
    time_out: int = 900,
) -> List[Regulation]:
    """
    Execute the plan to update internal regulations based on the user's request.
    The process is considered complete when all tasks are finished or the timeout is reached.
    Additional tasks may be generated through replanning after each task is completed.

    Args:
    tasks: List of task objects representing tasks to update.
    base_dir: Base directory where the internal regulation files are located.
    client: LLM client (e.g., OpenAI API client).
    client_model: The LLM model name to be used.
    internal_regulation_summary: An object containing a summary of all internal regulations.
    time_out: Timeout in seconds for the overall processing (default is 900 seconds).

    Returns:
        A list of updated Regulation objects.
    """
    updated_regulations = []
    completed_tasks = []
    failed_tasks = []
    start_time = datetime.now()

    while tasks:
        current_time = datetime.now()
        # TIMEOUT CHECK
        if (current_time - start_time).seconds > time_out:
            print(f"Timeout reached: {time_out} seconds.")
            print(f"Completed tasks: {completed_tasks}")
            print(f"Remaining tasks: {tasks}")
            return updated_regulations

        current_task = tasks.pop(0)
        print("=====================================================")
        print(f"[[Current Task]]: {current_task}")
        print(f"[[Remaining Tasks]]: {len(tasks)}")
        print(f"[[Completed Tasks]]: {len(completed_tasks)}")

        try:
            regulation_text = retrieve_internal_regulation(
                base_dir, current_task.file_name
            )
        except Exception as e:
            print(
                f"Error retrieving internal regulation for file '{current_task.file_name}': {e}"
            )
            failed_tasks.append(current_task)
            continue

        execution_system_message = execution_prompt.format(
            query=query,
            current_task_check_reason=current_task.check_reason,
            current_task_file_name=current_task.file_name,
            regulation_text=regulation_text,
            output_schema=Regulation.model_json_schema(),
        )

        # EXECUTION TASK
        user_message = "Please update the internal regulation."
        try:
            content, _ = get_response_from_llm(
                msg=user_message,
                system_message=execution_system_message,
                client=client,
                model=client_model,
            )
        except Exception as e:
            print(f"Error during LLM call for updating regulation: {e}")
            continue

        print(f"[[EXECUTION]]: {content}")

        json_output = extract_json_between_markers(content)
        if json_output is None:
            raise ValueError("Failed to extract JSON from the LLM output.")

        try:
            regulation = Regulation(**json_output)
            updated_regulations.append(regulation)
        except Exception as e:
            print(
                f"Error converting JSON to Regulation for file '{current_task.file_name}': {e}"
            )
            continue

        completed_tasks.append(current_task)

        # REPLANNING
        user_message = (
            "Please replan whether further internal regulation reviews are necessary."
        )
        replanning_system_message = replanning_prompt.format(
            updated_regulations=updated_regulations,
            tasks=tasks,
            query=query,
            internal_regulation_summary=internal_regulation_summary.content,
            current_regulation=current_task.file_name,
            output_schema=Task.model_json_schema(),
        )

        try:
            context, _ = get_response_from_llm(
                msg=user_message,
                system_message=replanning_system_message,
                client=client,
                model=client_model,
            )
            print(f"[[Additional Tasks]]: {context}")
        except Exception as e:
            print(f"Error during LLM call for replanning: {e}")
            continue
        new_tasks_json = extract_json_between_markers(context)
        assert new_tasks_json is not None, "Failed to extract JSON from LLM output"

        if isinstance(new_tasks_json, list) and len(new_tasks_json) > 0:
            new_tasks = parse_json_to_tasks(new_tasks_json)
            tasks.extend(new_tasks)
        else:
            print("No additional tasks to check.")
    return updated_regulations


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate Internal Regulation Agent plan"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-2024-11-20",
        choices=AVAILABLE_LLMS,
        help="Model to use for AI Scientist.",
    )
    parser.add_argument(
        "--experiment",
        type=str,
        default="internal_regulations",
        help="Experiment name to use for Internal Regulation Agent.",
    )
    parser.add_argument(
        "--query",
        type=str,
        default="コアタイムを8:30-16:30にする。変更すべき規程と変更後の文案をください。",  # English: "Change the core time to 8:30-16:30. Please provide the regulations to be changed and the revised text.",
        help="User query to update internal regulations.",
    )
    args = parser.parse_args()

    # Create client
    client, client_model = create_client(args.model)
    base_dir = osp.join("templates", args.experiment)

    internal_regulation_summary = retrieve_internal_regulation_summary(
        base_dir, skip_summary_file_creation=True
    )
    tasks = [
        Task(
            file_name="労使協定/フレックスタイム制に関する労使協定書_03.docx",  # English: "Labor and Management Agreement/Flextime Agreement_03.docx",
            check_reason="フレックスタイム制のコアタイムを変更する必要があるため、現在のコアタイムを確認します。",  # English: "The core time of the flextime system needs to be changed, so check the current core time.",
        ),
        Task(
            file_name="人事労務諸規程/22_在宅勤務規程.docx",  # English: "Personnel and Labor Regulations/22_Telecommuting Regulations.docx",
            check_reason="在宅勤務制度がフレックスタイム制と関連している可能性があるため、コアタイムに関する記載を確認します。",  # English: "Since the telecommuting system may be related to the flextime system, check the description of the core time.",
        ),
    ]
    updated_regulations = execute_plan(
        query=args.query,
        tasks=tasks,
        base_dir=base_dir,
        client=client,
        client_model=client_model,
        internal_regulation_summary=internal_regulation_summary,
        time_out=180,
    )

    print(f"Updated regulations:{updated_regulations}")
