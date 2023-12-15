#!/usr/bin/python3
import requests
import boto3
import json
import sys
import os


def get_metadata(path: str, parameter: str):
    # Use .format() instead of f-type to support python version before 3.7
    metadata_url = 'http://metadata.google.internal/computeMetadata/v1/{}/{}'.format(path, parameter)
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


if __name__ == '__main__':
    # Get AWS ARN from command line if specified
    if len(sys.argv) == 2:
        aws_role_arn = sys.argv[1]

    # Get AWS ARN from env var if specified
    elif 'AWS_JANUS_ROLE' in os.environ:
        aws_role_arn = os.environ['AWS_JANUS_ROLE']

    # Fail if both argv and env var configuration failed
    else:
        print('Please specify AWS arn role:\neither via env var `AWS_JANUS_ROLE` or \n CLI argument `{} arn:aws:iam::account-id:role/role-name`'.format(sys.argv[0]))
        exit(1)

    # Get variables from the metadata server
    try:
        instance_name = get_metadata('instance', 'hostname')
    # Cloud Run environment does not return instance name. use 'unknown' instead.
    except SystemExit:
        instance_name = 'unknown'
    project_id = get_metadata('project', 'project-id')
    project_and_instance_name = '{}.{}'.format(project_id, instance_name)[:64]
    token = get_metadata('instance', 'service-accounts/default/identity?format=standard&audience=gcp')

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
