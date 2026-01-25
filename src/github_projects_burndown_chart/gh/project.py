from datetime import datetime, date, timedelta
from dateutil.parser import isoparse

from config import config


def get_current_iteration(iteration_field):
    """Find the current iteration based on today's date.

    Returns a tuple of (iteration_id, start_date, end_date) or (None, None, None) if not found.
    """
    if not iteration_field:
        return None, None, None

    configuration = iteration_field.get('configuration', {})
    iterations = configuration.get('iterations', [])
    today = date.today()

    for iteration in iterations:
        start_date = datetime.strptime(iteration['startDate'], '%Y-%m-%d').date()
        end_date = start_date + timedelta(days=iteration['duration'])
        if start_date <= today <= end_date:
            return iteration['id'], start_date, end_date

    return None, None, None


class Project:
    columns = None

    @property
    def total_points(self):
        return sum([column.get_total_points() for column in self.columns])

    @property
    def cards(self):
        return [card for column in self.columns for card in column.cards]


class ProjectV1(Project):
    def __init__(self, project_data):
        self.name = project_data['name']
        self.columns = self.__parse_columns(project_data)

    def __parse_columns(self, project_data):
        columns_data = project_data['columns']['nodes']
        columns = [Column(self.__parse_cards(column_data)) for column_data in columns_data]
        return columns

    def __parse_cards(self, column_data):
        cards_data = column_data['cards']['nodes']
        cards = [Card(card_data) for card_data in cards_data]
        return cards


class ProjectV2(Project):
    def __init__(self, project_data):
        self.name = project_data['title']
        self.sprint_start_date: date = None
        self.sprint_end_date: date = None
        self.columns = self.__parse_columns(project_data)

    def __parse_columns(self, project_data):
        column_dict = {None: []}
        for option in project_data['field']['options']:
            column_dict[option['name']] = []

        # Get current iteration info for filtering and date tracking
        iteration_field = project_data.get('iterationField')
        current_iteration_id, start_date, end_date = get_current_iteration(iteration_field)

        # Store the iteration dates for use in chart generation
        self.sprint_start_date = start_date
        self.sprint_end_date = end_date

        for item_data in project_data['items']['nodes']:
            # Filter by current iteration if iteration field exists
            if current_iteration_id is not None:
                item_iteration_id = (item_data.get('iterationValue') or {}).get('iterationId')
                if item_iteration_id != current_iteration_id:
                    continue

            status = (item_data.get('fieldValueByName') or {}).get('name')
            column_dict[status].append(Card(item_data))

        columns = [Column(column_data) for column_data in column_dict.values()]
        return columns


class Column:
    def __init__(self, cards):
        self.cards = cards

    def get_total_points(self):
        return sum([card.points for card in self.cards])


class Card:
    def __init__(self, card_data):
        # Extract estimate from item level (for ProjectV2) before getting content
        estimate_value = (card_data.get('estimateValue') or {}).get('number')

        # Get content (Issue/PR data) for dates and labels
        content = card_data.get('content')
        if content:
            card_data = content

        self.created: datetime = self.__parse_createdAt(card_data)
        self.assigned: datetime = self.__parse_assignedAt(card_data)
        self.closed: datetime = self.__parse_closedAt(card_data)
        self.points = self.__parse_points(card_data, estimate_value)

    def __parse_assignedAt(self, card_data) -> datetime:
        assignedAt = None
        assignedDates = card_data.get('timelineItems', {}).get('nodes', [])
        if assignedDates:
            assignedAt = isoparse(assignedDates[0]['createdAt'])
        return assignedAt

    def __parse_createdAt(self, card_data) -> datetime:
        createdAt = None
        if card_data.get('createdAt'):
            createdAt = isoparse(card_data['createdAt'])
        return createdAt

    def __parse_closedAt(self, card_data) -> datetime:
        closedAt = None
        if card_data.get('closedAt'):
            closedAt = isoparse(card_data['closedAt'])
        return closedAt

    def __parse_points(self, card_data, estimate_value=None) -> int:
        card_points = 0
        points_label = config['settings']['points_label']

        # If no points_label configured, count issues (1 point each)
        if not points_label:
            card_points = 1
        # If estimate field value exists (from ProjectV2 number field), use it
        elif estimate_value is not None:
            card_points = int(estimate_value)
        # Otherwise try to parse from labels
        else:
            card_labels = card_data.get('labels', {"nodes": []})['nodes']
            card_points = sum([int(label['name'][len(points_label):])
                              for label in card_labels
                              if points_label in label['name']])
        return card_points
