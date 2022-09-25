import os
import re
import subprocess


##########################################
# requirements.txt
##########################################
def update_reqs(dst):
    """
    Creates or updates requirements.txt of a project. Runs pipreqs. If requirements exists, appends with pipreqs result
    :param dst: destination of scrapy project
    :return: boolean of successfulness
    """

    # check correct dst
    if not os.path.exists(os.path.join(dst, 'scrapy.cfg')):
        print('Select root directory with "scrapy.cfg" file.')
        return False

    import pipreqs
    reqs_file = os.path.join(dst, 'requirements.txt')

    # check if requirements.txt exists
    if not os.path.exists(os.path.join(dst, 'requirements.txt')):

        # compat mode for ~= requirements, supress output
        subprocess.run(["pipreqs", dst, "--mode", "compat"], stderr=subprocess.DEVNULL)
        with open(reqs_file, 'r') as reqs:
            unsafe_split_lines = [re.split('[~=<]=', x) for x in reqs.read().splitlines(keepends=False)]
            lines = remove_invalid_reqs(unsafe_split_lines)
        with open(reqs_file, 'w') as reqs:
            reqs.writelines([x[0] + '~=' + x[1] + '\n' for x in lines])
        print('Created requirements.txt')
        return True

    # create tmp file to save user requirements and call pipreqs
    reqs_tmp = os.path.join(dst, '.tmp_reqs.tmp_apify')

    if os.path.exists(reqs_tmp):
        # if tmp file exists, removes it. It should be created only in runs before and shouldn't be user's file.
        os.remove(reqs_tmp)

    os.rename(reqs_file, reqs_tmp)
    subprocess.run(["pipreqs", dst, "--mode", "compat"], stderr=subprocess.DEVNULL)

    # check for duplicates
    with open(reqs_file, 'r') as reqs:
        reqs_lines = reqs.read().splitlines(keepends=False)
    with open(reqs_tmp, 'r') as tmp:
        tmp_lines = tmp.read().splitlines(keepends=False)

    complete_reqs = concat_dedup_reqs(reqs_lines, tmp_lines)

    with open(reqs_file, 'w') as reqs:
        for req in complete_reqs:
            reqs.write(req + '\n')

    os.remove(reqs_tmp)
    print('Created requirements.txt')
    return True


def concat_dedup_reqs(reqs_lines, user_lines):
    """
    Check lines of requirements and concatenates them and removes duplicates. Users' versions will be preferred
    :param reqs_lines array of lines of the first requirements file
    :param user_lines array of lines of the second requirements file
    """
    # split module name and version number
    reqs_arr = [re.split('[~=<]=', line) for line in reqs_lines]
    unsafe_tmp_arr = [re.split('[~=<]=', line) for line in user_lines]

    # removes modules with non-numeric version
    # bug of pipreqs which adds 'apify_scrapy_executor.egg==info' to requirements
    user_arr = remove_invalid_reqs(unsafe_tmp_arr)

    res = []
    status = ('', -1)

    for req in reqs_arr:
        # skips modules with non-numeric version
        if not is_valid_version(req[1]):
            continue

        for i in range(len(user_arr)):
            if req[0] in user_arr[i]:
                # duplicate name found
                status = ('duplicate', i)
                if req[1] == user_arr[i][1]:
                    # same version
                    res.append(req[0] + '~=' + req[1])
                else:
                    # choose users_version version
                    res.append(req[0] + '==' + user_arr[i][1])
                break
            else:
                # not duplicate
                res.append(req[0] + '~=' + req[1])

        if status[0] == 'duplicate':
            # remove duplicate from tmp
            user_arr.remove(user_arr[status[1]])
            status = ('', -1)

    # append reqs left in tmp
    for req_left in user_arr:
        res.append(req_left[0] + '~=' + req_left[1])

    return res


def remove_invalid_reqs(req_lines):
    """
    Removes modules with non-numeric version. Bug of pipreqs which adds 'apify_scrapy_executor.egg==info'
    :param req_lines lines from requirements file
    :returns array of safe lines
    """
    safe_lines = []
    for req in req_lines:
        if is_valid_version(req[1]):
            safe_lines.append(req)
    return safe_lines


def is_valid_version(v):
    """
    Check if all values of version number separated by '.' is a numeric value
    :returns boolean
    """
    return not (False in [x.isnumeric() for x in v.split('.')])


##########################################
# main.py
##########################################
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


##########################################
# INPUT_SCHEMA.json
##########################################
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
    """
    Creates properties for each input
    :param inputs: inputs to be defined
    :return: str of properties
    """
    properties = ''
    for inp in inputs:
        inp_type = 'string'
        editor = 'textfield'
        prefill = ''
        if inp[1] is not None:
            if isinstance(inp[1], int):
                inp_type = 'integer'
                editor = 'number'
                prefill_value = inp[1]
            else:
                prefill_value = f'"{inp[1]}"'
            prefill = f""",\n\t\t\t"default": {prefill_value}"""
        properties += f""""{inp[0]}": {{
            "title": "{inp[0]}",
            "type": "{inp_type}",
            "editor": "{editor}",
            "description": "{inp[0]}"{prefill}
        }},"""
    return properties


##########################################
# apify.json
##########################################
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


##########################################
# Dockerfile
##########################################
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


##########################################
# README.md
##########################################
def create_readme(dst, spider_name):
    """
    Creates Readme file and fills it with content
    :param dst: directory in which file is created
    :param spider_name: name of the spider
    :return: boolean of successfulness
    """
    try:
        apify_json = open(os.path.join(dst, "README.md"), "w")
        apify_json.write(get_readme_content(spider_name))
        apify_json.close()
        print('Created README.md')
    except FileExistsError:
        print("Tried to create file 'README.md', but file already exists.")
        return False
    return True


def get_readme_content(spider_name):
    """
    Returns content for README.md
    :param spider_name: name of the spider
    :return: str of README.md content
    """
    return f"""# Apify Scrapy {spider_name} project

This file is generated by [Apify Scrapy Migrator](https://pypi.org/project/apify-scrapy-migrator/)

The `README.md` file contains a documentation what your actor does and how to use it,
which is then displayed in the app or Apify Store. It's always a good
idea to write a good `README.md`, in a few months not even you
will remember all the details about the actor.

You can use [Markdown](https://www.markdownguide.org/cheat-sheet)
language for rich formatting.

## Documentation reference

- [Apify Client for Python documentation](https://docs.apify.com/apify-client-python)
- [Apify Actor documentation](https://docs.apify.com/actor)
- [Apify CLI](https://docs.apify.com/cli)

## Writing a README

See our tutorial on [writing README's for your actors](
https://help.apify.com/en/articles/2912548-how-to-write-great-readme-for-your-actors) if you need more inspiration. 

### Table of contents

If your README requires a table of contents, use the template below and make sure to keep the `<!-- toc start -->` 
and `<!-- toc end -->` markers. 

<!-- toc start -->
- Introduction
- Use Cases
  - Case 1
  - Case 2
- Input
- Output
- Miscellaneous
<!-- toc end -->"""
