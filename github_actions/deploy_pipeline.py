from kfp import Client
from client import get_kubeflow_client
import argparse
import datetime
from yaml import safe_load
import json
import os
import sys

# build pipeline package and upload pipeline package as a new pipeline version
def deploy_pipeline(
    kfp_client_dict:dict,
    kfp_namespace:str,
    pipeline_yaml_path:str, 
    pipeline_version_name:str, 
    ):

    # get kfp client connection
    kfp_client = kfp_client_dict["data"]   
    kfp_client.set_user_namespace(kfp_namespace)

    # check pipeline existence
    with open(pipeline_yaml_path, 'r') as yml:
        pipeline_yaml = safe_load(yml)
    pipeline_name = pipeline_yaml['spec']['entrypoint']
    pipeline_desc = pipeline_yaml['metadata']['annotations']
    pipeline_id = kfp_client.get_pipeline_id(pipeline_name)

    # upload package as a new pipeline if specified pipeline already exists
    if pipeline_id == None:
        try:
            pipeline_info = kfp_client.upload_pipeline(
                pipeline_package_path=pipeline_yaml_path,
                pipeline_name=pipeline_name,
                description=pipeline_desc
                )
            # print('new pipeline has been successfully uploaded')
            print(pipeline_info)
        except Exception as e:
            print(e)
            return None

    try:
        pipeline_version_info = kfp_client.upload_pipeline_version(
            pipeline_package_path=pipeline_yaml_path,
            pipeline_name=pipeline_name,
            pipeline_version_name=pipeline_version_name,
            description=pipeline_desc
        )
        print(pipeline_version_info)
        return(pipeline_version_info)

    except Exception as e:
        print(e)
        return None

# create run of pipeline
def run_pipeline(
    kfp_client_dict:dict,
    kfp_namespace:str,
    kfp_experinment_name:str,
    pipeline_version_id:str,
    params:str = None 
    ):

    # get kfp client connection
    kfp_client = kfp_client_dict["data"]   
    kfp_client.set_user_namespace(kfp_namespace)

    # get experiment id by name
    experiment_info = kfp_client.get_experiment(experiment_name=kfp_experinment_name, namespace=kfp_namespace)

    # generate job name
    t_delta = datetime.timedelta(hours=9)
    JST = datetime.timezone(t_delta, 'JST')
    now = datetime.datetime.now(JST)
    # timestamp = now.strftime('%Y%m%d%H%M%S') # YYYYMMDDhhmmss
    job_name = "Run at " + str(now)

    # create run
    try:
        run_info = kfp_client.run_pipeline(
            experiment_id=experiment_info.id,
            version_id=pipeline_version_id,
            job_name=job_name,
            params=params
        )
        print(run_info)
        return run_info

    except Exception as e:
        print(e)
        return None


if __name__ == "__main__":
    # define command line arguments 
    parser = argparse.ArgumentParser()
    parser.add_argument('--k8s-context', help="kubeconfig context name", required=True)
    parser.add_argument('--kf-endpoint', help="kubeflow endpoint", required=True)
    parser.add_argument('--kf-username', help="kubeflow username", required=True)
    parser.add_argument('--kf-password', help="kubeflow password", required=True)
    parser.add_argument('--namespace', help="kubeflow profile", required=True)
    parser.add_argument('--kf-experiment-name', help="kubeflow experiment name", required=True)
    parser.add_argument('--pipeline-package-path', help="pipeline package path", required=True)
    parser.add_argument('--pipeline-version', help="pipeline version name", required=True)
    parser.add_argument('--deploy-only', action='store_true', help="specify if you don't want to run pipeline")
    parser.add_argument('--output-file', help="specify file path if you want to store output into a file")
    args = parser.parse_args()

    # get kfp client
    kfp_client_dict = get_kubeflow_client(
        kubeconfig_context = args.k8s_context,
        kubeflow_endpoint = args.kf_endpoint,
        kubeflow_username = args.kf_username,
        kubeflow_password = args.kf_password
    )

    # deploy pipeline
    pipeline_version_info = deploy_pipeline(
        kfp_client_dict = kfp_client_dict, 
        kfp_namespace = args.namespace,
        pipeline_yaml_path = args.pipeline_package_path,
        pipeline_version_name = args.pipeline_version
        )
    if pipeline_version_info == None:
        sys.exit(1)
            
    # run pipeline
    if args.deploy_only:
        sys.exit(0)
    else:
        # read params file
        pipeline_params_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
        pipeline_params_file = os.path.join(pipeline_params_dir, "pipeline_params.yaml")
        with open(pipeline_params_file, 'r') as yml:
            pipeline_params_content = safe_load(yml)

        # run pipeline
        run_info = run_pipeline(
            kfp_client_dict = kfp_client_dict, 
            kfp_namespace = args.namespace,
            kfp_experinment_name = args.kf_experiment_name,
            pipeline_version_id = pipeline_version_info.id,
            params = pipeline_params_content
        )
        if run_info == None:
            sys.exit(1)
    
        # for github actions
        if args.output_file:
            with open(args.output_file, mode='w') as f:
                f.write(run_info.id)
        
        sys.exit(0)