from inquirer import prompt, List, Text, Checkbox, Confirm

from kms_cli.create_yaml import CreateYAML
from kms_cli.utils import print_figlet, GetUsersAndRoles
from kms_cli.validators import name_validator
from kms_cli.deploy_cfn import DeployCfn

regions = [
    ('us-east-1      (N. Virginia)', 'us-east-1'),
    ('us-east-2      (Ohio)', 'us-east-2'),
    ('us-west-1      (N. California)', 'us-west-1'),
    ('us-west-2      (Oregon)', 'us-west-2'),
    ('ap-south-1     (Mumbai)', 'ap-south-1'),
    ('ap-northeast-3 (Osaka)', 'ap-northeast-3'),
    ('ap-northeast-2 (Seoul)', 'ap-northeast-2'),
    ('ap-southeast-1 (Singapore)', 'ap-southeast-1'),
    ('ap-southeast-2 (Sydney)', 'ap-southeast-2'),
    ('ap-northeast-1 (Tokyo)', 'ap-northeast-1'),
    ('ca-central-1   (Canada Central)', 'ca-central-1'),
    ('eu-central-1   (Frankfurt)', 'eu-central-1'),
    ('eu-west-1      (Ireland)', 'eu-west-1'),
    ('eu-west-2      (London)', 'eu-west-2'),
    ('eu-west-3      (Paris)', 'eu-west-3'),
    ('eu-north-1     (Stockholm)', 'eu-north-1'),
    ('sa-east-1      (Sao Paulo)', 'sa-east-1')
]


class Command:
    region = None
    entities = []
    alias = ''
    admin = []
    deletion = False
    usage = []
    other_accounts = []
    other_regions = []

    def __init__(self):
        print_figlet()

        self.entities = GetUsersAndRoles().get_list()

        self.choose_region()

        self.get_alias()

        self.define_permissions()

        self.choose_replica_regions()

        # create template yaml file
        CreateYAML(
            alias=self.alias,
            admin=self.admin,
            deletion=self.deletion,
            usage=self.usage,
            other_accounts=self.other_accounts,
            other_regions=self.other_regions,
        )

        # deploy using cloudformation
        DeployCfn(region=self.region, other_regions=self.other_regions)

    def choose_region(self):
        questions = [
            List(
                name='region',
                message='Choose primary region',
                choices=regions
            )
        ]

        answer = prompt(questions=questions, raise_keyboard_interrupt=True)
        self.region = answer.get('region')

    def get_alias(self):
        questions = [
            Text(
                name='alias',
                message='Enter the key\'s alias',
                validate=lambda _, x: name_validator(x)
            )
        ]

        answer = prompt(questions=questions, raise_keyboard_interrupt=True)
        self.alias = answer.get('alias')

    def define_permissions(self):
        name_max_len = len(max([item['name'] for item in self.entities], key=len))
        path_max_len = len(max([item['path'] for item in self.entities], key=len))
        entities = []
        row_str_base = '{0:<' + str(name_max_len) + '} | {1:<' + str(path_max_len) + '} | {2}'

        for entity in self.entities:
            row = (
                row_str_base.format(entity['name'], entity['path'], entity['type']),
                entity['arn']
            )
            entities.append(row)

        questions = [
            Checkbox(
                name='administrative',
                message='Choose the key administrators',
                choices=entities,
            ),
            Confirm(
                name='deletion',
                message='Do you want to allow key administrators to delete this key?',
                default=False
            ),
            Checkbox(
                name='usage',
                message='Choose the key usages',
                choices=entities,
            ),
            Text(
                name='other',
                message='If you want to add permissions to other AWS accounts, type here using COMMA(,)',
            )
        ]

        answer = prompt(questions=questions, raise_keyboard_interrupt=True)
        self.admin = answer.get('administrative')
        self.deletion = answer.get('deletion')
        self.usage = answer.get('usage')
        self.other_accounts = answer.get('other').replace(' ', '').split(',')

    def choose_replica_regions(self):
        replica_regions = regions

        replica_regions.pop([item[1] for item in regions].index(self.region))

        questions = [
            Checkbox(
                name='other-regions',
                message='Choose the other regions if you want to create replica keys',
                choices=replica_regions,
            )
        ]

        answer = prompt(questions=questions, raise_keyboard_interrupt=True)
        self.other_regions = answer.get('other-regions')
