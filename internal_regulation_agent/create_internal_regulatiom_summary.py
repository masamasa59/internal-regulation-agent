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


def retrieve_internal_regulation_summary(
    base_dir: str, skip_summary_file_creation: bool
) -> InternalRegulationSummary:
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
    return internal_regulation_summary
