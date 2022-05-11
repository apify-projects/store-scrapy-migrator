import os


def create_main_py(dst, module_name, path):
    """
    Creates main.py file and fills it with content
    :param dst: directory in which file is created
    :param module_name: name of the module with spider class
    :param path: path to the script with module
    :return: boolean of successfulness
    """
    try:
        # get relative path of main.py
        rel_path = os.path.relpath(path, dst)
        main_py = open(os.path.join(dst, "main.py"), "w")
        main_py.write(get_main_py_content(module_name, rel_path))
        main_py.close()
        print('Created main.py')
    except FileExistsError:
        print("Tried to create file 'main.py', but file already exists.")
        return False
    return True


def get_main_py_content(module_name, path):
    # override windows path style
    path = path.replace('\\', '/')
    path = path.replace('\\\\', '/')
    """
    Returns content for main.py
    :param module_name: name of the module with spider class
    :param path: path to the script with the module
    :return: str of main.py content
    """
    return f"""import os
import sys
import importlib.util
import importlib  
from apify_scrapy_executor import SpiderExecutor

from apify_client import ApifyClient

# loading spider module
spec = importlib.util.spec_from_file_location('{module_name}', '{path}')
module = importlib.util.module_from_spec(spec)
sys.modules[module.__name__] = module
spec.loader.exec_module(module)

# get input from Apify platform
client = ApifyClient(os.environ['APIFY_TOKEN'], api_url=os.environ['APIFY_API_BASE_URL'])
default_kv_store_client = client.key_value_store(os.environ['APIFY_DEFAULT_KEY_VALUE_STORE_ID'])
actor_input = default_kv_store_client.get_record(os.environ['APIFY_INPUT_KEY'])['value']

# run the spider
# TODO: shouldn't have getattr
spider_executor = SpiderExecutor(getattr(module, '{module_name}'))
spider_executor.run(dataset_id=os.environ['APIFY_DEFAULT_DATASET_ID'], args_dict=actor_input)"""


def create_input_schema(dst, name, inputs):
    """
    Creates apify.json file and fills it with content
    :param dst: directory in which file is created
    :param name: name of the spider
    :param inputs: inputs of the spider
    :return: boolean of successfulness
    """
    try:
        input_schema = open(os.path.join(dst, "INPUT_SCHEMA.json"), "w")
        content = get_input_schema_content(name, inputs)
        input_schema.write(content)
        input_schema.close()
        print('Created INPUT_SCHEMA.json')
    except FileExistsError:
        print("Tried to create file 'apify.json', but file already exists.")
        return False
    return True


def get_input_schema_content(name, inputs):
    """
    Returns content for INPUT_SCHEMA.json
    :param name: name of the module with spider class
    :param inputs: inputs to be defined
    :return: str of INPUT_SCHEMA.json content
    """
    return f"""{{
    "title": "{name} input",
    "type": "object",
    "schemaVersion": 1,
    "properties": {{
        {get_properties(inputs)[:-1]}
    }}
}}"""


def get_properties(inputs):
    properties = ''
    for inp in inputs:
        inp_type = 'string'
        editor = 'textfield'
        prefill_value = ''
        prefill = ''
        if inp[1] is not None:
            if isinstance(inp[1], int):
                inp_type = 'integer'
                editor = 'number'
                prefill_value = inp[1]
            else:
                prefill_value = f'"{inp[1]}"'
            prefill = f""",\n\t\t\t"prefill": {prefill_value}"""
        properties += f""""{inp[0]}": {{
            "title": "{inp[0]}",
            "type": "{inp_type}",
            "editor": "{editor}",
            "description": "{inp[0]}"{prefill}
        }},"""
    return properties


def create_apify_json(dst: str):
    """
    Creates apify.json file and fills it with content
    :param dst: directory in which file is created
    :return: boolean of successfulness
    """
    try:
        apify_json = open(os.path.join(dst, "apify.json"), "w")
        content = get_apify_json_content(dst)

        apify_json.write(content)
        apify_json.close()
        print('Created apify.json')
    except FileExistsError:
        print("Tried to create file 'apify.json', but file already exists.")
        return False
    return True


def get_apify_json_content(dst):
    """
    Creates content for apify.json. Reads scrapy.cfg file in @dst folder and finds for a name
    :param dst: directory in which scrapy.cfg is located
    :return: str of apify.json content
    """
    try:
        cfg = open(os.path.join(dst, "scrapy.cfg"), "r")
        line = cfg.readline()
        name = ""
        while line is not None and "[deploy]" not in line:
            line = cfg.readline()

        while line is not None and "project =" not in line:
            line = cfg.readline()

        if line is not None:
            name = line.split("=")[1].strip()

        return f"""{{
        "name": "{name}",
        "version": "0.1",
        "buildTag": "latest",
        "env": null
}}"""
    except FileNotFoundError:
        print('Could not find "scrapy.cfg" file.')
        return None


def create_dockerfile(dst):
    """
    Creates Dockerfile file and fills it with content
    :param dst: directory in which file is created
    :return: boolean of successfulness
    """
    try:
        apify_json = open(os.path.join(dst, "Dockerfile"), "w")
        apify_json.write(get_dockerfile_content())
        apify_json.close()
        print('Created Dockerfile')
    except FileExistsError:
        print("Tried to create file 'Dockerfile', but file already exists.")
        return False
    return True


def get_dockerfile_content():
    """
    Returns content for Dockerfile
    :return: str of Dockerfile content
    """
    return f"""# First, specify the base Docker image.
# You can see the Docker images from Apify at https://hub.docker.com/r/apify/.
# You can also use any other image from Docker Hub.
FROM apify/actor-python:3.9

# Second, copy just requirements.txt into the actor image,
# since it should be the only file that affects "pip install" in the next step,
# in order to speed up the build
COPY requirements.txt ./

# Install the packages specified in requirements.txt,
# Print the installed Python version, pip version
# and all installed packages with their versions for debugging
RUN echo "Python version:" \
 && python --version \
 && echo "Pip version:" \
 && pip --version \
 && echo "Installing dependencies from requirements.txt:" \
 && pip install -r requirements.txt \
 && echo "All installed Python packages:" \
 && pip freeze

# Next, copy the remaining files and directories with the source code.
# Since we do this after installing the dependencies, quick build will be really fast
# for most source file changes.
COPY . ./

# Specify how to launch the source code of your actor.
# By default, the main.py file is run
CMD python3 main.py
"""
