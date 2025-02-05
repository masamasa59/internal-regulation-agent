import os.path as osp
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from internal_regulation_agent.create_internal_regulatiom_summary import (
    InternalRegulationSummary, retrieve_internal_regulation_summary)
from internal_regulation_agent.llm import (AVAILABLE_LLMS, create_client,
                                           extract_json_between_markers,
                                           get_response_from_llm)

planning_prompt = """
You are tasked with updating the internal regulations of your company.
You need to review the existing internal regulations and update old regulations based on the given query.
First, you need to select as many relevant internal regulation files as possible for review and specify the reason for reviewing them.

Inside the <THOUGHT> tag, carefully analyze the user's query and compare it against the list of internal regulations.
Consider the general impact of modifying regulations and the potential secondary effects of such changes to avoid any oversight.

The internal regulations of the company are as follows:
{internal_regulation_summary}

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


class Task(BaseModel):
    file_name: str = Field(title="Internal regulation file name (excluding 'data/')")
    check_reason: str = Field(title="Reason for reviewing the file (Japanese)")


def parse_json_to_tasks(parsed_data: Dict) -> List[Task]:
    """
    Converts parsed JSON data (parsed_data) into a list of Task objects.

    Parameters:
        parsed_data: A Python object resulting from parsing JSON output from the LLM.

    Returns:
        A list of Task objects.

    Raises:
        ValueError: If parsed_data is in an unexpected format (not a list or dictionary, or if elements are not dictionaries).
    """
    tasks: List[Task] = []
    if isinstance(parsed_data, list):
        for item in parsed_data:
            if not isinstance(item, dict):
                raise ValueError("Each step must be in dictionary format.")
            task = Task(
                file_name=item.get("file_name", ""),
                check_reason=item.get("check_reason", ""),
            )
            tasks.append(task)
    elif isinstance(parsed_data, dict):
        task = Task(
            file_name=parsed_data.get("file_name", ""),
            check_reason=parsed_data.get("check_reason", ""),
        )
        tasks.append(task)
    else:
        ValueError(
            "Unexpected JSON format. Please return data in list or dictionary format."
        )
    return tasks


def generate_init_plan(
    query: str,
    client: Any,
    model_name: str,
    internal_regulation_summary: InternalRegulationSummary,
) -> List[Task]:
    """
    Generates an update plan for internal regulations.

    Parameters:
        query: The user's query.
        client: OpenAI API client.
        model_name: The name of the model to be used.
        internal_regulation_summary: Summary information of internal regulations.

    Returns:
        A list of Task objects.
    """

    planning_system_message = planning_prompt.format(
        internal_regulation_summary=internal_regulation_summary.content,
        output_schema=Task.model_json_schema(),
    )

    # GENERATE PLAN
    content, _ = get_response_from_llm(
        msg=query,
        system_message=planning_system_message,
        client=client,
        model=model_name,
    )
    print(f"generated plan:{content}")

    # PARSE OUTPUT
    json_output = extract_json_between_markers(content)
    assert json_output is not None, "Failed to extract JSON from LLM output"

    # RESPONSE TO TASKS
    tasks = parse_json_to_tasks(json_output)
    return tasks


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
        default="コアタイムを8:30-16:30にする。変更すべき規程と変更後の文案をください。",
        help="User query to update internal regulations.",
    )
    args = parser.parse_args()

    # Create client
    client, client_model = create_client(args.model)
    base_dir = osp.join("templates", args.experiment)

    internal_regulation_summary = retrieve_internal_regulation_summary(
        base_dir, skip_summary_file_creation=True
    )
    tasks = generate_init_plan(
        query=args.query,
        client=client,
        model_name=client_model,
        internal_regulation_summary=internal_regulation_summary,
    )
    assert isinstance(tasks, list), "tasks is not a list"
    assert all(
        isinstance(task, Task) for task in tasks
    ), "Not all elements in tasks are instances of Task"
