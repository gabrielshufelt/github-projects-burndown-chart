import argparse

from chart.burndown import *
from config import config
from discord import webhook
from gh.api_wrapper import get_organization_project, get_repository_project, get_project_v2
from gh.project import Project, ProjectV2
from util import calculators, colors
from util.stats import *
from util.calculators import *
from util.dates import parse_to_utc


def parse_cli_args():
    parser = argparse.ArgumentParser(
        description='Generate a burndown chart for a GitHub project.')
    parser.add_argument("project_type", choices=['repository', 'organization'],
                        help="The type of project to generate a burndown chart for. Can be either 'organization' or 'repository'.")
    parser.add_argument("project_name",
                        help="The name of the project as it appears in the config.json")
    parser.add_argument("--filepath",
                        help="The filepath where the burndown chart is saved.")
    parser.add_argument("--discord", action='store_true',
                        help="If present, posts the burndown chart to the configured webhook")
    return parser.parse_args()


def download_project_data(project_type: str, project_version: int) -> Project:
    if project_version == 2:
        return get_project_v2(project_type)

    if project_type == 'repository':
        return get_repository_project()
    elif project_type == 'organization':
        return get_organization_project()


def get_sprint_dates(project: Project):
    """Get sprint start and end dates from the project's iteration."""
    if isinstance(project, ProjectV2) and project.sprint_start_date and project.sprint_end_date:
        sprint_start = parse_to_utc(project.sprint_start_date.strftime('%Y-%m-%d'))
        sprint_end = parse_to_utc(project.sprint_end_date.strftime('%Y-%m-%d'))
        return sprint_start, sprint_end
    else:
        raise ValueError("No active iteration found. Ensure your GitHub Project has an Iteration field with a current sprint.")


def get_chart_title(project: Project) -> str:
    """Generate the chart title including sprint name if available."""
    title = project.name
    if isinstance(project, ProjectV2) and project.sprint_name:
        title = f"{project.name}, {project.sprint_name}"
    return title


def prepare_chart_data(stats: ProjectStats, sprint_start, sprint_end):
    color = colors()
    chart_end = config.utc_chart_end() or sprint_end
    data = BurndownChartData(
        sprint_name=get_chart_title(stats.project),
        utc_chart_start=sprint_start,
        utc_chart_end=chart_end,
        utc_sprint_start=sprint_start,
        utc_sprint_end=sprint_end,
        total_points=stats.total_points,
        series=[
            BurndownChartDataSeries(
                name=pts_type,
                data=stats.remaining_points_by_date(
                    calculators(stats.project)[pts_type]),
                format=dict(color=next(color))
            ) for pts_type in config['settings'].get('calculators', ['closed'])
        ],
        points_label=f"Outstanding {'Points' if config['settings']['points_label'] else 'Issues'}"
    )
    return data


if __name__ == '__main__':
    args = parse_cli_args()
    config.set_project(args.project_type, args.project_name)
    project = download_project_data(args.project_type, config['settings'].get('version', 1))
    sprint_start, sprint_end = get_sprint_dates(project)
    chart_end = config.utc_chart_end() or sprint_end
    stats = ProjectStats(project, sprint_start, chart_end)
    # Generate the burndown chart
    burndown_chart = BurndownChart(prepare_chart_data(stats, sprint_start, sprint_end))
    if args.discord:
        chart_path = "./tmp/chart.png"
        burndown_chart.generate_chart(chart_path)
        webhook.post_burndown_chart(chart_path)
    elif args.filepath:
        burndown_chart.generate_chart(args.filepath)
    else:
        burndown_chart.render()
    print('Done')
