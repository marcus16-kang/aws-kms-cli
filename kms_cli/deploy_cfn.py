import os
import sys
import yaml
import json
import time
import multiprocessing
import boto3
from botocore.config import Config
from inquirer import prompt, Confirm, Text
from datetime import datetime
from dateutil import tz
from prettytable import PrettyTable

from kms_cli.validators import stack_name_validator


class DeployCfn:
    client = None
    deploy = False
    name = ''
    region = ''
    other_regions = []
    kms_key_arns = []

    def __init__(
            self,
            region,
            other_regions
    ):
        self.region = region
        self.other_regions = other_regions
        self.ask_deployment()
        self.input_stack_name()
        self.deployment(self.name, region, other_regions)

    def ask_deployment(self):
        questions = [
            Confirm(
                name='required',
                message='Do you want to deploy using CloudFormation in here?',
                default=True
            )
        ]

        self.deploy = prompt(questions=questions, raise_keyboard_interrupt=True)['required']

    def input_stack_name(self):
        questions = [
            Text(
                name='name',
                message='Type CloudFormation Stack name',
                validate=lambda _, x: stack_name_validator(x, self.region),
            )
        ]

        self.name = prompt(questions=questions, raise_keyboard_interrupt=True)['name']

    def deployment(self, name, region, other_regions: []):
        if self.deploy:  # deploy using cloudformation
            self._deploy_primary()

            if other_regions:
                manager = multiprocessing.Manager()
                return_list = manager.list()
                jobs = []

                for i, other_region in enumerate(other_regions):
                    p = multiprocessing.Process(target=self._deploy_replica, args=(i, return_list, other_region))
                    jobs.append(p)
                    p.start()

                for proc in jobs:
                    proc.join()

                print(return_list)

        else:
            print('Done!\n\n')
            print('You can deploy Bastion EC2 using AWS CLI\n\n\n')
            print(
                'aws cloudformation deploy --stack-name {} --region {} --template-file ./kms-primary.yaml'.format(
                    name, region))
            for other_region in other_regions:
                print()
                print(
                    'aws cloudformation deploy --stack-name {} --region {} --template-file ./kms-replica.yaml'.format(
                        name, other_region))

    def get_template(self, primary: bool):
        with open(f'kms-{"primary" if primary else "replica"}.yaml', 'r') as f:
            content = f.read()

        return content

    def get_timestamp(self, timestamp: datetime):
        return timestamp.replace(tzinfo=tz.tzutc()).astimezone(tz.tzlocal()).strftime('%I:%M:%S %p')

    def get_color(self, status: str):
        if 'ROLLBACK' in status or 'FAILED' in status:
            return '91m'

        elif 'PROGRESS' in status:
            return '96m'

        elif 'COMPLETE' in status:
            return '92m'

    def print_table(self):
        table = PrettyTable()
        table.set_style(15)
        table.field_names = ['Logical ID', 'Physical ID', 'Type']
        table.vrules = 0
        table.hrules = 1
        table.align = 'l'
        rows = []

        response = self.client.describe_stack_resources(StackName=self.name)['StackResources']

        for resource in response:
            rows.append([resource['LogicalResourceId'], resource['PhysicalResourceId'], resource['ResourceType']])

        rows = sorted(rows, key=lambda x: (x[2], x[0]))
        table.add_rows(rows)
        print(table)

    def _deploy_primary(self):
        print()
        print(f'Start to deploy at primary region ({self.region})')
        self.client = boto3.client('cloudformation', config=Config(region_name=self.region))
        response = self.client.create_stack(
            StackName=self.name,
            TemplateBody=self.get_template(primary=True),
            TimeoutInMinutes=10,
            Tags=[{'Key': 'Name', 'Value': self.name}],
        )
        stack_id = response['StackId']
        event_count = 0

        while True:
            # 1. get stack status
            response = self.client.describe_stacks(
                StackName=self.name
            )
            stack_status = response['Stacks'][0]['StackStatus']

            if stack_status in ['CREATE_FAILED', 'ROLLBACK_FAILED',
                                'ROLLBACK_COMPLETE']:  # create failed
                print()
                print('\x1b[91m' + 'Failed! (Primary)' + '\x1b[0m')
                print()
                print('\x1b[91m' + 'Please check CloudFormation at here:' + '\x1b[0m')
                print()
                print(
                    '\x1b[91m' +
                    'https://{0}.console.aws.amazon.com/cloudformation/home?region={0}#/stacks/stackinfo?stackId={1}'.format(
                        self.region, stack_id) +
                    '\x1b[0m')
                sys.exit(1)

            elif stack_status == 'CREATE_COMPLETE':  # create complete successful
                print()
                # self.print_table()
                print('\x1b[92m' + 'Success! (Primary)' + '\x1b[0m')
                print()

                break

            else:
                events = self.client.describe_stack_events(StackName=self.name)['StackEvents']
                if len(events) > event_count:  # new events
                    for i in range(0, len(events) - event_count):
                        event = ' \x1b[35mPRIMARY[{}]\x1b[0m | {:>11} | \x1b[{}{:<27}\x1b[0m | {:<26} | {}'.format(
                            self.region,
                            self.get_timestamp(events[i]['Timestamp']),
                            self.get_color(events[i]['ResourceStatus']),
                            events[i]['ResourceStatus'],
                            events[i]['ResourceType'],
                            events[i].get('ResourceStatusReason', ''))
                        print(event)

                        event_count = len(events)

                time.sleep(1)

    def _deploy_replica(self, procnum, return_list, region):
        print(f'Start to deploy at replica region({region})')
        client = boto3.client('cloudformation', config=Config(region_name=region))
        response = self.client.create_stack(
            StackName=self.name,
            TemplateBody=self.get_template(primary=False),
            TimeoutInMinutes=10,
            Tags=[{'Key': 'Name', 'Value': self.name}],
        )
        stack_id = response['StackId']
        event_count = 0

        while True:
            # 1. get stack status
            response = client.describe_stacks(
                StackName=self.name
            )
            stack_status = response['Stacks'][0]['StackStatus']

            if stack_status in ['CREATE_FAILED', 'ROLLBACK_FAILED',
                                'ROLLBACK_COMPLETE']:  # create failed
                print()
                print('\x1b[91m' + f'Failed! (Replica at {region})' + '\x1b[0m')
                print()
                print('\x1b[91m' + 'Please check CloudFormation at here:' + '\x1b[0m')
                print()
                print(
                    '\x1b[91m' +
                    'https://{0}.console.aws.amazon.com/cloudformation/home?region={0}#/stacks/stackinfo?stackId={1}'.format(
                        region, stack_id) +
                    '\x1b[0m')
                break

            elif stack_status == 'CREATE_COMPLETE':  # create complete successful
                print()
                # self.print_table()
                print('\x1b[92m' + f'Success! (Replica at {region})' + '\x1b[0m')
                print()

                response = client.describe_stacks(
                    StackName=self.name
                )
                return_list.append((region, response['Stacks'][0]['Outputs'][0]['OutputValue']))

                break

            else:
                events = client.describe_stack_events(StackName=self.name)['StackEvents']
                if len(events) > event_count:  # new events
                    for i in range(0, len(events) - event_count):
                        event = ' \x1b[93mREPLICA[{}]\x1b[0m | {:>11} | \x1b[{}{:<27}\x1b[0m | {:<26} | {}'.format(
                            region,
                            self.get_timestamp(events[i]['Timestamp']),
                            self.get_color(events[i]['ResourceStatus']),
                            events[i]['ResourceStatus'],
                            events[i]['ResourceType'],
                            events[i].get('ResourceStatusReason', ''))
                        print(event)

                        event_count = len(events)

                time.sleep(1)
