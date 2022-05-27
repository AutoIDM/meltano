"""Schedule management CLI."""

import json
import sys

import click
from click_default_group import DefaultGroup
from sqlalchemy.orm import Session

from meltano.core.db import project_engine
from meltano.core.job.stale_job_failer import StaleJobFailer
from meltano.core.schedule import Schedule
from meltano.core.schedule_service import ScheduleAlreadyExistsError, ScheduleService
from meltano.core.task_sets import TaskSets
from meltano.core.task_sets_service import TaskSetsService
from meltano.core.tracking import GoogleAnalyticsTracker
from meltano.core.utils import coerce_datetime

from . import cli
from .params import pass_project


@cli.group(cls=DefaultGroup, default="add", short_help="Manage pipeline schedules.")
@click.pass_context
@pass_project(migrate=True)
def schedule(project, ctx):
    """
    Manage pipeline schedules.

    \b\nRead more at https://docs.meltano.com/reference/command-line-interface#schedule
    """
    ctx.obj["project"] = project
    ctx.obj["schedule_service"] = ScheduleService(project)
    ctx.obj["task_sets_service"] = TaskSetsService(project)


def _add_elt(
    ctx,
    name: str,
    extractor: str,
    loader: str,
    transform: str,
    interval: str,
    start_date: str,
):
    """Add a new legacy elt schedule."""
    project = ctx.obj["project"]
    schedule_service: ScheduleService = ctx.obj["schedule_service"]

    _, session_maker = project_engine(project)
    session = session_maker()
    try:
        added_schedule = schedule_service.add_elt(
            session, name, extractor, loader, transform, interval, start_date
        )
        tracker = GoogleAnalyticsTracker(schedule_service.project)
        tracker.track_meltano_schedule("add", added_schedule)
        click.echo(
            f"Scheduled elt '{added_schedule.name}' at {added_schedule.interval}"
        )
    except ScheduleAlreadyExistsError:
        click.secho(f"Schedule '{name}' already exists.", fg="yellow")
    finally:
        session.close()


def _add_job(ctx, name: str, job: str, interval: str):
    """Add a new scheduled job."""
    project = ctx.obj["project"]
    schedule_service: ScheduleService = ctx.obj["schedule_service"]

    _, session_maker = project_engine(project)
    session = session_maker()
    try:
        added_schedule = schedule_service.add(name, job, interval)
        tracker = GoogleAnalyticsTracker(schedule_service.project)
        tracker.track_meltano_schedule("add", added_schedule)
        click.echo(
            f"Scheduled job '{added_schedule.name}' at {added_schedule.interval}"
        )
    except ScheduleAlreadyExistsError:
        click.secho(f"Schedule '{name}' already exists.", fg="yellow")
    finally:
        session.close()


@schedule.command(short_help="[default] Add a new schedule.")
@click.argument("name")
@click.option("--interval", "-i", required=True, help="Interval of the schedule.")
@click.option("--job", "-j", help="The name of the job to run.")
@click.option("--extractor", "-e", required=False, help="ELT Only")
@click.option("--loader", "-l", required=False, help="ELT Only")
@click.option(
    "--transform",
    "-t",
    type=click.Choice(["skip", "only", "run"]),
    default="skip",
    help="ELT Only",
)
@click.option("--start-date", type=click.DateTime(), default=None, help="ELT Only")
@click.pass_context
def add(ctx, name, job, extractor, loader, transform, interval, start_date):
    """
    Add a new schedule. Schedules can be used to run Meltano jobs or ELT tasks at a specific interval.

    Example usage:

    \b
    \t# Schedule a job name "my_job" to run everyday
    \tmeltano schedule add <schedule_name> --job my_job --interval "@daily"
    \t# Schedule an ELT task to run hourly
    \tmeltano schedule add <schedule_name> --extractor <tap> --loader <target> --transform run --interval "@hourly"

    \b\nNote that the --job option and --extractor/--loader options are mutually exclusive.

    \b\nRead more at https://docs.meltano.com/reference/command-line-interface#schedule
    """
    if job and (extractor or loader):
        raise click.ClickException("Cannot specify both --job and --extractor/--loader")

    if not job:
        if not extractor:
            raise click.ClickException("Missing --extractor")
        if not loader:
            raise click.ClickException("Missing --loader")

        _add_elt(ctx, name, extractor, loader, transform, interval, start_date)
        return
    _add_job(ctx, name, job, interval)


def _format_job_list_output(entry: Schedule, job: TaskSets) -> dict:
    return {
        "name": entry.name,
        "interval": entry.interval,
        "cron_interval": entry.cron_interval,
        "env": entry.env,
        "job": {
            "name": job.name,
            "tasks": job.tasks,
        },
    }


def _format_elt_list_output(entry: Schedule, session: Session) -> dict:
    start_date = coerce_datetime(entry.start_date)
    if start_date:
        start_date = start_date.date().isoformat()

    last_successful_run = entry.last_successful_run(session)
    last_successful_run_ended_at = (
        last_successful_run.ended_at.isoformat() if last_successful_run else None
    )

    return {
        "name": entry.name,
        "extractor": entry.extractor,
        "loader": entry.loader,
        "transform": entry.transform,
        "interval": entry.interval,
        "start_date": start_date,
        "env": entry.env,
        "cron_interval": entry.cron_interval,
        "last_successful_run_ended_at": last_successful_run_ended_at,
        "elt_args": entry.elt_args,
    }


@schedule.command(short_help="List available schedules.")  # noqa: WPS441
@click.option("--format", type=click.Choice(["json", "text"]), default="text")
@click.pass_context
def list(ctx, format):  # noqa: WPS125
    """List available schedules."""
    project = ctx.obj["project"]
    schedule_service: ScheduleService = ctx.obj["schedule_service"]
    task_sets_service: TaskSetsService = ctx.obj["task_sets_service"]

    _, sessionMaker = project_engine(project)  # noqa: N806
    session = sessionMaker()
    try:
        StaleJobFailer().fail_stale_jobs(session)

        if format == "text":
            transform_elt_markers = {
                "run": ("→", "→"),
                "only": ("×", "→"),
                "skip": ("→", "x"),
            }

            for txt_schedule in schedule_service.schedules():
                if txt_schedule.job:
                    click.echo(
                        f"[{txt_schedule.interval}] job {txt_schedule.name}: {txt_schedule.job} → {task_sets_service.get(txt_schedule.job).tasks}"
                    )
                else:
                    markers = transform_elt_markers[txt_schedule.transform]
                    click.echo(
                        f"[{txt_schedule.interval}] elt {txt_schedule.name}: {txt_schedule.extractor} {markers[0]} {txt_schedule.loader} {markers[1]} transforms"
                    )

        elif format == "json":
            job_schedules = []
            elt_schedules = []
            for json_schedule in schedule_service.schedules():
                if json_schedule.job:
                    job_schedules.append(
                        _format_job_list_output(
                            json_schedule, task_sets_service.get(json_schedule.job)
                        )
                    )
                else:
                    elt_schedules.append(
                        _format_elt_list_output(json_schedule, session)
                    )
            click.echo(
                json.dumps(
                    {"schedules": {"job": job_schedules, "elt": elt_schedules}},
                    indent=2,
                )
            )
    finally:
        session.close()

    tracker = GoogleAnalyticsTracker(schedule_service.project)
    tracker.track_meltano_schedule("list")


@schedule.command(
    context_settings={"ignore_unknown_options": True, "allow_interspersed_args": False},
    short_help="Run a schedule.",
)
@click.argument("name")
@click.argument("elt_options", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def run(ctx, name, elt_options):
    """Run a schedule."""
    schedule_service = ctx.obj["schedule_service"]

    this_schedule = schedule_service.find_schedule(name)
    process = schedule_service.run(this_schedule, *elt_options)

    tracker = GoogleAnalyticsTracker(schedule_service.project)
    tracker.track_meltano_schedule("run", this_schedule)

    exitcode = process.returncode
    if exitcode:
        sys.exit(exitcode)


@schedule.command(name="remove", short_help="Remove a schedule.")
@click.argument("name", required=True)
@click.pass_context
def remove(ctx, name):
    """Remove a schedule.

    Usage:
        meltano schedule remove <name>
    """
    schedule_service: ScheduleService = ctx.obj["schedule_service"]
    removed_schedule = schedule_service.find_schedule(name)
    schedule_service.remove(name)
    tracker = GoogleAnalyticsTracker(schedule_service.project)
    tracker.track_meltano_schedule("remove", removed_schedule)
