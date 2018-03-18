import argparse
import json
from datetime import datetime, timezone, timedelta

import dateutil.parser
from TogglPy import TogglPy
from .settings import YAMLSettings


class TogglTools:

    def __init__(self):
        arg_parser = argparse.ArgumentParser()
        arg_parser.add_argument('command', help='Subcommand to run')

        arg_parser.add_argument('--source-workspace', '-s', help='Workspace ID to use as the source')
        arg_parser.add_argument('--dest-workspace', '-w', help='Workspace ID to use as the destination')
        arg_parser.add_argument('--start-date', '-d', help='Starting date for the query in YYYYMMDD format')

        self.args = arg_parser.parse_args()
        self.cfg = YAMLSettings()

        self.toggl = TogglPy.Toggl()
        self.toggl.setAPIKey(self.cfg.cfg('toggl', 'api-key'))

        getattr(self, self.args.command)()

    def copy(self):

        project_mappings = []
        try:
            project_mappings = json.load(open('project-mappings.json'))
        except IOError:
            print('Error opening project mappings file (project-mappings.json).')
            exit()
        except (json.decoder.JSONDecodeError, TypeError):
            print('Error decoding contents of project-mappings.json.')
            exit()

        if self.args.source_workspace is None or self.args.dest_workspace is None:
            self._list_clients()
        else:
            if self.args.start_date is None:
                print('Give a start date.')
            else:
                start_date = None
                try:
                    start_date = datetime.strptime(self.args.start_date, '%Y%m%d')
                except ValueError:
                    print('Date not in YYYYMMDD format.')
                    exit()

                source_workspace_id = int(self.args.source_workspace)
                dest_workspace_id = int(self.args.dest_workspace)
                relevant_mapping = list(filter(
                    lambda x: x['source_workspace'] == source_workspace_id
                              and x['dest_workspace'] == dest_workspace_id,
                    project_mappings))
                if len(relevant_mapping) > 1:
                    print('Multiple relevant project mappings for these workspaces.')
                    exit()
                if len(relevant_mapping) < 1:
                    print('No relevant project mappings for these workspaces.')
                    exit()

                self._copy(start_date, source_workspace_id, dest_workspace_id, relevant_mapping[0])

    def fix(self):

        if self.args.dest_workspace is None:
            self._list_clients()
        else:
            if self.args.start_date is None:
                print('Give a start date.')
            else:
                start_date = None
                try:
                    start_date = datetime.strptime(self.args.start_date, '%Y%m%d')
                except ValueError:
                    print('Date not in YYYYMMDD format.')
                    exit()
                self._fix(start_date, int(self.args.dest_workspace))

    def _list_clients(self):
        response = self.toggl.request('https://www.toggl.com/api/v8/clients')

        # print the client name and id for each client in the response
        # list of returned values can be found in the Toggl docs
        # (https://github.com/toggl/toggl_api_docs/blob/master/chapters/clients.md)
        table_format = '| {:<9} | {:<45} | {:<9} |'
        print(table_format.format('Workspace', 'Client name', 'Client id'))
        for client in response:
            print(table_format.format(client['wid'], client['name'], client['id']))

    def _add_entry(self, data):
        # data = {'time_entry': {'description': 'Meeting with possible clients',
        #                        'tags': ['billed'],
        #                        'duration': 1200,
        #                        'start': '2013-03-05T07:58:58.000Z',
        #                        'pid': 36063764,
        #                        'created_with': 'TogglPy'}}

        response = self.toggl.postRequest('https://www.toggl.com/api/v8/time_entries/start', parameters=data)

        print(response)

    def _get_ws_time_entries(self, start_date, workspace_id):
        start_date_str = start_date.astimezone().isoformat()
        end_date_str = datetime.now(timezone.utc).astimezone().isoformat()
        request_url = 'https://www.toggl.com/api/v8/time_entries'

        response = self.toggl.request(endpoint=request_url,
                                      parameters={'start_date': start_date_str, 'end_date': end_date_str})
        if isinstance(response, list):
            matching_results = filter(lambda x: x['wid'] == workspace_id, response)
            return matching_results
        else:
            print('Error, response was: ' + response)

    def _display_time_entries(self, entries):
        table_format = '| {:<3} | {:<11} | {:<25} | {:<8} | {:<75} |'
        print(table_format.format('#', 'id', 'Start', 'Duration', 'Description'))
        for idx, entry in entries:
            start_time = self._parse_response_date(entry['start']).strftime('%a %x %X')
            print(table_format.format(idx, entry['id'], start_time, entry['duration'], entry['description']))

    @staticmethod
    def _parse_response_date(date_string):
        return dateutil.parser.isoparse(date_string).astimezone()

    def _get_projects(self, workspace_id):
        return {}

    def _fix(self, start_date, dest_workspace_id):

        def _start_time_not_midnight(time_entry_dict):
            parsed_start = self._parse_response_date(time_entry_dict['start'])
            return 0 != (parsed_start - parsed_start.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()

        def _set_midnight_start(time_entry_dict):
            print(time_entry_dict)

            old_start = time_entry_dict['start']
            old_stop = time_entry_dict['stop']
            parsed_start = self._parse_response_date(old_start)
            new_start = parsed_start.replace(hour=0, minute=0, second=0, microsecond=0)
            duration_seconds = int(time_entry_dict['duration'])
            new_stop = new_start + timedelta(seconds=duration_seconds)

            time_entry_dict.update({'old_start': old_start,
                                    'old_stop': old_stop,
                                    'start': new_start.isoformat(),
                                    'stop': new_stop.isoformat(),
                                    'duronly': True,
                                    'dur_calc': (new_stop - new_start).total_seconds()})
            return time_entry_dict

        ws_time_entries = self._get_ws_time_entries(start_date, dest_workspace_id)

        bad_entries = list(filter(_start_time_not_midnight, ws_time_entries))

        print('Found the following entries to be changed:')
        self._display_time_entries(bad_entries)
        proceed = input('\nType y to proceed [y/N]: ')
        if proceed != 'y':
            print('Stopping.')
            return

        fixed_entries = list(map(_set_midnight_start, bad_entries))
        print('The following changes will be made:')
        table_format = '| {:<11} | {:<25} | {:<25} | {:<25} | {:<25} | {:<8} | {:<15} | {:<55} |'
        print(
            table_format.format('id', 'Start (before)', 'Start (after)', 'Stop (before)', 'Stop (after)', 'Duration',
                                'Duration (calc)', 'Description'))
        for entry in fixed_entries:
            print(table_format.format(entry['id'], entry['old_start'], entry['start'], entry['old_stop'], entry['stop'],
                                      entry['duration'], entry['dur_calc'], entry['description']))
        proceed = input('\nType y to send to Toggl [y/N]: ')
        if proceed != 'y':
            print('Canceled.')
            return

        for entry in fixed_entries:
            print(self.toggl.putTimeEntry(entry))

    def _copy(self, start_date, source_workspace_id, dest_workspace_id, mapping_def):

        # Get all the entries from the source, exit if there are more than 99
        source_time_entries = list(self._get_ws_time_entries(start_date, source_workspace_id))
        if len(source_time_entries) > 99:
            print('Too many time entries to get at once; choose a different start date.')
            exit()

        # Get all the available projects from both workspaces (for names)
        source_projects = self._get_projects(source_workspace_id)
        dest_projects = self._get_projects(dest_workspace_id)

        # Determine whether for all entries' projects there is a mapping
        mapping_lookup = {}
        for pair in mapping_def['mapped_projects']:
            source_project = pair['source_project']
            if source_project in mapping_lookup:
                print('Multiple destination projects for source project {}.'.format(source_project))
                exit()
            else:
                # Update pair with project names
                pair.update({
                    'source_project_name': source_projects[source_project]['name'],
                    'dest_project_name': dest_projects[pair['dest_project']]['name']
                })
                mapping_lookup[source_project] = pair

        def _set_destination_pid(time_entry_dict):
            source_pid = time_entry_dict['pid']
            source_id = time_entry_dict['id']
            if source_pid not in mapping_lookup:
                print('No mapped destination for time entry with project {} (id: {})'.format(
                    source_projects[source_pid], source_pid
                ))
            else:
                mapping = mapping_lookup[source_pid]
                time_entry_dict.update({
                    'wid': dest_workspace_id,
                    'source_id': source_id,
                    'source_pid': source_pid,
                    'pid': mapping['dest_project'],
                    'source_project_name': mapping['source_project_name'],
                    'dest_project_name': mapping['dest_project_name']
                })
                del time_entry_dict['id']

        updated_entries = list(map(_set_destination_pid, source_time_entries))

        # Check whether all the relevant destination projects exist
        mapped_dest_projects = set(map(lambda te: te['pid'], updated_entries))
        dest_project_ids = set(dest_projects.keys())
        missing_ids = mapped_dest_projects - dest_project_ids
        if len(missing_ids) > 0:
            print('Not all destination projects exist in workspace:')
            for mid in missing_ids:
                print(mid)
            exit()

        # Display the mappings to be applied (sorted by dest)
        '| {:50} --> {:50} |'.format('Source project', 'Destination project')
        '| {:50} --> {:50} |'.format('({})'.format(source_workspace_id), '({})'.format(dest_workspace_id))
        for dest in mapped_dest_projects:
            sources = set(map(
                lambda te: (te['source_project_name'], te['dest_project_name']),
                filter(
                    lambda te: te['pid'] == dest,
                    updated_entries)))
            for (source_name, dest_name) in sources:
                print('| {:50} --> {:50} |'.format(source_name, dest_name))

        # Aggregate total number of hours in source by project & in total, calculate expected total in dest and display.

        # Create all new time entries

        # Get and calculate total number of hours in destination by getting all new time entry ids, and display per project.

        # If all total hours correspond, mark all old time entries as copied (with dest id?)


if __name__ == '__main__':
    TogglTools()