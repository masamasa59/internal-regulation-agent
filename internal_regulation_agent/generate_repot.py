import os.path as osp
from datetime import datetime
from typing import Any, List

from weasyprint import HTML

from internal_regulation_agent.execute_plan import Regulation
from internal_regulation_agent.llm import (
    AVAILABLE_LLMS,
    create_client,
    get_response_from_llm,
)

reporting_system_message = """
You are responsible for summarizing the results of the user's tasks.  
Structure the report using **HTML format** with paragraphs, separators, headings, and bullet points for clarity.
The readers are familiar with the regulations and will closely examine the wording of the updated regulations, so include both the original and updated versions of the text.
At the end, list all the files explored by the agent, including those that were reviewed but not updated, and provide a reason for why each was not updated.

# Constraints
- Please output the report in Japanese.
- 
- Highlight only the most important parts in red.
- Use a smaller font size for better readability.
- Since the report will be converted directly to PDF, omit unnecessary information (such as enclosing it in ```html``` tags).


User Request: {query}  
Execution Result: {result}  

"""

reflection_message = """
Does the report adhere to all the specified constraints correctly?  
Does it include a title?  
Have thoughtful design choices been made, such as adding background color to section names? (Too many colors should be avoided.)  
Is it easy to compare the full text of the regulations before and after the changes?  
Is it clear which regulations have been modified?  
Are the reasons for the changes clearly stated?  
For files that were not updated, are the reasons also explicitly provided?  
Is the content structured in an easy-to-read format using hierarchical organization or tables?  
Please review everything, including the design aspects, and regenerate the report in HTML format.  
"""


def generate_report(
    results_dir: str,
    client: Any,
    model_name: str,
    query: str,
    updated_regulations: List[Regulation],
) -> bool:

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        # GENERATE REPORT
        system_message = reporting_system_message.format(
            query=query,
            result=updated_regulations,
        )
        print(f"system_message >>>>> {system_message}")

        html_content, messages = get_response_from_llm(
            msg="Create a report summarizing the user's tasks using HTML format.",
            system_message=system_message,
            client=client,
            model=model_name,
        )

        # REFLECTION
        html_content, message_history = get_response_from_llm(
            msg=reflection_message,
            system_message=system_message,
            client=client,
            msg_history=messages,
            model=model_name,
        )
        # ENGLISH VER
        html_content_english, _ = get_response_from_llm(
            msg="Please also create an English translation version.",
            system_message=system_message,
            client=client,
            msg_history=message_history,
            model=model_name,
        )
    except Exception as e:
        print(f"Failed to generate report: {str(e)}")
    try:
        HTML(string=html_content).write_pdf(
            osp.join(results_dir, f"report_japanese_{timestamp}.pdf")
        )
        HTML(string=html_content_english).write_pdf(
            osp.join(results_dir, f"report_english_{timestamp}.pdf")
        )
    except Exception as e:
        print(f"Failed to generate pdf: {str(e)}")
        return False

    return True


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
    results_dir = osp.join("results", args.experiment)

    updated_regulations = [
        Regulation(
            file_name="労使協定/フレックスタイム制に関する労使協定書_03.docx",
            original_text="（コアタイム）\n\n第５条\u3000コアタイムとして労働しなければならない時間帯は、午前１１時から午後３時までとする。",
            updated_text="（コアタイム）\n\n第５条\u3000コアタイムとして労働しなければならない時間帯は、午前８時３０分から午後４時３０分までとする。",
            is_updated=True,
            hypothesis="コアタイムを8:30-16:30に変更するため、フレックスタイム制の労使協定書を改定する必要がある。",
            reason="コアタイムの時間帯を変更する必要があるため、該当箇所を改定しました。",
        ),
        Regulation(
            file_name="01_就業規則.docx",
            original_text="第２６条 フレックスタイム制\n第２３条の規定にかかわらず、社員の過半数を代表する者との間で労使協定を締結し、始業および終業の時刻を社員の自主的決定に委ねることとした場合、全部または一部の者についてフレックスタイム制により勤務させることがある。",
            updated_text="第２６条 フレックスタイム制\n第２３条の規定にかかわらず、社員の過半数を代表する者との間で労使協定を締結し、始業および終業の時刻を社員の自主的決定に委ねることとした場合、全部または一部の者についてフレックスタイム制により勤務させることがある。この場合、コアタイムは午前8時30分から午後4時30分までとする。",
            is_updated=True,
            hypothesis="就業規則には通常、労働時間やコアタイムに関する記載が含まれるため、フレックスタイム制の変更と整合性があるか確認する必要があります。",
            reason="ユーザーのリクエストに基づき、フレックスタイム制のコアタイムを明確にするために、項目を更新しました。これにより、社員にとって労働時間の基準が明確になります。",
        ),
        Regulation(
            file_name="時間外労働休日労働に関する労使協定届（三六協定）（2021年4月以降対応版）_01-02.docx",
            original_text="",
            updated_text="",
            is_updated=False,
            hypothesis="三六協定は時間外労働や休日労働の基準を定めているため、コアタイム変更が労働時間に関連する影響を与える可能性がある。",
            reason="提示された三六協定の文面には、労働時間のコアタイムについての記載がなく、変更の必要性が見受けられません。コアタイムに関する事項は別途の規程で定められている可能性が高いため、該当部分は特定できませんでした。",
        ),
        Regulation(
            file_name="16_パートタイム社員就業規則.docx",
            original_text="（勤務時間）\n\n第２３条\u3000パート社員の始業・終業の時刻および休憩時間は原則として次のとおりとし、個別の雇用契約において定めるものとする。\n\n始業時刻\n\n終業時刻\n\n休憩時間\n\n午前９時００分\n\n午後５時００分\n\n正午より１時間\n\n２．前項の定めにかかわらず、パート社員の始業・終業の時刻および休憩時間は、業務または季節の都合等により変更することがある。この場合、会社は予め本人と協議した上で変更するものとする。",
            updated_text="（勤務時間）\n\n第２３条\u3000パート社員の始業・終業の時刻および休憩時間は原則として次のとおりとし、個別の雇用契約において定めるものとする。\n\n始業時刻\n\n終業時刻\n\n休憩時間\n\n午前８時３０分\n\n午後４時３０分\n\n正午より１時間\n\n２．前項の定めにかかわらず、パート社員の始業・終業の時刻および休憩時間は、業務または季節の都合等により変更することがある。この場合、会社は予め本人と協議した上で変更するものとする。",
            is_updated=True,
            hypothesis="パートタイム社員の就業規則には、フレックスタイム制やコアタイムについての記載が含まれる可能性がある。コアタイム変更に合わせて整合性を確認する必要がある。",
            reason="コアタイムの変更を反映させるために、勤務時間の規定を変更する必要があるため。",
        ),
        Regulation(
            file_name="22_在宅勤務規程.docx",
            original_text="",
            updated_text="",
            is_updated=False,
            hypothesis="在宅勤務規程には、コアタイムに関する規定が含まれる可能性があるため、変更との整合性を確認する必要がある。",
            reason="提供された在宅勤務規程にはコアタイムに関する具体的な規定が記載されていません。そのため、コアタイムを8:30-16:30に変更する必要がある部分はありません。",
        ),
        Regulation(
            file_name="１年単位の変形労働時間制に関する労使協定書_04.docx",
            original_text="２．１日の所定労働時間は、７時間３０分とし、始業・終業の時刻、休憩時間は次のとおりとする。\n\n\u3000\u3000\u3000\u3000始業：\u3000９時００分\u3000\u3000\u3000\u3000\n\n終業：１７時３０分\n\n\u3000\u3000\u3000\u3000休憩：１２時００分\u3000～\u3000１３時００分",
            updated_text="２．１日の所定労働時間は、７時間３０分とし、始業・終業の時刻、休憩時間は次のとおりとする。\n\n\u3000\u3000\u3000\u3000始業：\u30008時30分\u3000\u3000\u3000\u3000\n\n終業：16時30分\n\n\u3000\u3000\u3000\u3000休憩：１２時００分\u3000～\u3000１３時００分",
            is_updated=True,
            hypothesis="変形労働時間制における労働時間の記載がコアタイム変更と整合性があるか確認する必要があります。",
            reason="コアタイムを8:30-16:30に変更するため、始業時刻と終業時刻をそれに沿う形に修正しました。",
        ),
        Regulation(
            file_name="事業場外みなし労働時間制に関する労使協定書_06.docx",
            original_text="",
            updated_text="",
            is_updated=False,
            hypothesis="事業場外みなし労働時間制における労働時間の基準が、コアタイム変更と矛盾しないか確認する必要があります。",
            reason="事業場外みなし労働時間制の内容では、労働時間を算定し難い場合に1日9時間労働とみなす規定があり、特定のコアタイム（例：8:30-16:30）が直接的に影響を受ける部分がありません。そのため、規定の変更は不要です。",
        ),
        Regulation(
            file_name="専門業務型裁量労働制に関する労使協定書（2024年4月以降版）_08.docx",
            original_text="",
            updated_text="",
            is_updated=False,
            hypothesis="専門業務型裁量労働制に関する協定書において、労働時間やコアタイムの基準が影響を受けないか確認する必要があります。",
            reason="現行の規程では、裁量労働制の従業員に対して業務遂行の手段および時間配分について具体的な指示を行わないと定められており、始業・終業時刻も従業員の裁量に委ねられています。そのため、コアタイムの設定はこの規程には該当せず、変更の必要はありません。",
        ),
        Regulation(
            file_name="１年単位の変形労働時間制に関する労使協定届_05.docx",
            original_text="",
            updated_text="",
            is_updated=False,
            hypothesis="変形労働時間制の届出にも労働時間の基準が記載されている可能性があり、コアタイム変更との整合性を確認する必要があります。",
            reason="提供された規程にはコアタイムに関する具体的な記載がありませんでした。そのため、変更の必要性がないと判断しました。",
        ),
        Regulation(
            file_name="03_育児・介護休業等に関する規程_202210-2.docx",
            original_text="",
            updated_text="",
            is_updated=False,
            hypothesis="育児・介護休業における労働時間の調整やコアタイム変更の影響がないか確認する必要があります。",
            reason="提供された規程文中にはコアタイムに関する記述が見当たらず、具体的な修正箇所が特定できませんでした。そのため、変更は不要と判断しました。",
        ),
        Regulation(
            file_name="一斉休憩の適用除外に関する労使協定書_11.docx",
            original_text="",
            updated_text="",
            is_updated=False,
            hypothesis="一斉休憩の適用除外に関連して、コアタイム変更が影響を与えないか確認する必要があります。",
            reason="現行の規程において、コアタイムについての具体的な記載がないため、コアタイム変更が直接影響を与える箇所がありません。そのため、変更は必要ありません。",
        ),
    ]

    status = generate_report(
        query=args.query,
        results_dir=results_dir,
        client=client,
        model_name=client_model,
        updated_regulations=updated_regulations,
    )
    assert status == True, "Failed to generate report"
