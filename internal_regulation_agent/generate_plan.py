import os
import os.path as osp
import subprocess
from typing import Any, List

from pydantic import BaseModel, Field

from internal_regulation_agent.llm import (AVAILABLE_LLMS, create_client,
                                           extract_json_between_markers,
                                           get_response_from_llm)

INTERNAL_REGULATION_SUMMARY_FILE_NAME = "internal_regulation_summary.txt"

planning_prompt = """
You are tasked with updating the internal regulations of your company.
You need to review the existing internal regulations and update old regulations based on the given query.
First, you need to select as many relevant internal regulation files as possible for review and specify the reason for reviewing them.

The internal regulations of the company are as follows:
{internal_regulation_summary}

Respond in the following format:

JSON:
```json
<JSON>
```
In <JSON>, provide the new idea in JSON format with the following fields:
{output_schema}

This JSON will be automatically parsed, so ensure the format is precise.
"""


class InternalRegulationSummary(BaseModel):
    file_name: str
    content: str


class Step(BaseModel):
    file_name: str = Field(title="社内規程ファイル名（パスは不要）")
    check_reason: str = Field(title="ファイルの中身を確認する理由")


def create_internal_regulation_summary_file(
    base_dir: str, file_name: str
) -> InternalRegulationSummary:
    """
    base_dir内のファイル名一覧を取得し、社内規程のファイル名一覧ファイルを作成する関数
    """
    data_dir = os.path.join(base_dir, "data")
    if not os.path.exists(data_dir):
        raise ValueError(f"{data_dir} が存在しません。")
    try:
        # Unix/Linux, macOSの場合
        result = subprocess.check_output(["tree", data_dir], text=True)
    except FileNotFoundError:
        # treeコマンドが無い場合のエラー処理
        raise RuntimeError(
            "tree コマンドが見つかりません。インストールされているか確認してください。"
        )
    # ファイルを保存
    output_file_path = os.path.join(base_dir, file_name)
    with open(output_file_path, "w") as file:
        file.write(result)

    return InternalRegulationSummary(
        file_name=file_name,
        content=result,
    )


def parse_json_to_steps(parsed_data: Any) -> List[Step]:
    """
    JSONをパースした結果のデータ（parsed_data）を Step のリストに変換する関数

    Parameters:
        parsed_data: LLMのJSON出力をパースした結果のPythonオブジェクト

    Returns:
        Stepオブジェクトのリスト

    Raises:
        ValueError: parsed_dataが想定外の形式(リストや辞書でない、要素が辞書でないなど)の場合
    """
    steps: List[Step] = []
    if isinstance(parsed_data, list):
        for item in parsed_data:
            if not isinstance(item, dict):
                raise ValueError("各ステップは辞書形式である必要があります。")
            step = Step(
                file_name=item.get("file_name", ""),
                check_reason=item.get("check_reason", ""),
            )
            steps.append(step)
    elif isinstance(parsed_data, dict):
        # もし単一のStepが返ってくる場合への対応
        step = Step(
            file_name=parsed_data.get("file_name", ""),
            check_reason=parsed_data.get("check_reason", ""),
        )
        steps.append(step)
    else:
        # JSONが想定外の形式の場合のエラーハンドリング
        raise ValueError(
            "予期しないJSONの形式です。リストまたは辞書形式を返してください。"
        )
    return steps


# GENERATE PLAN
def generate_init_plan(
    query: str,
    base_dir: str,
    client: Any,
    model_name: str,
    skip_summary_file_creation=False,
) -> List[Step]:
    # スキップがなければ、指定フォルダ配下のファイル名一覧のファイルを作成する
    # 社内規程のファイル名一覧ファイルを取得する
    # ユーザーのクエリに基づき関連のあるファイル名を生成する

    summary_file_name = INTERNAL_REGULATION_SUMMARY_FILE_NAME
    if not skip_summary_file_creation:
        # CREATE INTERNAL REGULATION SUMMARY FILE
        internal_regulation_summary = create_internal_regulation_summary_file(
            base_dir, file_name=summary_file_name
        )
    else:
        with open(osp.join(base_dir, summary_file_name), "r") as f:
            internal_regulation_summary = InternalRegulationSummary(
                file_name=summary_file_name,
                content=f.read(),
            )

    planning_system_message = planning_prompt.format(
        internal_regulation_summary=internal_regulation_summary.content,
        output_schema=Step.model_json_schema()
    )
    print(f"system_message >>>>> {planning_system_message}")

    # GENERATE PLAN
    content, _ = get_response_from_llm(
        msg=query,
        system_message=planning_system_message,
        client=client,
        model=model_name,
    )
    print(f"generated plan >>>>> {content}")

    # PARSE OUTPUT
    json_output = extract_json_between_markers(content)
    assert json_output is not None, "Failed to extract JSON from LLM output"

    # RESPONSE TO STEPS
    steps = parse_json_to_steps(json_output)
    return steps


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
    results_dir = osp.join("results", args.experiment)
    steps = generate_init_plan(
        query=args.query,
        base_dir=base_dir,
        client=client,
        model_name=client_model,
        skip_summary_file_creation=False,
    )
    assert isinstance(steps, list), "steps is not a list"
    assert all(isinstance(step, Step) for step in steps), "Not all elements in steps are instances of Step"