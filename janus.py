#!/usr/bin/python3
import requests
import boto3
import json
import sys
import subprocess
import socket

# this script originated from https://github.com/doitintl/janus
# and a blog post https://www.doit.com/assume-an-aws-role-from-a-google-cloud-without-using-iam-keys/
# modified in order to be able to authenticated using local service account when metadata.google.internal is not available


def get_metadata(path: str, parameter: str):
    # Use .format() instead of f-type to support python version before 3.7
    metadata_url = 'http://metadata.google.internal/computeMetadata/v1/{}/{}'.format(
        path, parameter)
    headers = {'Metadata-Flavor': 'Google'}
    # execute http metadata request
    try:
        meta_request = requests.get(metadata_url, headers=headers)
    except requests.exceptions.RequestException as e:
        raise SystemExit(e)

    if meta_request.ok:
        return meta_request.text
    else:
        raise SystemExit('Compute Engine meta data error')


def get_account_details_local():
    a_command = '/usr/bin/gcloud config list --format json'
    config_out_json = subprocess.run(
        a_command, stdout=subprocess.PIPE, shell=True)
    config_out = json.loads(config_out_json.stdout.decode('utf-8'))

    return config_out


def get_token_local(service_account):
    # create token for impersonated service account
    token_command = f'gcloud auth print-identity-token --impersonate-service-account="{service_account}" --audiences="gcp"'
    # we need to redirect stderr because it produces warning about impersonation
    token_result = subprocess.run(
        token_command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        shell=True)
    token = token_result.stdout.decode('utf-8')

    return token


if __name__ == '__main__':
    # Get aws arn from command line argument
    try:
        aws_role_arn = sys.argv[1]
    except IndexError:
        print(
            'Please specify AWS arn role:\n{} arn:aws:iam::account-id:role/role-name [local]'.format(sys.argv[0]))
        exit(0)

    # Get variables from the metadata server
    if len(sys.argv) == 2:
        instance_name = get_metadata('instance', 'hostname')
        project_id = get_metadata('project', 'project-id')
        project_and_instance_name = '{}.{}'.format(
            project_id, instance_name)[:64]
        token = get_metadata(
            'instance', 'service-accounts/default/identity?format=standard&audience=gcp')
    elif sys.argv[2] == 'local':
        account_details = get_account_details_local()
        service_account = account_details["core"]["account"]
        project_id = account_details["core"]["project"]
        hostname = socket.gethostname()
        token = get_token_local(service_account)
        project_and_instance_name = f'{project_id}-local-{hostname}'

    # Assume role using gcp service account token
    sts = boto3.client('sts', aws_access_key_id='', aws_secret_access_key='')

    res = sts.assume_role_with_web_identity(
        RoleArn=aws_role_arn,
        WebIdentityToken=token,
        RoleSessionName=project_and_instance_name)

    aws_temporary_credentials = {
        'Version': 1,
        'AccessKeyId': res['Credentials']['AccessKeyId'],
        'SecretAccessKey': res['Credentials']['SecretAccessKey'],
        'SessionToken': res['Credentials']['SessionToken'],
        'Expiration': res['Credentials']['Expiration'].isoformat()
    }

    print(json.dumps(aws_temporary_credentials))
