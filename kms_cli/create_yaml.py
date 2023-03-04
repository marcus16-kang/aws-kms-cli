import os
import yaml

import boto3


class CreateYAML:
    template = {}
    parameters = {}
    resources = {}
    outputs = {}

    policy = {}

    primary_template = {}
    replica_template = {}

    def __init__(
            self,
            alias: str,
            admin: [],
            deletion: bool,
            usage: [],
            other_accounts: [],
            other_regions: []
    ):
        self.policy = self._create_key_policy(admin=admin, deletion=deletion, usage=usage,
                                              other_accounts=other_accounts)
        self.create_parameters(alias=alias)
        self.create_primary_key(other_regions=other_regions)
        self.create_outputs()
        self.create_primary_yaml()
        if other_regions:
            self.create_replica_yaml()

    def create_parameters(self, alias):
        self.parameters['AliasName'] = {
            'Type': 'String',
            'Description': '(REQUIRED) Alias(name) of kms key.',
            'Default': f'alias/{alias}'
        }
        self.parameters['EnableKeyRotation'] = {
            'Type': 'String',
            'Description': '(optional) Enable of disable key rotation.',
            'AllowedValues': [
                'true',
                'false'
            ],
            'Default': 'true'
        }
        self.parameters['PendingWindowInDays'] = {
            'Type': 'Number',
            'Description': '(optional) Pending window in days of kms key.',
            'Default': 7
        }

    def create_primary_key(self, other_regions):
        self.resources['Key'] = {
            'Type': 'AWS::KMS::Key',
            'Properties': {
                'Description': {
                    'Ref': 'AliasName'
                },
                'Enabled': True,
                'EnableKeyRotation': {
                    'Ref': 'EnableKeyRotation'
                },
                'KeyPolicy': self.policy,
                'KeySpec': 'SYMMETRIC_DEFAULT',
                'KeyUsage': 'ENCRYPT_DECRYPT',
                'MultiRegion': True if other_regions else False,
                'PendingWindowInDays': {
                    'Ref': 'PendingWindowInDays'
                },
                'Tags': [{
                    'Key': 'Name',
                    'Value': {
                        'Ref': 'AliasName'
                    }
                }]
            }
        }
        self.resources['Alias'] = {
            'Type': 'AWS::KMS::Alias',
            'Properties': {
                'AliasName': {
                    'Ref': 'AliasName'
                },
                'TargetKeyId': {
                    'Ref': 'Key'
                }
            }
        }

    def _create_key_policy(self, admin, deletion, usage, other_accounts):
        root_account_id = boto3.client('sts').get_caller_identity()['Account']

        policy = {
            'Version': '2012-10-17',
            'Statement': [{
                'Sid': 'Enable IAM User Permissions',
                'Effect': 'Allow',
                'Principal': {
                    'AWS': f'arn:aws:iam::{root_account_id}:root'
                },
                'Action': 'kms:*',
                'Resource': '*'
            }]
        }

        if admin:
            actions = [
                'ms:Create*',
                'kms:Describe*',
                'kms:Enable*',
                'kms:List*',
                'kms:Put*',
                'kms:Update*',
                'kms:Revoke*',
                'kms:Disable*',
                'kms:Get*',
                'kms:TagResource',
                'kms:UntagResource',
            ]
            if deletion:
                actions += ['kms:Get*', 'kms:ScheduleKeyDeletion', 'kms:CancelKeyDeletion']

            statement = {
                'Sid': 'Allow access for Key Administrators',
                'Effect': 'Allow',
                'Principal': {
                    'AWS': admin
                },
                'Action': actions,
                'Resource': '*'
            }

            policy['Statement'].append(statement)

        if len(usage) > 0 or other_accounts[0] != '':
            statement = {
                'Sid': 'Allow use of the key',
                'Effect': 'Allow',
                'Principal': {
                    'AWS': []
                },
                'Action': [
                    'kms:ListGrants',
                    'kms:RevokeGrant'
                ],
                'Resource': '*'
            }

            if usage:
                statement['Principal']['AWS'] += usage

            if other_accounts[0]:
                statement['Principal']['AWS'] += [f'arn:aws:iam::{account}:root' for account in other_accounts]
                statement['Action'].append('kms:CreateGrant')
                statement['Condition'] = {
                    'Bool': {
                        'kms:GrantIsForAWSResource': 'true'
                    }
                }

            policy['Statement'].append(statement)

        return policy

    def create_outputs(self):
        self.outputs = {
            'KmsKeyArn': {
                'Value': {
                    'Fn::GetAtt': 'Key.Arn'
                }
            }
        }

    def _get_base_template(self):
        return {
            'AWSTemplateFormatVersion': '2010-09-09',
            'Description': 'KMS Generator CLI',
            'Parameters': self.parameters,
            'Resources': self.resources,
            'Outputs': self.outputs
        }

    def create_primary_yaml(self):
        template = self._get_base_template()

        try:
            with open('kms-primary.yaml', 'w') as f:
                yaml.dump(template, f)

            self.primary_template = template

        except Exception as e:
            print(e)

    def create_replica_yaml(self, primary_key_arn: str = ''):
        template = self._get_base_template()
        template['Parameters']['PrimaryKeyArn'] = {
            'Description': '(REQUIRED) Arn of primary key arn',
            'Type': 'String',
            'Default': primary_key_arn
        }
        template['Resources']['Key']['Type'] = 'AWS::KMS::ReplicaKey'
        del template['Resources']['Key']['Properties']['EnableKeyRotation']
        del template['Resources']['Key']['Properties']['KeySpec']
        del template['Resources']['Key']['Properties']['KeyUsage']
        del template['Resources']['Key']['Properties']['MultiRegion']
        template['Resources']['Key']['Properties']['PrimaryKeyArn'] = {
            'Ref': 'PrimaryKeyArn'
        }

        try:
            with open('kms-replica.yaml', 'w') as f:
                yaml.dump(template, f)

            self.replica_template = template

        except Exception as e:
            print(e)
