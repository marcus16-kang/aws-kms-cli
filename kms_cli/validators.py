import re
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from botocore import session


def name_validator(text):
    return len(text) > 0


def stack_name_validator(text, region):
    if not len(text):
        return False

    else:
        try:
            boto3.client('cloudformation', config=Config(region_name=region)).describe_stacks(StackName=text)

        except ClientError:  # stack doest
            return True

        except Exception as e:
            print(e)

            return False
