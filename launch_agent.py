import argparse
import os.path as osp

from internal_regulation_agent.create_internal_regulatiom_summary import \
    retrieve_internal_regulation_summary
from internal_regulation_agent.execute_plan import execute_plan
from internal_regulation_agent.generate_plan import generate_init_plan
from internal_regulation_agent.generate_repot import generate_report
from internal_regulation_agent.llm import AVAILABLE_LLMS, create_client

NUM_REFLECTIONS = 3
TIME_OUT_SECONDS = 900


def parse_arguments():
    parser = argparse.ArgumentParser(description="Run Internal Regulation Agent")
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-2024-11-20",
        choices=AVAILABLE_LLMS,
        help="Model to use for  Internal Regulation Agent.",
    )
    parser.add_argument(
        "--query",
        type=str,
        default="コアタイムを8:30-16:30にする。変更すべき規程と変更後の文案をください。",
        help="User query to update internal regulations.",
    )
    parser.add_argument(
        "--experiment",
        type=str,
        default="internal_regulations",
        help="Experiment name to use for Internal Regulation Agent.",
    )
    parser.add_argument(
        "--skip_summary_file_creation",
        type=bool,
        default=False,
        help="Set to False when creating the internal_regulation_summary.txt file. If the file already exists, set it to True. Initially, it should be False.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()

    # Create client
    client, client_model = create_client(args.model)

    base_dir = osp.join("templates", args.experiment)
    results_dir = osp.join("results", args.experiment)

    internal_regulation_summary = retrieve_internal_regulation_summary(
        base_dir, skip_summary_file_creation=args.skip_summary_file_creation
    )

    print("[[INIT PLANNING START]]")
    tasks = generate_init_plan(
        query=args.query,
        client=client,
        model_name=client_model,
        internal_regulation_summary=internal_regulation_summary,
    )
    print(f"[[INIT PLANNING RESULT]]:{tasks}")
    print("[[INIT PLANNING END]]")

    print("[[EXECUTE PLAN START]]")
    updated_regulations = execute_plan(
        query=args.query,
        tasks=tasks,
        base_dir=base_dir,
        client=client,
        client_model=client_model,
        internal_regulation_summary=internal_regulation_summary,
        time_out=TIME_OUT_SECONDS,
    )
    print("[[EXECUTE PLAN END]]")

    try:
        print("[[REPORT START]]")
        success = generate_report(
            query=args.query,
            updated_regulations=updated_regulations,
            results_dir=results_dir,
            client=client,
            model_name=client_model,
        )
        print(f" Success: {success}")
        print("[[REPORT END]]")
    except Exception as e:
        print(f"Failed to output pdf: {str(e)}")
        import traceback

        print(traceback.format_exc())
    print("Task Completed.")
