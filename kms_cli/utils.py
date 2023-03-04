import multiprocessing
import itertools
import boto3
from pyfiglet import Figlet
from halo import Halo


def print_figlet():
    figlet_title = Figlet(font='slant')

    print(figlet_title.renderText('KMS Generator'))


class GetUsersAndRoles:
    def _get_user(self, procnum, return_dict):
        users = boto3.client('iam').list_users()['Users']
        user_list = []
        for user in users:
            user_dict = {
                'name': user['UserName'],
                'arn': user['Arn'],
                'path': user['Path'],
                'type': 'User'
            }
            user_list.append(user_dict)

        return_dict[procnum] = user_list

    def _get_role(self, procnum, return_dict):
        roles = boto3.client('iam').list_roles()['Roles']
        role_list = []
        for user in roles:
            user_dict = {
                'name': user['RoleName'],
                'arn': user['Arn'],
                'path': user['Path'],
                'type': 'Role'
            }
            role_list.append(user_dict)

        return_dict[procnum] = role_list

    @Halo(text='Getting AWS Resources...')
    def get_list(self):
        manager = multiprocessing.Manager()
        return_dict = manager.dict()
        jobs = []

        p1 = multiprocessing.Process(target=self._get_user, args=(1, return_dict))
        jobs.append(p1)
        p1.start()

        p2 = multiprocessing.Process(target=self._get_role, args=(2, return_dict))
        jobs.append(p2)
        p2.start()

        for proc in jobs:
            proc.join()

        entities = itertools.chain.from_iterable(return_dict.values())

        return list(entities)
