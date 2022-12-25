from kfp import Client
from client import get_kubeflow_client
import argparse
import datetime
from yaml import safe_load
import json
import os

def deploy_pipeline(
    pipeline_yaml_path:str, 
    deploy_environment:str, 
    pipeline_version_name:str, 
    ):

    # get kfp client connection
    client_info = get_kubeflow_client(deploy_environment)
    kfp_client = client_info["kfp_client"]   
    kfp_client.set_user_namespace(client_info["kfp_namespace"])
    # experiment_name = client_info["kfp_experinment_name"]

    # check pipeline existence
    with open(pipeline_yaml_path, 'r') as yml:
        pipeline_yaml = safe_load(yml)
    pipeline_name = pipeline_yaml['spec']['entrypoint']
    pipeline_desc = pipeline_yaml['metadata']['annotations']
    pipeline_id = kfp_client.get_pipeline_id(pipeline_name)

    # upload package as a new pipeline if specified pipeline already exists
    if pipeline_id == None:
        pipeline_info = kfp_client.upload_pipeline(
            pipeline_package_path=pipeline_yaml_path,
            pipeline_name=pipeline_name,
            description=pipeline_desc
            )

        # print('new pipeline has been successfully uploaded')
        print(pipeline_info)

    pipeline_version_info = kfp_client.upload_pipeline_version(
        pipeline_package_path=pipeline_yaml_path,
        pipeline_name=pipeline_name,
        pipeline_version_name=pipeline_version_name,
        description=pipeline_desc
    )

    # print('pipeline version has been successfully uploaded')
    print(pipeline_version_info)

    return(pipeline_version_info)

def run_pipeline(
    deploy_environment:str,
    pipeline_version_id:str,
    params:str = None 
    ):

    # get kfp client connection
    client_info = get_kubeflow_client(deploy_environment)
    kfp_client = client_info["kfp_client"]   
    kfp_client.set_user_namespace(client_info["kfp_namespace"])
    experiment_name = client_info["kfp_experinment_name"]

    # get experiment id by name
    experiment_info = kfp_client.get_experiment(experiment_name=experiment_name, namespace=client_info["kfp_namespace"])

    # generate job name
    t_delta = datetime.timedelta(hours=9)
    JST = datetime.timezone(t_delta, 'JST')
    now = datetime.datetime.now(JST)
    # timestamp = now.strftime('%Y%m%d%H%M%S') # YYYYMMDDhhmmss
    job_name = "Run at " + str(now)

    # create run
    run_info = kfp_client.run_pipeline(
        experiment_id=experiment_info.id,
        version_id=pipeline_version_id,
        job_name=job_name,
        params=params
    )
    # print('successfully launched the pipeline run')
    print(run_info)

    return run_info

if __name__ == "__main__":
    # define command line arguments 
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--cloud-environment', help="specify 'on-prem' or 'cloud'", required=True)
    parser.add_argument('-f', '--pipeline-package-path', help="pipeline package path", required=True)
    parser.add_argument('-v', '--pipeline-version', help="pipeline version name", required=True)
    parser.add_argument('-d', '--deploy-only', action='store_true', help="specify if you don't want to run pipeline")
    args = parser.parse_args()

    # deploy pipeline
    pipeline_version_info = deploy_pipeline(
        deploy_environment=args.cloud_environment, 
        pipeline_yaml_path=args.pipeline_package_path,
        pipeline_version_name=args.pipeline_version
        )
    print(type(pipeline_version_info))

    # run pipeline
    if not args.deploy_only:
        # read params file
        pipeline_params_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
        pipeline_params_file = os.path.join(pipeline_params_dir, "pipeline_params.yaml")
        with open(pipeline_params_file, 'r') as yml:
            pipeline_params_content = safe_load(yml)

        run_info = run_pipeline(
            deploy_environment=args.cloud_environment, 
            pipeline_version_id=pipeline_version_info.id,
            params=pipeline_params_content
        )