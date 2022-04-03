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
        main_py = open(os.path.join(dst, "main.py"), "w")
        main_py.write(get_main_py_content(module_name, path))
        main_py.close()
        print('Created main.py')
    except FileExistsError:
        print("Tried to create file 'main.py', but file already exists.")
        return False
    return True


def get_main_py_content(module_name, path):
    """
    Returns content for main.py
    :param module_name: name of the module with spider class
    :param path: path to the script with the module
    :return: str of main.py content
    """
    return f"""import os
import sys
import importlib.util

from apify_client import ApifyClient
from apify_scrapy_executor import SpiderExecutor

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
        print('Created apify.json')
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
    properties = ''

    for inp in inputs:
        inp_type = 'string'
        prefill = ''
        if inp[1] is not None:
            if inp[1].isdigit() or (inp[1][0] == '-' and inp[1][1:].isdigit()):
                inp_type = 'integer'
            prefill = f""",\n\t\t\t"prefill": "{inp[1]}\""""
        properties += f""""{inp[0]}": {{
            "title": "{inp[0]}",
            "type": "{inp_type}",
            "description": "{inp[0]}"{prefill}
        }},"""

    return f"""{{
    "title": "{name} input",
    "type": "object",
    "schemaVersion": 1,
    "properties": {{
        {properties[:-1]}
    }}
}}"""


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
        "version": "0.0.1",
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
    return f"""FROM apify/actor-python:3.9
CMD pipreqs --force

COPY requirements.txt ./

RUN echo "Python version:" \
 && python --version \
 && echo "Pip version:" \
 && pip --version \
 && echo "Installing dependencies from requirements.txt:" \
 && pip install -r requirements.txt \
 && echo "All installed Python packages:" \
 && pip freeze
COPY . ./

CMD python3 main.py"""
