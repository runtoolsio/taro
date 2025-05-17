from typing import List

import typer

app = typer.Typer(invoke_without_command=True)


@app.callback()
def approve(
        phase: str = typer.Option(..., "--phase", "-p", help="Phase ID"),
        instance_ids: List[str] = typer.Argument(..., help="One or more instance IDs"),
):
    typer.echo(f"Phase: {phase}")
    typer.echo(f"Instance IDs: {', '.join(instance_ids)}")

# def run(args):
#     run_match = argsutil.run_criteria(args, MatchingStrategy.FN_MATCH)
#     responses, _ = runcore.approve_pending_instances(run_match, None)
#     approved = [r.instance_metadata for r in responses if r.release_result == ApprovalResult.APPROVED]
#
#     if approved:
#         print('Approved:')
#         for a in approved:
#             print(a)
